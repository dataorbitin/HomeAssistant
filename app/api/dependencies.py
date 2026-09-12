import secrets

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

admin_header = APIKeyHeader(name="X-Admin-Key", auto_error=False)


async def get_session(request: Request):
    async with request.app.state.sessions() as session:
        yield session


async def require_admin(request: Request, supplied: str | None = Depends(admin_header)):
    expected = request.app.state.settings.admin_api_key.get_secret_value()
    if not expected:
        if request.app.state.settings.app_env == "production":
            raise HTTPException(503, "Admin access is not configured")
        return
    if not secrets.compare_digest((supplied or "").encode(), expected.encode()):
        raise HTTPException(401, "Invalid admin key")
