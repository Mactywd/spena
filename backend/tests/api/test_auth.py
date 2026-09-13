import pytest

from itsdangerous import TimestampSigner

from app.core.security import (
    PLACEHOLDER_SECRETS,
    SESSION_COOKIE,
    InsecureSessionSecret,
    hash_password,
    is_insecure_session_secret,
    verify_password,
)


# Una rotta vera dell'applicazione, non una sonda scritta per i test: la
# `/api/v1/ping-protected` di prima esisteva solo per questi test e arrivava in
# produzione. Provare il gate su una rotta che il proprietario usa davvero dimostra
# una cosa in più — che quella rotta è dietro la sessione — e non lascia niente in
# giro. `/pantry/availability` non prende parametri e risponde con la mappa vuota.
ROTTA_PROTETTA = "/api/v1/pantry/availability"


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
    assert (await client.get(ROTTA_PROTETTA)).status_code == 401


async def test_la_documentazione_non_e_raggiungibile_senza_sessione(client):
    """Spec §9: fuori dal gate stanno solo /health e /auth/login.

    Swagger e lo schema non espongono dati, ma pubblicherebbero l'intera superficie
    dell'app a chiunque trovi l'host.
    """
    assert (await client.get("/api/v1/docs")).status_code == 401
    assert (await client.get("/api/v1/openapi.json")).status_code == 401


async def test_la_documentazione_resta_raggiungibile_con_la_sessione(
    client, configured_password
):
    """L'altra metà: spegnerla del tutto sarebbe stato più facile e meno utile."""
    await client.post("/api/v1/auth/login", json={"password": "apriti sesamo"})

    assert (await client.get("/api/v1/docs")).status_code == 200
    schema = await client.get("/api/v1/openapi.json")
    assert schema.status_code == 200
    # lo schema è quello vero dell'app, non una pagina vuota
    assert "/api/v1/recipes/search" in schema.json()["paths"]


async def test_login_sets_cookie_and_unlocks(client, configured_password):
    bad = await client.post("/api/v1/auth/login", json={"password": "sbagliata"})
    assert bad.status_code == 401

    good = await client.post("/api/v1/auth/login", json={"password": "apriti sesamo"})
    assert good.status_code == 204
    assert "spena_session" in good.cookies

    assert (await client.get(ROTTA_PROTETTA)).status_code == 200


async def test_logout_clears_the_cookie(client, configured_password):
    await client.post("/api/v1/auth/login", json={"password": "apriti sesamo"})
    await client.post("/api/v1/auth/logout")
    assert (await client.get(ROTTA_PROTETTA)).status_code == 401


async def test_tampered_cookie_is_rejected(client, configured_password):
    client.cookies.set("spena_session", "valore-inventato")
    assert (await client.get(ROTTA_PROTETTA)).status_code == 401


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


@pytest.mark.parametrize("placeholder", sorted(PLACEHOLDER_SECRETS))
async def test_a_placeholder_session_secret_opens_nothing(client, monkeypatch, placeholder):
    """I segnaposto stanno in git: un cookie firmato con loro non deve valere nulla.

    Il server mal configurato si rompe in modo rumoroso; quello che non deve
    accadere è che risponda 200 a chi non conosce la password.
    """
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("SESSION_SECRET", placeholder)
    try:
        forged = TimestampSigner(placeholder).sign(b"spena").decode()
        client.cookies.set(SESSION_COOKIE, forged)
        with pytest.raises(InsecureSessionSecret):
            await client.get(ROTTA_PROTETTA)
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("placeholder", sorted(PLACEHOLDER_SECRETS))
async def test_a_forged_cookie_is_rejected_by_a_configured_server(
    client, configured_password, placeholder
):
    """Con un segreto vero il cookie forgiato sul segnaposto è solo una firma sbagliata."""
    forged = TimestampSigner(placeholder).sign(b"spena").decode()
    client.cookies.set(SESSION_COOKIE, forged)
    assert (await client.get(ROTTA_PROTETTA)).status_code == 401


