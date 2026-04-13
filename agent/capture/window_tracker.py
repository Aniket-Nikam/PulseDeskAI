"""
Cross-platform active window tracker.
Returns (app_name, window_title) for the currently focused window.
Supports: Windows, macOS, Linux (X11).
"""

import sys
import logging

log = logging.getLogger("window_tracker")


def get_active_window() -> tuple[str | None, str | None]:
    """
    Returns (app_name, window_title) or (None, None) on error.
    """
    try:
        if sys.platform == "win32":
            return _get_active_window_windows()
        elif sys.platform == "darwin":
            return _get_active_window_macos()
        else:
            return _get_active_window_linux()
    except Exception as e:
        log.debug(f"active_window_error: {e}")
        return None, None


def _get_active_window_windows() -> tuple[str | None, str | None]:
    import ctypes
    import ctypes.wintypes

    hwnd = ctypes.windll.user32.GetForegroundWindow()
    if not hwnd:
        return None, None

    # Get window title
    length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
    title = buf.value

    # Get process name via PID
    pid = ctypes.wintypes.DWORD()
    ctypes.windll.user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

    try:
        import psutil
        proc = psutil.Process(pid.value)
        app_name = proc.name().replace(".exe", "").replace("-", " ").title()
    except Exception:
        app_name = None

    return app_name, title


def _get_active_window_macos() -> tuple[str | None, str | None]:
    try:
        from AppKit import NSWorkspace
        from Quartz import (
            CGWindowListCopyWindowInfo,
            kCGWindowListOptionOnScreenOnly,
            kCGNullWindowID,
            kCGWindowOwnerName,
            kCGWindowName,
            kCGWindowLayer,
        )
    except ImportError:
        log.warning("pyobjc not installed. Run: pip install pyobjc-framework-Quartz")
        return None, None

    workspace = NSWorkspace.sharedWorkspace()
    active_app = workspace.activeApplication()
    app_name = active_app.get("NSApplicationName") if active_app else None

    # Get frontmost window title
    windows = CGWindowListCopyWindowInfo(kCGWindowListOptionOnScreenOnly, kCGNullWindowID)
    for win in windows:
        if win.get(kCGWindowLayer, 1) == 0 and win.get(kCGWindowOwnerName) == app_name:
            title = win.get(kCGWindowName, "")
            return app_name, title

    return app_name, None


def _get_active_window_linux() -> tuple[str | None, str | None]:
    try:
        from Xlib import display, X
        from Xlib.error import XError
    except ImportError:
        log.warning("python-xlib not installed. Run: pip install python-xlib")
        return _get_active_window_linux_subprocess()

    try:
        d = display.Display()
        root = d.screen().root
        net_active = d.intern_atom("_NET_ACTIVE_WINDOW")
        window_id = root.get_full_property(net_active, X.AnyPropertyType)

        if not window_id or not window_id.value:
            return None, None

        wid = window_id.value[0]
        win = d.create_resource_object("window", wid)

        # Get window title
        net_name = d.intern_atom("_NET_WM_NAME")
        title_prop = win.get_full_property(net_name, 0)
        title = title_prop.value.decode("utf-8", errors="replace") if title_prop else None

        if not title:
            try:
                title = win.get_wm_name()
            except Exception:
                pass

        # Get PID → process name
        net_pid = d.intern_atom("_NET_WM_PID")
        pid_prop = win.get_full_property(net_pid, X.AnyPropertyType)
        app_name = None
        if pid_prop:
            pid = pid_prop.value[0]
            try:
                import psutil
                proc = psutil.Process(pid)
                app_name = proc.name()
            except Exception:
                pass

        return app_name, title
    except XError:
        return None, None


def _get_active_window_linux_subprocess() -> tuple[str | None, str | None]:
    """Fallback: use xdotool if Xlib not available."""
    import subprocess
    try:
        wid = subprocess.check_output(["xdotool", "getactivewindow"]).decode().strip()
        title = subprocess.check_output(["xdotool", "getwindowname", wid]).decode().strip()
        pid = subprocess.check_output(["xdotool", "getwindowpid", wid]).decode().strip()
        import psutil
        app_name = psutil.Process(int(pid)).name()
        return app_name, title
    except Exception:
        return None, None
