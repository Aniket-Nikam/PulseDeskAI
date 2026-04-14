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
from app.models import Employee, DailySummary, AnomalyLog, ActivityEvent
from app.api.v1.routes.auth import require_admin_read
from app.core.logging import get_logger
from app.core.files import sanitize_filename_component
from app.core.audit import log_admin_action

router = APIRouter(prefix="/reports", tags=["reports"])
log = get_logger("reports")


# ── Page dimensions ───────────────────────────────────────────────────
PAGE_W = 210
PAGE_H = 297
MARGIN_LEFT = 18
MARGIN_RIGHT = 18
CONTENT_W = PAGE_W - MARGIN_LEFT - MARGIN_RIGHT


@router.get("/pdf/{employee_id}")
async def generate_employee_pdf(
    employee_id: uuid.UUID,
    days: int = Query(default=7, ge=1, le=30),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """Generate a PDF productivity report for one employee."""
    try:
        from fpdf import FPDF  # noqa: F401
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

        # TODO: Background Task
        # PDF generation can be CPU intensive. For very large date ranges or when 
        # many concurrent users request PDFs, this will block the FastAPI worker.
        # Consider generating PDFs via Celery/Arq and returning a presigned URL 
        # or downloading later.

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
        safe_name = sanitize_filename_component(employee.full_name.replace(" ", "_"))
        filename = f"pulsedesk_{safe_name}_{datetime.now().strftime('%Y%m%d')}.pdf"
        log_admin_action(
            "employee_report_downloaded",
            admin_id=str(admin.id),
            employee_id=str(employee.id),
            days=days,
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"pdf_generation_error: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail="PDF generation failed")


@router.get("/pdf/team/all")
async def generate_team_pdf(
    days: int = Query(default=7, ge=1, le=30),
    department_id: Optional[uuid.UUID] = Query(None),
    admin=Depends(require_admin_read),
    db: AsyncSession = Depends(get_db),
):
    """Generate a team-wide PDF productivity report."""
    try:
        from fpdf import FPDF  # noqa: F401
    except ImportError:
        raise HTTPException(status_code=501, detail="Run: pip install fpdf2")

    try:
        stmt = select(Employee).where(Employee.is_active)
        if department_id:
            stmt = stmt.where(Employee.department_id == department_id)
        stmt = stmt.order_by(Employee.full_name)

        emp_result = await db.execute(stmt)
        employees = emp_result.scalars().all()

        since = datetime.now(timezone.utc) - timedelta(days=days)
        rows = []
        
        # TODO: Background Task
        # Aggregating across all employees and generating a single PDF can be
        # computationally heavy and time-consuming. This should be moved to a
        # Celery/Arq background task to avoid blocking the API worker.
        
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
        log_admin_action(
            "team_report_downloaded",
            admin_id=str(admin.id),
            days=days,
            department_id=str(department_id) if department_id else None,
        )

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"pdf_team_generation_error: {type(e).__name__}: {str(e)}")
        raise HTTPException(status_code=500, detail="PDF generation failed")


# ── Helpers ───────────────────────────────────────────────────────────

def _fmt_seconds(s: float) -> str:
    s = int(s)
    if s < 60:
        return f"{s}s"
    if s < 3600:
        return f"{s//60}m"
    return f"{s//3600}h {(s%3600)//60}m"


def _score_color(score: float):
    """Return RGB tuple for the given productivity score."""
    if score >= 75:
        return (22, 163, 74)     # green-600
    if score >= 50:
        return (202, 138, 4)     # yellow-600
    return (220, 38, 38)                     # red-600


def _score_label(score: float) -> str:
    if score >= 80:
        return "Excellent"
    if score >= 65:
        return "Good"
    if score >= 50:
        return "Average"
    return "Needs Improvement"


def _draw_header(pdf, title: str, subtitle: str):
    """Draw a professional gradient-look header banner."""
    # Dark navy banner
    pdf.set_fill_color(15, 23, 42)    # slate-900
    pdf.rect(0, 0, PAGE_W, 44, "F")
    # Accent stripe
    pdf.set_fill_color(59, 130, 246)  # blue-500
    pdf.rect(0, 44, PAGE_W, 3, "F")

    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_y(10)
    pdf.set_x(MARGIN_LEFT)
    pdf.cell(CONTENT_W, 10, title, align="L")

    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(148, 163, 184)  # slate-400
    pdf.set_y(24)
    pdf.set_x(MARGIN_LEFT)
    pdf.cell(CONTENT_W, 8, subtitle, align="L")

    # Right-side date badge
    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(203, 213, 225)  # slate-300
    pdf.set_y(14)
    pdf.set_x(MARGIN_LEFT)
    pdf.cell(CONTENT_W, 8, f"Generated {datetime.now().strftime('%B %d, %Y')}", align="R")


def _draw_footer(pdf):
    """Draw a clean footer line."""
    pdf.set_y(-22)
    pdf.set_draw_color(226, 232, 240)  # slate-200
    pdf.line(MARGIN_LEFT, pdf.get_y(), PAGE_W - MARGIN_RIGHT, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "", 7)
    pdf.set_text_color(148, 163, 184)
    pdf.set_x(MARGIN_LEFT)
    pdf.cell(CONTENT_W / 2, 5, "PulseDesk - Employee Monitoring & Productivity", align="L")
    pdf.cell(CONTENT_W / 2, 5, f"Page {pdf.page_no()}", align="R")


def _draw_section_title(pdf, title: str, y_offset: float = 0):
    """Draw a section header with a small accent bar."""
    if y_offset:
        pdf.ln(y_offset)
    pdf.set_font("Helvetica", "B", 13)
    pdf.set_text_color(15, 23, 42)     # slate-900
    pdf.set_x(MARGIN_LEFT)
    # Accent dot
    pdf.set_fill_color(59, 130, 246)
    dot_y = pdf.get_y() + 4
    pdf.rect(MARGIN_LEFT, dot_y, 3, 3, "F")
    pdf.set_x(MARGIN_LEFT + 8)
    pdf.cell(CONTENT_W - 8, 10, title)
    pdf.ln(12)


def _draw_stat_card(pdf, x, y, w, h, label, value, color_rgb=None):
    """Draw a single stat card with rounded-look background."""
    # Card background
    pdf.set_fill_color(248, 250, 252)  # slate-50
    pdf.rect(x, y, w, h, "F")
    # Top accent line
    if color_rgb:
        pdf.set_fill_color(*color_rgb)
        pdf.rect(x, y, w, 1.5, "F")

    # Label
    pdf.set_font("Helvetica", "", 7.5)
    pdf.set_text_color(100, 116, 139)  # slate-500
    pdf.set_xy(x + 6, y + 5)
    pdf.cell(w - 12, 4, label.upper())

    # Value
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(15, 23, 42)     # slate-900
    if color_rgb:
        pdf.set_text_color(*color_rgb)
    pdf.set_xy(x + 6, y + 12)
    pdf.cell(w - 12, 8, str(value))


# ── Employee PDF ─────────────────────────────────────────────────────

def _build_employee_pdf(employee, summaries, top_apps, avg_score,
                         total_active_seconds, total_focus_sessions, anomaly_count, days):
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(MARGIN_LEFT, 20, MARGIN_RIGHT)
    pdf.set_auto_page_break(auto=True, margin=28)

    # ── Header ─────────────────────────────────────────────────────
    _draw_header(pdf, "Employee Productivity Report", f"PulseDesk Analytics - Last {days} days")

    # ── Employee Identity ──────────────────────────────────────────
    pdf.set_y(56)
    pdf.set_x(MARGIN_LEFT)

    # Name
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(CONTENT_W, 10, employee.full_name, ln=True)

    pdf.set_x(MARGIN_LEFT)
    pdf.set_font("Helvetica", "", 10)
    pdf.set_text_color(100, 116, 139)
    pdf.cell(CONTENT_W, 6, f"{employee.email}  |  Report period: Last {days} days", ln=True)
    pdf.ln(10)

    # ── Stat Cards Row ─────────────────────────────────────────────
    card_y = pdf.get_y()
    card_h = 28
    card_gap = 5
    card_w = (CONTENT_W - 3 * card_gap) / 4

    r, g, b = _score_color(avg_score)
    _draw_stat_card(pdf, MARGIN_LEFT,                           card_y, card_w, card_h, "Avg Score",      f"{avg_score:.0f}%", (r, g, b))
    _draw_stat_card(pdf, MARGIN_LEFT + card_w + card_gap,       card_y, card_w, card_h, "Active Time",     _fmt_seconds(total_active_seconds), (59, 130, 246))
    _draw_stat_card(pdf, MARGIN_LEFT + 2 * (card_w + card_gap), card_y, card_w, card_h, "Focus Sessions",  str(total_focus_sessions), (139, 92, 246))
    _draw_stat_card(pdf, MARGIN_LEFT + 3 * (card_w + card_gap), card_y, card_w, card_h, "Anomalies",       str(anomaly_count), (234, 88, 12))

    pdf.set_y(card_y + card_h + 4)

    # ── Score Rating ───────────────────────────────────────────────
    pdf.ln(2)
    pdf.set_x(MARGIN_LEFT)
    pdf.set_fill_color(r, g, b)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", "B", 9)
    label = _score_label(avg_score)
    label_w = pdf.get_string_width(label) + 12
    pdf.cell(label_w, 7, f"  {label}  ", fill=True)
    pdf.set_text_color(100, 116, 139)
    pdf.set_font("Helvetica", "", 9)
    pdf.cell(60, 7, f"  Productivity rating based on {len(summaries)} tracked day(s)")
    pdf.ln(14)

    # ── Daily Breakdown Table ──────────────────────────────────────
    if summaries:
        _draw_section_title(pdf, "Daily Breakdown")
        pdf.set_x(MARGIN_LEFT)

        col_widths = [36, 36, 28, 28, 24, CONTENT_W - 36 - 36 - 28 - 28 - 24]
        headers = ["Date", "Active Time", "Score", "Focus", "Anomalies", "Category"]

        # Table header
        pdf.set_fill_color(241, 245, 249)  # slate-100
        pdf.set_font("Helvetica", "B", 8)
        pdf.set_text_color(71, 85, 105)     # slate-600
        for i, (h, w) in enumerate(zip(headers, col_widths)):
            pdf.cell(w, 8, h, border=0, fill=True, align="L" if i == 0 else "C")
        pdf.ln()

        # Divider line
        pdf.set_draw_color(226, 232, 240)
        pdf.line(MARGIN_LEFT, pdf.get_y(), PAGE_W - MARGIN_RIGHT, pdf.get_y())

        # Table rows
        pdf.set_font("Helvetica", "", 8.5)
        for i, s in enumerate(summaries[:14]):
            try:
                if pdf.get_y() > PAGE_H - 40:
                    pdf.add_page()
                    pdf.set_y(20)

                fill = i % 2 == 0
                pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
                pdf.set_text_color(30, 41, 59)  # slate-800

                date_str = s.date.strftime("%b %d, %Y") if hasattr(s.date, "strftime") else str(s.date)[:10]
                score_val = float(s.productivity_score or 0)
                r2, g2, b2 = _score_color(score_val)

                pdf.set_x(MARGIN_LEFT)
                pdf.cell(col_widths[0], 7, date_str, fill=fill)
                pdf.cell(col_widths[1], 7, _fmt_seconds(int(s.active_seconds or 0)), fill=fill, align="C")

                # Score with color
                pdf.set_text_color(r2, g2, b2)
                pdf.set_font("Helvetica", "B", 8.5)
                pdf.cell(col_widths[2], 7, f"{score_val:.0f}%", fill=fill, align="C")
                pdf.set_font("Helvetica", "", 8.5)
                pdf.set_text_color(30, 41, 59)

                pdf.cell(col_widths[3], 7, str(int(s.focus_sessions or 0)), fill=fill, align="C")
                pdf.cell(col_widths[4], 7, str(int(s.anomaly_count or 0)), fill=fill, align="C")
                category = str(s.top_category or "-")[:18]
                pdf.cell(col_widths[5], 7, category, fill=fill, align="C")
                pdf.ln()
            except Exception as e:
                log.warning(f"Error adding summary row to PDF: {e}")
                continue

        # Bottom border
        pdf.set_draw_color(226, 232, 240)
        pdf.line(MARGIN_LEFT, pdf.get_y(), PAGE_W - MARGIN_RIGHT, pdf.get_y())
        pdf.ln(8)

    # ── Top Applications ──────────────────────────────────────────
    if top_apps:
        if pdf.get_y() > PAGE_H - 80:
            pdf.add_page()
            pdf.set_y(20)

        _draw_section_title(pdf, "Top Applications")
        total_secs = sum(int(r.total or 0) for r in top_apps)

        for i, app in enumerate(top_apps):
            try:
                if pdf.get_y() > PAGE_H - 35:
                    pdf.add_page()
                    pdf.set_y(20)

                pct = (int(app.total or 0) / total_secs * 100) if total_secs > 0 else 0
                app_name = str(app.active_app or "Unknown")[:35]
                time_str = _fmt_seconds(int(app.total or 0))

                row_y = pdf.get_y()
                bar_max_w = CONTENT_W * 0.38
                bar_w = max(2, bar_max_w * (pct / 100))

                # Rank number
                pdf.set_x(MARGIN_LEFT)
                pdf.set_font("Helvetica", "B", 9)
                pdf.set_text_color(148, 163, 184)
                pdf.cell(10, 9, f"{i + 1}.")

                # App name
                pdf.set_font("Helvetica", "", 9.5)
                pdf.set_text_color(30, 41, 59)
                pdf.cell(60, 9, app_name)

                # Time
                pdf.set_font("Helvetica", "", 8.5)
                pdf.set_text_color(100, 116, 139)
                pdf.cell(28, 9, time_str, align="R")

                # Progress bar
                bar_x = pdf.get_x() + 6
                bar_y = row_y + 3
                # Background track
                pdf.set_fill_color(241, 245, 249)
                pdf.rect(bar_x, bar_y, bar_max_w, 4, "F")
                # Filled bar
                pdf.set_fill_color(59, 130, 246)
                pdf.rect(bar_x, bar_y, bar_w, 4, "F")

                # Percentage text
                pdf.set_xy(bar_x + bar_max_w + 4, row_y)
                pdf.set_font("Helvetica", "B", 8.5)
                pdf.set_text_color(59, 130, 246)
                pdf.cell(20, 9, f"{pct:.1f}%")
                pdf.ln()
            except Exception as e:
                log.warning(f"Error adding app to PDF: {e}")
                continue

    # ── Footer ─────────────────────────────────────────────────────
    _draw_footer(pdf)

    return pdf


# ── Team PDF ─────────────────────────────────────────────────────────

def _build_team_pdf(rows, days):
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_margins(MARGIN_LEFT, 20, MARGIN_RIGHT)
    pdf.set_auto_page_break(auto=True, margin=28)

    # Header
    _draw_header(pdf, "Team Productivity Report", f"PulseDesk Analytics - Last {days} days")

    # Summary cards
    pdf.set_y(56)
    total_employees = len(rows)
    avg_team_score = sum(r["avg_score"] for r in rows) / max(total_employees, 1)
    total_anomalies = sum(r["anomalies"] for r in rows)
    avg_active = sum(r["avg_active_hours"] for r in rows) / max(total_employees, 1)

    card_y = pdf.get_y()
    card_h = 28
    card_gap = 5
    card_w = (CONTENT_W - 3 * card_gap) / 4

    r, g, b = _score_color(avg_team_score)
    _draw_stat_card(pdf, MARGIN_LEFT, card_y, card_w, card_h,
                    "Team Avg Score", f"{avg_team_score:.0f}%", (r, g, b))
    _draw_stat_card(pdf, MARGIN_LEFT + card_w + card_gap, card_y, card_w, card_h,
                    "Total Employees", str(total_employees), (59, 130, 246))
    _draw_stat_card(pdf, MARGIN_LEFT + 2 * (card_w + card_gap), card_y, card_w, card_h,
                    "Avg Active/Day", f"{avg_active:.1f}h", (139, 92, 246))
    _draw_stat_card(pdf, MARGIN_LEFT + 3 * (card_w + card_gap), card_y, card_w, card_h,
                    "Total Anomalies", str(total_anomalies), (234, 88, 12))

    pdf.set_y(card_y + card_h + 10)

    # ── Employee Ranking Table ─────────────────────────────────────
    _draw_section_title(pdf, f"Employee Rankings - {total_employees} Members")
    pdf.set_x(MARGIN_LEFT)

    col_widths = [14, 60, 28, 28, 24, 24]
    headers = ["#", "Employee", "Avg Score", "Active/Day", "Focus", "Anomalies"]

    # Table header
    pdf.set_fill_color(15, 23, 42)  # slate-900
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_text_color(255, 255, 255)
    for i, (h, w) in enumerate(zip(headers, col_widths)):
        pdf.cell(w, 8, h, fill=True, align="L" if i == 1 else "C")
    pdf.ln()

    # Table rows
    pdf.set_font("Helvetica", "", 8.5)
    for i, row in enumerate(rows):
        if pdf.get_y() > PAGE_H - 35:
            pdf.add_page()
            pdf.set_y(20)
            # Re-draw header row on new page
            pdf.set_x(MARGIN_LEFT)
            pdf.set_fill_color(15, 23, 42)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(255, 255, 255)
            for h_i, (h, w) in enumerate(zip(headers, col_widths)):
                pdf.cell(w, 8, h, fill=True, align="L" if h_i == 1 else "C")
            pdf.ln()
            pdf.set_font("Helvetica", "", 8.5)

        fill = i % 2 == 0
        pdf.set_fill_color(248, 250, 252) if fill else pdf.set_fill_color(255, 255, 255)
        r, g, b = _score_color(row["avg_score"])

        pdf.set_x(MARGIN_LEFT)

        # Rank
        pdf.set_text_color(148, 163, 184)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(col_widths[0], 7, str(i + 1), fill=fill, align="C")

        # Name
        pdf.set_text_color(30, 41, 59)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.cell(col_widths[1], 7, row["name"][:28], fill=fill, align="L")

        # Score (colored)
        pdf.set_text_color(r, g, b)
        pdf.set_font("Helvetica", "B", 8.5)
        pdf.cell(col_widths[2], 7, f"{row['avg_score']:.0f}%", fill=fill, align="C")

        # Active hours
        pdf.set_text_color(30, 41, 59)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.cell(col_widths[3], 7, f"{row['avg_active_hours']:.1f}h", fill=fill, align="C")

        # Focus
        pdf.cell(col_widths[4], 7, str(row["focus_sessions"]), fill=fill, align="C")

        # Anomalies
        anom = row["anomalies"]
        if anom > 0:
            pdf.set_text_color(234, 88, 12)
        pdf.cell(col_widths[5], 7, str(anom), fill=fill, align="C")
        pdf.set_text_color(30, 41, 59)
        pdf.ln()

    # Bottom border
    pdf.set_draw_color(226, 232, 240)
    pdf.line(MARGIN_LEFT, pdf.get_y(), PAGE_W - MARGIN_RIGHT, pdf.get_y())

    # Footer
    _draw_footer(pdf)

    return pdf
