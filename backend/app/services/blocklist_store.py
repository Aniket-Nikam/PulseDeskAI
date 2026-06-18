"""
Database-backed blocklist store.

Replaces the old in-memory _blocked_domains dict so that blocked site rules
persist across server restarts.  Every other module that previously imported
_blocked_domains now calls helpers from this module instead.
"""

import uuid
from typing import Any, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BlockedSiteRule
from app.core.logging import get_logger

log = get_logger("blocklist_store")


# ── Default rules seeded on first startup ────────────────────────────────────

DEFAULT_BLOCKS: list[dict[str, str]] = [
    {"domain": "facebook.com", "reason": "Social media — not work related", "category": "social", "severity": "low"},
    {"domain": "instagram.com", "reason": "Social media — not work related", "category": "social", "severity": "low"},
    {"domain": "twitter.com", "reason": "Social media — not work related", "category": "social", "severity": "low"},
    {"domain": "tiktok.com", "reason": "Social media — not work related", "category": "social", "severity": "low"},
    {"domain": "reddit.com", "reason": "Social media / forums", "category": "social", "severity": "low"},
    {"domain": "youtube.com", "reason": "Video streaming", "category": "streaming", "severity": "medium"},
    {"domain": "netflix.com", "reason": "Video streaming", "category": "streaming", "severity": "high"},
    {"domain": "twitch.tv", "reason": "Gaming / streaming", "category": "gaming", "severity": "high"},
    {"domain": "steam.com", "reason": "Gaming platform", "category": "gaming", "severity": "high"},
]


# ── Seed defaults ────────────────────────────────────────────────────────────

async def seed_default_rules(db: AsyncSession) -> int:
    """
    Insert default blocklist rules if the table is empty.
    Called once at application startup.  Returns count of rules inserted.
    """
    result = await db.execute(select(BlockedSiteRule.id).limit(1))
    if result.scalar_one_or_none() is not None:
        return 0  # Table already has data — skip seeding

    added = 0
    for block in DEFAULT_BLOCKS:
        db.add(BlockedSiteRule(
            domain=block["domain"],
            reason=block["reason"],
            category=block["category"],
            severity=block["severity"],
            applies_to_all=True,
            is_active=True,
        ))
        added += 1

    await db.commit()
    log.info(f"blocklist_defaults_seeded: {added} rules")
    return added


# ── Read helpers ─────────────────────────────────────────────────────────────

def _serialize_rule(rule: BlockedSiteRule) -> dict[str, Any]:
    """Convert a BlockedSiteRule ORM instance to the dict format the frontend expects."""
    return {
        "id": str(rule.id),
        "domain": rule.domain,
        "reason": rule.reason or "",
        "category": rule.category or "general",
        "severity": rule.severity or "medium",
        "applies_to_all": rule.applies_to_all,
        "department_id": str(rule.department_id) if rule.department_id else None,
        "employee_id": str(rule.employee_id) if rule.employee_id else None,
        "is_active": rule.is_active,
        "violation_count": rule.violation_count or 0,
        "created_at": rule.created_at.isoformat() if rule.created_at else None,
    }


async def get_all_rules(db: AsyncSession) -> List[dict[str, Any]]:
    """Return all blocked site rules (active and inactive)."""
    result = await db.execute(
        select(BlockedSiteRule).order_by(BlockedSiteRule.created_at.desc())
    )
    return [_serialize_rule(r) for r in result.scalars().all()]


async def get_active_rules(db: AsyncSession) -> List[dict[str, Any]]:
    """Return only active rules (used by anomaly detector and agent sync)."""
    result = await db.execute(
        select(BlockedSiteRule).where(BlockedSiteRule.is_active)
    )
    return [_serialize_rule(r) for r in result.scalars().all()]


async def get_active_domains(db: AsyncSession) -> List[str]:
    """Return just the domain strings for active rules (agent sync endpoint)."""
    result = await db.execute(
        select(BlockedSiteRule.domain).where(BlockedSiteRule.is_active)
    )
    return [row[0] for row in result.all()]


