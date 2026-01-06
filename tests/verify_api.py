import requests
import sys

BASE_URL = "http://127.0.0.1:5001"
ADMIN_KEY = "admin123"

def run_test():
    print("Starting API Verification...")
    
    # 1. Signup
    print("1. Testing Signup...")
    signup_payload = {
        "username": "api_checker_admin",
        "password": "password123",
        "role": "admin",
        "admin_key": ADMIN_KEY
    }
    try:
        resp = requests.post(f"{BASE_URL}/admin/auth/signup", json=signup_payload)
        if resp.status_code == 201:
            print("   Signup Successful (Created)")
        elif resp.status_code == 400 and "already exists" in resp.text:
            print("   Signup: User already exists (OK)")
        else:
            print(f"   Signup Failed: {resp.status_code} - {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"   Connection Failed: {e}")
        sys.exit(1)

    # 2. Login
    print("2. Testing Login...")
    login_payload = {
        "username": "api_checker_admin",
        "password": "password123"
    }
    token = None
    try:
        resp = requests.post(f"{BASE_URL}/admin/auth/login", json=login_payload)
        if resp.status_code == 200:
            data = resp.json()
            token = data.get("token")
            print("   Login Successful")
        else:
            print(f"   Login Failed: {resp.status_code} - {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"   Connection Failed: {e}")
        sys.exit(1)

    # 3. Check System Status
    print("3. Testing System Status...")
    headers = {"Authorization": f"Bearer {token}"}
    try:
        resp = requests.get(f"{BASE_URL}/admin/system/status", headers=headers)
        if resp.status_code == 200:
            data = resp.json()
            print(f"   System Status: {data}")
            if data.get("running") is True:
                print("   Verified: System IS running.")
            else:
                 print("   Verified: System is NOT running (might depend on main.py connection).")
        else:
            print(f"   Status Failed: {resp.status_code} - {resp.text}")
            sys.exit(1)
    except Exception as e:
        print(f"   Connection Failed: {e}")
        sys.exit(1)

    print("\nALL CHECKS PASSED.")

if __name__ == "__main__":
    run_test()
