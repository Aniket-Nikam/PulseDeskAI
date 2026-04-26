# Codebase Symbol Index

Total files indexed: 95

## `agent/agent.py` (349 lines)
Top-level symbols:
- 41: def handle_join_url
- 59: def update_or_add
- 87: class PulseDeskAgent
- 88: def __init__
- 101: def start
- 152: def _ensure_enrolled
- 169: def _run_loop
- 197: def _take_sample
- 229: def _check_blocklist
- 258: def _sync_blocklist
- 262: def _do_heartbeat
- 266: def _send_batch
- 274: def _maybe_take_screenshot
- 279: def _take_and_upload_screenshot
- 317: def _handle_signal
- 326: def main

## `agent/capture/input_monitor.py` (144 lines)
Top-level symbols:
- 17: class InputSample
- 23: def reset
- 37: class InputMonitor
- 43: def __init__
- 51: def start
- 71: def safe_convert
- 99: def stop
- 107: def take_sample
- 112: def get_idle_seconds
- 119: def _on_key_press
- 125: def _on_mouse_click
- 132: def _on_mouse_move

## `agent/capture/window_tracker.py` (248 lines)
Top-level symbols:
- 25: def get_active_window
- 41: def get_active_browser_url
- 54: def _coerce_url_candidate
- 83: def _get_active_browser_url_windows
- 131: def _get_active_window_windows
- 159: def _get_active_window_macos
- 188: def _get_active_window_linux
- 237: def _get_active_window_linux_subprocess

## `agent/core/config.py` (45 lines)
Top-level symbols:
- 9: class AgentConfig
- 21: def from_env
- 22: def safe_int

## `agent/DISABLE_AGENT_AUTOSTART.bat` (19 lines)
- No top-level symbols detected (likely constants/styles/markup).

## `agent/ENABLE_AGENT_AUTOSTART.bat` (33 lines)
- No top-level symbols detected (likely constants/styles/markup).

## `agent/INSTALL_AGENT.bat` (90 lines)
- No top-level symbols detected (likely constants/styles/markup).

## `agent/START_AGENT.bat` (40 lines)
- No top-level symbols detected (likely constants/styles/markup).

## `agent/START_AGENT_SILENT.bat` (19 lines)
- No top-level symbols detected (likely constants/styles/markup).

## `agent/sync/client.py` (374 lines)
Top-level symbols:
- 25: def _normalize_domain
- 31: def _extract_host
- 51: def _extract_hosts_from_text
- 61: def _host_matches
- 66: class PulseDeskClient
- 67: def __init__
- 95: def is_enrolled
- 99: def is_online
- 103: def blocklist
- 106: def _post
- 125: def _get
- 136: def sync_blocklist
- 155: def check_window_against_blocklist
- 200: def force_sync_blocklist
- 205: def report_violation
- 238: def check_screenshot_required
- 250: def upload_screenshot
- 268: def enroll
- 290: def start_session
- 304: def end_session
- 314: def send_heartbeat
- 331: def send_events
- 357: def _flush_offline_queue

## `agent/sync/queue.py` (114 lines)
Top-level symbols:
- 34: class OfflineSyncQueue
- 40: def __init__
- 45: def _init_db
- 52: def enqueue_batch
- 63: def dequeue_batch
- 73: def mark_sent
- 86: def mark_failed
- 95: def pending_count
- 99: def save_state
- 109: def load_state

## `backend/app/__init__.py` (3 lines)
- No top-level symbols detected (likely constants/styles/markup).

## `backend/app/ai/__init__.py` (2 lines)
- No top-level symbols detected (likely constants/styles/markup).

## `backend/app/ai/prompts/__init__.py` (2 lines)
- No top-level symbols detected (likely constants/styles/markup).

## `backend/app/ai/prompts/chat.py` (17 lines)
Top-level symbols:
- 4: def build_chat_system_prompt

## `backend/app/ai/prompts/work_report.py` (22 lines)
Top-level symbols:
- 4: def build_weekly_report_prompt

## `backend/app/ai/providers/__init__.py` (2 lines)
- No top-level symbols detected (likely constants/styles/markup).

## `backend/app/ai/providers/base.py` (26 lines)
Top-level symbols:
- 8: class AIProviderError
- 13: def __str__
- 17: class AIProvider
- 18: async def generate_text

## `backend/app/ai/providers/factory.py` (11 lines)
Top-level symbols:
- 7: def get_active_provider

## `backend/app/ai/providers/groq_provider.py` (86 lines)
Top-level symbols:
- 15: class GroqProvider
- 16: def __init__
- 21: def _get_client
- 29: def _sync_generate
- 54: async def generate_text

