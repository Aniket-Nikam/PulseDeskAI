from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ChatHistoryItem(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: list[ChatHistoryItem] = Field(default_factory=list)


class ChatResponse(BaseModel):
    reply: str
    source: str  # groq | heuristic


class BurnoutEmployee(BaseModel):
    employee_id: str
    name: str
    department: Optional[str] = None
    risk_score: int
    risk_level: str
    signals: list[str] = Field(default_factory=list)
    recommendation: str


class BurnoutResponse(BaseModel):
    employees: list[BurnoutEmployee] = Field(default_factory=list)
    summary: str


class ActivityPatternsResponse(BaseModel):
    employee_id: str
    employee_name: str
    department: Optional[str] = None
    peak_activity_time: str
    avg_daily_hours: float
    productivity_trend: str
    focus_quality: str
    recommendations: list[str] = Field(default_factory=list)
    message: Optional[str] = None


class WorkReportMetrics(BaseModel):
    avg_active_hours: float
    avg_focus_hours: float
    productivity_score: float
    anomalies: int


class WorkRecommendationsResponse(BaseModel):
    employee_id: str
    employee_name: str
    department: Optional[str] = None
    report_title: str
    period: str
    performance_rating: str
    summary: str
    highlights: list[str] = Field(default_factory=list)
    focus_areas: list[str] = Field(default_factory=list)
    coaching_tips: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    motivational_message: str = ""
    metrics: Optional[WorkReportMetrics] = None
    timestamp: datetime
    source: str  # groq | heuristic


class AnomalyRecommendationStats(BaseModel):
    total_violations: int
    high_severity: int
    medium_severity: int
    low_severity: int
    reviewed: int
    unreviewed: int


class AnomalyRecommendationResponse(BaseModel):
    employee_id: str
    employee_name: str
    recommendation: str
    source: str  # groq | heuristic
    stats: AnomalyRecommendationStats
    generated_at: datetime


class AIDiagnosticsResponse(BaseModel):
    status: str
    total_active_employees: int
    daily_summary_records_last_7_days: int
    anomaly_records_last_7_days: int
    employees_with_activity_data: int
    employee_names_with_data: list[str] = Field(default_factory=list)
    recommendation: str
    ai_enabled: bool
    ai_provider: str
    groq_model: str
    screenshot_analysis_enabled: bool
