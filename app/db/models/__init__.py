import enum
import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    false,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow():
    return datetime.now(UTC)


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "ix": "ix_%(table_name)s_%(column_0_name)s",
            "uq": "uq_%(table_name)s_%(column_0_N_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "pk": "pk_%(table_name)s",
        }
    )


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now(), onupdate=utcnow
    )


class RequestStatus(enum.StrEnum):
    NEW = "NEW"
    MATCHING = "MATCHING"
    VENDORS_SHARED = "VENDORS_SHARED"
    CONTACTED = "CONTACTED"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"


class Direction(enum.StrEnum):
    INBOUND = "INBOUND"
    OUTBOUND = "OUTBOUND"


class DeliveryStatus(enum.StrEnum):
    PENDING = "PENDING"
    SENDING = "SENDING"
    SENT = "SENT"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"


def enum_column(kind):
    return Enum(kind, native_enum=False, create_constraint=True, name=kind.__name__.lower())


class Society(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "societies"
    __table_args__ = (UniqueConstraint("name", "locality", "city"),)
    name: Mapped[str] = mapped_column(String(120))
    locality: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(80))
    state: Mapped[str] = mapped_column(String(80))
    pincode: Mapped[str | None] = mapped_column(String(12))
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    residents: Mapped[list["Resident"]] = relationship(back_populates="society")


class Resident(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "residents"
    whatsapp_number: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    name: Mapped[str | None] = mapped_column(String(120))
    society_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("societies.id", ondelete="RESTRICT")
    )
    building: Mapped[str | None] = mapped_column(String(80))
    flat_number: Mapped[str | None] = mapped_column(String(40))
    preferred_language: Mapped[str] = mapped_column(String(10), default="en", server_default="en")
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    society: Mapped[Society | None] = relationship(back_populates="residents", lazy="selectin")
    requests: Mapped[list["ServiceRequest"]] = relationship(back_populates="resident")


class ServiceCategory(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "service_categories"
    name: Mapped[str] = mapped_column(String(100))
    slug: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    vendor_services: Mapped[list["VendorService"]] = relationship(back_populates="category")


class Vendor(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "vendors"
    __table_args__ = (
        CheckConstraint("rating IS NULL OR (rating >= 1 AND rating <= 5)", name="rating_range"),
        CheckConstraint(
            "total_jobs >= 0 AND successful_jobs >= 0 AND successful_jobs <= total_jobs",
            name="valid_jobs",
        ),
    )
    name: Mapped[str] = mapped_column(String(120))
    business_name: Mapped[str | None] = mapped_column(String(160))
    primary_phone: Mapped[str] = mapped_column(String(40))
    whatsapp_number: Mapped[str | None] = mapped_column(String(40))
    society_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("societies.id", ondelete="RESTRICT")
    )
    locality: Mapped[str] = mapped_column(String(120))
    city: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text)
    verified: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), index=True)
    rating: Mapped[Decimal | None] = mapped_column(Numeric(3, 2))
    total_jobs: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    successful_jobs: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    services: Mapped[list["VendorService"]] = relationship(back_populates="vendor")


class VendorService(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "vendor_services"
    __table_args__ = (
        UniqueConstraint("vendor_id", "service_category_id"),
        CheckConstraint("price_min IS NULL OR price_min >= 0", name="price_min_nonnegative"),
        CheckConstraint("price_max IS NULL OR price_max >= 0", name="price_max_nonnegative"),
        CheckConstraint(
            "price_min IS NULL OR price_max IS NULL OR price_max >= price_min", name="price_order"
        ),
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("vendors.id", ondelete="CASCADE"), index=True
    )
    service_category_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_categories.id", ondelete="RESTRICT"), index=True
    )
    price_min: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    price_max: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    pricing_unit: Mapped[str | None] = mapped_column(String(60))
    description: Mapped[str | None] = mapped_column(Text)
    available: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true())
    vendor: Mapped[Vendor] = relationship(back_populates="services")
    category: Mapped[ServiceCategory] = relationship(back_populates="vendor_services")


