import copy

import pytest

from app.schemas.webhook import parse_webhook
from tests.conftest import payload


@pytest.mark.parametrize(
    "variant",
    [
        "own",
        "group",
        "lid",
        "broadcast",
        "missing_from_me",
        "missing_id",
        "blank_id",
        "media",
        "wrong_instance",
        "event",
        "bad_key",
        "bad_message",
        "bad_data",
        "bad_phone",
        "long_text",
    ],
)
def test_ignored_payloads(variant):
    value = payload()
    if variant == "own":
        value["data"]["key"]["fromMe"] = True
    elif variant in {"group", "lid", "broadcast"}:
        value["data"]["key"]["remoteJid"] = (
            "12025550101@" + {"group": "g.us", "lid": "lid", "broadcast": "broadcast"}[variant]
        )
    elif variant == "missing_from_me":
        del value["data"]["key"]["fromMe"]
    elif variant == "missing_id":
        del value["data"]["key"]["id"]
    elif variant == "blank_id":
        value["data"]["key"]["id"] = " "
    elif variant == "media":
        value["data"]["message"] = {"imageMessage": {}}
    elif variant == "wrong_instance":
        value["instance"] = "other"
    elif variant == "event":
        value["event"] = "connection.update"
    elif variant == "bad_key":
        value["data"]["key"] = []
    elif variant == "bad_message":
        value["data"]["message"] = "bad"
    elif variant == "bad_data":
        value["data"] = 17
    elif variant == "bad_phone":
        value["data"]["key"]["remoteJid"] = "TEST-RESIDENT-001@s.whatsapp.net"
    elif variant == "long_text":
        value["data"]["message"]["conversation"] = "x" * 4097
    assert parse_webhook(value, "home-assistance") == []


def test_extended_text_timestamp_and_batch():
    value = payload()
    value["event"] = "messages.upsert"
    value["data"]["message"] = {"extendedTextMessage": {"text": "नमस्कार"}}
    second = copy.deepcopy(value["data"])
    second["key"]["id"] = "second"
    second["messageTimestamp"] = float("inf")
    value["data"] = [None, value["data"], second]
    entries = parse_webhook(value, "home-assistance")
    assert len(entries) == 2
    assert entries[0].text == "नमस्कार" and entries[0].timestamp
    assert entries[1].timestamp is None


@pytest.mark.parametrize("body", ["{", "[]", "null", '"text"'])
async def test_malformed_webhook(client, evolution, body):
    response = await client.post("/webhook/evolution", content=body)
    assert response.status_code == 400
    evolution.send_text_message.assert_not_called()


async def test_secret_and_size(client, evolution):
    response = await client.post(
        "/webhook/evolution", json=payload(), headers={"x-webhook-secret": "wrong"}
    )
    assert response.status_code == 401
    response = await client.post("/webhook/evolution", content="x" * 262145)
    assert response.status_code == 413
    evolution.send_text_message.assert_not_called()


async def test_legacy_token_auth(client, settings):
    client.headers.pop("x-webhook-secret")
    result = await client.post(
        "/webhook/evolution",
        json=payload(),
        params={"token": settings.webhook_secret.get_secret_value()},
    )
    assert result.status_code == 200


async def test_irrelevant_event_acknowledged(client, ai):
    value = payload()
    value["event"] = "CONNECTION_UPDATE"
    response = await client.post("/webhook/evolution", json=value)
    assert response.json()["status"] == "ignored"
    ai.extract.assert_not_called()
