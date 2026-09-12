"""initial concierge schema

Revision ID: 0001
Revises:
"""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "service_categories",
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_categories")),
    )
    op.create_index(op.f("ix_service_categories_slug"), "service_categories", ["slug"], unique=True)
    op.create_table(
        "societies",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("locality", sa.String(length=120), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("state", sa.String(length=80), nullable=False),
        sa.Column("pincode", sa.String(length=12), nullable=True),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_societies")),
        sa.UniqueConstraint(
            "name", "locality", "city", name=op.f("uq_societies_name_locality_city")
        ),
    )
    op.create_table(
        "residents",
        sa.Column("whatsapp_number", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=True),
        sa.Column("society_id", sa.Uuid(), nullable=True),
        sa.Column("building", sa.String(length=80), nullable=True),
        sa.Column("flat_number", sa.String(length=40), nullable=True),
        sa.Column("preferred_language", sa.String(length=10), server_default="en", nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["society_id"],
            ["societies.id"],
            name=op.f("fk_residents_society_id_societies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_residents")),
    )
    op.create_index(
        op.f("ix_residents_whatsapp_number"), "residents", ["whatsapp_number"], unique=True
    )
    op.create_table(
        "vendors",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("business_name", sa.String(length=160), nullable=True),
        sa.Column("primary_phone", sa.String(length=40), nullable=False),
        sa.Column("whatsapp_number", sa.String(length=40), nullable=True),
        sa.Column("society_id", sa.Uuid(), nullable=True),
        sa.Column("locality", sa.String(length=120), nullable=False),
        sa.Column("city", sa.String(length=80), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("verified", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("rating", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("total_jobs", sa.Integer(), server_default="0", nullable=False),
        sa.Column("successful_jobs", sa.Integer(), server_default="0", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "rating IS NULL OR (rating >= 1 AND rating <= 5)", name=op.f("ck_vendors_rating_range")
        ),
        sa.CheckConstraint(
            "total_jobs >= 0 AND successful_jobs >= 0 AND successful_jobs <= total_jobs",
            name=op.f("ck_vendors_valid_jobs"),
        ),
        sa.ForeignKeyConstraint(
            ["society_id"],
            ["societies.id"],
            name=op.f("fk_vendors_society_id_societies"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vendors")),
    )
    op.create_index(op.f("ix_vendors_active"), "vendors", ["active"], unique=False)
    op.create_table(
        "conversations",
        sa.Column("resident_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(length=20), server_default="OPEN", nullable=False),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "last_message_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('OPEN', 'CLOSED')", name=op.f("ck_conversations_valid_status")
        ),
        sa.ForeignKeyConstraint(
            ["resident_id"],
            ["residents.id"],
            name=op.f("fk_conversations_resident_id_residents"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
    )
    op.create_index(
        op.f("ix_conversations_resident_id"), "conversations", ["resident_id"], unique=False
    )
    op.create_index(
        "uq_conversations_open_resident",
        "conversations",
        ["resident_id"],
        unique=True,
        postgresql_where=sa.text("status = 'OPEN'"),
        sqlite_where=sa.text("status = 'OPEN'"),
    )
    op.create_table(
        "vendor_services",
        sa.Column("vendor_id", sa.Uuid(), nullable=False),
        sa.Column("service_category_id", sa.Uuid(), nullable=False),
        sa.Column("price_min", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("price_max", sa.Numeric(precision=10, scale=2), nullable=True),
        sa.Column("pricing_unit", sa.String(length=60), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("available", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "price_max IS NULL OR price_max >= 0",
            name=op.f("ck_vendor_services_price_max_nonnegative"),
        ),
        sa.CheckConstraint(
            "price_min IS NULL OR price_max IS NULL OR price_max >= price_min",
            name=op.f("ck_vendor_services_price_order"),
        ),
        sa.CheckConstraint(
            "price_min IS NULL OR price_min >= 0",
            name=op.f("ck_vendor_services_price_min_nonnegative"),
        ),
        sa.ForeignKeyConstraint(
            ["service_category_id"],
            ["service_categories.id"],
            name=op.f("fk_vendor_services_service_category_id_service_categories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_vendor_services_vendor_id_vendors"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vendor_services")),
        sa.UniqueConstraint(
            "vendor_id",
            "service_category_id",
            name=op.f("uq_vendor_services_vendor_id_service_category_id"),
        ),
    )
    op.create_index(
        op.f("ix_vendor_services_service_category_id"),
        "vendor_services",
        ["service_category_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_vendor_services_vendor_id"), "vendor_services", ["vendor_id"], unique=False
    )
    op.create_table(
        "messages",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("resident_id", sa.Uuid(), nullable=False),
        sa.Column("instance", sa.String(length=120), nullable=False),
        sa.Column("external_message_id", sa.String(length=200), nullable=True),
        sa.Column("in_reply_to_id", sa.Uuid(), nullable=True),
        sa.Column(
            "direction",
            sa.Enum(
                "INBOUND", "OUTBOUND", name="direction", native_enum=False, create_constraint=True
            ),
            nullable=False,
        ),
        sa.Column("message_type", sa.String(length=30), server_default="text", nullable=False),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column(
            "raw_payload",
            sa.JSON().with_variant(postgresql.JSONB(astext_type=sa.Text()), "postgresql"),
            nullable=True,
        ),
        sa.Column(
            "delivery_status",
            sa.Enum(
                "PENDING",
                "SENDING",
                "SENT",
                "FAILED",
                "UNKNOWN",
                name="deliverystatus",
                native_enum=False,
                create_constraint=True,
            ),
            nullable=True,
        ),
        sa.Column("delivery_error", sa.String(length=60), nullable=True),
        sa.Column("delivery_attempted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "(direction = 'INBOUND' AND delivery_status IS NULL) OR (direction = 'OUTBOUND' AND delivery_status IS NOT NULL)",
            name=op.f("ck_messages_delivery_direction"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_messages_conversation_id_conversations"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["in_reply_to_id"],
            ["messages.id"],
            name=op.f("fk_messages_in_reply_to_id_messages"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["resident_id"],
            ["residents.id"],
            name=op.f("fk_messages_resident_id_residents"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
        sa.UniqueConstraint("in_reply_to_id", name=op.f("uq_messages_in_reply_to_id")),
        sa.UniqueConstraint(
            "instance",
            "direction",
            "external_message_id",
            name=op.f("uq_messages_instance_direction_external_message_id"),
        ),
    )
    op.create_index(
        op.f("ix_messages_conversation_id"), "messages", ["conversation_id"], unique=False
    )
    op.create_index(
        "ix_messages_delivery_created", "messages", ["delivery_status", "created_at"], unique=False
    )
    op.create_index(
        op.f("ix_messages_external_message_id"), "messages", ["external_message_id"], unique=False
    )
    op.create_table(
        "service_requests",
        sa.Column("resident_id", sa.Uuid(), nullable=False),
        sa.Column("service_category_id", sa.Uuid(), nullable=True),
        sa.Column("source_message_id", sa.Uuid(), nullable=True),
        sa.Column("original_message", sa.Text(), nullable=False),
        sa.Column("interpreted_requirement", sa.Text(), nullable=True),
        sa.Column("urgency", sa.String(length=20), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "NEW",
                "MATCHING",
                "VENDORS_SHARED",
                "CONTACTED",
                "COMPLETED",
                "CANCELLED",
                name="requeststatus",
                native_enum=False,
                create_constraint=True,
            ),
            server_default="NEW",
            nullable=False,
        ),
        sa.Column("locality", sa.String(length=120), nullable=True),
        sa.Column("preferred_time", sa.String(length=120), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["resident_id"],
            ["residents.id"],
            name=op.f("fk_service_requests_resident_id_residents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_category_id"],
            ["service_categories.id"],
            name=op.f("fk_service_requests_service_category_id_service_categories"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_message_id"],
            ["messages.id"],
            name=op.f("fk_service_requests_source_message_id_messages"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_requests")),
        sa.UniqueConstraint(
            "source_message_id", name=op.f("uq_service_requests_source_message_id")
        ),
    )
    op.create_index(
        op.f("ix_service_requests_resident_id"), "service_requests", ["resident_id"], unique=False
    )
    op.create_index(
        op.f("ix_service_requests_status"), "service_requests", ["status"], unique=False
    )
    op.create_table(
        "service_request_vendors",
        sa.Column("service_request_id", sa.Uuid(), nullable=False),
        sa.Column("vendor_id", sa.Uuid(), nullable=False),
        sa.Column("rank", sa.Integer(), nullable=False),
        sa.Column("ranking_score", sa.Numeric(precision=16, scale=2), nullable=True),
        sa.Column("selected", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("contacted", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "rank >= 1 AND rank <= 3", name=op.f("ck_service_request_vendors_rank_range")
        ),
        sa.ForeignKeyConstraint(
            ["service_request_id"],
            ["service_requests.id"],
            name=op.f("fk_service_request_vendors_service_request_id_service_requests"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_service_request_vendors_vendor_id_vendors"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_service_request_vendors")),
        sa.UniqueConstraint(
            "service_request_id",
            "rank",
            name=op.f("uq_service_request_vendors_service_request_id_rank"),
        ),
        sa.UniqueConstraint(
            "service_request_id",
            "vendor_id",
            name=op.f("uq_service_request_vendors_service_request_id_vendor_id"),
        ),
    )
    op.create_table(
        "vendor_feedback",
        sa.Column("service_request_id", sa.Uuid(), nullable=False),
        sa.Column("resident_id", sa.Uuid(), nullable=False),
        sa.Column("vendor_id", sa.Uuid(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("feedback", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("(CURRENT_TIMESTAMP)"),
            nullable=False,
        ),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "rating >= 1 AND rating <= 5", name=op.f("ck_vendor_feedback_rating_range")
        ),
        sa.ForeignKeyConstraint(
            ["resident_id"],
            ["residents.id"],
            name=op.f("fk_vendor_feedback_resident_id_residents"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["service_request_id"],
            ["service_requests.id"],
            name=op.f("fk_vendor_feedback_service_request_id_service_requests"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["vendor_id"],
            ["vendors.id"],
            name=op.f("fk_vendor_feedback_vendor_id_vendors"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_vendor_feedback")),
        sa.UniqueConstraint(
            "service_request_id",
            "resident_id",
            "vendor_id",
            name=op.f("uq_vendor_feedback_service_request_id_resident_id_vendor_id"),
        ),
    )


def downgrade():
    op.drop_table("vendor_feedback")
    op.drop_table("service_request_vendors")
    op.drop_index(op.f("ix_service_requests_status"), table_name="service_requests")
    op.drop_index(op.f("ix_service_requests_resident_id"), table_name="service_requests")
    op.drop_table("service_requests")
    op.drop_index(op.f("ix_messages_external_message_id"), table_name="messages")
    op.drop_index("ix_messages_delivery_created", table_name="messages")
    op.drop_index(op.f("ix_messages_conversation_id"), table_name="messages")
    op.drop_table("messages")
    op.drop_index(op.f("ix_vendor_services_vendor_id"), table_name="vendor_services")
    op.drop_index(op.f("ix_vendor_services_service_category_id"), table_name="vendor_services")
    op.drop_table("vendor_services")
    op.drop_index(
        "uq_conversations_open_resident",
        table_name="conversations",
        postgresql_where=sa.text("status = 'OPEN'"),
        sqlite_where=sa.text("status = 'OPEN'"),
    )
    op.drop_index(op.f("ix_conversations_resident_id"), table_name="conversations")
    op.drop_table("conversations")
    op.drop_index(op.f("ix_vendors_active"), table_name="vendors")
    op.drop_table("vendors")
    op.drop_index(op.f("ix_residents_whatsapp_number"), table_name="residents")
    op.drop_table("residents")
    op.drop_table("societies")
    op.drop_index(op.f("ix_service_categories_slug"), table_name="service_categories")
    op.drop_table("service_categories")
