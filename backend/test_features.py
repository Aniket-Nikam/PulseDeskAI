import sys
import os
from fastapi.testclient import TestClient

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.main import app

def test_employee_portal_features():
    print("Running integration tests for new features...")

    with TestClient(app, base_url="http://localhost") as client:
        # 1. Test Employee Login
        print("Testing employee login fallback...")
        login_payload = {
            "email": "aniket@pulsedesk.local",
            "password": "PulseDesk123!"
        }
        resp = client.post("/api/v1/auth/login", json=login_payload)
        assert resp.status_code == 200, f"Login failed: {resp.text}"
        data = resp.json()
        assert data["role"] == "employee"
        assert data["full_name"] == "Aniket Nikam"
        print("[OK] Employee login fallback succeeded!")

        # Store employee cookies
        employee_cookies = resp.cookies

        # 2. Test Employee accessing Employee Dashboard
        print("Testing Employee Dashboard access by Employee...")
        resp = client.get("/api/v1/employee/portal/dashboard", cookies=employee_cookies)
        assert resp.status_code == 200, f"Dashboard access failed: {resp.text}"
        db_data = resp.json()
        assert db_data["employee"]["email"] == "aniket@pulsedesk.local"
        assert "stats" in db_data
        assert "chart_data" in db_data
        print("[OK] Employee Dashboard fetched successfully!")

        # 3. Test Employee Consent status
        print("Testing Employee Consent GET & POST...")
        resp = client.get("/api/v1/employee/portal/consent", cookies=employee_cookies)
        assert resp.status_code == 200
        consent_info = resp.json()
        assert "consent_given" in consent_info
        
        # Toggle consent to true
        resp = client.post("/api/v1/employee/portal/consent", json={"consent_given": True}, cookies=employee_cookies, headers={"origin": "http://localhost:5173"})
        assert resp.status_code == 200
        assert resp.json()["consent_given"] is True
        print("[OK] Employee Consent toggle succeeded!")

        # 4. Test Employee Data Export
        print("Testing Employee Data Export (Article 15)...")
        resp = client.get("/api/v1/employee/portal/export", cookies=employee_cookies)
        assert resp.status_code == 200
        export_info = resp.json()
        assert export_info["employee_profile"]["email"] == "aniket@pulsedesk.local"
        assert "daily_summaries" in export_info
        assert "work_sessions" in export_info
        print("[OK] Employee Data Export (Article 15) succeeded!")

        # 5. Test Access Controls (Employee trying to access Admin endpoint)
        print("Testing Employee access restrictions (Admin endpoints)...")
        # /api/v1/employees is admin-only
        resp = client.get("/api/v1/employees", cookies=employee_cookies)
        assert resp.status_code == 403
        print("[OK] Access control blocked employee from accessing admin list!")

    # 6. Test Smart Categorization trigger check
    print("Testing Smart Categorization trigger function...")
    from app.services.categorizer import trigger_smart_categorization
    trigger_smart_categorization("unrecognized_test_app", "Coding in Test App")
    # Check that it gets queued / processed
    print("[OK] Smart categorization triggered safely!")

    print("\nIntegration tests completed successfully!")

if __name__ == "__main__":
    test_employee_portal_features()
