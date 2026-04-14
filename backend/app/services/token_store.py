from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Any, Dict, List, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


@dataclass
class TokenRecord:
    kind: str
    token_hash: str
    payload: Dict[str, Any]
    expires_at: datetime
    created_at: datetime = field(default_factory=_utcnow)
    consumed_at: Optional[datetime] = None

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def is_expired(self) -> bool:
        return _utcnow() >= self.expires_at


class InMemoryTokenStore:
    """
    In-memory token store for join/enrollment one-time flows.
    Replace with Redis for multi-instance production.
    """

    def __init__(self) -> None:
        self._records: Dict[str, TokenRecord] = {}
        self._lock = Lock()

    def issue(self, *, kind: str, token: str, payload: Dict[str, Any], ttl_seconds: int) -> None:
        digest = _token_hash(token)
        expires_at = _utcnow() + timedelta(seconds=max(1, ttl_seconds))
        with self._lock:
            self._records[digest] = TokenRecord(
                kind=kind,
                token_hash=digest,
                payload=payload.copy(),
                expires_at=expires_at,
            )

    def get(self, *, kind: str, token: str, allow_consumed: bool = False) -> Optional[TokenRecord]:
        digest = _token_hash(token)
        with self._lock:
            rec = self._records.get(digest)
            if not rec or rec.kind != kind:
                return None
            if rec.is_expired:
                self._records.pop(digest, None)
                return None
            if rec.is_consumed and not allow_consumed:
                return None
            return rec

    def consume(self, *, kind: str, token: str) -> bool:
        digest = _token_hash(token)
        with self._lock:
            rec = self._records.get(digest)
            if not rec or rec.kind != kind or rec.is_expired or rec.is_consumed:
                return False
            rec.consumed_at = _utcnow()
            return True

    def update_payload(self, *, kind: str, token: str, updates: Dict[str, Any]) -> bool:
        digest = _token_hash(token)
        with self._lock:
            rec = self._records.get(digest)
            if not rec or rec.kind != kind or rec.is_expired:
                return False
            rec.payload.update(updates)
            return True

    def delete(self, *, kind: str, token: str) -> None:
        digest = _token_hash(token)
        with self._lock:
            rec = self._records.get(digest)
            if rec and rec.kind == kind:
                self._records.pop(digest, None)

    def active_records(self, *, kind: str) -> List[TokenRecord]:
        now = _utcnow()
        out: List[TokenRecord] = []
        with self._lock:
            for digest, rec in list(self._records.items()):
                if rec.expires_at <= now:
                    self._records.pop(digest, None)
                    continue
                if rec.kind == kind and not rec.is_consumed:
                    out.append(rec)
        return out


token_store = InMemoryTokenStore()
