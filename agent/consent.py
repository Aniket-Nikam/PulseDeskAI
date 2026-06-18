"""
GDPR Consent Dialog for the PulseDesk Agent.

Shows a Windows popup when the agent starts for the first time,
asking the employee to accept or decline monitoring.

If declined:
  - Agent reports consent_given=false to the server
  - Agent exits and does not track any activity
  - Device is suspended on the server side

If accepted:
  - Consent timestamp is recorded both locally and on the server
  - Agent proceeds with normal monitoring
"""

import os
import sys
import logging
import ctypes
import time
from datetime import datetime, timezone

log = logging.getLogger("consent")

CONSENT_STATE_KEY = "monitoring_consent_given"
CONSENT_TIMESTAMP_KEY = "monitoring_consent_timestamp"


def _report_consent_to_server(client, consent_given: bool) -> None:
    if not client.device_token:
        return

    try:
        resp = client._post(
            "/api/v1/consent/submit",
            json={
                "device_token": client.device_token,
                "consent_given": consent_given,
            },
        )
        if resp.ok:
            log.info(f"consent_reported_to_server: {'given' if consent_given else 'declined'}")
        else:
            log.warning(f"consent_report_failed: {resp.status_code}")
    except Exception as e:
        log.warning(f"consent_report_failed: {e}")


def _show_windows_dialog() -> bool:
    """Show a native Windows MessageBox asking for monitoring consent."""
    title = "PulseDesk — Monitoring Consent"
    message = (
        "Your employer uses PulseDesk to monitor computer activity "
        "during work hours. This includes:\n\n"
        "  • Application usage tracking\n"
        "  • Active/idle time measurement\n"
        "  • Periodic screenshots (if enabled by your admin)\n"
        "  • Website access monitoring\n\n"
        "Your data is processed in accordance with applicable privacy "
        "regulations. You can revoke consent at any time by contacting "
        "your administrator.\n\n"
        "Do you consent to activity monitoring on this device?"
    )

    # MB_YESNO | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND
    MB_YESNO = 0x04
    MB_ICONQUESTION = 0x20
    MB_TOPMOST = 0x40000
    MB_SETFOREGROUND = 0x10000

    try:
        result = ctypes.windll.user32.MessageBoxW(
            None,
            message,
            title,
            MB_YESNO | MB_ICONQUESTION | MB_TOPMOST | MB_SETFOREGROUND,
        )
        return result == 6  # IDYES = 6
    except Exception as e:
        log.warning(f"Could not show consent dialog: {e}")
        # Fallback: console prompt
        return _show_console_dialog()


def _show_console_dialog() -> bool:
    """Fallback console-based consent prompt for non-GUI environments."""
    print("\n" + "=" * 60)
    print("  PulseDesk — Monitoring Consent Required")
    print("=" * 60)
    print()
    print("  Your employer uses PulseDesk to monitor computer")
    print("  activity during work hours. This includes:")
    print()
    print("  • Application usage tracking")
    print("  • Active/idle time measurement")
    print("  • Periodic screenshots (if enabled)")
    print("  • Website access monitoring")
    print()
    print("  Your data is processed in accordance with")
    print("  applicable privacy regulations.")
    print()

    while True:
        response = input("  Do you consent? (yes/no): ").strip().lower()
        if response in ("yes", "y"):
            return True
        if response in ("no", "n"):
            return False
        print("  Please enter 'yes' or 'no'.")


def check_and_request_consent(queue, client) -> bool:
    """
    Check if consent has already been given. If not, show the consent dialog.
    
    Args:
        queue: OfflineSyncQueue instance (for local state persistence)
        client: PulseDeskClient instance (to report consent to server)
    
    Returns:
        True if consent was given (monitoring can proceed).
        False if consent was declined (agent should exit).
    """
    # Check local state first
    stored_consent = queue.load_state(CONSENT_STATE_KEY)
    if stored_consent == "true":
        log.debug("consent_already_given")
        _report_consent_to_server(client, True)
        return True

    # Show consent dialog
    log.info("consent_required: showing dialog")

    if sys.platform == "win32":
        consent_given = _show_windows_dialog()
    else:
        consent_given = _show_console_dialog()

    # Save locally
    now_iso = datetime.now(timezone.utc).isoformat()
    queue.save_state(CONSENT_STATE_KEY, "true" if consent_given else "false")
    queue.save_state(CONSENT_TIMESTAMP_KEY, now_iso)

    # Report to server
    _report_consent_to_server(client, consent_given)

    if consent_given:
        log.info("monitoring_consent_given")
        print("\n  [OK] Consent recorded. Monitoring is now active.\n")
    else:
        log.warning("monitoring_consent_declined")
        print("\n  [DECLINED] Consent declined. Monitoring will NOT be active.")
        print("    Contact your administrator to resume monitoring.\n")

    return consent_given
