from flask import jsonify, request
from backend.models import Alert
from backend.extensions import db
from backend.state import state # Shared State

class DashboardController:
    @staticmethod
    def update_counts():
        # Legacy Endpoint Support (Optional, mostly unused now if thread is active)
        # But we can keep it to allow external updates if needed, pushing to state
        global live_counts
        # For simplicity, we just ignore this or map it to state.update if truly needed
        # But main.py now calls state.update direct.
        
        return jsonify({"status": "deprecated, use shared state"}), 200

    @staticmethod
    def get_live_data():
        try:
            from backend.models import Alert, Zone
            import datetime
            
            # GET FROM SHARED STATE
            live_counts = state.get_data()
            
            # 1. Alert Count (Last 24h)
            cutoff = datetime.datetime.now() - datetime.timedelta(hours=24)
            alert_count = db.session.query(Alert).filter(Alert.timestamp >= cutoff).count()
            live_counts['alert_count'] = alert_count
            
            # 2. Active Cameras
            live_counts['active_cameras'] = len(live_counts.get('cameras', {}))
            
            # 3. Sync Thresholds from DB (Source of Truth)
            db_zones = {z.name: z.threshold for z in Zone.query.all()}
            current_zones = live_counts.get("zones", [])
            
            def sync_threshold(z_item):
                if not isinstance(z_item, dict): return
                raw_name = z_item.get('name', '')
                
                # Robust matching
                candidates = [raw_name]
                if ':' in raw_name:
                    parts = raw_name.split(':')
                    if len(parts) > 1:
                        candidates.append(parts[1].strip()) 
                
                for c in candidates:
                    if c in db_zones:
                        z_item['threshold'] = db_zones[c]
                        break

            if isinstance(current_zones, list):
                for z in current_zones: sync_threshold(z)
            elif isinstance(current_zones, dict):
                # Logic to convert dict to flat list for dashboard if needed?
                # Actually dashboard.html handles both? Let's assume yes or sync deeply
                for cam_id, z_list in current_zones.items():
                    for z in z_list: sync_threshold(z)
                    
        except Exception as e:
            print(f"Live Data Error: {e}")
            return jsonify({}), 500
            
        return jsonify(live_counts), 200

    @staticmethod
    def get_analytics():
        try:
            # Prefer in-memory high-freq history if available
            # Downsample to 1-minute intervals for cleaner chart
            global trend_history
            
            # Helper to downsample
            def downsample(raw_data, time_key='time', val_key='count'):
                sampled = {}
                for item in raw_data:
                    # Parse time if string, else assume string HH:MM:SS
                    # We expect HH:MM:SS string in trend_history
                    t_str = item[time_key] 
                    # Extract HH:MM
                    hm = t_str[:5] if len(t_str) >= 5 else t_str
                    
                    # Store last value for that minute (most recent)
                    sampled[hm] = item[val_key]
                
                return list(sampled.keys()), list(sampled.values())

            if trend_history:
                labels, data = downsample(trend_history)
                return jsonify({"labels": labels, "data": data}), 200

            # Fallback
            from backend.models import AnalyticsData
            import datetime
            now = datetime.datetime.now()
            start_time = now - datetime.timedelta(hours=1)
            data_points = AnalyticsData.query.filter(
                AnalyticsData.zone_name == '_GLOBAL_OCCUPANCY_',
                AnalyticsData.timestamp >= start_time
            ).order_by(AnalyticsData.timestamp).all()
            
            # Convert DB objects to dict for same helper
            db_data = [{'time': dp.timestamp.strftime('%H:%M:%S'), 'count': dp.count} for dp in data_points]
            labels, data = downsample(db_data)
            
            return jsonify({"labels": labels, "data": data}), 200
        except Exception as e:
            print(f"Analytics Error: {e}")
            return jsonify({"labels": [], "data": []}), 500

    @staticmethod
    def get_analytics_summary():
        # ... (analytics logic unchanged, assuming it queries DB)
        try:
            from backend.models import AnalyticsData
            import datetime
            from sqlalchemy import func
            
            # Date Filter
            date_str = request.args.get('date')
            if date_str:
                try:
                    target_date = datetime.datetime.strptime(date_str, '%Y-%m-%d')
                except:
                    target_date = datetime.datetime.now()
            else:
                target_date = datetime.datetime.now()

            start_dt = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
            end_dt = start_dt + datetime.timedelta(days=1)
            
            # 1. Peak Occupancy (Target Day)
            peak_val = db.session.query(func.max(AnalyticsData.count)).filter(
                AnalyticsData.zone_name == '_GLOBAL_OCCUPANCY_',
                AnalyticsData.timestamp >= start_dt,
                AnalyticsData.timestamp < end_dt
            ).scalar() or 0
            
            # 2. Avg Occupancy (Target Day)
            avg_val = db.session.query(func.avg(AnalyticsData.count)).filter(
                AnalyticsData.zone_name == '_GLOBAL_OCCUPANCY_',
                AnalyticsData.timestamp >= start_dt,
                AnalyticsData.timestamp < end_dt
            ).scalar() or 0
            
            # 3. Hourly Trend (Target Day) - Average Occupancy
            data_points = AnalyticsData.query.filter(
                AnalyticsData.zone_name == '_GLOBAL_OCCUPANCY_',
                AnalyticsData.timestamp >= start_dt,
                AnalyticsData.timestamp < end_dt
            ).all()
            
            hourly_sums = {} # hour -> sum
            hourly_counts = {} # hour -> count of records
            
            for dp in data_points:
                h = dp.timestamp.strftime("%H")
                if h not in hourly_sums: 
                    hourly_sums[h] = 0
                    hourly_counts[h] = 0
                hourly_sums[h] += dp.count
                hourly_counts[h] += 1
                
            hourly_data = [0] * 24
            for h_str, total in hourly_sums.items():
                avg = total / hourly_counts[h_str]
                hourly_data[int(h_str)] = round(avg)
                
            # 4. Zone Distribution
            zone_dist = []
            total_current = 0
            current_zones_list = []
            
            # Use Shared State for CURRENT zones data
            live_counts = state.get_data()
            c_zones = live_counts.get("zones", [])
            
            if isinstance(c_zones, dict):
                 for k, v in c_zones.items(): current_zones_list.extend(v)
            elif isinstance(c_zones, list):
                 current_zones_list = c_zones
            
            for z in current_zones_list:
                total_current += z.get('count', 0)
                
            if total_current > 0:
                for z in current_zones_list:
                     zone_dist.append({
                         "name": z.get('name'),
                         "count": z.get('count', 0),
                         "pct": round((z.get('count', 0) / total_current) * 100, 1)
                     })
            
            return jsonify({
                "peak_occupancy": peak_val,
                "avg_occupancy": round(avg_val, 1),
                "hourly_trend": hourly_data,
                "zone_distribution": zone_dist
            }), 200

        except Exception as e:
            print(f"Analytics Summary Error: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"error": str(e)}), 500
        
    @staticmethod
    def proxy_update_zones():
        pass


def get_commands():
    # Deprecated: usage should go through state manager directly in main.py
    return jsonify([]), 200

def post_command():
    data = request.get_json()
    state.queue_command(data)
    return jsonify({"status": "queued"}), 200

