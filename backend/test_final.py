"""Final targeted test: view a screenshot that exists on disk."""
import sys
import os
import json
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
BASE = os.getenv("PULSEDESK_API_BASE", "http://localhost:8000/api/v1").rstrip("/")
ADMIN_EMAIL = os.getenv("PULSEDESK_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("PULSEDESK_ADMIN_PASSWORD", "")
EMP_ID = os.getenv("PULSEDESK_TEST_EMPLOYEE_ID", "")

if not ADMIN_EMAIL or not ADMIN_PASSWORD or not EMP_ID:
    raise RuntimeError(
        "Set PULSEDESK_ADMIN_EMAIL, PULSEDESK_ADMIN_PASSWORD, and PULSEDESK_TEST_EMPLOYEE_ID before running."
    )

# Login
req = urllib.request.Request(
    f"{BASE}/auth/login",
    data=json.dumps({"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD}).encode(),
    headers={"Content-Type": "application/json"},
)
resp = urllib.request.urlopen(req)
data = json.loads(resp.read())
token = data["access_token"]
print(f"[OK] Login successful")

# Get screenshots for a configured employee id
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
