"""Il lucchetto sul pasto (idee 52 e 42): la ricetta di un pasto si scrive con la riga del
pasto bloccata, così due scritture nello stesso istante non lasciano una ricetta orfana, e
«Annulla» non passa sopra una scrittura in corso.

Su un database suo, con i dati committati, come `test_double_tap.py`: il `FOR UPDATE` si
vede solo fra due transazioni vere. «Aspetta» è un `wait_for` di 0,3 secondi che scade su
`shield`, così l'attesa vera non si cancella e finisce dopo il `commit` dell'altra.
"""

import asyncio
from contextlib import asynccontextmanager
import dataclasses
import os
import uuid
import subprocess
from datetime import date

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import exists, func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.meal import Meal
from app.db.models.recipe import EMBEDDING_DIM, Recipe, RecipeSource
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
from app.services.meals import (
    MealRefusal,
    MealRefusalCode,
    create_meal,
    delete_meal,
    link_recipe,
)

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


async def test_un_errore_inatteso_della_scrittura_libera_il_pasto(maker, dati, monkeypatch):
    """Un errore che non è un rifiuto (qui un guasto finto dentro l'imbuto) risale dallo
    strumento senza lasciare la riga del pasto bloccata per il resto del giro di Claude."""
    from app.services import meal_recipes
    from app.services.claude.tools import TurnContext, write_recipe_tool

    meal_id, uova_id = dati

    async def guasto(*args, **kwargs):
        raise RuntimeError("guasto inatteso")

    async def nessuna_modifica(change):
        return None

    monkeypatch.setattr(meal_recipes, "resolve_lines", guasto)
    async with maker() as turno, maker() as altra:
        ctx = TurnContext(
            session=turno, lock=asyncio.Lock(), today=date(2026, 11, 19), meal_id=meal_id,
            conversation_id=None, turn_message_id=None, on_change=nessuna_modifica,
            create_only=True,
        )
        write = write_recipe_tool(ctx)
        with pytest.raises(RuntimeError):
            await write.handler({
                "title": "Frittata", "servings": 1, "instructions": "1. Cuoci.",
                "summary": "ok",
                "ingredients": [{"ingredient_id": str(uova_id), "role": "primary"}],
            })
        presa = asyncio.create_task(lock_meal(altra, meal_id))
        try:
            done, _ = await asyncio.wait({presa}, timeout=WAIT)
            assert done, "il pasto è ancora bloccato dal giro"
        finally:
            await turno.rollback()  # nel rosso libera la riga, così il compito finisce
            await asyncio.wait_for(presa, 5)
            await altra.rollback()


async def test_eliminare_il_pasto_aspetta_chi_scrive_senza_ciclo(maker, dati):
    """F-R6: l'eliminazione prende il pasto per primo, come la scrittura e «Annulla». Chi
    scrive la ricetta tiene il pasto e poi tocca la ricetta; l'eliminazione aspetta il pasto
    invece di prendere prima la ricetta (il ciclo che Postgres chiuderebbe con un deadlock)."""
    meal_id, uova_id = dati
    await _scrivi_e_committa(maker, meal_id, uova_id)
    async with maker() as x, maker() as y:
        meal_y = await get_meal(y, meal_id)
        meal_x = await lock_meal(x, meal_id)

        async def elimina():
            await delete_meal(y, meal_y)
            await y.commit()

        eliminazione = asyncio.create_task(elimina())
        await _aspetta(eliminazione)
        await write_meal_recipe(x, meal_x, _draft(uova_id, title="Frittata riscritta"))
        await x.commit()
        await asyncio.wait_for(eliminazione, 5)

    async with maker() as check:
        assert await get_meal(check, meal_id) is None
        recipe = (await check.execute(select(Recipe))).scalar_one()
        assert recipe.title == "Frittata riscritta" and recipe.archived_at is not None
        assert await _orfane(check) == 0


