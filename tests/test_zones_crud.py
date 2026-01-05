import requests
import json
import time

BASE_URL = "http://127.0.0.1:5000"
TOKEN = None

def get_token():
    global TOKEN
    username = f"zone_tester_{int(time.time())}"
    requests.post(f"{BASE_URL}/signup", json={"username": username, "password": "p", "role": "admin"})
    res = requests.post(f"{BASE_URL}/login", json={"username": username, "password": "p"})
    if res.status_code == 200:
        TOKEN = res.json().get('token')
        return True
    return False

def check_backend_zones():
    headers = {"Authorization": f"Bearer {TOKEN}"}
    res = requests.get(f"{BASE_URL}/admin/zones", headers=headers)
    if res.status_code != 200: return []
    data = res.json()
    # Returns map: {"id": {"name": ...}}
    print(f"DEBUG Response: {data}")
    return [z['name'] for z in data.get('configured_zones', {}).values()]

def run_test():
    if not get_token():
        print("❌ Auth Failed")
        return

    headers = {"Authorization": f"Bearer {TOKEN}"}

    print("--- Test 1: Create 2 Zones ---")
    payload_1 = {
        "action": "save_zones",
        "zones": [
            {"name": "Zone_A", "coords": [[0,0],[10,10]], "threshold": 10},
            {"name": "Zone_B", "coords": [[20,20],[30,30]], "threshold": 20}
        ]
    }
    requests.post(f"{BASE_URL}/admin/zones/config", json=payload_1, headers=headers)
    
    current_zones = check_backend_zones()
    if "Zone_A" in current_zones and "Zone_B" in current_zones:
        print("✅ Zones Created")
    else:
        print(f"❌ Creation Failed: {current_zones}")

    print("--- Test 2: Delete Zone_B (Send only Zone_A) ---")
    payload_2 = {
        "action": "save_zones",
        "zones": [
            {"name": "Zone_A", "coords": [[0,0],[10,10]], "threshold": 10}
        ]
    }
    requests.post(f"{BASE_URL}/admin/zones/config", json=payload_2, headers=headers)
    
    current_zones_2 = check_backend_zones()
    if "Zone_B" not in current_zones_2:
        print("✅ Zone_B Deleted Successfully")
    else:
        print("❌ Zone_B Still Exists (Backend deletion missing)")

run_test()
