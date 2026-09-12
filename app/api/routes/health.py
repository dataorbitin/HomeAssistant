import asyncio

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

router = APIRouter()


@router.get("/health")
async def health(request: Request):
    try:
        async with asyncio.timeout(5):
            async with request.app.state.engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError, TimeoutError):
        return JSONResponse(
            status_code=503,
            content={"status": "degraded", "database": "disconnected", "service": "home-assistant"},
        )
    return {"status": "ok", "database": "connected", "service": "home-assistant"}