async def find_rule_by_domain(domain: str, db: AsyncSession) -> Optional[dict[str, Any]]:
    """Find a rule matching the given domain (normalized)."""
    normalized = _normalize_domain(domain)
    result = await db.execute(
        select(BlockedSiteRule).where(BlockedSiteRule.domain == normalized)
    )
    rule = result.scalar_one_or_none()
    return _serialize_rule(rule) if rule else None


# ── Write helpers ────────────────────────────────────────────────────────────

async def add_rule(
    *,
    domain: str,
    reason: str = "",
    category: str = "general",
    severity: str = "medium",
    applies_to_all: bool = True,
    department_id: Optional[str] = None,
    employee_id: Optional[str] = None,
    admin_id: Optional[uuid.UUID] = None,
    db: AsyncSession,
) -> dict[str, Any]:
    """Add a new blocked domain rule. Raises ValueError if domain already exists."""
    normalized = _normalize_domain(domain)

    existing = await db.execute(
        select(BlockedSiteRule).where(BlockedSiteRule.domain == normalized)
    )
    if existing.scalar_one_or_none():
        raise ValueError(f"Domain '{normalized}' is already blocked")

    rule = BlockedSiteRule(
        domain=normalized,
        reason=reason,
        category=category,
        severity=severity,
        applies_to_all=applies_to_all,
        department_id=uuid.UUID(department_id) if department_id else None,
        employee_id=uuid.UUID(employee_id) if employee_id else None,
        is_active=True,
        created_by=admin_id,
    )
    db.add(rule)
    await db.commit()
    await db.refresh(rule)
    log.info("domain_blocked_db", domain=normalized)
    return _serialize_rule(rule)


async def remove_rule(domain_id: str, db: AsyncSession) -> bool:
    """Delete a blocked domain rule by ID. Returns True if deleted."""
    result = await db.execute(
        select(BlockedSiteRule).where(BlockedSiteRule.id == uuid.UUID(domain_id))
    )
    rule = result.scalar_one_or_none()
    if not rule:
        return False
    await db.delete(rule)
    await db.commit()
    return True


async def toggle_rule(domain_id: str, db: AsyncSession) -> Optional[dict[str, Any]]:
    """Toggle is_active on a rule. Returns updated rule or None if not found."""
    result = await db.execute(
        select(BlockedSiteRule).where(BlockedSiteRule.id == uuid.UUID(domain_id))
    )
    rule = result.scalar_one_or_none()
    if not rule:
        return None
    rule.is_active = not rule.is_active
    await db.commit()
    await db.refresh(rule)
    return _serialize_rule(rule)


async def increment_violation_count(domain: str, db: AsyncSession) -> None:
    """Increment the violation count for a domain (called when a violation is reported)."""
    normalized = _normalize_domain(domain)
    await db.execute(
        update(BlockedSiteRule)
        .where(BlockedSiteRule.domain == normalized)
        .values(violation_count=BlockedSiteRule.violation_count + 1)
    )
    await db.commit()


async def load_defaults(admin_id: Optional[uuid.UUID], db: AsyncSession) -> int:
    """Load default blocks, skipping domains that already exist. Returns count added."""
    result = await db.execute(select(BlockedSiteRule.domain))
    existing = {row[0] for row in result.all()}

    added = 0
    for block in DEFAULT_BLOCKS:
        normalized = _normalize_domain(block["domain"])
        if normalized not in existing:
            db.add(BlockedSiteRule(
                domain=normalized,
                reason=block["reason"],
                category=block["category"],
                severity=block["severity"],
                applies_to_all=True,
                is_active=True,
                created_by=admin_id,
            ))
            added += 1

    if added:
        await db.commit()
    return added


# ── Domain normalization (shared) ────────────────────────────────────────────

def _normalize_domain(value: str) -> str:
    normalized = (value or "").strip().lower()
    normalized = normalized.replace("https://", "").replace("http://", "").replace("www.", "")
    return normalized.split("/", 1)[0]
