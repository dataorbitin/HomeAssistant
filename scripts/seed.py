"""Repeatable fictional dataset. Run python -m scripts.seed; never contacts external APIs."""

import argparse
import asyncio
import sys
from datetime import timedelta
from decimal import Decimal
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import func, select

from app.core.config import Settings
from app.db.models import (
    Conversation,
    DeliveryStatus,
    Direction,
    Message,
    RequestStatus,
    Resident,
    ServiceCategory,
    ServiceRequest,
    ServiceRequestVendor,
    Society,
    Vendor,
    VendorFeedback,
    VendorService,
    utcnow,
)
from app.db.repositories.common import insert_for
from app.db.session import create_engine, session_factory

CATEGORIES = [
    ("Plumber", "plumber"),
    ("Electrician", "electrician"),
    ("Cleaning", "cleaning"),
    ("Carpenter", "carpenter"),
    ("AC Repair", "ac-repair"),
    ("Appliance Repair", "appliance-repair"),
    ("RO / Water Purifier", "ro-water-purifier"),
    ("Pest Control", "pest-control"),
    ("Packers & Movers", "packers-movers"),
    ("Maid", "maid"),
    ("Cook", "cook"),
    ("Babysitter", "babysitter"),
    ("Painting", "painting"),
    ("Internet / Broadband", "internet-broadband"),
    ("Locksmith", "locksmith"),
]


def seed_id(label):
    return uuid5(NAMESPACE_URL, "home-assistant-fictional-seed/" + label)


async def insert_once(session, model, **values):
    await session.execute(insert_for(session, model).values(**values).on_conflict_do_nothing())


async def seed_reference(session):
    await insert_once(
        session,
        Society,
        id=seed_id("society"),
        name="Megapolis",
        locality="Hinjewadi Phase 3",
        city="Pune",
        state="Maharashtra",
    )
    society_id = await session.scalar(
        select(Society.id).where(
            Society.name == "Megapolis",
            Society.locality == "Hinjewadi Phase 3",
            Society.city == "Pune",
        )
    )
    category_ids = {}
    for name, slug in CATEGORIES:
        await insert_once(
            session,
            ServiceCategory,
            id=seed_id("category/" + slug),
            name=name,
            slug=slug,
            description=f"Local {name.lower()} services",
        )
        category_ids[slug] = await session.scalar(
            select(ServiceCategory.id).where(ServiceCategory.slug == slug)
        )
    return society_id, category_ids


