import json
import logging
import secrets

from fastapi import APIRouter, HTTPException, Request
from sqlalchemy.exc import SQLAlchemyError

from app.schemas.webhook import parse_webhook
from app.services.message_service import MessageService

router = APIRouter()
log = logging.getLogger(__name__)


@router.post("/webhook/evolution")
async def evolution_webhook(request: Request):
    state = request.app.state
    expected = state.settings.webhook_secret.get_secret_value()
    if not expected:
        raise HTTPException(503, "Webhook authentication is not configured")
    supplied = request.headers.get("x-webhook-secret") or request.query_params.get("token", "")
    if not secrets.compare_digest(supplied.encode(), expected.encode()):
        raise HTTPException(401, "Invalid webhook secret")
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 262144:
            raise HTTPException(413, "Payload exceeds 256 KiB; disable webhook Base64")
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError, RecursionError):
        raise HTTPException(400, "Invalid JSON") from None
    if not isinstance(payload, dict):
        raise HTTPException(400, "Expected a JSON object")
    entries = parse_webhook(payload, state.settings.evolution_api_instance)
    if len(entries) > 50:
        raise HTTPException(413, "Batch exceeds 50 supported messages")
    processed = duplicates = 0
    for incoming in entries:
        try:
            async with state.sessions.begin() as session:
                outbound_id = await MessageService(state.settings, state.ai).process(
                    session, incoming
                )
        except (SQLAlchemyError, RuntimeError) as exc:
            log.error("message_processing_failed error=%s", type(exc).__name__)
            raise HTTPException(503, "Message processing temporarily unavailable") from None
        if outbound_id is None:
            duplicates += 1
            continue
        processed += 1
        # Pending rows survive a process crash; the poller can complete delivery.
        try:
            await state.outbox.deliver(outbound_id)
        except SQLAlchemyError:
            log.error("delivery_state_update_failed")
    return {
        "status": "ok" if entries else "ignored",
        "processed": processed,
        "duplicates_or_inactive": duplicates,
    }
