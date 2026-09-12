from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select

from app.api.dependencies import get_session, require_admin
from app.db.models import RequestStatus, Resident, ServiceRequest
from app.schemas.api import RequestResponse

router = APIRouter(prefix="/api", dependencies=[Depends(require_admin)])


@router.get("/service-requests", response_model=list[RequestResponse])
async def service_requests(
    status: RequestStatus | None = None,
    unmet_demand: bool = False,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session=Depends(get_session),
):
    statement = select(ServiceRequest)
    if status:
        statement = statement.where(ServiceRequest.status == status)
    if unmet_demand:
        statement = statement.where(~ServiceRequest.recommendations.any())
    return (
        await session.scalars(
            statement.order_by(ServiceRequest.created_at.desc(), ServiceRequest.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()


@router.get("/residents/{resident_id}/requests", response_model=list[RequestResponse])
async def resident_requests(
    resident_id: UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    session=Depends(get_session),
):
    if await session.get(Resident, resident_id) is None:
        raise HTTPException(404, "Resident not found")
    return (
        await session.scalars(
            select(ServiceRequest)
            .where(ServiceRequest.resident_id == resident_id)
            .order_by(ServiceRequest.created_at.desc(), ServiceRequest.id)
            .limit(limit)
            .offset(offset)
        )
    ).all()
