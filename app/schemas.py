from __future__ import annotations

from typing import Literal

from pydantic import BaseModel


class WebhookRequest(BaseModel):
    event_id: str
    source: Literal["website", "facebook", "whatsapp"]
    data: dict


class WebhookResponse(BaseModel):
    status: Literal["created", "merged", "duplicate_event"]
    lead_id: int
