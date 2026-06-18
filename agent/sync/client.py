import logging
import re
import time
import threading
import hashlib
import hmac
import json as jsonlib
import secrets
from typing import Optional, List
from urllib.parse import urlparse
import requests
from requests.exceptions import RequestException

from core.config import config
from sync.queue import OfflineSyncQueue

log = logging.getLogger("api_client")
TIMEOUT = 15


DOMAIN_ALIASES = {
    "youtube.com": {"youtu.be", "youtube"},
    "youtu.be": {"youtube.com", "youtube"},
    "twitter.com": {"x.com", "twitter"},
    "x.com": {"twitter.com", "twitter"},
}


def _normalize_domain(value: str) -> str:
    normalized = (value or "").strip().lower()
    normalized = normalized.replace("https://", "").replace("http://", "").replace("www.", "")
    return normalized.split("/", 1)[0].split(":", 1)[0]


def _extract_host(value: str) -> Optional[str]:
    candidate = (value or "").strip().lower()
    if not candidate:
        return None
    if candidate.startswith("www."):
        candidate = f"https://{candidate}"
    elif not candidate.startswith(("http://", "https://")):
        candidate = f"https://{candidate}"

    try:
        parsed = urlparse(candidate)
    except Exception:
        return None

    host = (parsed.netloc or "").split("@")[-1].split(":")[0]
    if "." not in host:
        return None
    return host.removeprefix("www.")


def _extract_hosts_from_text(value: str) -> set[str]:
    hosts: set[str] = set()
    text = (value or "").lower()
    for match in re.findall(r"(?:https?://)?(?:www\.)?[a-z0-9-]+(?:\.[a-z0-9-]+)+(?:/[^\s]*)?", text):
        host = _extract_host(match)
        if host:
            hosts.add(host)
    return hosts


def _host_matches(domain: str, host: str) -> bool:
    domain = _normalize_domain(domain)
    host = _normalize_domain(host)
    return host == domain or host.endswith(f".{domain}")

