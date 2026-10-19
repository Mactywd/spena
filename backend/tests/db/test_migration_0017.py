"""La migrazione 0017 sale, scende e risale (S4, fetta 2), su un database suo.

Il vincolo che conta è `UNIQUE NULLS NOT DISTINCT`: senza, due righe «pezzo» (unità NULL)
dello stesso ingrediente sarebbero per Postgres due righe diverse, e il peso dell'uovo
potrebbe esistere due volte con due valori.
"""

import os
import subprocess

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://spena:spena@localhost:5433/spena_test"
)
SERVER, _, TEST_DB = TEST_DATABASE_URL.rpartition("/")
SCRATCH_DB = f"{TEST_DB}_migrazione_0017"
TABELLA = "SELECT count(*) FROM information_schema.tables WHERE table_name = 'ingredient_unit_grams'"
UOVA = "00000000-0000-0000-0000-000000000001"
SPICCHIO = "00000000-0000-0000-0000-000000000002"


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


async def _scalar(url: str, sql: str):
    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            return (await conn.execute(text(sql))).scalar()
    finally:
        await engine.dispose()


async def _run(url: str, *statements: str) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            for statement in statements:
                await conn.execute(text(statement))
    finally:
        await engine.dispose()


def _peso(unita: str, grammi: str) -> str:
    return (
        "INSERT INTO ingredient_unit_grams (id, ingredient_id, unit_id, grams, decided_by) "
        f"VALUES (gen_random_uuid(), '{UOVA}', {unita}, {grammi}, 'ai')"
    )


async def test_la_0017_sale_scende_e_risale(scratch_url):
    alembic(scratch_url, "upgrade", "0017")
    assert await _scalar(scratch_url, TABELLA) == 1

    await _run(
        scratch_url,
        "INSERT INTO ingredients (id, name, display_name, category, kind) "
        f"VALUES ('{UOVA}', 'uova', 'Uova', 'altro', 'food')",
        f"INSERT INTO units (id, key) VALUES ('{SPICCHIO}', 'spicchio')",
        _peso("NULL", "50"),
        _peso(f"'{SPICCHIO}'", "NULL"),
    )
    # un secondo «pezzo» dello stesso ingrediente non entra: NULLS NOT DISTINCT
    with pytest.raises(IntegrityError):
        await _run(scratch_url, _peso("NULL", "55"))
    # un peso è più di zero, o è NULL («nessun peso»)
    with pytest.raises(IntegrityError):
        await _run(scratch_url, "UPDATE ingredient_unit_grams SET grams = 0")
    # un'unità cancellata si porta via i suoi pesi (la pulizia delle dosi ne toglie)
    await _run(scratch_url, f"DELETE FROM units WHERE id = '{SPICCHIO}'")
    assert await _scalar(scratch_url, "SELECT count(*) FROM ingredient_unit_grams") == 1
    # e un ingrediente cancellato i suoi
    await _run(scratch_url, f"DELETE FROM ingredients WHERE id = '{UOVA}'")
    assert await _scalar(scratch_url, "SELECT count(*) FROM ingredient_unit_grams") == 0

    alembic(scratch_url, "downgrade", "0016")
    assert await _scalar(scratch_url, TABELLA) == 0

    alembic(scratch_url, "upgrade", "head")
    assert await _scalar(scratch_url, TABELLA) == 1
