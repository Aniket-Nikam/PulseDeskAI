"""Final targeted test: view a screenshot that exists on disk."""
import sys
import os
import json
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = "http://localhost:8000/api/v1"

# Login
req = urllib.request.Request(
    f"{BASE}/auth/login",
    data=json.dumps({"email": "admin@company.com", "password": "changeme123"}).encode(),
    headers={"Content-Type": "application/json"},
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
token = data["access_token"]
print(f"[OK] Login successful")

# Get screenshots for Nikam Aniket (6725e0be-d289-4727-be1c-3e690ac9773f)
EMP_ID = "6725e0be-d289-4727-be1c-3e690ac9773f"
req = urllib.request.Request(
    f"{BASE}/screenshots/{EMP_ID}?limit=3",
    headers={"Authorization": f"Bearer {token}"},
)
resp = urllib.request.urlopen(req)
shots = json.loads(resp.read())
print(f"[OK] Found {len(shots)} screenshots for Nikam Aniket")

for s in shots[:3]:
    shot_id = s["id"]
    url = f"{BASE}/screenshots/view/{shot_id}?token={token}"
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req)
        content = resp.read()
        ct = resp.headers.get("content-type")
        print(f"  [OK] {shot_id}: content-type={ct}, size={len(content)} bytes")
    except Exception as e:
        body = e.read().decode() if hasattr(e, "read") else str(e)
        print(f"  [FAIL] {shot_id}: {body}")

# Test the frontend URL pattern (what the img src would be through the Vite proxy)
print(f"\n--- Frontend <img> URL would be: ---")
print(f"  /api/v1/screenshots/view/{shots[0]['id']}?token=<JWT_TOKEN>")
print(f"\nThis URL goes through Vite proxy -> http://localhost:8000/api/v1/screenshots/view/...")
