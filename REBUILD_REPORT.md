# Home Assistant rebuild report

The echo application was replaced with an async FastAPI concierge backend. The repository is ready for target-environment configuration and deployment; implementation and verification details are recorded below.

## Implemented

- Evolution webhook authentication, normalization, own-message filtering and durable database idempotency.
- UUID resident creation, conversation storage, bounded context and validated OpenAI-compatible intent extraction.
- Parameterized vendor lookup, deterministic ranking, maximum three recommendations, direct DB-sourced contacts and persisted unmet demand.
- Contacted-vendor tracking, rating feedback, service history and protected read APIs.
- Durable outbound delivery claims, safe transient retries, failure inspection and operator recovery tooling.
- Two explicit Alembic revisions, PostgreSQL indexes/constraints/JSONB and Supabase RLS protection.
- Repeatable fictional data, Docker/Railway configuration, PostgreSQL CI and complete README.

## Database schema

Ten UUID-keyed tables: societies, residents, service_categories, vendors, vendor_services, service_requests, service_request_vendors, conversations, messages and vendor_feedback.

Revision 0001 creates the schema. Revision 0002 adds the initial society/categories and enables RLS on all business tables. Supabase client roles have no public policies. The trusted backend uses an appropriate database owner/server role.

The messages table additionally stores delivery state and a unique reply linkage. Message idempotency is enforced per instance/direction/external ID. The source message is unique per service request.

## Seed validation

Repeatable seed counts: 1 society, 5 residents, 15 categories, 20 vendors, 40 vendor-service relationships, 6 historical requests, 5 recommendations, 5 conversations, 12 messages and 5 feedback records. All contact values are non-dialable TEST placeholders. There are no eligible maid providers. Inactive/unavailable vendors and varied ranking data are present.

Seeding ran twice on isolated local PostgreSQL and SQLite databases with unchanged counts. No seed operation contacted WhatsApp or an LLM. Dummy seeding is disabled in production.

## Verification results

- Python 3.12.9; temporary local PostgreSQL 16.15.
- Full pytest suite with SQLite: **68 passed**, no warnings.
- Full pytest suite with PostgreSQL: **68 passed**, no warnings.
- Urgent plumber and unavailable maid scenarios, concurrent duplicate webhooks and concurrent delivery claims passed.
- Ruff lint and formatting checks passed across 51 Python files.
- Import/compile validation and pip dependency checks passed.
- Live Uvicorn HTTP startup, connected /health, /docs, /openapi.json and clean shutdown passed.
- Migration upgrade, full downgrade/re-upgrade, reference-revision rollback/re-upgrade and alembic check passed on PostgreSQL. SQLite migration/seed checks also passed.
- PostgreSQL offline migration SQL compiled successfully.
- All ten business tables have RLS enabled. A temporary non-owner role granted SELECT could read zero resident rows. The role experiment was rolled back.
- messages.raw_payload is JSONB in PostgreSQL.
- Git whitespace checks passed.

The tests mock Evolution and the LLM. A Docker image build was not run because Docker is unavailable locally. GitHub Actions has been configured but has not run until these changes are pushed. Live Supabase, Railway and Evolution/WhatsApp validation requires target-environment access and credentials.

## Required environment and deployment actions

