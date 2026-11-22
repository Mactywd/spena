"""Gli strumenti della pianificazione (piano 6c, Task 6): propose_meals, propose_changes,
write_recipe con `create_only`, e il finto con un copione per chiamata. Oggi è giovedì
12 novembre 2026 (il 13 è venerdì, il 14 sabato)."""

import asyncio
import uuid
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.db.models.change_card import ChangeCard
from app.db.models.conversation import Conversation, ConversationMessage
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.planning import MealProposal
from app.domain.meals import MealSlot, MealStatus
from app.repositories.conversations import create_planning
from app.repositories.meals import get_meal
from app.services.claude.client import TurnFinished
from app.services.claude.tools import TurnContext, dish_tools, planning_tools, recipe_tools
from app.services.meal_recipes import DraftLine, MealRecipeDraft, write_meal_recipe
from app.services.meals import create_meal
from app.domain.rules import IngredientRole
from tests.claude_fakes import FakeClaude, Finish, Say, UseTool

TODAY = date(2026, 11, 12)
FRI, SAT = date(2026, 11, 13), date(2026, 11, 14)


@pytest_asyncio.fixture
async def voci(db_session):
    rows = {
        "ricotta": Ingredient(
            name="ricotta", display_name="Ricotta", category=IngredientCategory.LATTICINI
        ),
        "limoni": Ingredient(
            name="limoni", display_name="Limoni", category=IngredientCategory.FRUTTA
        ),
        "detersivo": Ingredient(
            name="detersivo", display_name="Detersivo", category=IngredientCategory.CASA
        ),
    }
    db_session.add_all(rows.values())
    await db_session.flush()
    items = {
        "ricotta": PantryItem(ingredient_id=rows["ricotta"].id, status="available"),
        "detersivo": PantryItem(ingredient_id=rows["detersivo"].id, status="available"),
    }
    db_session.add_all(items.values())
    await db_session.flush()
    return rows, items


@pytest_asyncio.fixture
async def chat(db_session):
    conversation = await create_planning(db_session)
    message = ConversationMessage(
        conversation_id=conversation.id, role="user", text="Pianifichiamo",
        created_at=datetime(2026, 11, 12, 17, 40, tzinfo=UTC),
    )
    db_session.add(message)
    await db_session.flush()
    return conversation, message


@pytest.fixture
def seen():
    return {"proposals": [], "cards": [], "changes": []}


def make_ctx(db_session, chat, seen, meal_id=None, **extra):
    conversation, message = chat

    async def on_proposal(proposal):
        seen["proposals"].append(proposal)

    async def on_card(card):
        seen["cards"].append(card)

    async def on_change(change):
        seen["changes"].append(change)

    return TurnContext(
        session=db_session, lock=asyncio.Lock(), today=TODAY, meal_id=meal_id,
        conversation_id=conversation.id, turn_message_id=message.id, on_change=on_change,
        on_proposal=on_proposal, on_card=on_card, **extra,
    )


def named(tools):
    return {t.name: t for t in tools}


def text_of(result):
    return result["content"][0]["text"]


def test_planning_tools_sono_sei(db_session, chat, seen):
    names = [t.name for t in planning_tools(make_ctx(db_session, chat, seen))]
    assert names == [
        "read_pantry", "read_shopping_list", "read_meals", "search_ingredients",
        "propose_meals", "propose_changes",
    ]
    assert "write_recipe" not in names


async def test_propose_meals_salva_e_avvisa(db_session, chat, seen):
    tool = named(planning_tools(make_ctx(db_session, chat, seen)))["propose_meals"]
    result = await tool.handler({
        "kind": "official",
        "meals": [{"day": "2026-11-13", "slot": "dinner", "dish": "Frittata", "sides": "pane"}],
    })
    assert "is_error" not in result
    assert text_of(result).startswith("Proposta mandata")
    saved = (await db_session.execute(select(MealProposal))).scalars().all()
    assert len(saved) == 1 and saved[0].rows[0]["dish"] == "Frittata"
    assert seen["proposals"] == saved


async def test_propose_meals_nel_passato_lo_dice_a_claude(db_session, chat, seen):
    tool = named(planning_tools(make_ctx(db_session, chat, seen)))["propose_meals"]
    result = await tool.handler({
        "kind": "draft",
        "meals": [{"day": "2026-11-10", "slot": "lunch", "dish": "Pasta"}],
    })
    assert result["is_error"] is True
    assert "Non si pianifica nel passato" in text_of(result)
    assert (await db_session.execute(select(func.count(MealProposal.id)))).scalar_one() == 0
    assert seen["proposals"] == []


