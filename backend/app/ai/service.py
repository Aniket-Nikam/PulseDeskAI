from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.prompts.chat import build_chat_system_prompt
from app.ai.prompts.work_report import build_weekly_report_prompt
from app.ai.providers.base import AIProviderError
from app.ai.providers.factory import get_active_provider
from app.ai.schemas import (
    AIDiagnosticsResponse,
    AnomalyRecommendationResponse,
    AnomalyRecommendationStats,
    ActivityPatternsResponse,
    BurnoutEmployee,
    BurnoutResponse,
    ChatRequest,
    ChatResponse,
    WorkRecommendationsResponse,
    WorkReportMetrics,
)
from app.core.config import settings
from app.core.logging import get_logger
from app.models import AnomalyLog, AnomalyType, DailySummary, Department, Employee

log = get_logger("ai_service")

VALID_SEVERITIES = {"low", "medium", "high"}
DEFAULT_ANOMALY_SEVERITY_BY_TYPE = {
    getattr(AnomalyType.excessive_idle, "value", "excessive_idle"): "medium",
    getattr(AnomalyType.rapid_app_switching, "value", "rapid_app_switching"): "low",
    getattr(AnomalyType.after_hours_activity, "value", "after_hours_activity"): "medium",
    getattr(AnomalyType.unusual_app_usage, "value", "unusual_app_usage"): "medium",
}


def _clean_json_text(raw: str) -> str:
    return re.sub(r"```json|```", "", raw or "").strip()


