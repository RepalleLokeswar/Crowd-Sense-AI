from flask import Flask, jsonify, send_from_directory, request, Response
import time
import threading
from .state import state # Import shared state

# ... (rest of imports)


from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
import os
import subprocess
from backend.extensions import db, jwt
from backend.models import User, Zone, Alert, AnalyticsData

from backend.system_manager import start_unified_detection

def start_detection_background():
    # Use centralized manager
    start_unified_detection("0")

def create_app():
    # Frontend is now in ../frontend relative to backend/app.py
    app = Flask(__name__, static_folder='../frontend', static_url_path='')
    
    # Config
    basedir = os.path.abspath(os.path.dirname(__file__))
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///' + os.path.join(basedir, 'instance/people_count_v2.db')
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['JWT_SECRET_KEY'] = 'super-secret-key-change-this'
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = 86400  # 24 hours
    
    # Init
    db.init_app(app)
    jwt.init_app(app)
    CORS(app)

    # Blueprints
    from backend.routes.admin_routes import admin_bp
    from backend.routes.dashboard_routes import dashboard_bp
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(dashboard_bp, url_prefix='/')

    # Serve Frontend
    @app.route('/')
    def serve_index():
        return app.send_static_file('login.html') # Start at Login

    @app.route('/<path:path>')
    def serve_static(path):
        return app.send_static_file(path)

    # Serve Camera Images (from Root)
    @app.route('/cam_<id>.jpg')
    def serve_cam_image(id):
        root_dir = os.path.abspath(os.path.join(basedir, '../'))
        filename = f"cam_{id}.jpg"
        return send_from_directory(root_dir, filename, mimetype='image/jpeg')

    # MJPEG Streaming Route
    @app.route('/video_feed/<id>')
    def video_feed(id):
        # IN-MEMORY STREAMING
        def gen():
            while True:
                try:
                    # Blocking wait for new frame (efficient)
                    frame = state.wait_for_frame(id, timeout=1.0)
                    if frame:
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                    else:
                        # Timeout or no frame yet
                         time.sleep(0.1)
                except Exception as e:
                    print(f"Stream Error: {e}")
                    time.sleep(1)

        return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

    # Create Tables
    with app.app_context():
        db.create_all()

    return app

if __name__ == '__main__':
    # Start Detection BEFORE App Run if executing directly
    # start_detection_background() <--- REMOVED: Auto-start disabled by user request.
    
    app = create_app()
    
    # Start Persistence Thread
    from backend.persistence import start_persistence_thread
    start_persistence_thread(app, interval=30) # 30s for better resolution
    
    app.run(debug=True, port=5001, use_reloader=False)

