from __future__ import annotations

import json
import logging

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Lead

logger = logging.getLogger(__name__)

CATEGORIES = [
    "SEO",
    "Performance Marketing",
    "Website",
    "Social Media",
    "AI Chatbot",
    "Other",
]


def _openai_client() -> OpenAI | None:
    settings = get_settings()
    if not settings.openai_api_key:
        return None
    kwargs: dict = {"api_key": settings.openai_api_key}
    if settings.openai_base_url:
        kwargs["base_url"] = settings.openai_base_url
    return OpenAI(**kwargs)


def guess_category(text: str) -> str:
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


def lead_messages_text(lead: Lead) -> str:
    return "\n".join(m.text for m in lead.messages)


def apply_heuristic_enrichment(lead: Lead) -> None:
    text = lead_messages_text(lead)
    lead.service_category = guess_category(text)
    lead.summary = (lead.messages[0].text[:120] if lead.messages else "") or "No message"


def enrich_lead_record(lead: Lead) -> None:
    messages_text = lead_messages_text(lead)
    apply_heuristic_enrichment(lead)
    fallback_summary = lead.summary

    client = _openai_client()
    if not client:
        return

    settings = get_settings()
    prompt = (
        "Classify this marketing agency lead and write a one-line English summary.\n\n"
        f"Messages:\n{messages_text}\n\n"
        f"Pick exactly one service_category from: {', '.join(CATEGORIES)}.\n"
        'Respond with JSON only: {"service_category": "...", "summary": "..."}'
    )
    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
            timeout=30.0,
        )
        content = response.choices[0].message.content or "{}"
        parsed = json.loads(content)
        cat = parsed.get("service_category", "Other")
        if cat not in CATEGORIES:
            cat = "Other"
        lead.service_category = cat
        lead.summary = (parsed.get("summary") or fallback_summary).strip()
    except Exception as e:
        logger.warning("LLM enrich failed: %s", e)


def enrich_lead_by_id(lead_id: int) -> None:
    from app.db import SessionLocal

    session = SessionLocal()
    try:
        lead = session.get(Lead, lead_id)
        if not lead:
            return
        enrich_lead_record(lead)
        session.commit()
    finally:
        session.close()


def enrich_lead_dict(lead: dict) -> None:
    """In-memory dict shape (tests / legacy)."""
    messages_text = "\n".join(lead["messages"])
    fallback = (lead["messages"][0][:120] if lead["messages"] else "") or "No message"
    lead["service_category"] = guess_category(messages_text)
    lead["summary"] = fallback

    client = _openai_client()
    if not client:
        return

    settings = get_settings()
    prompt = (
        "Classify this marketing agency lead and write a one-line English summary.\n\n"
        f"Messages:\n{messages_text}\n\n"
        f"Pick exactly one service_category from: {', '.join(CATEGORIES)}.\n"
        'Respond with JSON only: {"service_category": "...", "summary": "..."}'
    )
    try:
        response = client.chat.completions.create(
            model=settings.openai_model,
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
        lead["summary"] = (parsed.get("summary") or fallback).strip()
    except Exception as e:
        logger.warning("LLM enrich failed: %s", e)


def enrich_lead(session: Session, lead: Lead, sync_llm: bool) -> None:
    apply_heuristic_enrichment(lead)
    session.flush()
    if sync_llm:
        enrich_lead_record(lead)
