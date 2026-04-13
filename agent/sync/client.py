"""
PulseDesk Agent API Client v3
- Supports DEVICE_TOKEN from .env (set by join portal download)
- Syncs blocklist from server every 5 minutes
- Reports blocked domain violations
"""

import logging
import time
import threading
from typing import Optional, List
import requests
from requests.exceptions import ConnectionError, Timeout, RequestException

from core.config import config
from sync.queue import OfflineSyncQueue

log = logging.getLogger("api_client")
TIMEOUT = 10


class PulseDeskClient:
    def __init__(self, queue: OfflineSyncQueue):
        self.base_url = config.server_url.rstrip("/")
        self.queue = queue
        self._is_online = False
        self._blocklist: List[str] = []
        self._blocklist_last_sync = 0.0

        # Try to load device token from env first, then from queue
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

    def sync_blocklist(self):
        """Fetch active blocklist from server. Call every 5 minutes."""
        now = time.monotonic()
        if now - self._blocklist_last_sync < 300:  # 5 min
            return
        try:
            resp = requests.get(
                f"{self.base_url}/api/v1/blocker/domains/active-list",
                timeout=TIMEOUT,
            )
            if resp.status_code == 200:
                data = resp.json()
                self._blocklist = data.get("domains", [])
                self._blocklist_last_sync = now
                if self._blocklist:
                    log.debug(f"blocklist_synced: {len(self._blocklist)} domains")
        except RequestException:
            pass

    def report_violation(self, domain: str, window_title: str, app_name: str):
        """Report a blocked domain access to the server."""
        if not self.device_token:
            return
        try:
            from datetime import datetime, timezone
            requests.post(
                f"{self.base_url}/api/v1/blocker/violation",
                json={
                    "device_token": self.device_token,
                    "domain": domain,
                    "window_title": window_title or "",
                    "app_name": app_name or "",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                },
                timeout=TIMEOUT,
            )
            log.warning(f"blocked_site_reported: {domain}")
        except RequestException:
            pass

    def check_window_against_blocklist(self, app_name: Optional[str], window_title: Optional[str]) -> Optional[str]:
        """Returns the matched blocked domain, or None if clean."""
        if not self._blocklist:
            return None
        text = f"{(app_name or '').lower()} {(window_title or '').lower()}"
        for domain in self._blocklist:
            if domain.lower() in text:
                return domain
        return None

    def enroll(self, hostname: str, platform: str, os_version: str) -> dict:
        import socket
        payload = {
            "employee_email": config.employee_email,
            "hostname": hostname or socket.gethostname(),
            "platform": platform,
            "os_version": os_version,
            "agent_version": "3.0.0",
            "enrollment_code": self.queue.load_state("enrollment_code") or "",
        }
        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/devices/enroll",
                json=payload, timeout=TIMEOUT,
            )
            resp.raise_for_status()
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
            resp = requests.post(
                f"{self.base_url}/api/v1/agent/session/start",
                json={"device_token": self.device_token}, timeout=TIMEOUT,
            )
            resp.raise_for_status()
            session_id = resp.json().get("session_id")
            if session_id:
                self.session_id = session_id
                self.queue.save_state("session_id", session_id)
            return session_id
        except RequestException as e:
            log.warning(f"session_start_failed: {e}")
            return None

    def end_session(self):
        if not self.device_token or not self.session_id:
            return
        try:
            requests.post(
                f"{self.base_url}/api/v1/agent/session/end",
                json={"device_token": self.device_token, "session_id": self.session_id},
                timeout=TIMEOUT,
            )
            self.session_id = None
            self.queue.save_state("session_id", "")
        except RequestException:
            pass

    def send_heartbeat(self) -> bool:
        if not self.device_token:
            return False
        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/agent/heartbeat",
                json={"device_token": self.device_token}, timeout=TIMEOUT,
            )
            resp.raise_for_status()
            self._is_online = True
            self.sync_blocklist()
            return True
        except RequestException:
            self._is_online = False
            return False

    def send_events(self, events: list) -> bool:
        if not self.device_token:
            return False
        payload = {
            "device_token": self.device_token,
            "session_id": self.session_id,
            "events": events,
        }
        self._flush_offline_queue()
        try:
            resp = requests.post(
                f"{self.base_url}/api/v1/agent/events",
                json=payload, timeout=TIMEOUT,
            )
            resp.raise_for_status()
            data = resp.json()
            server_session = data.get("session_id")
            if server_session and server_session != self.session_id:
                self.session_id = server_session
                self.queue.save_state("session_id", server_session)
            self._is_online = True
            log.debug(f"events_sent: accepted={data.get('accepted', 0)}")
            return True
        except (ConnectionError, Timeout):
            log.warning("server_offline: queuing events locally")
            self.queue.enqueue_batch(payload)
            self._is_online = False
            return False
        except RequestException as e:
            log.error(f"send_events_error: {e}")
            self.queue.enqueue_batch(payload)
            self._is_online = False
            return False

    def _flush_offline_queue(self):
        pending = self.queue.pending_count()
        if pending == 0:
            return
        batches = self.queue.dequeue_batch(limit=5)
        sent_ids = []
        for queue_id, batch_payload in batches:
            try:
                resp = requests.post(
                    f"{self.base_url}/api/v1/agent/events",
                    json=batch_payload, timeout=TIMEOUT,
                )
                if resp.status_code < 400:
                    sent_ids.append(queue_id)
                else:
                    self.queue.mark_failed(queue_id)
            except RequestException:
                self.queue.mark_failed(queue_id)
                break
        if sent_ids:
            self.queue.mark_sent(sent_ids)
            log.info(f"offline_queue_flushed: {len(sent_ids)} batches")
