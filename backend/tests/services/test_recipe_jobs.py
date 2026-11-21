"""Le ricette dei pasti ufficiali, scritte da Claude in coda (piano 6c, Task 8; decisioni 15,
16 e 17). Con il finto al posto dell'SDK e una `session_factory` sulla connessione del
test, come i test dei giri della chat. Ogni test aspetta `wait_idle`: nessun task della
coda sopravvive al test, e nel frattempo il test non usa la connessione condivisa."""

from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.api.meals import meal_out
from app.db.models.conversation import ConversationMessage
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.llm_call import LlmCall
from app.db.models.recipe import RecipeSource
from app.domain.meal_chat import FailureKind, failure_notice
from app.domain.meals import MealSlot
from app.domain.rules import today_in_pantry
from app.repositories.conversations import create_planning
from app.repositories.meals import get_meal
from app.repositories.recipes import create_recipe
from app.services.claude.prompts import recipe_system_prompt
from app.services.meals import create_meal, link_recipe
from app.services.recipe_jobs import (
    INTERRUPTED_RECIPE_NOTICE,
    NOT_WRITTEN_NOTICE,
    RecipeJobs,
    generate_meal_recipe,
    recipe_run,
    settle_orphans,
)
from app.services.utensils import utensils_prompt_block
from claude_fakes import Fail, FakeClaude, Finish, Hang, Say, UseTool

TODAY = today_in_pantry(datetime.now(UTC))
DAY1, DAY2, DAY3 = (TODAY + timedelta(days=n) for n in (1, 2, 3))


@pytest.fixture
def factory(db_session):
    return async_sessionmaker(
        bind=db_session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )


@pytest_asyncio.fixture
async def uova(db_session):
    ingredient = Ingredient(name="uova", display_name="Uova", category=IngredientCategory.LATTICINI)
    db_session.add(ingredient)
    await db_session.flush()
    return ingredient


async def tre_cene(db_session):
    """Tre cene ufficiali con la ricetta chiesta, come le lascia la messa nella settimana."""
    meals = []
    for day, dish in ((DAY1, "Frittata"), (DAY2, "Uova al tegamino"), (DAY3, "Uova sode")):
        meal = await create_meal(db_session, day=day, slot=MealSlot.DINNER, dish=dish)
        meal.recipe_requested_at = datetime.now(UTC)
        meals.append(meal)
    await db_session.commit()
    return meals


def scrivi(uova, title="Frittata"):
    return UseTool(
        "write_recipe",
        {
            "title": title,
            "servings": 1,
            "instructions": "1. Sbatti le uova.\n2. Cuoci in padella.",
            "ingredients": [
                {"ingredient_id": str(uova.id), "role": "primary", "quantity": "2"}
            ],
            "summary": "due uova in padella",
        },
    )


def ok(uova, title="Frittata"):
    return [scrivi(uova, title), Say("fatta"), Finish()]


async def dal_db(factory, meal_id):
    async with factory() as session:
        return await get_meal(session, meal_id)


async def chiamate(db_session):
    rows = await db_session.execute(select(LlmCall).where(LlmCall.call_site == "meal_recipe"))
    return list(rows.scalars().all())


async def in_coda(factory, fake, meals, *, conversation_id=None, timeout=5.0):
    jobs = RecipeJobs()
    jobs.enqueue(
        [m.id for m in meals], conversation_id, recipe_run(factory, fake, timeout_seconds=timeout)
    )
    assert jobs.live_ids() == frozenset(m.id for m in meals)
    await jobs.wait_idle()
    assert jobs.live_ids() == frozenset()
    return jobs


