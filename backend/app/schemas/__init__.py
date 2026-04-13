"""
PulseDesk Pydantic Schemas
Request/response models for all API endpoints.
"""

from __future__ import annotations
from datetime import datetime
from typing import Optional, List, Dict, Any
import uuid

from pydantic import BaseModel, EmailStr, Field, ConfigDict


# ─── Base ─────────────────────────────────────────────────────────────────────

class TimestampMixin(BaseModel):
    created_at: datetime
    updated_at: Optional[datetime] = None


# ─── Auth ─────────────────────────────────────────────────────────────────────

class AdminLogin(BaseModel):
    email: str  # str not EmailStr to allow .local domains
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    admin_id: uuid.UUID
    full_name: str
    role: str


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class AdminCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=2, max_length=255)
    role: str = "admin"


class AdminOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    full_name: str
    role: str
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime


# ─── Department ───────────────────────────────────────────────────────────────

class DepartmentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: Optional[str] = None


class DepartmentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    name: str
    description: Optional[str]
    created_at: datetime
    employee_count: Optional[int] = 0


# ─── Employee ─────────────────────────────────────────────────────────────────

class EmployeeCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=255)
    department_id: Optional[uuid.UUID] = None
    job_title: Optional[str] = None
    timezone: str = "UTC"
    work_start_hour: int = Field(default=9, ge=0, le=23)
    work_end_hour: int = Field(default=18, ge=0, le=23)


class EmployeeUpdate(BaseModel):
    full_name: Optional[str] = None
    department_id: Optional[uuid.UUID] = None
    job_title: Optional[str] = None
    timezone: Optional[str] = None
    work_start_hour: Optional[int] = Field(default=None, ge=0, le=23)
    work_end_hour: Optional[int] = Field(default=None, ge=0, le=23)
    is_active: Optional[bool] = None


class EmployeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    email: str
    full_name: str
    department_id: Optional[uuid.UUID]
    department_name: Optional[str] = None
    job_title: Optional[str]
    timezone: str
    work_start_hour: int
    work_end_hour: int
    is_active: bool
    created_at: datetime
    device_count: Optional[int] = 0
    is_online: Optional[bool] = False


# ─── Device ───────────────────────────────────────────────────────────────────

class DeviceEnrollRequest(BaseModel):
    """Sent by the agent on first run."""
    employee_email: EmailStr
    hostname: str
    platform: str
    os_version: Optional[str] = None
    agent_version: str = "1.0.0"
    enrollment_code: str  # short code shown on device, admin uses this to approve


class DeviceEnrollResponse(BaseModel):
    device_id: uuid.UUID
    device_token: str
    status: str
    message: str


class DeviceApproval(BaseModel):
    status: str  # "approved" | "revoked" | "suspended"


class DeviceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: Optional[str] = None
    hostname: str
    platform: str
    os_version: Optional[str]
    agent_version: Optional[str]
    status: str
    last_heartbeat: Optional[datetime]
    enrolled_at: Optional[datetime]
    created_at: datetime
    is_online: Optional[bool] = False


# ─── Activity Events (Agent → Backend) ───────────────────────────────────────

class ActivityEventIn(BaseModel):
    """Single sample from agent. Batched in ActivityBatch."""
    timestamp: datetime
    activity_type: str  # active | idle | locked | away
    active_app: Optional[str] = None
    active_window_title: Optional[str] = None
    keystrokes: int = Field(default=0, ge=0)
    mouse_clicks: int = Field(default=0, ge=0)
    mouse_distance_px: int = Field(default=0, ge=0)
    idle_duration_seconds: int = Field(default=0, ge=0)
    sample_duration_seconds: int = Field(default=30, ge=1, le=300)


class ActivityBatch(BaseModel):
    """Agent sends up to 200 events per POST."""
    device_token: str
    session_id: Optional[uuid.UUID] = None  # if continuing a session
    events: List[ActivityEventIn] = Field(max_length=200)


class BatchResponse(BaseModel):
    accepted: int
    session_id: uuid.UUID
    server_time: datetime


# ─── Session ──────────────────────────────────────────────────────────────────

class SessionStart(BaseModel):
    device_token: str