## `backend/app/ai/schemas.py` (105 lines)
Top-level symbols:
- 9: class ChatHistoryItem
- 14: class ChatRequest
- 19: class ChatResponse
- 24: class BurnoutEmployee
- 34: class BurnoutResponse
- 39: class ActivityPatternsResponse
- 51: class WorkReportMetrics
- 58: class WorkRecommendationsResponse
- 76: class AnomalyRecommendationStats
- 85: class AnomalyRecommendationResponse
- 94: class AIDiagnosticsResponse

## `backend/app/ai/service.py` (872 lines)
Top-level symbols:
- 43: def _clean_json_text
- 47: class AIInsightsService
- 48: def __init__
- 52: def ai_enabled
- 56: def _compute_risk_level
- 66: def _normalize_severity
- 73: def _extract_anomaly_severity
- 91: def _summarize_anomaly_stats
- 120: def _heuristic_anomaly_recommendation
- 144: def _build_anomaly_recommendation_prompt
- 183: async def _build_team_context
- 247: async def _heuristic_chat_response
- 275: async def chat
- 300: async def burnout_risks
- 419: async def activity_patterns
- 510: async def _build_work_report_data
- 543: def _heuristic_work_report
- 606: async def work_recommendations
- 737: async def anomaly_recommendation
- 828: async def diagnostics

## `backend/app/api/v1/__init__.py` (22 lines)
- No top-level symbols detected (likely constants/styles/markup).

## `backend/app/api/v1/routes/actions.py` (264 lines)
Routes:
- 85: POST "/", response_model=ActionItemResponse
- 127: GET "/{item_id}", response_model=ActionItemResponse
- 143: GET "/employee/{employee_id}", response_model=List[ActionItemResponse]
- 166: PATCH "/{item_id}", response_model=ActionItemResponse
- 210: DELETE "/{item_id}"
- 232: GET "/employee/{employee_id}/completion-stats"
Top-level symbols:
- 27: class ActionItemCreate
- 36: def validate_priority
- 43: class ActionItemUpdate
- 51: def validate_priority
- 60: class ActionItemResponse
- 72: def serialize_uuid
- 76: def serialize_datetime
- 79: class Config
- 86: async def create_action_item
- 128: async def get_action_item
- 144: async def get_employee_action_items
- 167: async def update_action_item
- 211: async def delete_action_item
- 233: async def get_completion_stats

## `backend/app/api/v1/routes/agent.py` (339 lines)
Routes:
- 54: POST "/agent/heartbeat", response_model=HeartbeatOut
- 90: PATCH "/agent/device-info"
- 125: POST "/agent/session/start", response_model=dict
- 164: POST "/agent/session/end", status_code=200
- 195: POST "/agent/events", response_model=BatchResponse
Top-level symbols:
- 36: class DeviceInfoPatchRequest
- 44: async def _get_approved_device
- 55: async def heartbeat
- 91: async def update_device_info
- 126: async def start_session
- 165: async def end_session
- 196: async def ingest_events

## `backend/app/api/v1/routes/ai_insights.py` (59 lines)
Routes:
- 27: POST "/chat", response_model=ChatResponse
- 36: GET "/work-recommendations/{employee_id}", response_model=WorkRecommendationsResponse
- 45: GET "/anomaly-recommendation/{employee_id}", response_model=AnomalyRecommendationResponse
- 54: GET "/diagnostics/data-status", response_model=AIDiagnosticsResponse
Top-level symbols:
- 28: async def ai_chat
- 37: async def work_recommendations
- 46: async def anomaly_recommendation
- 55: async def data_status

## `backend/app/api/v1/routes/analytics.py` (561 lines)
Routes:
- 39: GET "/overview"
- 121: GET "/leaderboard"
- 219: GET "/timeline/{employee_id}"
- 272: GET "/heatmap/{employee_id}"
- 312: GET "/app-usage/{employee_id}"
- 360: GET "/summaries/{employee_id}"
- 430: GET "/department-comparison"
- 504: GET "/anomalies"
- 538: PATCH "/anomalies/{anomaly_id}/review"
- 556: POST "/recompute-summaries"
Top-level symbols:
- 40: async def get_live_overview
- 122: async def get_leaderboard
- 220: async def get_timeline
- 273: async def get_heatmap
- 313: async def get_app_usage
- 361: async def get_summaries
- 431: async def get_dept_comparison
- 505: async def get_anomalies
- 539: async def review_anomaly
- 557: async def recompute

