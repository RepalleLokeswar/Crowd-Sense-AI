from flask import Flask, jsonify, send_from_directory, request, Response
import time

# ... (rest of imports)


from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager
import os
import subprocess
from backend.extensions import db, jwt

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
        root_dir = os.path.abspath(os.path.join(basedir, '../'))
        path = os.path.join(root_dir, f"cam_{id}.jpg")
        
        def gen():
            last_mtime = 0
            while True:
                if os.path.exists(path):
                    try:
                        mtime = os.path.getmtime(path)
                        if mtime > last_mtime:
                            last_mtime = mtime
                            with open(path, 'rb') as f:
                                frame = f.read()
                            yield (b'--frame\r\n'
                                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')
                        else:
                            time.sleep(0.01) # Low latency check
                    except:
                        time.sleep(0.1)
                else:
                    time.sleep(0.5)

        return Response(gen(), mimetype='multipart/x-mixed-replace; boundary=frame')

    # Create Tables
    with app.app_context():
        db.create_all()

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True, port=5001, use_reloader=False)



#.venv\Scripts\python.exe" backend/app.py