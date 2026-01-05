import requests
import time
import os

BASE_URL = "http://127.0.0.1:5000"
TOKEN = None

def run():
    global TOKEN
    # Login
    res = requests.post(f"{BASE_URL}/login", json={"username": "feed_test", "password": "p"})
    if res.status_code != 200:
        # Try signup
        requests.post(f"{BASE_URL}/signup", json={"username": "feed_test", "password": "p", "role": "admin"})
        res = requests.post(f"{BASE_URL}/login", json={"username": "feed_test", "password": "p"})
    
    TOKEN = res.json().get('token')
    headers = {"Authorization": f"Bearer {TOKEN}"}

    # Start System
    print("🚀 Starting System...")
    res = requests.post(f"{BASE_URL}/admin/system/start", json={"source": "0"}, headers=headers)
    print(f"Start Response: {res.text}")

    print("⏳ Waiting for frames...")
    time.sleep(10)

    # Check File
    if os.path.exists("cam_0.jpg"):
        print("✅ cam_0.jpg found on disk")
    else:
        print("❌ cam_0.jpg NOT found on disk")

    # Check URL
    try:
        res = requests.get(f"{BASE_URL}/cam_0.jpg")
        if res.status_code == 200:
             print("✅ /cam_0.jpg serves 200 OK")
        else:
             print(f"❌ /cam_0.jpg returned {res.status_code}: {res.text}")
    except:
        print("❌ Connection Failed")

    # Stop System
    requests.post(f"{BASE_URL}/admin/system/stop", headers=headers)
    print("🛑 System Stopped")

if __name__ == "__main__":
    run()
