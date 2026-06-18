from __future__ import annotations

import hashlib
import hmac
import time
from threading import Lock

from fastapi import HTTPException, Request

from app.core.config import settings

_nonce_lock = Lock()
_seen_nonces: dict[str, float] = {}


def _cleanup_nonces(now: float) -> None:
    cutoff = now - settings.AGENT_SIGNATURE_REPLAY_CACHE_SECONDS
    expired = [key for key, seen_at in _seen_nonces.items() if seen_at < cutoff]
    for key in expired:
        _seen_nonces.pop(key, None)


def _device_fingerprint(device_token: str) -> str:
    return hashlib.sha256(device_token.encode("utf-8")).hexdigest()[:24]


async def verify_agent_request_signature(request: Request, device_token: str) -> None:
    """
    Verify tamper-evident signatures on agent HTTP requests.

    Signature format:
      HMAC-SHA256(device_token, METHOD + path + timestamp + nonce + sha256(raw_body))
    """
    if not settings.AGENT_SIGNATURE_REQUIRED:
        return

    token = (device_token or "").strip()
    timestamp_raw = request.headers.get("x-request-timestamp", "").strip()
    nonce = request.headers.get("x-request-nonce", "").strip()
    provided = request.headers.get("x-request-signature", "").strip()

    if not token or not timestamp_raw or not nonce or not provided:
        raise HTTPException(status_code=401, detail="Signed agent request required")

    try:
        timestamp = int(timestamp_raw)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid agent request timestamp")

    now = int(time.time())
    if abs(now - timestamp) > settings.AGENT_SIGNATURE_TOLERANCE_SECONDS:
        raise HTTPException(status_code=401, detail="Agent request timestamp outside allowed window")

    if len(nonce) < 16 or len(nonce) > 128:
        raise HTTPException(status_code=401, detail="Invalid agent request nonce")

    nonce_key = f"{_device_fingerprint(token)}:{nonce}"
    with _nonce_lock:
        current = time.time()
        _cleanup_nonces(current)
        if nonce_key in _seen_nonces:
            raise HTTPException(status_code=401, detail="Replay detected")
        _seen_nonces[nonce_key] = current

    if getattr(request, "_stream_consumed", False):
        request._stream_consumed = False
    body = await request.body()
    body_hash = hashlib.sha256(body).hexdigest()
    message = "\n".join(
        [
            request.method.upper(),
            request.url.path,
            timestamp_raw,
            nonce,
            body_hash,
        ]
    )
    expected = hmac.new(token.encode("utf-8"), message.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, provided):
        raise HTTPException(status_code=401, detail="Invalid agent request signature")