## `backend/app/api/v1/routes/auth.py` (312 lines)
Routes:
- 149: POST "/login", response_model=TokenResponse
- 195: POST "/refresh", response_model=TokenResponse
- 246: POST "/logout", status_code=200
- 261: GET "/me", response_model=AdminOut
- 267: POST "/admins", response_model=AdminOut, status_code=201
- 295: POST "/change-password", status_code=200
Top-level symbols:
- 28: def _set_auth_cookies
- 61: def _clear_auth_cookies
- 84: def _token_from_request
- 96: async def get_current_admin
- 132: def require_role
- 133: async def checker
- 144: class ChangePasswordRequest
- 150: async def login
- 196: async def refresh
- 247: async def logout
- 262: async def get_me
- 268: async def create_admin
- 296: async def change_password

## `backend/app/api/v1/routes/blocker.py` (563 lines)
Routes:
- 238: GET "/domains", response_model=List[dict]
- 244: POST "/domains", status_code=201
- 270: DELETE "/domains/{domain_id}", status_code=204
- 278: PATCH "/domains/{domain_id}/toggle"
- 287: POST "/load-defaults", status_code=201
- 314: GET "/domains/active-list"
- 351: POST "/violation"
- 489: GET "/violations/summary"
- 550: GET "/violations", response_model=List[dict]
Top-level symbols:
- 29: def _metadata_text
- 38: def _normalize_domain
- 44: def _domain_matches
- 50: def _find_block_rule
- 57: def _metadata_domains
- 86: def _domain_detail
- 95: def _serialize_violation
- 129: async def _blocked_violation_rows
- 164: class BlockedDomain
- 178: def validate_domain
- 187: class BlockViolation
- 214: def _auto_load_defaults
- 239: async def list_blocked_domains
- 245: async def add_blocked_domain
- 271: async def remove_blocked_domain
- 279: async def toggle_domain
- 288: async def load_default_blocks
- 315: async def get_active_blocklist
- 352: async def report_violation
- 490: async def get_violation_summary
- 551: async def list_blocked_site_violations

## `backend/app/api/v1/routes/devices.py` (109 lines)
Routes:
- 19: POST "/enroll", response_model=DeviceEnrollResponse, status_code=201
- 50: GET "", response_model=PaginatedResponse[DeviceOut]
- 67: GET "/pending", response_model=PaginatedResponse[DeviceOut]
- 84: PATCH "/{device_id}/status", response_model=DeviceOut
- 102: DELETE "/{device_id}", status_code=204
Top-level symbols:
- 20: async def enroll_device
- 51: async def list_devices
- 68: async def list_pending_devices
- 85: async def update_device_status
- 103: async def delete_device

## `backend/app/api/v1/routes/employees.py` (110 lines)
Routes:
- 27: POST "/departments", response_model=DepartmentOut, status_code=201
- 38: GET "/departments", response_model=List[DepartmentOut]
- 46: DELETE "/departments/{dept_id}", status_code=204
- 58: POST "/employees", response_model=EmployeeOut, status_code=201
- 69: GET "/employees", response_model=List[EmployeeOut]
- 82: GET "/employees/{employee_id}", response_model=EmployeeOut
- 91: PATCH "/employees/{employee_id}", response_model=EmployeeOut
- 103: DELETE "/employees/{employee_id}", status_code=204
Top-level symbols:
- 28: async def create_department
- 39: async def list_departments
- 47: async def delete_department
- 59: async def create_employee
- 70: async def list_employees
- 83: async def get_employee
- 92: async def update_employee
- 104: async def deactivate_employee

## `backend/app/api/v1/routes/enrollment.py` (162 lines)
Routes:
- 41: POST "/generate-link"
- 105: GET "/join/{token}"
- 150: GET "/tokens/active"
Top-level symbols:
- 33: def _normalize_server_url
- 42: async def generate_join_link
- 106: async def get_join_config
- 151: async def list_active_tokens

## `backend/app/api/v1/routes/join_portal.py` (561 lines)
Routes:
- 53: POST "/api/v1/enroll/generate-join-link"
- 110: GET "/join", response_class=HTMLResponse
- 116: POST "/join/verify"
- 193: GET "/join/download/{download_token}"
Top-level symbols:
- 43: def _normalize_server_url
- 54: async def generate_join_link
- 111: async def join_portal_page
- 117: async def verify_join_code
- 194: async def download_agent
- 377: def _render_join_page

