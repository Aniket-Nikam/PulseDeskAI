# PulseDesk Technical Handbook

## 1. Purpose and Scope
This handbook explains how PulseDesk is built and how it works in production-like usage.
It covers:
- Languages, frameworks, and tools used in each layer
- Backend, frontend, and agent internals
- Data flow from user activity capture to dashboard visualization
- AI integration and fallback behavior
- Security and reliability posture
- Current limitations and hardening roadmap

Important scope note:
- The repository has roughly 18k+ lines of core code. A literal sentence for every single line is not practical in one file.
- This document gives deep module-level coverage with line-aware references through `CODEBASE_SYMBOL_INDEX.md`.
- For true line-by-line walkthrough, use this file together with `CODEBASE_SYMBOL_INDEX.md`.

## 2. Project Outcome in One Paragraph
PulseDesk is a three-part monitoring platform:
- A desktop agent collects activity samples (active app, window title, idle time, input counters).
- A FastAPI backend validates device identity, stores telemetry, computes productivity and anomalies, and serves APIs.
- A React dashboard visualizes live and historical data, manages employees/devices/policies, and calls AI-assisted insights.

The architecture is workable for local deployment and small teams, with clear paths to production hardening.

## 3. Source Footprint and Structure
Approximate core source size (excluding `venv`, `node_modules`, `dist`, caches):
- `backend/app`: ~50 files, ~9056 lines
- `frontend/src`: ~34 files, ~8327 lines
- `agent`: ~11 files, ~1475 lines

Top-level directories:
- `backend/`: FastAPI app, business logic, models, AI integration
- `frontend/`: React TypeScript dashboard
- `agent/`: Python endpoint monitoring client
- `logs/`: runtime logs from launcher scripts

## 4. Languages, Frameworks, and Tooling

### 4.1 Backend stack (Python)
Source: `backend/requirements.txt`

Runtime and API:
- `fastapi==0.111.0`
- `uvicorn[standard]==0.29.0`

Data and ORM:
- `sqlalchemy==2.0.30`
- `alembic==1.13.1`
- `asyncpg==0.29.0`
- `psycopg[binary]==3.1.19` (Windows)

Validation and config:
- `pydantic==2.7.1`
- `pydantic-settings==2.2.1`

Security:
- `python-jose[cryptography]==3.3.0` for JWT
- `passlib[bcrypt]==1.7.4` and `bcrypt==4.0.1`

Other core libs:
- `python-multipart`, `aiofiles`, `pillow`, `websockets`, `httpx`, `structlog`, `python-dotenv`, `fpdf2`, `groq`

Why this stack:
- FastAPI + Pydantic gives strict API contracts.
- SQLAlchemy async supports structured relational telemetry and analytics queries.
- JWT + bcrypt is a standard pattern for admin auth.
- Structlog enables machine-readable JSON logs.

### 4.2 Frontend stack (TypeScript + React)
Source: `frontend/package.json`

Core:
- React 18 + TypeScript 5
- Vite 5 bundler/dev server
- React Router 6 routing

State and data:
- TanStack Query for server cache and refetch behavior
- Zustand (persist middleware) for auth session state
- Axios for HTTP calls and interceptor-based token refresh

Visualization and utilities:
- Recharts
- date-fns
- clsx
- lucide-react

Styling toolchain present:
- Tailwind, PostCSS, Autoprefixer in dependencies
- The app mostly uses custom CSS variables and utility classes in project styles

### 4.3 Agent stack (Python)
Source: `agent/requirements.txt`

Key libs:
- `requests` for backend communication
- `sqlite3` (stdlib) for local offline queue persistence
- `tenacity` for enrollment retry
- `pynput` for keyboard/mouse counters
- `mss` and `Pillow` for screenshot capture
- `pywinauto` for Windows window support

Why this stack:
- Requests + SQLite is simple and robust for intermittent connectivity.
- Low-level input/window libs allow near-real-time desktop activity capture.

### 4.4 Developer and runtime scripts
Windows operational scripts:
- `SETUP_WINDOWS.bat`: first-time environment setup
- `START_WINDOWS.bat`: local backend + frontend launch
- `START_WORLDWIDE_TEST.bat`: LAN frontend + ngrok tunnel flow

## 5. End-to-End Architecture

