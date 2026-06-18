# PulseDesk - Employee Monitoring System
Production-ready. All core features are available.

## Quick Start (2 steps)

### Step 1 - Create PostgreSQL database
```sql
CREATE DATABASE pulsedesk;
```

### Step 2 - Run Launcher
Double-click `RUN_PULSEDESK.bat`.
- **First Time Run**: It runs setup, opens `.env` to configure settings (like database password, Groq key, and secrets), and prompts to create the admin account.
- **Subsequent Runs**: It verifies configuration, checks ports, and starts the backend (FastAPI) and frontend (React/Vite) servers automatically.

- Dashboard: `http://localhost:5173`
- API docs: `http://localhost:8000/api/docs`

## Run Modes

### 1) Localhost (same PC)
Use `RUN_PULSEDESK.bat`. This is the default developer flow.

### 2) LAN & Internet Exposure (Live Testing)
Double-click `RUN_LIVE_TEST.bat`.
This launcher:
- Checks the installation.
- Starts backend and frontend in LAN mode (binding to `0.0.0.0`).
- Launches a public tunnel using `localtunnel` so the system can be tested remotely/globally.
- Prints the Local IP and Tunnel URL to access the site and enroll devices.

## Adding employees and monitoring
1. Go to Employees and add an employee.
2. Open Enroll Device, enter server URL (local or tunnel URL), and generate a code.
3. Share the code with the employee.
4. Employee opens `<server-url>/join` in browser.
5. Employee enters code and downloads the agent package.
6. Employee runs `INSTALL_AGENT.bat` once, then `START_AGENT.bat` daily.

Note: `INSTALL_AGENT.bat` now enables Windows login auto-start automatically.
Manual controls:
- Enable again: `agent/ENABLE_AGENT_AUTOSTART.bat`
- Disable: `agent/DISABLE_AGENT_AUTOSTART.bat`

## URLs
- `http://localhost:5173` - Admin dashboard
- `http://localhost:8000/join` - Employee join portal
- `http://localhost:8000/api/docs` - API documentation

## Credentials
Use the admin email/password configured during setup.