async def test_annulla_prende_il_lucchetto_prima_di_guardare_se_claude_risponde(
    maker, dati, monkeypatch
):
    """F-R7: «Annulla» aspetta il pasto prima di chiedere al registro se c'è un giro. Un giro
    che parte mentre aspetta si vede: 409 `claude_busy`, e la ricetta resta com'è."""
    from app.core.config import get_settings
    from app.core.db import get_session
    from app.core.security import hash_password
    from app.main import app
    from app.repositories.conversations import get_or_create_dish_conversation
    from app.services.chat_turns import TurnRegistry, get_turn_registry

    meal_id, uova_id = dati
    change_id = await _scrivi_e_committa(maker, meal_id, uova_id)
    async with maker() as setup:
        conversation = await get_or_create_dish_conversation(setup, meal_id)
        conversation_id = conversation.id
        await setup.commit()

    registry = TurnRegistry()
    get_settings.cache_clear()
    monkeypatch.setenv("APP_PASSWORD_HASH", hash_password("test"))
    monkeypatch.setenv("SESSION_SECRET", "segreto-di-test")

    async def sessione_vera():
        async with maker() as session:
            yield session

    app.dependency_overrides[get_session] = sessione_vera
    app.dependency_overrides[get_turn_registry] = lambda: registry
    libera = asyncio.Event()

    async def giro_vivo(emit):
        await libera.wait()

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
            await c.post("/api/v1/auth/login", json={"password": "test"})
            async with maker() as x:
                assert await lock_meal(x, meal_id) is not None
                annulla = asyncio.create_task(
                    c.post(f"/api/v1/meals/{meal_id}/chat/changes/{change_id}/undo")
                )
                await _aspetta(annulla)
                registry.start(conversation_id, giro_vivo)
                await x.commit()
                r = await asyncio.wait_for(annulla, 5)
    finally:
        libera.set()
        await registry.wait(conversation_id)
        app.dependency_overrides.clear()
        get_settings.cache_clear()

    assert r.status_code == 409, r.text
    assert r.json()["code"] == "claude_busy"
    async with maker() as check:
        meal = await get_meal(check, meal_id)
        assert meal.recipe is not None and meal.recipe.title == "Frittata della coda"


@asynccontextmanager
async def _client(maker, monkeypatch):
    """Il client HTTP dell'app, autenticato, su sessioni vere del database di questi test."""
    from app.core.config import get_settings
    from app.core.db import get_session
    from app.core.security import hash_password
    from app.main import app

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
            yield c
    finally:
        app.dependency_overrides.clear()
        get_settings.cache_clear()


async def _ricetta_del_pasto(maker, meal_id, uova_id, *, in_book: bool) -> uuid.UUID:
    """La coda scrive la ricetta del pasto; `in_book` la mette nel ricettario («Salva»)."""
    await _scrivi_e_committa(maker, meal_id, uova_id)
    async with maker() as setup:
        meal = await get_meal(setup, meal_id)
        meal.recipe.in_book = in_book
        await setup.commit()
        return meal.recipe_id


async def _patch_mentre_si_elimina_il_pasto(maker, monkeypatch, meal_id, recipe_id, body):
    """A tiene il pasto; il `PATCH` parte e aspetta il lucchetto; A elimina il pasto e
    committa; il `PATCH` finisce sul pasto che non c'è più."""
    async with _client(maker, monkeypatch) as c, maker() as a:
        meal_a = await lock_meal(a, meal_id)
        assert meal_a is not None
        patch = asyncio.create_task(c.patch(f"/api/v1/recipes/{recipe_id}", json=body))
        await _aspetta(patch)
        await delete_meal(a, meal_a)
        await a.commit()
        return await asyncio.wait_for(patch, 5)


async def test_elimina_dal_ricettario_mentre_si_elimina_il_pasto_non_lascia_orfane(
    maker, dati, monkeypatch
):
    """Review Focus 1: «Elimina» su una ricetta del pasto nel ricettario la toglierebbe dal
    ricettario lasciandola al pasto; ma il pasto se ne va mentre il `PATCH` aspetta. Col
    pasto riletto dopo il lucchetto, la ricetta si elimina davvero e non resta orfana."""
    meal_id, uova_id = dati
    recipe_id = await _ricetta_del_pasto(maker, meal_id, uova_id, in_book=True)

    r = await _patch_mentre_si_elimina_il_pasto(
        maker, monkeypatch, meal_id, recipe_id, {"archived": True}
    )

    assert r.status_code == 200, r.text
    assert r.json()["archived_at"] is not None
    async with maker() as check:
        assert await get_meal(check, meal_id) is None
        recipe = await check.get(Recipe, recipe_id)
        assert recipe.archived_at is not None
        assert await _orfane(check) == 0