## `backend/app/api/v1/routes/reports.py` (626 lines)
Routes:
- 37: GET "/pdf/{employee_id}"
- 138: GET "/pdf/team/all"
Top-level symbols:
- 38: async def generate_employee_pdf
- 139: async def generate_team_pdf
- 227: def _fmt_seconds
- 234: def _score_color
- 241: def _score_label
- 248: def _draw_header
- 277: def _draw_footer
- 290: def _draw_section_title
- 306: def _draw_stat_card
- 333: def _build_employee_pdf
- 516: def _build_team_pdf

## `backend/app/api/v1/routes/screenshots.py` (546 lines)
Routes:
- 59: POST "/agent/screenshot", status_code=201
- 140: GET "/screenshots/{employee_id}", response_model=dict
- 215: GET "/screenshots/view/{screenshot_id}"
- 287: DELETE "/screenshots/cleanup-missing", status_code=200
- 318: DELETE "/screenshots/{screenshot_id}", status_code=200
- 357: POST "/screenshot-policies", status_code=201
- 396: GET "/screenshot-policies", response_model=List[dict]
- 421: PATCH "/screenshot-policies/{policy_id}/toggle", response_model=dict
- 456: DELETE "/screenshot-policies/{policy_id}", status_code=200
- 473: GET "/agent/screenshot-required"
Top-level symbols:
- 36: def _safe_file_exists
- 43: def _extract_device_token_from_request
- 60: async def upload_screenshot
- 141: async def list_screenshots
- 216: async def view_screenshot
- 288: async def cleanup_missing_screenshots
- 319: async def delete_screenshot
- 358: async def create_policy
- 397: async def list_policies
- 422: async def toggle_policy
- 457: async def delete_policy
- 474: async def check_screenshot_required
- 529: def _compress_image

## `backend/app/api/v1/routes/settings.py` (71 lines)
Routes:
- 20: GET "", response_model=SettingsUpdate
- 42: PUT "", response_model=SettingsUpdate
Top-level symbols:
- 12: class SettingsUpdate
- 21: async def get_settings
- 43: async def update_settings

## `backend/app/api/v1/routes/ws.py` (76 lines)
Routes:
- 25: WEBSOCKET "/ws/live"
Top-level symbols:
- 21: def _allowed_ws_origins
- 26: async def live_feed

## `backend/app/core/audit.py` (12 lines)
Top-level symbols:
- 10: def log_admin_action

## `backend/app/core/config.py` (166 lines)
Top-level symbols:
- 8: class Settings
- 75: def _parse_json_list
- 96: def parse_bool_flags
- 109: def validate_sensitive_secret
- 120: def validate_cookie_samesite
- 128: def resolve_groq_model
- 133: def cors_origins_list
- 140: def cors_allow_methods_list
- 144: def cors_allow_headers_list
- 148: def trusted_hosts_list
- 152: def csrf_origin_allowlist
- 156: def require_origin_check_for_cookie_auth
- 160: def cookie_security_valid

## `backend/app/core/exceptions.py` (46 lines)
Top-level symbols:
- 13: class ServiceError
- 18: def __init__
- 24: class NotFoundError
- 29: class ConflictError
- 34: class ValidationError
- 39: class AuthorizationError
- 44: class RateLimitedError

## `backend/app/core/files.py` (23 lines)
Top-level symbols:
- 8: def safe_path_join
- 16: def sanitize_filename_component

## `backend/app/core/logging.py` (27 lines)
Top-level symbols:
- 6: def setup_logging
- 26: def get_logger

## `backend/app/core/pagination.py` (63 lines)
Top-level symbols:
- 20: class PaginatedResult
- 28: def pages
- 32: def clamp_pagination
- 39: async def paginate_query

## `backend/app/core/rate_limit.py` (79 lines)
Top-level symbols:
- 12: class InMemoryRateLimiter
- 18: def __init__
- 22: def allow
- 42: def _anonymize
- 46: def _client_ip
- 55: def enforce_rate_limit

## `backend/app/core/security.py` (93 lines)
Top-level symbols:
- 21: def hash_password
- 25: def verify_password
- 29: def create_access_token
- 49: def create_refresh_token
- 67: def decode_token
- 77: def generate_device_token
- 87: def generate_enrollment_code
- 92: def generate_one_time_token

## `backend/app/db/seed.py` (54 lines)
Top-level symbols:
- 20: async def seed

## `backend/app/db/session.py` (87 lines)
Top-level symbols:
- 37: class Base
- 41: async def get_db
- 53: async def check_db_connection
- 75: async def ensure_schema_ready

## `backend/app/main.py` (152 lines)
Top-level symbols:
- 29: def _extract_origin
- 38: def _is_allowed_origin
- 47: async def lifespan
- 90: async def service_error_handler
- 106: async def validation_handler
- 120: async def csrf_guard_middleware
- 134: async def security_headers_middleware
- 145: async def generic_handler
- 151: async def health