class AIInsightsService:
    def __init__(self) -> None:
        self.provider = get_active_provider()

    @property
    def ai_enabled(self) -> bool:
        return bool(settings.AI_ENABLED)

    @staticmethod
    def _compute_risk_level(score: int) -> str:
        if score >= 85:
            return "critical"
        if score >= 70:
            return "high"
        if score >= 45:
            return "medium"
        return "low"

    @staticmethod
    def _normalize_severity(raw: Optional[str]) -> str:
        normalized = (raw or "").strip().lower()
        if normalized in VALID_SEVERITIES:
            return normalized
        return "medium"

    @staticmethod
    def _extract_anomaly_severity(anomaly: AnomalyLog) -> str:
        metadata = anomaly.event_metadata or {}
        severity_override = metadata.get("severity_override") if isinstance(metadata, dict) else None
        severity = metadata.get("severity") if isinstance(metadata, dict) else None
        if isinstance(severity_override, str):
            normalized_override = severity_override.strip().lower()
            if normalized_override in VALID_SEVERITIES:
                return normalized_override
        if isinstance(severity, str):
            normalized_severity = severity.strip().lower()
            if normalized_severity in VALID_SEVERITIES:
                return normalized_severity

        anomaly_type = getattr(anomaly.anomaly_type, "value", str(anomaly.anomaly_type))
        fallback = DEFAULT_ANOMALY_SEVERITY_BY_TYPE.get(anomaly_type, "medium")
        return AIInsightsService._normalize_severity(fallback)

    @staticmethod
    def _summarize_anomaly_stats(anomalies: list[AnomalyLog]) -> AnomalyRecommendationStats:
        high = 0
        medium = 0
        low = 0
        reviewed = 0

        for anomaly in anomalies:
            severity = AIInsightsService._extract_anomaly_severity(anomaly)
            if severity == "high":
                high += 1
            elif severity == "low":
                low += 1
            else:
                medium += 1

            if bool(getattr(anomaly, "is_reviewed", False)):
                reviewed += 1

        total = len(anomalies)
        return AnomalyRecommendationStats(
            total_violations=total,
            high_severity=high,
            medium_severity=medium,
            low_severity=low,
            reviewed=reviewed,
            unreviewed=max(total - reviewed, 0),
        )

    @staticmethod
    def _heuristic_anomaly_recommendation(stats: AnomalyRecommendationStats) -> str:
        if stats.total_violations == 0:
            return "No violations made. Continue regular monitoring."
        if stats.high_severity >= 3 or stats.unreviewed >= 8:
            return (
                "High risk: schedule a manager check-in within 24 hours, document incidents, "
                "and start a formal performance improvement plan if this pattern continues."
            )
        if stats.high_severity >= 1 or stats.unreviewed >= 4:
            return (
                "Medium risk: discuss policy adherence this week, align task priorities, and "
                "track this employee's violations daily for the next 7 days."
            )
        if stats.total_violations >= 5:
            return (
                "Moderate pattern: run a coaching conversation, reinforce policy expectations, "
                "and review progress with the employee in the next weekly check-in."
            )
        return (
            "Low risk: keep monitoring, acknowledge improvement when violations decrease, "
            "and use a weekly policy reminder."
        )

    @staticmethod
    def _build_anomaly_recommendation_prompt(
        *,
        employee_name: str,
        department_name: str,
        stats: AnomalyRecommendationStats,
        anomalies: list[AnomalyLog],
    ) -> str:
        recent_lines: list[str] = []
        for anomaly in anomalies[:10]:
            anomaly_type = getattr(anomaly.anomaly_type, "value", str(anomaly.anomaly_type))
            severity = AIInsightsService._extract_anomaly_severity(anomaly)
            detected_at = anomaly.detected_at.isoformat()
            description = (anomaly.description or "").strip()
            if len(description) > 180:
                description = f"{description[:177]}..."
            recent_lines.append(
                f"- [{detected_at}] type={anomaly_type}, severity={severity}, reviewed={bool(anomaly.is_reviewed)} :: {description}"
            )

        recent_text = "\n".join(recent_lines) if recent_lines else "- No recent violation rows"
        return f"""You are an operations and HR compliance copilot for managers.
Provide one concise recommendation paragraph (max 90 words) for the manager.
Base the recommendation on severity mix, total violations, and review status.
Do not mention that you are an AI model.

Employee: {employee_name}
Department: {department_name}
Violation totals:
- Total: {stats.total_violations}
- High severity: {stats.high_severity}
- Medium severity: {stats.medium_severity}
- Low severity: {stats.low_severity}
- Reviewed: {stats.reviewed}
- Unreviewed: {stats.unreviewed}

Recent violations:
{recent_text}
"""

    async def _build_team_context(self, db: AsyncSession) -> str:
        today = date.today()
        week_ago = today - timedelta(days=7)

        emp_result = await db.execute(
            select(Employee, Department.name.label("dept_name"))
            .outerjoin(Department, Employee.department_id == Department.id)
            .where(Employee.is_active.is_(True))
        )
        employees = emp_result.fetchall()

        summary_result = await db.execute(
            select(DailySummary)
            .where(DailySummary.date >= week_ago)
            .order_by(DailySummary.date.desc())
        )
        summaries = summary_result.scalars().all()

        anomaly_result = await db.execute(
            select(AnomalyLog)
            .where(
                AnomalyLog.detected_at
                >= datetime.combine(week_ago, datetime.min.time()).replace(tzinfo=timezone.utc)
            )
            .order_by(AnomalyLog.detected_at.desc())
            .limit(100)
        )
        anomalies = anomaly_result.scalars().all()

        emp_summaries: dict[str, list] = {}
        for s in summaries:
            emp_summaries.setdefault(str(s.employee_id), []).append(s)

        emp_anomalies: dict[str, list] = {}
        for a in anomalies:
            emp_anomalies.setdefault(str(a.employee_id), []).append(a)

        lines = [
            f"Today's date: {today.isoformat()}",
            f"Total active employees: {len(employees)}",
            "",
            "=== EMPLOYEE PERFORMANCE DATA (last 7 days) ===",
        ]

        for row in employees:
            emp = row[0]
            dept = row[1] or "No department"
            eid = str(emp.id)
            sums = emp_summaries.get(eid, [])
            anoms = emp_anomalies.get(eid, [])

            avg_score = round(sum(s.productivity_score or 0 for s in sums) / max(len(sums), 1), 1)
            avg_active_h = round(sum((s.active_seconds or 0) for s in sums) / 3600 / max(len(sums), 1), 1)
            anom_types = [a.anomaly_type.value for a in anoms if getattr(a, "anomaly_type", None)]

            lines.append(
                f"- {emp.full_name} ({dept}): "
                f"avg_productivity={avg_score}/100, "
                f"avg_active_hours={avg_active_h}h/day, "
                f"anomalies_this_week={len(anoms)} ({', '.join(sorted(set(anom_types))) or 'none'})"
            )

        return "\n".join(lines)

    async def _heuristic_chat_response(self, db: AsyncSession) -> str:
        week_ago = date.today() - timedelta(days=7)
        emp_result = await db.execute(select(Employee).where(Employee.is_active.is_(True)))
        employees = emp_result.scalars().all()

        summary_result = await db.execute(select(DailySummary).where(DailySummary.date >= week_ago))
        summaries = summary_result.scalars().all()

        anomaly_result = await db.execute(
            select(AnomalyLog).where(
                AnomalyLog.detected_at
                >= datetime.combine(week_ago, datetime.min.time()).replace(tzinfo=timezone.utc)
            )
        )
        anomalies = anomaly_result.scalars().all()

        avg_score = round(
            sum(s.productivity_score or 0 for s in summaries) / max(len(summaries), 1),
            1,
        )
        return (
            "AI response is currently unavailable, so here is a heuristic snapshot:\n"
            f"- Active employees: {len(employees)}\n"
            f"- 7-day average productivity: {avg_score}\n"
            f"- Anomalies in last 7 days: {len(anomalies)}\n"
            "- You can still use burnout risk and activity pattern endpoints for deterministic insights."
        )

    async def chat(self, req: ChatRequest, db: AsyncSession) -> ChatResponse:
        if not self.ai_enabled:
            return ChatResponse(reply=await self._heuristic_chat_response(db), source="heuristic")

        team_context = await self._build_team_context(db)
        system_prompt = build_chat_system_prompt(team_context)

        messages = [{"role": h.role, "content": h.content} for h in req.history[-10:]]
        messages.append({"role": "user", "content": req.message})

        try:
            reply = await self.provider.generate_text(
                messages=messages,
                system_prompt=system_prompt,
                temperature=0.4,
                max_tokens=800,
            )
            return ChatResponse(reply=reply, source="groq")
        except AIProviderError as e:
            log.warning("ai_chat_provider_failed", error=e.message, retriable=e.retriable)
            return ChatResponse(reply=await self._heuristic_chat_response(db), source="heuristic")
        except Exception as e:
            log.error("ai_chat_unknown_failure", error_type=type(e).__name__)
            return ChatResponse(reply=await self._heuristic_chat_response(db), source="heuristic")

    async def burnout_risks(self, db: AsyncSession) -> BurnoutResponse:
        today = date.today()
        week_ago = today - timedelta(days=7)

        emp_result = await db.execute(
            select(Employee, Department.name.label("dept_name"))
            .outerjoin(Department, Employee.department_id == Department.id)
            .where(Employee.is_active.is_(True))
        )
        emp_rows = emp_result.fetchall()

        summary_result = await db.execute(
            select(DailySummary).where(DailySummary.date >= week_ago).order_by(DailySummary.date.desc())
        )
        summaries = summary_result.scalars().all()

        anomaly_result = await db.execute(
            select(AnomalyLog)
            .where(
                AnomalyLog.detected_at
                >= datetime.combine(week_ago, datetime.min.time()).replace(tzinfo=timezone.utc)
            )
            .order_by(AnomalyLog.detected_at.desc())
        )
        anomalies = anomaly_result.scalars().all()

        emp_summaries: dict[str, list] = {}
        for s in summaries:
            emp_summaries.setdefault(str(s.employee_id), []).append(s)

        emp_anomalies: dict[str, list] = {}
        for a in anomalies:
            emp_anomalies.setdefault(str(a.employee_id), []).append(a)

        result: list[BurnoutEmployee] = []
        for row in emp_rows:
            emp = row[0]
            dept = row[1] or "No department"
            eid = str(emp.id)

            sums = emp_summaries.get(eid, [])
            anoms = emp_anomalies.get(eid, [])

            avg_score = round(sum(s.productivity_score or 0 for s in sums) / max(len(sums), 1), 1)
            avg_active_h = round(sum((s.active_seconds or 0) for s in sums) / 3600 / max(len(sums), 1), 1)

            anomaly_names = []
            for a in anoms:
                anomaly_type = getattr(a, "anomaly_type", None)
                if anomaly_type is not None:
                    anomaly_names.append(getattr(anomaly_type, "value", str(anomaly_type)))

            risk_score = 10
            signals: list[str] = []

            if avg_active_h > 9:
                risk_score += 35
                signals.append("Very high average work hours")
            elif avg_active_h > 8:
                risk_score += 20
                signals.append("Sustained long work hours")

            if avg_score < 45:
                risk_score += 25
                signals.append("Low productivity trend")
            elif avg_score < 60:
                risk_score += 10
                signals.append("Moderate productivity dip")

            after_hours_count = sum(1 for x in anomaly_names if x == "after_hours_activity")
            excessive_idle_count = sum(1 for x in anomaly_names if x == "excessive_idle")

            if after_hours_count >= 3:
                risk_score += 20
                signals.append("Frequent after-hours activity")
            elif after_hours_count > 0:
                risk_score += 10
                signals.append("Some after-hours work detected")

            if excessive_idle_count >= 2:
                risk_score += 15
                signals.append("Repeated excessive idle periods")

            if not signals:
                signals.append("No strong burnout indicators this week")

            risk_score = max(0, min(100, risk_score))
            risk_level = self._compute_risk_level(risk_score)

            if risk_level in {"critical", "high"}:
                recommendation = (
                    "Schedule a 1:1 check-in, review workload, and reduce after-hours expectations."
                )
            elif risk_level == "medium":
                recommendation = "Monitor work patterns and encourage better work-rest balance this week."
            else:
                recommendation = "Continue monitoring and maintain current workload support."

            result.append(
                BurnoutEmployee(
                    employee_id=eid,
                    name=emp.full_name,
                    department=dept,
                    risk_score=risk_score,
                    risk_level=risk_level,
                    signals=signals[:3],
                    recommendation=recommendation,
                )
            )

        result.sort(key=lambda x: x.risk_score, reverse=True)
        high_count = sum(1 for e in result if e.risk_level in {"high", "critical"})
        medium_count = sum(1 for e in result if e.risk_level == "medium")
        summary = (
            f"Team wellbeing analysis: {high_count} employees in high/critical burnout risk, "
            f"{medium_count} in medium risk."
        )
        return BurnoutResponse(employees=result, summary=summary)

    async def activity_patterns(
        self,
        employee_id: str,
        db: AsyncSession,
    ) -> ActivityPatternsResponse:
        emp_result = await db.execute(
            select(Employee, Department.name.label("dept_name")).where(Employee.id == employee_id)
        )
        emp_row = emp_result.first()
        if not emp_row:
            raise HTTPException(status_code=404, detail="Employee not found")

        employee, dept = emp_row[0], emp_row[1]
        week_ago = date.today() - timedelta(days=7)
        summary_result = await db.execute(
            select(DailySummary)
            .where((DailySummary.employee_id == employee_id) & (DailySummary.date >= week_ago))
            .order_by(DailySummary.date.asc())
        )
        summaries = summary_result.scalars().all()

        if not summaries:
            return ActivityPatternsResponse(
                employee_id=str(employee_id),
                employee_name=employee.full_name,
                department=dept or "No department",
                peak_activity_time="N/A",
                avg_daily_hours=0,
                productivity_trend="N/A",
                focus_quality="N/A",
                recommendations=[
                    "Enable device tracking for this employee to collect activity data.",
                    "Activity data appears in the system after the monitoring agent starts.",
                    "Once data is available, personalized insights will be generated here.",
                ],
                message="No activity data available - employee tracking not yet active",
            )

        total_active_seconds = sum(s.active_seconds or 0 for s in summaries)
        total_focus_seconds = sum(s.focus_seconds or 0 for s in summaries)
        avg_daily_hours = round(total_active_seconds / 3600 / max(len(summaries), 1), 1)
        avg_focus_hours = round(total_focus_seconds / 3600 / max(len(summaries), 1), 1)

        first_half_avg = round(
            sum(s.productivity_score or 0 for s in summaries[: len(summaries) // 2])
            / max(len(summaries) // 2, 1),
            1,
        )
        second_half_avg = round(
            sum(s.productivity_score or 0 for s in summaries[len(summaries) // 2 :])
            / max(len(summaries) - len(summaries) // 2, 1),
            1,
        )

        if second_half_avg > first_half_avg + 5:
            trend = "improving"
        elif second_half_avg < first_half_avg - 5:
            trend = "declining"
        else:
            trend = "stable"

        focus_quality = "high" if avg_focus_hours >= 4 else ("medium" if avg_focus_hours >= 2 else "low")

        peak_hours = {8: 0, 10: 0, 14: 0, 16: 0}
        for s in summaries:
            if isinstance(s.hourly_active_seconds, dict):
                for h, sec in s.hourly_active_seconds.items():
                    try:
                        hour = int(h)
                        if hour in peak_hours:
                            peak_hours[hour] += sec
                    except (ValueError, TypeError):
                        continue
        peak_hour = max(peak_hours.items(), key=lambda x: x[1])[0] if peak_hours else 10
        peak_time = f"{peak_hour % 12 or 12}:00 {'AM' if peak_hour < 12 else 'PM'}"

        return ActivityPatternsResponse(
            employee_id=str(employee_id),
            employee_name=employee.full_name,
            department=dept or "No department",
            peak_activity_time=peak_time,
            avg_daily_hours=avg_daily_hours,
            productivity_trend=trend,
            focus_quality=focus_quality,
            recommendations=[
                f"Peak productivity occurs at {peak_time}. Schedule deep work during this window.",
                f"Average daily focus: {avg_focus_hours}h. Maintain {max(1, avg_focus_hours - 1)}h+ for optimal performance.",
                "Take 5-minute breaks every hour to prevent context-switching fatigue.",
            ],
        )

    async def _build_work_report_data(
        self,
        employee_id: str,
        db: AsyncSession,
    ) -> tuple[Employee, Optional[str], list, int]:
        emp_result = await db.execute(
            select(Employee, Department.name.label("dept_name")).where(Employee.id == employee_id)
        )
        emp_row = emp_result.first()
        if not emp_row:
            raise HTTPException(status_code=404, detail="Employee not found")

        employee, dept = emp_row[0], emp_row[1]
        week_ago = date.today() - timedelta(days=7)

        summary_result = await db.execute(
            select(DailySummary)
            .where((DailySummary.employee_id == employee_id) & (DailySummary.date >= week_ago))
            .order_by(DailySummary.date.desc())
            .limit(7)
        )
        summaries = summary_result.scalars().all()

        anomaly_result = await db.execute(
            select(AnomalyLog)
            .where(AnomalyLog.employee_id == employee_id)
            .order_by(AnomalyLog.detected_at.desc())
            .limit(5)
        )
        anomalies = anomaly_result.scalars().all()

        return employee, dept, summaries, len(anomalies)

    def _heuristic_work_report(
        self,
        *,
        employee_id: str,
        employee_name: str,
        dept: Optional[str],
        period: str,
        avg_productivity: float,
        avg_active_hours: float,
        avg_focus_hours: float,
        anomaly_count: int,
    ) -> WorkRecommendationsResponse:
        rating = (
            "Excellent"
            if avg_productivity >= 80
            else "Good"
            if avg_productivity >= 65
            else "Fair"
            if avg_productivity >= 50
            else "Needs Improvement"
        )
        return WorkRecommendationsResponse(
            employee_id=employee_id,
            employee_name=employee_name,
            department=dept or "No department",
            report_title="Weekly Performance Report",
            period=period,
            performance_rating=rating,
            summary=(
                f"Avg productivity: {avg_productivity}%, active time: {avg_active_hours}h/day, "
                f"focus: {avg_focus_hours}h/day, anomalies: {anomaly_count}."
            ),
            highlights=[
                "Consistent data captured across the week.",
                f"Average active hours: {avg_active_hours}h/day.",
                f"Average focus hours: {avg_focus_hours}h/day.",
            ],
            focus_areas=[
                "Reduce context switching in lower-productivity windows.",
                "Schedule focused blocks in peak hours.",
                "Review anomalies for recurring patterns.",
            ],
            coaching_tips=[
                "Use calendar-based focus blocks for deep work.",
                "Align demanding tasks with peak activity periods.",
                "Set a clear end-of-day boundary to avoid fatigue.",
            ],
            action_items=[
                "Review this week's activity timeline with the employee.",
                "Agree on 2-3 focus windows for next week.",
                "Track anomaly trend weekly.",
            ],
            motivational_message="Progress is measurable. Build consistency, not perfection.",
            metrics=WorkReportMetrics(
                avg_active_hours=avg_active_hours,
                avg_focus_hours=avg_focus_hours,
                productivity_score=avg_productivity,
                anomalies=anomaly_count,
            ),
            timestamp=datetime.now(timezone.utc),
            source="heuristic",
        )

    async def work_recommendations(
        self,
        employee_id: str,
        db: AsyncSession,
    ) -> WorkRecommendationsResponse:
        employee, dept, summaries, anomaly_count = await self._build_work_report_data(employee_id, db)

        if not summaries:
            return WorkRecommendationsResponse(
                employee_id=str(employee_id),
                employee_name=employee.full_name,
                department=dept or "No department",
                report_title="Weekly Performance Report",
                period="No Data Available",
                performance_rating="Data Pending",
                summary="Enable device tracking for this employee to generate performance insights.",
                highlights=["Data collection needed"],
                focus_areas=["Enable monitoring to track activity"],
                coaching_tips=["Once tracking is enabled, AI coaching will be available"],
                action_items=["Start the monitoring agent for this employee"],
                motivational_message="Once data is available, coaching insights will be generated.",
                metrics=WorkReportMetrics(
                    avg_active_hours=0,
                    avg_focus_hours=0,
                    productivity_score=0,
                    anomalies=0,
                ),
                timestamp=datetime.now(timezone.utc),
                source="heuristic",
            )

        avg_productivity = round(sum(s.productivity_score or 0 for s in summaries) / len(summaries), 1)
        avg_active_hours = round(sum(s.active_seconds or 0 for s in summaries) / 3600 / len(summaries), 1)
        avg_focus_hours = round(sum(s.focus_seconds or 0 for s in summaries) / 3600 / len(summaries), 1)
        total_app_switches = sum(s.app_switches or 0 for s in summaries)
        focus_sessions_total = sum(s.focus_sessions or 0 for s in summaries)

        date_end = summaries[0].date.strftime("%b %d, %Y")
        date_start = summaries[-1].date.strftime("%b %d")
        period = f"{date_start} - {date_end}"
        breakdown_data = [
            {
                "date": str(s.date),
                "active_h": round((s.active_seconds or 0) / 3600, 1),
                "focus_h": round((s.focus_seconds or 0) / 3600, 1),
                "productivity": s.productivity_score,
            }
            for s in summaries[::-1]
        ]
        data_context = f"""Employee: {employee.full_name} ({dept or 'No department'})
Week: {period}

Key Metrics (7-day average):
- Daily Active Hours: {avg_active_hours}h
- Focus Hours: {avg_focus_hours}h
- Productivity Score: {avg_productivity}/100
- App Switches: {total_app_switches} total
- Focus Sessions: {focus_sessions_total} total
- Anomalies Detected: {anomaly_count}
- Top App Category: {summaries[0].top_category or 'N/A'}

Daily Breakdown:
{json.dumps(breakdown_data, indent=2)}"""

        if not self.ai_enabled:
            return self._heuristic_work_report(
                employee_id=str(employee_id),
                employee_name=employee.full_name,
                dept=dept,
                period=period,
                avg_productivity=avg_productivity,
                avg_active_hours=avg_active_hours,
                avg_focus_hours=avg_focus_hours,
                anomaly_count=anomaly_count,
            )

        prompt = build_weekly_report_prompt(data_context)
        try:
            report_raw = await self.provider.generate_text(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.6,
                max_tokens=1200,
            )
            parsed = json.loads(_clean_json_text(report_raw))
            return WorkRecommendationsResponse(
                employee_id=str(employee_id),
                employee_name=employee.full_name,
                department=dept or "No department",
                report_title="AI-Generated Weekly Performance Report",
                period=period,
                performance_rating=parsed.get("performance_rating", "Evaluating"),
                summary=parsed.get("summary", "Report processing..."),
                highlights=parsed.get("highlights", []),
                focus_areas=parsed.get("focus_areas", []),
                coaching_tips=parsed.get("coaching_tips", []),
                action_items=parsed.get("action_items", []),
                motivational_message=parsed.get("motivational_message", ""),
                metrics=WorkReportMetrics(
                    avg_active_hours=avg_active_hours,
                    avg_focus_hours=avg_focus_hours,
                    productivity_score=avg_productivity,
                    anomalies=anomaly_count,
                ),
                timestamp=datetime.now(timezone.utc),
                source="groq",
            )
        except (AIProviderError, json.JSONDecodeError) as e:
            log.warning("ai_weekly_report_fallback", error_type=type(e).__name__)
            return self._heuristic_work_report(
                employee_id=str(employee_id),
                employee_name=employee.full_name,
                dept=dept,
                period=period,
                avg_productivity=avg_productivity,
                avg_active_hours=avg_active_hours,
                avg_focus_hours=avg_focus_hours,
                anomaly_count=anomaly_count,
            )
        except Exception as e:
            log.error("ai_weekly_report_unknown_failure", error_type=type(e).__name__)
            return self._heuristic_work_report(
                employee_id=str(employee_id),
                employee_name=employee.full_name,
                dept=dept,
                period=period,
                avg_productivity=avg_productivity,
                avg_active_hours=avg_active_hours,
                avg_focus_hours=avg_focus_hours,
                anomaly_count=anomaly_count,
            )

    async def anomaly_recommendation(
        self,
        employee_id: str,
        db: AsyncSession,
    ) -> AnomalyRecommendationResponse:
        emp_result = await db.execute(
            select(Employee, Department.name.label("dept_name")).where(Employee.id == employee_id)
        )
        emp_row = emp_result.first()
        if not emp_row:
            raise HTTPException(status_code=404, detail="Employee not found")

        employee, dept = emp_row[0], emp_row[1]
        anomaly_result = await db.execute(
            select(AnomalyLog)
            .where(AnomalyLog.employee_id == employee_id)
            .order_by(AnomalyLog.detected_at.desc())
            .limit(60)
        )
        anomalies = anomaly_result.scalars().all()
        stats = self._summarize_anomaly_stats(anomalies)
        fallback_recommendation = self._heuristic_anomaly_recommendation(stats)

        if stats.total_violations == 0:
            return AnomalyRecommendationResponse(
                employee_id=str(employee.id),
                employee_name=employee.full_name,
                recommendation=fallback_recommendation,
                source="heuristic",
                stats=stats,
                generated_at=datetime.now(timezone.utc),
            )

        if not self.ai_enabled:
            return AnomalyRecommendationResponse(
                employee_id=str(employee.id),
                employee_name=employee.full_name,
                recommendation=fallback_recommendation,
                source="heuristic",
                stats=stats,
                generated_at=datetime.now(timezone.utc),
            )

        prompt = self._build_anomaly_recommendation_prompt(
            employee_name=employee.full_name,
            department_name=dept or "No department",
            stats=stats,
            anomalies=anomalies,
        )
        try:
            recommendation = await self.provider.generate_text(
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=220,
            )
            recommendation = (recommendation or "").strip()
            if not recommendation:
                recommendation = fallback_recommendation
                source = "heuristic"
            else:
                source = "groq"

            return AnomalyRecommendationResponse(
                employee_id=str(employee.id),
                employee_name=employee.full_name,
                recommendation=recommendation,
                source=source,
                stats=stats,
                generated_at=datetime.now(timezone.utc),
            )
        except AIProviderError as e:
            log.warning("ai_anomaly_recommendation_fallback", error=e.message, retriable=e.retriable)
            return AnomalyRecommendationResponse(
                employee_id=str(employee.id),
                employee_name=employee.full_name,
                recommendation=fallback_recommendation,
                source="heuristic",
                stats=stats,
                generated_at=datetime.now(timezone.utc),
            )
        except Exception as e:
            log.error("ai_anomaly_recommendation_unknown_failure", error_type=type(e).__name__)
            return AnomalyRecommendationResponse(
                employee_id=str(employee.id),
                employee_name=employee.full_name,
                recommendation=fallback_recommendation,
                source="heuristic",
                stats=stats,
                generated_at=datetime.now(timezone.utc),
            )

    async def diagnostics(self, db: AsyncSession) -> AIDiagnosticsResponse:
        week_ago = date.today() - timedelta(days=7)

        emp_result = await db.execute(select(Employee).where(Employee.is_active.is_(True)))
        total_employees = len(emp_result.scalars().all())

        summary_result = await db.execute(select(DailySummary).where(DailySummary.date >= week_ago))
        summary_records = summary_result.scalars().all()

        anomaly_result = await db.execute(
            select(AnomalyLog).where(
                AnomalyLog.detected_at
                >= datetime.combine(week_ago, datetime.min.time()).replace(tzinfo=timezone.utc)
            )
        )
        anomaly_records = anomaly_result.scalars().all()

        emp_with_activity = await db.execute(
            select(Employee.full_name)
            .outerjoin(DailySummary)
            .where((Employee.is_active.is_(True)) & (DailySummary.date >= week_ago))
            .distinct()
        )
        employee_names_with_data = [row[0] for row in emp_with_activity.fetchall()]

        return AIDiagnosticsResponse(
            status="Database Data Status",
            total_active_employees=total_employees,
            daily_summary_records_last_7_days=len(summary_records),
            anomaly_records_last_7_days=len(anomaly_records),
            employees_with_activity_data=len(employee_names_with_data),
            employee_names_with_data=employee_names_with_data,
            recommendation=(
                "Empty: Agent/device not sending data. Check device enrollment and agent status."
                if len(summary_records) == 0
                else "Data present. AI features ready."
            ),
            ai_enabled=bool(settings.AI_ENABLED),
            ai_provider="groq",
            groq_model=settings.GROQ_MODEL,
            screenshot_analysis_enabled=bool(settings.AI_SCREENSHOT_ANALYSIS_ENABLED),
        )


ai_insights_service = AIInsightsService()
