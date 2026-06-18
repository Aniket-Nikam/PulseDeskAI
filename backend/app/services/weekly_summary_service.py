import asyncio
import json
from datetime import datetime, date, time, timedelta, timezone
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.models import WeeklySummary, DailySummary, AnomalyLog, Employee
from app.core.config import settings
from app.core.logging import get_logger
from app.ai.providers.factory import get_active_provider

log = get_logger("weekly_summaries")

SYSTEM_PROMPT = """You are an expert team productivity analyst.
Analyze the given team productivity metrics and anomalies for a week and write a concise, professional, and actionable management report.
The report must be in Markdown format and include these sections:
1. ## Highlights (Key positive trends, high productivity, etc.)
2. ## Key Concerns (Low productivity, excessive idle, frequent anomalies, etc.)
3. ## Security & Anomaly Assessment (Review of anomalies detected)
4. ## Recommended Action Items (Concrete steps for the manager to take)

Do not include introduction, signatures or greeting. Focus strictly on data-driven observations."""

async def generate_weekly_summary(
    week_start: datetime,
    week_end: datetime,
    db: AsyncSession
) -> Optional[WeeklySummary]:
    """
    Query, aggregate, and generate a WeeklySummary using Groq LLM.
    """
    try:
        # 1. Fetch daily summaries
        result = await db.execute(
            select(DailySummary, Employee.full_name)
            .join(Employee, DailySummary.employee_id == Employee.id)
            .where(DailySummary.date >= week_start, DailySummary.date <= week_end)
        )
        rows = result.all()

        if not rows:
            log.info("no_data_for_weekly_summary", start=week_start.isoformat(), end=week_end.isoformat())
            return None

        # Aggregate stats
        total_tracked = 0
        total_active = 0
        total_idle = 0
        total_focus = 0
        prod_score_sum = 0.0
        anomalies_count = 0
        employee_stats = {}

        for summary, emp_name in rows:
            total_tracked += summary.total_tracked_seconds
            total_active += summary.active_seconds
            total_idle += summary.idle_seconds
            total_focus += getattr(summary, "focus_seconds", 0) or 0
            prod_score_sum += summary.productivity_score
            anomalies_count += summary.anomaly_count

            if emp_name not in employee_stats:
                employee_stats[emp_name] = {"active": 0, "idle": 0, "prod_score_sum": 0.0, "days": 0, "anomalies": 0}
            employee_stats[emp_name]["active"] += summary.active_seconds
            employee_stats[emp_name]["idle"] += summary.idle_seconds
            employee_stats[emp_name]["prod_score_sum"] += summary.productivity_score
            employee_stats[emp_name]["days"] += 1
            employee_stats[emp_name]["anomalies"] += summary.anomaly_count

        avg_prod = (prod_score_sum / len(rows)) if rows else 0.0

        # Compile summaries by employee
        employee_breakdown = []
        for name, stats in employee_stats.items():
            avg_p = stats["prod_score_sum"] / stats["days"]
            employee_breakdown.append({
                "name": name,
                "active_hours": round(stats["active"] / 3600, 1),
                "idle_hours": round(stats["idle"] / 3600, 1),
                "avg_productivity": round(avg_p * 100, 1),
                "anomalies": stats["anomalies"]
            })

        # 2. Fetch anomalies
        anomalies_result = await db.execute(
            select(AnomalyLog, Employee.full_name)
            .join(Employee, AnomalyLog.employee_id == Employee.id)
            .where(AnomalyLog.detected_at >= week_start, AnomalyLog.detected_at <= week_end)
            .order_by(AnomalyLog.detected_at.desc())
            .limit(30)
        )
        anomalies_rows = anomalies_result.all()
        anomalies_list = [
            {
                "employee": emp_name,
                "type": row.anomaly_type.value if hasattr(row.anomaly_type, "value") else str(row.anomaly_type),
                "description": row.description,
                "detected_at": row.detected_at.strftime("%Y-%m-%d %H:%M")
            }
            for row, emp_name in anomalies_rows
        ]

        metrics = {
            "total_tracked_hours": round(total_tracked / 3600, 1),
            "total_active_hours": round(total_active / 3600, 1),
            "total_idle_hours": round(total_idle / 3600, 1),
            "total_focus_hours": round(total_focus / 3600, 1),
            "avg_productivity_score": round(avg_prod * 100, 1),
            "total_anomalies": anomalies_count,
            "employee_breakdown": employee_breakdown,
            "recent_anomalies_sample": anomalies_list
        }

        # Generate report text using AI
        report_text = ""
        if settings.AI_ENABLED:
            try:
                provider = get_active_provider()
                prompt = f"""
                Week Range: {week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}
                Team Aggregates:
                - Total Active Hours: {metrics['total_active_hours']}
                - Total Idle Hours: {metrics['total_idle_hours']}
                - Average Team Productivity Score: {metrics['avg_productivity_score']}%
                - Total Anomalies: {metrics['total_anomalies']}
                
                Employee Details:
                {json.dumps(employee_breakdown, indent=2)}

                Recent Anomalies:
                {json.dumps(anomalies_list, indent=2)}
                """
                report_text = await provider.generate_text(
                    messages=[{"role": "user", "content": prompt}],
                    system_prompt=SYSTEM_PROMPT,
                    temperature=0.3,
                    max_tokens=1500
                )
            except Exception as e:
                log.warning("weekly_summary_ai_generation_failed", error=str(e))

        # Fallback heuristic summary
        if not report_text:
            report_text = f"""## Highlights
* The team tracked a total of {metrics['total_active_hours']} active hours this week.
* Average team productivity score was {metrics['avg_productivity_score']}%.

## Key Concerns
* Total idle time accumulated was {metrics['total_idle_hours']} hours.
* Ensure employees with low productivity or high anomalies are supported.

## Security & Anomaly Assessment
* A total of {metrics['total_anomalies']} anomalies were logged. Please review the security log for details.

## Recommended Action Items
1. Review individual daily timelines for the team.
2. Conduct wellness/support check-ins if high idle durations persist.
3. Investigate the logged anomalies in detail.
"""

        # Save to database
        # Check if weekly summary already exists for this start date
        exist_res = await db.execute(select(WeeklySummary).where(WeeklySummary.week_start == week_start))
        summary = exist_res.scalar_one_or_none()

        if not summary:
            summary = WeeklySummary(
                week_start=week_start,
                week_end=week_end,
                summary_text=report_text,
                metrics_json=metrics
            )
            db.add(summary)
        else:
            summary.summary_text = report_text
            summary.metrics_json = metrics

        await db.commit()
        await db.refresh(summary)
        log.info("weekly_summary_saved", id=str(summary.id), start=week_start.isoformat())
        return summary

    except Exception as e:
        log.error("generate_weekly_summary_failed", error=str(e))
        await db.rollback()
        return None

