# Lead Tracker

**Multi-source lead webhook intake** for Parmarketing-style agency workflows. A single FastAPI service accepts leads from **website forms**, **Facebook Lead Ads**, and **WhatsApp**, normalizes contact data, deduplicates provider retries, merges the same person across channels, and enriches each lead with an LLM-assigned **service category** and **one-line summary**.

Production-oriented FastAPI service with **SQLite/PostgreSQL** persistence, **background LLM enrichment** (configurable), optional **webhook HMAC** verification, **Docker Compose** deployment, and a full **pytest** suite. Product requirements: [`prd.md`](prd.md).

---

## Table of contents

- [Features](#features)
- [Architecture](#architecture)
- [Request lifecycle](#request-lifecycle)
- [Data model](#data-model)
- [API reference](#api-reference)
- [Normalization rules](#normalization-rules)
- [Environment variables](#environment-variables)
- [Quick start](#quick-start)
- [Demo script](#demo-script)
- [Testing](#testing)
- [Project structure](#project-structure)
- [Production roadmap](#production-roadmap)

---

## Features

| Capability | Description |
|------------|-------------|
| **Multi-format ingestion** | One `POST /webhook` endpoint; payload shape depends on `source`. |
| **Field normalization** | Phone → 10 digits; email → lowercase; names/messages trimmed. |
| **Idempotent events** | Same `event_id` twice → `duplicate_event`, no data change. |
| **Person merge** | Match existing lead by normalized **phone** or **email** → append message & source. |
| **LLM enrichment** | `service_category` + English `summary` from all messages (OpenAI-compatible API). |
| **Fast responses** | HTTP **200** with `{ "status", "lead_id" }`; LLM runs in background when `ENRICH_SYNC=false`. |
| **Persistence** | SQLAlchemy + SQLite (dev) or PostgreSQL (prod). |
| **Security** | Optional `WEBHOOK_SECRET` + `X-Webhook-Signature` HMAC. |
| **Operations** | `GET /health`, structured logs, Docker Compose stack. |

---

## Architecture

High-level components and data flow:

```mermaid
flowchart TB
  subgraph sources [Lead sources]
    WEB[Website form]
    FB[Facebook Lead Ads]
    WA[WhatsApp]
  end

  subgraph api [FastAPI service]
    WH[POST /webhook]
    PARSE[parse_lead_fields]
    NORM[normalize phone / email]
    DEDUP{event_id seen?}
    MERGE{phone or email match?}
    STORE[(In-memory store)]
    LLM[enrich_lead LLM]
    GL[GET /leads]
  end

  WEB --> WH
  FB --> WH
  WA --> WH
  WH --> PARSE --> NORM --> DEDUP
  DEDUP -->|yes| DUP[duplicate_event]
  DEDUP -->|no| MERGE
  MERGE -->|yes| M[merged: append source + message]
  MERGE -->|no| C[created: new lead]
  M --> LLM --> STORE
  C --> LLM --> STORE
  STORE --> GL
  DUP --> WH
```

Persistent storage model (SQLAlchemy — see [`app/models.py`](app/models.py)):

```mermaid
erDiagram
  LEADS {
    int lead_id PK
    string name
    string phone
    string email
    string service_category
    string summary
  }
  LEAD_MESSAGES {
    int id PK
    int lead_id FK
    int position
    string text
  }
  LEAD_SOURCES {
    int id PK
    int lead_id FK
    string source
  }
  PROCESSED_EVENTS {
    string event_id PK
    int lead_id FK
  }
  LEADS ||--o{ LEAD_MESSAGES : contains
  LEADS ||--o{ LEAD_SOURCES : has
  LEADS ||--o{ PROCESSED_EVENTS : idempotent_by
```

Runtime lookup uses indexed **phone** and **email** on `LEADS` plus `PROCESSED_EVENTS.event_id` for deduplication.

---

## Request lifecycle

Sequence for a **new** event (not duplicate, not merge):

```mermaid
sequenceDiagram
  participant Provider
  participant Webhook as POST /webhook
  participant Parser
  participant Store
  participant LLM

  Provider->>Webhook: JSON event_id, source, data
  Webhook->>Parser: parse_lead_fields(source, data)
  Parser-->>Webhook: name, phone, email, message
  Webhook->>Webhook: normalize_phone, normalize_email
  alt event_id already processed
    Webhook-->>Provider: 200 duplicate_event + lead_id
  else existing phone or email
    Webhook->>Store: append message and source
    Webhook->>LLM: enrich_lead(all messages)
    Webhook-->>Provider: 200 merged + lead_id
  else new person
    Webhook->>Store: create lead + indexes
    Webhook->>LLM: enrich_lead(messages)
    Webhook-->>Provider: 200 created + lead_id
  end
```

---

## Data model

Each lead returned by `GET /leads`:

```json
{
  "lead_id": 1,
  "name": "Rohit Sharma",
  "phone": "9876500011",
  "email": "rohit@greenleaf.in",
  "sources": ["website", "whatsapp"],
  "messages": [
    "Need Google Ads for our D2C brand, budget 1.5L/month",
    "Any update on my Google Ads query?"
  ],
  "service_category": "Performance Marketing",
  "summary": "D2C brand wants Google Ads at about 1.5 lakh per month and is following up."
}
```

**Service categories** (exactly one):

`SEO` · `Performance Marketing` · `Website` · `Social Media` · `AI Chatbot` · `Other`

---

## API reference

### `POST /webhook`

Ingest one lead event.

**Request body**

| Field | Type | Description |
|-------|------|-------------|
| `event_id` | string | Provider idempotency key (unique per logical event). |
| `source` | `"website"` \| `"facebook"` \| `"whatsapp"` | Determines how `data` is parsed. |
| `data` | object | Source-specific payload (see below). |

**Response** (always HTTP 200 on valid input)

| Field | Type | Description |
|-------|------|-------------|
| `status` | `"created"` \| `"merged"` \| `"duplicate_event"` | Processing outcome. |
| `lead_id` | integer | Target lead record. |

**`data` by source**

| Source | Fields used |
|--------|-------------|
| **website** | `full_name`, `phone`, `email`, `message` |
| **facebook** | `field_data[]` with `name` / `values` — `full_name`, `phone_number`, `what_service_do_you_need` |
| **whatsapp** | `profile_name`, `from` (phone), `text` |

<details>
<summary><strong>Example: website (E1)</strong></summary>

```bash
curl -s -X POST http://127.0.0.1:8000/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "event_id": "w-101",
    "source": "website",
    "data": {
      "full_name": "Rohit Sharma",
      "phone": "+91 98765 00011",
      "email": "rohit@greenleaf.in",
      "message": "Need Google Ads for our D2C brand, budget 1.5L/month"
    }
  }'
```

```json
{"status": "created", "lead_id": 1}
```

</details>

<details>
<summary><strong>Example: Facebook Lead Ad</strong></summary>

```json
{
  "event_id": "fb-201",
  "source": "facebook",
  "data": {
    "field_data": [
      {"name": "full_name", "values": ["Sneha Patil"]},
      {"name": "phone_number", "values": ["9876500022"]},
      {"name": "what_service_do_you_need", "values": ["Website for dental clinic"]}
    ]
  }
}
```

</details>

<details>
<summary><strong>Example: WhatsApp</strong></summary>

```json
{
  "event_id": "wa-301",
  "source": "whatsapp",
  "data": {
    "from": "919876500033",
    "profile_name": "Anil",
    "text": "Hi, social media management chahiye real estate project ke liye"
  }
}
```

</details>

---

### `GET /leads`

List all leads (newest append order in the in-memory list).

**Response**

```json
{
  "leads": [ /* lead objects */ ]
}
```

---

### Official fixture sequence (E1–E6)

Send in order to reproduce the interview scenario:

```mermaid
flowchart LR
  E1[E1 website Rohit] --> E2[E2 FB Sneha]
  E2 --> E3[E3 WA Anil]
  E3 --> E4[E4 dup w-101]
  E4 --> E5[E5 WA merge Rohit]
  E5 --> E6[E6 FB Priya]
  E6 --> R[4 leads total]
```

| Event | Expected `status` | `lead_id` |
|-------|-------------------|-----------|
| E1 | `created` | 1 |
| E2 | `created` | 2 |
| E3 | `created` | 3 |
| E4 | `duplicate_event` | 1 |
| E5 | `merged` | 1 |
| E6 | `created` | 4 |

After E6, lead **1** has two messages and sources `website` + `whatsapp`. Categories: Rohit → Performance Marketing, Sneha → Website, Anil → Social Media, Priya → AI Chatbot.

---

## Normalization rules

**Phone**

1. Strip non-digits.
2. If length &gt; 10 and starts with `91`, remove leading `91`.
3. If 11 digits and starts with `0`, remove leading `0`.
4. If still &gt; 10 digits, keep the **last 10** (edge-case safety).

| Raw | Normalized |
|-----|------------|
| `+91 98765 00011` | `9876500011` |
| `919876500011` | `9876500011` |
| `09876500044` | `9876500044` |

**Email**: trim, lowercase; empty → `null` in JSON responses.

**Dedupe vs merge**

```mermaid
flowchart TD
  A[Incoming event] --> B{event_id in seen_event_ids?}
  B -->|yes| D[duplicate_event]
  B -->|no| C{phone or email in index?}
  C -->|yes| M[merged]
  C -->|no| N[created]
```

---

## Environment variables

Copy [`.env.example`](.env.example) to `.env`:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Optional | Default `sqlite:///./data/leads.db`; use Postgres in production. |
| `OPENAI_API_KEY` | Recommended | OpenAI (or compatible) API key for LLM enrichment. |
| `OPENAI_BASE_URL` | Optional | Override base URL (Groq, OpenRouter, etc.). |
| `OPENAI_MODEL` | Optional | Default: `gpt-4o-mini`. |
| `ENRICH_SYNC` | Optional | `true` = wait for LLM in request; `false` = background (default). |
| `WEBHOOK_SECRET` | Optional | When set, requires valid `X-Webhook-Signature: sha256=<hex>`. |

Without `OPENAI_API_KEY`, the service uses keyword heuristics for category and the first message (truncated) as summary — sufficient for local demos and tests.

---

## Quick start

**Requirements:** Python 3.9+

```bash
git clone https://github.com/hamzaparvez-dev/lead_tracker.git
cd lead_tracker

python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -r requirements.txt
cp .env.example .env        # add OPENAI_API_KEY if you have one

uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

**Docker (API + Postgres)**

```bash
docker compose up --build
```

- Health: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- Interactive docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- OpenAPI JSON: [http://127.0.0.1:8000/openapi.json](http://127.0.0.1:8000/openapi.json)

---

## Demo script

Posts E1–E6 and prints `GET /leads`:

```bash
python scripts/send_events.py
# optional base URL:
python scripts/send_events.py http://127.0.0.1:8000
```

---

## Testing

The suite uses **FastAPI `TestClient`**, isolated in-memory state (`reset_store()` per test), and **no live LLM calls** (API key unset; LLM path covered with mocks).

```bash
source .venv/bin/activate
pip install -r requirements.txt
pytest -v
```

| Module | Coverage |
|--------|----------|
| [`tests/test_normalization.py`](tests/test_normalization.py) | Phone/email normalization; parsers for website, Facebook, WhatsApp. |
| [`tests/test_webhook.py`](tests/test_webhook.py) | `GET /leads`, create/merge/duplicate, validation 422, full E1–E6 sequence, LLM success/fallback mocks. |

Example:

```bash
pytest tests/test_webhook.py::TestFixtureSequence::test_six_events_expected_outcomes -v
```

---

## Project structure

```
lead_tracker/
├── prd.md                  # Product requirements
├── main.py                 # Entrypoint + test re-exports
├── app/
│   ├── api.py              # Routes, background LLM
│   ├── config.py           # Environment settings
│   ├── db.py               # SQLAlchemy engine
│   ├── models.py           # Lead, messages, sources, events
│   ├── repository.py       # Dedupe, merge, persistence
│   ├── llm.py              # Enrichment + heuristics
│   ├── security.py         # Webhook HMAC
│   └── ...
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── pytest.ini
├── scripts/send_events.py
└── tests/
```

---

## Production roadmap

| Area | Shipped | Next steps |
|------|---------|------------|
| **Storage** | SQLite + PostgreSQL via `DATABASE_URL` | Migrations (Alembic), read replicas |
| **LLM** | Background tasks when `ENRICH_SYNC=false` | Queue worker, retries, cache by message hash |
| **Webhooks** | Optional HMAC secret | Provider-specific signature formats |
| **Scale** | Docker Compose | Horizontal API + connection pooling, rate limits |
| **Observability** | Request logging | OpenTelemetry, metrics on merge/dedupe/LLM latency |

---

## License

MIT (or specify your license here).
