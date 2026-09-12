"""Initial geography and categories; protect Supabase Data API access.

Revision ID: 0002
Revises: 0001
"""

from uuid import NAMESPACE_URL, uuid5

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

# Frozen migration data: never import the evolving application seed or models.
CATEGORIES = [
    ["Plumber", "plumber"],
    ["Electrician", "electrician"],
    ["Cleaning", "cleaning"],
    ["Carpenter", "carpenter"],
    ["AC Repair", "ac-repair"],
    ["Appliance Repair", "appliance-repair"],
    ["RO / Water Purifier", "ro-water-purifier"],
    ["Pest Control", "pest-control"],
    ["Packers & Movers", "packers-movers"],
    ["Maid", "maid"],
    ["Cook", "cook"],
    ["Babysitter", "babysitter"],
    ["Painting", "painting"],
    ["Internet / Broadband", "internet-broadband"],
    ["Locksmith", "locksmith"],
]
TABLES = (
    "societies",
    "residents",
    "service_categories",
    "vendors",
    "vendor_services",
    "service_requests",
    "service_request_vendors",
    "conversations",
    "messages",
    "vendor_feedback",
)


def initial_id(label):
    return uuid5(NAMESPACE_URL, "home-assistant-fictional-seed/" + label)


def upgrade():
    societies = sa.table(
        "societies",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("locality", sa.String()),
        sa.column("city", sa.String()),
        sa.column("state", sa.String()),
    )
    categories = sa.table(
        "service_categories",
        sa.column("id", sa.Uuid()),
        sa.column("name", sa.String()),
        sa.column("slug", sa.String()),
        sa.column("description", sa.Text()),
    )
    insert = pg_insert if op.get_context().dialect.name == "postgresql" else sqlite_insert
    op.execute(
        insert(societies)
        .values(
            [
                {
                    "id": initial_id("society"),
                    "name": "Megapolis",
                    "locality": "Hinjewadi Phase 3",
                    "city": "Pune",
                    "state": "Maharashtra",
                }
            ]
        )
        .on_conflict_do_nothing()
    )
    op.execute(
        insert(categories)
        .values(
            [
                {
                    "id": initial_id("category/" + slug),
                    "name": name,
                    "slug": slug,
                    "description": f"Local {name.lower()} services",
                }
                for name, slug in CATEGORIES
            ]
        )
        .on_conflict_do_nothing()
    )
    if op.get_context().dialect.name == "postgresql":
        # Backend connects as table owner (or a dedicated BYPASSRLS server role).
        # No public policies: anon/authenticated Supabase API users cannot read PII.
        for table in TABLES:
            op.execute(sa.text(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY'))


def downgrade():
    if op.get_context().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(sa.text(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY'))
    # Keep reference rows on a one-step rollback: they may have resident/vendor FKs.
    # Downgrading 0001 removes the schema and its data.