class ServiceRequest(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "service_requests"
    resident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("residents.id", ondelete="RESTRICT"), index=True
    )
    service_category_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("service_categories.id", ondelete="RESTRICT")
    )
    source_message_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="RESTRICT"), unique=True
    )
    original_message: Mapped[str] = mapped_column(Text)
    interpreted_requirement: Mapped[str | None] = mapped_column(Text)
    urgency: Mapped[str | None] = mapped_column(String(20))
    status: Mapped[RequestStatus] = mapped_column(
        enum_column(RequestStatus), default=RequestStatus.NEW, server_default="NEW", index=True
    )
    locality: Mapped[str | None] = mapped_column(String(120))
    preferred_time: Mapped[str | None] = mapped_column(String(120))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    resident: Mapped[Resident] = relationship(back_populates="requests")
    recommendations: Mapped[list["ServiceRequestVendor"]] = relationship(
        back_populates="request", lazy="selectin", order_by="ServiceRequestVendor.rank"
    )


class ServiceRequestVendor(UUIDMixin, Base):
    __tablename__ = "service_request_vendors"
    __table_args__ = (
        UniqueConstraint("service_request_id", "vendor_id"),
        UniqueConstraint("service_request_id", "rank"),
        CheckConstraint("rank >= 1 AND rank <= 3", name="rank_range"),
    )
    service_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_requests.id", ondelete="CASCADE")
    )
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id", ondelete="RESTRICT"))
    rank: Mapped[int] = mapped_column(Integer)
    ranking_score: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    selected: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    contacted: Mapped[bool] = mapped_column(Boolean, default=False, server_default=false())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    request: Mapped[ServiceRequest] = relationship(back_populates="recommendations")


class Conversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        CheckConstraint("status IN ('OPEN', 'CLOSED')", name="valid_status"),
        Index(
            "uq_conversations_open_resident",
            "resident_id",
            unique=True,
            postgresql_where=text("status = 'OPEN'"),
            sqlite_where=text("status = 'OPEN'"),
        ),
    )
    resident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("residents.id", ondelete="RESTRICT"), index=True
    )
    status: Mapped[str] = mapped_column(String(20), default="OPEN", server_default="OPEN")
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    last_message_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    messages: Mapped[list["Message"]] = relationship(back_populates="conversation")


class Message(UUIDMixin, Base):
    __tablename__ = "messages"
    __table_args__ = (
        UniqueConstraint("instance", "direction", "external_message_id"),
        Index("ix_messages_delivery_created", "delivery_status", "created_at"),
        CheckConstraint(
            "(direction = 'INBOUND' AND delivery_status IS NULL) OR "
            "(direction = 'OUTBOUND' AND delivery_status IS NOT NULL)",
            name="delivery_direction",
        ),
    )
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="RESTRICT"), index=True
    )
    resident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("residents.id", ondelete="RESTRICT"))
    instance: Mapped[str] = mapped_column(String(120))
    external_message_id: Mapped[str | None] = mapped_column(String(200), index=True)
    in_reply_to_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("messages.id", ondelete="RESTRICT"), unique=True
    )
    direction: Mapped[Direction] = mapped_column(enum_column(Direction))
    message_type: Mapped[str] = mapped_column(String(30), default="text", server_default="text")
    message_text: Mapped[str] = mapped_column(Text)
    raw_payload: Mapped[dict | None] = mapped_column(JSON().with_variant(JSONB(), "postgresql"))
    delivery_status: Mapped[DeliveryStatus | None] = mapped_column(enum_column(DeliveryStatus))
    delivery_error: Mapped[str | None] = mapped_column(String(60))
    delivery_attempted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    received_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
    conversation: Mapped[Conversation] = relationship(back_populates="messages")


class VendorFeedback(UUIDMixin, Base):
    __tablename__ = "vendor_feedback"
    __table_args__ = (
        CheckConstraint("rating >= 1 AND rating <= 5", name="rating_range"),
        UniqueConstraint("service_request_id", "resident_id", "vendor_id"),
    )
    service_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("service_requests.id", ondelete="RESTRICT")
    )
    resident_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("residents.id", ondelete="RESTRICT"))
    vendor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("vendors.id", ondelete="RESTRICT"))
    rating: Mapped[int] = mapped_column(Integer)
    feedback: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, server_default=func.now()
    )