### 5.1 Core components
1. Agent
- Captures periodic events on employee machine
- Maintains local buffer and offline retry queue
- Sends heartbeat/events/screenshots
- Pulls active blocked-domain rules

2. Backend
- Validates admin and device identities
- Persists telemetry and policy data
- Computes scores/summaries/anomalies
- Exposes APIs for dashboard and agent
- Pushes live updates over WebSocket

3. Frontend
- Admin dashboard for operations and analytics
- Uses protected routes and automatic session refresh
- Renders live status, trend charts, and control actions

### 5.2 Main telemetry flow
1. Agent captures sample.
2. Agent batches events and posts to `/api/v1/agent/events`.
3. Backend resolves approved device and active session.
4. Backend stores `ActivityEvent` rows and updates `WorkSession` totals.
5. Backend runs anomaly rules.
6. Backend schedules summary recomputation task.
7. Backend broadcasts latest employee update via WebSocket.
8. Frontend queries or listens and updates UI.

## 6. Backend Deep Dive

### 6.1 Application bootstrap and middleware
Main file: `backend/app/main.py`

Startup behavior:
- Initializes structured logging.
- Validates cookie security settings.
- Ensures screenshot directory exists.
- Checks DB connection.
- Auto-creates schema via `ensure_schema_ready()`.

API composition:
- FastAPI app at version `5.0.0`
- API docs at `/api/docs`
- All main routers under `/api/v1`
- Join portal router mounted directly (for `/join` UX)

