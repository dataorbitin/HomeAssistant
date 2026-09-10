"""Text echo MVP for Evolution API v2. Run one worker and one replica."""
import asyncio
import logging
import os
import re
import secrets
import time
from contextlib import asynccontextmanager
from urllib.parse import quote

import httpx
from fastapi import FastAPI, HTTPException, Request

log = logging.getLogger('echo')
logging.basicConfig(level=logging.INFO)
logging.getLogger('httpx').setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.base_url = os.environ['EVOLUTION_API_URL'].rstrip('/')
    app.state.instance = os.environ.get('EVOLUTION_INSTANCE', 'home-assistance')
    app.state.secret = os.environ['WEBHOOK_SECRET']
    if len(app.state.secret) < 32:
        raise RuntimeError('WEBHOOK_SECRET must contain at least 32 characters')
    app.state.seen = {}
    app.state.lock = asyncio.Lock()
    async with httpx.AsyncClient(
        headers={'apikey': os.environ['EVOLUTION_API_KEY']}, timeout=15.0
    ) as client:
        app.state.client = client
        yield


app = FastAPI(title='Home Assistant Echo', lifespan=lifespan)


@app.get('/health')
async def health():
    return {'status': 'ok'}


@app.post('/webhooks/evolution')
async def webhook(request: Request):
    # Prefer a custom header. Query token supports Manager versions without headers.
    supplied = request.headers.get('x-webhook-secret') or request.query_params.get('token', '')
    if not secrets.compare_digest(supplied, request.app.state.secret):
        raise HTTPException(401, 'Invalid webhook secret')
    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 262144:
            raise HTTPException(413, 'Payload too large; disable webhook Base64')
    import json
    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError):
        raise HTTPException(400, 'Invalid JSON')
    if not isinstance(payload, dict):
        raise HTTPException(400, 'Expected an object')
    state = request.app.state
    event = str(payload.get('event', '')).lower().replace('_', '.')
    if event != 'messages.upsert' or payload.get('instance') != state.instance:
        return {'status': 'ignored', 'echoed': 0}
    data = payload.get('data')
    entries = data if isinstance(data, list) else [data]
    sent = 0
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = entry.get('key') or {}
        message = entry.get('message') or {}
        if not isinstance(key, dict) or not isinstance(message, dict):
            continue
        # Missing fromMe is ignored too: never assume an event is inbound.
        if key.get('fromMe') is not False:
            continue
        jid = key.get('remoteJid', '')
        mid = key.get('id')
        if not isinstance(jid, str) or not re.fullmatch(r'\d{7,15}@s\.whatsapp\.net', jid):
            continue  # Ignore groups, broadcasts, and unresolved LID identifiers.
        extended = message.get('extendedTextMessage') or {}
        text = message.get('conversation')
        if text is None and isinstance(extended, dict):
            text = extended.get('text')
        if not isinstance(text, str) or not text or len(text) > 4096 or not isinstance(mid, str) or not mid:
            continue
        dedup_key = (jid, mid)
        # Serial processing is intentional for this small, single-worker MVP.
        async with state.lock:
            now = time.monotonic()
            state.seen = {k: expiry for k, expiry in state.seen.items() if expiry > now}
            if dedup_key in state.seen:
                continue
            try:
                response = await state.client.post(
                    state.base_url + '/message/sendText/' + quote(state.instance, safe=''),
                    json={'number': jid.split('@')[0], 'text': text},
                )
                response.raise_for_status()
            except httpx.HTTPError:
                log.warning('Echo send failed; returning 502 (no message content logged)')
                raise HTTPException(502, 'Evolution send failed')
            if len(state.seen) >= 10000:
                state.seen.pop(next(iter(state.seen)))
            state.seen[dedup_key] = time.monotonic() + 86400
            sent += 1
            log.info('Echo sent successfully')
    return {'status': 'ok', 'echoed': sent}
