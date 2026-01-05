import requests
import time
import os
import sys

BASE_URL = "http://127.0.0.1:5001"
IMG_PATH = "cam_0.jpg"

def test_flow():
    # 1. Login
    print("Logging in...")
    try:
        resp = requests.post(f"{BASE_URL}/admin/auth/login", json={"username": "admin", "password": "admin123"}, timeout=5)
        if resp.status_code != 200:
            print(f"Login failed: {resp.text}")
            return
        token = resp.json()['token']
        headers = {"Authorization": f"Bearer {token}"}
        print("Login successful.")
    except Exception as e:
        print(f"Connection failed: {e}")
        return

    # 2. Start System
    print("Starting system...")
    resp = requests.post(f"{BASE_URL}/admin/system/start", json={"source": "0"}, headers=headers, timeout=5)
    print(f"Start response: {resp.status_code} - {resp.text}")

    # 3. Wait and Check Image
    print("Waiting for main.py to start...")
    time.sleep(10)
    
    if os.path.exists(IMG_PATH):
        mtime = os.path.getmtime(IMG_PATH)
        age = time.time() - mtime
        print(f"Image exists. Age: {age:.2f}s")
        if age < 5:
            print("SUCCESS: Image is being updated live!")
        else:
            print("FAILURE: Image is old/stale.")
    else:
        print("FAILURE: Image cam_0.jpg not found.")

if __name__ == "__main__":
    test_flow()
