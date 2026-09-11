"""Text echo MVP for Evolution API v2. Run one worker and one replica."""
import asyncio
import json
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
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')
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
        log.info('App ready; instance=%r', app.state.instance)
        try:
            yield
        finally:
            log.info('App shutting down')


app = FastAPI(title='Home Assistant Echo', lifespan=lifespan)


@app.get('/health')
async def health():
    return {'status': 'ok'}


@app.post("/webhook/evolution")
async def webhook(request: Request):
    print("========== EVOLUTION WEBHOOK HIT ==========", flush=True)

    supplied = (
        request.headers.get("x-webhook-secret")
        or request.query_params.get("token", "")
    )
    print("TOKEN PRESENT:", bool(supplied), flush=True)

    if not secrets.compare_digest(supplied, request.app.state.secret):
        print("❌ INVALID WEBHOOK SECRET", flush=True)
        raise HTTPException(401, "Invalid webhook secret")

    raw = bytearray()
    async for chunk in request.stream():
        raw.extend(chunk)
        if len(raw) > 262144:
            log.warning('Webhook rejected: payload exceeds 256 KiB')
            raise HTTPException(413, 'Payload too large; disable webhook Base64')
    print("CONTENT-TYPE:", request.headers.get("content-type"), flush=True)
    print("BODY LENGTH:", len(raw), flush=True)
    print("RAW BODY:", raw[:3000], flush=True)

    try:
        payload = json.loads(raw)
    except (ValueError, UnicodeDecodeError) as exc:
        print("❌ JSON PARSE ERROR:", repr(exc), flush=True)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON: {type(exc).__name__}"
        )

    print("PAYLOAD TYPE:", type(payload).__name__, flush=True)
    print("PAYLOAD:", payload, flush=True)
    trace = secrets.token_hex(4)

    def reached(stage, *args):
        log.info('request=%s ' + stage, trace, *args)

    if not isinstance(payload, dict):
        reached('Webhook rejected: expected an object')
        raise HTTPException(400, 'Expected an object')
    state = request.app.state
    event = str(payload.get('event', '')).lower().replace('_', '.')
    reached('Payload parsed; event=%r instance=%r', event, payload.get('instance'))
    if event != 'messages.upsert' or payload.get('instance') != state.instance:
        reached('Webhook ignored: unsupported event or wrong instance')
        return {'status': 'ignored', 'echoed': 0}
    data = payload.get('data')
    entries = data if isinstance(data, list) else [data]
    sent = 0
    reached('Processing batch; entries=%d', len(entries))
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            reached('Entry %d ignored: expected an object', index)
            continue
        key = entry.get('key') or {}
        message = entry.get('message') or {}
        if not isinstance(key, dict) or not isinstance(message, dict):
            reached('Entry %d ignored: invalid key or message', index)
            continue
        # Missing fromMe is ignored too: never assume an event is inbound.
        if key.get('fromMe') is not False:
            reached('Entry %d ignored: outgoing message or missing fromMe', index)
            continue
        jid = key.get('remoteJid', '')
        mid = key.get('id')
        if not isinstance(jid, str) or not re.fullmatch(r'\d{7,15}@s\.whatsapp\.net', jid):
            reached('Entry %d ignored: unsupported sender (group, broadcast, LID, or invalid JID)', index)
            continue  # Ignore groups, broadcasts, and unresolved LID identifiers.
        extended = message.get('extendedTextMessage') or {}
        text = message.get('conversation')
        if text is None and isinstance(extended, dict):
            text = extended.get('text')
        if not isinstance(text, str) or not text or len(text) > 4096 or not isinstance(mid, str) or not mid:
            reached('Entry %d ignored: missing/invalid text or message ID, or text exceeds 4096 characters', index)
            continue
        reached('Entry %d inbound text; message_id=%r text=%r', index, mid, text)
        dedup_key = (jid, mid)
        # Serial processing is intentional for this small, single-worker MVP.
        async with state.lock:
            now = time.monotonic()
            state.seen = {k: expiry for k, expiry in state.seen.items() if expiry > now}
            if dedup_key in state.seen:
                reached('Entry %d ignored: duplicate message_id=%r', index, mid)
                continue
            reached('Entry %d sending echo; message_id=%r', index, mid)
            try:
                response = await state.client.post(
                    state.base_url + '/message/sendText/' + quote(state.instance, safe=''),
                    json={'number': jid.split('@')[0], 'text': text},
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                status = exc.response.status_code if isinstance(exc, httpx.HTTPStatusError) else None
                log.warning('request=%s Entry %d echo failed; message_id=%r error=%s upstream_status=%s; returning 502',
                            trace, index, mid, type(exc).__name__, status)
                raise HTTPException(502, 'Evolution send failed')
            if len(state.seen) >= 10000:
                state.seen.pop(next(iter(state.seen)))
            state.seen[dedup_key] = time.monotonic() + 86400
            sent += 1
            reached('Echo sent successfully; entry=%d message_id=%r upstream_status=%d', index, mid, response.status_code)
    reached('Webhook completed; echoed=%d', sent)
    return {'status': 'ok', 'echoed': sent}
