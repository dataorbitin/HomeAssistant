from app.db.repositories.vendor_repository import VendorRepository
from app.services.vendor_ranking_service import VendorRankingService


class VendorService:
    async def recommend(self, session, category, society):
        if category is None:
            return []
        eligible = await VendorRepository.eligible(session, category.id, society)
        return VendorRankingService().rank(eligible, society)
