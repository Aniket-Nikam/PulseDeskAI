"""
PulseDesk Unified Exception Hierarchy

Service-layer exceptions that route handlers translate to HTTP responses.
This decouples business logic from FastAPI's HTTPException.
"""

from __future__ import annotations

from typing import Any, Optional


class ServiceError(Exception):
    """Base for all service-layer errors."""
    status_code: int = 500
    detail: str = "Internal server error"

    def __init__(self, detail: Optional[str] = None, **context: Any) -> None:
        self.detail = detail or self.__class__.detail
        self.context = context
        super().__init__(self.detail)


class NotFoundError(ServiceError):
    status_code = 404
    detail = "Resource not found"


class ConflictError(ServiceError):
    status_code = 409
    detail = "Resource already exists"


class ValidationError(ServiceError):
    status_code = 400
    detail = "Invalid input"


class AuthorizationError(ServiceError):
    status_code = 403
    detail = "Insufficient permissions"


class RateLimitedError(ServiceError):
    status_code = 429
    detail = "Too many requests"
