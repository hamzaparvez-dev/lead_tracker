from __future__ import annotations

import hashlib
import hmac
import json

import pytest
from fastapi.testclient import TestClient


def _payload_bytes(body: dict) -> bytes:
    return json.dumps(body, separators=(",", ":")).encode()


def _sign_payload(payload: bytes, secret: str) -> str:
    digest = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


class TestWebhookSignature:
    def test_no_secret_allows_request(self, client: TestClient) -> None:
        response = client.post(
            "/webhook",
            json={
                "event_id": "w-1",
                "source": "website",
                "data": {
                    "full_name": "A",
                    "phone": "9876500001",
                    "email": "a@test.com",
                    "message": "Hi",
                },
            },
        )
        assert response.status_code == 200

    def test_valid_signature(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WEBHOOK_SECRET", "test-secret")
        from app.config import get_settings

        get_settings.cache_clear()
        main = __import__("main")
        main.reset_store()

        body = {
            "event_id": "w-1",
            "source": "website",
            "data": {
                "full_name": "A",
                "phone": "9876500001",
                "email": "a@test.com",
                "message": "Hi",
            },
        }
        payload = _payload_bytes(body)
        client = TestClient(main.app)
        response = client.post(
            "/webhook",
            content=payload,
            headers={
                "Content-Type": "application/json",
                "X-Webhook-Signature": _sign_payload(payload, "test-secret"),
            },
        )
        assert response.status_code == 200
        get_settings.cache_clear()

    def test_invalid_signature_401(self, client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WEBHOOK_SECRET", "test-secret")
        from app.config import get_settings

        get_settings.cache_clear()
        main = __import__("main")
        main.reset_store()
        client = TestClient(main.app)

        body = {
            "event_id": "w-1",
            "source": "website",
            "data": {"full_name": "A", "phone": "9876500001", "message": "Hi"},
        }
        response = client.post(
            "/webhook",
            json=body,
            headers={"X-Webhook-Signature": "sha256=deadbeef"},
        )
        assert response.status_code == 401
        get_settings.cache_clear()
