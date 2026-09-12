from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.models import RequestStatus


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CategoryResponse(ORMModel):
    id: UUID
    name: str
    slug: str
    description: str | None
    active: bool


class VendorResponse(ORMModel):
    id: UUID
    name: str
    business_name: str | None
    primary_phone: str
    whatsapp_number: str | None
    society_id: UUID | None
    locality: str
    city: str
    description: str | None
    verified: bool
    active: bool
    rating: Decimal | None
    total_jobs: int
    successful_jobs: int


class RecommendationResponse(ORMModel):
    vendor_id: UUID
    rank: int
    ranking_score: Decimal | None
    selected: bool
    contacted: bool


class RequestResponse(ORMModel):
    id: UUID
    resident_id: UUID
    service_category_id: UUID | None
    original_message: str
    interpreted_requirement: str | None
    urgency: str | None
    status: RequestStatus
    locality: str | None
    preferred_time: str | None
    created_at: datetime
    completed_at: datetime | None
    recommendations: list[RecommendationResponse]
