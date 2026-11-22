"""La migrazione 0019 sale e scende: la tabella degli utensili di cucina.

Su un database suo, creato e distrutto qui, come `test_migration_0018.py`: far scendere
quello della suite toglierebbe le tabelle sotto i piedi a ogni altro test. Alembic gira
in un sottoprocesso, perché il suo template async chiama `asyncio.run`.
"""

import os
import subprocess
import uuid

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://spena:spena@localhost:5433/spena_test"
)
SERVER, _, TEST_DB = TEST_DATABASE_URL.rpartition("/")
SCRATCH_DB = f"{TEST_DB}_migrazione_0019"

TABELLA = "SELECT count(*) FROM information_schema.tables WHERE table_name = 'utensils'"
UTENSILE = "INSERT INTO utensils (id, name, note) VALUES (:id, :nome, :nota)"


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


async def _execute(url: str, sql: str, **params) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(sql), params)
    finally:
        await engine.dispose()


async def test_la_0019_crea_gli_utensili_e_scende(scratch_url):
    alembic(scratch_url, "upgrade", "0019")
    assert await _scalar(scratch_url, TABELLA) == 1
    await _execute(scratch_url, UTENSILE, id=uuid.uuid4(), nome="padella antiaderente", nota="da 24 cm")
    assert await _scalar(scratch_url, "SELECT count(*) FROM utensils") == 1
    alembic(scratch_url, "downgrade", "0018")
    assert await _scalar(scratch_url, TABELLA) == 0


async def test_un_nome_di_soli_spazi_non_entra(scratch_url):
    alembic(scratch_url, "upgrade", "0019")
    with pytest.raises(IntegrityError, match="ck_utensils_name_not_blank"):
        await _execute(scratch_url, UTENSILE, id=uuid.uuid4(), nome="   ", nota=None)
