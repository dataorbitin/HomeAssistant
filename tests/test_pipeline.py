import asyncio
from unittest.mock import AsyncMock

from sqlalchemy import func, select

from app.db.models import (
    Conversation,
    DeliveryStatus,
    Direction,
    Message,
    RequestStatus,
    Resident,
    ServiceRequest,
    ServiceRequestVendor,
    VendorFeedback,
)
from app.schemas.intent import Intent, ServiceIntent
from app.services.ai_service import AIUnavailable
from app.services.evolution_service import EvolutionDeliveryError
from tests.conftest import payload


async def test_plumber_end_to_end_and_duplicate(client, sessions, ai, evolution):
    response = await client.post("/webhook/evolution", json=payload())
    assert response.status_code == 200
    assert response.json()["processed"] == 1
    async with sessions() as session:
        resident = await session.scalar(
            select(Resident).where(Resident.whatsapp_number == "12025550101")
        )
        assert resident is not None and resident.id and resident.society.name == "Megapolis"
        assert (
            await session.scalar(
                select(func.count())
                .select_from(Conversation)
                .where(Conversation.resident_id == resident.id)
            )
            == 1
        )
        messages = list(
            (await session.scalars(select(Message).where(Message.resident_id == resident.id))).all()
        )
        assert len(messages) == 2
        inbound = next(m for m in messages if m.direction == Direction.INBOUND)
        outbound = next(m for m in messages if m.direction == Direction.OUTBOUND)
        assert inbound.message_text == payload()["data"]["message"]["conversation"]
        assert inbound.received_at is not None and inbound.raw_payload is None
        assert outbound.delivery_status == DeliveryStatus.SENT
        assert outbound.in_reply_to_id == inbound.id
        request = await session.scalar(
            select(ServiceRequest).where(ServiceRequest.resident_id == resident.id)
        )
        assert request.status == RequestStatus.VENDORS_SHARED
        assert request.urgency == "HIGH"
        assert len(request.recommendations) == 3
        assert [r.rank for r in request.recommendations] == [1, 2, 3]
        assert "Contact: TEST-VENDOR-" in outbound.message_text
        assert "TEST-VENDOR-019" not in outbound.message_text
        assert "TEST-VENDOR-020" not in outbound.message_text
    duplicate = await client.post("/webhook/evolution", json=payload())
    assert duplicate.json()["processed"] == 0
    assert evolution.send_text_message.await_count == 1
    assert ai.extract.await_count == 1
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(ServiceRequest)) == 7
        assert await session.scalar(select(func.count()).select_from(Message)) == 14


async def test_maid_unmet_demand(client, sessions, evolution):
    assert (await client.post("/webhook/evolution", json=payload("Need maid"))).status_code == 200
    async with sessions() as session:
        request = await session.scalar(
            select(ServiceRequest)
            .where(
                ServiceRequest.original_message == "Need maid",
                ServiceRequest.source_message_id.is_not(None),
            )
            .order_by(ServiceRequest.created_at.desc())
        )
        assert request.status == RequestStatus.NEW
        assert request.recommendations == []
    reply = evolution.send_text_message.call_args.args[1]
    assert "maid contact available in Megapolis yet" in reply
    assert "recorded your requirement" in reply
    assert "Contact:" not in reply


async def test_unknown_category_is_stored(client, sessions, ai, evolution):
    ai.extract.side_effect = None
    ai.extract.return_value = ServiceIntent(
        intent=Intent.FIND_SERVICE, service_category="dog-walker", requirement="Walk my dog"
    )
    await client.post("/webhook/evolution", json=payload("Need dog walker"))
    async with sessions() as session:
        request = await session.scalar(
            select(ServiceRequest).where(ServiceRequest.original_message == "Need dog walker")
        )
        assert request.service_category_id is None
        assert request.status == RequestStatus.NEW
        assert request.recommendations == []


async def test_concurrent_duplicate(client, sessions, evolution):
    responses = await asyncio.gather(
        *[client.post("/webhook/evolution", json=payload()) for _ in range(5)]
    )
    assert all(response.status_code == 200 for response in responses)
    assert sum(response.json()["processed"] for response in responses) == 1
    assert evolution.send_text_message.await_count == 1
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Message)) == 14


async def test_greeting_and_context_bound(client, settings, ai):
    settings.max_context_messages = 1
    settings.max_context_characters = 10
    ai.extract.side_effect = None
    ai.extract.return_value = ServiceIntent(intent=Intent.GREETING)
    for i in range(3):
        await client.post("/webhook/evolution", json=payload("Hello", f"greeting-{i}"))
    history = ai.extract.call_args.args[1]
    assert len(history) == 1
    assert sum(len(item["content"]) for item in history) <= 10


async def test_llm_failure_is_safe_and_idempotent(client, sessions, ai, evolution):
    ai.extract.side_effect = AIUnavailable()
    await client.post("/webhook/evolution", json=payload())
    await client.post("/webhook/evolution", json=payload())
    assert evolution.send_text_message.await_count == 1
    assert "new message" in evolution.send_text_message.call_args.args[1]
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(ServiceRequest)) == 6


async def test_ambiguous_send_never_retried(client, sessions, evolution):
    evolution.send_text_message.side_effect = EvolutionDeliveryError(
        "transport_unknown", ambiguous=True
    )
    await client.post("/webhook/evolution", json=payload())
    await client.post("/webhook/evolution", json=payload())
    assert evolution.send_text_message.await_count == 1
    async with sessions() as session:
        pending = await session.scalar(
            select(Message).where(Message.external_message_id == "test-message-1")
        )
        outbound = await session.scalar(select(Message).where(Message.in_reply_to_id == pending.id))
        assert outbound.delivery_status == DeliveryStatus.UNKNOWN
        assert await session.scalar(select(func.count()).select_from(ServiceRequest)) == 7


async def test_feedback_and_contact_tracking(client, sessions, ai, evolution):
    evolution.send_text_message = AsyncMock(return_value=None)
    await client.post("/webhook/evolution", json=payload())
    ai.extract.side_effect = None
    ai.extract.return_value = ServiceIntent(
        intent=Intent.FEEDBACK, recommendation_rank=1, contacted=True
    )
    await client.post("/webhook/evolution", json=payload("I contacted vendor 1", "contact-1"))
    ai.extract.return_value = ServiceIntent(
        intent=Intent.FEEDBACK, recommendation_rank=1, rating=5, feedback="Great job"
    )
    await client.post("/webhook/evolution", json=payload("Vendor 1 gets 5 stars", "feedback-1"))
    await client.post("/webhook/evolution", json=payload("Vendor 1 gets 5 stars", "feedback-1"))
    async with sessions() as session:
        resident = await session.scalar(
            select(Resident).where(Resident.whatsapp_number == "12025550101")
        )
        request = await session.scalar(
            select(ServiceRequest).where(ServiceRequest.resident_id == resident.id)
        )
        assert request.status == RequestStatus.COMPLETED and request.completed_at
        assert request.recommendations[0].contacted
        assert (
            await session.scalar(
                select(func.count())
                .select_from(VendorFeedback)
                .where(VendorFeedback.resident_id == resident.id)
            )
            == 1
        )
        assert (
            await session.scalar(
                select(func.count())
                .select_from(ServiceRequestVendor)
                .where(ServiceRequestVendor.service_request_id == request.id)
            )
            == 3
        )