async def test_togli_dal_ricettario_mentre_si_elimina_il_pasto_non_lascia_orfane(
    maker, dati, monkeypatch
):
    """«Togli dal ricettario» mentre il pasto se ne va: il pasto non c'è più, e una ricetta
    viva fuori dal ricettario senza pasto è proprio l'orfana. 409, e resta nel ricettario."""
    from app.api.recipes import NOT_A_MEAL_RECIPE

    meal_id, uova_id = dati
    recipe_id = await _ricetta_del_pasto(maker, meal_id, uova_id, in_book=True)

    r = await _patch_mentre_si_elimina_il_pasto(
        maker, monkeypatch, meal_id, recipe_id, {"in_book": False}
    )

    assert r.status_code == 409, r.text
    assert r.json()["detail"] == NOT_A_MEAL_RECIPE
    async with maker() as check:
        recipe = await check.get(Recipe, recipe_id)
        assert recipe.in_book is True and recipe.archived_at is None
        assert await _orfane(check) == 0


async def test_salva_nel_ricettario_mentre_si_elimina_il_pasto(maker, dati, monkeypatch):
    """Review Focus 2: l'eliminazione del pasto, col pasto bloccato, elimina la sua ricetta
    fuori dal ricettario. «Salva nel ricettario» che arriva in quel momento aspetta, rilegge
    la ricetta eliminata e risponde 409: mai una ricetta eliminata nel ricettario con un 200."""
    from app.api.recipes import RECIPE_ARCHIVED

    meal_id, uova_id = dati
    recipe_id = await _ricetta_del_pasto(maker, meal_id, uova_id, in_book=False)

    async with _client(maker, monkeypatch) as c, maker() as a:
        meal_a = await lock_meal(a, meal_id)
        assert meal_a is not None
        await delete_meal(a, meal_a)
        patch = asyncio.create_task(
            c.patch(f"/api/v1/recipes/{recipe_id}", json={"in_book": True})
        )
        await _aspetta(patch)
        await a.commit()
        r = await asyncio.wait_for(patch, 5)

    assert r.status_code == 409, r.text
    assert r.json()["detail"] == RECIPE_ARCHIVED
    async with maker() as check:
        assert await get_meal(check, meal_id) is None
        eliminate_nel_ricettario = (
            await check.execute(
                select(func.count()).select_from(Recipe).where(
                    Recipe.in_book.is_(True), Recipe.archived_at.is_not(None)
                )
            )
        ).scalar_one()
        assert eliminate_nel_ricettario == 0
        assert await _orfane(check) == 0


def _corpo_put(dettaglio, titolo, **extra):
    """Il modulo com'era quando si è aperto (dal dettaglio), con un titolo nuovo."""
    return {
        "title": titolo, "description": dettaglio["description"],
        "category": dettaglio["category"], "instructions": dettaglio["instructions"],
        "servings": dettaglio["servings"], "cost": dettaglio["cost"],
        "ingredients": [
            {"ingredient_id": i["ingredient_id"], "role": i["role"],
             "quantity_text": i["quantity_text"], "note": i["note"]}
            for i in dettaglio["ingredients"]
        ],
        **extra,
    }


async def test_il_put_aspetta_la_chat_e_poi_dice_che_e_cambiata(maker, dati, monkeypatch):
    """Review Focus 3, la chat prima: A scrive la ricetta col pasto bloccato e non ha ancora
    committato; il `PUT` del modulo aperto prima aspetta il pasto, rilegge la ricetta dopo il
    `commit` di A e risponde 409 `recipe_changed`. La scrittura della chat resta."""
    meal_id, uova_id = dati
    recipe_id = await _ricetta_del_pasto(maker, meal_id, uova_id, in_book=False)

    async with _client(maker, monkeypatch) as c, maker() as a:
        aperta = (await c.get(f"/api/v1/recipes/{recipe_id}")).json()
        meal_a = await get_meal(a, meal_id)
        await write_meal_recipe(a, meal_a, _draft(uova_id, title="Frittata della chat"))
        put = asyncio.create_task(
            c.put(
                f"/api/v1/recipes/{recipe_id}",
                json=_corpo_put(aperta, "Frittata mia", expected_version=aperta["version"]),
            )
        )
        await _aspetta(put)
        await a.commit()
        r = await asyncio.wait_for(put, 5)

    assert r.status_code == 409, r.text
    assert r.json() == {
        "code": "recipe_changed",
        "detail": "La ricetta è cambiata mentre la correggevi.",
    }
    async with maker() as check:
        meal = await get_meal(check, meal_id)
        assert meal.recipe_id == recipe_id
        assert meal.recipe.title == "Frittata della chat"
        assert await _orfane(check) == 0


