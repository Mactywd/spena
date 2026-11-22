"""Il lucchetto sul pasto (idee 52 e 42): la ricetta di un pasto si scrive con la riga del
pasto bloccata, così due scritture nello stesso istante non lasciano una ricetta orfana, e
«Annulla» non passa sopra una scrittura in corso.

Su un database suo, con i dati committati, come `test_double_tap.py`: il `FOR UPDATE` si
vede solo fra due transazioni vere. «Aspetta» è un `wait_for` di 0,3 secondi che scade su
`shield`, così l'attesa vera non si cancella e finisce dopo il `commit` dell'altra.
"""

import asyncio
import os
import uuid
import subprocess
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import exists, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.meal import Meal
from app.db.models.recipe import Recipe, RecipeSource
from app.db.models.recipe_change import RecipeChange
from app.domain.meals import MealSlot
from app.domain.rules import IngredientRole
from app.repositories.meals import get_meal, lock_meal
from app.repositories.recipes import create_recipe
from app.services.meal_recipes import (
    CREATE_ONLY_MESSAGE,
    ChangeRefusal,
    ChangeRefusalCode,
    DraftLine,
    MealRecipeDraft,
    RecipeWriteRefused,
    undo_recipe_change,
    write_meal_recipe,
)
from app.services.meals import MealRefusal, MealRefusalCode, create_meal, link_recipe

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://spena:spena@localhost:5433/spena_test"
)
SERVER, _, TEST_DB = TEST_DATABASE_URL.rpartition("/")
SCRATCH_DB = f"{TEST_DB}_lucchetto_pasto"
WAIT = 0.3


@pytest_asyncio.fixture
async def maker():
    admin = create_async_engine(f"{SERVER}/postgres", isolation_level="AUTOCOMMIT")
    engine = None
    try:
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)'))
            await conn.execute(text(f'CREATE DATABASE "{SCRATCH_DB}"'))
        url = f"{SERVER}/{SCRATCH_DB}"
        setup = create_async_engine(url)
        async with setup.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await setup.dispose()
        subprocess.run(
            ["alembic", "upgrade", "head"], check=True,
            env={**os.environ, "DATABASE_URL": url},
        )
        engine = create_async_engine(url)
        yield async_sessionmaker(engine, expire_on_commit=False)
    finally:
        if engine is not None:
            await engine.dispose()
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)'))
        await admin.dispose()


@pytest_asyncio.fixture
async def dati(maker):
    """Un pasto ufficiale senza ricetta e l'ingrediente delle ricette, committati."""
    async with maker() as setup:
        uova = Ingredient(name="uova", display_name="Uova", category=IngredientCategory.LATTICINI)
        setup.add(uova)
        await setup.flush()
        meal = await create_meal(
            setup, day=date(2026, 11, 20), slot=MealSlot.DINNER, dish="Frittata"
        )
        await setup.commit()
        return meal.id, uova.id


def _draft(uova_id, title="Frittata della coda"):
    return MealRecipeDraft(
        title=title, description=None, instructions="Sbatti. Cuoci.", servings=1,
        lines=(
            DraftLine(
                ingredient_id=uova_id, name=None, category=None,
                role=IngredientRole.PRIMARY, quantity_text="2", note=None,
            ),
        ),
        summary=title,
    )


async def _a_mano(session: AsyncSession, uova_id, title="Frittata a mano") -> Recipe:
    return await create_recipe(
        session, title=title, description=None, instructions="Cuoci.", servings=1,
        source=RecipeSource.MANUAL, source_ref=None,
        ingredients=[(uova_id, IngredientRole.PRIMARY, "3", None)],
        embedding=None, in_book=False,
    )


async def _aspetta(task: asyncio.Task) -> None:
    """Il compito è fermo: dopo `WAIT` secondi non ha finito (e non si cancella)."""
    with pytest.raises(TimeoutError):
        await asyncio.wait_for(asyncio.shield(task), WAIT)


async def _orfane(session: AsyncSession) -> int:
    """Le ricette vive fuori dal ricettario che nessun pasto ha: l'invariante dice zero."""
    owned = exists().where(Meal.recipe_id == Recipe.id)
    return (
        await session.execute(
            select(func.count()).select_from(Recipe).where(
                Recipe.in_book.is_(False), Recipe.archived_at.is_(None), ~owned
            )
        )
    ).scalar_one()


async def _scrivi_e_committa(maker, meal_id, uova_id) -> uuid.UUID:
    async with maker() as session:
        meal = await get_meal(session, meal_id)
        change = await write_meal_recipe(session, meal, _draft(uova_id))
        await session.commit()
        return change.id



async def test_lock_meal_aspetta_chi_lo_tiene(maker, dati):
    meal_id, _ = dati
    async with maker() as a, maker() as b:
        assert await lock_meal(a, meal_id) is not None
        presa = asyncio.create_task(lock_meal(b, meal_id))
        await _aspetta(presa)
        await a.commit()
        meal = await asyncio.wait_for(presa, 5)
        assert meal is not None and meal.id == meal_id
        await b.rollback()


