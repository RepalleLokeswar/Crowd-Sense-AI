from backend.app import create_app
from backend.models import User
from backend.extensions import db
from werkzeug.security import generate_password_hash

app = create_app()

with app.app_context():
    print(f"Targeting DB: {app.config['SQLALCHEMY_DATABASE_URI']}")
    
    # 1. Reset 'admin'
    admin = User.query.filter_by(username='admin').first()
    if not admin:
        print("Creating admin user...")
        admin = User(username='admin', role='admin')
        db.session.add(admin)
    else:
        print("Found admin user.")
        
    admin.password = generate_password_hash('admin123')
    admin.role = 'admin' # Ensure role
    
    # 2. Print all users for verification
    users = User.query.all()
    print(f"Total Users: {len(users)}")
    
    db.session.commit()
    print("SUCCESS: Password for 'admin' set to 'admin123'")