class PulseDeskClient:
    def __init__(self, queue: OfflineSyncQueue):
        self.base_url = config.server_url.rstrip("/")
        self.queue = queue
        self._is_online = False
        self._blocklist: List[str] = []
        self._blocklist_last_sync = 0.0

        # Create localized resilient session
        self.session = requests.Session()
        self.session.headers.update({
            "ngrok-skip-browser-warning": "1",
            "Bypass-Tunnel-Reminder": "true"
        })
        adapter = requests.adapters.HTTPAdapter(pool_connections=5, pool_maxsize=5, max_retries=1)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        import os
        env_token = os.getenv("DEVICE_TOKEN", "").strip()
        if env_token:
            self.device_token = env_token
            queue.save_state("device_token", env_token)
        else:
            self.device_token = queue.load_state("device_token") or ""

        env_device_id = os.getenv("DEVICE_ID", "").strip()
        if env_device_id:
            queue.save_state("device_id", env_device_id)

        self.session_id: Optional[str] = queue.load_state("session_id") or None

    @property
    def is_enrolled(self) -> bool:
        return bool(self.device_token)

    @property
    def is_online(self) -> bool:
        return self._is_online

    @property
    def blocklist(self) -> List[str]:
        return self._blocklist

    def _post(
        self,
        path: str,
        json: dict = None,
        data: dict = None,
        files: dict = None,
        headers: dict | None = None,
    ):
        """Unified internal POST with request signing and robust failure boundaries."""
        url = f"{self.base_url}{path}"
        req_headers = dict(headers or {})
        if self.device_token:
            req_headers.setdefault("X-Device-Token", self.device_token)
        try:
            request_kwargs = {"data": data, "files": files, "headers": req_headers}
            if json is not None:
                body = jsonlib.dumps(json, separators=(",", ":"), sort_keys=True).encode("utf-8")
                req_headers["Content-Type"] = "application/json"
                request_kwargs["data"] = body

            req = requests.Request("POST", url, **request_kwargs)
            prepared = self.session.prepare_request(req)
            self._sign_prepared_request(prepared, path)
            r = self.session.send(prepared, timeout=TIMEOUT)
            r.raise_for_status()
            self._is_online = True
            return r
        except RequestException as e:
            self._is_online = False
            raise e

    def _get(self, path: str, params: dict = None, headers: dict | None = None):
        url = f"{self.base_url}{path}"
        req_headers = dict(headers or {})
        if self.device_token:
            req_headers.setdefault("X-Device-Token", self.device_token)
        try:
            req = requests.Request("GET", url, params=params, headers=req_headers)
            prepared = self.session.prepare_request(req)
            self._sign_prepared_request(prepared, path)
            r = self.session.send(prepared, timeout=TIMEOUT)
            r.raise_for_status()
            self._is_online = True
            return r
        except RequestException as e:
            self._is_online = False
            raise e

    def _sign_prepared_request(self, prepared: requests.PreparedRequest, path: str) -> None:
        if not self.device_token:
            return

        body = prepared.body or b""
        if isinstance(body, str):
            body = body.encode("utf-8")

        timestamp = str(int(time.time()))
        nonce = secrets.token_urlsafe(24)
        body_hash = hashlib.sha256(body).hexdigest()
        message = "\n".join(
            [
                prepared.method.upper() if prepared.method else "GET",
                path,
                timestamp,
                nonce,
                body_hash,
            ]
        )
        signature = hmac.new(
            self.device_token.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        prepared.headers["X-Request-Timestamp"] = timestamp
        prepared.headers["X-Request-Nonce"] = nonce
        prepared.headers["X-Request-Signature"] = signature

    def sync_blocklist(self):
        if not self.device_token:
            return
        now = time.monotonic()
        if now - self._blocklist_last_sync < 300:
            return
        try:
            resp = self._get(
                "/api/v1/blocker/domains/active-list",
                headers={"X-Device-Token": self.device_token},
            )
            data = resp.json()
            self._blocklist = data.get("domains", [])
            self._blocklist_last_sync = now
            if self._blocklist:
                log.info(f"blocklist_synced: {len(self._blocklist)} domains: {self._blocklist}")
        except RequestException:
            pass

    def check_window_against_blocklist(
        self,
        app_name: Optional[str],
        window_title: Optional[str],
        current_url: Optional[str] = None,
    ) -> List[str]:
        """
        Check current active window against local blocklist.
        Returns a list of matched domain strings if violations are detected, else an empty list.

        Matching is bidirectional — extracts brand keyword from domain:
          "netflix.com"  → keyword "netflix"  matches app "Netflix", title "Netflix - ..."
          "youtube.com"  → keyword "youtube"  matches app "YouTube", title "YouTube - Chrome"
          "twitch.tv"    → keyword "twitch"   matches app "Twitch", title "Watch Streams - Twitch"
        """
        if not self._blocklist:
            return []

        app_lower = (app_name or "").lower()
        title_lower = (window_title or "").lower()
        url_lower = (current_url or "").lower()

        if not app_lower and not title_lower and not url_lower:
            return []

        hosts = _extract_hosts_from_text(url_lower) | _extract_hosts_from_text(title_lower)
        found_domains = []
        for domain in self._blocklist:
            domain_lower = _normalize_domain(domain)
            keyword = domain_lower.split(".")[0]
            aliases = DOMAIN_ALIASES.get(domain_lower, set())

            if any(_host_matches(domain_lower, host) for host in hosts):
                found_domains.append(domain)
            elif domain_lower in title_lower or domain_lower in url_lower:
                found_domains.append(domain)
            elif any(alias in url_lower for alias in aliases):
                found_domains.append(domain)
            elif keyword and len(keyword) >= 3 and (keyword in app_lower or keyword in title_lower):
                found_domains.append(domain)
            elif any(alias in app_lower or alias in title_lower for alias in aliases):
                found_domains.append(domain)

        return list(set(found_domains))

    def force_sync_blocklist(self):
        """Force immediate blocklist sync ignoring the 5-minute throttle. Call on startup."""
        self._blocklist_last_sync = 0.0  # Reset throttle
        self.sync_blocklist()

    def report_violation(
        self,
        domain: str,
        window_title: str,
        app_name: str,
        current_url: Optional[str] = None,
    ) -> bool:
        """
        Report a blocked domain violation to the backend.
        Returns True if the backend requests an immediate screenshot (violation trigger).
        """
        if not self.device_token:
            return False
        try:
            from datetime import datetime, timezone
            resp = self._post(
                "/api/v1/blocker/violation",
                json={
                    "device_token": self.device_token,
                    "domain": domain,
                    "window_title": window_title or "",
                    "app_name": app_name or "",
                    "current_url": current_url or "",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }
            )
            log.warning(f"blocked_site_reported: {domain}")
            data = resp.json()
            return data.get("screenshot_requested", False)
        except RequestException as e:
            log.warning(f"violation_report_failed: {e}")
            return False

    def check_screenshot_required(self) -> bool:
        if not self.device_token:
            return False
        try:
            resp = self._get(
                "/api/v1/agent/screenshot-required",
                headers={"X-Device-Token": self.device_token},
            )
            return resp.json().get("required", False)
        except RequestException:
            return False

    def upload_screenshot(self, image_bytes: bytes, mime_type: str, trigger: str = "interval"):
        if not self.device_token:
            return
        from datetime import datetime, timezone
        try:
            self._post(
                "/api/v1/agent/screenshot",
                data={
                    "device_token": self.device_token,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "trigger": trigger,
                },
                files={"file": ("screenshot.jpg", image_bytes, mime_type)}
            )
            log.info("screenshot_uploaded")
        except RequestException as e:
            log.debug(f"screenshot_upload_failed: {e}")

    def enroll(self, hostname: str, platform: str, os_version: str) -> dict:
        payload = {
            "employee_email": config.employee_email,
            "hostname": hostname,
            "platform": platform,
            "os_version": os_version,
            "agent_version": "4.0.0",
            "enrollment_code": self.queue.load_state("enrollment_code") or "",
        }
        try:
            resp = self._post("/api/v1/devices/enroll", json=payload)
            data = resp.json()
            token = data.get("device_token")
            if token:
                self.device_token = token
                self.queue.save_state("device_token", token)
                self.queue.save_state("device_id", str(data.get("device_id", "")))
            return data
        except RequestException as e:
            log.error(f"enrollment_failed: {e}")
            raise

    def start_session(self) -> Optional[str]:
        if not self.device_token:
            return None
        try:
            resp = self._post("/api/v1/agent/session/start", json={"device_token": self.device_token})
            session_id = resp.json().get("session_id")
            if session_id:
                self.session_id = session_id
                self.queue.save_state("session_id", session_id)
            return session_id
        except RequestException as e:
            log.debug(f"session_start_delayed: {e}")
            return None

    def end_session(self):
        if not self.device_token or not self.session_id:
            return
        try:
            self._post("/api/v1/agent/session/end", json={"device_token": self.device_token, "session_id": self.session_id})
            self.session_id = None
            self.queue.save_state("session_id", "")
        except RequestException:
            pass

    def send_heartbeat(self) -> bool:
        if not self.device_token:
            return False
        import platform, socket
        lat, lon = None, None
        try:
            r_geo = self.session.get("http://ip-api.com/json", timeout=4)
            if r_geo.status_code == 200:
                geo_data = r_geo.json()
                if geo_data.get("status") == "success":
                    lat = float(geo_data.get("lat"))
                    lon = float(geo_data.get("lon"))
                    log.info(f"Detected client location: lat={lat}, lon={lon}")
        except Exception:
            pass

        try:
            resp = self._post("/api/v1/agent/heartbeat", json={
                "device_token": self.device_token,
                "hostname": socket.gethostname(),
                "platform": platform.system().lower(),
                "os_version": platform.version()[:100],
                "agent_version": "4.0.0",
                "latitude": lat,
                "longitude": lon,
            })
            data = resp.json()
            within = data.get("within_geofence")
            near = data.get("nearest_location_name")
            if within is False:
                log.warning(f"[GEOFENCE WARNING] You are currently OUTSIDE the approved geofence location: '{near or 'Unknown'}'. Please move closer to register attendance correctly.")
            elif within is True:
                log.info(f"[GEOFENCE OK] You are inside the approved geofence location: '{near}'")
            self.sync_blocklist()
            return True
        except RequestException:
            return False

    def send_events(self, events: list) -> bool:
        if not self.device_token:
            return False
        payload = {
            "device_token": self.device_token,
            "session_id": self.session_id,
            "events": events,
        }
        
        # Always attempt flush prior to sending new payloads 
        self._flush_offline_queue()
        
        try:
            resp = self._post("/api/v1/agent/events", json=payload)
            data = resp.json()
            server_session = data.get("session_id")
            if server_session and server_session != self.session_id:
                self.session_id = server_session
                self.queue.save_state("session_id", server_session)
            log.debug(f"events_sent: accepted={data.get('accepted', 0)}")
            return True
        except RequestException as e:
            log.warning(f"server_offline: queuing {len(events)} events locally")
            self.queue.enqueue_batch(payload)
            return False

    def _flush_offline_queue(self):
        pending = self.queue.pending_count()
        if pending == 0:
            return
            
        batches = self.queue.dequeue_batch(limit=5)
        sent_ids = []
        for queue_id, batch_payload in batches:
            try:
                self._post("/api/v1/agent/events", json=batch_payload)
                sent_ids.append(queue_id)
            except RequestException:
                self.queue.mark_failed(queue_id)
                break  # Stop flush on first failure to maintain order
                
        if sent_ids:
            self.queue.mark_sent(sent_ids)
            log.info(f"offline_queue_flushed: restored {len(sent_ids)} batches")