## `backend/app/models/__init__.py` (332 lines)
Top-level symbols:
- 21: def utcnow
- 25: class UserRole
- 32: class DeviceStatus
- 39: class ActivityType
- 46: class SnapshotPolicy
- 52: class AnomalyType
- 59: class Admin
- 73: class Department
- 84: class Employee
- 104: class Device
- 127: class WorkSession
- 149: class ActivityEvent
- 177: class AppUsageDaily
- 195: class AnomalyLog
- 210: class ScreenshotPolicy
- 226: class AdminAuditLog
- 237: class BlockedSiteRule
- 247: class Screenshot
- 260: class ProductivityRule
- 274: class DailySummary
- 302: class SystemSettings
- 315: class ActionItem

## `backend/app/schemas/__init__.py` (367 lines)
Top-level symbols:
- 16: class TimestampMixin
- 23: class AdminLogin
- 28: class TokenResponse
- 37: class RefreshTokenRequest
- 41: class AdminCreate
- 48: class AdminOut
- 61: class DepartmentCreate
- 66: class DepartmentOut
- 77: class EmployeeCreate
- 87: class EmployeeUpdate
- 97: class EmployeeOut
- 116: class DeviceEnrollRequest
- 126: class DeviceEnrollResponse
- 133: class DeviceApproval
- 137: class DeviceOut
- 155: class ActivityEventIn
- 168: class ActivityBatch
- 175: class BatchResponse
- 183: class SessionStart
- 187: class SessionEnd
- 192: class SessionOut
- 209: class HeartbeatIn
- 217: class HeartbeatOut
- 225: class EmployeeStatusOut
- 242: class TimelineBlock
- 251: class WorkdayTimeline
- 260: class AppUsageStat
- 267: class HourlyHeatmap
- 274: class DepartmentComparisonRow
- 285: class DailySummaryOut
- 303: class AnomalyOut
- 319: class ScreenshotUpload
- 325: class PolicyCreate
- 336: class ReportRequest
- 346: class ReportRow
- 362: class PaginatedResponse

## `backend/app/services/aggregator.py` (167 lines)
Top-level symbols:
- 23: async def compute_daily_summaries
- 48: async def _compute_for_employee

## `backend/app/services/analytics_service.py` (351 lines)
Top-level symbols:
- 32: async def get_live_overview
- 109: async def get_leaderboard
- 193: async def get_dept_comparison
- 300: async def get_anomalies
- 342: async def review_anomaly

## `backend/app/services/anomaly_detector.py` (553 lines)
Top-level symbols:
- 73: def _metadata_text
- 86: def _extract_domain_keyword
- 96: def _matches_blocked
- 123: async def check_anomalies
- 143: async def _can_create
- 161: async def _create
- 209: async def _check_excessive_idle
- 248: async def _check_rapid_switching
- 305: async def _check_after_hours
- 380: async def _check_distraction
- 449: async def _check_blocked_domains

## `backend/app/services/categorizer.py` (146 lines)
Top-level symbols:
- 115: def categorize_app
- 135: def is_productive_category
- 144: def is_distraction_category

## `backend/app/services/device_service.py` (205 lines)
Top-level symbols:
- 24: async def enroll_device
- 87: async def list_devices
- 120: async def list_pending_devices
- 153: async def update_device_status
- 190: async def delete_device

## `backend/app/services/employee_service.py` (177 lines)
Top-level symbols:
- 26: async def create_department
- 41: async def list_departments
- 57: async def delete_department
- 68: async def build_employee_out
- 103: async def create_employee
- 121: async def get_employee
- 129: async def list_employees
- 153: async def update_employee
- 171: async def deactivate_employee

## `backend/app/services/online_tracker.py` (50 lines)
Top-level symbols:
- 17: def is_device_online
- 27: async def is_employee_online
- 39: async def get_employee_last_event

## `backend/app/services/scoring.py` (72 lines)
Top-level symbols:
- 16: def compute_session_score
- 39: def compute_score_from_events

## `backend/app/services/screenshot_ai.py` (148 lines)
Top-level symbols:
- 17: def _encode_image
- 21: async def process_screenshot_with_ai_task
- 32: async def _process_screenshot_with_ai

## `backend/app/services/token_store.py` (108 lines)
Top-level symbols:
- 10: def _utcnow
- 14: def _token_hash
- 19: class TokenRecord
- 28: def is_consumed
- 32: def is_expired
- 36: class InMemoryTokenStore
- 42: def __init__
- 46: def issue
- 57: def get
- 70: def consume
- 79: def update_payload
- 88: def delete
- 95: def active_records