async def test_la_coda_non_riscrive_una_ricetta_scritta_a_mano_nel_frattempo(maker, dati):
    meal_id, uova_id = dati
    async with maker() as a, maker() as b:
        meal_a = await lock_meal(a, meal_id)
        assert meal_a is not None
        mano = await _a_mano(a, uova_id)
        await link_recipe(a, meal_a, mano)

        meal_b = await get_meal(b, meal_id)
        coda = asyncio.create_task(
            write_meal_recipe(b, meal_b, _draft(uova_id), allowed_recipe_ids=frozenset({None}))
        )
        await _aspetta(coda)
        await a.commit()
        with pytest.raises(RecipeWriteRefused) as refused:
            await asyncio.wait_for(coda, 5)
        assert refused.value.message == CREATE_ONLY_MESSAGE
        await b.rollback()

    async with maker() as check:
        meal = await get_meal(check, meal_id)
        assert meal.recipe_id == mano.id
        assert await _orfane(check) == 0
        assert (await check.execute(select(func.count()).select_from(RecipeChange))).scalar() == 0


async def test_scrivere_a_mano_dopo_la_coda_rifiuta(maker, dati):
    meal_id, uova_id = dati
    async with maker() as a:
        meal_a = await get_meal(a, meal_id)  # letto prima: senza ricetta
        assert meal_a.recipe_id is None
        await _scrivi_e_committa(maker, meal_id, uova_id)

        mano = await _a_mano(a, uova_id)
        with pytest.raises(MealRefusal) as refused:
            await link_recipe(a, meal_a, mano)
        assert refused.value.code == MealRefusalCode.HAS_RECIPE
        await a.rollback()

    async with maker() as check:
        meal = await get_meal(check, meal_id)
        assert meal.recipe is not None and meal.recipe.title == "Frittata della coda"
        assert await _orfane(check) == 0


async def test_annulla_aspetta_la_scrittura(maker, dati):
    meal_id, uova_id = dati
    change_id = await _scrivi_e_committa(maker, meal_id, uova_id)
    async with maker() as a, maker() as b:
        change_b = await b.get(RecipeChange, change_id)
        meal_a = await get_meal(a, meal_id)
        await write_meal_recipe(a, meal_a, _draft(uova_id, title="Frittata riscritta"))

        annulla = asyncio.create_task(undo_recipe_change(b, change_b))
        await _aspetta(annulla)
        await a.commit()
        with pytest.raises(ChangeRefusal) as refused:
            await asyncio.wait_for(annulla, 5)
        assert refused.value.code == ChangeRefusalCode.STALE
        await b.rollback()

    async with maker() as check:
        meal = await get_meal(check, meal_id)
        assert meal.recipe.title == "Frittata riscritta"
        assert await _orfane(check) == 0


async def test_due_annulla_insieme(maker, dati):
    meal_id, uova_id = dati
    change_id = await _scrivi_e_committa(maker, meal_id, uova_id)
    sessions = [maker(), maker()]
    # tutte e due leggono la modifica ancora da annullare, prima che una delle due la annulli
    changes = [await s.get(RecipeChange, change_id) for s in sessions]

    async def tocco(session: AsyncSession, change: RecipeChange):
        try:
            await undo_recipe_change(session, change)
            await session.commit()
            return "annullata"
        except ChangeRefusal as exc:
            await session.rollback()
            return exc.code.value

    try:
        risultati = await asyncio.wait_for(
            asyncio.gather(*(tocco(s, c) for s, c in zip(sessions, changes, strict=True))), 10
        )
    finally:
        for s in sessions:
            await s.close()

    assert sorted(risultati) == sorted(["annullata", ChangeRefusalCode.ALREADY_UNDONE.value])
    async with maker() as check:
        meal = await get_meal(check, meal_id)
        assert meal.recipe_id is None
        assert await _orfane(check) == 0


async def test_salvare_a_mano_mentre_la_coda_scrive_non_lascia_orfane(maker, dati, monkeypatch):
    """La corsa vera di «Scrivi la ricetta» (Review Focus 3): la rotta ha già controllato che
    il pasto non abbia una ricetta, e mentre calcola il vettore la coda scrive e committa.
    Il collegamento, col pasto bloccato, se ne accorge: 409, e la ricetta a mano non resta."""
    from app.api import recipes as recipes_api
    from app.core.config import get_settings
    from app.core.db import get_session
    from app.core.security import hash_password
    from app.main import app

    meal_id, uova_id = dati
    original = recipes_api.embedding_for

    async def vettore_mentre_la_coda_scrive(*args, **kwargs):
        await _scrivi_e_committa(maker, meal_id, uova_id)
        return await original(*args, **kwargs)

    monkeypatch.setattr(recipes_api, "embedding_for", vettore_mentre_la_coda_scrive)
    get_settings.cache_clear()
    monkeypatch.setenv("APP_PASSWORD_HASH", hash_password("test"))
    monkeypatch.setenv("SESSION_SECRET", "segreto-di-test")

    async def sessione_vera():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = sessione_vera
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post("/api/v1/auth/login", json={"password": "test"})
            r = await c.post(
                "/api/v1/recipes",
                json={
                    "title": "Frittata a mano", "description": None, "category": None,
                    "instructions": "Cuoci.", "servings": 1, "cost": None, "source": "manual",
                    "ingredients": [
                        {"ingredient_id": str(uova_id), "role": "primary",
                         "quantity_text": "3", "note": None}
                    ],
                    "meal_id": str(meal_id),
                },
            )
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert r.status_code == 409, r.text
    assert r.json()["code"] == "has_recipe"
    async with maker() as check:
        meal = await get_meal(check, meal_id)
        assert meal.recipe.title == "Frittata della coda"
        assert (await check.execute(select(func.count()).select_from(Recipe))).scalar() == 1
        assert await _orfane(check) == 0
