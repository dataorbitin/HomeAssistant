from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.dependencies import get_session, require_admin
from app.db.models import ServiceCategory
from app.schemas.api import CategoryResponse

router = APIRouter(prefix="/api/services", dependencies=[Depends(require_admin)])


@router.get("", response_model=list[CategoryResponse])
async def services(session=Depends(get_session)):
    return (
        await session.scalars(
            select(ServiceCategory)
            .where(ServiceCategory.active.is_(True))
            .order_by(ServiceCategory.name)
        )
    ).all()
