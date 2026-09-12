from dataclasses import dataclass
from decimal import Decimal

from app.db.models import Society, Vendor


@dataclass(frozen=True)
class RankedVendor:
    vendor: Vendor
    score: Decimal


class VendorRankingService:
    """Lexicographic priorities encoded without letting job count swamp locality."""

    @staticmethod
    def score(vendor: Vendor, society: Society) -> Decimal:
        location = (
            2
            if vendor.society_id == society.id
            else 1
            if vendor.locality.casefold() == society.locality.casefold()
            else 0
        )
        # Rating is stored to two decimals; jobs are capped below one rating step.
        return (
            Decimal(location * 10_000_000 + int(vendor.verified) * 1_000_000)
            + Decimal(vendor.rating or 0) * 100_000
            + Decimal(min(vendor.successful_jobs, 999))
        )

    def rank(self, vendors: list[Vendor], society: Society) -> list[RankedVendor]:
        ranked = [
            RankedVendor(vendor, self.score(vendor, society)) for vendor in vendors if vendor.active
        ]
        return sorted(ranked, key=lambda item: (-item.score, str(item.vendor.id)))[:3]
