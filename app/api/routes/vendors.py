from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.api.dependencies import get_session, require_admin
from app.db.models import ServiceCategory, Vendor, VendorService
from app.schemas.api import VendorResponse

router = APIRouter(prefix="/api/vendors", dependencies=[Depends(require_admin)])


@router.get("", response_model=list[VendorResponse])
async def vendors(
    service: str | None = Query(None, max_length=80),
    society_id: UUID | None = None,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session=Depends(get_session),
):
    statement = select(Vendor).where(Vendor.active.is_(True))
    if service:
        statement = (
            statement.join(VendorService)
            .join(ServiceCategory)
            .where(
                ServiceCategory.slug == service,
                ServiceCategory.active.is_(True),
                VendorService.available.is_(True),
            )
        )
    if society_id:
        statement = statement.where(Vendor.society_id == society_id)
    return (
        await session.scalars(
            statement.order_by(Vendor.name, Vendor.id).limit(limit).offset(offset)
        )
    ).all()


@router.get("/{vendor_id}", response_model=VendorResponse)
async def vendor(vendor_id: UUID, session=Depends(get_session)):
    result = await session.get(Vendor, vendor_id)
    if result is None:
        raise HTTPException(404, "Vendor not found")
    return result