## `backend/app/services/ws_broadcaster.py` (49 lines)
Top-level symbols:
- 9: class ConnectionManager
- 10: def __init__
- 13: async def connect
- 18: def disconnect
- 23: async def broadcast
- 40: async def broadcast_employee_update
- 44: async def broadcast_device_status
- 48: async def broadcast_anomaly

## `frontend/src/api/client.ts` (193 lines)
Top-level symbols:
- 5: const BASE
- 6: const API_ROOT
- 8: export const api
- 21: const original
- 60: export const authApi
- 68: export const employeesApi
- 78: export const departmentsApi
- 84: export const devicesApi
- 94: export const analyticsApi
- 111: const days
- 136: export const blockerApi
- 145: export const actionsApi
- 156: export const settingsApi
- 161: export const reportsApi
- 163: const response
- 169: const params
- 171: const response
- 178: export const aiApi
- 188: export const enrollApi

## `frontend/src/App.tsx` (128 lines)
Top-level symbols:
- 26: const queryClient
- 32: function SessionValidator
- 45: const me
- 80: function RequireAuth
- 81: const isAuthenticated
- 86: function RequireUnauth
- 87: const isAuthenticated
- 94: const saved

## `frontend/src/components/charts/ActivityHeatmap.tsx` (69 lines)
Top-level symbols:
- 9: const HOURS
- 11: export function ActivityHeatmap
- 12: const values
- 13: const maxVal
- 15: function formatHour
- 22: function intensity
- 30: const secs
- 31: const alpha
- 32: const mins
- 33: const barHeight

## `frontend/src/components/charts/WorkdayTimeline.tsx` (116 lines)
Top-level symbols:
- 11: export function WorkdayTimelineChart
- 12: const dayStart
- 13: const dayStartMs
- 14: const dayEndMs
- 15: const windowMs
- 27: function toPercent
- 28: const ms
- 32: function widthPercent
- 33: const startMs
- 34: const endMs
- 39: const hours
- 56: const left
- 57: const width
- 80: const pct

## `frontend/src/components/layout/AppLayout.tsx` (228 lines)
Top-level symbols:
- 14: const NAV_GROUPS
- 51: export function AppLayout
- 55: const navigate
- 57: function toggleTheme
- 58: const next

## `frontend/src/components/ui/AlertSystem.tsx` (217 lines)
Top-level symbols:
- 14: const ANOMALY_LABELS
- 21: export function AlertSystem
- 25: const audioCtxRef
- 26: const dismissTimerRef
- 27: const lastAnomalyRef
- 38: const perm
- 42: function playAlertSound
- 47: const ctx
- 48: const osc
- 49: const gain
- 61: function clearDismissTimer
- 68: function buildAlertId
- 75: const handleWsMessage
- 78: const dedupeKey
- 79: const now
- 85: const alert
- 116: function dismissAlert
- 121: function clearAll

## `frontend/src/components/ui/ErrorBoundary.tsx` (60 lines)
- No top-level symbols detected (likely constants/styles/markup).

## `frontend/src/components/ui/OnlineBadge.tsx` (27 lines)
Top-level symbols:
- 9: export function OnlineBadge
- 10: const dotSize

## `frontend/src/components/ui/PageHeader.tsx` (40 lines)
Top-level symbols:
- 9: export function PageHeader

## `frontend/src/components/ui/StatCard.tsx` (39 lines)
Top-level symbols:
- 11: export function StatCard

## `frontend/src/config.ts` (17 lines)
Top-level symbols:
- 1: export const isBrowser
- 11: export const API_BASE_URL
- 13: export const BACKEND_ROOT
- 15: export const APP_ORIGIN
- 17: export const WS_BASE_URL

## `frontend/src/hooks/useWebSocket.ts` (54 lines)
Top-level symbols:
- 8: export function useWebSocket
- 9: const ws
- 10: const reconnectTimer
- 11: const isAuthenticated
- 13: const connect
- 16: const socket
- 22: const ping
- 30: const msg

## `frontend/src/main.tsx` (9 lines)
- No top-level symbols detected (likely constants/styles/markup).

## `frontend/src/pages/ActionItemsPage.tsx` (339 lines)
Top-level symbols:
- 30: const PRIORITY_COLORS
- 36: export function ActionItemsPage
- 59: const loadItems
- 62: const res
- 78: const filteredItems
- 85: const handleToggle
- 107: const handleDelete
- 117: const selectedEmployeeName

