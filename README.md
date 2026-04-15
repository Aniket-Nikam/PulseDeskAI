# PulseDesk - Employee Monitoring System
Production-ready. All core features are available.

## Quick Start (3 steps)

### Step 1 - Create PostgreSQL database
```sql
CREATE DATABASE pulsedesk;
```

### Step 2 - First time setup
Double-click `SETUP_WINDOWS.bat`.
- Update `YOUR_PASSWORD` with your PostgreSQL password.
- Configure `GROQ_API_KEY`, `SECRET_KEY`, and `DEVICE_TOKEN_SECRET`.
- Enter your admin email/password when prompted.

### Step 3 - Run every time
Double-click `START_WINDOWS.bat`.
- Dashboard: `http://localhost:5173`
- API docs: `http://localhost:8000/api/docs`

## Run Modes

### 1) Localhost (same PC)
Use `START_WINDOWS.bat`. This is the default developer flow.

### 2) Same Wi-Fi / LAN (different PC)
Run frontend in LAN mode:
```bash
cd frontend
npm run dev:lan
```
Then open `http://<SERVER_LAN_IP>:5173` from another PC on the same network.

### 3) Different networks (internet test)
Recommended for testing: expose frontend with a tunnel (ngrok or Cloudflare Tunnel).

Example with ngrok:
```bash
ngrok http 5173
```
Use the generated HTTPS URL on any network. Since Vite proxies `/api` to backend, localhost testing still works unchanged on your main machine.

One-click option (Windows):
```bash
START_WORLDWIDE_TEST.bat
```
This launches backend, frontend LAN mode, and ngrok together.

If you expose backend directly (not through Vite proxy), update `backend/.env`:
- `CORS_ORIGINS` must include your frontend public URL.
- `TRUSTED_HOSTS` must include your backend host/domain.

## Adding employees and monitoring
1. Go to Employees and add an employee.
2. Open Enroll Device, enter server URL, and generate a code.
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
Use the admin email/password configured during `SETUP_WINDOWS.bat`.