async def test_propose_meals_rifiuta_un_piatto_di_soli_spazi(db_session, chat, seen):
    tool = named(planning_tools(make_ctx(db_session, chat, seen)))["propose_meals"]
    result = await tool.handler({
        "kind": "official",
        "meals": [{"day": "2026-11-13", "slot": "lunch", "dish": "   "}],
    })
    assert result["is_error"] is True
    assert (await db_session.execute(select(func.count(MealProposal.id)))).scalar_one() == 0


async def test_propose_changes_per_i_posti(db_session, chat, seen, voci):
    _, items = voci
    await create_meal(db_session, day=FRI, slot=MealSlot.DINNER, dish="Torta di ricotta")
    await create_meal(db_session, day=SAT, slot=MealSlot.LUNCH, dish="Crostata")
    tool = named(planning_tools(make_ctx(db_session, chat, seen)))["propose_changes"]
    result = await tool.handler({
        "meals": [
            {"day": "2026-11-13", "slot": "dinner"},
            {"day": "2026-11-14", "slot": "lunch"},
        ],
        "pantry": [{"pantry_item_id": str(items["ricotta"].id), "to": "finished"}],
    })
    assert "is_error" not in result, text_of(result)
    assert text_of(result) == "Scheda mandata: Mattia la rivede e la applica."
    card = (await db_session.execute(select(ChangeCard))).scalar_one()
    assert seen["cards"] == [card]
    assert len(card.meal_ids) == 2
    assert any(r.pantry_item_id == items["ricotta"].id for r in card.rows)


async def test_propose_changes_su_un_posto_vuoto(db_session, chat, seen, voci):
    _, items = voci
    tool = named(planning_tools(make_ctx(db_session, chat, seen)))["propose_changes"]
    result = await tool.handler({
        "meals": [{"day": "2026-11-13", "slot": "dinner"}],
        "pantry": [{"pantry_item_id": str(items["ricotta"].id), "to": "finished"}],
    })
    assert result["is_error"] is True
    assert text_of(result) == (
        "Nessun pasto in venerdì 13 novembre · cena: "
        "la scheda è per pasti già nella settimana."
    )
    assert seen["cards"] == []


async def test_propose_changes_dal_piatto_senza_posti(db_session, chat, seen, voci):
    rows, items = voci
    meal = await create_meal(db_session, day=FRI, slot=MealSlot.DINNER, dish="Torta di ricotta")
    ctx = make_ctx(db_session, chat, seen, meal_id=meal.id)
    tool = named(dish_tools(ctx))["propose_changes"]
    result = await tool.handler({
        "pantry": [{"pantry_item_id": str(items["ricotta"].id), "to": "finished"}],
        "shopping": [{"name": "Limoni"}],
    })
    assert "is_error" not in result, text_of(result)
    card = (await db_session.execute(select(ChangeCard))).scalar_one()
    assert card.meal_ids == [str(meal.id)]
    assert {r.label for r in card.rows} >= {"Limoni"}


async def test_propose_changes_senza_posti_in_pianificazione_chiede_i_posti(
    db_session, chat, seen, voci
):
    _, items = voci
    tool = named(planning_tools(make_ctx(db_session, chat, seen)))["propose_changes"]
    result = await tool.handler({
        "pantry": [{"pantry_item_id": str(items["ricotta"].id), "to": "finished"}]
    })
    assert result["is_error"] is True and "meals" in text_of(result)


async def test_propose_changes_una_bozza_senza_dispensa(db_session, chat, seen, voci):
    _, items = voci
    await create_meal(
        db_session, day=FRI, slot=MealSlot.DINNER, dish="Orata", status=MealStatus.DRAFT
    )
    tool = named(planning_tools(make_ctx(db_session, chat, seen)))["propose_changes"]
    result = await tool.handler({
        "meals": [{"day": "2026-11-13", "slot": "dinner"}],
        "pantry": [{"pantry_item_id": str(items["ricotta"].id), "to": "finished"}],
    })
    assert result["is_error"] is True
    assert text_of(result) == (
        "Per una bozza la scheda ha solo le cose da comprare: la dispensa si aggiorna "
        "quando i pasti diventano ufficiali."
    )
    assert (await db_session.execute(select(func.count(ChangeCard.id)))).scalar_one() == 0