Middleware chain:
- CORS with explicit origin list from config
- TrustedHost middleware with host allowlist
- CSRF origin enforcement for cookie-auth write requests
- Security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cache-Control`

Exception strategy:
- Service exceptions mapped to structured HTTP errors
- Validation errors normalized to `field/message`
- Generic exception handler logs type and returns 500

### 6.2 Configuration and environment safety
File: `backend/app/core/config.py`

Highlights:
- Typed settings via Pydantic Settings.
- Secrets enforced with validators:
  - `SECRET_KEY` and `DEVICE_TOKEN_SECRET` minimum length 32.
  - Placeholder-like values rejected.
- CORS/trusted-host JSON parsing from env strings.
- Cookie safety check:
  - If `COOKIE_SAMESITE=none`, then `COOKIE_SECURE` must be true.

AI-related settings:
- `AI_ENABLED`
- `GROQ_API_KEY`
- `GROQ_PRIMARY_MODEL` and `GROQ_MODEL`
- `AI_REQUEST_TIMEOUT_SECONDS`
- `AI_SCREENSHOT_ANALYSIS_ENABLED`

Operational settings:
- Rate limits for auth, enrollment, join flow, agent upload
- Batch and heartbeat limits
- Join token/code TTL settings

### 6.3 Logging and observability behavior
File: `backend/app/core/logging.py`

Implementation:
- Python logging configured by `LOG_LEVEL`.
- Structlog processors include timestamp and log level.
- Renderer:
  - Console renderer in DEBUG
  - JSON renderer otherwise

Impact:
- Production logs are structured and can be ingested by ELK/Loki/Datadog.

### 6.4 Authentication and authorization
Main files:
- `backend/app/core/security.py`
- `backend/app/api/v1/routes/auth.py`

Password model:
- Bcrypt hash via Passlib context
- `verify_password` for login checks

JWT model:
- Access and refresh tokens
- Claims include `exp`, `iat`, `nbf`, `jti`, `iss`, `aud`, `type`
- Token type is explicitly validated (`access` vs `refresh`)

Auth transport:
- Supports bearer header and HttpOnly cookies
- Cookies set with configurable `secure/samesite/domain/path`

Role model:
- `super_admin`, `admin`, `manager`, `employee`
- Read operations allow super_admin/admin/manager
- Write operations allow super_admin/admin

Rate limiting:
- Login and refresh endpoints explicitly rate-limited.

### 6.5 Rate limiting design
File: `backend/app/core/rate_limit.py`

Implementation:
- Sliding-window in-memory limiter using deques.
- Key includes prefix + client IP + path.
- Optional auth fingerprint and custom identifiers.

Tradeoff:
- Works for single-process deployments.
- Not shared across multiple backend instances.

### 6.6 Database session and schema behavior
File: `backend/app/db/session.py`

Behavior:
- Async engine with pool settings and pre-ping.
- Session dependency rolls back on exceptions.
- Startup checks DB connectivity.
- Current implementation auto-creates tables at startup (`Base.metadata.create_all`).

Important operational note:
- There is a mixed migration posture:
  - File docstring mentions Alembic-first workflow.
  - Runtime still auto-creates schema.
- For strict production governance, choose one strategy clearly.

### 6.7 Data model (what each table means)
File: `backend/app/models/__init__.py`

Core identity tables:
- `Admin`: dashboard users and roles
- `Department`
- `Employee`
- `Device`: enrolled endpoints and status (`pending/approved/revoked/suspended`)

Telemetry tables:
- `WorkSession`: session-level totals and score
- `ActivityEvent`: per-sample detailed events
- `DailySummary`: pre-aggregated day-level metrics

Policy and alerting tables:
- `AnomalyLog`
- `ScreenshotPolicy`
- `Screenshot`
- `BlockedSiteRule` (model exists; current route logic uses in-memory blocker map)
- `SystemSettings` for anomaly thresholds

Management and audit:
- `AdminAuditLog`
- `ActionItem`

### 6.8 Route map and responsibilities
Router assembly: `backend/app/api/v1/__init__.py`

Main route groups:
- `auth.py`: login, refresh, logout, profile, admin creation
- `employees.py`: department and employee management
- `devices.py`: enrollment listing, approval/revoke, deletion
- `agent.py`: heartbeat, sessions, event ingest
- `analytics.py`: overview, leaderboard, timeline, heatmap, summaries, anomalies, dept comparison
- `screenshots.py`: upload, view, cleanup, policy management, agent poll
- `blocker.py`: blocked domains, active sync list, violation ingestion, summaries
- `ai_insights.py`: chat, recommendations, diagnostics
- `actions.py`: action item CRUD and completion stats
- `enrollment.py` and `join_portal.py`: onboarding token/code/package flows
- `reports.py`: PDF export endpoints
- `ws.py`: websocket channel

### 6.9 Agent ingestion internals
File: `backend/app/api/v1/routes/agent.py`

Important behavior:
- Validates approved device token before accepting data.
- Enforces batch size limit (`BATCH_SIZE_LIMIT`).
- Resolves or creates active `WorkSession`.
- Converts incoming events into `ActivityEvent` rows.
- Categorizes app names via categorizer service.
- Updates session aggregates and productivity score.
- Runs anomaly checks after commit.
- Triggers async summary recompute using `asyncio.create_task`.
- Broadcasts latest employee activity via websocket.

Reliability caveat:
- `asyncio.create_task` work is non-durable if process exits.

### 6.10 Scoring and summary computation
Files:
- `backend/app/services/scoring.py`
- `backend/app/services/aggregator.py`

Summary logic:
- Aggregates total tracked, active, idle, focus, switches.
- Builds hourly active heatmap map.
- Determines top app and top category.
- Calculates productivity score with weighted components:
  - active ratio
  - productive category ratio
  - switch penalty
  - focus bonus
- Upserts `DailySummary` for each employee/date.

### 6.11 Anomaly detection engine
File: `backend/app/services/anomaly_detector.py`

Rule families:
- Excessive idle
- Rapid app switching
- After-hours activity
- Distraction-category usage
- Blocked domain usage

Characteristics:
- Rule-based deterministic engine.
- Uses `SystemSettings` thresholds when present.
- Cooldowns applied to prevent duplicate noise.
- Enriches anomaly metadata with severity/risk/recommended action.
- Broadcasts anomaly events to dashboard websocket.

### 6.12 Website blocker behavior
File: `backend/app/api/v1/routes/blocker.py`

Current design:
- Uses in-memory `_blocked_domains` dictionary.
- Auto-loads default blocked domains at process start.
- Agent syncs active list through `/blocker/domains/active-list`.
- Agent reports domain violations to `/blocker/violation`.
- Violations persisted as `AnomalyLog` entries with `violation_type=blocked_domain`.

Tradeoff:
- In-memory rules are not shared across instances and are reset on restart.

### 6.13 Screenshot subsystem
File: `backend/app/api/v1/routes/screenshots.py`

Upload path:
- Agent uploads image via multipart endpoint.
- Device token and status are validated.
- Content-type and max size checks enforced.
- Optional compression performed.
- File saved under configured screenshot directory.
- DB record created in `screenshots` table.

View path:
- Supports bearer, query token, or cookie auth.
- Token validated and admin checked.
- File path joined with `safe_path_join` to prevent traversal.

Policy path:
- Admin can create/toggle/delete screenshot policies.
- Implementation keeps one active policy at a time.

### 6.14 Enrollment and join workflows
Files:
- `backend/app/api/v1/routes/enrollment.py`
- `backend/app/api/v1/routes/join_portal.py`
- `backend/app/services/token_store.py`

Two onboarding modes:
1. Join URL token flow (`/enroll/generate-link` and `/enroll/join/{token}`)
2. Join code + web portal flow (`/join`, `/join/verify`, `/join/download/{token}`)

Token store behavior:
- In-memory token records with hash, TTL, consumed flags.
- Supports issue/get/consume/update/delete/active listing.

Package generation behavior:
- Join portal builds ZIP in memory with:
  - prefilled `.env`
  - install/start scripts
  - required agent source files

Tradeoff:
- In-memory token store is process-local.

### 6.15 AI subsystem
Files:
- `backend/app/ai/service.py`
- `backend/app/ai/providers/groq_provider.py`
- `backend/app/api/v1/routes/ai_insights.py`

Provider behavior:
- Groq client created lazily using `GROQ_API_KEY`.
- Requests wrapped with timeout and error translation.

Feature behavior:
- Chat assistant with team context prompt.
- Work recommendations from summary/anomaly metrics.
- Anomaly recommendation generation.
- Burnout and activity pattern deterministic analysis.
- Diagnostics endpoint to verify data availability.

Reliability behavior:
- If AI fails or disabled, service returns heuristic fallback response.
- Response includes `source` (`groq` or `heuristic`).

### 6.16 WebSocket live updates
Files:
- `backend/app/api/v1/routes/ws.py`
- `backend/app/services/ws_broadcaster.py`

Implementation:
- In-memory active connection list.
- Broadcast helpers for employee update, device status, anomaly.

Tradeoff:
- No cross-instance pub/sub; scoped to one process.

## 7. Frontend Deep Dive

### 7.1 App bootstrap and providers
Files:
- `frontend/src/main.tsx`
- `frontend/src/App.tsx`

Behavior:
- React StrictMode root.
- QueryClient provider with defaults:
  - retry=1
  - staleTime=30s
  - no refetch on window focus
- BrowserRouter route tree.
- Session validation on startup:
  - call `/auth/me`
  - on 401 attempt `/auth/refresh`
  - logout if refresh fails

### 7.2 Route structure
Main routes under protected app layout:
- Overview, live screens, graph, analytics, leaderboard, reports
- Employees, departments, devices, anomalies, blocker, screenshots
- AI insights, action items, settings

Auth gates:
- `RequireAuth`
- `RequireUnauth`

### 7.3 API client and auth refresh logic
File: `frontend/src/api/client.ts`

Implementation:
- Axios instance with `withCredentials=true`.
- 401 interceptor with refresh deduplication (`_refreshing` promise).
- Prevents refresh loop on `/auth/*` routes.
- On refresh failure:
  - clear auth store
  - redirect to `/login`

Modules exported by concern:
- `authApi`, `employeesApi`, `departmentsApi`, `devicesApi`
- `analyticsApi`, `blockerApi`, `actionsApi`, `settingsApi`
- `reportsApi`, `aiApi`, `enrollApi`

### 7.4 Auth state management
File: `frontend/src/store/authStore.ts`

Implementation:
- Zustand with persist middleware.
- Storage key: `pulsedesk-auth-v2`.
- Persisted data: `admin` only.
- Hydration flag used to avoid early route flicker.

### 7.5 Devices page behavior (revoke/delete flow)
File: `frontend/src/pages/DevicesPage.tsx`

Implemented UX behavior:
- Approved device row shows `Revoke` action.
- Revoked device row shows `Delete` action.
- Query invalidation refreshes list after mutation.
- Errors shown using API `detail` when available.
- Empty-state filler is present for both tabs.

This matches backend policy:
- Device must be revoked before permanent delete.

### 7.6 Build and local proxy behavior
File: `frontend/vite.config.ts`

Dev server:
- Port 5173
- Proxy `/api` and `/join` to backend at `localhost:8000`
- WebSocket proxy enabled for `/api`

Implication:
- Frontend can call same-origin relative API paths during development.

## 8. Agent Deep Dive

### 8.1 Agent runtime orchestration
Main file: `agent/agent.py`

Startup sequence:
- Load config.
- Build offline queue and API client.
- Ensure server URL exists.
- Enroll if needed (retry via Tenacity).
- Send heartbeat.
- Force initial blocklist sync.
- Start input monitor and session.
- Enter sampling loop.

Main loop periodic actions:
- Sample capture every `sample_interval`.
- Event batch send at `batch_interval`.
- Heartbeat at `heartbeat_interval`.
- Screenshot policy poll every 60s.
- Blocklist sync every 300s.

### 8.2 Event capture model
Per sample data includes:
- UTC timestamp
- activity type (`active` or `idle`)
- active app and window title
- keystrokes/mouse counters
- mouse distance
- idle duration
- sample duration

Idle guard:
- Protects against invalid infinity/NaN idle values.

### 8.3 Local violation detection behavior
The agent checks current app/title/url against synced blocked domains.
If match occurs:
- Local cooldown prevents repeated immediate reports for same domain.
- Agent reports violation to backend.
- If backend requests screenshot, agent captures and uploads immediately.

### 8.4 Screenshot capture strategy
Capture order:
- Try `mss` first
- Fallback to Pillow ImageGrab

Upload:
- Multipart post with `device_token`, timestamp, trigger

### 8.5 Offline queue and state persistence
Files:
- `agent/sync/queue.py`
- `agent/sync/client.py`

Queue design:
- SQLite tables: `event_queue`, `agent_state`
- WAL mode enabled
- Thread lock around queue writes

Delivery behavior:
- Flush queued batches before sending new events.
- Stop flush on first failure to preserve order.
- Save `device_token`, `device_id`, and `session_id` in state table.

### 8.6 Join URL auto-enrollment behavior
Agent can run with `--join <url>`:
- Calls join URL
- Saves returned device credentials
- Writes or updates local `.env`
- Continues as enrolled client

## 9. Data Flow by Feature

### 9.1 Employee productivity analytics
- Agent emits activity samples.
- Backend stores events and updates sessions.
- Aggregator computes daily summaries.
- Analytics endpoints return overview/timeline/heatmap/leaderboard.
- Frontend charts render these results.

### 9.2 Device approval and deprovisioning
- Agent enrolls and device enters pending or receives token in join flow.
- Admin approves via devices page.
- Admin can revoke approved device.
- Admin can delete only revoked device.
- Backend deletes dependent telemetry rows before deleting device.

### 9.3 Blocked domain monitoring
- Admin edits blocked list.
- Agent syncs active domains.
- Agent detects matches and reports violations.
- Backend stores anomaly and notifies websocket listeners.
- Frontend can review violation summary/list.

### 9.4 Screenshot policy cycle
- Admin enables interval policy.
- Agent polls `screenshot-required` endpoint.
- Agent captures and uploads when required.
- Backend stores file + metadata.
- Admin views image via protected endpoint.

### 9.5 AI insights flow
- Dashboard calls AI endpoints.
- Service builds context from summaries and anomalies.
- Groq provider generates text when available.
- On provider failure, heuristic output is returned.

## 10. Security Assessment

### 10.1 Security strengths already implemented
- Password hashing with bcrypt.
- JWT claim discipline with issuer/audience/type.
- Cookie auth with HttpOnly and samesite/secure validation.
- Role-based read/write gate separation.
- CSRF origin guard for cookie-auth writes.
- CORS and trusted-host controls.
- Route-level rate limiting across sensitive endpoints.
- Path-safe screenshot file serving.
- Admin audit logging in key actions.

### 10.2 Main security and architecture risks
1. In-memory token store
- Join/enrollment tokens are not shared across instances.

2. In-memory rate limiter
- Limits are process-local.

3. In-memory blocklist state
- Rules reset on backend restart and do not synchronize across nodes.

4. Join package confidentiality
- Downloaded package includes device token by design.
- If package leaks, token misuse is possible until revoked.

5. Non-durable background tasks
- `asyncio.create_task` work may be lost on process crash/redeploy.

6. Screenshot privacy governance
- Data capture is implemented, but enterprise retention/audit controls need stricter policy governance.

### 10.3 Recommended hardening actions
- Move token store and rate limiting to Redis.
- Persist blocklist in DB and cache it with explicit invalidation.
- Move background jobs to durable worker system (Celery/Arq/RQ).
- Rotate device tokens and add explicit token revocation list.
- Add comprehensive security tests (auth, CSRF, access control, path traversal).
- Add encryption-at-rest and access auditing for screenshot artifacts.

## 11. Reliability and Scalability Assessment

### 11.1 Reliability strengths
- Agent offline queue avoids immediate data loss during network outages.
- Enrollment retry and queue replay reduce operational friction.
- AI fallback keeps endpoints responsive when provider fails.
- Structured logging improves troubleshooting.

### 11.2 Bottlenecks and single-node assumptions
- In-memory limiter/token/blocklist/websocket connection manager.
- Some analytics endpoints perform per-employee loops (N+1 style behavior).
- Background tasks are fire-and-forget.

### 11.3 Scale roadmap
- Introduce Redis for shared state.
- Use worker queue for summary and screenshot AI tasks.
- Add DB indexes and query tuning for heavy analytics.
- Partition large telemetry tables by time.
- Add pub/sub websocket fanout for multi-node real-time updates.

## 12. Testing and Quality Posture
Current repo includes smoke-style scripts such as:
- `backend/smoke_test_routes.py`
- `backend/test_screenshot_api.py`
- `backend/test_final.py`

Current gap:
- Limited unit tests for service logic.
- Limited contract tests for endpoint behavior.
- No explicit load tests in repo.

Recommended test strategy:
- Unit tests for scoring, anomaly thresholds, and token handling.
- Integration tests for auth, devices, enrollment, screenshots, blocker.
- Performance tests for event ingestion and analytics endpoints.

## 13. Deployment and Hosting Readiness

### 13.1 Current local hosting scripts
- `SETUP_WINDOWS.bat` prepares Python venv, installs deps, configures `.env`, runs migrations, and seeds admin.
- `START_WINDOWS.bat` launches backend on `0.0.0.0:8000` and frontend on `5173`.
- `START_WORLDWIDE_TEST.bat` adds ngrok for cross-network testing.

### 13.2 Can this be hosted publicly?
Yes, with hardening.

Minimum production checklist:
- HTTPS termination and secure cookie settings (`COOKIE_SECURE=true`).
- Strong secrets (`SECRET_KEY`, `DEVICE_TOKEN_SECRET`) and key rotation.
- Managed PostgreSQL and backups.
- Redis for shared cache/limits/token state.
- Process manager and health monitoring.
- Centralized logs and alerting.

## 14. How the Team Achieved Core Goals
Goal: end-to-end employee activity visibility with operational controls and AI assistance.

How it was achieved:
1. Capture layer
- Built a sampling agent with window/input capture and heartbeat.

2. Secure ingest layer
- Built device-token validated ingestion endpoints with status checks.

3. Data model layer
- Designed normalized telemetry/session/anomaly/screenshot schema.

4. Insight layer
- Implemented scoring + daily summary aggregation + anomaly detection.

5. Control layer
- Added admin features for employees, devices, policies, blocker, reports.

6. AI augmentation layer
- Integrated Groq provider and deterministic fallbacks.

7. Operational layer
- Added one-click setup/start scripts for Windows workflows.

## 15. Practical Line-by-Line Study Method
Use these two documents together:
- `PROJECT_FULL_TECHNICAL_EXPLANATION.md`
- `CODEBASE_SYMBOL_INDEX.md`

Recommended reading order:
1. Backend core (`main.py`, config, security, db session)
2. Auth and route layer
3. Telemetry services (`agent.py`, anomaly detector, aggregator)
4. Frontend app shell and API client
5. Feature pages by business area
6. Agent runtime and sync queue

This method provides real line-level understanding while keeping architecture context.

## 16. Final Technical Verdict
Current maturity:
- Strong functional platform for local and small-team deployment.
- Good feature coverage across monitoring, analytics, policy control, and reporting.
- Security-aware implementation in several critical areas.

What blocks enterprise-grade readiness today:
- Process-local state in critical control paths.
- Non-durable background task execution.
- Limited automated test depth.
- Some scaling and observability gaps.

With focused hardening on shared state, background jobs, and test coverage, PulseDesk can move from robust prototype to production-grade system.
