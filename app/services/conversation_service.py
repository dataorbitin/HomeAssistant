from sqlalchemy import or_, select, text

from app.db.models import Conversation, DeliveryStatus, Direction, Message, utcnow
from app.db.repositories.common import insert_for


class ConversationService:
    @staticmethod
    async def find_or_create(session, resident_id):
        await session.execute(
            insert_for(session, Conversation)
            .values(
                resident_id=resident_id,
                status="OPEN",
            )
            .on_conflict_do_nothing(
                index_elements=["resident_id"], index_where=text("status = 'OPEN'")
            )
        )
        conversation = await session.scalar(
            select(Conversation).where(
                Conversation.resident_id == resident_id, Conversation.status == "OPEN"
            )
        )
        conversation.last_message_at = utcnow()
        return conversation

    @staticmethod
    async def recent_context(session, conversation_id, settings):
        if settings.max_context_messages == 0 or settings.max_context_characters == 0:
            return []
        rows = list(
            (
                await session.scalars(
                    select(Message)
                    .where(
                        Message.conversation_id == conversation_id,
                        or_(
                            Message.direction == Direction.INBOUND,
                            Message.delivery_status == DeliveryStatus.SENT,
                        ),
                    )
                    .order_by(Message.created_at.desc(), Message.id.desc())
                    .limit(settings.max_context_messages)
                )
            ).all()
        )
        remaining = settings.max_context_characters
        history = []
        for message in rows:
            if remaining <= 0:
                break
            content = message.message_text[:remaining]
            remaining -= len(content)
            history.append(
                {
                    "role": "user" if message.direction == Direction.INBOUND else "assistant",
                    "content": content,
                }
            )
        return list(reversed(history))