async def test_tre_pasti_tre_ricette(db_session, factory, uova):
    meals = await tre_cene(db_session)
    fake = FakeClaude.per_call(ok(uova, "Uno"), ok(uova, "Due"), ok(uova, "Tre"))

    await in_coda(factory, fake, meals)

    titles = []
    for meal in meals:
        fresh = await dal_db(factory, meal.id)
        assert fresh.recipe is not None
        assert fresh.recipe.source == RecipeSource.AI.value
        assert fresh.recipe.in_book is False
        assert fresh.recipe_notice is None and fresh.recipe_requested_at is None
        titles.append(fresh.recipe.title)
        out = meal_out(fresh, TODAY)
        assert out.recipe_state == "none" and out.can_ask_recipe is False
    assert titles == ["Uno", "Due", "Tre"]
    rows = await chiamate(db_session)
    assert len(rows) == 3 and all(r.ok for r in rows)
    system = recipe_system_prompt(await utensils_prompt_block(db_session))
    assert [c["system_prompt"] for c in fake.calls] == [system] * 3
    assert {c["effort"] for c in fake.calls} == {"medium"}
    assert {c["max_turns"] for c in fake.calls} == {12}
    assert fake.calls[0]["tool_names"] == [
        "read_pantry", "read_shopping_list", "read_meals", "search_ingredients", "write_recipe",
    ]


async def test_il_limite_a_meta_lascia_ogni_pasto_usabile(db_session, factory, uova):
    meals = await tre_cene(db_session)
    resets_at = datetime.now(UTC) + timedelta(hours=2)
    fake = FakeClaude.per_call(ok(uova), [Fail(FailureKind.RATE_LIMIT, resets_at=resets_at)])

    await in_coda(factory, fake, meals)

    assert len(fake.calls) == 2  # dopo il limite, nessun'altra chiamata
    notice = failure_notice(FailureKind.RATE_LIMIT, resets_at, datetime.now(UTC))
    assert "riprova" in notice and f":{resets_at.astimezone().minute:02d}" in notice
    first = await dal_db(factory, meals[0].id)
    assert first.recipe is not None and first.recipe_notice is None
    for meal in meals[1:]:
        fresh = await dal_db(factory, meal.id)
        assert fresh.recipe is None
        assert fresh.recipe_notice == notice
        assert fresh.recipe_requested_at is None
        out = meal_out(fresh, TODAY)
        assert out.recipe_state == "failed"
        assert out.recipe_notice == notice
        assert out.can_ask_recipe is True
    rows = await chiamate(db_session)
    assert sorted(r.ok for r in rows) == [False, True]


async def test_un_guasto_del_singolo_passa_al_dopo(db_session, factory, uova):
    meals = (await tre_cene(db_session))[:2]
    fake = FakeClaude.per_call([Say("Allora…"), Hang()], ok(uova))

    await in_coda(factory, fake, meals, timeout=0.2)

    first = await dal_db(factory, meals[0].id)
    assert first.recipe is None
    assert first.recipe_notice == failure_notice(FailureKind.TIMEOUT, None, datetime.now(UTC))
    assert first.recipe_requested_at is None
    second = await dal_db(factory, meals[1].id)
    assert second.recipe is not None and second.recipe_notice is None
    assert len(fake.calls) == 2


async def test_senza_write_recipe(db_session, factory, uova):
    [meal] = (await tre_cene(db_session))[:1]
    fake = FakeClaude([Say("ecco"), Finish()])

    failure = await generate_meal_recipe(
        factory, fake, meal_id=meal.id, conversation_id=None, timeout_seconds=5.0
    )

    assert failure is None
    fresh = await dal_db(factory, meal.id)
    assert fresh.recipe is None
    assert fresh.recipe_notice == NOT_WRITTEN_NOTICE
    assert fresh.recipe_requested_at is None
    assert meal_out(fresh, TODAY).recipe_state == "failed"
    [row] = await chiamate(db_session)
    assert row.ok is True