async def test_propose_changes_id_sconosciuti_e_non_alimentari(db_session, chat, seen, voci):
    rows, items = voci
    await create_meal(db_session, day=FRI, slot=MealSlot.DINNER, dish="Orata")
    tool = named(planning_tools(make_ctx(db_session, chat, seen)))["propose_changes"]
    place = [{"day": "2026-11-13", "slot": "dinner"}]
    ghost = uuid.uuid4()

    unknown = await tool.handler({"meals": place, "shopping": [{"ingredient_id": str(ghost)}]})
    assert text_of(unknown) == f"{ghost} non è nell'anagrafica: cercalo con search_ingredients."
    by_name = await tool.handler({"meals": place, "shopping": [{"name": "Mirto"}]})
    assert text_of(by_name) == "Mirto non è nell'anagrafica: cercalo con search_ingredients."
    gone = await tool.handler({
        "meals": place, "pantry": [{"pantry_item_id": str(ghost), "to": "low"}]
    })
    assert text_of(gone) == f"La voce {ghost} non è in dispensa: rileggi con read_pantry."
    soap = await tool.handler({
        "meals": place, "pantry": [{"pantry_item_id": str(items["detersivo"].id), "to": "low"}]
    })
    assert text_of(soap) == "Detersivo non è un alimento: non va nella scheda."
    soap_list = await tool.handler({
        "meals": place, "shopping": [{"ingredient_id": str(rows["detersivo"].id)}]
    })
    assert text_of(soap_list) == "Detersivo non è un alimento: non va nella scheda."
    for result in (unknown, by_name, gone, soap, soap_list):
        assert result["is_error"] is True
    assert (await db_session.execute(select(func.count(ChangeCard.id)))).scalar_one() == 0


async def test_recipe_tools_non_riscrive_una_ricetta_a_mano(db_session, chat, seen, voci):
    rows, _ = voci
    scritta = await create_meal(db_session, day=FRI, slot=MealSlot.DINNER, dish="Torta")
    await write_meal_recipe(
        db_session, scritta,
        MealRecipeDraft(
            title="Torta a mano", description=None, instructions="1. Cuoci.", servings=1,
            lines=(
                DraftLine(
                    ingredient_id=rows["ricotta"].id, name=None, category=None,
                    role=IngredientRole.PRIMARY, quantity_text=None, note=None,
                ),
            ),
            summary="a mano",
        ),
    )
    nuova = await create_meal(db_session, day=SAT, slot=MealSlot.LUNCH, dish="Crostata")
    await db_session.flush()

    def args(title):
        return {
            "title": title, "servings": 1, "instructions": "1. Fai.", "summary": "ok",
            "ingredients": [{"ingredient_id": str(rows["ricotta"].id), "role": "primary"}],
        }

    ctx = make_ctx(db_session, chat, seen, meal_id=scritta.id, create_only=True)
    write = named(recipe_tools(ctx))["write_recipe"]
    result = await write.handler(args("Rifatta"))
    assert result["is_error"] is True
    assert text_of(result) == "Il pasto ha già una ricetta: non riscriverla."
    meal = await get_meal(db_session, scritta.id)
    assert meal.recipe.title == "Torta a mano"
    assert seen["changes"] == []

    ctx = make_ctx(db_session, chat, seen, meal_id=nuova.id, create_only=True)
    write = named(recipe_tools(ctx))["write_recipe"]
    first = await write.handler(args("Crostata"))
    assert "is_error" not in first, text_of(first)
    second = await write.handler(args("Crostata di limoni"))
    assert "is_error" not in second, text_of(second)
    meal = await get_meal(db_session, nuova.id)
    assert meal.recipe.title == "Crostata di limoni"


async def test_fake_per_call(db_session, chat, seen):
    fake = FakeClaude.per_call([Say("uno"), Finish()], [Say("due"), Finish()])

    async def run():
        return [e async for e in fake.run(
            system_prompt="", prompt="", tools=[], effort="low", max_turns=1
        )]

    first = await run()
    second = await run()
    assert [e for e in first if isinstance(e, TurnFinished)][0].text == "uno"
    assert [e for e in second if isinstance(e, TurnFinished)][0].text == "due"
    with pytest.raises(AssertionError):
        await run()