async def test_an_unconfigured_secret_cannot_issue_a_session(client, monkeypatch):
    """Password giusta ma SESSION_SECRET assente: nessun cookie utilizzabile."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_PASSWORD_HASH", hash_password("apriti sesamo"))
    monkeypatch.setenv("SESSION_SECRET", "")
    try:
        with pytest.raises(InsecureSessionSecret):
            await client.post("/api/v1/auth/login", json={"password": "apriti sesamo"})
        assert SESSION_COOKIE not in client.cookies
    finally:
        get_settings.cache_clear()


def test_the_env_file_is_resolved_absolutely(tmp_path, monkeypatch):
    """Il .env sta nella radice del repository: la CWD del processo non deve contare.

    La terza asserzione del primo giro è stata rimossa perché non aveva denti: una
    variabile d'ambiente vince comunque sul file, quindi passava anche con un percorso
    relativo. Ciò che il percorso assoluto garantisce è qui sotto.
    """
    from app.core.config import ENV_FILE, REPO_ROOT

    monkeypatch.chdir(tmp_path)
    assert ENV_FILE.is_absolute()
    assert (REPO_ROOT / "docker-compose.yml").exists(), "REPO_ROOT non è la radice del repo"


def test_the_suite_does_not_read_the_developers_env_file(monkeypatch):
    """Senza questa garanzia, un test che dimostra «variabile non configurata» legge il
    .env reale e il prossimo fa una chiamata a pagamento. Vedi il commento in conftest.
    """
    from app.core.config import Settings

    monkeypatch.delenv("APP_PASSWORD_HASH", raising=False)
    monkeypatch.delenv("SESSION_SECRET", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)

    settings = Settings()
    assert settings.app_password_hash == ""
    assert settings.session_secret == ""
    assert not settings.openrouter_api_key


def test_il_predicato_boccia_solo_i_segreti_inutilizzabili():
    """Il giudizio condiviso fra `_signer()` e il controllo all'avvio.

    Elencato qui perché è l'unico punto in cui i due controlli possono divergere: se
    qualcuno aggiunge un segnaposto a .env.example senza metterlo in
    PLACEHOLDER_SECRETS, questa lista resta la documentazione di cosa viene bocciato.
    """
    assert is_insecure_session_secret("") is True
    for placeholder in PLACEHOLDER_SECRETS:
        assert is_insecure_session_secret(placeholder) is True
    assert is_insecure_session_secret("segreto-di-test") is False


async def test_cookie_is_marked_secure_when_configured(client, monkeypatch):
    """In produzione il cookie viaggia solo su HTTPS: COOKIE_SECURE=true lo impone."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_PASSWORD_HASH", hash_password("test"))
    monkeypatch.setenv("SESSION_SECRET", "segreto-di-test")
    monkeypatch.setenv("COOKIE_SECURE", "true")
    try:
        response = await client.post("/api/v1/auth/login", json={"password": "test"})
        assert "secure" in response.headers["set-cookie"].lower()
    finally:
        get_settings.cache_clear()


async def test_cookie_is_not_secure_by_default(client, monkeypatch):
    """L'altra metà, che dà denti alla variabile.

    Un `secure=True` scritto fisso passerebbe il test di sopra e romperebbe lo
    sviluppo su http://localhost: il browser non manderebbe mai il cookie e ogni
    chiamata dopo l'accesso risponderebbe 401 senza spiegazione.
    """
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("APP_PASSWORD_HASH", hash_password("test"))
    monkeypatch.setenv("SESSION_SECRET", "segreto-di-test")
    monkeypatch.delenv("COOKIE_SECURE", raising=False)
    try:
        response = await client.post("/api/v1/auth/login", json={"password": "test"})
        assert "secure" not in response.headers["set-cookie"].lower()
    finally:
        get_settings.cache_clear()
