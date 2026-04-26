from __future__ import annotations

import hashlib
import time
from collections import deque
from threading import Lock
from typing import Deque, Dict

from fastapi import HTTPException, Request


class InMemoryRateLimiter:
    """
    Lightweight in-memory sliding-window limiter.
    For multi-instance deployments, move this to Redis.
    """

    def __init__(self) -> None:
        self._buckets: Dict[str, Deque[float]] = {}
        self._lock = Lock()

    def allow(self, key: str, *, limit: int, window_seconds: int) -> tuple[bool, int]:
        now = time.time()
        window_start = now - window_seconds

        with self._lock:
            bucket = self._buckets.setdefault(key, deque())
            while bucket and bucket[0] < window_start:
                bucket.popleft()

            if len(bucket) >= limit:
                retry_after = max(1, int(window_seconds - (now - bucket[0])))
                return False, retry_after

            bucket.append(now)
            return True, 0


limiter = InMemoryRateLimiter()


def _anonymize(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").strip()
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


def enforce_rate_limit(
    request: Request,
    *,
    key_prefix: str,
    limit: int,
    window_seconds: int = 60,
    include_auth_fingerprint: bool = False,
    custom_identifier: str | None = None,
) -> None:
    parts = [key_prefix, _client_ip(request), request.url.path]

    if include_auth_fingerprint:
        auth = request.headers.get("authorization", "")
        if auth:
            parts.append(_anonymize(auth))
    if custom_identifier:
        parts.append(_anonymize(custom_identifier))

    allowed, retry_after = limiter.allow("|".join(parts), limit=limit, window_seconds=window_seconds)
    if not allowed:
        raise HTTPException(
            status_code=429,
            detail="Too many requests. Please retry shortly.",
            headers={"Retry-After": str(retry_after)},
        )