async def weekly_summary_scheduler_loop():
    """
    Checks daily if a weekly report has been generated for the previous completed week.
    """
    log.info("weekly_summary_scheduler_loop_started")
    while True:
        try:
            # Check previous week (Monday to Sunday)
            today = date.today()
            # If today is Monday (weekday == 0), the previous week was from today - 7 to today - 1
            # To be general: let's calculate the start of the previous week (last Monday)
            last_monday = today - timedelta(days=today.weekday() + 7)
            last_sunday = last_monday + timedelta(days=6)

            week_start = datetime.combine(last_monday, time.min, tzinfo=timezone.utc)
            week_end = datetime.combine(last_sunday, time.max, tzinfo=timezone.utc)

            async with AsyncSessionLocal() as db:
                # Check if already generated
                result = await db.execute(select(WeeklySummary).where(WeeklySummary.week_start == week_start))
                existing = result.scalar_one_or_none()

                if not existing:
                    log.info("triggering_automated_weekly_summary", start=week_start.isoformat())
                    await generate_weekly_summary(week_start, week_end, db)

        except Exception as e:
            log.error("weekly_summary_scheduler_loop_error", error=str(e))

        # Check once every 24 hours (86400 seconds)
        await asyncio.sleep(86400)

def start_weekly_summary_scheduler():
    """
    Starts the weekly summary background scheduler task.
    """
    loop = asyncio.get_event_loop()
    loop.create_task(weekly_summary_scheduler_loop())
