import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models import Conversation, ServiceRequestVendor
from scripts.seed import seed_id


async def test_single_open_conversation_constraint(sessions, seeded):
    with pytest.raises(IntegrityError):
        async with sessions.begin() as session:
            session.add(Conversation(resident_id=seed_id("resident/1"), status="OPEN"))
            await session.flush()


async def test_fourth_recommendation_rejected_by_database(sessions, seeded):
    with pytest.raises(IntegrityError):
        async with sessions.begin() as session:
            session.add(
                ServiceRequestVendor(
                    service_request_id=seed_id("request/1"), vendor_id=seed_id("vendor/2"), rank=4
                )
            )
            await session.flush()


async def test_duplicate_rank_rejected_by_database(sessions, seeded):
    with pytest.raises(IntegrityError):
        async with sessions.begin() as session:
            session.add(
                ServiceRequestVendor(
                    service_request_id=seed_id("request/1"), vendor_id=seed_id("vendor/2"), rank=1
                )
            )
            await session.flush()
