from __future__ import annotations

import json
import logging
import os
import re
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI
from openai import OpenAI
from pydantic import BaseModel

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

CATEGORIES = [
    "SEO",
    "Performance Marketing",
    "Website",
    "Social Media",
    "AI Chatbot",
    "Other",
]

# --- In-memory store ---
leads: list[dict] = []
seen_event_ids: set[str] = set()
event_to_lead_id: dict[str, int] = {}
phone_index: dict[str, int] = {}
email_index: dict[str, int] = {}
next_lead_id = 1


def normalize_phone(raw: str | None) -> str:
    if not raw:
        return ""
    digits = re.sub(r"\D", "", raw)
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    if len(digits) > 10:
        digits = digits[-10:]
    return digits


def normalize_email(raw: str | None) -> str | None:
    if not raw:
        return None
    email = raw.strip().lower()
    return email or None


def parse_lead_fields(source: str, data: dict) -> tuple[str, str, str | None, str]:
    if source == "website":
        return (
            (data.get("full_name") or "").strip(),
            data.get("phone") or "",
            data.get("email"),
            (data.get("message") or "").strip(),
        )
    if source == "facebook":
        fields: dict[str, str] = {}
        for item in data.get("field_data") or []:
            values = item.get("values") or []
            if values:
                fields[item.get("name", "")] = values[0]
        return (
            (fields.get("full_name") or "").strip(),
            fields.get("phone_number") or "",
            None,
            (fields.get("what_service_do_you_need") or "").strip(),
        )
    if source == "whatsapp":
        return (
            (data.get("profile_name") or "").strip(),
            data.get("from") or "",
            None,
            (data.get("text") or "").strip(),
        )
    raise ValueError(f"Unknown source: {source}")


def find_lead_id(phone: str, email: str | None) -> int | None:
    if phone and phone in phone_index:
        return phone_index[phone]
    if email and email in email_index:
        return email_index[email]
    return None


def index_lead(lead_id: int, phone: str, email: str | None) -> None:
    if phone:
        phone_index[phone] = lead_id
    if email:
        email_index[email] = lead_id


def _openai_client() -> OpenAI | None:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None
    kwargs: dict = {"api_key": api_key}
    base_url = os.getenv("OPENAI_BASE_URL")
    if base_url:
        kwargs["base_url"] = base_url
    return OpenAI(**kwargs)


def enrich_lead(lead: dict) -> None:
    messages_text = "\n".join(lead["messages"])
    fallback_summary = (lead["messages"][0][:120] if lead["messages"] else "") or "No message"

    client = _openai_client()
    if not client:
        lead["service_category"] = _guess_category(messages_text)
        lead["summary"] = fallback_summary
        return

    model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
    prompt = (
        "Classify this marketing agency lead and write a one-line English summary.\n\n"
        f"Messages:\n{messages_text}\n\n"
        f"Pick exactly one service_category from: {', '.join(CATEGORIES)}.\n"
        'Respond with JSON only: {"service_category": "...", "summary": "..."}'
    )
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout=30.0,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        cat = parsed.get("service_category", "Other")
        if cat not in CATEGORIES:
            cat = "Other"
        lead["service_category"] = cat
        lead["summary"] = (parsed.get("summary") or fallback_summary).strip()
    except Exception as e:
        logger.warning("LLM enrich failed: %s", e)
        lead["service_category"] = _guess_category(messages_text)
        lead["summary"] = fallback_summary


def _guess_category(text: str) -> str:
    lower = text.lower()
    if "google ads" in lower or "performance" in lower or "d2c" in lower:
        return "Performance Marketing"
    if "dental" in lower or "website" in lower and "clinic" in lower:
        return "Website"
    if "social media" in lower:
        return "Social Media"
    if "chatbot" in lower or "ai " in lower:
        return "AI Chatbot"
    if "seo" in lower:
        return "SEO"
    return "Other"


class WebhookRequest(BaseModel):
    event_id: str
    source: Literal["website", "facebook", "whatsapp"]
    data: dict


class WebhookResponse(BaseModel):
    status: Literal["created", "merged", "duplicate_event"]
    lead_id: int


app = FastAPI(title="Lead Webhook Intake")


@app.get("/leads")
def get_leads():
    return {"leads": leads}


@app.post("/webhook", response_model=WebhookResponse)
def post_webhook(body: WebhookRequest):
    global next_lead_id

    if body.event_id in seen_event_ids:
        lead_id = event_to_lead_id[body.event_id]
        return WebhookResponse(status="duplicate_event", lead_id=lead_id)

    name, phone_raw, email_raw, message = parse_lead_fields(body.source, body.data)
    phone = normalize_phone(phone_raw)
    email = normalize_email(email_raw)

    existing_id = find_lead_id(phone, email)
    if existing_id is not None:
        lead = next(l for l in leads if l["lead_id"] == existing_id)
        if message:
            lead["messages"].append(message)
        if body.source not in lead["sources"]:
            lead["sources"].append(body.source)
        enrich_lead(lead)
        seen_event_ids.add(body.event_id)
        event_to_lead_id[body.event_id] = existing_id
        return WebhookResponse(status="merged", lead_id=existing_id)

    lead_id = next_lead_id
    next_lead_id += 1
    lead = {
        "lead_id": lead_id,
        "name": name,
        "phone": phone,
        "email": email,
        "sources": [body.source],
        "messages": [message] if message else [],
        "service_category": "Other",
        "summary": "",
    }
    enrich_lead(lead)
    leads.append(lead)
    index_lead(lead_id, phone, email)
    seen_event_ids.add(body.event_id)
    event_to_lead_id[body.event_id] = lead_id
    return WebhookResponse(status="created", lead_id=lead_id)
