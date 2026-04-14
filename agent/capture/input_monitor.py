"""
Input activity monitor.
Counts keystrokes and mouse events in a sampling window using pynput.
Does NOT record key content — only counts.
"""

import threading
import math
import logging
from dataclasses import dataclass, field
from typing import Optional

log = logging.getLogger("input_monitor")


@dataclass
class InputSample:
    keystrokes: int = 0
    mouse_clicks: int = 0
    mouse_distance_px: float = 0.0
    last_input_time: Optional[float] = None

    def reset(self) -> "InputSample":
        """Return a copy of current values and reset."""
        snapshot = InputSample(
            keystrokes=self.keystrokes,
            mouse_clicks=self.mouse_clicks,
            mouse_distance_px=int(self.mouse_distance_px),
            last_input_time=self.last_input_time,
        )
        self.keystrokes = 0
        self.mouse_clicks = 0
        self.mouse_distance_px = 0.0
        return snapshot


class InputMonitor:
    """
    Thread-safe input counter using pynput listeners.
    Records counts only — no keylog content, no screenshots from here.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._sample = InputSample()
        self._last_mouse_pos: Optional[tuple[int, int]] = None
        self._keyboard_listener = None
        self._mouse_listener = None
        self._running = False

    def start(self):
        if self._running:
            return
        try:
            from pynput import keyboard, mouse

            # Windows-specific patch: suppress NotImplementedError for unrecognized pointer events
            import platform
            if platform.system() == "Windows":
                try:
                    import pynput._util.win32
                    orig_convert = pynput._util.win32.Listener._convert
                    def safe_convert(self_obj, code, msg, lpdata):
                        try:
                            return orig_convert(self_obj, code, msg, lpdata)
                        except NotImplementedError:
                            # Ignore unknown Windows message types (like specific touchpad gestures)
                            # Return something safe that doesn't forward a bad type tuple
                            pass
                    pynput._util.win32.Listener._convert = safe_convert
                except Exception as e:
                    log.warning(f"Failed to apply win32 pynput patch: {e}")

            self._keyboard_listener = keyboard.Listener(
                on_press=self._on_key_press,
                suppress=False,
            )
            self._mouse_listener = mouse.Listener(
                on_click=self._on_mouse_click,
                on_move=self._on_mouse_move,
                suppress=False,
            )
            self._keyboard_listener.start()
            self._mouse_listener.start()
            self._running = True
            log.info("input_monitor_started")
        except Exception as e:
            log.error(f"input_monitor_start_failed: {e}")

    def stop(self):
        if self._keyboard_listener:
            self._keyboard_listener.stop()
        if self._mouse_listener:
            self._mouse_listener.stop()
        self._running = False
        log.info("input_monitor_stopped")

    def take_sample(self) -> InputSample:
        """Atomically take current counts and reset."""
        with self._lock:
            return self._sample.reset()

    def get_idle_seconds(self, current_time: float) -> float:
        """Seconds since last input event."""
        with self._lock:
            if self._sample.last_input_time is None:
                return float("inf")
            return current_time - self._sample.last_input_time

    def _on_key_press(self, key):
        import time
        with self._lock:
            self._sample.keystrokes += 1
            self._sample.last_input_time = time.monotonic()

    def _on_mouse_click(self, x, y, button, pressed):
        import time
        if pressed:
            with self._lock:
                self._sample.mouse_clicks += 1
                self._sample.last_input_time = time.monotonic()

    def _on_mouse_move(self, x, y):
        import time
        with self._lock:
            if self._last_mouse_pos is not None:
                dx = x - self._last_mouse_pos[0]
                dy = y - self._last_mouse_pos[1]
                self._sample.mouse_distance_px += math.sqrt(dx * dx + dy * dy)
            self._last_mouse_pos = (x, y)
            self._sample.last_input_time = time.monotonic()


# Singleton for the agent process
monitor = InputMonitor()
