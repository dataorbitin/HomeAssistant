# Home Assistant WhatsApp echo

Text-only FastAPI MVP for your Evolution instance `home-assistance`.
Flow: WhatsApp → Meta → Evolution → FastAPI → Evolution → WhatsApp.
No LLM, Supabase, or Meta token is needed in this app.

## Deploy to Railway

1. Extract this ZIP and put its files at the root of a new GitHub repository.
2. In your Railway project, add a NEW service from that repository. Keep your existing Evolution service running.
3. Railway can build the included Dockerfile. Set these Variables on the NEW service:

| Variable | Value |
| --- | --- |
| EVOLUTION_API_URL | Your existing Evolution public HTTPS URL, without `/manager` or `/webhook/meta` |
| EVOLUTION_API_KEY | Evolution's API key (not the Meta access token) |
| EVOLUTION_INSTANCE | `home-assistance` — exact instance name |
| WEBHOOK_SECRET | A new random secret of at least 32 characters |

Generate a secret locally: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.
The `.env.example` is a reference, not loaded automatically. Never commit real secrets.
4. Deploy, generate a public domain for the new FastAPI service, and open `https://YOUR-FASTAPI-DOMAIN/health`. Expect `{"status":"ok"}`.
5. Run only ONE replica and ONE worker for this MVP.

## Configure Evolution's outgoing webhook

In Evolution Manager, open the instance → Events → Webhook (labels may vary).
- Enabled: ON
- URL: `https://YOUR-FASTAPI-DOMAIN/webhooks/evolution`
- Webhook by Events: OFF
- Webhook Base64: OFF
- Event: MESSAGES_UPSERT
- If custom headers are supported, set `x-webhook-secret` to WEBHOOK_SECRET.
- If custom headers aren't available, use this URL instead:
  `https://YOUR-FASTAPI-DOMAIN/webhooks/evolution?token=YOUR_WEBHOOK_SECRET`
- Save.

The query-token option is a compatibility fallback: its URL is a credential and can appear in proxy logs. Keep it private. Application access logs are disabled in the Docker start command. Prefer the header option when supported.

Do NOT change Meta's existing callback URL `/webhook/meta`, or the WABA subscription you just fixed.

## Test

Send `Hi Sachin` from your personal WhatsApp to the business number. Expect exactly `Hi Sachin` back. FastAPI deploy logs show webhook receipt, parsed event/instance, incoming text, skip reasons, send attempts/results, and completion. Each webhook has a `request=` ID so you can follow its flow. Search for `inbound text` to see the received message and `Echo sent successfully` to confirm the reply.

- No request at FastAPI: check Evolution webhook URL, enabled status, and MESSAGES_UPSERT.
- HTTP 401: webhook secret doesn't match.
- HTTP 502: check Evolution URL/key/instance, then Evolution logs. The failure log includes the error type and upstream HTTP status, without upstream response bodies.
- HTTP 200 with echoed=0: event was ignored (outgoing, wrong instance, duplicate, unsupported payload, group, or media).

## Local run

Python 3.12 recommended.
```
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```
Export the four variables from `.env.example` in your terminal, then:
```
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log
```
Localhost is not reachable by Railway; use the deployed app for WhatsApp testing.

## Supported payload and limitations

Expects Evolution v2's normalized `messages.upsert` envelope with `instance`, `data.key` (id, remoteJid, fromMe), and `data.message.conversation` or `extendedTextMessage.text`. It accepts a single data object or a list. This is NOT a raw Meta webhook endpoint. If your installed v2.3.7 emits a different payload, capture a redacted sample to adapt the parser.

Replies through POST `/message/sendText/{instance}`, header `apikey`, JSON `{"number":"sender digits","text":"original text"}`. The endpoint contract needs live validation against your installation; no credentials or live WhatsApp account were available during development.

Only individual text messages up to 4096 characters are echoed. Groups, media, broadcasts, and unresolved @lid senders are ignored. Missing fromMe is ignored conservatively. Incoming payloads are capped at 256 KiB.

Duplicate suppression is in memory for 24 hours, up to 10,000 successful messages. It resets on restart and does not work across replicas. A send timeout or process crash after an accepted send can cause a duplicate on redelivery. This is not exactly-once delivery. Failed sends return 502; automatic webhook retry behavior depends on your Evolution configuration. There is no durable queue or automatic retry worker. Add Redis/Postgres-backed jobs before production use.

The outbound URL and API key always come from environment variables, never webhook payload fields. Incoming supported text is logged at INFO level using an escaped representation. Phone numbers, API keys, webhook secrets, and upstream response bodies are not logged by these application logs.

## Automated tests

```
python -m unittest -v test_main.py
```
Tests use mocked HTTP responses; no real WhatsApp messages are sent.

FastAPI lifespan reference: https://fastapi.tiangolo.com/advanced/events/
