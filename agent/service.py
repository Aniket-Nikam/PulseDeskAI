"""
PulseDesk Agent — Windows Service Wrapper

Install:   python service.py install
Start:     python service.py start
Stop:      python service.py stop
Remove:    python service.py remove
Debug:     python service.py debug   (runs in foreground for testing)

Alternatively, use NSSM (Non-Sucking Service Manager):
  nssm install PulseDeskAgent "C:\path\to\python.exe" "C:\path\to\agent.py"
  nssm start PulseDeskAgent

Requirements:
  pip install pywin32
"""

import sys
import os
import time
import logging
import servicemanager

# Ensure agent directory is on the path
AGENT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, AGENT_DIR)

try:
    import win32serviceutil
    import win32service
    import win32event
except ImportError:
    print("ERROR: pywin32 is required for Windows Service mode.")
    print("Install it with:  pip install pywin32")
    print("\nAlternatively, use NSSM to run agent.py as a service:")
    print('  nssm install PulseDeskAgent "C:\\path\\to\\python.exe" "C:\\path\\to\\agent.py"')
    sys.exit(1)


class PulseDeskService(win32serviceutil.ServiceFramework):
    """Windows Service that runs the PulseDesk monitoring agent."""

    _svc_name_ = "PulseDeskAgent"
    _svc_display_name_ = "PulseDesk Monitoring Agent"
    _svc_description_ = (
        "PulseDesk employee monitoring agent. "
        "Tracks application usage, captures screenshots, and syncs with the PulseDesk server."
    )

    def __init__(self, args):
        win32serviceutil.ServiceFramework.__init__(self, args)
        self.hWaitStop = win32event.CreateEvent(None, 0, 0, None)
        self._agent = None

    def SvcStop(self):
        """Called when the service is asked to stop."""
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        logging.info("PulseDesk service stop requested")

        if self._agent:
            self._agent._running = False
            try:
                self._agent._send_batch()
                self._agent.client.end_session()
            except Exception as e:
                logging.warning(f"Error during shutdown: {e}")

        win32event.SetEvent(self.hWaitStop)

    def SvcDoRun(self):
        """Called when the service starts."""
        servicemanager.LogMsg(
            servicemanager.EVENTLOG_INFORMATION_TYPE,
            servicemanager.PYS_SERVICE_STARTED,
            (self._svc_name_, ""),
        )

        # Set working directory to agent folder
        os.chdir(AGENT_DIR)

        # Setup logging to file (services don't have stdout)
        log_dir = os.path.join(AGENT_DIR, "logs")
        os.makedirs(log_dir, exist_ok=True)
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            handlers=[
                logging.FileHandler(os.path.join(log_dir, "service.log"), encoding="utf-8"),
            ],
        )

        logging.info("PulseDesk service starting")

        try:
            from agent import PulseDeskAgent
            self._agent = PulseDeskAgent()
            self._agent.start()
        except Exception as e:
            logging.error(f"PulseDesk service failed: {e}", exc_info=True)
            servicemanager.LogErrorMsg(f"PulseDesk agent error: {e}")

        # Wait for stop signal
        win32event.WaitForSingleObject(self.hWaitStop, win32event.INFINITE)
        logging.info("PulseDesk service stopped")


def install_with_nssm_instructions():
    """Print instructions for using NSSM as an alternative."""
    python_path = sys.executable
    agent_path = os.path.join(AGENT_DIR, "agent.py")

    print("\n" + "=" * 60)
    print("  NSSM Installation (Alternative Method)")
    print("=" * 60)
    print(f"\n  1. Download NSSM from https://nssm.cc/download")
    print(f"  2. Run these commands as Administrator:\n")
    print(f'     nssm install PulseDeskAgent "{python_path}" "{agent_path}"')
    print(f'     nssm set PulseDeskAgent AppDirectory "{AGENT_DIR}"')
    print(f'     nssm set PulseDeskAgent Description "PulseDesk Monitoring Agent"')
    print(f'     nssm set PulseDeskAgent Start SERVICE_AUTO_START')
    print(f'     nssm set PulseDeskAgent AppStdout "{AGENT_DIR}\\logs\\stdout.log"')
    print(f'     nssm set PulseDeskAgent AppStderr "{AGENT_DIR}\\logs\\stderr.log"')
    print(f'     nssm start PulseDeskAgent')
    print(f"\n  To remove:")
    print(f'     nssm stop PulseDeskAgent')
    print(f'     nssm remove PulseDeskAgent confirm')
    print("=" * 60 + "\n")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "nssm":
        install_with_nssm_instructions()
    elif len(sys.argv) == 1:
        # When run without args, Windows Service Control Manager invokes this
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(PulseDeskService)
        servicemanager.StartServiceCtrlDispatcher()
    else:
        win32serviceutil.HandleCommandLine(PulseDeskService)
