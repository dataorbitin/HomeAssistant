import asyncio
from datetime import timedelta

from sqlalchemy import select

from app.db.models import DeliveryStatus, Direction, Message, utcnow
from app.schemas.webhook import parse_webhook
from app.services.message_service import MessageService
from app.services.outbox_service import OutboxService
from tests.conftest import payload


async def test_pending_outbox_survives_restart(sessions, seeded, settings, ai, evolution):
    incoming = parse_webhook(payload(), settings.evolution_api_instance)[0]
    async with sessions.begin() as session:
        outbound_id = await MessageService(settings, ai).process(session, incoming)
    # No send occurred before commit. A new worker recovers the pending row.
    evolution.send_text_message.assert_not_called()
    worker = OutboxService(sessions, evolution, settings)
    await worker.tick()
    await OutboxService(sessions, evolution, settings).tick()
    assert evolution.send_text_message.await_count == 1
    async with sessions() as session:
        assert (await session.get(Message, outbound_id)).delivery_status == DeliveryStatus.SENT


async def test_concurrent_delivery_claim(sessions, seeded, settings, ai, evolution):
    async with sessions.begin() as session:
        outbound_id = await MessageService(settings, ai).process(
            session, parse_webhook(payload(), settings.evolution_api_instance)[0]
        )
    workers = [OutboxService(sessions, evolution, settings) for _ in range(4)]
    await asyncio.gather(*[worker.deliver(outbound_id) for worker in workers])
    assert evolution.send_text_message.await_count == 1


async def test_stale_claim_not_resent(sessions, seeded, settings, ai, evolution):
    async with sessions.begin() as session:
        outbound_id = await MessageService(settings, ai).process(
            session, parse_webhook(payload(), settings.evolution_api_instance)[0]
        )
        message = await session.get(Message, outbound_id)
        message.delivery_status = DeliveryStatus.SENDING
        message.delivery_attempted_at = utcnow() - timedelta(minutes=11)
    await OutboxService(sessions, evolution, settings).tick()
    evolution.send_text_message.assert_not_called()
    async with sessions() as session:
        assert (await session.get(Message, outbound_id)).delivery_status == DeliveryStatus.UNKNOWN


async def test_transaction_rolls_back_on_processing_failure(sessions, seeded, settings, ai):
    ai.extract.side_effect = RuntimeError("unexpected failure")
    try:
        async with sessions.begin() as session:
            await MessageService(settings, ai).process(
                session, parse_webhook(payload(), settings.evolution_api_instance)[0]
            )
    except RuntimeError:
        pass
    async with sessions() as session:
        assert (
            await session.scalar(
                select(Message.id).where(
                    Message.direction == Direction.INBOUND,
                    Message.external_message_id == "test-message-1",
                )
            )
            is None
        )


async def test_definite_failure_stored_without_duplicate_send(
    sessions, seeded, settings, ai, evolution
):
    from app.services.evolution_service import EvolutionDeliveryError

    async with sessions.begin() as session:
        outbound_id = await MessageService(settings, ai).process(
            session, parse_webhook(payload(), settings.evolution_api_instance)[0]
        )
    evolution.send_text_message.side_effect = EvolutionDeliveryError("upstream_rejected")
    worker = OutboxService(sessions, evolution, settings)
    await worker.tick()
    await worker.tick()
    evolution.send_text_message.assert_awaited_once()
    async with sessions() as session:
        message = await session.get(Message, outbound_id)
        assert message.delivery_status == DeliveryStatus.FAILED
        assert message.delivery_error == "upstream_rejected"
