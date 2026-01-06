from flask import jsonify, request
from flask_jwt_extended import create_access_token
from backend.models import User, Zone, Alert
from backend.extensions import db
from backend.state import state # Shared State
from werkzeug.security import check_password_hash
import subprocess
import sys
import os
import json

# Global process handle deprecated - we use Thread + State now
# But we can keep variable for compatibility if needed, though it's unused

class AdminController:
    # --- Auth ---
    @staticmethod
    def signup():
        try:
            data = request.get_json()
            username = data.get('username')
            password = data.get('password')
            role = data.get('role', 'user')
            admin_key = data.get('admin_key')

            if User.query.filter_by(username=username).first():
                return jsonify({"msg": "Username already exists"}), 400

            if role == 'admin' and admin_key != "admin123": # Simple secret key
                return jsonify({"msg": "Invalid Admin Key"}), 403

            from werkzeug.security import generate_password_hash
            new_user = User(username=username, password=generate_password_hash(password), role=role)
            db.session.add(new_user)
            db.session.commit()
            
            AdminController.log_event("User Signup", f"New user '{username}' registered as {role}")
            return jsonify({"message": "User created successfully"}), 201
        except Exception as e:
            print(f"SIGNUP ERROR: {e}")
            return jsonify({"msg": f"Server Error: {str(e)}"}), 500

    @staticmethod
    def login():
        try:
            data = request.get_json()
            # print(f"DEBUG LOGIN ATTEMPT: Username='{data.get('username')}' Password='{data.get('password')}'")
            user = User.query.filter_by(username=data.get('username')).first()
            if user and check_password_hash(user.password, data.get('password')):
                 # Role check
                 role = getattr(user, 'role', 'user') # Safe access
                 
                 identity_str = str(user.id)
                 
                 try:
                     token = create_access_token(identity=identity_str, additional_claims={"role": role})
                 except Exception as token_err:
                     raise token_err
                     
                 AdminController.log_event("User Login", f"User '{user.username}' logged in", user=user.username)
                 return jsonify(token=token, role=role, username=user.username), 200
            return jsonify({"msg": "Invalid credentials"}), 401
        except Exception as e:
            print(f"LOGIN ERROR TRACEBACK: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({"msg": f"Server Error: {str(e)}"}), 500

    @staticmethod
    def get_profile(current_user_id):
        user = User.query.get(current_user_id)
        if user:
            return jsonify(username=user.username, role=user.role), 200
        return jsonify({"msg": "User not found"}), 404

    # --- System Control ---
    @staticmethod
    def start_system(current_user):
        from backend.system_manager import start_unified_detection
        
        data = request.get_json() or {}
        source = data.get('source', '0')
        
        msg = start_unified_detection(source)
        
        # Check if it was an error message or success
        if "Error" in msg or "Failed" in msg:
            return jsonify({"message": msg}), 500
            
        AdminController.log_event("System Start", f"Detection started/resumed with source {source}")
        return jsonify({"message": msg}), 200

    @staticmethod
    def stop_system(current_user):
        # Signal Stop Event
        if state.detection_thread and state.detection_thread.is_alive():
            state.stop_event.set()
            AdminController.log_event("System Stop", "Detection stop signal sent")
            return jsonify({"message": "Stop signal sent. System stopping..."}), 200
        else:
             return jsonify({"message": "System is not running."}), 200

    @staticmethod
    def get_system_status(current_user):
        # We assume running if app is up, or check stop_event
        is_running = not state.stop_event.is_set()
        return jsonify({"running": is_running}), 200

    # --- Camera Management ---
    @staticmethod
    def get_cameras(current_user):
        return jsonify(state.get_data().get("cameras", {})), 200

    @staticmethod
    def add_camera(current_user):
        return jsonify({"message": "Camera added"}), 201

    @staticmethod
    def delete_camera(current_user, cam_id):
        return jsonify({"message": "Camera deleted"}), 200

    # --- Zone Management ---
    @staticmethod
    def get_zones(current_user):
        source = request.args.get('source', '0')
        filepath = f"zones/zones_source_{source}.json"
        
        zones_data = []
        if os.path.exists(filepath):
            try:
                with open(filepath, 'r') as f:
                    zones_data = json.load(f)
            except: pass
            
        formatted_zones = {}
        for z in zones_data:
            zid = str(z.get('id', 'unknown'))
            formatted_zones[zid] = {
                "name": z.get('id'), # logic uses ID as name often
                "points_json": json.dumps(z.get('coords', [])),
                "threshold": z.get('threshold', 10)
            }
            
        return jsonify({"configured_zones": formatted_zones, "live_zones": state.get_data().get("zones", [])}), 200

    @staticmethod
    def update_zones_config(current_user):
        data = request.get_json()
        action = data.get('action') 
        source = data.get('source', '0')
        
        if action == 'save_zones':
             new_zones = data.get('zones', [])
             
             # 1. Save to File
             json_zones = []
             for z_data in new_zones:
                 json_zones.append({
                     "id": z_data.get('name') or z_data.get('id'),
                     "coords": z_data.get('coords', []),
                     "threshold": int(z_data.get('threshold', 10))
                 })
             
             filepath = f"zones/zones_source_{source}.json"
             os.makedirs("zones", exist_ok=True)
             try:
                 with open(filepath, "w") as f:
                     json.dump(json_zones, f, indent=4)
             except Exception as e:
                 return jsonify({"message": f"Failed to save file: {e}"}), 500

             # 2. Update Database (Source of Truth for Dashboard)
             try:
                 for z_data in new_zones:
                     name = z_data.get('name') or z_data.get('id')
                     threshold = int(z_data.get('threshold', 10))
                     coords = json.dumps(z_data.get('coords', []))
                     
                     zone = Zone.query.filter_by(name=name).first()
                     if zone:
                         zone.threshold = threshold
                         zone.points_json = coords
                     else:
                         zone = Zone(name=name, threshold=threshold, points_json=coords)
                         db.session.add(zone)
                 
                 db.session.commit()
             except Exception as e:
                 print(f"DB Update Error: {e}")

             # 3. Push Command via Shared State
             cmd = {
                 "action": "update_zones",
                 "cam_id": f"C{int(source)+1}",
                 "zones": json_zones
             }
             state.queue_command(cmd)
             
             AdminController.log_event("Zones Updated", f"Zone configuration saved for Source {source} ({len(json_zones)} zones)")
             return jsonify({"message": "Zones saved and command queued"}), 200
             
        return jsonify({"message": "Invalid action"}), 400

    # --- Export ---
    @staticmethod
    def export_data(current_user):
        import csv
        import io
        from flask import make_response
        
        fmt = request.args.get('format', 'csv')
        
        # Use Shared State
        live_counts = state.get_data()
        
        zones = Zone.query.all()
        current_counts = live_counts.get("zones", [])
        
        if fmt == 'pdf':
            from reportlab.lib.pagesizes import letter
            from reportlab.pdfgen import canvas
            from datetime import datetime
            
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=letter)
            width, height = letter
            
            # Title
            p.setFont("Helvetica-Bold", 16)
            p.drawString(50, height - 50, "CrowdSense AI - System Report")
            
            p.setFont("Helvetica", 12)
            p.drawString(50, height - 70, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            p.drawString(50, height - 90, f"Generated By: {current_user}")
            
            # --- Dashboard Summary ---
            p.setFont("Helvetica-Bold", 14)
            p.drawString(50, height - 130, "System Overview")
            
            p.setFont("Helvetica", 12)
            p.drawString(50, height - 150, f"Live Occupancy: {live_counts.get('people_count', 0)}")
            p.drawString(250, height - 150, f"Total Visitors: {live_counts.get('total_visitors', 0)}")
            p.drawString(450, height - 150, f"Active Alerts: {live_counts.get('alert_count', 0)}")

            p.line(50, height - 160, 550, height - 160)

            # Counts
            y = height - 200
            p.setFont("Helvetica-Bold", 14)
            p.drawString(50, y, "Zone Details")
            y -= 30
            
            p.setFont("Helvetica-Bold", 10)
            p.drawString(50, y, "Zone Name")
            p.drawString(250, y, "Threshold")
            p.drawString(350, y, "Current Count")
            p.drawString(450, y, "Status")
            y -= 20
            p.line(50, y+10, 550, y+10)
            
            p.setFont("Helvetica", 10)
            p.setFont("Helvetica", 10)
            
            # Use Live Zones instead of DB Zones (Source of Truth is JSON/Main.py)
            current_zones_data = live_counts.get("zones", {})
            flattened_zones = []
            if isinstance(current_zones_data, dict):
                for k, v in current_zones_data.items(): flattened_zones.extend(v)
            elif isinstance(current_zones_data, list):
                flattened_zones = current_zones_data
                
            # Try to fetch thresholds from DB for reference, else default
            db_zones_map = {z.name: z.threshold for z in Zone.query.all()}
            
            for z_item in flattened_zones:
                name = z_item.get('name', 'Unknown')
                count = z_item.get('count', 0)
                threshold = db_zones_map.get(name, 20) # Default set to 20 as per request
                
                status = "Normal"
                if count > threshold: 
                    status = "OVERCROWDED"
                    p.setFillColorRGB(1, 0, 0)
                else:
                    p.setFillColorRGB(0, 0, 0)
                    
                p.drawString(50, y, str(name))
                p.drawString(250, y, str(threshold))
                p.drawString(350, y, str(count))
                p.drawString(450, y, status)
                y -= 20
                if y < 50:
                    p.showPage()
                    y = height - 50
            
            p.save()
            buffer.seek(0)
            response = make_response(buffer.getvalue())
            response.headers["Content-Disposition"] = "attachment; filename=crowd_report.pdf"
            response.headers["Content-type"] = "application/pdf"
            return response
        else:
            # CSV Default
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Summary Section
            writer.writerow(['--- System Overview ---'])
            writer.writerow(['Live Occupancy', live_counts.get('people_count', 0)])
            writer.writerow(['Total Visitors', live_counts.get('total_visitors', 0)])
            writer.writerow(['Active Alerts', live_counts.get('alert_count', 0)])
            writer.writerow([]) # Spacer
            
            # Zone Section
            writer.writerow(['--- Zone Details ---'])
            writer.writerow(['Zone Name', 'Threshold', 'Current Live Count', 'Status'])
            
            current_zones_data = live_counts.get("zones", {})
            flattened_zones = []
            if isinstance(current_zones_data, dict):
                for k, v in current_zones_data.items(): flattened_zones.extend(v)
            elif isinstance(current_zones_data, list):
                flattened_zones = current_zones_data
            
            db_zones_map = {z.name: z.threshold for z in Zone.query.all()}

            for z_item in flattened_zones:
                name = z_item.get('name', 'Unknown')
                count = z_item.get('count', 0)
                threshold = db_zones_map.get(name, 10)
                
                status = "Normal"
                if count > threshold: status = "Overcrowded"
                writer.writerow([name, threshold, count, status])
                
            output.seek(0)
            
            response = make_response(output.getvalue())
            response.headers["Content-Disposition"] = "attachment; filename=crowd_report.csv"
            response.headers["Content-type"] = "text/csv"
            return response

    # --- Alerts ---
    @staticmethod
    def get_alerts(current_user):
        alerts = Alert.query.order_by(Alert.timestamp.desc()).limit(10).all()
        return jsonify([{
            "id": a.id, "zone_name": a.zone_name, 
            "message": a.message, "timestamp": a.timestamp.isoformat()
        } for a in alerts]), 200

    # --- Logs ---
    @staticmethod
    def get_logs(current_user):
        from ..models import SystemLog
        logs = SystemLog.query.order_by(SystemLog.timestamp.desc()).limit(50).all()
        return jsonify([{
            "timestamp": l.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            "event": l.event,
            "description": l.description,
            "user": l.user
        } for l in logs]), 200
    
    @staticmethod
    def log_event(event, description, user="System"):
        from ..models import SystemLog
        try:
            log = SystemLog(event=event, description=description, user=user)
            db.session.add(log)
            db.session.commit()
        except: pass
