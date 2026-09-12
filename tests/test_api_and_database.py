from unittest.mock import patch
from uuid import uuid4

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.config import Settings
from app.db.models import Resident, Vendor, VendorFeedback
from scripts.seed import seed_demo, seed_id


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "connected", "service": "home-assistant"}


async def test_health_database_failure(client, engine):
    with patch.object(
        type(engine), "connect", side_effect=OperationalError("secret statement", {}, Exception())
    ):
        response = await client.get("/health")
    assert response.status_code == 503
    assert "secret" not in response.text
    assert response.json()["database"] == "disconnected"


async def test_apis_and_auth(client, settings):
    assert len((await client.get("/api/services")).json()) == 15
    vendors = (await client.get("/api/vendors", params={"service": "plumber"})).json()
    assert vendors
    assert all(v["active"] for v in vendors)
    assert (await client.get("/api/vendors/" + vendors[0]["id"])).status_code == 200
    assert (await client.get("/api/vendors/" + str(uuid4()))).status_code == 404
    assert (await client.get("/api/vendors/not-uuid")).status_code == 422
    assert (await client.get("/api/vendors?limit=101")).status_code == 422
    assert len((await client.get("/api/service-requests?unmet_demand=true")).json()) == 1
    assert len((await client.get(f"/api/residents/{seed_id('resident/1')}/requests")).json()) == 2
    assert (await client.get(f"/api/residents/{uuid4()}/requests")).status_code == 404
    # Assignment is intentionally through SecretStr, as environment loading would do.
    from pydantic import SecretStr

    settings.admin_api_key = SecretStr("admin-test")
    assert (await client.get("/api/service-requests")).status_code == 401
    assert (
        await client.get("/api/service-requests", headers={"X-Admin-Key": "admin-test"})
    ).status_code == 200
    assert (await client.get("/openapi.json")).status_code == 200


async def test_seed_is_repeatable_and_synthetic(sessions, seeded):
    async with sessions.begin() as session:
        again = await seed_demo(session)
        assert again == seeded
        assert again == {
            "societies": 1,
            "residents": 5,
            "service_categories": 15,
            "vendors": 20,
            "vendor_services": 40,
            "service_requests": 6,
            "service_request_vendors": 5,
            "conversations": 5,
            "messages": 12,
            "vendor_feedback": 5,
        }
        assert all(
            p.startswith("TEST-")
            for p in (await session.scalars(select(Resident.whatsapp_number))).all()
        )
        assert all(
            p.startswith("TEST-")
            for p in (await session.scalars(select(Vendor.primary_phone))).all()
        )


async def test_unique_resident_enforced(sessions, seeded):
    with pytest.raises(IntegrityError):
        async with sessions.begin() as session:
            session.add(Resident(whatsapp_number="TEST-RESIDENT-001"))
            await session.flush()


@pytest.mark.parametrize("rating", [0, 6])
async def test_feedback_rating_constraint(sessions, seeded, rating):
    with pytest.raises(IntegrityError):
        async with sessions.begin() as session:
            session.add(
                VendorFeedback(
                    service_request_id=seed_id("request/6"),
                    resident_id=seed_id("resident/1"),
                    vendor_id=seed_id("vendor/1"),
                    rating=rating,
                )
            )
            await session.flush()


def test_legacy_environment_aliases(monkeypatch):
    monkeypatch.setenv("EVOLUTION_API_URL", "https://example.test")
    monkeypatch.setenv("EVOLUTION_INSTANCE", "legacy")
    result = Settings(_env_file=None)
    assert result.evolution_api_base_url == "https://example.test"
    assert result.evolution_api_instance == "legacy"


def test_production_rejects_missing_credentials():
    with pytest.raises(ValueError):
        Settings(_env_file=None, app_env="production")


def test_configuration_errors_do_not_expose_secrets():
    with pytest.raises(ValueError) as exc:
        Settings(
            _env_file=None,
            app_env="production",
            openai_api_key="private-llm-test-value",
            evolution_api_key="private-evolution-test-value",
            evolution_api_base_url="not-a-url",
        )
    assert "private-llm-test-value" not in str(exc.value)
    assert "private-evolution-test-value" not in str(exc.value)