## `frontend/src/pages/ActivityGraphPage.tsx` (332 lines)
Top-level symbols:
- 19: const MAX_POINTS
- 21: export function ActivityGraphPage
- 25: const qc
- 46: const handleWsMessage
- 50: const now
- 53: const point
- 60: const next
- 72: const today
- 74: const timeline
- 85: const points
- 96: const selected
- 97: const emp
- 99: const isOnline
- 100: const currentApp
- 101: const activityType
- 103: const activityColor
- 106: const CustomTooltip

## `frontend/src/pages/AIInsightsPage.tsx` (1194 lines)
Top-level symbols:
- 61: const QUICK_PROMPTS
- 72: function categoryIcon
- 73: const map
- 82: function scoreColor
- 88: function scoreBg
- 94: function trendIcon
- 100: function trendLabel
- 107: function renderMarkdown
- 108: const lines
- 111: const parts
- 112: const rendered
- 135: export function AIInsightsPage
- 196: function ChatPanel
- 200: const bottomRef
- 207: const msg
- 210: const newMessages
- 214: const history
- 379: function TeamPulsePanel
- 384: const fetchPulse
- 396: const employeeList
- 408: const topPerformers
- 409: const needsAttention
- 412: const employeeMetrics
- 455: const avgScore
- 458: const avgHours
- 461: const totalAnomalies
- 792: function WorkRecommendationsPanel
- 803: const loadEmployees
- 825: const generateReport
- 841: const errorMsg
- 850: const handleActionItemToggle
- 861: const response
- 868: const itemId
- 884: const response

## `frontend/src/pages/AnalyticsPage.tsx` (337 lines)
Top-level symbols:
- 10: const ACTIVITY_COLORS
- 17: function TimelineBar
- 30: const blocks
- 31: const start
- 32: const end
- 33: const total
- 35: const fmt
- 63: const w
- 64: const startTime
- 95: function HeatmapChart24Hr
- 107: const hours
- 111: const maxSeconds
- 113: const getColor
- 114: const pct
- 126: const mins
- 127: const color
- 128: const hour12
- 170: export function AnalyticsPage
- 173: const employeeId
- 180: const selected
- 219: const trendData

## `frontend/src/pages/AnomaliesPage.tsx` (1050 lines)
Top-level symbols:
- 34: const ANOMALY_CONFIG
- 73: const SEVERITY_STYLE
- 91: function getMetadataValue
- 95: function getMetadataString
- 96: const value
- 100: function getBlockedDomains
- 101: const blockedDomains
- 105: const domain
- 109: function getSeverity
- 110: const override
- 111: const severity
- 112: const fallback
- 113: const normalized
- 120: function summarizeEmployeeViolations
- 125: const severityCounts
- 135: const severity
- 157: function sortGroups
- 170: function buildHeuristicRecommendation
- 186: function formatDateTime
- 196: function formatTime
- 209: function EmployeeViolationsCard
- 225: const recommendation
- 241: const recommendationText
- 242: const recommendationSource
- 344: const config
- 345: const severity
- 346: const severityStyle
- 347: const blockedDomains
- 348: const isViolationExpanded
- 349: const risk
- 350: const recommendedAction
- 489: export function AnomaliesPage
- 490: const queryClient
- 498: const anomaliesQuery
- 508: const reviewMutation
- 515: const anomalies
- 517: const employeeGroups
- 518: const grouped
- 520: const employeeId
- 522: const employeeName
- 523: const existing
- 531: const groups
- 538: const filteredGroups
- 539: const query
- 541: const result
- 543: const filteredViolations
- 553: const blockedDomains
- 576: const overview
- 577: const severityTotals
- 595: const countsByType
- 657: const severityStyle
- 784: const SETTINGS_GROUPS
- 849: function AnomalySettingsModal
- 850: const queryClient
- 854: const settingsQuery
- 865: const saveMutation
- 872: const errorText

## `frontend/src/pages/BlockerPage.tsx` (207 lines)
Top-level symbols:
- 17: const CATEGORIES
- 26: const SEVERITY_COLORS
- 32: export function BlockerPage
- 33: const qc
- 45: const addDomain
- 54: const removeDomain
- 59: const toggleDomain
- 64: const loadDefaults
- 72: const active
- 169: const cat
- 170: const sev

## `frontend/src/pages/DepartmentsPage.tsx` (163 lines)
Top-level symbols:
- 10: export function DepartmentsPage
- 11: const qc
- 26: const create
- 31: const deleteDept
- 36: const comparisonChartData
- 37: const scoreRaw
- 38: const activeRaw
- 39: const score
- 40: const activeHours
- 48: const hasMeaningfulComparison
- 78: const comp