1. Configure a dedicated Supabase database and copy its direct/session PostgreSQL URL into DATABASE_URL. Use TLS and URL-encode the database password. Optionally set MIGRATION_DATABASE_URL.
2. Set EVOLUTION_API_BASE_URL, EVOLUTION_API_INSTANCE, EVOLUTION_API_KEY, WEBHOOK_SECRET, OPENAI_API_KEY, OPENAI_MODEL, APP_ENV=production and ADMIN_API_KEY. OPENAI_BASE_URL is configurable. SUPABASE_URL/SUPABASE_KEY are optional reserved settings; database queries use DATABASE_URL.
3. Migrate the old Railway names EVOLUTION_API_URL -> EVOLUTION_API_BASE_URL and EVOLUTION_INSTANCE -> EVOLUTION_API_INSTANCE. Both legacy aliases remain supported; the new names take precedence. Keep the existing Evolution API key, valid webhook secret and exact instance spelling.
4. Railway uses the Dockerfile and runs alembic upgrade head as its pre-deploy command. Remove any old main:app start-command override. Startup is uvicorn app.main:app --host 0.0.0.0 --port $PORT --no-access-log. Set /health as the health check.
5. Onboard real vendor records in the production database. Keep fictional vendor/resident data in development.
6. Configure Evolution's MESSAGES_UPSERT webhook to **https://YOUR-FASTAPI-DOMAIN/webhook/evolution**, with x-webhook-secret set. Keep the existing Meta-to-Evolution callback unchanged. Disable Webhook by Events and Base64.
7. Run the controlled live plumber/maid smoke test and redeliver the same external message ID. Inspect saved recommendations and delivery state.

Full settings, commands, architecture diagrams and troubleshooting are in [README.md](README.md) and [.env.example](.env.example).

## Delivery limitation

PostgreSQL and the external send API cannot commit atomically. The implementation prioritizes avoiding duplicate replies: uncertain network outcomes and crashed send claims are not resent automatically. They remain UNKNOWN for operator reconciliation. Pending committed messages recover automatically. Only definitely failed sends can be explicitly requeued with python -m scripts.outbox --retry-failed UUID. This is documented rather than claiming exactly-once remote delivery.

## File inventory

Useful deployment ignore rules, Python 3.12 Docker infrastructure and Git history were preserved or updated. The .git directory and existing virtual environment were retained. No .env or real credentials were created or committed.

### Deleted (2)

- `main.py`
- `test_main.py`

### Modified (6)

- `.dockerignore`
- `.env.example`
- `.gitignore`
- `Dockerfile`
- `README.md`
- `requirements.txt`

### Created (58)

- `.github/workflows/ci.yml`
- `REBUILD_REPORT.md`
- `alembic.ini`
- `alembic/env.py`
- `alembic/script.py.mako`
- `alembic/versions/0001_initial_concierge_schema.py`
- `alembic/versions/0002_reference_data_and_rls.py`
- `app/__init__.py`
- `app/api/__init__.py`
- `app/api/dependencies.py`
- `app/api/routes/__init__.py`
- `app/api/routes/health.py`
- `app/api/routes/service_requests.py`
- `app/api/routes/services.py`
- `app/api/routes/vendors.py`
- `app/api/routes/webhook.py`
- `app/core/__init__.py`
- `app/core/config.py`
- `app/core/logging.py`
- `app/db/__init__.py`
- `app/db/models/__init__.py`
- `app/db/repositories/__init__.py`
- `app/db/repositories/common.py`
- `app/db/repositories/vendor_repository.py`
- `app/db/session.py`
- `app/main.py`
- `app/prompts/__init__.py`
- `app/prompts/service_intent_prompt.py`
- `app/schemas/__init__.py`
- `app/schemas/api.py`
- `app/schemas/intent.py`
- `app/schemas/webhook.py`
- `app/services/__init__.py`
- `app/services/ai_service.py`
- `app/services/conversation_service.py`
- `app/services/evolution_service.py`
- `app/services/message_service.py`
- `app/services/outbox_service.py`
- `app/services/resident_service.py`
- `app/services/vendor_ranking_service.py`
- `app/services/vendor_service.py`
- `pyproject.toml`
- `railway.toml`
- `requirements-dev.txt`
- `scripts/__init__.py`
- `scripts/outbox.py`
- `scripts/seed.py`
- `scripts/serve.py`
- `tests/__init__.py`
- `tests/conftest.py`
- `tests/test_api_and_database.py`
- `tests/test_clients.py`
- `tests/test_migration_constraints.py`
- `tests/test_outbox.py`
- `tests/test_pipeline.py`
- `tests/test_ranking.py`
- `tests/test_startup.py`
- `tests/test_webhook.py`
