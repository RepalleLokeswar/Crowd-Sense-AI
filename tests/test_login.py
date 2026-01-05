import requests

url = "http://127.0.0.1:5001/admin/auth/login"
payload = {
    "username": "admin",
    "password": "admin123"
}

try:
    print(f"Attempting login to {url}...")
    resp = requests.post(url, json=payload)
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.text}")
except Exception as e:
    print(f"Error: {e}")
