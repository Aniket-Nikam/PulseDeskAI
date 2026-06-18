"""
PulseDesk Agent — Screen Streamer
Real-time screen capture and streaming over WebSocket.
Streams continuously at video-like frame rates (default 5 FPS).
"""

import io
import time
import base64
import logging
import json
import threading
from typing import Optional
from urllib.parse import urlparse
from datetime import datetime, timezone
from PIL import Image
import mss
import websocket

log = logging.getLogger("screen_streamer")


class ScreenStreamer:
    def __init__(self, server_url: str, device_token: str, fps: float = 24.0, quality: int = 50):
        self.server_url = server_url
        self.device_token = device_token
        self.fps = fps
        self.quality = quality
        # Always-on by default — the admin sees live video at all times
        self.enabled = True
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._ws: Optional[websocket.WebSocketApp] = None
        self._ws_connected = False
        self._frame_count = 0
        self._last_log_time = 0.0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        log.info("ScreenStreamer thread started (always-on live video mode)")

    def stop(self):
        self._running = False
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=2.0)
            self._thread = None
        log.info("ScreenStreamer thread stopped")

    def _run(self):
        parsed = urlparse(self.server_url)
        ws_scheme = "wss" if parsed.scheme == "https" else "ws"
        ws_url = f"{ws_scheme}://{parsed.netloc}/api/v1/ws/screen-stream"
        reconnect_delay = 3.0
        max_delay = 30.0

        while self._running:
            log.info(f"ScreenStreamer connecting to: {ws_url}")
            connected_event = threading.Event()
            self._ws_connected = False
            close_code_holder = [None]  # mutable container for closure

            def on_open(ws):
                nonlocal reconnect_delay
                log.info("ScreenStreamer WebSocket connected — starting live video feed")
                self._ws_connected = True
                reconnect_delay = 3.0  # Reset backoff on successful connection
                # Spawn the frame capture & send loop
                threading.Thread(
                    target=self._send_loop, args=(ws, connected_event), daemon=True
                ).start()

            def on_message(ws, message):
                try:
                    data = json.loads(message)
                    if data.get("type") == "config":
                        self.enabled = data.get("enabled", True)
                        
                        raw_fps = data.get("fps")
                        if raw_fps is not None:
                            try:
                                self.fps = max(0.5, min(float(raw_fps), 30.0))
                            except (ValueError, TypeError):
                                pass
                                
                        raw_quality = data.get("quality")
                        if raw_quality is not None:
                            try:
                                self.quality = max(10, min(int(raw_quality), 85))
                            except (ValueError, TypeError):
                                pass

                        log.info(f"ScreenStreamer config update: enabled={self.enabled}, fps={self.fps}, quality={self.quality}")
                except Exception as e:
                    log.warning(f"ScreenStreamer failed to parse message: {e}")

            def on_close(ws, close_status_code, close_msg):
                self._ws_connected = False
                close_code_holder[0] = close_status_code
                if close_status_code == 4001:
                    log.warning("ScreenStreamer rejected: device token not recognized by server")
                elif close_status_code == 4003:
                    log.warning("ScreenStreamer rejected: device not approved or monitoring consent not given — check admin dashboard")
                else:
                    log.info(f"ScreenStreamer WebSocket closed: {close_status_code} — {close_msg}")
                connected_event.set()

            def on_error(ws, error):
                self._ws_connected = False
                log.warning(f"ScreenStreamer WebSocket error: {error}")
                connected_event.set()

            self._ws = websocket.WebSocketApp(
                ws_url,
                header=[f"X-Device-Token: {self.device_token}"],
                on_open=on_open,
                on_message=on_message,
                on_close=on_close,
                on_error=on_error
            )

            # run_forever blocks until connection is closed
            self._ws.run_forever()

            if not self._running:
                break

            # Exponential backoff, slower for permission errors
            if close_code_holder[0] in (4001, 4003):
                reconnect_delay = min(reconnect_delay * 2, max_delay)
            else:
                reconnect_delay = min(reconnect_delay * 1.5, max_delay)
            log.info(f"ScreenStreamer connection lost, retrying in {reconnect_delay:.0f} seconds...")
            time.sleep(reconnect_delay)

    def _send_loop(self, ws, connected_event):
        log.info(f"ScreenStreamer video capture started — FPS={self.fps}, quality={self.quality}")
        self._frame_count = 0
        self._last_log_time = time.monotonic()

        # Small delay to let the WebSocket handshake fully settle before
        # sending frames — avoids a race between run_forever() and send()
        time.sleep(0.3)

        from capture.screen_capture import capture_primary_screen

        consecutive_errors = 0
        max_consecutive_errors = 5

        while self._running and not connected_event.is_set():
            if not self.enabled:
                time.sleep(0.25)
                consecutive_errors = 0
                continue

            loop_start = time.monotonic()
            interval = 1.0 / max(0.5, self.fps)

            try:
                # Capture and compress using unified helper
                jpeg_bytes, _ = capture_primary_screen(max_width=1280, quality=self.quality, format_type="JPEG")
                if not jpeg_bytes:
                    time.sleep(0.1)
                    continue

                # Base64 encode for JSON transport
                b64_frame = base64.b64encode(jpeg_bytes).decode("utf-8")

                # Send frame payload
                payload = json.dumps({
                    "type": "screen_frame",
                    "frame": b64_frame,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })

                ws.send(payload)
                self._frame_count += 1
                consecutive_errors = 0  # Reset on success

                # Log frame stats every 30 seconds
                now = time.monotonic()
                if now - self._last_log_time >= 30.0:
                    actual_fps = self._frame_count / (now - self._last_log_time)
                    frame_size_kb = len(jpeg_bytes) / 1024
                    log.debug(f"ScreenStreamer stats: {self._frame_count} frames sent, "
                              f"actual={actual_fps:.1f} FPS, "
                              f"frame_size={frame_size_kb:.0f}KB")
                    self._frame_count = 0
                    self._last_log_time = now

            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError, OSError) as e:
                log.warning(f"ScreenStreamer connection lost: {e}")
                connected_event.set()  # Signal connection is dead
                break
            except Exception as e:
                consecutive_errors += 1
                log.warning(f"ScreenStreamer capture/send error ({consecutive_errors}/{max_consecutive_errors}): {e}")
                if consecutive_errors >= max_consecutive_errors:
                    log.error("ScreenStreamer too many consecutive errors, closing connection")
                    connected_event.set()
                    break

            # Sleep to maintain target FPS
            elapsed = time.monotonic() - loop_start
            sleep_time = max(0.0, interval - elapsed)
            if sleep_time > 0:
                time.sleep(sleep_time)

