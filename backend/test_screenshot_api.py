"""Test script to verify screenshot API endpoints end-to-end."""
import asyncio
import sys
import os
import json
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = os.getenv("PULSEDESK_API_BASE", "http://localhost:8000/api/v1").rstrip("/")
ADMIN_EMAIL = os.getenv("PULSEDESK_ADMIN_EMAIL", "")
ADMIN_PASSWORD = os.getenv("PULSEDESK_ADMIN_PASSWORD", "")


def api_get(path, token):
    req = urllib.request.Request(f"{BASE}{path}", headers={"Authorization": f"Bearer {token}"})
    resp = urllib.request.urlopen(req)
    return json.loads(resp.read())


def test_login(email, password):
    try:
        req = urllib.request.Request(
            f"{BASE}/auth/login",
            data=json.dumps({"email": email, "password": password}).encode(),
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req)
        data = json.loads(resp.read())
        print(f"[OK] Login successful")
        return data["access_token"]
    except Exception as e:
        body = e.read().decode() if hasattr(e, "read") else str(e)
        print(f"[FAIL] Login failed: {body}")
        return None


def test_view_screenshot_with_token(token, screenshot_id):
    """Test the ?token= query param auth for img tags."""
    url = f"{BASE}/screenshots/view/{screenshot_id}?token={token}"
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req)
        content = resp.read()
        ct = resp.headers.get("content-type")
        print(f"  [OK] View with ?token: content-type={ct}, size={len(content)} bytes")
        return True
    except Exception as e:
        body = e.read().decode() if hasattr(e, "read") else str(e)
        print(f"  [FAIL] View with ?token: {body}")
        return False


def test_view_screenshot_no_token(screenshot_id):
    """Test that viewing without token returns 401."""
    url = f"{BASE}/screenshots/view/{screenshot_id}"
    try:
        req = urllib.request.Request(url)
        resp = urllib.request.urlopen(req)
        print(f"  [FAIL] View without token should have returned 401 but got 200")
        return False
    except urllib.error.HTTPError as e:
        if e.code == 401:
            print(f"  [OK] View without token correctly returns 401")
            return True
        else:
            print(f"  [FAIL] View without token returned {e.code}")
            return False


if __name__ == "__main__":
    print("=" * 60)
    print("SCREENSHOT API FULL TEST")
    print("=" * 60)

    # Login
    print("\n--- Login ---")
    if not ADMIN_EMAIL or not ADMIN_PASSWORD:
        raise RuntimeError("Set PULSEDESK_ADMIN_EMAIL and PULSEDESK_ADMIN_PASSWORD before running.")
    token = test_login(ADMIN_EMAIL, ADMIN_PASSWORD)
    if not token:
        sys.exit(1)

    # Get all employees
    print("\n--- Employees ---")
    employees = api_get("/employees", token)
    for emp in employees:
        print(f"  {emp['id']} - {emp['full_name']}")

    # Check screenshots for ALL employees
    print("\n--- Finding employee with screenshots ---")
    target_emp = None
    target_shots = []
    for emp in employees:
        shots = api_get(f"/screenshots/{emp['id']}?limit=5", token)
        print(f"  {emp['full_name']}: {len(shots)} screenshots")
        if shots and not target_emp:
            target_emp = emp
            target_shots = shots

    # Also check the employee_id from the files on disk
    print("\n--- Checking screenshots dir ---")
    screenshot_dir = "./screenshots"
    if os.path.exists(screenshot_dir):
        files = os.listdir(screenshot_dir)
        print(f"  {len(files)} files on disk")
        if files:
            # Extract employee IDs from filenames
            emp_ids = set()
            for f in files:
                parts = f.split("_", 1)
                if len(parts) == 2:
                    emp_ids.add(parts[0])
            print(f"  Employee IDs in filenames: {emp_ids}")
            
            # Check if these IDs are in the employee list
            emp_id_set = {e["id"] for e in employees}
            for eid in emp_ids:
                if eid in emp_id_set:
                    print(f"  [OK] Employee {eid} exists in DB")
                else:
                    print(f"  [WARN] Employee {eid} NOT found in employees list!")
    
    # Check DB directly for screenshots
    print("\n--- Direct DB check ---")
    async def check_db():
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy import text
        database_url = os.getenv("DATABASE_URL", "").strip()
        if not database_url:
            print("  [WARN] DATABASE_URL not set; skipping direct DB check")
            return
        engine = create_async_engine(database_url)
        async with engine.connect() as conn:
            result = await conn.execute(
                text("SELECT s.id, s.employee_id, s.file_path, e.full_name FROM screenshots s LEFT JOIN employees e ON s.employee_id = e.id ORDER BY s.captured_at DESC LIMIT 5")
            )
            rows = result.fetchall()
            for row in rows:
                print(f"  Screenshot: id={row[0]}, emp_id={row[1]}, file={row[2]}, emp_name={row[3]}")
                if not target_shots:
                    target_shots.append({"id": str(row[0])})
        await engine.dispose()
    asyncio.run(check_db())

    # Test view endpoint
    if target_shots:
        shot_id = target_shots[0]["id"]
        print(f"\n--- Test view screenshot {shot_id} ---")
        test_view_screenshot_with_token(token, shot_id)
        test_view_screenshot_no_token(shot_id)
    else:
        print("\n[WARN] No screenshots found to test view endpoint")

    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