async def test_la_ricetta_scritta_registra_il_costo(db_session, factory, uova):
    [meal] = (await tre_cene(db_session))[:1]
    fake = FakeClaude(ok(uova))

    await in_coda(factory, fake, [meal])

    [row] = await chiamate(db_session)
    assert row.ok is True and row.cost_usd == 0.05
    assert row.prompt_tokens == 100 and row.completion_tokens == 20


async def test_un_giro_fallito_della_coda_registra_l_uso(db_session, factory, uova):
    [meal] = (await tre_cene(db_session))[:1]
    fake = FakeClaude(
        [Fail(FailureKind.UNAVAILABLE, input_tokens=300, output_tokens=30, cost_usd=0.02)]
    )

    await in_coda(factory, fake, [meal])

    [row] = await chiamate(db_session)
    assert row.ok is False and row.cost_usd == 0.02
    assert row.prompt_tokens == 300 and row.completion_tokens == 30


async def test_troppi_passaggi_senza_ricetta_dicono_che_non_l_ha_scritta(
    db_session, factory, uova
):
    meals = (await tre_cene(db_session))[:2]
    fake = FakeClaude.per_call(
        [Say("Vediamo"), Fail(FailureKind.MAX_TURNS, input_tokens=900, output_tokens=90, cost_usd=0.3)],
        ok(uova),
    )

    await in_coda(factory, fake, meals)

    first = await dal_db(factory, meals[0].id)
    assert first.recipe is None and first.recipe_notice == NOT_WRITTEN_NOTICE
    # non è un guasto terminale: la coda passa al pasto dopo
    assert len(fake.calls) == 2
    assert (await dal_db(factory, meals[1].id)).recipe is not None
    rows = await chiamate(db_session)
    assert sorted((r.ok, r.cost_usd) for r in rows) == [(False, 0.3), (True, 0.05)]


async def test_il_credito_finito_ferma_la_coda(db_session, factory, uova):
    meals = await tre_cene(db_session)
    fake = FakeClaude.per_call([Fail(FailureKind.CREDIT)], ok(uova), ok(uova))

    await in_coda(factory, fake, meals)

    assert len(fake.calls) == 1
    notice = failure_notice(FailureKind.CREDIT, None, datetime.now(UTC))
    for meal in meals:
        fresh = await dal_db(factory, meal.id)
        assert fresh.recipe is None and fresh.recipe_notice == notice
        assert meal_out(fresh, TODAY).can_ask_recipe is True


async def test_la_ricetta_scritta_a_mano_nel_frattempo_resta(db_session, factory, uova):
    meals = (await tre_cene(db_session))[:2]
    # prima che la coda arrivi al secondo pasto, Mattia scrive la ricetta col modulo
    mine = await create_recipe(
        db_session, title="La mia", description=None, instructions="1. A modo mio.",
        servings=1, source=RecipeSource.MANUAL, source_ref=None,
        ingredients=[(uova.id, "primary", "3", None)], embedding=None, in_book=False,
    )
    await link_recipe(db_session, meals[1], mine)
    await db_session.commit()
    fake = FakeClaude.per_call(ok(uova))  # un solo copione: una seconda chiamata fallirebbe

    await in_coda(factory, fake, meals)

    assert len(fake.calls) == 1
    second = await dal_db(factory, meals[1].id)
    assert second.recipe_id == mine.id and second.recipe.title == "La mia"
    assert second.recipe_notice is None and second.recipe_requested_at is None
    assert meal_out(second, TODAY).recipe_state == "none"


async def test_una_preparazione_orfana_diventa_un_avviso(db_session, factory, uova):
    [meal, other] = (await tre_cene(db_session))[:2]

    # `other` è ancora nella coda viva; `meal` no (il container è ripartito)
    wrote = await settle_orphans(db_session, [meal, other], frozenset({other.id}))
    await db_session.commit()

    assert wrote is True
    fresh = await dal_db(factory, meal.id)
    assert fresh.recipe_notice == INTERRUPTED_RECIPE_NOTICE
    assert fresh.recipe_requested_at is None
    out = meal_out(fresh, TODAY)
    assert out.recipe_state == "failed" and out.can_ask_recipe is True
    alive = await dal_db(factory, other.id)
    assert alive.recipe_requested_at is not None and alive.recipe_notice is None
    assert meal_out(alive, TODAY, preparing=frozenset({other.id})).recipe_state == "preparing"
    assert meal_out(alive, TODAY, preparing=frozenset({other.id})).can_ask_recipe is False
    # niente da sistemare: non scrive
    assert await settle_orphans(db_session, [fresh], frozenset()) is False


