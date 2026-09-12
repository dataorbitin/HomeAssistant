import asyncio
import logging
from datetime import timedelta

from sqlalchemy import select, update

from app.db.models import (
    DeliveryStatus,
    Direction,
    Message,
    RequestStatus,
    Resident,
    ServiceRequest,
    utcnow,
)
from app.services.evolution_service import EvolutionDeliveryError

log = logging.getLogger(__name__)


class OutboxService:
    def __init__(self, sessions, evolution, settings):
        self.sessions, self.evolution, self.settings = sessions, evolution, settings

    async def deliver(self, message_id):
        # Commit the claim BEFORE the remote side effect. CAS allows many workers.
        async with self.sessions.begin() as session:
            claimed = await session.scalar(
                update(Message)
                .where(
                    Message.id == message_id,
                    Message.direction == Direction.OUTBOUND,
                    Message.instance == self.settings.evolution_api_instance,
                    Message.delivery_status == DeliveryStatus.PENDING,
                )
                .values(delivery_status=DeliveryStatus.SENDING, delivery_attempted_at=utcnow())
                .returning(Message.id)
            )
            if claimed is None:
                return
            message = await session.get(Message, message_id)
            resident = await session.get(Resident, message.resident_id)
            phone, body, inbound_id = (
                resident.whatsapp_number,
                message.message_text,
                message.in_reply_to_id,
            )
        external_id, error = None, None
        try:
            external_id = await self.evolution.send_text_message(phone, body)
            status = DeliveryStatus.SENT
        except EvolutionDeliveryError as exc:
            status = DeliveryStatus.UNKNOWN if exc.ambiguous else DeliveryStatus.FAILED
            error = exc.code
        except Exception:
            status, error = DeliveryStatus.UNKNOWN, "unexpected_transport_failure"
        async with self.sessions.begin() as session:
            await session.execute(
                update(Message)
                .where(Message.id == message_id, Message.delivery_status == DeliveryStatus.SENDING)
                .values(
                    delivery_status=status, external_message_id=external_id, delivery_error=error
                )
            )
            if status == DeliveryStatus.SENT and inbound_id:
                await session.execute(
                    update(ServiceRequest)
                    .where(
                        ServiceRequest.source_message_id == inbound_id,
                        ServiceRequest.status == RequestStatus.MATCHING,
                    )
                    .values(status=RequestStatus.VENDORS_SHARED)
                )
        log.info("outbound_delivery status=%s", status.value)

    async def tick(self):
        async with self.sessions.begin() as session:
            # Crash while sending: unknown, never automatically resend.
            await session.execute(
                update(Message)
                .where(
                    Message.instance == self.settings.evolution_api_instance,
                    Message.delivery_status == DeliveryStatus.SENDING,
                    Message.delivery_attempted_at < utcnow() - timedelta(minutes=10),
                )
                .values(delivery_status=DeliveryStatus.UNKNOWN, delivery_error="stale_send_claim")
            )
            ids = list(
                (
                    await session.scalars(
                        select(Message.id)
                        .where(
                            Message.instance == self.settings.evolution_api_instance,
                            Message.delivery_status == DeliveryStatus.PENDING,
                        )
                        .order_by(Message.created_at, Message.id)
                        .limit(20)
                    )
                ).all()
            )
        for message_id in ids:
            await self.deliver(message_id)

    async def run(self):
        while True:
            try:
                await self.tick()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                log.error("outbox_poll_failed error=%s", type(exc).__name__)
            await asyncio.sleep(self.settings.outbox_poll_seconds)
