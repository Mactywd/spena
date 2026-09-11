import pytest

from app.core.security import hash_password, verify_password


def test_password_hash_roundtrip():
    hashed = hash_password("apriti sesamo")
    assert hashed != "apriti sesamo"
    assert verify_password("apriti sesamo", hashed) is True
    assert verify_password("sbagliata", hashed) is False


@pytest.fixture
def configured_password(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_PASSWORD_HASH", hash_password("apriti sesamo"))
    monkeypatch.setenv("SESSION_SECRET", "segreto-di-test")
    yield
    get_settings.cache_clear()


async def test_health_needs_no_session(client):
    assert (await client.get("/api/v1/health")).status_code == 200


async def test_protected_route_rejects_without_cookie(client):
    assert (await client.get("/api/v1/ping-protected")).status_code == 401


async def test_login_sets_cookie_and_unlocks(client, configured_password):
    bad = await client.post("/api/v1/auth/login", json={"password": "sbagliata"})
    assert bad.status_code == 401

    good = await client.post("/api/v1/auth/login", json={"password": "apriti sesamo"})
    assert good.status_code == 204
    assert "spena_session" in good.cookies

    assert (await client.get("/api/v1/ping-protected")).status_code == 200


async def test_logout_clears_the_cookie(client, configured_password):
    await client.post("/api/v1/auth/login", json={"password": "apriti sesamo"})
    await client.post("/api/v1/auth/logout")
    assert (await client.get("/api/v1/ping-protected")).status_code == 401


async def test_tampered_cookie_is_rejected(client, configured_password):
    client.cookies.set("spena_session", "valore-inventato")
    assert (await client.get("/api/v1/ping-protected")).status_code == 401


async def test_login_with_malformed_hash_is_401_not_500(client, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_PASSWORD_HASH", "non-e-un-hash-argon2-valido")
    monkeypatch.setenv("SESSION_SECRET", "segreto-di-test")
    try:
        response = await client.post(
            "/api/v1/auth/login", json={"password": "apriti sesamo"}
        )
        assert response.status_code == 401
    finally:
        get_settings.cache_clear()


async def test_login_without_configured_password_is_401(client, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_PASSWORD_HASH", "")
    monkeypatch.setenv("SESSION_SECRET", "segreto-di-test")
    try:
        response = await client.post(
            "/api/v1/auth/login", json={"password": "apriti sesamo"}
        )
        assert response.status_code == 401
    finally:
        get_settings.cache_clear()
