import asyncio
import os
import sys
import uuid
from fastapi.responses import JSONResponse

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.db.session import AsyncSessionLocal, engine
from app.api.v1.routes.analytics import get_live_overview, get_dept_comparison
from app.main import csrf_guard_middleware
from app.core.config import settings

class MockAdmin:
    def __init__(self):
        self.id = uuid.uuid4()
        self.role = "admin"

class MockRequest:
    def __init__(self, method: str, path: str, headers: dict, cookies: dict):
        self.method = method
        self.url = self
        self.path = path
        self.headers = headers
        self.cookies = cookies

async def test_live_overview_optimized_query(db):
    print("Testing get_live_overview query...")
    overview = await get_live_overview(admin=MockAdmin(), db=db)
    assert isinstance(overview, list)
    if overview:
        emp = overview[0]
        assert "employee_name" in emp
        assert "is_online" in emp
        assert "today_active_seconds" in emp
        assert "today_productivity_score" in emp
    print("[OK] test_live_overview_optimized_query passed")

async def test_dept_comparison_optimized_query(db):
    print("Testing get_dept_comparison query...")
    dept_comp = await get_dept_comparison(date_str=None, admin=MockAdmin(), db=db)
    assert isinstance(dept_comp, list)
    if dept_comp:
        dept = dept_comp[0]
        assert "department_name" in dept
        assert "employee_count" in dept
        assert "avg_productivity_score" in dept
        assert "avg_active_seconds" in dept
    print("[OK] test_dept_comparison_optimized_query passed")

async def test_csrf_guard_strict_origin_check():
    print("Testing CSRF guard strict check...")
    # Mock request with cookie but missing Origin and Referer
    headers = {}
    cookies = {
        settings.ACCESS_COOKIE_NAME: "mock_token"
    }
    req = MockRequest("POST", "/api/v1/screenshots", headers, cookies)

    # Mock call_next function
    async def call_next(request):
        return JSONResponse(status_code=200, content={"status": "success"})

    # Call CSRF middleware
    resp = await csrf_guard_middleware(req, call_next)
    
    # Should be blocked with 403 Forbidden
    assert resp.status_code == 403
    assert b"Cross-site request blocked" in resp.body
    print("[OK] test_csrf_guard_strict_origin_check blocked invalid request")

    # Now test with valid Origin header
    headers = {"origin": "http://localhost:5173"}
    req = MockRequest("POST", "/api/v1/screenshots", headers, cookies)
    
    resp = await csrf_guard_middleware(req, call_next)
    
    # Should succeed (status code 200) since Origin is valid
    assert resp.status_code == 200
    print("[OK] test_csrf_guard_strict_origin_check allowed valid request")

async def main():
    db = AsyncSessionLocal()
    try:
        await test_live_overview_optimized_query(db)
        await test_dept_comparison_optimized_query(db)
        await test_csrf_guard_strict_origin_check()
        print("\nAll tests completed successfully!")
    finally:
        await db.close()
        # Dispose engine to close active pool connections cleanly
        await engine.dispose()

if __name__ == "__main__":
    asyncio.run(main())