## `frontend/src/pages/DevicesPage.tsx` (242 lines)
Top-level symbols:
- 11: function getApiErrorMessage
- 13: const detail
- 18: export function DevicesPage
- 19: const qc
- 35: const approve
- 47: const revoke
- 59: const deleteDevice
- 71: const shown
- 73: function statusBadge
- 74: const map

## `frontend/src/pages/EmployeesPage.tsx` (579 lines)
Top-level symbols:
- 12: function getDefaultEnrollServerUrl
- 20: function getServerReachabilityHint
- 21: const url
- 32: export function EmployeesPage
- 33: const qc
- 66: const create
- 91: const updateWorkHours
- 115: const deactivate
- 123: const reactivate
- 131: const hardDelete
- 362: function EnrollModal
- 368: const reachabilityHint
- 373: const data
- 380: function copy
- 460: function WorkHoursModal
- 544: function DeleteModal

## `frontend/src/pages/LeaderboardPage.tsx` (177 lines)
Top-level symbols:
- 19: const MEDAL
- 20: const MEDAL_COLORS
- 22: export function LeaderboardPage
- 32: const top3
- 33: const rest
- 81: const isFirst
- 82: const heights

## `frontend/src/pages/LiveScreensPage.tsx` (265 lines)
Top-level symbols:
- 11: export function LiveScreensPage
- 17: const interval
- 27: const online
- 116: function ScreenCard
- 135: const shots
- 139: const imgResp
- 143: const blobUrl

## `frontend/src/pages/LoginPage.tsx` (237 lines)
Top-level symbols:
- 8: export function LoginPage
- 9: const portalUrl
- 16: const isAuthenticated
- 17: const navigate
- 29: const me
- 33: const s

## `frontend/src/pages/OverviewPage.tsx` (218 lines)
Top-level symbols:
- 13: export function OverviewPage
- 14: const queryClient
- 23: const handleWsMessage
- 45: const online
- 46: const active
- 47: const idle
- 48: const avgScore
- 118: function EmployeeCard
- 119: const scoreColor

## `frontend/src/pages/ReportsPage.tsx` (178 lines)
Top-level symbols:
- 8: export function ReportsPage
- 33: const emp
- 40: const a
- 46: const errorMsg

## `frontend/src/pages/ScreenshotsPage.tsx` (653 lines)
Top-level symbols:
- 9: const MIN_CARD_WIDTH
- 10: const GRID_GAP
- 11: const TARGET_ROWS
- 47: function getPolicyBadge
- 53: export function ScreenshotsPage
- 54: const qc
- 69: const createPolicy
- 79: const togglePolicy
- 84: const deletePolicy
- 89: const handleTogglePolicy
- 90: const action
- 95: const handleDeletePolicy
- 177: const badge
- 242: function ScreenshotGallery
- 243: const qc
- 249: const gridRef
- 251: const pageSize
- 254: const node
- 257: const updateColumns
- 258: const width
- 259: const cols
- 266: const observer
- 313: const cleanupMissing
- 316: const removed
- 322: const deleteScreenshot
- 330: const handleCleanupMissing
- 335: const handleDeleteScreenshot
- 340: const screenshots
- 341: const currentPage
- 342: const totalPages
- 343: const totalItems
- 395: const imageUrl
- 521: function ScreenshotCard
- 536: const canExpand
- 537: const isMissingFile

## `frontend/src/pages/SettingsPage.tsx` (205 lines)
Top-level symbols:
- 8: export function SettingsPage
- 45: function ProfileTab
- 77: function SecurityTab
- 81: const change
- 95: function submit
- 156: function SystemTab
- 157: const baseUrl
- 158: const checks

## `frontend/src/store/authStore.ts` (50 lines)
Top-level symbols:
- 15: export const useAuthStore
- 49: export const selectIsAuthenticated

## `frontend/src/styles/globals.css` (402 lines)
- No top-level symbols detected (likely constants/styles/markup).

## `frontend/src/types/index.ts` (209 lines)
- No top-level symbols detected (likely constants/styles/markup).

## `frontend/src/utils/format.ts` (92 lines)
Top-level symbols:
- 3: export function formatSeconds
- 6: const h
- 7: const m
- 11: export function formatTime
- 15: export function formatDate
- 19: export function todayISO
- 23: export function daysAgoISO
- 24: const d
- 31: export function productivityColor
- 38: export function activityColor
- 48: export function categoryColor
- 49: const palette
- 72: export function clamp
- 76: export function initials
- 85: export function platformIcon

## `frontend/src/vite-env.d.ts` (1 lines)
- No top-level symbols detected (likely constants/styles/markup).
