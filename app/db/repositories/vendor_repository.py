from sqlalchemy import func, or_, select

from app.db.models import ServiceCategory, Vendor, VendorService


class VendorRepository:
    @staticmethod
    async def eligible(session, category_id, society):
        if society is None or not society.active:
            return []
        # A different city is not a useful local recommendation.
        statement = (
            select(Vendor)
            .join(VendorService)
            .join(ServiceCategory)
            .where(
                VendorService.service_category_id == category_id,
                Vendor.active.is_(True),
                VendorService.available.is_(True),
                ServiceCategory.active.is_(True),
                func.lower(Vendor.city) == society.city.lower(),
                or_(
                    Vendor.society_id == society.id,
                    func.lower(Vendor.locality) == society.locality.lower(),
                ),
            )
        )
        return list((await session.scalars(statement)).all())
