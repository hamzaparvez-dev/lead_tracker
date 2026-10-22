from __future__ import annotations

import logging

from fastapi import BackgroundTasks, FastAPI, HTTPException, Request
from pydantic import ValidationError

from app.config import get_settings
from app.db import SessionLocal, init_db
from app.llm import enrich_lead_by_id
from app.repository import list_leads, process_webhook
from app.schemas import WebhookRequest, WebhookResponse
from app.security import verify_webhook_signature

logger = logging.getLogger(__name__)

app = FastAPI(title="Lead Webhook Intake", version="1.0.0")


@app.on_event("startup")
def on_startup() -> None:
    init_db()


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/leads")
def get_leads():
    session = SessionLocal()
    try:
        return {"leads": list_leads(session)}
    finally:
        session.close()


@app.post("/webhook", response_model=WebhookResponse)
async def post_webhook(request: Request, background_tasks: BackgroundTasks):
    body_bytes = await request.body()
    verify_webhook_signature(request.headers.get("X-Webhook-Signature"), body_bytes)
    try:
        body = WebhookRequest.model_validate_json(body_bytes)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=exc.errors()) from exc
    settings = get_settings()

    session = SessionLocal()
    try:
        result = process_webhook(
            session,
            body.event_id,
            body.source,
            body.data,
            sync_enrich=settings.enrich_sync,
        )
    finally:
        session.close()

    if not settings.enrich_sync and result.status != "duplicate_event":
        background_tasks.add_task(enrich_lead_by_id, result.lead_id)

    logger.info(
        "webhook event_id=%s status=%s lead_id=%s",
        body.event_id,
        result.status,
        result.lead_id,
    )
    return WebhookResponse(status=result.status, lead_id=result.lead_id)
