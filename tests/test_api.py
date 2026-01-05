import requests
import json

BASE_URL = "http://127.0.0.1:5001"

def test_login(username, password):
    print(f"\n--- Testing Login for '{username}' ---")
    try:
        res = requests.post(f"{BASE_URL}/admin/auth/login", json={"username": username, "password": password})
        print(f"Status: {res.status_code}")
        print(f"Response: {res.text}")
        if res.status_code == 200:
            return res.json().get('token')
    except Exception as e:
        print(f"ERROR: {e}")
    return None

def test_signup(username, password, role="user", admin_key=None):
    print(f"\n--- Testing Signup for '{username}' ---")
    payload = {"username": username, "password": password, "role": role}
    if admin_key:
        payload["admin_key"] = admin_key
        
    try:
        res = requests.post(f"{BASE_URL}/admin/auth/signup", json=payload)
        print(f"Status: {res.status_code}")
        print(f"Response: {res.text}")
    except Exception as e:
        print(f"ERROR: {e}")

# 1. Test Admin Login (Should work if reset script worked)
token = test_login("admin", "admin123")

# 2. If Admin fails, try to create it? (Start fresh)
if not token:
    print("Admin login failed. Attempting to CREATE admin...")
    test_signup("admin", "admin123", "admin", "admin123")
    token = test_login("admin", "admin123")

# 3. Create a fresh User
test_signup("debug_user", "pass123")
test_login("debug_user", "pass123")
