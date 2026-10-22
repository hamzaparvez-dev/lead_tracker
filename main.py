from __future__ import annotations

from dotenv import load_dotenv

load_dotenv()

from app.api import app  # noqa: E402
from app.llm import (  # noqa: E402
    CATEGORIES,
    _openai_client,
    enrich_lead_dict as enrich_lead,
    guess_category as _guess_category,
)
from app.normalize import normalize_email, normalize_phone  # noqa: E402
from app.parsers import parse_lead_fields  # noqa: E402
from app.repository import get_all_leads, reset_store  # noqa: E402

__all__ = [
    "app",
    "reset_store",
    "normalize_phone",
    "normalize_email",
    "parse_lead_fields",
    "enrich_lead",
    "_guess_category",
    "_openai_client",
    "CATEGORIES",
    "get_all_leads",
]
