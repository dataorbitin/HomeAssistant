"""Inspect delivery state or explicitly retry a definitely failed (not ambiguous) send."""

import argparse
import asyncio
import sys
from uuid import UUID

from sqlalchemy import select, update

from app.core.config import Settings
from app.db.models import DeliveryStatus, Message
from app.db.session import create_engine, session_factory


async def run(retry_id=None):
    settings = Settings()
    engine = create_engine(settings.database_url.get_secret_value())
    try:
        async with session_factory(engine).begin() as session:
            if retry_id:
                result = await session.execute(
                    update(Message)
                    .where(
                        Message.id == retry_id,
                        Message.instance == settings.evolution_api_instance,
                        Message.delivery_status == DeliveryStatus.FAILED,
                    )
                    .values(delivery_status=DeliveryStatus.PENDING, delivery_error=None)
                )
                print(
                    f"Queued {result.rowcount} definitely failed message(s). UNKNOWN/SENDING are never retried here."
                )
            else:
                rows = (
                    await session.execute(
                        select(
                            Message.id,
                            Message.delivery_status,
                            Message.delivery_error,
                            Message.created_at,
                        )
                        .where(
                            Message.instance == settings.evolution_api_instance,
                            Message.delivery_status.in_(
                                [
                                    DeliveryStatus.FAILED,
                                    DeliveryStatus.UNKNOWN,
                                    DeliveryStatus.SENDING,
                                    DeliveryStatus.PENDING,
                                ]
                            ),
                        )
                        .order_by(Message.created_at)
                        .limit(100)
                    )
                ).all()
                for row in rows:
                    print(*row)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retry-failed", type=UUID)
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run(args.retry_failed))
