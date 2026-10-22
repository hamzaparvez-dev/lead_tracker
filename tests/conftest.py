from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def isolated_store(monkeypatch: pytest.MonkeyPatch):
    """Fresh in-memory store and no live LLM calls during tests."""
    main.reset_store()
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    yield
    main.reset_store()


@pytest.fixture
def client() -> TestClient:
    return TestClient(main.app)


@pytest.fixture
def fixture_events() -> list[dict]:
    """Official interview fixture payloads E1–E6 in order."""
    return [
        {
            "event_id": "w-101",
            "source": "website",
            "data": {
                "full_name": "Rohit Sharma",
                "phone": "+91 98765 00011",
                "email": "rohit@greenleaf.in",
                "message": "Need Google Ads for our D2C brand, budget 1.5L/month",
            },
        },
        {
            "event_id": "fb-201",
            "source": "facebook",
            "data": {
                "field_data": [
                    {"name": "full_name", "values": ["Sneha Patil"]},
                    {"name": "phone_number", "values": ["9876500022"]},
                    {"name": "what_service_do_you_need", "values": ["Website for dental clinic"]},
                ]
            },
        },
        {
            "event_id": "wa-301",
            "source": "whatsapp",
            "data": {
                "from": "919876500033",
                "profile_name": "Anil",
                "text": "Hi, social media management chahiye real estate project ke liye",
            },
        },
        {
            "event_id": "w-101",
            "source": "website",
            "data": {
                "full_name": "Rohit Sharma",
                "phone": "+91 98765 00011",
                "email": "rohit@greenleaf.in",
                "message": "Need Google Ads for our D2C brand, budget 1.5L/month",
            },
        },
        {
            "event_id": "wa-302",
            "source": "whatsapp",
            "data": {
                "from": "919876500011",
                "profile_name": "Rohit",
                "text": "Any update on my Google Ads query?",
            },
        },
        {
            "event_id": "fb-202",
            "source": "facebook",
            "data": {
                "field_data": [
                    {"name": "full_name", "values": ["Priya Nair"]},
                    {"name": "phone_number", "values": ["09876500044"]},
                    {"name": "what_service_do_you_need", "values": ["AI chatbot for our hospital"]},
                ]
            },
        },
    ]
