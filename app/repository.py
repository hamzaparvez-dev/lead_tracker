from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db import Base, SessionLocal, configure_engine, get_engine, init_db
from app.llm import enrich_lead
from app.models import Lead, LeadMessage, LeadSource, ProcessedEvent
from app.normalize import normalize_email, normalize_phone
from app.parsers import parse_lead_fields


class WebhookResult:
    def __init__(self, status: str, lead_id: int):
        self.status = status
        self.lead_id = lead_id


def reset_store() -> None:
    get_settings.cache_clear()
    configure_engine()
    Base.metadata.drop_all(bind=get_engine())
    init_db()


def list_leads(session: Session) -> list[dict]:
    from app.serializers import lead_to_dict

    stmt = select(Lead).options(
        selectinload(Lead.messages),
        selectinload(Lead.sources),
    ).order_by(Lead.lead_id)
    return [lead_to_dict(l) for l in session.scalars(stmt).all()]


def find_lead_id(session: Session, phone: str, email: str | None) -> int | None:
    if phone:
        row = session.scalar(select(Lead.lead_id).where(Lead.phone == phone).limit(1))
        if row:
            return row
    if email:
        row = session.scalar(select(Lead.lead_id).where(Lead.email == email).limit(1))
        if row:
            return row
    return None


def process_webhook(
    session: Session,
    event_id: str,
    source: str,
    data: dict,
    *,
    sync_enrich: bool,
) -> WebhookResult:
    existing_event = session.get(ProcessedEvent, event_id)
    if existing_event:
        return WebhookResult("duplicate_event", existing_event.lead_id)

    name, phone_raw, email_raw, message = parse_lead_fields(source, data)
    phone = normalize_phone(phone_raw)
    email = normalize_email(email_raw)

    existing_id = find_lead_id(session, phone, email)
    if existing_id is not None:
        lead = session.get(
            Lead,
            existing_id,
            options=(selectinload(Lead.messages), selectinload(Lead.sources)),
        )
        assert lead is not None
        if message:
            lead.messages.append(
                LeadMessage(position=len(lead.messages), text=message)
            )
        if not any(s.source == source for s in lead.sources):
            lead.sources.append(LeadSource(source=source))
        enrich_lead(session, lead, sync_llm=sync_enrich)
        session.add(ProcessedEvent(event_id=event_id, lead_id=existing_id))
        session.commit()
        return WebhookResult("merged", existing_id)

    lead = Lead(name=name, phone=phone, email=email)
    if message:
        lead.messages.append(LeadMessage(position=0, text=message))
    lead.sources.append(LeadSource(source=source))
    session.add(lead)
    session.flush()
    enrich_lead(session, lead, sync_llm=sync_enrich)
    session.add(ProcessedEvent(event_id=event_id, lead_id=lead.lead_id))
    session.commit()
    return WebhookResult("created", lead.lead_id)


def get_all_leads() -> list[dict]:
    session = SessionLocal()
    try:
        return list_leads(session)
    finally:
        session.close()
