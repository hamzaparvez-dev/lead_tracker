from __future__ import annotations


def parse_lead_fields(source: str, data: dict) -> tuple[str, str, str | None, str]:
    if source == "website":
        return (
            (data.get("full_name") or "").strip(),
            data.get("phone") or "",
            data.get("email"),
            (data.get("message") or "").strip(),
        )
    if source == "facebook":
        fields: dict[str, str] = {}
        for item in data.get("field_data") or []:
            values = item.get("values") or []
            if values:
                fields[item.get("name", "")] = values[0]
        return (
            (fields.get("full_name") or "").strip(),
            fields.get("phone_number") or "",
            None,
            (fields.get("what_service_do_you_need") or "").strip(),
        )
    if source == "whatsapp":
        return (
            (data.get("profile_name") or "").strip(),
            data.get("from") or "",
            None,
            (data.get("text") or "").strip(),
        )
    raise ValueError(f"Unknown source: {source}")
