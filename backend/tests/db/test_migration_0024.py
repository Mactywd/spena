"""La migrazione 0024 sale e scende: pasto fuori casa con ricetta, scheda sostituita, origini dell'inversa.

Su un database suo, come `test_migration_0022.py`; Alembic gira in un sottoprocesso.
"""

import os
import subprocess
import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://spena:spena@localhost:5433/spena_test"
)
SERVER, _, TEST_DB = TEST_DATABASE_URL.rpartition("/")
SCRATCH_DB = f"{TEST_DB}_migrazione_0024"

RICETTA = (
    "INSERT INTO recipes (id, title, instructions, source) "
    "VALUES (:id, 'Pasta', 'Cuoci.', 'manual')"
)
PASTO_FUORI_CASA = (
    "INSERT INTO meals (id, day, slot, dish, away, status, recipe_id, created_at, updated_at) "
    "VALUES (:id, :day, 'lunch', 'Pasta', true, 'official', :recipe_id, now(), now())"
)
SCHEDA = (
    "INSERT INTO change_cards (id, kind, status, title) "
    "VALUES (:id, 'forward', :status, 'Cena di sabato')"
)
RIGA = (
    "INSERT INTO change_card_rows (id, card_id, position, kind, label, to_status, checked) "
    "VALUES (:id, :card_id, 0, 'pantry', 'parmigiano', 'low', true)"
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


async def _vincolo_fuori_casa(url: str) -> int:
    return await _scalar(
        url,
        "SELECT count(*) FROM pg_constraint WHERE conname = 'ck_meal_away_no_recipe'",
    )


async def _colonna_origini(url: str) -> int:
    return await _scalar(
        url,
        "SELECT count(*) FROM information_schema.columns "
        "WHERE table_name = 'change_card_rows' AND column_name = 'source_row_ids'",
    )


async def test_la_0024_sale_e_scende(scratch_url):
    alembic(scratch_url, "upgrade", "head")
    assert await _vincolo_fuori_casa(scratch_url) == 0
    assert await _colonna_origini(scratch_url) == 1
    alembic(scratch_url, "downgrade", "0023")
    assert await _vincolo_fuori_casa(scratch_url) == 1
    assert await _colonna_origini(scratch_url) == 0


async def test_un_pasto_fuori_casa_puo_tenere_la_ricetta(scratch_url):
    alembic(scratch_url, "upgrade", "head")
    ricetta = uuid.uuid4()
    await _esegui(scratch_url, RICETTA, id=ricetta)
    await _esegui(
        scratch_url, PASTO_FUORI_CASA, id=uuid.uuid4(), day=date(2026, 11, 16), recipe_id=ricetta
    )
    assert await _scalar(scratch_url, "SELECT count(*) FROM meals WHERE away") == 1


async def test_una_scheda_puo_essere_sostituita(scratch_url):
    alembic(scratch_url, "upgrade", "head")
    await _esegui(scratch_url, SCHEDA, id=uuid.uuid4(), status="superseded")
    assert await _scalar(scratch_url, "SELECT count(*) FROM change_cards") == 1
    with pytest.raises(IntegrityError):
        await _esegui(scratch_url, SCHEDA, id=uuid.uuid4(), status="lost")


async def test_le_origini_dell_inversa_hanno_un_default(scratch_url):
    alembic(scratch_url, "upgrade", "head")
    scheda = uuid.uuid4()
    await _esegui(scratch_url, SCHEDA, id=scheda, status="proposed")
    await _esegui(scratch_url, RIGA, id=uuid.uuid4(), card_id=scheda)
    assert await _scalar(scratch_url, "SELECT source_row_ids FROM change_card_rows") == []


async def test_la_0024_scende_staccando_le_ricette_fuori_casa(scratch_url):
    alembic(scratch_url, "upgrade", "head")
    ricetta, pasto, scheda = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await _esegui(scratch_url, RICETTA, id=ricetta)
    await _esegui(
        scratch_url, PASTO_FUORI_CASA, id=pasto, day=date(2026, 11, 16), recipe_id=ricetta
    )
    await _esegui(scratch_url, SCHEDA, id=scheda, status="superseded")

    alembic(scratch_url, "downgrade", "0023")
    assert await _scalar(
        scratch_url, "SELECT recipe_id IS NULL FROM meals WHERE id = :id", id=pasto
    ) is True
    assert await _scalar(
        scratch_url, "SELECT status FROM change_cards WHERE id = :id", id=scheda
    ) == "discarded"
