"""
PulseDesk Monitoring Agent v4 — Production
All bugs fixed:
- Device info sent on startup and heartbeat
- Idle time overflow fixed
- Blocklist enforcement
- Screenshot capture
- Robust session handling
"""

import sys
import os
import time
import signal
import socket
import logging
import platform
import threading
import argparse
import requests
from datetime import datetime, timezone
from typing import List, Optional

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.config import config
from capture.window_tracker import get_active_window
from capture.input_monitor import monitor as input_monitor
from sync.queue import OfflineSyncQueue
from sync.client import PulseDeskClient

logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
log = logging.getLogger("agent")

AGENT_VERSION = "4.0.0"


def handle_join_url(join_url: str, queue: OfflineSyncQueue) -> bool:
    log.info("Auto-enrolling via join URL...")
    try:
        resp = requests.get(join_url, timeout=15)
        resp.raise_for_status()
        data = resp.json()

        queue.save_state("device_token", data["device_token"])
        queue.save_state("device_id", data["device_id"])
        queue.save_state("server_url", data["server_url"])
        queue.save_state("employee_email", data["employee_email"])

        env_path = os.path.join(os.path.dirname(__file__), ".env")
        env_lines = []
        if os.path.exists(env_path):
            with open(env_path) as f:
                env_lines = f.readlines()

        def update_or_add(lines, key, value):
            for i, line in enumerate(lines):
                if line.startswith(f"{key}="):
                    lines[i] = f"{key}={value}\n"
                    return lines
            lines.append(f"{key}={value}\n")
            return lines

        env_lines = update_or_add(env_lines, "SERVER_URL", data["server_url"])
        env_lines = update_or_add(env_lines, "EMPLOYEE_EMAIL", data["employee_email"])
        if "DEVICE_TOKEN" not in "".join(env_lines):
            env_lines = update_or_add(env_lines, "DEVICE_TOKEN", data["device_token"])
        if "DEVICE_ID" not in "".join(env_lines):
            env_lines = update_or_add(env_lines, "DEVICE_ID", data["device_id"])

        with open(env_path, "w") as f:
            f.writelines(env_lines)

        print(f"\n{'='*50}")
        print(f"  Enrolled: {data.get('message', 'Success')}")
        print(f"  Device ID: {data['device_id']}")
        print(f"{'='*50}\n")
        return True
    except Exception as e:
        log.error(f"Auto-enrollment failed: {e}")
        return False


