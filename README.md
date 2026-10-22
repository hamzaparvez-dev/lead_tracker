# lead_tracker

Multi-source lead webhook intake service (FastAPI): website, Facebook Lead Ads, and WhatsApp.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # set OPENAI_API_KEY
uvicorn main:app --reload --port 8000
```

## API

- `POST /webhook` — ingest lead events
- `GET /leads` — list normalized leads

## Demo

```bash
python scripts/send_events.py
```
