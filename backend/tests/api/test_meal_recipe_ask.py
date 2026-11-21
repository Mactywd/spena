"""«Chiedi la ricetta a Claude» (piano 6c, Task 8): `POST /api/v1/meals/{id}/recipe/ask`, e lo
stato della ricetta nelle letture del pasto e della settimana (decisioni 15 e 16).

Il finto di Claude, la `session_factory` sulla connessione del test e una coda per test
arrivano come dipendenze. Il test non usa la connessione mentre la coda lavora: aspetta che
il finto sia fermo (`arrivato`) o che la coda sia vuota (`wait_idle`)."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.meal import Meal
from app.domain.meal_chat import FailureKind, failure_notice
from app.domain.meals import MealSlot, MealStatus
from app.domain.rules import today_in_pantry
from app.services.claude.client import get_claude_client
from app.services.meals import create_meal
from app.services.recipe_jobs import RecipeJobs, get_recipe_jobs
from claude_fakes import FakeClaude, Finish, Say, UseTool

TODAY = today_in_pantry(datetime.now(UTC))
CHIAVE_FINTA = "chiave-finta-per-i-test"


class Ferma(FakeClaude):
    """Il finto che aspetta `cancello` prima di rispondere, e dice quando è arrivato lì."""

    def __init__(self, script):
        super().__init__(script)
        self.arrivato = asyncio.Event()
        self.cancello = asyncio.Event()

    async def run(self, **kwargs):
        self.arrivato.set()
        await self.cancello.wait()
        async for event in super().run(**kwargs):
            yield event


@pytest_asyncio.fixture
async def coda(logged_client, db_session, monkeypatch):
    from app.main import app

    monkeypatch.setenv("ANTHROPIC_API_KEY", CHIAVE_FINTA)
    get_settings.cache_clear()
    jobs = RecipeJobs()

    class Coda:
        client = logged_client
        fake: FakeClaude = FakeClaude([Say("fatta"), Finish()])
        queue = jobs

    holder = Coda()
    factory = async_sessionmaker(
        bind=db_session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    app.dependency_overrides[get_claude_client] = lambda: holder.fake
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_recipe_jobs] = lambda: jobs
    yield holder
    await jobs.wait_idle()  # nessun task della coda sopravvive al test
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def uova(db_session):
    ingredient = Ingredient(name="uova", display_name="Uova", category=IngredientCategory.LATTICINI)
    db_session.add(ingredient)
    await db_session.flush()
    return ingredient


def ok(uova):
    return [
        UseTool(
            "write_recipe",
            {
                "title": "Frittata",
                "servings": 1,
                "instructions": "1. Sbatti le uova.\n2. Cuoci in padella.",
                "ingredients": [
                    {"ingredient_id": str(uova.id), "role": "primary", "quantity": "2"}
                ],
                "summary": "due uova in padella",
            },
        ),
        Say("fatta"),
        Finish(),
    ]


async def cena(db_session, **kwargs):
    meal = await create_meal(
        db_session, day=TODAY, slot=MealSlot.DINNER, dish="Frittata", **kwargs
    )
    await db_session.commit()
    return meal


async def dal_db(dal_database, meal_id):
    return await dal_database(Meal, meal_id)


def ask(meal):
    return f"/api/v1/meals/{meal.id}/recipe/ask"


async def test_chiedere_la_ricetta(coda, db_session, uova, dal_database):
    meal = await cena(db_session)
    coda.fake = FakeClaude(ok(uova))

    response = await coda.client.post(ask(meal))
    assert response.status_code == 202
    body = response.json()
    assert body["recipe_state"] == "preparing"
    assert body["can_ask_recipe"] is False
    assert body["recipe_notice"] is None
    await coda.queue.wait_idle()

    one = (await coda.client.get(f"/api/v1/meals/{meal.id}")).json()
    assert one["recipe"]["title"] == "Frittata"
    assert one["recipe_state"] == "none" and one["can_ask_recipe"] is False
    fresh = await dal_db(dal_database, meal.id)
    assert fresh.recipe_requested_at is None and fresh.recipe_notice is None


async def test_senza_chiave_503_e_niente_scritto(coda, db_session, monkeypatch, dal_database):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    meal = await cena(db_session)

    response = await coda.client.post(ask(meal))

    assert response.status_code == 503
    assert response.json() == {
        "code": "claude_not_configured",
        "detail": failure_notice(FailureKind.NOT_CONFIGURED, None, datetime.now(UTC)),
    }
    assert coda.fake.calls == []
    assert coda.queue.live_ids() == frozenset()
    fresh = await dal_db(dal_database, meal.id)
    assert fresh.recipe_requested_at is None and fresh.recipe_notice is None


async def test_due_volte_e_409(coda, db_session, uova):
    meal = await cena(db_session)
    coda.fake = Ferma(ok(uova))

    assert (await coda.client.post(ask(meal))).status_code == 202
    await coda.fake.arrivato.wait()
    again = await coda.client.post(ask(meal))
    coda.fake.cancello.set()
    await coda.queue.wait_idle()

    assert again.status_code == 409
    assert again.json() == {
        "code": "recipe_preparing", "detail": "La ricetta è già in preparazione.",
    }
    assert len(coda.fake.calls) == 1


async def test_chi_non_puo_avere_una_ricetta(coda, db_session):
    draft = await create_meal(
        db_session, day=TODAY + timedelta(days=1), slot=MealSlot.DINNER, dish="Zuppa",
        status=MealStatus.DRAFT,
    )
    away = await create_meal(
        db_session, day=TODAY + timedelta(days=2), slot=MealSlot.LUNCH, dish="Pizza", away=True,
    )
    await db_session.commit()
    # gli url prima: il rifiuto fa rollback sulla sessione del test, e scade i due pasti
    draft_url, away_url = ask(draft), ask(away)

    response = await coda.client.post(draft_url)
    assert response.status_code == 409
    assert response.json()["code"] == "no_recipe_here"
    assert response.json()["detail"] == "È una bozza: la ricetta arriva quando diventa ufficiale."

    response = await coda.client.post(away_url)
    assert response.status_code == 409
    assert response.json()["detail"] == "Un pasto fuori casa non ha una ricetta."

    week = (await coda.client.get("/api/v1/meals/week", params={"of": str(TODAY)})).json()
    flags = {m["dish"]: m["can_ask_recipe"] for m in week["meals"]}
    assert flags.get("Zuppa", False) is False and flags.get("Pizza", False) is False
    assert coda.fake.calls == []


async def test_la_settimana_dice_se_qualcosa_e_in_preparazione(coda, db_session, uova):
    meal = await cena(db_session)
    coda.fake = Ferma(ok(uova))

    before = (await coda.client.get("/api/v1/meals/week", params={"of": str(TODAY)})).json()
    assert before["preparing"] is False
    assert [m["can_ask_recipe"] for m in before["meals"]] == [True]

    assert (await coda.client.post(ask(meal))).status_code == 202
    await coda.fake.arrivato.wait()
    during = (await coda.client.get("/api/v1/meals/week", params={"of": str(TODAY)})).json()
    one = (await coda.client.get(f"/api/v1/meals/{meal.id}")).json()
    coda.fake.cancello.set()
    await coda.queue.wait_idle()
    after = (await coda.client.get("/api/v1/meals/week", params={"of": str(TODAY)})).json()

    assert during["preparing"] is True
    assert [m["recipe_state"] for m in during["meals"]] == ["preparing"]
    assert one["recipe_state"] == "preparing"
    assert after["preparing"] is False
    [done] = after["meals"]
    assert done["recipe_state"] == "none" and done["recipe"]["title"] == "Frittata"


async def test_una_preparazione_orfana_si_legge_come_avviso(coda, db_session, dal_database):
    meal = await cena(db_session)
    meal.recipe_requested_at = datetime.now(UTC)  # chiesta, ma nessuna coda l'ha (riavvio)
    await db_session.commit()

    week = (await coda.client.get("/api/v1/meals/week", params={"of": str(TODAY)})).json()

    assert week["preparing"] is False
    [out] = week["meals"]
    assert out["recipe_state"] == "failed"
    assert out["recipe_notice"] == (
        "La ricetta non è arrivata: chiedila di nuovo a Claude o scrivila a mano."
    )
    assert out["can_ask_recipe"] is True
    fresh = await dal_db(dal_database, meal.id)
    assert fresh.recipe_requested_at is None
    assert fresh.recipe_notice == out["recipe_notice"]