class SessionEnd(BaseModel):
    device_token: str
    session_id: uuid.UUID


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    employee_id: uuid.UUID
    device_id: uuid.UUID
    started_at: datetime
    ended_at: Optional[datetime]
    duration_seconds: Optional[int]
    active_seconds: int
    idle_seconds: int
    app_switches: int
    focus_blocks: int
    productivity_score: Optional[float]


# ─── Heartbeat ────────────────────────────────────────────────────────────────

class HeartbeatIn(BaseModel):
    device_token: str
    hostname: Optional[str] = None
    platform: Optional[str] = None
    os_version: Optional[str] = None
    agent_version: Optional[str] = None


class HeartbeatOut(BaseModel):
    status: str
    server_time: datetime
    screenshot_required: bool = False


# ─── Analytics ────────────────────────────────────────────────────────────────

class EmployeeStatusOut(BaseModel):
    """Live status for dashboard overview."""
    employee_id: uuid.UUID
    employee_name: str
    department_name: Optional[str]
    is_online: bool
    activity_type: Optional[str]
    active_app: Optional[str]
    active_window_title: Optional[str]
    idle_seconds: int
    session_started_at: Optional[datetime]
    today_active_seconds: int
    today_productivity_score: Optional[float]
    last_seen: Optional[datetime]


class TimelineBlock(BaseModel):
    """One block in the workday timeline."""
    start: datetime
    end: datetime
    activity_type: str
    app_name: Optional[str]
    duration_seconds: int


class WorkdayTimeline(BaseModel):
    employee_id: uuid.UUID
    date: str  # YYYY-MM-DD
    blocks: List[TimelineBlock]
    total_active_seconds: int
    total_idle_seconds: int
    focus_sessions: int


class AppUsageStat(BaseModel):
    app_name: str
    app_category: Optional[str]
    total_seconds: int
    percentage: float


class HourlyHeatmap(BaseModel):
    """24 values (0-23 hours), seconds active per hour."""
    employee_id: uuid.UUID
    date: str
    hours: Dict[str, int]  # {"0": 0, "9": 1800, ...}


class DepartmentComparisonRow(BaseModel):
    department_id: uuid.UUID
    department_name: str
    employee_count: int
    avg_active_seconds: float
    avg_productivity_score: float
    avg_focus_sessions: float
    avg_app_switches: float
    online_count: int


class DailySummaryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    employee_id: uuid.UUID
    date: datetime
    total_tracked_seconds: int
    active_seconds: int
    idle_seconds: int
    focus_seconds: int
    productivity_score: float
    focus_sessions: int
    app_switches: int
    top_app: Optional[str]
    top_category: Optional[str]
    hourly_active_seconds: Optional[Dict[str, int]]
    anomaly_count: int


class AnomalyOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    employee_id: uuid.UUID
    employee_name: Optional[str] = None
    device_id: uuid.UUID
    anomaly_type: str
    detected_at: datetime
    description: str
    metadata: Optional[Dict[str, Any]]
    is_reviewed: bool


# ─── Screenshot ───────────────────────────────────────────────────────────────

class ScreenshotUpload(BaseModel):
    device_token: str
    captured_at: datetime
    trigger: str = "interval"


class PolicyCreate(BaseModel):
    name: str
    policy_type: str = "disabled"
    interval_minutes: Optional[int] = None
    applies_to_all: bool = False
    department_id: Optional[uuid.UUID] = None
    employee_id: Optional[uuid.UUID] = None


# ─── Reports ──────────────────────────────────────────────────────────────────

class ReportRequest(BaseModel):
    employee_ids: Optional[List[uuid.UUID]] = None
    department_id: Optional[uuid.UUID] = None
    date_from: datetime
    date_to: datetime
    include_timeline: bool = False
    include_app_usage: bool = True
    include_anomalies: bool = True


class ReportRow(BaseModel):
    employee_id: uuid.UUID
    employee_name: str
    department_name: Optional[str]
    total_days: int
    avg_active_seconds: float
    avg_productivity_score: float
    total_focus_sessions: int
    total_anomalies: int
    top_app: Optional[str]


# ─── Pagination ───────────────────────────────────────────────────────────────

class PaginatedResponse(BaseModel):
    items: List[Any]
    total: int
    page: int
    page_size: int
    pages: int
