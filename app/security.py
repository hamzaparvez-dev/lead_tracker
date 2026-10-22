from __future__ import annotations

import hashlib
import hmac

from fastapi import HTTPException

from app.config import get_settings


def verify_webhook_signature(signature: str | None, payload: bytes) -> None:
    secret = get_settings().webhook_secret
    if not secret:
        return
    if not signature:
        raise HTTPException(status_code=401, detail="Missing X-Webhook-Signature")
    expected = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    provided = signature.removeprefix("sha256=").strip()
    if not hmac.compare_digest(provided, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook signature")
