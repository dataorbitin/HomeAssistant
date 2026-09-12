import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from app.api.routes import health, service_requests, services, vendors, webhook
from app.core.config import Settings
from app.core.logging import configure_logging
from app.db.session import create_engine, session_factory
from app.services.ai_service import AIService
from app.services.evolution_service import EvolutionAPIClient
from app.services.outbox_service import OutboxService


def create_app(settings: Settings | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(application):
        config = settings or Settings()
        configure_logging()
        engine = create_engine(config.database_url.get_secret_value())
        application.state.settings = config
        application.state.engine = engine
        application.state.sessions = session_factory(engine)
        async with httpx.AsyncClient() as client:
            application.state.ai = AIService(config, client)
            application.state.evolution = EvolutionAPIClient(config, client)
            application.state.outbox = OutboxService(
                application.state.sessions, application.state.evolution, config
            )
            worker = (
                asyncio.create_task(application.state.outbox.run())
                if config.outbox_enabled
                else None
            )
            try:
                yield
            finally:
                if worker:
                    worker.cancel()
                    with contextlib.suppress(asyncio.CancelledError):
                        await worker
                await engine.dispose()

    application = FastAPI(title="Home Assistant", version="0.1.0", lifespan=lifespan)

    @application.exception_handler(SQLAlchemyError)
    async def database_error(request: Request, exc: SQLAlchemyError):
        logging.getLogger(__name__).error("database_operation_failed error=%s", type(exc).__name__)
        return JSONResponse(status_code=503, content={"detail": "Database temporarily unavailable"})

    for router in (
        health.router,
        webhook.router,
        services.router,
        vendors.router,
        service_requests.router,
    ):
        application.include_router(router)
    return application


app = create_app()
