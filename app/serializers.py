from __future__ import annotations

from app.models import Lead


def lead_to_dict(lead: Lead) -> dict:
    return {
        "lead_id": lead.lead_id,
        "name": lead.name,
        "phone": lead.phone,
        "email": lead.email,
        "sources": [s.source for s in lead.sources],
        "messages": [m.text for m in lead.messages],
        "service_category": lead.service_category,
        "summary": lead.summary,
    }
