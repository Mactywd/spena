"""La migrazione 0025 sale e scende: i token della cache in `llm_calls`.

Su un database suo, come `test_migration_0024.py`; Alembic gira in un sottoprocesso.
"""

import os
import subprocess

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://spena:spena@localhost:5433/spena_test"
)
SERVER, _, TEST_DB = TEST_DATABASE_URL.rpartition("/")
SCRATCH_DB = f"{TEST_DB}_migrazione_0025"

RIGA_VECCHIA = (
    "INSERT INTO llm_calls (id, call_site, ok, prompt_tokens, completion_tokens, cost_usd) "
    "VALUES (gen_random_uuid(), 'term_decision', true, 3100, 35, 0.000123)"
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


async def _esegui(url: str, sql: str) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(sql))
    finally:
        await engine.dispose()


async def _colonne_cache(url: str) -> int:
    return await _scalar(
        url,
        "SELECT count(*) FROM information_schema.columns WHERE table_name = 'llm_calls' "
        "AND column_name IN ('cache_read_tokens', 'cache_write_tokens') "
        "AND is_nullable = 'YES' AND data_type = 'integer'",
    )


async def test_la_0025_sale_e_scende(scratch_url):
    alembic(scratch_url, "upgrade", "0024")
    await _esegui(scratch_url, RIGA_VECCHIA)
    alembic(scratch_url, "upgrade", "head")
    assert await _colonne_cache(scratch_url) == 2
    assert await _scalar(
        scratch_url,
        "SELECT count(*) FROM llm_calls "
        "WHERE cache_read_tokens IS NULL AND cache_write_tokens IS NULL",
    ) == 1
    alembic(scratch_url, "downgrade", "0024")
    assert await _colonne_cache(scratch_url) == 0