async def test_il_giro_della_ricetta_sa_cosa_si_e_detto(db_session, factory, uova):
    [meal] = (await tre_cene(db_session))[:1]
    conversation = await create_planning(db_session)
    db_session.add(
        ConversationMessage(
            conversation_id=conversation.id, role="user", status="sent",
            text="Il merluzzo non c'era, ho preso il salmone.",
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()
    fake = FakeClaude(ok(uova))

    await generate_meal_recipe(
        factory, fake, meal_id=meal.id, conversation_id=conversation.id, timeout_seconds=5.0
    )

    [call] = fake.calls
    assert "ho preso il salmone" in call["prompt"]
    assert "Piatto: Frittata." in call["prompt"]


async def test_un_pasto_che_non_vuole_una_ricetta_non_chiama_claude(db_session, factory, uova):
    meal = await create_meal(db_session, day=DAY1, slot=MealSlot.LUNCH, dish="Pizza", away=True)
    meal.recipe_requested_at = datetime.now(UTC)
    await db_session.commit()
    fake = FakeClaude([])

    assert (
        await generate_meal_recipe(
            factory, fake, meal_id=meal.id, conversation_id=None, timeout_seconds=5.0
        )
        is None
    )

    assert fake.calls == []
    fresh = await dal_db(factory, meal.id)
    assert fresh.recipe_requested_at is None and fresh.recipe_notice is None


async def test_un_eccezione_della_coda_lascia_il_pasto_usabile(db_session, factory, uova):
    meals = (await tre_cene(db_session))[:2]

    class Rotto(FakeClaude):
        async def run(self, **kwargs):
            self.calls.append(kwargs)
            if len(self.calls) == 1:
                raise RuntimeError("il client si è rotto")
            async for event in FakeClaude.run(self, **kwargs):
                yield event

    fake = Rotto(ok(uova))

    await in_coda(factory, fake, meals)

    first = await dal_db(factory, meals[0].id)
    assert first.recipe is None and first.recipe_requested_at is None
    assert first.recipe_notice == failure_notice(FailureKind.UNAVAILABLE, None, datetime.now(UTC))
    assert meal_out(first, TODAY).can_ask_recipe is True
    second = await dal_db(factory, meals[1].id)
    assert second.recipe is not None


async def test_un_run_che_cade_non_lascia_il_pasto_in_preparazione(db_session, factory):
    meals = (await tre_cene(db_session))[:2]
    seen = []

    class Cade:
        async def __call__(self, meal_id, conversation_id):
            seen.append(meal_id)
            if meal_id == meals[0].id:
                raise RuntimeError("caduta")
            return FailureKind.AUTH

        async def give_up(self, meal_ids, *, failure, like):
            await recipe_run(factory, FakeClaude([]), timeout_seconds=1.0).give_up(
                meal_ids, failure=failure, like=like
            )

    jobs = RecipeJobs()
    jobs.enqueue([m.id for m in meals], None, Cade())
    await jobs.wait_idle()

    assert seen == [meals[0].id, meals[1].id]  # la caduta del primo non ferma la coda
    assert jobs.live_ids() == frozenset()
    first = await dal_db(factory, meals[0].id)
    assert first.recipe_requested_at is None
    assert first.recipe_notice == failure_notice(FailureKind.UNAVAILABLE, None, datetime.now(UTC))