async def seed_demo(session):
    society_id, categories = await seed_reference(session)
    timestamp = utcnow() - timedelta(days=30)
    for i in range(1, 6):
        await insert_once(
            session,
            Resident,
            id=seed_id(f"resident/{i}"),
            whatsapp_number=f"TEST-RESIDENT-{i:03}",
            name=f"Fictional Resident {i:02}",
            society_id=society_id,
            building="Demo Tower",
            flat_number=f"TEST-{i}",
        )
        await insert_once(
            session,
            Conversation,
            id=seed_id(f"conversation/{i}"),
            resident_id=seed_id(f"resident/{i}"),
            status="OPEN",
            started_at=timestamp,
            last_message_at=timestamp,
        )
    supported = [slug for _, slug in CATEGORIES if slug != "maid"]
    for i in range(1, 21):
        await insert_once(
            session,
            Vendor,
            id=seed_id(f"vendor/{i}"),
            name=f"Fictional Vendor {i:02}",
            business_name=f"TEST Home Services {i:02}",
            primary_phone=f"TEST-VENDOR-{i:03}",
            whatsapp_number=f"TEST-VENDOR-{i:03}",
            society_id=society_id if i % 3 else None,
            locality="Hinjewadi Phase 3",
            city="Pune",
            description="FICTIONAL DEVELOPMENT DATA - NOT A REAL PROVIDER",
            verified=i % 4 != 0,
            active=i != 20,
            rating=None if i == 18 else Decimal(35 + i % 16) / 10,
            total_jobs=i * 12,
            successful_jobs=i * 10,
        )
        first = "plumber" if i <= 6 or i >= 19 else supported[(i - 1) % len(supported)]
        second = supported[(supported.index(first) + 1) % len(supported)]
        for slug in (first, second):
            await insert_once(
                session,
                VendorService,
                id=seed_id(f"vendor-service/{i}/{slug}"),
                vendor_id=seed_id(f"vendor/{i}"),
                service_category_id=categories[slug],
                price_min=Decimal(100 + i * 10),
                price_max=Decimal(300 + i * 10),
                pricing_unit="test visit",
                available=not (i == 19 and slug == "plumber"),
            )
    for i in range(1, 7):
        resident_index = i if i <= 5 else 1
        resident_id = seed_id(f"resident/{resident_index}")
        conversation_id = seed_id(f"conversation/{resident_index}")
        inbound_id = seed_id(f"message/in/{i}")
        request_id = seed_id(f"request/{i}")
        unmet = i == 6
        body = "Need maid" if unmet else "TEST historical plumber request"
        await insert_once(
            session,
            Message,
            id=inbound_id,
            resident_id=resident_id,
            conversation_id=conversation_id,
            instance="fictional-seed",
            external_message_id=f"TEST-INBOUND-{i}",
            direction=Direction.INBOUND,
            message_text=body,
            created_at=timestamp,
        )
        await insert_once(
            session,
            ServiceRequest,
            id=request_id,
            resident_id=resident_id,
            service_category_id=categories["maid" if unmet else "plumber"],
            source_message_id=inbound_id,
            original_message=body,
            interpreted_requirement=body,
            urgency="NORMAL",
            status=RequestStatus.NEW if unmet else RequestStatus.COMPLETED,
            locality="Hinjewadi Phase 3",
            created_at=timestamp,
            completed_at=None if unmet else timestamp + timedelta(days=1),
        )
        if not unmet:
            await insert_once(
                session,
                ServiceRequestVendor,
                id=seed_id(f"recommendation/{i}"),
                service_request_id=request_id,
                vendor_id=seed_id(f"vendor/{i}"),
                rank=1,
                ranking_score=Decimal(100),
                selected=True,
                contacted=True,
            )
            await insert_once(
                session,
                VendorFeedback,
                id=seed_id(f"feedback/{i}"),
                service_request_id=request_id,
                resident_id=resident_id,
                vendor_id=seed_id(f"vendor/{i}"),
                rating=3 + i % 3,
                feedback="FICTIONAL test feedback",
                created_at=timestamp,
            )
        await insert_once(
            session,
            Message,
            id=seed_id(f"message/out/{i}"),
            resident_id=resident_id,
            conversation_id=conversation_id,
            instance="fictional-seed",
            in_reply_to_id=inbound_id,
            external_message_id=f"TEST-OUTBOUND-{i}",
            direction=Direction.OUTBOUND,
            delivery_status=DeliveryStatus.SENT,
            message_text="TEST historical response; no WhatsApp message was sent",
            created_at=timestamp,
        )
    counts = {}
    for model in (
        Society,
        Resident,
        ServiceCategory,
        Vendor,
        VendorService,
        ServiceRequest,
        ServiceRequestVendor,
        Conversation,
        Message,
        VendorFeedback,
    ):
        counts[model.__tablename__] = await session.scalar(select(func.count()).select_from(model))
    return counts


async def run(reference_only=False):
    settings = Settings()
    if settings.app_env == "production" and not reference_only:
        raise SystemExit("Dummy seeding is disabled in production. Use --reference-only.")
    engine = create_engine(settings.database_url.get_secret_value())
    try:
        async with session_factory(engine).begin() as session:
            if reference_only:
                await seed_reference(session)
                print("Reference society and categories ready.")
            else:
                print(await seed_demo(session))
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference-only", action="store_true")
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run(args.reference_only))
