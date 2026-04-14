"""
PulseDesk Productivity Scoring Service

Consolidates all productivity score calculations into a single module.
Previously duplicated across agent.py, analytics.py, and aggregator.py.
"""

from __future__ import annotations

from typing import Sequence

from app.models import WorkSession, ActivityEvent, ActivityType
from app.services.categorizer import is_productive_category


def compute_session_score(session: WorkSession) -> float:
    """
    Compute productivity score (0-100) for a work session.
    Based on active ratio, switch frequency, and focus blocks.
    """
    active = session.active_seconds or 0
    idle = session.idle_seconds or 0
    total = max(active + idle, 1)

    active_ratio = active / total

    # Switch penalty: >60 switches/hr is very distracting
    hours = total / 3600
    switches_per_hr = (session.app_switches or 0) / max(hours, 0.1)
    switch_penalty = min(0.3, switches_per_hr / 200)

    # Focus bonus: each 25min+ focus block adds up to 15%
    focus_bonus = min(0.15, (session.focus_blocks or 0) * 0.03)

    score = (active_ratio - switch_penalty + focus_bonus) * 100
    return round(max(0.0, min(100.0, score)), 1)


def compute_score_from_events(events: Sequence[ActivityEvent]) -> float:
    """
    Compute productivity score (0-100) from a list of activity events.
    More nuanced than session score — factors in productive app usage.
    """
    if not events:
        return 0.0

    active = sum(
        e.sample_duration_seconds for e in events
        if e.activity_type == ActivityType.active
    )
    idle = sum(
        e.sample_duration_seconds for e in events
        if e.activity_type == ActivityType.idle
    )
    total = max(active + idle, 1)

    productive = sum(
        e.sample_duration_seconds for e in events
        if e.activity_type == ActivityType.active and is_productive_category(e.app_category)
    )

    active_ratio = active / total
    productive_ratio = productive / max(active, 1)

    # App switch frequency
    apps = [e.active_app for e in events if e.active_app]
    switches = sum(1 for i in range(1, len(apps)) if apps[i] != apps[i - 1])
    hours = total / 3600
    switch_penalty = min(0.25, (switches / max(hours, 0.1)) / 100)

    score = (active_ratio * 0.5 + productive_ratio * 0.4 - switch_penalty) * 100
    return round(max(0.0, min(100.0, score)), 1)
