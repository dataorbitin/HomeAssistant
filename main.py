"""Text echo MVP for Evolution API v2. Run one worker and one replica."""
import asyncio
import json
import logging
import os
import secrets
from contextlib import asynccontextmanager

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

    raw = await request.body()
    print("CONTENT-TYPE:", request.headers.get("content-type"), flush=True)
    print("BODY LENGTH:", len(raw), flush=True)
    print("RAW BODY:", raw[:3000], flush=True)

    try:
        payload = json.loads(raw)
    except Exception as exc:
        print("❌ JSON PARSE ERROR:", repr(exc), flush=True)
        raise HTTPException(
            status_code=400,
            detail=f"Invalid JSON: {type(exc).__name__}"
        )

    print("PAYLOAD TYPE:", type(payload).__name__, flush=True)
    print("PAYLOAD:", payload, flush=True)
    return {"status": "ok"}
