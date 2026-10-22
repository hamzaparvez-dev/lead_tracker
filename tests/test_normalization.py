from __future__ import annotations

import pytest

import main


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("+91 98765 00011", "9876500011"),
        ("9876500022", "9876500022"),
        ("919876500011", "9876500011"),
        ("09876500044", "9876500044"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_phone(raw: str | None, expected: str) -> None:
    assert main.normalize_phone(raw) == expected


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Rohit@GreenLeaf.IN", "rohit@greenleaf.in"),
        ("  a@b.co  ", "a@b.co"),
        ("", None),
        (None, None),
    ],
)
def test_normalize_email(raw: str | None, expected: str | None) -> None:
    assert main.normalize_email(raw) == expected


def test_parse_website_fields() -> None:
    name, phone, email, message = main.parse_lead_fields(
        "website",
        {
            "full_name": " Rohit ",
            "phone": "+91 98765 00011",
            "email": "rohit@greenleaf.in",
            "message": "Hello",
        },
    )
    assert name == "Rohit"
    assert phone == "+91 98765 00011"
    assert email == "rohit@greenleaf.in"
    assert message == "Hello"


def test_parse_facebook_fields() -> None:
    name, phone, email, message = main.parse_lead_fields(
        "facebook",
        {
            "field_data": [
                {"name": "full_name", "values": ["Sneha Patil"]},
                {"name": "phone_number", "values": ["9876500022"]},
                {"name": "what_service_do_you_need", "values": ["Website for dental clinic"]},
            ]
        },
    )
    assert name == "Sneha Patil"
    assert phone == "9876500022"
    assert email is None
    assert message == "Website for dental clinic"


def test_parse_whatsapp_fields() -> None:
    name, phone, email, message = main.parse_lead_fields(
        "whatsapp",
        {"from": "919876500033", "profile_name": "Anil", "text": "Hi there"},
    )
    assert name == "Anil"
    assert phone == "919876500033"
    assert email is None
    assert message == "Hi there"


def test_parse_unknown_source_raises() -> None:
    with pytest.raises(ValueError, match="Unknown source"):
        main.parse_lead_fields("twitter", {})
