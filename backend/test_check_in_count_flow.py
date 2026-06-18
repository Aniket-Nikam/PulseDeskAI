import asyncio
import urllib.request
import urllib.error
import json
from datetime import datetime, timezone, timedelta
from sqlalchemy import select, delete
from app.db.session import AsyncSessionLocal
from app.models import AttendanceRecord, Employee, Device, WorkSession, AttendanceSettings

BASE_URL = "http://localhost:8000/api/v1"
ADMIN_EMAIL = "admin@pulsedesk.com"
ADMIN_PASSWORD = "admin12345678"
EMPLOYEE_EMAIL = "aniket@pulsedesk.local"
DEVICE_TOKEN = "a6797787991a2d2889d0f0cfee1759a3fcf5c122f64c61f9312188429da5b36b"

def api_post(path, data, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code} for {path}: {e.read().decode()}")
        raise

def api_put(path, data, token=None):
    url = f"{BASE_URL}{path}"
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, data=json.dumps(data).encode(), headers=headers, method="PUT")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code} for {path}: {e.read().decode()}")
        raise

def api_get(path, token=None):
    url = f"{BASE_URL}{path}"
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code} for {path}: {e.read().decode()}")
        raise

async def clean_database():
    async with AsyncSessionLocal() as db:
        # Find employee
        res = await db.execute(select(Employee).where(Employee.email == EMPLOYEE_EMAIL))
        emp = res.scalar_one_or_none()
        if not emp:
            raise ValueError(f"Employee {EMPLOYEE_EMAIL} not found")
        
        # Enable remote checkin in settings
        sett_res = await db.execute(select(AttendanceSettings))
        settings = sett_res.scalar_one_or_none()
        if settings:
            settings.allow_remote_checkin = True
            await db.commit()
            print("[DB] Enabled allow_remote_checkin in settings")
            
        # Delete today's attendance records for the employee to start fresh
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        await db.execute(
            delete(AttendanceRecord).where(
                AttendanceRecord.employee_id == emp.id,
                AttendanceRecord.date == today
            )
        )
        await db.execute(
            delete(WorkSession).where(
                WorkSession.employee_id == emp.id,
                WorkSession.started_at >= today
            )
        )
        await db.commit()
        print(f"[DB] Cleared today's attendance and work sessions for {emp.full_name}")
        return emp.id

async def verify_record(employee_id):
    async with AsyncSessionLocal() as db:
        today = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        res = await db.execute(
            select(AttendanceRecord).where(
                AttendanceRecord.employee_id == employee_id,
                AttendanceRecord.date == today
            )
        )
        return res.scalar_one_or_none()

async def update_work_end_hour(employee_id, hour):
    async with AsyncSessionLocal() as db:
        res = await db.execute(select(Employee).where(Employee.id == employee_id))
        emp = res.scalar_one_or_none()
        if emp:
            emp.work_end_hour = hour
            await db.commit()
            print(f"[DB] Updated work_end_hour to {hour} for employee {emp.full_name}")

async def test_flow():
    # 0. Clean DB
    employee_id = await clean_database()
    
    # 1. Login
    print("\n--- 1. Logging in as admin ---")
    auth_resp = api_post("/auth/login", {"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    token = auth_resp["access_token"]
    print("Login successful! Token acquired.")
    
    # 2. Simulate agent heartbeat (creates attendance record for today)
    print("\n--- 2. Sending heartbeat (Check-in) ---")
    hb_resp = api_post("/agent/heartbeat", {
        "device_token": DEVICE_TOKEN,
        "latitude": None,
        "longitude": None
    })
    print("Heartbeat response:", hb_resp)
    
    record = await verify_record(employee_id)
    assert record is not None, "Attendance record not created!"
    print(f"Record created successfully: id={record.id}, check_in_count={record.check_in_count}")
    assert record.check_in_count == 1, f"Expected initial check_in_count to be 1, got {record.check_in_count}"
    
    # 3. Simulate first session start (should NOT increment check_in_count since session_count == 0)
    print("\n--- 3. Starting first agent session ---")
    start_resp1 = api_post("/agent/session/start", {
        "device_token": DEVICE_TOKEN,
        "session_id": None
    })
    session_id1 = start_resp1["session_id"]
    print(f"First session started: {session_id1}")
    
    # Verify check_in_count is still 1
    record = await verify_record(employee_id)
    print(f"check_in_count after 1st session start: {record.check_in_count}")
    assert record.check_in_count == 1, f"Expected check_in_count to remain 1, got {record.check_in_count}"
    
    # 4. Simulate second session start (should increment check_in_count to 2 since session_count > 0 and during work hours)
    # Let's make sure work_end_hour is set high (e.g. 23) so we are during work hours
    await update_work_end_hour(employee_id, 23)
    
    # Close session 1 first so it counts as a finished session (or not, but session_count counts all today's sessions)
    print("\n--- 4. Starting second agent session ---")
    start_resp2 = api_post("/agent/session/start", {
        "device_token": DEVICE_TOKEN,
        "session_id": None
    })
    session_id2 = start_resp2["session_id"]
    print(f"Second session started: {session_id2}")
    
    # Verify check_in_count is now 2
    record = await verify_record(employee_id)
    print(f"check_in_count after 2nd session start: {record.check_in_count}")
    assert record.check_in_count == 2, f"Expected check_in_count to be 2, got {record.check_in_count}"
    
    # 5. Test manual admin override of check_in_count to 5
    print("\n--- 5. Overriding check_in_count via admin API ---")
    record_id = record.id
    override_resp = api_put(f"/attendance/records/{record_id}", {
        "check_in_count": 5,
        "notes": "Testing manual check-in override"
    }, token=token)
    print("Override response check_in_count:", override_resp["check_in_count"])
    assert override_resp["check_in_count"] == 5, f"Expected check_in_count to be overridden to 5, got {override_resp['check_in_count']}"
    
    # 6. Test automatic checkout on agent shutdown after work hours
    print("\n--- 6. Testing agent shutdown automatic checkout ---")
    # Change work_end_hour to 0 (so that local time hour (e.g., 11) >= work_end_hour)
    await update_work_end_hour(employee_id, 0)
    
    # Verify checkout is currently empty
    record = await verify_record(employee_id)
    assert record.check_out_time is None, "Check out time should not be set yet"
    
    # End session 2
    print("Ending session 2 after work hours...")
    end_resp = api_post("/agent/session/end", {
        "device_token": DEVICE_TOKEN,
        "session_id": session_id2
    })
    print("End session response:", end_resp)
    
    # Verify checkout time is now set!
    record = await verify_record(employee_id)
    print(f"Record checkout time after shutdown: {record.check_out_time}")
    assert record.check_out_time is not None, "Checkout time was not set on session end!"
    
    print("\n==============================")
    print("ALL TESTS PASSED SUCCESSFULLY!")
    print("==============================")

if __name__ == "__main__":
    asyncio.run(test_flow())
