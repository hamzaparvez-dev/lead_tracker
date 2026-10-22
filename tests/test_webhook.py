from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

import main


class TestGetLeads:
    def test_get_leads_empty(self, client: TestClient) -> None:
        response = client.get("/leads")
        assert response.status_code == 200
        assert response.json() == {"leads": []}

    def test_get_leads_after_create(self, client: TestClient) -> None:
        client.post(
            "/webhook",
            json={
                "event_id": "w-1",
                "source": "website",
                "data": {
                    "full_name": "Test User",
                    "phone": "9876500099",
                    "email": "test@example.com",
                    "message": "SEO help",
                },
            },
        )
        response = client.get("/leads")
        body = response.json()
        assert response.status_code == 200
        assert len(body["leads"]) == 1
        lead = body["leads"][0]
        assert lead["lead_id"] == 1
        assert lead["phone"] == "9876500099"
        assert lead["email"] == "test@example.com"
        assert lead["sources"] == ["website"]
        assert lead["service_category"] == "SEO"


class TestPostWebhook:
    def test_created_returns_200(self, client: TestClient) -> None:
        response = client.post(
            "/webhook",
            json={
                "event_id": "w-1",
                "source": "website",
                "data": {
                    "full_name": "A",
                    "phone": "9876500001",
                    "email": "a@test.com",
                    "message": "Need SEO",
                },
            },
        )
        assert response.status_code == 200
        assert response.json() == {"status": "created", "lead_id": 1}

    def test_duplicate_event_unchanged(self, client: TestClient) -> None:
        payload = {
            "event_id": "w-dup",
            "source": "website",
            "data": {
                "full_name": "A",
                "phone": "9876500001",
                "email": "a@test.com",
                "message": "First",
            },
        }
        client.post("/webhook", json=payload)
        dup = client.post("/webhook", json=payload)
        assert dup.status_code == 200
        assert dup.json() == {"status": "duplicate_event", "lead_id": 1}
        leads = client.get("/leads").json()["leads"]
        assert len(leads[0]["messages"]) == 1

    def test_merge_by_phone(self, client: TestClient) -> None:
        client.post(
            "/webhook",
            json={
                "event_id": "w-1",
                "source": "website",
                "data": {
                    "full_name": "Rohit Sharma",
                    "phone": "+91 98765 00011",
                    "email": "rohit@greenleaf.in",
                    "message": "Msg one",
                },
            },
        )
        merged = client.post(
            "/webhook",
            json={
                "event_id": "wa-1",
                "source": "whatsapp",
                "data": {
                    "from": "919876500011",
                    "profile_name": "Rohit",
                    "text": "Msg two",
                },
            },
        )
        assert merged.status_code == 200
        assert merged.json() == {"status": "merged", "lead_id": 1}
        lead = client.get("/leads").json()["leads"][0]
        assert lead["sources"] == ["website", "whatsapp"]
        assert lead["messages"] == ["Msg one", "Msg two"]

    def test_merge_by_email(self, client: TestClient) -> None:
        client.post(
            "/webhook",
            json={
                "event_id": "w-1",
                "source": "website",
                "data": {
                    "full_name": "Same Person",
                    "phone": "9876500100",
                    "email": "same@corp.in",
                    "message": "First touch",
                },
            },
        )
        merged = client.post(
            "/webhook",
            json={
                "event_id": "w-2",
                "source": "website",
                "data": {
                    "full_name": "Same Person",
                    "phone": "9876500199",
                    "email": "same@corp.in",
                    "message": "Second touch",
                },
            },
        )
        assert merged.json()["status"] == "merged"
        assert len(client.get("/leads").json()["leads"]) == 1

    def test_invalid_source_422(self, client: TestClient) -> None:
        response = client.post(
            "/webhook",
            json={"event_id": "x", "source": "twitter", "data": {}},
        )
        assert response.status_code == 422

    def test_missing_event_id_422(self, client: TestClient) -> None:
        response = client.post(
            "/webhook",
            json={"source": "website", "data": {}},
        )
        assert response.status_code == 422


class TestFixtureSequence:
    def test_six_events_expected_outcomes(
        self, client: TestClient, fixture_events: list[dict]
    ) -> None:
        expected_statuses = [
            ("created", 1),
            ("created", 2),
            ("created", 3),
            ("duplicate_event", 1),
            ("merged", 1),
            ("created", 4),
        ]
        for payload, (status, lead_id) in zip(fixture_events, expected_statuses):
            resp = client.post("/webhook", json=payload)
            assert resp.status_code == 200
            assert resp.json() == {"status": status, "lead_id": lead_id}

        all_leads = client.get("/leads").json()["leads"]
        assert len(all_leads) == 4

        rohit = next(l for l in all_leads if l["lead_id"] == 1)
        assert rohit["name"] == "Rohit Sharma"
        assert rohit["phone"] == "9876500011"
        assert rohit["email"] == "rohit@greenleaf.in"
        assert rohit["sources"] == ["website", "whatsapp"]
        assert len(rohit["messages"]) == 2
        assert rohit["service_category"] == "Performance Marketing"

        categories = {l["lead_id"]: l["service_category"] for l in all_leads}
        assert categories[2] == "Website"
        assert categories[3] == "Social Media"
        assert categories[4] == "AI Chatbot"


class TestEnrichLead:
    def test_llm_enrich_when_api_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.config import get_settings

        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        get_settings.cache_clear()
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices[0].message.content = json.dumps(
            {
                "service_category": "Performance Marketing",
                "summary": "D2C brand wants Google Ads at about 1.5 lakh per month.",
            }
        )
        mock_client.chat.completions.create.return_value = mock_response

        lead = {
            "messages": ["Need Google Ads for our D2C brand, budget 1.5L/month"],
            "service_category": "Other",
            "summary": "",
        }

        with patch("app.llm._openai_client", return_value=mock_client):
            main.enrich_lead(lead)

        assert lead["service_category"] == "Performance Marketing"
        assert "Google Ads" in lead["summary"]
        mock_client.chat.completions.create.assert_called_once()

    def test_llm_failure_falls_back_to_heuristic(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.config import get_settings

        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        get_settings.cache_clear()
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = RuntimeError("API down")

        lead = {
            "messages": ["AI chatbot for our hospital"],
            "service_category": "Other",
            "summary": "",
        }

        with patch("app.llm._openai_client", return_value=mock_client):
            main.enrich_lead(lead)

        assert lead["service_category"] == "AI Chatbot"
        assert lead["summary"] == "AI chatbot for our hospital"
