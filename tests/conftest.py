import asyncio
import os
import sys
import uuid
from unittest.mock import AsyncMock

import httpx
import pytest
from sqlalchemy import text
from sqlalchemy.pool import NullPool

from app.core.config import Settings
from app.db.models import Base
from app.db.session import create_engine, session_factory
from app.main import create_app
from app.schemas.intent import Intent, ServiceIntent
from scripts.seed import seed_demo

# Psycopg async connections require a selector loop on Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


@pytest.fixture
async def engine(tmp_path):
    # Set TEST_POSTGRES_URL to run the same suite against PostgreSQL.
    # Each test gets its own schema; no pre-existing tables are touched.
    postgres_url = os.environ.get("TEST_POSTGRES_URL")
    if postgres_url:
        from sqlalchemy.ext.asyncio import create_async_engine

        from app.db.session import normalize_url

        schema = "test_" + uuid.uuid4().hex
        admin = create_engine(postgres_url)
        async with admin.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        result = create_async_engine(
            normalize_url(postgres_url),
            poolclass=NullPool,
            connect_args={"prepare_threshold": None, "options": f"-csearch_path={schema}"},
        )
    else:
        result = create_engine("sqlite+aiosqlite:///" + str(tmp_path / "test.db"))
    async with result.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    yield result
    await result.dispose()
    if postgres_url:
        async with admin.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
        await admin.dispose()


@pytest.fixture
async def sessions(engine):
    return session_factory(engine)


@pytest.fixture
async def seeded(sessions):
    async with sessions.begin() as session:
        return await seed_demo(session)


@pytest.fixture
def settings():
    return Settings(
        _env_file=None,
        app_env="test",
        webhook_secret="test-secret-" * 4,
        evolution_api_key="mock-evolution-key",
        openai_api_key="mock-llm-key",
        openai_model="mock-model",
        outbox_enabled=False,
    )


@pytest.fixture
def ai():
    async def extract(text_value, history, categories):
        if "maid" in text_value.lower():
            return ServiceIntent(
                intent=Intent.FIND_SERVICE,
                service_category="maid",
                requirement="Need maid",
                urgency="NORMAL",
            )
        return ServiceIntent(
            intent=Intent.FIND_SERVICE,
            service_category="plumber",
            requirement="Kitchen sink leaking",
            urgency="HIGH",
        )

    return AsyncMock(extract=AsyncMock(side_effect=extract))


@pytest.fixture
def evolution():
    return AsyncMock(
        send_text_message=AsyncMock(side_effect=lambda *_: "mock-outbound-" + uuid.uuid4().hex)
    )


@pytest.fixture
async def client(engine, sessions, seeded, settings, ai, evolution):
    from app.services.outbox_service import OutboxService

    application = create_app(settings)
    application.state.settings = settings
    application.state.engine = engine
    application.state.sessions = sessions
    application.state.ai = ai
    application.state.outbox = OutboxService(sessions, evolution, settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=application),
        base_url="http://test",
        headers={"x-webhook-secret": settings.webhook_secret.get_secret_value()},
    ) as result:
        yield result


def payload(
    text_value="Hi, I need a plumber urgently. My kitchen sink is leaking.",
    message_id="test-message-1",
    phone="12025550101",
):
    # 202-555-0100 through 0199 is reserved for fictional NANP examples.
    return {
        "event": "MESSAGES_UPSERT",
        "instance": "home-assistance",
        "data": {
            "key": {"id": message_id, "remoteJid": phone + "@s.whatsapp.net", "fromMe": False},
            "message": {"conversation": text_value},
            "messageTimestamp": 1789196400,
        },
    }
