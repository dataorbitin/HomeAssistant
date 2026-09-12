from sqlalchemy import select

from app.db.models import Resident, Society
from app.db.repositories.common import insert_for


class ResidentService:
    @staticmethod
    async def find_or_create(session, phone_number: str, default_society_name: str):
        lookup = select(Resident).where(Resident.whatsapp_number == phone_number).with_for_update()
        resident = await session.scalar(lookup)
        if resident is not None:
            return resident
        society_id = await session.scalar(
            select(Society.id).where(
                Society.name == default_society_name,
                Society.locality == "Hinjewadi Phase 3",
                Society.city == "Pune",
                Society.active.is_(True),
            )
        )
        if society_id is None:
            raise RuntimeError("Default society missing; run reference seed")
        await session.execute(
            insert_for(session, Resident)
            .values(whatsapp_number=phone_number, society_id=society_id)
            .on_conflict_do_nothing(index_elements=["whatsapp_number"])
        )
        # Serialize distinct messages from the same resident across processes.
        return await session.scalar(lookup)
