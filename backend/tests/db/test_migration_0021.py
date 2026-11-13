"""La migrazione 0021 sale e scende: conversazioni, messaggi e modifiche della ricetta.

Su un database suo, come `test_migration_0020.py`; Alembic gira in un sottoprocesso.
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
SCRATCH_DB = f"{TEST_DB}_migrazione_0021"

RICETTA = "INSERT INTO recipes (id, title, instructions, source) VALUES (:id, 'Pasta', 'Cuoci.', 'manual')"
PASTO = (
    "INSERT INTO meals (id, day, slot, dish, away, status, created_at, updated_at) "
    "VALUES (:id, :day, 'lunch', 'Pasta', false, 'official', now(), now())"
)
CONVERSAZIONE = (
    "INSERT INTO conversations (id, kind, meal_id, created_at, updated_at) "
    "VALUES (:id, :kind, :meal_id, now(), now())"
)
MESSAGGIO = (
    "INSERT INTO conversation_messages (id, conversation_id, role, text, status) "
    "VALUES (:id, :conversation_id, :role, 'ciao', :status)"
)
MODIFICA = (
    "INSERT INTO recipe_changes (id, meal_id, recipe_id, created_recipe, summary, before, after, "
    "changed) VALUES (:id, :meal_id, :recipe_id, false, 'Più sale', '{}', '{}', '{}')"
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


async def _pasto(url: str) -> uuid.UUID:
    pasto = uuid.uuid4()
    await _esegui(url, PASTO, id=pasto, day=date(2026, 11, 16))
    return pasto


TABELLE = ("conversations", "conversation_messages", "recipe_changes")


async def _tabelle(url: str) -> int:
    return await _scalar(
        url,
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ANY(:nomi)",
        nomi=list(TABELLE),
    )


async def test_la_0021_sale_e_scende(scratch_url):
    alembic(scratch_url, "upgrade", "head")
    assert await _tabelle(scratch_url) == 3
    alembic(scratch_url, "downgrade", "0020")
    assert await _tabelle(scratch_url) == 0
    assert (
        await _scalar(
            scratch_url,
            "SELECT count(*) FROM information_schema.tables WHERE table_name = 'meals'",
        )
        == 1
    )


async def test_una_chat_del_piatto_per_pasto(scratch_url):
    alembic(scratch_url, "upgrade", "head")
    pasto = await _pasto(scratch_url)
    await _esegui(scratch_url, CONVERSAZIONE, id=uuid.uuid4(), kind="dish", meal_id=pasto)
    with pytest.raises(IntegrityError):
        await _esegui(scratch_url, CONVERSAZIONE, id=uuid.uuid4(), kind="dish", meal_id=pasto)


@pytest.mark.parametrize("caso", ["tipo_sconosciuto", "piatto_senza_pasto", "pianificazione_con_pasto"])
async def test_i_vincoli_della_conversazione(scratch_url, caso):
    alembic(scratch_url, "upgrade", "head")
    pasto = await _pasto(scratch_url)
    righe = {
        "tipo_sconosciuto": {"kind": "chat", "meal_id": pasto},
        "piatto_senza_pasto": {"kind": "dish", "meal_id": None},
        "pianificazione_con_pasto": {"kind": "planning", "meal_id": pasto},
    }
    with pytest.raises(IntegrityError):
        await _esegui(scratch_url, CONVERSAZIONE, id=uuid.uuid4(), **righe[caso])


@pytest.mark.parametrize("caso", ["ruolo", "stato"])
async def test_i_vincoli_del_messaggio(scratch_url, caso):
    alembic(scratch_url, "upgrade", "head")
    pasto = await _pasto(scratch_url)
    conversazione = uuid.uuid4()
    await _esegui(scratch_url, CONVERSAZIONE, id=conversazione, kind="dish", meal_id=pasto)
    righe = {
        "ruolo": {"role": "system", "status": "sent"},
        "stato": {"role": "user", "status": "lost"},
    }
    with pytest.raises(IntegrityError):
        await _esegui(
            scratch_url, MESSAGGIO, id=uuid.uuid4(), conversation_id=conversazione, **righe[caso]
        )


async def test_cancellare_il_pasto_porta_via_chat_messaggi_e_modifiche(scratch_url):
    alembic(scratch_url, "upgrade", "head")
    pasto, ricetta, conversazione = await _pasto(scratch_url), uuid.uuid4(), uuid.uuid4()
    await _esegui(scratch_url, RICETTA, id=ricetta)
    await _esegui(scratch_url, CONVERSAZIONE, id=conversazione, kind="dish", meal_id=pasto)
    await _esegui(
        scratch_url,
        MESSAGGIO,
        id=uuid.uuid4(),
        conversation_id=conversazione,
        role="user",
        status="sent",
    )
    await _esegui(scratch_url, MODIFICA, id=uuid.uuid4(), meal_id=pasto, recipe_id=ricetta)

    await _esegui(scratch_url, "DELETE FROM meals WHERE id = :id", id=pasto)
    for tabella in TABELLE:
        assert await _scalar(scratch_url, f"SELECT count(*) FROM {tabella}") == 0
