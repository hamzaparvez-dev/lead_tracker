# Product Requirements Document — Multi-Source Lead Webhook

## Overview

Agency lead intake from **website**, **Facebook Lead Ads**, and **WhatsApp**. Each provider sends a different JSON shape. The service normalizes data, deduplicates by `event_id`, merges the same person by phone or email, and enriches leads with LLM-derived **service_category** and **summary**.

## Functional requirements

### FR-1 Webhook ingestion

- `POST /webhook` accepts JSON: `event_id`, `source` (`website` | `facebook` | `whatsapp`), `data`.
- Response: HTTP **200** with `{"status": "created"|"merged"|"duplicate_event", "lead_id": int}`.

### FR-2 Normalization

- **Phone**: 10 digits; strip `+91`, leading `91`, or leading `0` as specified.
- **Email**: lowercase, trimmed.
- **Name / message**: trimmed per source parser.

### FR-3 Deduplication

- Same `event_id` twice → `duplicate_event`, no mutation.

### FR-4 Merge

- Match existing lead by normalized **phone** or **email** → append message and source, `merged`.

### FR-5 LLM enrichment

- Categories: SEO, Performance Marketing, Website, Social Media, AI Chatbot, Other.
- One-line English **summary** from all messages.
- API key via environment variable only.

### FR-6 List leads

- `GET /leads` returns all leads in standard shape.

## Non-functional requirements (production)

| ID | Requirement |
|----|-------------|
| NFR-1 | **Persistence**: SQLite (dev) or PostgreSQL (prod) via `DATABASE_URL`. |
| NFR-2 | **Fast webhook**: LLM enrichment runs in background by default (`ENRICH_SYNC=false`). |
| NFR-3 | **Webhook auth**: Optional HMAC `X-Webhook-Signature` when `WEBHOOK_SECRET` is set. |
| NFR-4 | **Health**: `GET /health` for load balancers. |
| NFR-5 | **Observability**: Structured logging for event_id, status, lead_id. |
| NFR-6 | **Deploy**: Docker + docker-compose (API + Postgres). |
| NFR-7 | **Tests**: pytest covering parsers, API, E1–E6 fixture, signature, health. |

## Acceptance criteria (E1–E6)

| Event | Status | Lead |
|-------|--------|------|
| E1 | created | 1 |
| E2 | created | 2 |
| E3 | created | 3 |
| E4 | duplicate_event | 1 |
| E5 | merged | 1 (2 messages, website + whatsapp) |
| E6 | created | 4 |

Final: **4 leads**; categories Rohit → Performance Marketing, Sneha → Website, Anil → Social Media, Priya → AI Chatbot.

## Lead JSON shape

```json
{
  "lead_id": 1,
  "name": "Rohit Sharma",
  "phone": "9876500011",
  "email": "rohit@greenleaf.in",
  "sources": ["website", "whatsapp"],
  "messages": ["...", "..."],
  "service_category": "Performance Marketing",
  "summary": "..."
}
```
