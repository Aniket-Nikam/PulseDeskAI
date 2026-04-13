"""
PDF report generator.
Produces a clean, professional PDF report for an employee or entire team.
Uses only stdlib + fpdf2 (lightweight, no headless browser needed).
"""

import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db.session import get_db
from app.models import Employee, DailySummary, AnomalyLog, Department, ActivityEvent
from app.api.v1.routes.auth import get_current_admin
from app.core.logging import get_logger

router = APIRouter(prefix="/reports", tags=["reports"])
log = get_logger("reports")


@router.get("/pdf/{employee_id}")
async def generate_employee_pdf(
    employee_id: uuid.UUID,
    days: int = Query(default=7, ge=1, le=30),
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Generate a PDF productivity report for one employee."""
    try:
        from fpdf import FPDF
    except ImportError as e:
        log.error(f"fpdf2_import_failed: {e}")
        raise HTTPException(
            status_code=501,
            detail="PDF generation requires fpdf2. Run: pip install fpdf2"
        )

    try:
        result = await db.execute(select(Employee).where(Employee.id == employee_id))
        employee = result.scalar_one_or_none()
        if not employee:
            raise HTTPException(status_code=404, detail="Employee not found")

        since = datetime.now(timezone.utc) - timedelta(days=days)

        summaries_result = await db.execute(
            select(DailySummary)
            .where(DailySummary.employee_id == employee_id, DailySummary.date >= since)
            .order_by(DailySummary.date.desc())
        )
        summaries = summaries_result.scalars().all()

        anomalies_result = await db.execute(
            select(func.count(AnomalyLog.id)).where(
                AnomalyLog.employee_id == employee_id,
                AnomalyLog.detected_at >= since,
            )
        )
        anomaly_count = anomalies_result.scalar() or 0

        top_app_result = await db.execute(
            select(ActivityEvent.active_app, func.sum(ActivityEvent.sample_duration_seconds).label("total"))
            .where(ActivityEvent.employee_id == employee_id, ActivityEvent.timestamp >= since, ActivityEvent.active_app.isnot(None))
            .group_by(ActivityEvent.active_app)
            .order_by(func.sum(ActivityEvent.sample_duration_seconds).desc())
            .limit(5)
        )
        top_apps = top_app_result.all()

        avg_score = sum(s.productivity_score for s in summaries) / len(summaries) if summaries else 0
        total_active = sum(s.active_seconds for s in summaries)
        total_focus = sum(s.focus_sessions for s in summaries)

        pdf = _build_employee_pdf(
            employee=employee,
            summaries=summaries,
            top_apps=top_apps,
            avg_score=avg_score,
            total_active_seconds=total_active,
            total_focus_sessions=total_focus,
            anomaly_count=anomaly_count,
            days=days,
        )

        pdf_bytes = bytes(pdf.output())
        filename = f"pulsedesk_{employee.full_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        log.error(f"pdf_generation_error: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


@router.get("/pdf/team/all")
async def generate_team_pdf(
    days: int = Query(default=7, ge=1, le=30),
    department_id: Optional[uuid.UUID] = Query(None),
    admin=Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
):
    """Generate a team-wide PDF productivity report."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise HTTPException(status_code=501, detail="Run: pip install fpdf2")

    try:
        stmt = select(Employee).where(Employee.is_active == True)
        if department_id:
            stmt = stmt.where(Employee.department_id == department_id)
        stmt = stmt.order_by(Employee.full_name)

        emp_result = await db.execute(stmt)
        employees = emp_result.scalars().all()

        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = []
        for emp in employees:
            s_result = await db.execute(
                select(
                    func.avg(DailySummary.productivity_score).label("avg_score"),
                    func.avg(DailySummary.active_seconds).label("avg_active"),
                    func.sum(DailySummary.focus_sessions).label("focus"),
                    func.count(DailySummary.id).label("days_tracked"),
                ).where(DailySummary.employee_id == emp.id, DailySummary.date >= since)
            )
            agg = s_result.one()
            a_result = await db.execute(
                select(func.count(AnomalyLog.id)).where(
                    AnomalyLog.employee_id == emp.id, AnomalyLog.detected_at >= since
                )
            )
            rows.append({
                "name": emp.full_name,
                "email": emp.email,
                "avg_score": float(agg.avg_score or 0),
                "avg_active_hours": float(agg.avg_active or 0) / 3600,
                "focus_sessions": int(agg.focus or 0),
                "days_tracked": int(agg.days_tracked or 0),
                "anomalies": int(a_result.scalar() or 0),
            })

        rows.sort(key=lambda r: r["avg_score"], reverse=True)
        pdf = _build_team_pdf(rows=rows, days=days)
        pdf_bytes = bytes(pdf.output())
        filename = f"pulsedesk_team_report_{datetime.now().strftime('%Y%m%d')}.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except Exception as e:
        log.error(f"pdf_team_generation_error: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")


def _fmt_seconds(s: float) -> str:
    s = int(s)
    if s < 60: return f"{s}s"
    if s < 3600: return f"{s//60}m"
    return f"{s//3600}h {(s%3600)//60}m"


def _score_color(score: float):
    if score >= 75: return (34, 139, 34)
    if score >= 50: return (218, 165, 32)
    return (178, 34, 34)


def _build_employee_pdf(employee, summaries, top_apps, avg_score,
                         total_active_seconds, total_focus_sessions, anomaly_count, days):
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    # Header
    pdf.set_fill_color(37, 99, 235)
    pdf.rect(0, 0, 210, 40, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_y(12)
    pdf.cell(0, 10, "PulseDesk Productivity Report", align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_y(26)
    pdf.cell(0, 8, f"Generated {datetime.now().strftime('%B %d, %Y')}", align="C")

    pdf.set_y(50)
    pdf.set_text_color(26, 26, 24)

    # Employee info
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, employee.full_name, ln=True)
    pdf.set_font("Helvetica", "", 11)
    pdf.set_text_color(82, 82, 78)
    pdf.cell(0, 6, f"{employee.email}  |  Last {days} days", ln=True)
    pdf.ln(8)

    # Score box
    r, g, b = _score_color(avg_score)
    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 28)
    pdf.cell(50, 20, f"{avg_score:.0f}%", border=0, fill=True, align="C")
    pdf.set_font("Helvetica", "", 10)
    pdf.cell(0, 20, "  Average productivity score", border=0)
    pdf.ln(8)

    # Stats row
    pdf.set_text_color(26, 26, 24)
    stats = [
        ("Days tracked", str(len(summaries))),
        ("Total active time", _fmt_seconds(total_active_seconds)),
        ("Focus sessions", str(total_focus_sessions)),
        ("Anomalies", str(anomaly_count)),
    ]
    
    # Stats labels
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(130, 130, 126)
    pdf.set_fill_color(240, 240, 239)
    for i, (label, _) in enumerate(stats):
        pdf.cell(50, 6, label, ln=(i == 3), fill=True)
    
    # Stats values
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(26, 26, 24)
    for i, (_, value) in enumerate(stats):
        pdf.cell(50, 8, str(value), ln=(i == 3))
    pdf.ln(6)

    # Daily summary table
    if summaries:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(26, 26, 24)
        pdf.cell(0, 8, "Daily Breakdown", ln=True)
        pdf.ln(2)

        headers = ["Date", "Active time", "Score", "Focus", "Anomalies"]
        widths = [40, 40, 30, 30, 30]
        pdf.set_fill_color(245, 245, 244)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(130, 130, 126)
        for h, w in zip(headers, widths):
            pdf.cell(w, 7, h, border="B", fill=True)
        pdf.ln()

        pdf.set_font("Helvetica", "", 9)
        for i, s in enumerate(summaries[:14]):
            try:
                fill = i % 2 == 0
                pdf.set_fill_color(252, 252, 251) if fill else pdf.set_fill_color(255, 255, 255)
                pdf.set_text_color(26, 26, 24)
                date_str = s.date.strftime("%b %d") if hasattr(s.date, "strftime") else str(s.date)[:10]
                row = [
                    date_str,
                    _fmt_seconds(int(s.active_seconds or 0)),
                    f"{float(s.productivity_score or 0):.0f}%",
                    str(int(s.focus_sessions or 0)),
                    str(int(s.anomaly_count or 0)),
                ]
                for val, w in zip(row, widths):
                    pdf.cell(w, 6, str(val)[:25], fill=fill)
                pdf.ln()
            except Exception as e:
                log.warning(f"Error adding summary row to PDF: {e}")
                continue
        pdf.ln(8)

    # Top apps
    if top_apps:
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(26, 26, 24)
        pdf.cell(0, 8, "Top Applications", ln=True)
        pdf.ln(2)
        total_secs = sum(int(r.total or 0) for r in top_apps)
        for app in top_apps:
            try:
                pct = (int(app.total or 0) / total_secs * 100) if total_secs > 0 else 0
                pdf.set_font("Helvetica", "", 10)
                pdf.set_text_color(26, 26, 24)
                app_name = str(app.active_app or "Unknown")[:50]
                pdf.cell(80, 6, app_name)
                pdf.cell(30, 6, _fmt_seconds(int(app.total or 0)))
                pdf.set_fill_color(37, 99, 235)
                bar_w = max(1, int(pct * 0.6))
                pdf.rect(pdf.get_x(), pdf.get_y() + 2, bar_w, 3, "F")
                pdf.cell(80, 6, f"  {pct:.1f}%")
                pdf.ln()
            except Exception as e:
                log.warning(f"Error adding app to PDF: {e}")
                continue

    # Footer
    pdf.set_y(-20)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(160, 160, 156)
    pdf.cell(0, 6, "Generated by PulseDesk — Employee Monitoring & Productivity System", align="C")

    return pdf


def _build_team_pdf(rows, days):
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(20, 20, 20)

    pdf.set_fill_color(37, 99, 235)
    pdf.rect(0, 0, 210, 40, "F")
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_y(12)
    pdf.cell(0, 10, "PulseDesk Team Report", align="C")
    pdf.set_font("Helvetica", "", 11)
    pdf.set_y(26)
    pdf.cell(0, 8, f"Last {days} days  |  Generated {datetime.now().strftime('%B %d, %Y')}", align="C")

    pdf.set_y(52)
    pdf.set_text_color(26, 26, 24)
    pdf.set_font("Helvetica", "B", 14)
    pdf.cell(0, 8, f"Team Summary — {len(rows)} employees", ln=True)
    pdf.ln(4)

    headers = ["Rank", "Employee", "Avg Score", "Avg Active", "Focus", "Anomalies"]
    widths = [15, 65, 30, 30, 20, 25]

    pdf.set_fill_color(245, 245, 244)
    pdf.set_font("Helvetica", "B", 9)
    pdf.set_text_color(130, 130, 126)
    for h, w in zip(headers, widths):
        pdf.cell(w, 7, h, border="B", fill=True)
    pdf.ln()

    pdf.set_font("Helvetica", "", 9)
    for i, row in enumerate(rows):
        fill = i % 2 == 0
        pdf.set_fill_color(252, 252, 251) if fill else pdf.set_fill_color(255, 255, 255)
        r, g, b = _score_color(row["avg_score"])
        pdf.set_text_color(26, 26, 24)
        vals = [
            f"#{i+1}",
            row["name"][:28],
            f"{row['avg_score']:.0f}%",
            f"{row['avg_active_hours']:.1f}h",
            str(row["focus_sessions"]),
            str(row["anomalies"]),
        ]
        for j, (val, w) in enumerate(zip(vals, widths)):
            if j == 2:
                pdf.set_text_color(r, g, b)
            else:
                pdf.set_text_color(26, 26, 24)
            pdf.cell(w, 6, val, fill=fill)
        pdf.ln()

    pdf.set_y(-20)
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(160, 160, 156)
    pdf.cell(0, 6, "Generated by PulseDesk — Employee Monitoring & Productivity System", align="C")
    return pdf
