from flask import jsonify, request
from flask_jwt_extended import create_access_token
from backend.models import User, Zone, Alert
from backend.extensions import db
from werkzeug.security import check_password_hash
import subprocess
import sys
import os
import json
from .dashboard_controller import live_counts

# Global process handle
system_process = None

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
            print(f"DEBUG LOGIN ATTEMPT: Username='{data.get('username')}' Password='{data.get('password')}'")
            user = User.query.filter_by(username=data.get('username')).first()
            if user and check_password_hash(user.password, data.get('password')):
                 # Role check
                 role = getattr(user, 'role', 'user') # Safe access
                 
                 print(f"DEBUG: User ID: {user.id} Type: {type(user.id)}")
                 identity_str = str(user.id)
                 print(f"DEBUG: Identity String: '{identity_str}' Type: {type(identity_str)}")
                 
                 try:
                     token = create_access_token(identity=identity_str, additional_claims={"role": role})
                     print("DEBUG: Token created successfully")
                 except Exception as token_err:
                     print(f"DEBUG: Token Creation Failed: {token_err}")
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
        global system_process
        if system_process is None or system_process.poll() is not None:
            data = request.get_json() or {}
            source = data.get('source')

            if not source:
                 return jsonify({"message": "Source is required."}), 400
            
            # Using sys.executable to ensure correct python env
            cmd = [sys.executable, "-u", "main.py", "--source", str(source), "--headless"]
            
            
            
            # Redirect Output to Log
            try:
                log_file = open("main.log", "w")
                system_process = subprocess.Popen(cmd, stdout=log_file, stderr=log_file, cwd=os.getcwd())
                AdminController.log_event("System Start", f"Detection started with source {source}")
                return jsonify({"message": f"System started with source {source}"}), 200
            except Exception as e:
                AdminController.log_event("System Error", f"Failed to start: {str(e)}")
                return jsonify({"message": f"Failed to start: {str(e)}"}), 500
        return jsonify({"message": "System already running"}), 400

    @staticmethod
    def stop_system(current_user):
        global system_process
        if system_process and system_process.poll() is None:
            system_process.terminate()
            system_process = None
            AdminController.log_event("System Stop", "Detection process terminated")
            return jsonify({"message": "System stopped"}), 200
        return jsonify({"message": "System not running"}), 200

    @staticmethod
    def get_system_status(current_user):
        global system_process
        is_running = system_process is not None and system_process.poll() is None
        return jsonify({"running": is_running}), 200

    # --- Camera Management ---
    @staticmethod
    def get_cameras(current_user):
        return jsonify(live_counts.get("cameras", {})), 200

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
            
        # Ensure format consistency
        # Frontend expects dictionary keyed by ID or list? 
        # Existing frontend code: Object.values(data.configured_zones).map... 
        # let's return a dict to match existing contract if possible, or list if easier.
        # But wait, we are rewriting frontend too. Let's return a Clean List.
        # But to minimize frontend breakage during transition, let's see.
        # The contract in admin_controller was: {"configured_zones": {id: data}, ...}
        # Let's keep it similar: {id: data}
        
        formatted_zones = {}
        for z in zones_data:
            zid = str(z.get('id', 'unknown'))
            formatted_zones[zid] = {
                "name": z.get('id'), # logic uses ID as name often
                "points_json": json.dumps(z.get('coords', [])),
                "threshold": z.get('threshold', 10)
            }
            
        return jsonify({"configured_zones": formatted_zones, "live_zones": live_counts.get("zones", [])}), 200

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
             from backend.models import Zone
             from backend.extensions import db
             
             try:
                 # Debug Logging
                 with open("debug_log.txt", "a") as log:
                     log.write(f"Saving {len(new_zones)} zones to DB for source {source}\n")

                 for z_data in new_zones:
                     name = z_data.get('name') or z_data.get('id')
                     threshold = int(z_data.get('threshold', 10))
                     coords = json.dumps(z_data.get('coords', []))
                     
                     with open("debug_log.txt", "a") as log:
                         log.write(f" - Upserting Zone: {name} Threshold: {threshold}\n")
                     
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
                 with open("debug_log.txt", "a") as log:
                     log.write(f"DB Update Error: {e}\n")
                 # Don't fail the request, but log it.

             # 3. Push Command to Main.py
             from backend.controllers.dashboard_controller import post_command, command_queue
             # We can append directly since we are in same package
             cmd = {
                 "action": "update_zones",
                 "cam_id": f"C{int(source)+1}",
                 "zones": json_zones
             }
             command_queue.append(cmd)
             
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
