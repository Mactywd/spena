"""La migrazione 0020 sale e scende: `meals` e `recipes.in_book`.

Su un database suo, creato e distrutto qui, come `test_migration_0018.py`. Alembic gira
in un sottoprocesso (il suo template async chiama `asyncio.run`).
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
SCRATCH_DB = f"{TEST_DB}_migrazione_0020"

RICETTA = "INSERT INTO recipes (id, title, instructions, source) VALUES (:id, 'Pasta', 'Cuoci.', 'manual')"
PASTO = (
    "INSERT INTO meals (id, day, slot, dish, away, status, recipe_id, leftover_of_id, "
    "created_at, updated_at) VALUES (:id, :day, :slot, :dish, :away, :status, :recipe_id, "
    ":leftover_of_id, now(), now())"
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


def _pasto(**over):
    base = {
        "id": uuid.uuid4(),
        "day": "2026-11-16",
        "slot": "lunch",
        "dish": "Pasta",
        "away": False,
        "status": "official",
        "recipe_id": None,
        "leftover_of_id": None,
    }
    base.update(over)
    return base


def _dati(**over):
    from datetime import date

    p = _pasto(**over)
    p["day"] = date.fromisoformat(p["day"])
    return p


async def test_la_0020_sale_e_le_ricette_che_ci_sono_restano_nel_ricettario(scratch_url):
    alembic(scratch_url, "upgrade", "0019")
    await _esegui(scratch_url, RICETTA, id=uuid.uuid4())
    alembic(scratch_url, "upgrade", "head")
    assert await _scalar(scratch_url, "SELECT in_book FROM recipes") is True


async def test_un_posto_tiene_un_pasto_solo(scratch_url):
    alembic(scratch_url, "upgrade", "head")
    await _esegui(scratch_url, PASTO, **_dati())
    with pytest.raises(IntegrityError):
        await _esegui(scratch_url, PASTO, **_dati(dish="Altro"))


async def test_una_ricetta_appartiene_a_un_pasto_solo(scratch_url):
    alembic(scratch_url, "upgrade", "head")
    ricetta = uuid.uuid4()
    await _esegui(scratch_url, RICETTA, id=ricetta)
    await _esegui(scratch_url, PASTO, **_dati(recipe_id=ricetta))
    with pytest.raises(IntegrityError):
        await _esegui(scratch_url, PASTO, **_dati(slot="dinner", recipe_id=ricetta))


@pytest.mark.parametrize(
    "caso",
    [
        "slot",
        "status",
        "piatto_vuoto",
        "avanzo_con_ricetta",
        "fuori_casa_con_avanzo",
        "bozza_con_ricetta",
        "avanzo_di_se_stesso",
    ],
)
async def test_i_vincoli_del_pasto(scratch_url, caso):
    alembic(scratch_url, "upgrade", "head")
    ricetta, origine = uuid.uuid4(), uuid.uuid4()
    await _esegui(scratch_url, RICETTA, id=ricetta)
    await _esegui(scratch_url, PASTO, **_dati(id=origine, day="2026-11-15"))
    nuovo = uuid.uuid4()
    righe = {
        "slot": _dati(id=nuovo, slot="brunch"),
        "status": _dati(id=nuovo, status="maybe"),
        "piatto_vuoto": _dati(id=nuovo, dish="   "),
        "avanzo_con_ricetta": _dati(id=nuovo, recipe_id=ricetta, leftover_of_id=origine),
        "fuori_casa_con_avanzo": _dati(id=nuovo, away=True, leftover_of_id=origine),
        "bozza_con_ricetta": _dati(id=nuovo, status="draft", recipe_id=ricetta),
        "avanzo_di_se_stesso": _dati(id=nuovo, leftover_of_id=nuovo),
    }
    with pytest.raises(IntegrityError):
        await _esegui(scratch_url, PASTO, **righe[caso])


async def test_cancellare_la_ricetta_o_il_pasto_d_origine_lascia_il_pasto(scratch_url):
    alembic(scratch_url, "upgrade", "head")
    ricetta, origine, avanzo = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    await _esegui(scratch_url, RICETTA, id=ricetta)
    await _esegui(scratch_url, PASTO, **_dati(id=origine, recipe_id=ricetta))
    await _esegui(
        scratch_url, PASTO, **_dati(id=avanzo, day="2026-11-17", leftover_of_id=origine)
    )

    await _esegui(scratch_url, "DELETE FROM recipes WHERE id = :id", id=ricetta)
    assert (
        await _scalar(scratch_url, "SELECT recipe_id FROM meals WHERE id = :id", id=origine)
        is None
    )
    assert await _scalar(scratch_url, "SELECT count(*) FROM meals") == 2

    await _esegui(scratch_url, "DELETE FROM meals WHERE id = :id", id=origine)
    assert await _scalar(scratch_url, "SELECT count(*) FROM meals") == 1
    assert (
        await _scalar(scratch_url, "SELECT leftover_of_id FROM meals WHERE id = :id", id=avanzo)
        is None
    )


async def test_la_0020_scende(scratch_url):
    alembic(scratch_url, "upgrade", "head")
    alembic(scratch_url, "downgrade", "0019")
    assert (
        await _scalar(
            scratch_url,
            "SELECT count(*) FROM information_schema.tables WHERE table_name = 'meals'",
        )
        == 0
    )
    assert (
        await _scalar(
            scratch_url,
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = 'recipes' AND column_name = 'in_book'",
        )
        == 0
    )
