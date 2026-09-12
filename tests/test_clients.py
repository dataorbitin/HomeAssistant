import json

import httpx
import pytest

from app.schemas.intent import Intent
from app.services.ai_service import AIService, AIUnavailable, redact_contacts
from app.services.evolution_service import EvolutionAPIClient, EvolutionDeliveryError


async def test_intent_extraction_schema_and_redaction(settings):
    captured = []

    def handler(request):
        captured.append(json.loads(request.content))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "intent": "FIND_SERVICE",
                                    "service_category": "plumber",
                                    "requirement": "Kitchen sink leaking",
                                    "urgency": "HIGH",
                                }
                            )
                        }
                    }
                ]
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        result = await AIService(settings, client).extract(
            "Hi, need plumber urgently, kitchen sink leaking. Call +1 202 555 0101.",
            [{"role": "assistant", "content": "Contact: 12025550102"}],
            ["plumber", "maid"],
        )
    assert result.intent == Intent.FIND_SERVICE
    assert result.service_category == "plumber" and result.urgency == "HIGH"
    body = str(captured[0])
    assert "12025550102" not in body and "202 555 0101" not in body
    assert "tools" not in captured[0]


@pytest.mark.parametrize(
    "content",
    [
        "not json",
        '{"intent":"SQL","query":"SELECT 1"}',
        '{"intent":"FIND_SERVICE","vendor":"invented"}',
        '{"intent":"FEEDBACK","rating":6}',
    ],
)
async def test_invalid_llm_output(settings, content):
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"choices": [{"message": {"content": content}}]}
            )
        )
    ) as client:
        with pytest.raises(AIUnavailable):
            await AIService(settings, client).extract("help", [], [])


async def test_llm_timeout(settings):
    def handler(request):
        raise httpx.ReadTimeout("never log this private content")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(AIUnavailable):
            await AIService(settings, client).extract("help", [], [])


def test_redaction():
    assert "12025550101" not in redact_contacts("Call 12025550101 please")


async def test_evolution_success_and_contract(settings):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(201, json={"key": {"id": "outbound-1"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert (
            await EvolutionAPIClient(settings, client).send_text_message("12025550101", "Hello")
            == "outbound-1"
        )
    assert calls[0].url.path == "/message/sendText/home-assistance"
    assert calls[0].headers["apikey"] == "mock-evolution-key"
    assert json.loads(calls[0].content) == {"number": "12025550101", "text": "Hello"}


@pytest.mark.parametrize("failure", ["connect", "rate_limit"])
async def test_safe_transient_retry(settings, failure):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        if count == 1:
            if failure == "connect":
                raise httpx.ConnectError("connection failed")
            return httpx.Response(429)
        return httpx.Response(201, json={"key": {"id": "sent"}})

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        assert (
            await EvolutionAPIClient(settings, client).send_text_message("12025550101", "Hello")
            == "sent"
        )
    assert count == 2


@pytest.mark.parametrize("failure,ambiguous", [("timeout", True), ("500", True), ("401", False)])
async def test_evolution_failures_no_unsafe_retry(settings, failure, ambiguous):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        if failure == "timeout":
            raise httpx.ReadTimeout("private payload")
        return httpx.Response(int(failure))

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EvolutionDeliveryError) as exc:
            await EvolutionAPIClient(settings, client).send_text_message("12025550101", "Hello")
    assert count == 1 and exc.value.ambiguous == ambiguous


async def test_seed_phones_cannot_be_sent(settings):
    def handler(request):
        raise AssertionError("Synthetic number must never reach transport")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EvolutionDeliveryError, match="invalid_recipient"):
            await EvolutionAPIClient(settings, client).send_text_message("TEST-VENDOR-001", "Hello")


async def test_evolution_connection_retry_exhausted(settings):
    count = 0

    def handler(request):
        nonlocal count
        count += 1
        raise httpx.ConnectError("offline")

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        with pytest.raises(EvolutionDeliveryError) as exc:
            await EvolutionAPIClient(settings, client).send_text_message("12025550101", "Hello")
    assert count == settings.evolution_max_attempts
    assert exc.value.code == "connect_failed"
    assert not exc.value.ambiguous
