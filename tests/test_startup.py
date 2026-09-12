import httpx

from app.core.config import Settings
from app.main import create_app


async def test_real_lifespan_startup_and_shutdown(tmp_path):
    settings = Settings(
        _env_file=None,
        app_env="test",
        outbox_enabled=False,
        database_url="sqlite+aiosqlite:///" + str(tmp_path / "startup.db"),
    )
    application = create_app(settings)
    async with application.router.lifespan_context(application):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=application), base_url="http://test"
        ) as client:
            assert (await client.get("/health")).json()["database"] == "connected"
            assert (await client.get("/docs")).status_code == 200
            assert (await client.get("/openapi.json")).json()["info"]["title"] == "Home Assistant"
            assert application.state.ai is not None
            assert application.state.evolution is not None
