import requests

BASE_URL = "http://127.0.0.1:5001"

def test_signup():
    print("Testing Signup...")
    payload = {
        "username": "test_admin",
        "password": "password123",
        "role": "admin",
        "admin_key": "admin123"
    }
    try:
        resp = requests.post(f"{BASE_URL}/admin/auth/signup", json=payload)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Failed: {e}")

def test_login():
    print("\nTesting Login...")
    payload = {
        "username": "test_admin",
        "password": "password123"
    }
    try:
        resp = requests.post(f"{BASE_URL}/admin/auth/login", json=payload)
        print(f"Status: {resp.status_code}")
        print(f"Response: {resp.text}")
    except Exception as e:
        print(f"Failed: {e}")

if __name__ == "__main__":
    test_signup()
    test_login()
