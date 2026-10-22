#!/usr/bin/env python3
from __future__ import annotations
"""POST fixture events E1–E6 in order, then GET /leads."""

import json
import sys
import urllib.error
import urllib.request

BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"

EVENTS = [
    {
        "label": "E1 website",
        "body": {
            "event_id": "w-101",
            "source": "website",
            "data": {
                "full_name": "Rohit Sharma",
                "phone": "+91 98765 00011",
                "email": "rohit@greenleaf.in",
                "message": "Need Google Ads for our D2C brand, budget 1.5L/month",
            },
        },
    },
    {
        "label": "E2 facebook",
        "body": {
            "event_id": "fb-201",
            "source": "facebook",
            "data": {
                "field_data": [
                    {"name": "full_name", "values": ["Sneha Patil"]},
                    {"name": "phone_number", "values": ["9876500022"]},
                    {"name": "what_service_do_you_need", "values": ["Website for dental clinic"]},
                ]
            },
        },
    },
    {
        "label": "E3 whatsapp",
        "body": {
            "event_id": "wa-301",
            "source": "whatsapp",
            "data": {
                "from": "919876500033",
                "profile_name": "Anil",
                "text": "Hi, social media management chahiye real estate project ke liye",
            },
        },
    },
    {
        "label": "E4 duplicate website",
        "body": {
            "event_id": "w-101",
            "source": "website",
            "data": {
                "full_name": "Rohit Sharma",
                "phone": "+91 98765 00011",
                "email": "rohit@greenleaf.in",
                "message": "Need Google Ads for our D2C brand, budget 1.5L/month",
            },
        },
    },
    {
        "label": "E5 whatsapp merge",
        "body": {
            "event_id": "wa-302",
            "source": "whatsapp",
            "data": {
                "from": "919876500011",
                "profile_name": "Rohit",
                "text": "Any update on my Google Ads query?",
            },
        },
    },
    {
        "label": "E6 facebook",
        "body": {
            "event_id": "fb-202",
            "source": "facebook",
            "data": {
                "field_data": [
                    {"name": "full_name", "values": ["Priya Nair"]},
                    {"name": "phone_number", "values": ["09876500044"]},
                    {"name": "what_service_do_you_need", "values": ["AI chatbot for our hospital"]},
                ]
            },
        },
    },
]


def request(method: str, path: str, data: dict | None = None) -> dict:
    url = f"{BASE}{path}"
    headers = {"Content-Type": "application/json"}
    body = json.dumps(data).encode() if data is not None else None
    req = urllib.request.Request(url, data=body, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.loads(resp.read().decode())


def main() -> None:
    print(f"Target: {BASE}\n")
    for ev in EVENTS:
        try:
            result = request("POST", "/webhook", ev["body"])
            print(f"{ev['label']}: {result}")
        except urllib.error.HTTPError as e:
            print(f"{ev['label']}: HTTP {e.code} {e.read().decode()}")
            sys.exit(1)
        except urllib.error.URLError as e:
            print(f"Cannot reach server: {e.reason}")
            sys.exit(1)

    print("\nGET /leads:")
    all_leads = request("GET", "/leads")
    print(json.dumps(all_leads, indent=2))
    n = len(all_leads.get("leads", []))
    print(f"\nTotal leads: {n} (expected 4)")


if __name__ == "__main__":
    main()
