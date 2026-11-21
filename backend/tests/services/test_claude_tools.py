import asyncio
import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio

from app.db.models.conversation import Conversation, ConversationMessage
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.shopping import ShoppingListItem
from app.domain.meals import MealSlot
from app.repositories.recipes import get_recipe
from app.services.claude.tools import SPENA_SERVER, TurnContext, dish_tools
from app.services.meal_recipes import (
    DraftLine,
    MealRecipeDraft,
    write_meal_recipe,
)
from app.services.meals import create_meal, update_meal

TODAY = date(2026, 11, 12)


@pytest_asyncio.fixture
async def voci(db_session):
    rows = {
        "uova": Ingredient(name="uova", display_name="Uova", category=IngredientCategory.LATTICINI),
        "spinaci": Ingredient(
            name="spinaci", display_name="Spinaci", category=IngredientCategory.VERDURA
        ),
        "detersivo": Ingredient(
            name="detersivo", display_name="Detersivo", category=IngredientCategory.CASA
        ),
    }
    db_session.add_all(rows.values())
    await db_session.flush()
    return rows


@pytest_asyncio.fixture
async def meal(db_session, voci):
    return await create_meal(
        db_session, day=date(2026, 11, 13), slot=MealSlot.DINNER, dish="Frittata", sides=None
    )


@pytest.fixture
def changes():
    return []


@pytest_asyncio.fixture
async def ctx(db_session, meal, changes):
    async def on_change(change):
        changes.append(change)

    conversation = Conversation(kind="dish", meal_id=meal.id)
    db_session.add(conversation)
    await db_session.flush()
    message = ConversationMessage(conversation_id=conversation.id, role="user", text="ciao")
    db_session.add(message)
    await db_session.flush()
    return TurnContext(
        session=db_session, lock=asyncio.Lock(), today=TODAY, meal_id=meal.id,
        conversation_id=conversation.id, turn_message_id=message.id, on_change=on_change,
    )


def by_name(ctx):
    return {t.name: t for t in dish_tools(ctx)}


def text_of(result):
    return result["content"][0]["text"]


def recipe_args(voci, **extra):
    args = {
        "title": "Frittata di spinaci",
        "servings": 1,
        "instructions": "1. Sbatti.\n2. Cuoci.",
        "ingredients": [
            {"ingredient_id": str(voci["uova"].id), "role": "primary", "quantity": "2"},
            {"ingredient_id": str(voci["spinaci"].id), "role": "secondary", "note": "freschi"},
        ],
        "summary": "Frittata di spinaci",
    }
    args.update(extra)
    return args


def test_dish_tools_sono_i_sei_di_spena(ctx):
    tools = dish_tools(ctx)
    assert [t.name for t in tools] == [
        "read_pantry", "read_shopping_list", "read_meals", "search_ingredients", "write_recipe",
        "propose_changes",
    ]
    assert all(t.annotations.read_only_hint is True for t in tools[:4])
    assert SPENA_SERVER == "spena"


async def test_read_pantry_per_reparto_senza_non_alimentari(ctx, db_session, voci):
    db_session.add_all(
        [
            PantryItem(
                ingredient_id=voci["spinaci"].id, status="low",
                expires_on=TODAY + timedelta(days=3),
            ),
            PantryItem(ingredient_id=voci["uova"].id, status="available"),
            PantryItem(ingredient_id=voci["detersivo"].id, status="available"),
        ]
    )
    await db_session.flush()
    result = await by_name(ctx)["read_pantry"].handler({})
    text = text_of(result)
    assert "quasi finito" in text and "scade presto" in text
    assert "detersivo" not in text.lower()
    assert "Uova" in text


async def test_read_pantry_porta_gli_id(ctx, db_session, voci):
    item = PantryItem(ingredient_id=voci["uova"].id, status="available")
    db_session.add(item)
    await db_session.flush()
    text = text_of(await by_name(ctx)["read_pantry"].handler({}))
    assert f"id {item.id}" in text


async def test_read_pantry_vuota(ctx):
    assert text_of(await by_name(ctx)["read_pantry"].handler({})) == "La dispensa è vuota."


async def test_read_shopping_list(ctx, db_session, voci):
    db_session.add_all(
        [
            ShoppingListItem(
                raw_text="latte", status="pending", reason="manual"
            ),
            ShoppingListItem(
                raw_text="pane", status="checked", reason="manual"
            ),
        ]
    )
    await db_session.flush()
    text = text_of(await by_name(ctx)["read_shopping_list"].handler({}))
    assert "da comprare" in text and "nel carrello" in text


