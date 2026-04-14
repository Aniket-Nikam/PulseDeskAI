"""
PulseDesk Pagination Utilities

Provides consistent pagination for all list endpoints.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Generic, List, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

T = TypeVar("T")


@dataclass
class PaginatedResult(Generic[T]):
    """Service-layer pagination result."""
    items: List[T]
    total: int
    page: int
    page_size: int

    @property
    def pages(self) -> int:
        return max(1, math.ceil(self.total / self.page_size))


def clamp_pagination(page: int, page_size: int, max_page_size: int = 100) -> tuple[int, int]:
    """Sanitize page/page_size to safe ranges."""
    page = max(1, page)
    page_size = max(1, min(page_size, max_page_size))
    return page, page_size


async def paginate_query(
    db: AsyncSession,
    stmt: Select,
    *,
    page: int = 1,
    page_size: int = 50,
    max_page_size: int = 100,
) -> PaginatedResult:
    """
    Execute a SQLAlchemy select with pagination.
    Returns a PaginatedResult with items, total count, and page metadata.
    """
    page, page_size = clamp_pagination(page, page_size, max_page_size)

    # Count total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar() or 0

    # Fetch page
    offset = (page - 1) * page_size
    paginated_stmt = stmt.offset(offset).limit(page_size)
    result = await db.execute(paginated_stmt)
    items = list(result.scalars().all())

    return PaginatedResult(items=items, total=total, page=page, page_size=page_size)