class PulseDeskAgent:
    def __init__(self):
        self.queue = OfflineSyncQueue(config.offline_db_path)
        self.client = PulseDeskClient(self.queue)
        self._running = False
        self._event_buffer: List[dict] = []
        self._buffer_lock = threading.Lock()
        self._last_heartbeat = 0.0
        self._last_batch_send = 0.0
        self._last_screenshot_check = 0.0
        self._blocklist: List[str] = []
        self._last_blocklist_sync = 0.0
        self._last_violation_reported: dict = {}  # domain -> timestamp, cooldown

    def start(self):
        print(f"\nPulseDesk Agent v{AGENT_VERSION}")
        print(f"  System   : {platform.system()} {platform.release()}")
        print(f"  Hostname : {socket.gethostname()}")
        print(f"  Employee : {config.employee_email or '(from device token)'}")
        print(f"  Server   : {config.server_url}")
        print(f"  Interval : {config.sample_interval}s\n")

        if not self.client.is_enrolled:
            self._ensure_enrolled()
        else:
            log.info("Device already enrolled.")

        if not self.client.is_enrolled:
            log.error("Not enrolled. Run: python agent.py --join <URL>")
            sys.exit(1)

        # Update device info immediately
        self._send_device_info()

        input_monitor.start()
        self.client.start_session()

        signal.signal(signal.SIGINT, self._handle_signal)
        signal.signal(signal.SIGTERM, self._handle_signal)

        self._running = True
        log.info("Monitoring active. Press Ctrl+C to stop.")
        self._run_loop()

    def _send_device_info(self):
        """Send hostname, platform, OS version to server — fixes 'pending/unknown' in dashboard."""
        try:
            requests.patch(
                f"{config.server_url}/api/v1/agent/device-info",
                json={
                    "device_token": self.client.device_token,
                    "hostname": socket.gethostname(),
                    "platform": platform.system().lower(),
                    "os_version": platform.version()[:100],
                    "agent_version": AGENT_VERSION,
                },
                timeout=10,
            )
            log.info(f"device_info_sent: {socket.gethostname()} ({platform.system().lower()})")
        except Exception as e:
            log.debug(f"device_info_failed: {e}")

    def _ensure_enrolled(self):
        if not config.employee_email:
            log.error("No EMPLOYEE_EMAIL set. Use --join URL or set in .env")
            return
        try:
            result = self.client.enroll(
                hostname=socket.gethostname(),
                platform=platform.system().lower(),
                os_version=platform.version(),
            )
            log.info(f"Enrollment: {result.get('status')} — {result.get('message', '')}")
        except Exception as e:
            log.error(f"Enrollment failed: {e}")

    def _run_loop(self):
        while self._running:
            loop_start = time.monotonic()
            self._take_sample()

            if (loop_start - self._last_batch_send) >= config.batch_interval:
                self._send_batch()
                self._last_batch_send = loop_start

            if (loop_start - self._last_heartbeat) >= config.heartbeat_interval:
                self._do_heartbeat()
                self._last_heartbeat = loop_start

            if (loop_start - self._last_screenshot_check) >= 60:
                self._maybe_take_screenshot()
                self._last_screenshot_check = loop_start

            if (loop_start - self._last_blocklist_sync) >= 300:  # every 5 min
                self._sync_blocklist()
                self._last_blocklist_sync = loop_start

            elapsed = time.monotonic() - loop_start
            time.sleep(max(0, config.sample_interval - elapsed))

    def _take_sample(self):
        now = time.monotonic()
        timestamp = datetime.now(timezone.utc).isoformat()
        app_name, window_title = get_active_window()
        sample = input_monitor.take_sample()

        # FIXED: infinity guard
        raw_idle = input_monitor.get_idle_seconds(now)
        idle_seconds = 0 if raw_idle == float("inf") or raw_idle != raw_idle else int(min(raw_idle, 86400))

        activity_type = "idle" if idle_seconds >= config.idle_threshold else "active"

        event = {
            "timestamp": timestamp,
            "activity_type": activity_type,
            "active_app": app_name,
            "active_window_title": window_title[:500] if window_title else None,
            "keystrokes": sample.keystrokes,
            "mouse_clicks": sample.mouse_clicks,
            "mouse_distance_px": int(sample.mouse_distance_px),
            "idle_duration_seconds": idle_seconds if activity_type == "idle" else 0,
            "sample_duration_seconds": config.sample_interval,
        }

        with self._buffer_lock:
            self._event_buffer.append(event)

        # Check blocklist
        if app_name or window_title:
            self._check_blocklist(app_name, window_title)

    def _check_blocklist(self, app_name: Optional[str], window_title: Optional[str]):
        """Detect and report blocked domain access."""
        if not self._blocklist:
            return
        text = f"{(app_name or '').lower()} {(window_title or '').lower()}"
        for domain in self._blocklist:
            if domain.lower() in text:
                # Rate limit: report same domain max once per 5 min
                now = time.monotonic()
                last = self._last_violation_reported.get(domain, 0)
                if now - last < 300:
                    return
                self._last_violation_reported[domain] = now
                log.warning(f"BLOCKED DOMAIN DETECTED: {domain}")
                try:
                    requests.post(
                        f"{config.server_url}/api/v1/blocker/violation",
                        json={
                            "device_token": self.client.device_token,
                            "domain": domain,
                            "window_title": window_title or "",
                            "app_name": app_name or "",
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                        timeout=5,
                    )
                except Exception:
                    pass
                break

    def _sync_blocklist(self):
        """Fetch active blocklist from server."""
        try:
            resp = requests.get(
                f"{config.server_url}/api/v1/blocker/domains/active-list",
                timeout=5,
            )
            if resp.status_code == 200:
                self._blocklist = resp.json().get("domains", [])
                if self._blocklist:
                    log.debug(f"blocklist_synced: {len(self._blocklist)} domains")
        except Exception:
            pass

    def _do_heartbeat(self):
        """Send heartbeat and include device info for updates."""
        if not self.client.device_token:
            return
        try:
            requests.post(
                f"{config.server_url}/api/v1/agent/heartbeat",
                json={
                    "device_token": self.client.device_token,
                    "hostname": socket.gethostname(),
                    "platform": platform.system().lower(),
                    "os_version": platform.version()[:100],
                    "agent_version": AGENT_VERSION,
                },
                timeout=10,
            )
        except Exception:
            pass
        # Also use client method for queue flush
        self.client.send_heartbeat()

    def _send_batch(self):
        with self._buffer_lock:
            if not self._event_buffer:
                return
            batch = self._event_buffer.copy()
            self._event_buffer.clear()
        self.client.send_events(batch)

    def _maybe_take_screenshot(self):
        """Check if screenshot required by policy, then take one."""
        if not self.client.device_token:
            return
        try:
            resp = requests.get(
                f"{config.server_url}/api/v1/agent/screenshot-required",
                params={"device_token": self.client.device_token},
                timeout=5,
            )
            if resp.status_code == 200 and resp.json().get("required"):
                self._take_and_upload_screenshot()
        except Exception:
            pass

    def _take_and_upload_screenshot(self):
        """Capture and upload screenshot."""
        data = None
        mime = "image/jpeg"

        # Try mss first (fastest, no dependencies)
        try:
            import mss
            import mss.tools
            import io
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                img = sct.grab(monitor)
                buf = io.BytesIO()
                buf.write(mss.tools.to_png(img.rgb, img.size))
                data = buf.getvalue()
                mime = "image/png"
        except ImportError:
            # Fallback: PIL
            try:
                from PIL import ImageGrab
                import io
                img = ImageGrab.grab()
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=60)
                data = buf.getvalue()
            except Exception as e:
                log.debug(f"screenshot_failed: {e}")
                return
        except Exception as e:
            log.debug(f"screenshot_failed: {e}")
            return

        if not data:
            return

        try:
            resp = requests.post(
                f"{config.server_url}/api/v1/agent/screenshot",
                data={
                    "device_token": self.client.device_token,
                    "captured_at": datetime.now(timezone.utc).isoformat(),
                    "trigger": "interval",
                },
                files={"file": ("screenshot.jpg", data, mime)},
                timeout=30,
            )
            if resp.status_code == 201:
                log.info("screenshot_uploaded")
            else:
                log.debug(f"screenshot_upload_status: {resp.status_code}")
        except Exception as e:
            log.debug(f"screenshot_upload_failed: {e}")

    def _handle_signal(self, signum, frame):
        log.info("Shutting down gracefully...")
        self._running = False
        self._send_batch()
        self.client.end_session()
        input_monitor.stop()
        sys.exit(0)


def main():
    parser = argparse.ArgumentParser(description="PulseDesk Monitoring Agent")
    parser.add_argument("--join", metavar="URL", help="Zero-config join URL from admin dashboard")
    args = parser.parse_args()

    queue = OfflineSyncQueue(config.offline_db_path)

    if args.join:
        success = handle_join_url(args.join, queue)
        if not success:
            print("ERROR: Could not enroll. Check the URL and try again.")
            sys.exit(1)
        import importlib
        import core.config as cfg_module
        importlib.reload(cfg_module)
        from core.config import config as new_config
        config.__dict__.update(new_config.__dict__)

    agent = PulseDeskAgent()
    agent.start()


if __name__ == "__main__":
    main()
