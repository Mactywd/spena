"""La migrazione 0014 sale e scende (R8): il legame di una variante con la sua originale.

Su un database suo, creato e distrutto qui, come `test_migration_0012.py`: far scendere
quello della suite toglierebbe la colonna sotto i piedi a ogni altro test. Alembic gira
in un sottoprocesso, perché il suo template async chiama `asyncio.run`, che dentro un
loop già in corsa esplode.
"""

import os
import subprocess
import uuid

import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://spena:spena@localhost:5433/spena_test"
)
SERVER, _, TEST_DB = TEST_DATABASE_URL.rpartition("/")
SCRATCH_DB = f"{TEST_DB}_migrazione_0014"

COLONNA = (
    "SELECT is_nullable FROM information_schema.columns "
    "WHERE table_name = 'recipes' AND column_name = 'derived_from_id'"
)
REGOLA = (
    "SELECT rc.delete_rule FROM information_schema.referential_constraints rc "
    "JOIN information_schema.key_column_usage k ON k.constraint_name = rc.constraint_name "
    "WHERE k.table_name = 'recipes' AND k.column_name = 'derived_from_id'"
)
RICETTA = (
    "INSERT INTO recipes (id, title, instructions, source, derived_from_id) "
    "VALUES (:id, :titolo, 'Cuoci.', :fonte, :da)"
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


async def test_la_0014_sale_scende_e_risale(scratch_url):
    alembic(scratch_url, "upgrade", "0014")
    assert await _scalar(scratch_url, COLONNA) == "YES"
    assert await _scalar(scratch_url, REGOLA) == "SET NULL"

    originale, variante = uuid.uuid4(), uuid.uuid4()
    await _esegui(scratch_url, RICETTA, id=originale, titolo="Torta di mele", fonte="manual", da=None)
    await _esegui(
        scratch_url, RICETTA, id=variante, titolo="Torta di mele con dolcificante", fonte="ai",
        da=originale,
    )
    # cancellare l'originale non cancella la variante: perde soltanto il legame
    await _esegui(scratch_url, "DELETE FROM recipes WHERE id = :id", id=originale)
    restata = "SELECT count(*) FROM recipes WHERE id = :id"
    assert await _scalar(scratch_url, restata, id=variante) == 1
    legame = "SELECT derived_from_id FROM recipes WHERE id = :id"
    assert await _scalar(scratch_url, legame, id=variante) is None

    alembic(scratch_url, "downgrade", "0013")
    assert await _scalar(scratch_url, COLONNA) is None

    alembic(scratch_url, "upgrade", "head")
    assert await _scalar(scratch_url, COLONNA) == "YES"
