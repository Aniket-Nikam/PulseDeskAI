"""
PulseDesk Database Models — Fixed relationships
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, List

from sqlalchemy import (
    String, Integer, Boolean, Float, DateTime, Text,
    ForeignKey, Enum as SAEnum, UniqueConstraint, Index,
    JSON,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base
import enum


def utcnow():
    return datetime.now(timezone.utc)


class UserRole(str, enum.Enum):
    super_admin = "super_admin"
    admin = "admin"
    manager = "manager"
    employee = "employee"


class DeviceStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    revoked = "revoked"
    suspended = "suspended"


class ActivityType(str, enum.Enum):
    active = "active"
    idle = "idle"
    locked = "locked"
    away = "away"


class SnapshotPolicy(str, enum.Enum):
    disabled = "disabled"
    interval = "interval"
    on_anomaly = "on_anomaly"


class AnomalyType(str, enum.Enum):
    excessive_idle = "excessive_idle"
    rapid_app_switching = "rapid_app_switching"
    after_hours_activity = "after_hours_activity"
    unusual_app_usage = "unusual_app_usage"
    excessive_break = "excessive_break"


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    business_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    role: Mapped[UserRole] = mapped_column(SAEnum(UserRole), default=UserRole.admin, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Department(Base):
    __tablename__ = "departments"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    employees: Mapped[List["Employee"]] = relationship("Employee", back_populates="department")


class Employee(Base):
    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False)
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"), index=True)
    job_title: Mapped[Optional[str]] = mapped_column(String(100))
    timezone: Mapped[str] = mapped_column(String(50), default="UTC")
    work_start_hour: Mapped[int] = mapped_column(Integer, default=9)
    work_end_hour: Mapped[int] = mapped_column(Integer, default=18)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # GDPR consent tracking
    consent_given_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    department: Mapped[Optional["Department"]] = relationship("Department", back_populates="employees")
    devices: Mapped[List["Device"]] = relationship("Device", back_populates="employee")
    sessions: Mapped[List["WorkSession"]] = relationship("WorkSession", back_populates="employee")

    @property
    def role(self) -> UserRole:
        return UserRole.employee


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    hostname: Mapped[str] = mapped_column(String(255), nullable=False)
    platform: Mapped[str] = mapped_column(String(50))
    os_version: Mapped[Optional[str]] = mapped_column(String(100))
    agent_version: Mapped[Optional[str]] = mapped_column(String(20))
    device_token: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    enrollment_code: Mapped[Optional[str]] = mapped_column(String(10))
    status: Mapped[DeviceStatus] = mapped_column(SAEnum(DeviceStatus), default=DeviceStatus.pending)
    monitoring_consent_given: Mapped[bool] = mapped_column(Boolean, default=False)
    last_heartbeat: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    enrolled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="devices")

    __table_args__ = (
        Index("ix_devices_employee_status", "employee_id", "status"),
    )


class WorkSession(Base):
    __tablename__ = "work_sessions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    active_seconds: Mapped[int] = mapped_column(Integer, default=0)
    idle_seconds: Mapped[int] = mapped_column(Integer, default=0)
    app_switches: Mapped[int] = mapped_column(Integer, default=0)
    focus_blocks: Mapped[int] = mapped_column(Integer, default=0)
    productivity_score: Mapped[Optional[float]] = mapped_column(Float)

    employee: Mapped["Employee"] = relationship("Employee", back_populates="sessions")

    __table_args__ = (
        Index("ix_sessions_employee_date", "employee_id", "started_at"),
    )


class ActivityEvent(Base):
    __tablename__ = "activity_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("work_sessions.id"), index=True)

    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    activity_type: Mapped[ActivityType] = mapped_column(SAEnum(ActivityType), nullable=False)

    active_app: Mapped[Optional[str]] = mapped_column(String(200))
    active_window_title: Mapped[Optional[str]] = mapped_column(String(500))
    app_category: Mapped[Optional[str]] = mapped_column(String(100))

    keystrokes: Mapped[int] = mapped_column(Integer, default=0)
    mouse_clicks: Mapped[int] = mapped_column(Integer, default=0)
    mouse_distance_px: Mapped[int] = mapped_column(Integer, default=0)
    idle_duration_seconds: Mapped[int] = mapped_column(Integer, default=0)
    sample_duration_seconds: Mapped[int] = mapped_column(Integer, default=30)

    __table_args__ = (
        Index("ix_events_employee_time", "employee_id", "timestamp"),
        Index("ix_events_device_time", "device_id", "timestamp"),
        Index("ix_events_session", "session_id", "timestamp"),
    )


class AppUsageDaily(Base):
    __tablename__ = "app_usage_daily"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    app_name: Mapped[str] = mapped_column(String(200), nullable=False)
    app_category: Mapped[Optional[str]] = mapped_column(String(100))
    total_seconds: Mapped[int] = mapped_column(Integer, default=0)
    active_seconds: Mapped[int] = mapped_column(Integer, default=0)
    session_count: Mapped[int] = mapped_column(Integer, default=1)

    __table_args__ = (
        UniqueConstraint("employee_id", "date", "app_name", name="uq_app_usage_daily"),
        Index("ix_app_usage_employee_date", "employee_id", "date"),
    )


class AnomalyLog(Base):
    __tablename__ = "anomaly_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    anomaly_type: Mapped[AnomalyType] = mapped_column(SAEnum(AnomalyType), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    event_metadata: Mapped[Optional[dict]] = mapped_column(JSON)
    is_reviewed: Mapped[bool] = mapped_column(Boolean, default=False)
    reviewed_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("admins.id"))
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    __table_args__ = (
        Index("ix_anomalies_employee_detected_at", "employee_id", "detected_at"),
    )


class ScreenshotPolicy(Base):
    __tablename__ = "screenshot_policies"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    policy_type: Mapped[SnapshotPolicy] = mapped_column(SAEnum(SnapshotPolicy), default=SnapshotPolicy.disabled)
    interval_minutes: Mapped[Optional[int]] = mapped_column(Integer)
    retention_days: Mapped[int] = mapped_column(Integer, default=7) # Privacy compliance: Data minimization
    allowed_viewer_roles: Mapped[Optional[dict]] = mapped_column(JSON) # e.g., ["super_admin", "admin"]
    applies_to_all: Mapped[bool] = mapped_column(Boolean, default=False)
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"))
    employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("admins.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

class AdminAuditLog(Base):
    __tablename__ = "admin_audit_logs"
    
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    admin_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("admins.id"), nullable=False, index=True)
    action: Mapped[str] = mapped_column(String(100), nullable=False) # e.g. "VIEW_SCREENSHOT", "EXPORT_REPORT"
    target_employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), index=True)
    metadata_json: Mapped[Optional[dict]] = mapped_column(JSON)
    ip_address: Mapped[Optional[str]] = mapped_column(String(50))
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)

class BlockedSiteRule(Base):
    __tablename__ = "blocked_site_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    domain: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    reason: Mapped[str] = mapped_column(String(500), default="")
    category: Mapped[str] = mapped_column(String(50), default="general")
    severity: Mapped[str] = mapped_column(String(20), default="medium")
    applies_to_all: Mapped[bool] = mapped_column(Boolean, default=True)
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    violation_count: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("admins.id"), nullable=True)


class Screenshot(Base):
    __tablename__ = "screenshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    device_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("devices.id"), nullable=False)
    policy_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("screenshot_policies.id"))
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    trigger: Mapped[str] = mapped_column(String(50))

    __table_args__ = (
        Index("ix_screenshots_employee_captured_at", "employee_id", "captured_at"),
    )


class ProductivityRule(Base):
    __tablename__ = "productivity_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    rule_type: Mapped[str] = mapped_column(String(50), nullable=False)
    conditions: Mapped[dict] = mapped_column(JSON, nullable=False)
    action: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("admins.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class DailySummary(Base):
    __tablename__ = "daily_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    total_tracked_seconds: Mapped[int] = mapped_column(Integer, default=0)
    active_seconds: Mapped[int] = mapped_column(Integer, default=0)
    idle_seconds: Mapped[int] = mapped_column(Integer, default=0)
    focus_seconds: Mapped[int] = mapped_column(Integer, default=0)

    productivity_score: Mapped[float] = mapped_column(Float, default=0.0)
    focus_sessions: Mapped[int] = mapped_column(Integer, default=0)
    app_switches: Mapped[int] = mapped_column(Integer, default=0)
    top_app: Mapped[Optional[str]] = mapped_column(String(200))
    top_category: Mapped[Optional[str]] = mapped_column(String(100))

    hourly_active_seconds: Mapped[Optional[dict]] = mapped_column(JSON)
    anomaly_count: Mapped[int] = mapped_column(Integer, default=0)
    computed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("employee_id", "date", name="uq_daily_summary"),
        Index("ix_daily_summary_employee_date", "employee_id", "date"),
    )


class SystemSettings(Base):
    __tablename__ = "system_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rapid_switching_high_threshold: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    rapid_switching_critical_threshold: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    rapid_switching_window_seconds: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    excessive_idle_threshold_minutes: Mapped[int] = mapped_column(Integer, default=45, nullable=False)
    distraction_threshold_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    after_hours_min_active_minutes: Mapped[int] = mapped_column(Integer, default=5, nullable=False)
    screenshot_retention_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ActionItem(Base):
    __tablename__ = "action_items"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    report_id: Mapped[Optional[str]] = mapped_column(String(100))
    action_text: Mapped[str] = mapped_column(String(500), nullable=False)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    priority: Mapped[str] = mapped_column(String(20), default="medium")
    due_date: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    __table_args__ = (
        Index("ix_action_items_employee_date", "employee_id", "created_at"),
        Index("ix_action_items_completion", "employee_id", "is_completed"),
    )


# ── Attendance System ─────────────────────────────────────────────────────────

class AttendanceMode(str, enum.Enum):
    employee = "employee"
    student = "student"
    both = "both"


class AttendanceStatus(str, enum.Enum):
    present = "present"
    late = "late"
    half_day = "half_day"
    absent = "absent"
    on_leave = "on_leave"
    holiday = "holiday"


class AttendanceSettings(Base):
    """Singleton attendance configuration row."""
    __tablename__ = "attendance_settings"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    mode: Mapped[AttendanceMode] = mapped_column(SAEnum(AttendanceMode), nullable=False)
    is_configured: Mapped[bool] = mapped_column(Boolean, default=False)

    # Default work hours
    work_start_time: Mapped[str] = mapped_column(String(5), default="09:00")
    work_end_time: Mapped[str] = mapped_column(String(5), default="18:00")

    # Lunch break (employee mode)
    lunch_break_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    lunch_break_start_time: Mapped[str] = mapped_column(String(5), default="13:00")
    lunch_break_duration_minutes: Mapped[int] = mapped_column(Integer, default=60)
    auto_deduct_lunch: Mapped[bool] = mapped_column(Boolean, default=False)

    # Late / early thresholds
    late_threshold_minutes: Mapped[int] = mapped_column(Integer, default=15)
    early_checkout_threshold_minutes: Mapped[int] = mapped_column(Integer, default=30)
    half_day_threshold_hours: Mapped[float] = mapped_column(Float, default=4.0)

    # Overtime
    overtime_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    overtime_after_hours: Mapped[float] = mapped_column(Float, default=8.0)

    # Location rules
    require_location_for_checkout: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_remote_checkin: Mapped[bool] = mapped_column(Boolean, default=False)

    # Break alert settings
    break_alert_enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    break_alert_grace_minutes: Mapped[int] = mapped_column(Integer, default=5)

    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("admins.id"), nullable=True)



class AttendanceLocation(Base):
    """Geofence locations for attendance check-in/out validation."""
    __tablename__ = "attendance_locations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    radius_meters: Mapped[int] = mapped_column(Integer, default=200)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    applies_to: Mapped[str] = mapped_column(String(20), default="all")  # "all" | "employee" | "student"
    department_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("departments.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    created_by: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("admins.id"), nullable=True)


class AttendanceRecord(Base):
    """Individual daily attendance record per employee/student."""
    __tablename__ = "attendance_records"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    check_in_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    check_out_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    check_in_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    check_in_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    check_out_latitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    check_out_longitude: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    check_in_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("attendance_locations.id"), nullable=True)
    check_out_location_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True), ForeignKey("attendance_locations.id"), nullable=True)

    check_in_within_geofence: Mapped[bool] = mapped_column(Boolean, default=False)
    check_out_within_geofence: Mapped[bool] = mapped_column(Boolean, default=False)

    status: Mapped[AttendanceStatus] = mapped_column(SAEnum(AttendanceStatus), default=AttendanceStatus.present)
    check_in_count: Mapped[int] = mapped_column(Integer, default=1)
    total_work_seconds: Mapped[int] = mapped_column(Integer, default=0)
    effective_work_seconds: Mapped[int] = mapped_column(Integer, default=0)
    overtime_seconds: Mapped[int] = mapped_column(Integer, default=0)
    lunch_deducted_seconds: Mapped[int] = mapped_column(Integer, default=0)

    is_remote: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    __table_args__ = (
        UniqueConstraint("employee_id", "date", name="uq_attendance_employee_date"),
        Index("ix_attendance_employee_date", "employee_id", "date"),
        Index("ix_attendance_date_status", "date", "status"),
    )


class LunchBreakLog(Base):
    """Tracks lunch break start/end for employees."""
    __tablename__ = "lunch_break_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    attendance_record_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("attendance_records.id"), nullable=False, index=True)
    employee_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("employees.id"), nullable=False, index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    auto_deducted: Mapped[bool] = mapped_column(Boolean, default=False)


class WeeklySummary(Base):
    __tablename__ = "weekly_summaries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    week_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    week_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    metrics_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

