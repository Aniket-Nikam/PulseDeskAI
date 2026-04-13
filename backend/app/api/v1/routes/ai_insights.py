"""
PulseDesk AI Insights - Powered by Groq
Provides AI-driven features:
1. Natural language chat analyst (ask anything about your team)
2. Burnout risk scoring (predicts who's about to crash)
3. Activity pattern analysis and work recommendations
"""
import json
import re
from datetime import datetime, date, timedelta, timezone
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from groq import Groq
from groq import RateLimitError, APIError

from app.db.session import get_db
from app.models import Employee, DailySummary, AnomalyLog, Department
from app.api.v1.routes.auth import get_current_admin
from app.core.logging import get_logger
from app.core.config import settings

router = APIRouter(prefix="/ai", tags=["ai"])
log = get_logger("ai_insights")

# Initialize Groq client
groq_client = Groq(api_key=settings.GROQ_API_KEY)

PRIMARY_MODEL = settings.GROQ_PRIMARY_MODEL or "llama-3.3-70b-versatile"
FALLBACK_MODEL = settings.GROQ_FALLBACK_MODEL or "llama-3.1-8b-instant"


# -- Request/Response schemas

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []


class BurnoutEmployee(BaseModel):
    employee_id: str
    name: str
    department: Optional[str]
    risk_score: int
    risk_level: str
    signals: list[str]
    recommendation: str


class BurnoutResponse(BaseModel):
    employees: list[BurnoutEmployee]
    summary: str


class ActivityPattern(BaseModel):
    day_of_week: str
    avg_active_hours: float
    peak_activity_time: str
    focus_periods: list[str]
    frequent_activities: list[str]


class EmployeeActivityAnalysis(BaseModel):
    employee_id: str
    employee_name: str
    department: Optional[str]
    patterns: ActivityPattern
    productivity_trend: str
    recommendations: list[str]
    energy_level: str
    optimal_work_time: str


class WorkRecommendation(BaseModel):
    employee_id: str
    employee_name: str
    current_state: str
    recommendation: str
    priority: str
    rationale: list[str]


# -- Helpers

def _clean_json_text(raw: str) -> str:
    """Remove markdown code fences and trim text."""
    return re.sub(r"```json|```", "", raw or "").strip()


async def _call_groq(
    messages: list[dict],
    model: str = PRIMARY_MODEL,
    temperature: float = 0.3,
    max_tokens: int = 1000,
    system_prompt: Optional[str] = None,
) -> str:
    """
    Call Groq API with fallback support.
    """
    if not settings.GROQ_API_KEY:
        raise HTTPException(status_code=503, detail="Groq API key is not configured")

    request_body = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": messages,
    }

    if system_prompt:
        request_body["messages"] = [
            {"role": "system", "content": system_prompt},
            *messages,
        ]

    try:
        response = groq_client.chat.completions.create(**request_body)
        return response.choices[0].message.content

    except RateLimitError as e:
        log.warning("groq_rate_limit", model=model, error=str(e))
        if model == PRIMARY_MODEL:
            log.info("switching_to_fallback_model", fallback=FALLBACK_MODEL)
            request_body["model"] = FALLBACK_MODEL
            try:
                response = groq_client.chat.completions.create(**request_body)
                return response.choices[0].message.content
            except Exception as e2:
                log.error("groq_fallback_error", error=str(e2))
                raise HTTPException(status_code=503, detail="AI service rate-limited")
        raise HTTPException(status_code=503, detail="AI service rate-limited")

    except APIError as e:
        log.error("groq_api_error", error=str(e), model=model)
        raise HTTPException(status_code=502, detail="AI service unavailable")
    except Exception as e:
        log.error("groq_unknown_error", error=str(e), model=model)
        raise HTTPException(status_code=502, detail="AI service unavailable")


