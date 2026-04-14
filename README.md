# PulseDesk — Employee Monitoring System v4
Production-ready. All features working.

## Quick Start (3 steps)

### Step 1 — Create PostgreSQL database
```sql
CREATE DATABASE pulsedesk;
```

### Step 2 — First time setup
Double-click **SETUP_WINDOWS.bat**
- When Notepad opens, change `YOUR_PASSWORD` to your PostgreSQL password
- Configure `GROQ_API_KEY`, `SECRET_KEY`, and `DEVICE_TOKEN_SECRET`
- Enter your admin email/password when prompted (used for first login)
- Save and close → setup continues automatically

### Step 3 — Run every time
Double-click **START_WINDOWS.bat**
→ Opens dashboard at http://localhost:5173
→ Login with the admin credentials you entered during setup

---

## Adding employees & monitoring

1. **Employees** → **Add employee** → fill in name + email
2. **Enroll device** → enter server URL → click Generate
3. Copy the 6-digit code
4. Employee visits `http://YOUR-LAN-IP:8000/join` in browser
5. Enters code → clicks Download → extracts ZIP
6. Runs `INSTALL_AGENT.bat` once → `START_AGENT.bat` every time

---

## Features
- Live activity monitoring with real-time WebSocket updates
- Workday timeline, hourly heatmap, app usage breakdown
- Productivity scores computed from keyboard/mouse activity
- Leaderboard with rankings and streaks
- Anomaly detection: idle, distraction, after-hours, blocked sites
- Website/domain blocking with violation alerts
- Screenshot capture (create an interval policy in Screenshots page)
- PDF reports per employee or team
- Dark mode

## URLs
| URL | Purpose |
|-----|---------|
| http://localhost:5173 | Admin dashboard |
| http://localhost:8000/join | Employee join portal |
| http://localhost:8000/api/docs | API documentation |

## Credentials
Use the admin email/password configured during `SETUP_WINDOWS.bat`.