async def test_la_chat_aspetta_il_put_e_poi_si_ferma(maker, dati, monkeypatch):
    """Review Focus 3, il `PUT` prima: tiene il pasto (fermo appena prima del `commit`), la
    chat con l'istantanea di prima aspetta, e dopo il `commit` si ferma con
    `STALE_WRITE_MESSAGE`. La scrittura del modulo resta."""
    from app.api import recipes as recipes_api
    from app.services.meal_recipes import STALE_WRITE_MESSAGE, meal_snapshot

    meal_id, uova_id = dati
    recipe_id = await _ricetta_del_pasto(maker, meal_id, uova_id, in_book=False)
    original = recipes_api.adopt_import_page
    dentro, via = asyncio.Event(), asyncio.Event()

    async def adozione_ferma(*args, **kwargs):
        dentro.set()
        await via.wait()
        return await original(*args, **kwargs)

    monkeypatch.setattr(recipes_api, "adopt_import_page", adozione_ferma)
    try:
        async with _client(maker, monkeypatch) as c, maker() as b:
            aperta = (await c.get(f"/api/v1/recipes/{recipe_id}")).json()
            meal_b = await get_meal(b, meal_id)
            visto = await meal_snapshot(b, meal_b)  # quel che Claude ha letto
            put = asyncio.create_task(
                c.put(
                    f"/api/v1/recipes/{recipe_id}",
                    json=_corpo_put(aperta, "Frittata mia", expected_version=aperta["version"]),
                )
            )
            await asyncio.wait_for(dentro.wait(), 5)
            chat = asyncio.create_task(
                write_meal_recipe(
                    b, meal_b, _draft(uova_id, title="Frittata della chat"), expected=visto
                )
            )
            await _aspetta(chat)
            via.set()
            r = await asyncio.wait_for(put, 5)
            with pytest.raises(RecipeWriteRefused) as refused:
                await asyncio.wait_for(chat, 5)
            await b.rollback()
    finally:
        via.set()

    assert r.status_code == 200, r.text
    assert refused.value.message == STALE_WRITE_MESSAGE
    async with maker() as check:
        meal = await get_meal(check, meal_id)
        assert meal.recipe.title == "Frittata mia"
        assert await _orfane(check) == 0


# Il vettore fuori dal lucchetto (Task 5 del quarto giro): `embedding_for` va in rete, e
# col pasto bloccato fermerebbe per tutto quel tempo la coda, la chat e «Annulla».
VETTORE = [0.5] * EMBEDDING_DIM
VETTORE_DI_PRIMA = [0.25] * EMBEDDING_DIM


def _finto_vettore(maker, meal_id, chiamate: list, vettore=VETTORE):
    """Un `embedding_for` finto che annota il titolo e se il pasto, in quel momento, è libero:
    da un'altra sessione prova a prenderlo con `NOWAIT`, e lo rilascia subito."""

    async def finto(title, description, **kwargs):
        async with maker() as altra:
            try:
                await altra.execute(
                    text("SELECT id FROM meals WHERE id = :id FOR UPDATE NOWAIT"),
                    {"id": meal_id},
                )
                libero = True
            except DBAPIError:
                libero = False
            await altra.rollback()
        chiamate.append((title, libero))
        return vettore

    return finto


def _vettore(recipe: Recipe) -> list[float]:
    return [float(x) for x in recipe.embedding]


