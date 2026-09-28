"""La migrazione 0012 sale e scende (R10 §8.1).

Su un database suo, creato e distrutto qui: far scendere quello della suite
toglierebbe `archived_at` sotto i piedi a ogni altro test, e un fallimento a metà lo
lascerebbe lì. Alembic gira in un sottoprocesso, come nella fixture `engine` di
conftest: il suo template async chiama `asyncio.run`, che dentro un loop già in corsa
esplode.
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
SCRATCH_DB = f"{TEST_DB}_migrazione"

ARCHIVED_AT = (
    "SELECT data_type FROM information_schema.columns "
    "WHERE table_name = 'recipes' AND column_name = 'archived_at'"
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


async def _pagina(url: str, indirizzo: str, stato: str) -> None:
    engine = create_async_engine(url)
    try:
        async with engine.begin() as conn:
            await conn.execute(
                text(
                    "INSERT INTO recipe_imports (id, source, url, payload, state) "
                    "VALUES (gen_random_uuid(), 'giallozafferano', :url, '{}'::jsonb, :state)"
                ),
                {"url": indirizzo, "state": stato},
            )
    finally:
        await engine.dispose()


async def test_la_0012_sale_scende_e_risale(scratch_url):
    alembic(scratch_url, "upgrade", "0012")
    assert await _scalar(scratch_url, ARCHIVED_AT) == "timestamp with time zone"
    await _pagina(scratch_url, "https://esempio.invalid/presa", "adopted")
    with pytest.raises(IntegrityError):
        await _pagina(scratch_url, "https://esempio.invalid/inventata", "quasi")

    alembic(scratch_url, "downgrade", "0011")
    assert await _scalar(scratch_url, ARCHIVED_AT) is None
    # scendendo, la presa in carico si perde: la pagina torna «imported», e il vecchio
    # CHECK non rifiuta niente di quel che c'è
    assert (
        await _scalar(
            scratch_url,
            "SELECT state FROM recipe_imports WHERE url = 'https://esempio.invalid/presa'",
        )
        == "imported"
    )
    with pytest.raises(IntegrityError):
        await _pagina(scratch_url, "https://esempio.invalid/dopo", "adopted")

    alembic(scratch_url, "upgrade", "head")
    assert await _scalar(scratch_url, ARCHIVED_AT) == "timestamp with time zone"