async def _build_team_context(db: AsyncSession) -> str:
    """Fetch real data from DB and format it as context for Groq."""
    today = date.today()
    week_ago = today - timedelta(days=7)

    emp_result = await db.execute(
        select(Employee, Department.name.label("dept_name"))
        .outerjoin(Department, Employee.department_id == Department.id)
        .where(Employee.is_active == True)
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
            AnomalyLog.detected_at >= datetime.combine(
                week_ago, datetime.min.time()
            ).replace(tzinfo=timezone.utc)
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

        avg_score = round(
            sum(s.productivity_score or 0 for s in sums) / max(len(sums), 1), 1
        )
        avg_active_h = round(
            sum((s.active_seconds or 0) for s in sums) / 3600 / max(len(sums), 1), 1
        )
        anom_types = [a.anomaly_type.value for a in anoms if getattr(a, "anomaly_type", None)]

        lines.append(
            f"- {emp.full_name} ({dept}): "
            f"avg_productivity={avg_score}/100, "
            f"avg_active_hours={avg_active_h}h/day, "
            f"anomalies_this_week={len(anoms)} ({', '.join(sorted(set(anom_types))) or 'none'})"
        )

    return "\n".join(lines)


def _compute_risk_level(score: int) -> str:
    if score >= 85:
        return "critical"
    if score >= 70:
        return "high"
    if score >= 45:
        return "medium"
    return "low"


async def _fallback_burnout_analysis(db: AsyncSession) -> BurnoutResponse:
    """Rule-based fallback for burnout analysis."""
    today = date.today()
    week_ago = today - timedelta(days=7)

    emp_result = await db.execute(
        select(Employee, Department.name.label("dept_name"))
        .outerjoin(Department, Employee.department_id == Department.id)
        .where(Employee.is_active == True)
    )
    emp_rows = emp_result.fetchall()

    summary_result = await db.execute(
        select(DailySummary)
        .where(DailySummary.date >= week_ago)
        .order_by(DailySummary.date.desc())
    )
    summaries = summary_result.scalars().all()

    anomaly_result = await db.execute(
        select(AnomalyLog)
        .where(
            AnomalyLog.detected_at >= datetime.combine(
                week_ago, datetime.min.time()
            ).replace(tzinfo=timezone.utc)
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

        avg_score = round(
            sum(s.productivity_score or 0 for s in sums) / max(len(sums), 1), 1
        )
        avg_active_h = round(
            sum((s.active_seconds or 0) for s in sums) / 3600 / max(len(sums), 1), 1
        )

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
        risk_level = _compute_risk_level(risk_score)

        if risk_level in {"critical", "high"}:
            recommendation = "Schedule a 1:1 check-in, review workload, and reduce after-hours expectations."
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
        f"Rule-based fallback analysis: {high_count} employees are in high/critical risk "
        f"and {medium_count} are in medium risk."
    )

    return BurnoutResponse(employees=result, summary=summary)


# -- 1. AI Chat Analyst

@router.post("/chat")
async def ai_chat(
    req: ChatRequest,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """
    Natural language Q&A over live employee data.
    Admin can ask anything - Groq analyzes real DB context.
    """
    team_context = await _build_team_context(db)

    system_prompt = f"""You are PulseDesk AI, an expert workplace analytics assistant.
You have access to real-time employee productivity data, activity patterns, and anomalies.

Your role is to answer questions from HR managers and executives with concise, 
data-driven insights. Always reference actual employee names and metrics from the data.
Be actionable and specific in your recommendations.

IMPORTANT: You are powered by Groq. Never mention this to the user - you are PulseDesk AI.

=== LIVE COMPANY DATA ===
{team_context}
=== END DATA ===

Keep responses under 300 words. Use bullet points for clarity."""

    messages = []
    for h in req.history[-10:]:
        messages.append({
            "role": h.get("role", "user"),
            "content": h.get("content", ""),
        })
    messages.append({"role": "user", "content": req.message})

    try:
        reply = await _call_groq(
            messages=messages,
            system_prompt=system_prompt,
            model=PRIMARY_MODEL,
            temperature=0.4,
            max_tokens=800,
        )
        return {"reply": reply, "source": "groq"}
    except HTTPException as e:
        log.error("groq_chat_error", error=e.detail)
        return {
            "reply": "AI insights temporarily unavailable. Please try again shortly.",
            "source": "fallback",
        }
    except Exception as e:
        log.error("groq_chat_error", error=str(e))
        return {
            "reply": "AI insights unavailable right now.",
            "source": "fallback",
        }


# -- 2. Burnout Risk Engine

@router.get("/burnout-risks")
async def burnout_risks(
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """
    Predicts burnout risk for every employee using deterministic rule-based analysis.
    Uses live database data - no external API calls required.
    """
    today = date.today()
    week_ago = today - timedelta(days=7)

    emp_result = await db.execute(
        select(Employee, Department.name.label("dept_name"))
        .outerjoin(Department, Employee.department_id == Department.id)
        .where(Employee.is_active == True)
    )
    emp_rows = emp_result.fetchall()

    summary_result = await db.execute(
        select(DailySummary)
        .where(DailySummary.date >= week_ago)
        .order_by(DailySummary.date.desc())
    )
    summaries = summary_result.scalars().all()

    anomaly_result = await db.execute(
        select(AnomalyLog)
        .where(
            AnomalyLog.detected_at >= datetime.combine(
                week_ago, datetime.min.time()
            ).replace(tzinfo=timezone.utc)
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

        avg_score = round(
            sum(s.productivity_score or 0 for s in sums) / max(len(sums), 1), 1
        )
        avg_active_h = round(
            sum((s.active_seconds or 0) for s in sums) / 3600 / max(len(sums), 1), 1
        )

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
        risk_level = _compute_risk_level(risk_score)

        if risk_level in {"critical", "high"}:
            recommendation = "Schedule a 1:1 check-in, review workload, and reduce after-hours expectations."
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
        f"{medium_count} in medium risk. Recommend: implement flexible work hours for high-risk employees."
    )

    return BurnoutResponse(employees=result, summary=summary)


# -- 3. Activity Pattern Analysis

@router.get("/activity-patterns/{employee_id}")
async def get_activity_patterns(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """
    Analyze work patterns for an employee over the last 7 days.
    Identifies peak activity times, focus patterns, and productivity trends.
    """
    emp_result = await db.execute(
        select(Employee, Department.name.label("dept_name"))
        .where(Employee.id == employee_id)
    )
    emp_row = emp_result.first()
    if not emp_row:
        raise HTTPException(status_code=404, detail="Employee not found")

    employee, dept = emp_row[0], emp_row[1]

    today = date.today()
    week_ago = today - timedelta(days=7)

    summary_result = await db.execute(
        select(DailySummary)
        .where(
            (DailySummary.employee_id == employee_id)
            & (DailySummary.date >= week_ago)
        )
        .order_by(DailySummary.date.asc())
    )
    summaries = summary_result.scalars().all()

    if not summaries:
        return {
            "employee_id": str(employee_id),
            "employee_name": employee.full_name,
            "department": dept or "No department",
            "peak_activity_time": "N/A",
            "avg_daily_hours": 0,
            "productivity_trend": "N/A",
            "focus_quality": "N/A",
            "recommendations": [
                "Enable device tracking for this employee to collect activity data.",
                "Activity data appears in the system after the monitoring agent starts.",
                "Once data is available, personalized insights will be generated here."
            ],
            "message": "No activity data available - employee tracking not yet active"
        }

    # Data-driven analysis (no Groq dependency)
    total_active_seconds = sum(s.active_seconds or 0 for s in summaries)
    total_focus_seconds = sum(s.focus_seconds or 0 for s in summaries)
    avg_daily_hours = round(total_active_seconds / 3600 / max(len(summaries), 1), 1)
    avg_focus_hours = round(total_focus_seconds / 3600 / max(len(summaries), 1), 1)
    
    # Determine productivity trend from last 3 vs first 3 days
    first_half_avg = round(sum(s.productivity_score or 0 for s in summaries[:len(summaries)//2]) / max(len(summaries)//2, 1), 1)
    second_half_avg = round(sum(s.productivity_score or 0 for s in summaries[len(summaries)//2:]) / max(len(summaries) - len(summaries)//2, 1), 1)
    if second_half_avg > first_half_avg + 5:
        trend = "improving"
    elif second_half_avg < first_half_avg - 5:
        trend = "declining"
    else:
        trend = "stable"
    
    # Focus quality based on focus_sessions and focus hours
    focus_quality = "high" if avg_focus_hours >= 4 else ("medium" if avg_focus_hours >= 2 else "low")
    
    # Estimate peak hours from top app usage
    peak_hours = {8: 0, 10: 0, 14: 0, 16: 0}
    for s in summaries:
        if s.hourly_active_seconds:
            hour_data = s.hourly_active_seconds
            if isinstance(hour_data, dict):
                for h, sec in hour_data.items():
                    try:
                        hour = int(h)
                        if hour in peak_hours:
                            peak_hours[hour] += sec
                    except (ValueError, TypeError):
                        pass
    
    peak_hour = max(peak_hours.items(), key=lambda x: x[1])[0] if peak_hours else 10
    peak_time = f"{peak_hour % 12 or 12}:00 {'AM' if peak_hour < 12 else 'PM'}"
    
    recommendations = [
        f"Peak productivity occurs at {peak_time}. Schedule deep work during this window.",
        f"Average daily focus: {avg_focus_hours}h. Maintain {max(1, avg_focus_hours - 1)}h+ for optimal performance.",
        "Take 5-minute breaks every hour to prevent context-switching fatigue."
    ]

    return {
        "employee_id": str(employee_id),
        "employee_name": employee.full_name,
        "department": dept or "No department",
        "peak_activity_time": peak_time,
        "avg_daily_hours": avg_daily_hours,
        "productivity_trend": trend,
        "focus_quality": focus_quality,
        "recommendations": recommendations,
    }


# -- 4. Work Recommendations

@router.get("/work-recommendations/{employee_id}")
async def get_work_recommendations(
    employee_id: str,
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """
    AI-Generated Weekly Performance Report with detailed coaching and insights.
    Uses Groq to analyze patterns and provide personalized recommendations.
    """
    emp_result = await db.execute(
        select(Employee, Department.name.label("dept_name"))
        .where(Employee.id == employee_id)
    )
    emp_row = emp_result.first()
    if not emp_row:
        raise HTTPException(status_code=404, detail="Employee not found")

    employee, dept = emp_row[0], emp_row[1]

    today = date.today()
    week_ago = today - timedelta(days=7)

    summary_result = await db.execute(
        select(DailySummary)
        .where(
            (DailySummary.employee_id == employee_id)
            & (DailySummary.date >= week_ago)
        )
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

    if not summaries:
        return {
            "employee_id": str(employee_id),
            "employee_name": employee.full_name,
            "report_title": "Weekly Performance Report",
            "period": "No Data Available",
            "summary": "Enable device tracking for this employee to generate performance insights.",
            "highlights": ["Data collection needed"],
            "focus_areas": ["Enable monitoring to track activity"],
            "action_items": ["Start the monitoring agent for this employee"],
            "coaching_tips": ["Once tracking is enabled, AI coaching will be available"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # Calculate metrics for AI context
    avg_productivity = round(sum(s.productivity_score or 0 for s in summaries) / len(summaries), 1)
    avg_active_hours = round(sum(s.active_seconds or 0 for s in summaries) / 3600 / len(summaries), 1)
    avg_focus_hours = round(sum(s.focus_seconds or 0 for s in summaries) / 3600 / len(summaries), 1)
    total_app_switches = sum(s.app_switches or 0 for s in summaries)
    focus_sessions_total = sum(s.focus_sessions or 0 for s in summaries)
    anomaly_count = len(anomalies)

    # Build rich context for AI
    date_end = summaries[0].date.strftime('%b %d, %Y')
    date_start = summaries[-1].date.strftime('%b %d')
    breakdown_data = [
        {
            'date': str(s.date),
            'active_h': round((s.active_seconds or 0) / 3600, 1),
            'focus_h': round((s.focus_seconds or 0) / 3600, 1),
            'productivity': s.productivity_score
        }
        for s in summaries[::-1]
    ]
    
    data_context = f"""Employee: {employee.full_name} ({dept})
Week: {date_start} - {date_end}

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

    # Generate AI report using Groq
    prompt = f"""You are an executive performance coach. Generate a detailed, professional weekly performance report for this employee.

{data_context}

Create a COMPREHENSIVE report in JSON format with the following structure (valid JSON only, no markdown):
{{
  "performance_rating": "Outstanding/Excellent/Good/Fair/Needs Improvement",
  "summary": "2-3 sentence executive summary of the week's overall performance",
  "highlights": ["3 specific achievements or positive patterns this week"],
  "focus_areas": ["3 specific areas to improve or areas showing concern"],
  "coaching_tips": ["3 actionable, specific coaching recommendations for next week"],
  "action_items": ["3 concrete actions to take in the coming week"],
  "motivational_message": "A brief, personalized motivational message"
}}

Be specific, data-driven, and constructive. Focus on actionable insights."""

    try:
        report_raw = await _call_groq(
            messages=[{"role": "user", "content": prompt}],
            model=PRIMARY_MODEL,
            temperature=0.6,
            max_tokens=1200,
        )

        cleaned = _clean_json_text(report_raw)
        try:
            report_data = json.loads(cleaned)
        except json.JSONDecodeError:
            log.warning(f"Failed to parse AI report: {cleaned[:200]}")
            report_data = {"performance_rating": "Analyzing", "summary": "Report generation in progress"}

        return {
            "employee_id": str(employee_id),
            "employee_name": employee.full_name,
            "department": dept or "No department",
            "report_title": "AI-Generated Weekly Performance Report",
            "period": f"{date_start} - {date_end}",
            "performance_rating": report_data.get("performance_rating", "Evaluating"),
            "summary": report_data.get("summary", "Report processing..."),
            "highlights": report_data.get("highlights", []),
            "focus_areas": report_data.get("focus_areas", []),
            "coaching_tips": report_data.get("coaching_tips", []),
            "action_items": report_data.get("action_items", []),
            "motivational_message": report_data.get("motivational_message", ""),
            "metrics": {
                "avg_active_hours": avg_active_hours,
                "avg_focus_hours": avg_focus_hours,
                "productivity_score": avg_productivity,
                "anomalies": anomaly_count,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        log.error("weekly_report_error", employee_id=str(employee_id), error=str(e), exc_info=True)
        return {
            "employee_id": str(employee_id),
            "employee_name": employee.full_name,
            "report_title": "Weekly Performance Report",
            "period": f"{date_start} - {date_end}",
            "performance_rating": "Data Available",
            "summary": f"Performance data available. Avg productivity: {avg_productivity}%, Active hours: {avg_active_hours}h/day, Focus: {avg_focus_hours}h/day",
            "highlights": ["Data-driven metrics available", f"Consistent activity pattern: {avg_active_hours}h/day", f"Focus capacity: {avg_focus_hours}h/day"],
            "focus_areas": ["Enable AI coaching by ensuring continuous tracking", "Review anomalies detected this week", "Optimize app-switching patterns"],
            "coaching_tips": ["Schedule deep work blocks during peak productivity hours", "Reduce context-switching for better focus quality", "Maintain work-life balance with consistent end times"],
            "action_items": ["Review this week's activity patterns", "Plan focus blocks for next week", "Address any anomalies detected"],
            "metrics": {
                "avg_active_hours": avg_active_hours,
                "avg_focus_hours": avg_focus_hours,
                "productivity_score": avg_productivity,
                "anomalies": anomaly_count,
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }


# -- 5. Database Diagnostics

@router.get("/diagnostics/data-status")
async def get_data_status(
    db: AsyncSession = Depends(get_db),
    admin=Depends(get_current_admin),
):
    """
    Check what activity data exists in the database.
    Useful for debugging data flow issues.
    """
    today = date.today()
    week_ago = today - timedelta(days=7)

    emp_count_result = await db.execute(select(Employee).where(Employee.is_active == True))
    total_employees = len(emp_count_result.scalars().all())

    summary_count_result = await db.execute(
        select(DailySummary).where(DailySummary.date >= week_ago)
    )
    summary_records = summary_count_result.scalars().all()

    anomaly_count_result = await db.execute(
        select(AnomalyLog).where(
            AnomalyLog.detected_at >= datetime.combine(
                week_ago, datetime.min.time()
            ).replace(tzinfo=timezone.utc)
        )
    )
    anomaly_records = anomaly_count_result.scalars().all()

    # Get employees with activity
    emp_with_activity = await db.execute(
        select(Employee.full_name, Employee.id)
        .outerjoin(DailySummary)
        .where(
            (Employee.is_active == True)
            & (DailySummary.date >= week_ago)
        )
        .distinct()
    )
    employees_with_data = emp_with_activity.fetchall()

    return {
        "status": "Database Data Status",
        "total_active_employees": total_employees,
        "daily_summary_records_last_7_days": len(summary_records),
        "anomaly_records_last_7_days": len(anomaly_records),
        "employees_with_activity_data": len(employees_with_data),
        "employee_names_with_data": [row[0] for row in employees_with_data],
        "recommendation": (
            "Empty: Agent/device not sending data. Check device enrollment and agent status."
            if len(summary_records) == 0
            else "Data present. AI features ready."
        ),
    }