async def test_read_meals_con_le_ricette_e_i_posti_vuoti(ctx, db_session, voci):
    dinner = await create_meal(
        db_session, day=date(2026, 11, 10), slot=MealSlot.DINNER, dish="Frittata"
    )
    await write_meal_recipe(
        db_session, dinner,
        MealRecipeDraft(
            title="Frittata", description=None, instructions="Cuoci.", servings=1,
            lines=(
                DraftLine(voci["uova"].id, None, None, "primary", "2 uova", None),
            ),
            summary="x",
        ),
    )
    result = await by_name(ctx)["read_meals"].handler({"start": "2026-11-10", "end": "2026-11-10"})
    assert not result.get("is_error")
    text = text_of(result)
    assert "Frittata" in text and "2 uova" in text and "(vuoto)" in text


async def test_read_meals_non_mostra_la_ricetta_di_un_pasto_fuori_casa(ctx, db_session, voci):
    dinner = await create_meal(
        db_session, day=date(2026, 11, 10), slot=MealSlot.DINNER, dish="Frittata"
    )
    await write_meal_recipe(
        db_session, dinner,
        MealRecipeDraft(
            title="Frittata", description=None, instructions="Cuoci.", servings=1,
            lines=(DraftLine(voci["uova"].id, None, None, "primary", "2 uova", None),),
            summary="x",
        ),
    )
    await update_meal(db_session, dinner, {"away": True})
    result = await by_name(ctx)["read_meals"].handler({"start": "2026-11-10", "end": "2026-11-10"})
    text = text_of(result)
    assert "(fuori casa)" in text
    assert "ricetta:" not in text and "2 uova" not in text


async def test_read_meals_rifiuta_un_intervallo_troppo_lungo(ctx):
    tool = by_name(ctx)["read_meals"]
    lungo = await tool.handler({"start": "2026-11-01", "end": "2026-11-29"})
    assert lungo["is_error"] is True
    assert "Chiedi al massimo 28 giorni" in text_of(lungo)
    rovescio = await tool.handler({"start": "2026-11-10", "end": "2026-11-09"})
    assert rovescio["is_error"] is True


async def test_search_ingredients_solo_alimentari(ctx, voci):
    tool = by_name(ctx)["search_ingredients"]
    assert str(voci["spinaci"].id) in text_of(await tool.handler({"name": "spinaci"}))
    assert text_of(await tool.handler({"name": "detersivo"})) == (
        "Nessun ingrediente con questo nome: usa name e department nella riga."
    )


async def test_write_recipe_scrive_e_avvisa(ctx, db_session, meal, voci, changes):
    result = await by_name(ctx)["write_recipe"].handler(recipe_args(voci))
    assert not result.get("is_error")
    assert text_of(result) == "Scritta. Mattia vede la ricetta aggiornata."
    await db_session.refresh(meal)
    recipe = await get_recipe(db_session, meal.recipe_id)
    assert recipe is not None and len(recipe.ingredients) == 2
    assert len(changes) == 1


async def test_write_recipe_non_accetta_il_posto(ctx, db_session, meal, voci, changes):
    result = await by_name(ctx)["write_recipe"].handler(recipe_args(voci, day="2026-11-13"))
    assert result["is_error"] is True
    await db_session.refresh(meal)
    assert meal.recipe_id is None and changes == []


async def test_write_recipe_rifiutata_lo_dice_a_claude(ctx, db_session, meal, voci, changes):
    args = recipe_args(voci)
    args["ingredients"].append(
        {"ingredient_id": str(voci["detersivo"].id), "role": "secondary"}
    )
    result = await by_name(ctx)["write_recipe"].handler(args)
    assert result["is_error"] is True
    assert "Detersivo" in text_of(result)
    assert changes == []
    # la sessione resta usabile, e niente è scritto
    await db_session.refresh(meal)
    assert meal.recipe_id is None


async def test_write_recipe_senza_pasto(ctx, voci):
    ctx.meal_id = None
    result = await by_name(ctx)["write_recipe"].handler(recipe_args(voci))
    assert result["is_error"] is True


async def test_due_letture_in_parallelo_non_si_pestano(ctx):
    tools = by_name(ctx)
    a, b = await asyncio.gather(
        tools["read_pantry"].handler({}), tools["read_shopping_list"].handler({})
    )
    assert not a.get("is_error") and not b.get("is_error")
