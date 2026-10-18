"""La migrazione 0016 sale, scende e risale (S4, fetta 1).

Su un database suo, creato e distrutto qui, come `test_migration_0012.py`: far scendere
quello della suite toglierebbe le tabelle sotto i piedi a ogni altro test. Alembic gira
in un sottoprocesso, perché il suo template async chiama `asyncio.run`, che dentro un
loop già in corsa esplode.
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
SCRATCH_DB = f"{TEST_DB}_migrazione_0016"

TABELLE = (
    "SELECT count(*) FROM information_schema.tables "
    "WHERE table_name IN ('ciqual_foods', 'ingredient_nutrition')"
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


async def test_la_0016_sale_scende_e_risale(scratch_url):
    alembic(scratch_url, "upgrade", "0016")
    assert await _scalar(scratch_url, TABELLE) == 2

    await _run(
        scratch_url,
        "INSERT INTO ciqual_foods (code, name_fr, group_fr, nutrients, version) "
        "VALUES ('90001', 'Tomate, crue', 'légumes', '{\"kcal\": 18}', '2025')",
        "INSERT INTO ingredients (id, name, display_name, category, kind) "
        "VALUES ('00000000-0000-0000-0000-000000000001', 'pomodoro', 'Pomodoro', 'verdura', 'food')",
        "INSERT INTO ingredient_nutrition (ingredient_id, ciqual_code, decided_by) "
        "VALUES ('00000000-0000-0000-0000-000000000001', '90001', 'ai')",
    )
    # chi ha deciso è uno dei due, e nient'altro
    with pytest.raises(IntegrityError):
        await _run(
            scratch_url,
            "UPDATE ingredient_nutrition SET decided_by = 'robot'",
        )
    # un alimento scelto da un ingrediente non si cancella da sotto
    with pytest.raises(IntegrityError):
        await _run(scratch_url, "DELETE FROM ciqual_foods WHERE code = '90001'")
    # cancellare l'ingrediente cancella la sua scelta
    await _run(scratch_url, "DELETE FROM ingredients WHERE name = 'pomodoro'")
    assert await _scalar(scratch_url, "SELECT count(*) FROM ingredient_nutrition") == 0

    alembic(scratch_url, "downgrade", "0012")
    assert await _scalar(scratch_url, TABELLE) == 0

    alembic(scratch_url, "upgrade", "head")
    assert await _scalar(scratch_url, TABELLE) == 2
