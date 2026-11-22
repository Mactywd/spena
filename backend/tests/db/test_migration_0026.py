"""La migrazione 0026 sale e scende: le righe di dispensa che hanno portato una riga di lista.

Su un database suo, come `test_migration_0024.py`; Alembic gira in un sottoprocesso.
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
SCRATCH_DB = f"{TEST_DB}_migrazione_0026"

SCHEDA = (
    "INSERT INTO change_cards (id, kind, status, title) "
    "VALUES (:id, 'forward', 'applied', 'Cena di sabato')"
)
RIGA_DI_LISTA = (
    "INSERT INTO change_card_rows (id, card_id, position, kind, label, checked) "
    "VALUES (:id, :card_id, 0, 'list', 'passata', true)"
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


async def _esegui(url: str, sql: str, **params) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.execute(text(sql), params)
    finally:
        await engine.dispose()


async def _colonna(url: str) -> int:
    return await _scalar(
        url,
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name = 'change_card_rows' AND column_name = 'from_pantry_row_ids' "
        "AND is_nullable = 'NO' AND data_type = 'jsonb'",
    )


async def test_la_0026_sale_e_scende(scratch_url):
    alembic(scratch_url, "upgrade", "0025")
    scheda = uuid.uuid4()
    await _esegui(scratch_url, SCHEDA, id=scheda)
    await _esegui(scratch_url, RIGA_DI_LISTA, id=uuid.uuid4(), card_id=scheda)
    alembic(scratch_url, "upgrade", "head")
    assert await _colonna(scratch_url) == 1
    # una riga scritta prima sta in piedi da sola, come oggi
    assert await _scalar(
        scratch_url, "SELECT from_pantry_row_ids FROM change_card_rows"
    ) == []
    alembic(scratch_url, "downgrade", "0025")
    assert await _colonna(scratch_url) == 0
    assert await _scalar(scratch_url, "SELECT count(*) FROM change_card_rows") == 1
