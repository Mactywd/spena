"""La migrazione 0023 sale e scende: gli ingredienti creati da una modifica della ricetta.

Su un database suo, come `test_migration_0021.py`; Alembic gira in un sottoprocesso.
"""

import os
import subprocess
import uuid
from datetime import date

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://spena:spena@localhost:5433/spena_test"
)
SERVER, _, TEST_DB = TEST_DATABASE_URL.rpartition("/")
SCRATCH_DB = f"{TEST_DB}_migrazione_0023"

RICETTA = "INSERT INTO recipes (id, title, instructions, source) VALUES (:id, 'Pasta', 'Cuoci.', 'manual')"
PASTO = (
    "INSERT INTO meals (id, day, slot, dish, away, status, created_at, updated_at) "
    "VALUES (:id, :day, 'lunch', 'Pasta', false, 'official', now(), now())"
)
MODIFICA = (
    "INSERT INTO recipe_changes (id, meal_id, recipe_id, created_recipe, summary, before, after, "
    "changed) VALUES (:id, :meal_id, :recipe_id, false, 'Più sale', '{}', '{}', '{}')"
)
COLONNA = (
    "SELECT count(*) FROM information_schema.columns "
    "WHERE table_name = 'recipe_changes' AND column_name = 'created_ingredient_ids'"
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


async def test_la_0023_sale_e_scende(scratch_url):
    alembic(scratch_url, "upgrade", "0022")
    assert await _scalar(scratch_url, COLONNA) == 0
    pasto, ricetta, modifica = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await _esegui(scratch_url, PASTO, id=pasto, day=date(2026, 11, 16))
    await _esegui(scratch_url, RICETTA, id=ricetta)
    await _esegui(scratch_url, MODIFICA, id=modifica, meal_id=pasto, recipe_id=ricetta)

    alembic(scratch_url, "upgrade", "head")
    assert await _scalar(scratch_url, COLONNA) == 1
    # una modifica scritta con la 0022 non ricorda niente: non toglie niente
    assert await _scalar(
        scratch_url, "SELECT created_ingredient_ids::text FROM recipe_changes WHERE id = :id",
        id=modifica,
    ) == "[]"

    alembic(scratch_url, "downgrade", "0022")
    assert await _scalar(scratch_url, COLONNA) == 0