async def test_scrivere_la_ricetta_calcola_il_vettore_col_pasto_libero(
    maker, dati, monkeypatch
):
    from app.services import meal_recipes

    meal_id, uova_id = dati
    chiamate: list = []
    monkeypatch.setattr(
        meal_recipes, "embedding_for", _finto_vettore(maker, meal_id, chiamate)
    )
    await _scrivi_e_committa(maker, meal_id, uova_id)

    assert chiamate == [("Frittata della coda", True)]
    async with maker() as check:
        meal = await get_meal(check, meal_id)
        assert _vettore(meal.recipe) == VETTORE


async def test_annulla_calcola_il_vettore_col_pasto_libero(maker, dati, monkeypatch):
    from app.services import meal_recipes

    meal_id, uova_id = dati
    chiamate: list = []
    monkeypatch.setattr(
        meal_recipes, "embedding_for", _finto_vettore(maker, meal_id, chiamate)
    )
    await _scrivi_e_committa(maker, meal_id, uova_id)
    async with maker() as session:
        meal = await get_meal(session, meal_id)
        change = await write_meal_recipe(
            session, meal, _draft(uova_id, title="Frittata riscritta")
        )
        await session.commit()
        change_id = change.id
    chiamate.clear()

    async with maker() as session:
        change = await session.get(RecipeChange, change_id)
        await undo_recipe_change(session, change)
        await session.commit()

    assert chiamate == [("Frittata della coda", True)]
    async with maker() as check:
        meal = await get_meal(check, meal_id)
        assert meal.recipe.title == "Frittata della coda"
        assert _vettore(meal.recipe) == VETTORE


async def test_annulla_senza_titolo_cambiato_non_calcola_il_vettore(
    maker, dati, monkeypatch
):
    from app.services import meal_recipes

    meal_id, uova_id = dati
    chiamate: list = []
    monkeypatch.setattr(
        meal_recipes, "embedding_for", _finto_vettore(maker, meal_id, chiamate)
    )
    await _scrivi_e_committa(maker, meal_id, uova_id)
    async with maker() as session:
        meal = await get_meal(session, meal_id)
        change = await write_meal_recipe(
            session, meal, dataclasses.replace(_draft(uova_id), instructions="Sbatti piano.")
        )
        await session.commit()
        change_id = change.id
    chiamate.clear()

    async with maker() as session:
        change = await session.get(RecipeChange, change_id)
        await undo_recipe_change(session, change)
        await session.commit()

    assert chiamate == []
    async with maker() as check:
        meal = await get_meal(check, meal_id)
        assert meal.recipe.instructions == "Sbatti. Cuoci."


async def test_la_ricetta_cambiata_fra_la_lettura_e_il_lucchetto_ha_il_vettore_giusto(
    maker, dati, monkeypatch
):
    """La corsa rara (decisione 7): la lettura senza lucchetto trova già titolo e
    descrizione della bozza, quindi il vettore non serve; prima del lucchetto un'altra
    sessione cambia il titolo. La decisione rifatta sotto il lucchetto lo vede."""
    from app.services import meal_recipes

    meal_id, uova_id = dati
    chiamate_prima: list = []
    monkeypatch.setattr(
        meal_recipes, "embedding_for",
        _finto_vettore(maker, meal_id, chiamate_prima, VETTORE_DI_PRIMA),
    )
    await _scrivi_e_committa(maker, meal_id, uova_id)  # titolo e descrizione della bozza

    chiamate: list = []
    monkeypatch.setattr(
        meal_recipes, "embedding_for", _finto_vettore(maker, meal_id, chiamate)
    )
    vero = meal_recipes.lock_meal

    async def lucchetto_dopo_un_altro_titolo(session, wanted_id):
        async with maker() as altra:
            meal = await get_meal(altra, wanted_id)
            meal.recipe.title = "Frittata cambiata intanto"
            await altra.commit()
        return await vero(session, wanted_id)

    monkeypatch.setattr(meal_recipes, "lock_meal", lucchetto_dopo_un_altro_titolo)
    async with maker() as session:
        meal = await get_meal(session, meal_id)
        await write_meal_recipe(session, meal, _draft(uova_id))
        await session.commit()

    assert chiamate == [("Frittata della coda", False)]
    async with maker() as check:
        meal = await get_meal(check, meal_id)
        assert meal.recipe.title == "Frittata della coda"
        assert _vettore(meal.recipe) == VETTORE
