"""
Lightweight PulseDesk end-to-end route smoke test.

Usage:
  py smoke_test_routes.py
  py smoke_test_routes.py --base-url http://localhost:8000
  py smoke_test_routes.py --email admin@yourcompany.com --password <password>
  py smoke_test_routes.py --exercise-join
"""

from __future__ import annotations

import argparse
import json
import sys
import socket
import os
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class HttpResult:
    status: int
    body_text: str
    headers: dict[str, str]

    def json(self) -> Any:
        if not self.body_text:
            return None
        return json.loads(self.body_text)


class SmokeRunner:
    def __init__(self, base_url: str, email: str, password: str, timeout: float, exercise_join: bool):
        self.base_url = base_url.rstrip("/")
        self.api_base = f"{self.base_url}/api/v1"
        self.email = email
        self.password = password
        self.timeout = timeout
        self.exercise_join = exercise_join

        self.access_token: Optional[str] = None
        self.refresh_token: Optional[str] = None
        self.first_employee_id: Optional[str] = None

        self.total = 0
        self.passed = 0
        self.failed = 0

    def _request(
        self,
        method: str,
        url: str,
        token: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> HttpResult:
        data = None
        headers: dict[str, str] = {}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        if token:
            headers["Authorization"] = f"Bearer {token}"

        req = urllib.request.Request(url=url, method=method, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return HttpResult(
                    status=resp.status,
                    body_text=body,
                    headers={k.lower(): v for k, v in resp.headers.items()},
                )
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            return HttpResult(
                status=e.code,
                body_text=body,
                headers={k.lower(): v for k, v in e.headers.items()},
            )
        except (urllib.error.URLError, TimeoutError, socket.timeout) as e:
            return HttpResult(
                status=0,
                body_text=str(e),
                headers={},
            )

    def _assert(self, name: str, ok: bool, detail: str = "") -> None:
        self.total += 1
        if ok:
            self.passed += 1
            print(f"[PASS] {name}")
        else:
            self.failed += 1
            suffix = f" -> {detail}" if detail else ""
            print(f"[FAIL] {name}{suffix}")

    def _expect_status(self, name: str, result: HttpResult, expected: int) -> bool:
        ok = result.status == expected
        detail = "" if ok else f"expected {expected}, got {result.status}, body={result.body_text[:220]}"
        self._assert(name, ok, detail)
        return ok

    def run(self) -> int:
        print("=" * 72)
        print("PulseDesk Lightweight End-to-End Smoke Test")
        print(f"Base URL: {self.base_url}")
        print("=" * 72)

        healthy = self.test_health()
        if not healthy:
            print("[INFO] Backend is unreachable. Start PulseDesk backend and re-run this script.")
            print("-" * 72)
            print(f"Checks: {self.total} | Passed: {self.passed} | Failed: {self.failed}")
            print("-" * 72)
            return 1

        self.test_auth()
        self.test_core_routes()
        self.test_reports()
        self.test_enrollment_routes()
        self.test_screenshots_flow()

        print("-" * 72)
        print(f"Checks: {self.total} | Passed: {self.passed} | Failed: {self.failed}")
        print("-" * 72)
        return 0 if self.failed == 0 else 1

    def test_health(self) -> bool:
        result = self._request("GET", f"{self.base_url}/api/health")
        if self._expect_status("GET /api/health", result, 200):
            try:
                data = result.json() or {}
                self._assert("health payload has status=ok", data.get("status") == "ok", str(data))
                return True
            except Exception as e:
                self._assert("health payload is valid json", False, str(e))
                return False
        return False

    def test_auth(self) -> None:
        login = self._request(
            "POST",
            f"{self.api_base}/auth/login",
            payload={"email": self.email, "password": self.password},
        )
        if not self._expect_status("POST /api/v1/auth/login", login, 200):
            return

        try:
            data = login.json() or {}
            self.access_token = data.get("access_token")
            self.refresh_token = data.get("refresh_token")
            self._assert("login returned access_token", bool(self.access_token))
            self._assert("login returned refresh_token", bool(self.refresh_token))
        except Exception as e:
            self._assert("login response parse", False, str(e))
            return

        me = self._request("GET", f"{self.api_base}/auth/me", token=self.access_token)
        self._expect_status("GET /api/v1/auth/me", me, 200)

        if self.refresh_token:
            refresh = self._request(
                "POST",
                f"{self.api_base}/auth/refresh",
                payload={"refresh_token": self.refresh_token},
            )
            self._expect_status("POST /api/v1/auth/refresh", refresh, 200)

    def test_core_routes(self) -> None:
        if not self.access_token:
            return

        employees = self._request("GET", f"{self.api_base}/employees", token=self.access_token)
        if self._expect_status("GET /api/v1/employees", employees, 200):
            try:
                items = employees.json() or []
                self._assert("employees response is list", isinstance(items, list))
                if items:
                    self.first_employee_id = items[0].get("id")
                    self._assert("captured first employee id", bool(self.first_employee_id))
            except Exception as e:
                self._assert("employees response parse", False, str(e))

        self._expect_status(
            "GET /api/v1/departments",
            self._request("GET", f"{self.api_base}/departments", token=self.access_token),
            200,
        )
        self._expect_status(
            "GET /api/v1/devices",
            self._request("GET", f"{self.api_base}/devices", token=self.access_token),
            200,
        )
        self._expect_status(
            "GET /api/v1/analytics/overview",
            self._request("GET", f"{self.api_base}/analytics/overview", token=self.access_token),
            200,
        )
        self._expect_status(
            "GET /api/v1/analytics/leaderboard?days=7",
            self._request("GET", f"{self.api_base}/analytics/leaderboard?days=7", token=self.access_token),
            200,
        )
        self._expect_status(
            "GET /api/v1/analytics/anomalies?limit=5",
            self._request("GET", f"{self.api_base}/analytics/anomalies?limit=5", token=self.access_token),
            200,
        )
        self._expect_status(
            "GET /api/v1/screenshot-policies",
            self._request("GET", f"{self.api_base}/screenshot-policies", token=self.access_token),
            200,
        )
        self._expect_status(
            "GET /api/v1/ai/diagnostics/data-status",
            self._request("GET", f"{self.api_base}/ai/diagnostics/data-status", token=self.access_token),
            200,
        )
        if self.first_employee_id:
            self._expect_status(
                f"GET /api/v1/ai/work-recommendations/{self.first_employee_id}",
                self._request(
                    "GET",
                    f"{self.api_base}/ai/work-recommendations/{self.first_employee_id}",
                    token=self.access_token,
                ),
                200,
            )

    def test_reports(self) -> None:
        if not self.access_token:
            return

        team = self._request("GET", f"{self.api_base}/reports/pdf/team/all?days=7", token=self.access_token)
        ok_team = team.status == 200 and "application/pdf" in team.headers.get("content-type", "").lower()
        self._assert(
            "GET /api/v1/reports/pdf/team/all?days=7",
            ok_team,
            f"status={team.status}, content-type={team.headers.get('content-type')}",
        )

        if self.first_employee_id:
            emp = self._request(
                "GET",
                f"{self.api_base}/reports/pdf/{self.first_employee_id}?days=7",
                token=self.access_token,
            )
            ok_emp = emp.status == 200 and "application/pdf" in emp.headers.get("content-type", "").lower()
            self._assert(
                f"GET /api/v1/reports/pdf/{self.first_employee_id}?days=7",
                ok_emp,
                f"status={emp.status}, content-type={emp.headers.get('content-type')}",
            )

    def test_enrollment_routes(self) -> None:
        if not self.access_token or not self.first_employee_id:
            return

        query = urllib.parse.urlencode(
            {"employee_id": self.first_employee_id, "server_url": self.base_url}
        )

        join_link_api = self._request(
            "POST",
            f"{self.api_base}/enroll/generate-join-link?{query}",
            token=self.access_token,
        )
        join_link_ok = self._expect_status(
            "POST /api/v1/enroll/generate-join-link",
            join_link_api,
            200,
        )

        # Keep legacy token enrollment covered as a secondary path.
        legacy_enroll = self._request(
            "POST",
            f"{self.api_base}/enroll/generate-link?{query}",
            token=self.access_token,
        )
        self._expect_status("POST /api/v1/enroll/generate-link", legacy_enroll, 200)

        if not join_link_ok or not self.exercise_join:
            return

        try:
            payload = join_link_api.json() or {}
            code = payload.get("code")
            if not code:
                self._assert("join-link API returned code", False, str(payload))
                return
        except Exception as e:
            self._assert("join-link API parse", False, str(e))
            return

        verify = self._request(
            "POST",
            f"{self.base_url}/join/verify",
            payload={"code": code},
        )
        if not self._expect_status("POST /join/verify", verify, 200):
            return

        try:
            verify_data = verify.json() or {}
            download_url = verify_data.get("download_url")
            self._assert("join verify returned download_url", bool(download_url), str(verify_data))
            if not download_url:
                return
        except Exception as e:
            self._assert("join verify parse", False, str(e))
            return

        download = self._request("GET", f"{self.base_url}{download_url}")
        ok_zip = (
            download.status == 200
            and "application/zip" in download.headers.get("content-type", "").lower()
        )
        self._assert(
            "GET join download zip",
            ok_zip,
            f"status={download.status}, content-type={download.headers.get('content-type')}",
        )

    def test_screenshots_flow(self) -> None:
        if not self.access_token or not self.first_employee_id:
            return

        listing = self._request(
            "GET",
            f"{self.api_base}/screenshots/{self.first_employee_id}?limit=1",
            token=self.access_token,
        )
        if not self._expect_status(
            f"GET /api/v1/screenshots/{self.first_employee_id}?limit=1",
            listing,
            200,
        ):
            return

        try:
            payload = listing.json() or {}
            items = payload.get("items") if isinstance(payload, dict) else payload
            if not isinstance(items, list):
                self._assert("screenshot list payload has items[]", False, str(payload))
                return
            if not items:
                self._assert("screenshot list returned 0 items (skipping view tests)", True)
                return
            screenshot_id = items[0].get("id")
            if not screenshot_id:
                self._assert("screenshot id exists", False, str(items[0]))
                return
        except Exception as e:
            self._assert("screenshot listing parse", False, str(e))
            return

        view_query = self._request(
            "GET",
            f"{self.api_base}/screenshots/view/{screenshot_id}?token={self.access_token}",
        )
        self._assert(
            "GET screenshot view via ?token",
            view_query.status == 200,
            f"status={view_query.status}",
        )

        view_header = self._request(
            "GET",
            f"{self.api_base}/screenshots/view/{screenshot_id}",
            token=self.access_token,
        )
        self._assert(
            "GET screenshot view via Authorization header",
            view_header.status == 200,
            f"status={view_header.status}",
        )

        view_no_auth = self._request(
            "GET",
            f"{self.api_base}/screenshots/view/{screenshot_id}",
        )
        self._assert(
            "GET screenshot view without auth returns 401",
            view_no_auth.status == 401,
            f"status={view_no_auth.status}",
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PulseDesk route smoke test")
    default_email = os.getenv("PULSEDESK_ADMIN_EMAIL", "")
    default_password = os.getenv("PULSEDESK_ADMIN_PASSWORD", "")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Backend base URL")
    parser.add_argument("--email", default=default_email, help="Admin login email")
    parser.add_argument("--password", default=default_password, help="Admin login password")
    parser.add_argument("--timeout", type=float, default=15.0, help="HTTP timeout seconds")
    parser.add_argument(
        "--exercise-join",
        action="store_true",
        help="Also run /join/verify + download ZIP flow (creates one enrolled device).",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.email or not args.password:
        print("Provide --email/--password or set PULSEDESK_ADMIN_EMAIL/PULSEDESK_ADMIN_PASSWORD.")
        return 2
    runner = SmokeRunner(
        base_url=args.base_url,
        email=args.email,
        password=args.password,
        timeout=args.timeout,
        exercise_join=args.exercise_join,
    )
    return runner.run()


if __name__ == "__main__":
    sys.exit(main())
