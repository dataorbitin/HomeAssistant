import asyncio
import sys

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.core.config import Settings
from app.db.models import Base
from app.db.session import normalize_url

config = context.config
settings = Settings()
url = normalize_url(
    settings.migration_database_url.get_secret_value() or settings.database_url.get_secret_value()
)
target_metadata = Base.metadata


def run_sync(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_online():
    options = {"poolclass": pool.NullPool, "hide_parameters": True}
    if url.startswith("postgresql"):
        options["connect_args"] = {"prepare_threshold": None, "connect_timeout": 10}
    engine = create_async_engine(url, **options)
    async with engine.connect() as connection:
        await connection.run_sync(run_sync)
    await engine.dispose()


if context.is_offline_mode():
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
else:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_online())
