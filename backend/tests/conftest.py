import os
import subprocess

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

os.environ.setdefault("EMBEDDING_BACKEND", "fake")

# La suite non legge il .env dello sviluppatore. Da quando `env_file` è un percorso
# assoluto (app/core/config.py) quel file viene trovato anche sotto pytest, e un test
# che dimostra il comportamento "variabile non configurata" ricadrebbe in silenzio sul
# valore reale: con OPENROUTER_API_KEY valorizzata, i test che verificano la
# degradazione senza chiave costruirebbero una richiesta vera e farebbero una chiamata a
# pagamento, contro la regola di CLAUDE.md per cui la suite non tocca la rete.
# Neutralizzarlo qui, prima che Settings venga istanziata la prima volta, vale per tutti
# i test presenti e futuri: ciò che un test vuole configurato lo imposta come variabile
# d'ambiente, esplicitamente.
from app.core.config import Settings  # noqa: E402

Settings.model_config["env_file"] = None

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://spena:spena@localhost:5433/spena_test"
)


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DATABASE_URL)
    async with eng.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))

    # Alembic gira in un sottoprocesso: il template async chiama asyncio.run al
    # suo interno, che esplode se invocato dentro un loop già in esecuzione.
    subprocess.run(
        ["alembic", "upgrade", "head"],
        check=True,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
    )
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncSession:
    """Ogni test in una transazione annullata alla fine: nessuna fuga di stato.

    `join_transaction_mode="create_savepoint"` è indispensabile: il codice
    dell'applicazione chiama `commit()` e `rollback()` sulla sessione, e senza i
    savepoint quelle chiamate chiuderebbero la transazione esterna del test.
    """
    connection = await engine.connect()
    transaction = await connection.begin()
    session = async_sessionmaker(
        bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )()
    yield session
    await session.close()
    await transaction.rollback()
    await connection.close()


@pytest_asyncio.fixture
async def client(db_session) -> AsyncClient:
    from app.core.db import get_session
    from app.main import app

    app.dependency_overrides[get_session] = lambda: db_session
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def logged_client(client, monkeypatch):
    """Client con sessione già valida: evita di rifare il login in ogni test."""
    from app.core.config import get_settings
    from app.core.security import hash_password

    get_settings.cache_clear()
    monkeypatch.setenv("APP_PASSWORD_HASH", hash_password("test"))
    monkeypatch.setenv("SESSION_SECRET", "segreto-di-test")
    await client.post("/api/v1/auth/login", json={"password": "test"})
    yield client
    get_settings.cache_clear()
