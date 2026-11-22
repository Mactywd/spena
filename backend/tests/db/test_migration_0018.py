"""La migrazione 0018 sale e scende (H2): le cinque tabelle dell'attività.

Su un database suo, creato e distrutto qui, come `test_migration_0012.py`: far scendere
quello della suite toglierebbe le tabelle sotto i piedi a ogni altro test. Alembic gira
in un sottoprocesso, perché il suo template async chiama `asyncio.run`, che dentro un
loop già in corsa esplode.
"""

import os
import subprocess
import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://spena:spena@localhost:5433/spena_test"
)
SERVER, _, TEST_DB = TEST_DATABASE_URL.rpartition("/")
SCRATCH_DB = f"{TEST_DB}_migrazione_0018"

TABELLE = (
    "SELECT count(*) FROM information_schema.tables WHERE table_name IN "
    "('activity_tokens', 'activity_steps_days', 'activity_exercises', 'activity_weights', "
    "'activity_syncs')"
)
CHIAVE = (
    "INSERT INTO activity_tokens (id, token_hash, created_at) "
    "VALUES (:id, :impronta, now())"
)
ALLENAMENTO = (
    "INSERT INTO activity_exercises (id, source, started_at, ended_at, day) "
    "VALUES (:id, 'com.sec.android.app.shealth', '2026-10-12T16:00:00Z', :fine, '2026-10-12')"
)


def alembic(url: str, *args: str) -> None:
    subprocess.run(["alembic", *args], check=True, env={**os.environ, "DATABASE_URL": url})


@pytest_asyncio.fixture
async def scratch_url():
    admin = create_async_engine(f"{SERVER}/postgres", isolation_level="AUTOCOMMIT")
    async with admin.connect() as conn:
        await conn.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)'))
        await conn.execute(text(f'CREATE DATABASE "{SCRATCH_DB}"'))
    try:
        yield f"{SERVER}/{SCRATCH_DB}"
    finally:
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)'))
        await admin.dispose()


async def _scalar(url: str, sql: str, **params):
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            return (await conn.execute(text(sql), params)).scalar()
    finally:
        await engine.dispose()


async def _esegui(url: str, sql: str, **params) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(sql), params)
    finally:
        await engine.dispose()


async def test_la_0018_sale_scende_e_risale(scratch_url):
    alembic(scratch_url, "upgrade", "0018")
    assert await _scalar(scratch_url, TABELLE) == 5

    # la chiave è una sola: la riga 1, e nessun'altra
    await _esegui(scratch_url, CHIAVE, id=1, impronta="a" * 64)
    with pytest.raises(IntegrityError):
        await _esegui(scratch_url, CHIAVE, id=2, impronta="b" * 64)

    # lo stesso allenamento della stessa app non entra due volte
    await _esegui(
        scratch_url,
        ALLENAMENTO,
        id=uuid.uuid4(),
        fine=datetime(2026, 10, 12, 16, 30, tzinfo=UTC),
    )
    with pytest.raises(IntegrityError):
        await _esegui(
            scratch_url,
            ALLENAMENTO,
            id=uuid.uuid4(),
            fine=datetime(2026, 10, 12, 16, 45, tzinfo=UTC),
        )

    alembic(scratch_url, "downgrade", "0017")
    assert await _scalar(scratch_url, TABELLE) == 0

    alembic(scratch_url, "upgrade", "head")
    assert await _scalar(scratch_url, TABELLE) == 5
