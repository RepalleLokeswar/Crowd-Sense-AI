from flask import jsonify, request
from backend.models import Alert
from backend.extensions import db

# In-Memory Store for Real-Time Data from Main.py
live_counts = {
    "live_count": 0,
    "people_count": 0,
    "total_visitors": 0,
    "zones": {},
    "cameras": {}
}

class DashboardController:
    @staticmethod
    def update_counts():
        global live_counts
        from backend.models import Zone, Alert, AnalyticsData
        import datetime
        
        try:
            data = request.get_json()
            if not data:
                return jsonify({"status": "ignored"}), 200

            # print(f"DEBUG: Payload received with keys: {list(data.keys())}")
            live_counts.update(data)
            
            # --- Persistence: Update In-Memory Trend History ---
            global trend_history
            now_str = datetime.datetime.now().strftime("%H:%M:%S")
            p_count = live_counts.get('people_count', 0)
            
            # Append new point
            trend_history.append({"time": now_str, "count": p_count})
            
            # Prune (Keep last 100 points ~ 3 minutes of 2s updates)
            if len(trend_history) > 100:
                trend_history.pop(0)

            # --- Global Occupancy Tracking (Every Minute) ---
            should_save = False
            last_global = AnalyticsData.query.filter_by(zone_name='_GLOBAL_OCCUPANCY_').order_by(AnalyticsData.timestamp.desc()).first()
            
            if not last_global:
                should_save = True
            else:
                now = datetime.datetime.now()
                if (now - last_global.timestamp).total_seconds() >= 60:
                    should_save = True
            
            if should_save:
                # Save global count
                g_record = AnalyticsData(zone_name='_GLOBAL_OCCUPANCY_', count=live_counts.get('people_count', 0))
                db.session.add(g_record)
                db.session.commit()

            # --- Alert Logic ---
            current_zones = live_counts.get("zones", [])
            
            # Handle list or dict format
            zone_list = []
            if isinstance(current_zones, dict):
                for k, v in current_zones.items(): zone_list.extend(v)
            elif isinstance(current_zones, list):
                zone_list = current_zones
            
            # Load Thresholds
            db_zones = {z.name: z.threshold for z in Zone.query.all()}
            
            for z in zone_list:
                name = z.get('name', '').replace('C0: ', '').replace('C1: ', '')
                threshold = db_zones.get(name, 1000)
                count = z.get('count', 0)
                
                if count > threshold:
                    recent = Alert.query.filter_by(zone_name=name).order_by(Alert.timestamp.desc()).first()
                    # Fix: Use python datetime for comparison, not SQL func
                    if not recent or (datetime.datetime.now() - recent.timestamp).total_seconds() > 60:
                        new_alert = Alert(zone_name=name, message=f"Occupancy exceeded! ({count}/{threshold})")
                        db.session.add(new_alert)
                        db.session.commit()
                        print(f"ALERT: {name} is overcrowded!")

        except Exception as e:
            print(f"Error in Logic: {e}")

        # Access global queue directly
        global command_queue
        cmds = list(command_queue)
        command_queue.clear()
        
        return jsonify({"status": "updated", "commands": cmds}), 200

    @staticmethod
    def get_live_data():
        try:
            from backend.models import Alert, Zone
            import datetime
            
            # 1. Alert Count (Last 24h)
            cutoff = datetime.datetime.now() - datetime.timedelta(hours=24)
            alert_count = db.session.query(Alert).filter(Alert.timestamp >= cutoff).count()
            live_counts['alert_count'] = alert_count
            
            # 2. Active Cameras
            live_counts['active_cameras'] = len(live_counts.get('cameras', {}))
            
            # 3. Sync Thresholds from DB (Source of Truth)
            # This ensures dashboard shows updated thresholds immediately after save
            db_zones = {z.name: z.threshold for z in Zone.query.all()}
            current_zones = live_counts.get("zones", [])
            
            # Debug Log (Throttle? One per request might be spammy, but useful for one-shot debug)
            # with open("debug_log.txt", "a") as log:
            #    log.write(f"Live Sync: DB Zones keys: {list(db_zones.keys())}\n")

            def sync_threshold(z_item):
                if not isinstance(z_item, dict): return
                raw_name = z_item.get('name', '')
                
                # Robust matching: try exact, then exact split, then loose split
                candidates = [raw_name]
                if ':' in raw_name:
                    parts = raw_name.split(':')
                    if len(parts) > 1:
                        candidates.append(parts[1].strip()) # "C1: Name" -> "Name"
                
                matched = False
                for c in candidates:
                    if c in db_zones:
                        old_t = z_item.get('threshold')
                        new_t = db_zones[c]
                        z_item['threshold'] = new_t
                        matched = True
                        break
                
                # if not matched:
                #    with open("debug_log.txt", "a") as log:
                #        log.write(f"FAILED MATCH: {raw_name} against {list(db_zones.keys())}\n")

            if isinstance(current_zones, list):
                for z in current_zones: sync_threshold(z)
            elif isinstance(current_zones, dict):
                for cam_id, z_list in current_zones.items():
                    for z in z_list: sync_threshold(z)
                    
        except Exception as e:
            with open("debug_log.txt", "a") as log:
                log.write(f"Live Data Error: {e}\n")
            print(f"Live Data Error: {e}")
            
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
        # Proxy 'update_zones' command to Main.py
        pass

# Command Queue for Main.py
command_queue = []
# In-Memory Trend History (High Frequency)
trend_history = []  # List of {"time": str, "count": int}

def get_commands():
    global command_queue
    cmds = list(command_queue)
    command_queue.clear()
    return jsonify(cmds), 200

def post_command():
    data = request.get_json()
    command_queue.append(data)
    return jsonify({"status": "queued"}), 200
