"""La migrazione 0015 sale e scende (R5).

Su un database suo, creato e distrutto qui, come `test_migration_0012.py`: far scendere
quello della suite toglierebbe le tabelle sotto i piedi a ogni altro test. Alembic gira
in un sottoprocesso, perché il suo template async chiama `asyncio.run`, che dentro un
loop già in corsa esplode.

Scende di **una** revisione (`downgrade -1`) e non verso un numero: al merge la
`down_revision` della 0015 si ripunta sulla testa di `master` di quel momento, e questo
test deve reggere senza essere toccato.
"""

import os
import subprocess

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://spena:spena@localhost:5433/spena_test"
)
SERVER, _, TEST_DB = TEST_DATABASE_URL.rpartition("/")
SCRATCH_DB = f"{TEST_DB}_migrazione_0015"

TABELLE = (
    "SELECT count(*) FROM information_schema.tables "
    "WHERE table_name IN ('ingredient_substitutions', 'substitution_options')"
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


async def _scrivi(url: str, sql: str, **params) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(sql), params)
    finally:
        await engine.dispose()


async def test_la_0015_sale_scende_e_risale(scratch_url):
    alembic(scratch_url, "upgrade", "0015")
    assert await _scalar(scratch_url, TABELLE) == 2
    await _scrivi(
        scratch_url,
        "INSERT INTO ingredients (id, name, display_name, category, kind) VALUES "
        "('00000000-0000-0000-0000-000000000001', 'pollo', 'Pollo', 'carne', 'food'), "
        "('00000000-0000-0000-0000-000000000002', 'tacchino', 'Tacchino', 'carne', 'food')",
    )
    await _scrivi(
        scratch_url,
        "INSERT INTO ingredient_substitutions (id, ingredient_id, context, verdict, decided_by) "
        "VALUES ('00000000-0000-0000-0000-0000000000a1', '00000000-0000-0000-0000-000000000001', "
        "'salato', 'substitutes', 'ai')",
    )
    await _scrivi(
        scratch_url,
        "INSERT INTO substitution_options (id, substitution_id, substitute_id, note, position) "
        "VALUES (gen_random_uuid(), '00000000-0000-0000-0000-0000000000a1', "
        "'00000000-0000-0000-0000-000000000002', 'metà dose', 0)",
    )
    assert await _scalar(scratch_url, "SELECT note FROM substitution_options") == "metà dose"

    alembic(scratch_url, "downgrade", "-1")
    assert await _scalar(scratch_url, TABELLE) == 0

    alembic(scratch_url, "upgrade", "head")
    assert await _scalar(scratch_url, TABELLE) == 2
