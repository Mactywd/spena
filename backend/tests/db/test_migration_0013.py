"""La migrazione 0013 sale e scende (S12).

Su un database suo, creato e distrutto qui, come `test_migration_0012.py`: far scendere
quello della suite toglierebbe la colonna sotto i piedi a ogni altro test. Alembic gira
in un sottoprocesso, perché il suo template async chiama `asyncio.run`, che dentro un
loop già in corsa esplode.
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
SCRATCH_DB = f"{TEST_DB}_migrazione_0013"

EMOJI = (
    "SELECT character_maximum_length FROM information_schema.columns "
    "WHERE table_name = 'ingredients' AND column_name = 'emoji'"
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


async def _ingrediente(url: str, nome: str, emoji: str | None) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO ingredients (id, name, display_name, category, kind, emoji) "
                    "VALUES (gen_random_uuid(), :nome, :nome, 'verdura', 'food', :emoji)"
                ),
                {"nome": nome, "emoji": emoji},
            )
    finally:
        await engine.dispose()


async def test_la_0013_sale_scende_e_risale(scratch_url):
    alembic(scratch_url, "upgrade", "0013")
    assert await _scalar(scratch_url, EMOJI) == 16
    await _ingrediente(scratch_url, "carota", "🥕")
    await _ingrediente(scratch_url, "sedano", None)
    figura = "SELECT emoji FROM ingredients WHERE name = :nome"
    assert await _scalar(scratch_url, figura, nome="carota") == "🥕"
    # un ingrediente nasce «non deciso» (decisione 4 della bozza: nessuna emoji alla
    # creazione): è il comando dell'AI, non la migrazione, che lo decide
    assert await _scalar(scratch_url, figura, nome="sedano") is None

    alembic(scratch_url, "downgrade", "0012")
    assert await _scalar(scratch_url, EMOJI) is None

    alembic(scratch_url, "upgrade", "head")
    assert await _scalar(scratch_url, EMOJI) == 16
