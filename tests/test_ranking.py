from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.db.models import ServiceCategory, Society, Vendor
from app.db.repositories.vendor_repository import VendorRepository
from app.services.vendor_ranking_service import VendorRankingService
from scripts.seed import seed_id


def test_ranking_priority_and_tie_breaker():
    society = Society(
        id=UUID(int=1),
        name="Megapolis",
        locality="Hinjewadi Phase 3",
        city="Pune",
        state="Maharashtra",
    )

    def vendor(i, same=True, verified=True, rating=Decimal("4.50"), jobs=10):
        return Vendor(
            id=UUID(int=i),
            name="TEST",
            primary_phone="TEST-VENDOR",
            society_id=society.id if same else None,
            locality=society.locality,
            city="Pune",
            active=True,
            verified=verified,
            rating=rating,
            successful_jobs=jobs,
            total_jobs=jobs,
        )

    items = [
        vendor(5, same=False, jobs=99999, rating=Decimal(5)),
        vendor(4, verified=False, rating=Decimal(5)),
        vendor(3, rating=Decimal("4.51"), jobs=0),
        vendor(2, jobs=99999),
        vendor(1, jobs=99999),
    ]
    ranker = VendorRankingService()
    ranked = ranker.rank(items, society)
    assert [r.vendor.id.int for r in ranked] == [3, 1, 2]
    assert ranker.rank(list(reversed(items)), society) == ranked
    assert ranker.score(items[1], society) > ranker.score(items[0], society)


async def test_vendor_eligibility_and_no_maid(sessions, seeded):
    async with sessions() as session:
        society = await session.get(Society, seed_id("society"))
        category = await session.scalar(
            select(ServiceCategory).where(ServiceCategory.slug == "plumber")
        )
        vendors = await VendorRepository.eligible(session, category.id, society)
        ids = {v.id for v in vendors}
        assert seed_id("vendor/19") not in ids  # unavailable plumber relationship
        assert seed_id("vendor/20") not in ids  # inactive vendor
        assert len(vendors) > 3
        maid = await session.scalar(select(ServiceCategory).where(ServiceCategory.slug == "maid"))
        assert await VendorRepository.eligible(session, maid.id, society) == []


async def test_other_city_not_recommended(sessions, seeded):
    async with sessions.begin() as session:
        vendor = await session.get(Vendor, seed_id("vendor/1"))
        vendor.city = "Mumbai"
    async with sessions() as session:
        society = await session.get(Society, seed_id("society"))
        category = await session.get(ServiceCategory, seed_id("category/plumber"))
        eligible = await VendorRepository.eligible(session, category.id, society)
        assert seed_id("vendor/1") not in {v.id for v in eligible}
