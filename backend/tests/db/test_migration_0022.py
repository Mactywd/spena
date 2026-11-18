"""La migrazione 0022 sale e scende: proposte, schede dei cambi, posto di partenza, ricetta chiesta.

Su un database suo, come `test_migration_0021.py`; Alembic gira in un sottoprocesso.
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
SCRATCH_DB = f"{TEST_DB}_migrazione_0022"

CONVERSAZIONE = (
    "INSERT INTO conversations (id, kind, meal_id, created_at, updated_at) "
    "VALUES (:id, 'planning', NULL, now(), now())"
)
PROPOSTA = (
    "INSERT INTO meal_proposals (id, conversation_id, kind, rows) "
    "VALUES (:id, :conversation_id, :kind, '[]')"
)
SCHEDA = (
    "INSERT INTO change_cards (id, kind, status, title, conversation_id) "
    "VALUES (:id, :kind, :status, 'Cena di sabato', :conversation_id)"
)
RIGA = (
    "INSERT INTO change_card_rows (id, card_id, position, kind, label, to_status, checked) "
    "VALUES (:id, :card_id, 0, :kind, 'parmigiano', :to_status, true)"
)

TABELLE = ("meal_proposals", "change_cards", "change_card_rows")
COLONNE = (
    ("conversations", "focus_day"),
    ("conversations", "focus_slot"),
    ("meals", "recipe_requested_at"),
    ("meals", "recipe_notice"),
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


async def _tabelle(url: str) -> int:
    return await _scalar(
        url,
        "SELECT count(*) FROM information_schema.tables WHERE table_name = ANY(:nomi)",
        nomi=list(TABELLE),
    )


async def _colonne(url: str) -> int:
    totale = 0
    for tabella, colonna in COLONNE:
        totale += await _scalar(
            url,
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c",
            t=tabella,
            c=colonna,
        )
    return totale


async def test_la_0022_sale_e_scende(scratch_url):
    alembic(scratch_url, "upgrade", "head")
    assert await _tabelle(scratch_url) == 3
    assert await _colonne(scratch_url) == 4
    alembic(scratch_url, "downgrade", "0021")
    assert await _tabelle(scratch_url) == 0
    assert await _colonne(scratch_url) == 0
    for tabella in ("meals", "conversations"):
        assert (
            await _scalar(
                scratch_url,
                "SELECT count(*) FROM information_schema.tables WHERE table_name = :t",
                t=tabella,
            )
            == 1
        )


@pytest.mark.parametrize(
    "caso",
    [
        "proposta_tipo",
        "scheda_stato",
        "riga_pantry_senza_stato",
        "riga_stato_vuoto",
        "focus_day_senza_slot",
    ],
)
async def test_i_vincoli_della_proposta_e_della_scheda(scratch_url, caso):
    alembic(scratch_url, "upgrade", "head")
    conversazione, scheda = uuid.uuid4(), uuid.uuid4()
    await _esegui(scratch_url, CONVERSAZIONE, id=conversazione)
    await _esegui(
        scratch_url, SCHEDA, id=scheda, kind="forward", status="proposed", conversation_id=None
    )
    prove = {
        "proposta_tipo": (
            PROPOSTA, {"id": uuid.uuid4(), "conversation_id": conversazione, "kind": "maybe"}
        ),
        "scheda_stato": (
            SCHEDA,
            {"id": uuid.uuid4(), "kind": "forward", "status": "done", "conversation_id": None},
        ),
        "riga_pantry_senza_stato": (
            RIGA, {"id": uuid.uuid4(), "card_id": scheda, "kind": "pantry", "to_status": None}
        ),
        "riga_stato_vuoto": (
            RIGA, {"id": uuid.uuid4(), "card_id": scheda, "kind": "pantry", "to_status": "empty"}
        ),
        "focus_day_senza_slot": (
            "UPDATE conversations SET focus_day = :d WHERE id = :id",
            {"id": conversazione, "d": date(2026, 11, 16)},
        ),
    }
    sql, params = prove[caso]
    with pytest.raises(IntegrityError):
        await _esegui(scratch_url, sql, **params)


async def test_cancellare_la_conversazione_porta_via_le_proposte_e_lascia_le_schede(scratch_url):
    alembic(scratch_url, "upgrade", "head")
    conversazione, proposta, scheda = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await _esegui(scratch_url, CONVERSAZIONE, id=conversazione)
    await _esegui(
        scratch_url, PROPOSTA, id=proposta, conversation_id=conversazione, kind="draft"
    )
    await _esegui(
        scratch_url, SCHEDA, id=scheda, kind="inverse", status="proposed",
        conversation_id=conversazione,
    )

    await _esegui(scratch_url, "DELETE FROM conversations WHERE id = :id", id=conversazione)
    assert await _scalar(scratch_url, "SELECT count(*) FROM meal_proposals") == 0
    assert await _scalar(
        scratch_url, "SELECT conversation_id IS NULL FROM change_cards WHERE id = :id", id=scheda
    ) is True


async def test_cancellare_la_scheda_porta_via_le_righe(scratch_url):
    alembic(scratch_url, "upgrade", "head")
    scheda = uuid.uuid4()
    await _esegui(
        scratch_url, SCHEDA, id=scheda, kind="forward", status="proposed", conversation_id=None
    )
    await _esegui(
        scratch_url, RIGA, id=uuid.uuid4(), card_id=scheda, kind="pantry", to_status="low"
    )
    assert await _scalar(scratch_url, "SELECT count(*) FROM change_card_rows") == 1

    await _esegui(scratch_url, "DELETE FROM change_cards WHERE id = :id", id=scheda)
    assert await _scalar(scratch_url, "SELECT count(*) FROM change_card_rows") == 0
