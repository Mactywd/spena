import uuid
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe
from app.db.models.recipe_change import RecipeChange
from app.domain.meals import MealSlot, MealStatus
from app.repositories.recipes import get_recipe
from app.services.meal_recipes import (
    UNSET,
    ChangeRefusal,
    ChangeRefusalCode,
    DraftLine,
    MealRecipeDraft,
    RecipeWriteRefused,
    change_is_undoable,
    meal_snapshot,
    undo_recipe_change,
    write_meal_recipe,
)
from app.services.meals import MealRefusal, create_meal
from app.services.registry import merge_ingredients

DAY = date(2026, 11, 11)


@pytest_asyncio.fixture
async def voci(db_session):
    rows = {
        "uova": Ingredient(name="uova", display_name="Uova", category=IngredientCategory.LATTICINI),
        "spinaci": Ingredient(
            name="spinaci", display_name="Spinaci", category=IngredientCategory.VERDURA
        ),
        "parmigiano": Ingredient(
            name="parmigiano", display_name="Parmigiano", category=IngredientCategory.LATTICINI
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
        db_session, day=DAY, slot=MealSlot.DINNER, dish="Frittata", sides="insalata"
    )


def line(ingredient, role="primary", text=None, note=None):
    return DraftLine(
        ingredient_id=ingredient.id, name=None, category=None,
        role=role, quantity_text=text, note=note,
    )


def named(name, category=None, role="primary", text=None):
    return DraftLine(
        ingredient_id=None, name=name, category=category, role=role,
        quantity_text=text, note=None,
    )


def draft(*lines, title="Frittata di spinaci", **extra):
    return MealRecipeDraft(
        title=title, description=None, instructions="Sbatti. Cuoci.", servings=1,
        lines=tuple(lines), summary="Frittata di spinaci", **extra,
    )


async def lines_of(session, meal):
    recipe = await get_recipe(session, meal.recipe_id)
    await session.refresh(recipe)
    return {ri.ingredient_id: ri for ri in recipe.ingredients}


async def test_scrive_da_zero_la_ricetta_di_un_pasto_senza_ricetta(db_session, voci, meal):
    change = await write_meal_recipe(
        db_session, meal,
        draft(line(voci["uova"], text="2"), line(voci["spinaci"], text="150 g")),
    )
    await db_session.flush()
    stored = await get_recipe(db_session, meal.recipe_id)
    assert stored.source == "ai" and stored.in_book is False and stored.servings == 1
    assert meal.recipe_id == stored.id == change.recipe_id
    rows = await lines_of(db_session, meal)
    assert rows[voci["spinaci"].id].quantity_value == 150
    assert change.created_recipe is True
    assert change.before["recipe"] is None


async def _two_writes(db_session, voci, meal):
    first = await write_meal_recipe(
        db_session, meal, draft(line(voci["uova"], text="2"), line(voci["spinaci"], text="200 g"))
    )
    second = await write_meal_recipe(
        db_session, meal,
        draft(
            line(voci["uova"], text="2"),
            line(voci["spinaci"], text="150 g", note="congelati"),
        ),
    )
    await db_session.flush()
    return first, second


async def test_riscrive_la_ricetta_che_c_e_e_ricorda_quella_di_prima(db_session, voci, meal):
    _, second = await _two_writes(db_session, voci, meal)
    spin = str(voci["spinaci"].id)
    before = {x["ingredient_id"]: x for x in second.before["recipe"]["lines"]}
    after = {x["ingredient_id"]: x for x in second.after["recipe"]["lines"]}
    assert before[spin]["quantity_text"] == "200 g"
    assert after[spin]["quantity_text"] == "150 g"
    assert second.created_recipe is False
    assert second.changed["ingredient_ids"] == [spin]


async def test_cambia_piatto_e_accompagnamenti_ma_non_il_posto(db_session, voci, meal):
    await write_meal_recipe(
        db_session, meal,
        draft(line(voci["uova"]), dish="  Frittata di zucchine ", sides=None),
    )
    assert meal.dish == "Frittata di zucchine" and meal.sides is None
    assert meal.day == DAY and meal.slot == MealSlot.DINNER.value
    meal.sides = "pane"
    await write_meal_recipe(db_session, meal, draft(line(voci["uova"]), sides=UNSET))
    assert meal.sides == "pane"
    await write_meal_recipe(db_session, meal, draft(line(voci["uova"]), sides="  "))
    assert meal.sides is None


async def test_un_nome_nuovo_passa_dalla_strada_del_modulo(db_session, voci, meal):
    before = len((await db_session.execute(select(Ingredient))).scalars().all())
    await write_meal_recipe(
        db_session, meal,
        draft(named("Spinaci"), named("erba cipollina", IngredientCategory.VERDURA)),
    )
    rows = await lines_of(db_session, meal)
    assert voci["spinaci"].id in rows
    after = (await db_session.execute(select(Ingredient))).scalars().all()
    assert len(after) == before + 1
    assert any(i.name == "erba cipollina" for i in after)


@pytest.mark.parametrize("by_name", [False, True])
async def test_il_non_alimentare_si_rifiuta(db_session, voci, meal, by_name):
    bad = named("detersivo") if by_name else line(voci["detersivo"])
    with pytest.raises(RecipeWriteRefused) as caught:
        await write_meal_recipe(db_session, meal, draft(bad))
    assert "Detersivo" in caught.value.message and "non è un alimento" in caught.value.message
    await db_session.refresh(meal)
    assert meal.recipe_id is None


async def test_un_rifiuto_non_lascia_niente(db_session, voci, meal):
    first = await write_meal_recipe(db_session, meal, draft(line(voci["uova"], text="2")))
    await db_session.flush()
    snap = await meal_snapshot(db_session, meal)
    with pytest.raises(RecipeWriteRefused) as caught:
        await write_meal_recipe(
            db_session, meal,
            draft(
                named("erba cipollina", IngredientCategory.VERDURA),
                line(voci["uova"]), line(voci["uova"]), dish="Altro",
            ),
        )
    assert caught.value.message == (
        "Due righe puntano allo stesso ingrediente, Uova: tienine una."
    )
    names = (await db_session.execute(select(Ingredient.name))).scalars().all()
    assert "erba cipollina" not in names
    assert await meal_snapshot(db_session, meal) == snap
    changes = (await db_session.execute(select(RecipeChange))).scalars().all()
    assert [c.id for c in changes] == [first.id]


async def test_un_id_che_non_c_e_si_rifiuta(db_session, voci, meal):
    missing = uuid.uuid4()
    with pytest.raises(RecipeWriteRefused) as caught:
        await write_meal_recipe(
            db_session, meal,
            draft(DraftLine(missing, None, None, "primary", None, None)),
        )
    assert caught.value.message == (
        f"L'ingrediente {missing} non esiste: cercalo di nuovo con search_ingredients."
    )


@pytest.mark.parametrize("case", ["bozza", "fuori casa", "avanzo"])
async def test_chi_non_puo_avere_una_ricetta(db_session, voci, case):
    if case == "bozza":
        target = await create_meal(
            db_session, day=DAY, slot=MealSlot.LUNCH, dish="Pasta", status=MealStatus.DRAFT
        )
    elif case == "fuori casa":
        target = await create_meal(
            db_session, day=DAY, slot=MealSlot.LUNCH, dish="Pizza", away=True
        )
    else:
        origin = await create_meal(db_session, day=date(2026, 11, 9), slot=MealSlot.LUNCH, dish="Ragù")
        target = await create_meal(
            db_session, day=DAY, slot=MealSlot.LUNCH, dish="Ragù avanzato",
            leftover_of_id=origin.id,
        )
    with pytest.raises(MealRefusal):
        await write_meal_recipe(db_session, target, draft(line(voci["uova"])))
    assert (await db_session.execute(select(Recipe))).scalars().all() == []


async def test_annulla_rimette_la_versione_di_prima(db_session, voci, meal):
    first, second = await _two_writes(db_session, voci, meal)
    # il piatto cambiato dalla seconda scrittura torna com'era
    await undo_recipe_change(db_session, second)
    rows = await lines_of(db_session, meal)
    spin = rows[voci["spinaci"].id]
    assert spin.quantity_text == "200 g" and spin.note is None and spin.quantity_value == 200
    assert second.undone_at is not None
    assert meal.dish == "Frittata"


async def test_annulla_una_ricetta_scritta_da_zero_la_stacca_dal_pasto(db_session, voci, meal):
    change = await write_meal_recipe(db_session, meal, draft(line(voci["uova"])))
    await undo_recipe_change(db_session, change)
    assert meal.recipe_id is None
    recipe = await db_session.get(Recipe, change.recipe_id)
    await db_session.refresh(recipe)
    assert recipe.archived_at is not None


async def test_annulla_dopo_una_correzione_a_mano_si_rifiuta(
    db_session, logged_client, voci, meal
):
    change = await write_meal_recipe(db_session, meal, draft(line(voci["uova"], text="2")))
    await db_session.flush()
    risposta = await logged_client.put(
        f"/api/v1/recipes/{change.recipe_id}",
        json={
            "title": "Titolo corretto", "description": None, "category": None,
            "instructions": "Sbatti. Cuoci.", "servings": 1, "cost": None,
            "ingredients": [
                {"ingredient_id": str(voci["uova"].id), "role": "primary", "quantity_text": "2"}
            ],
        },
    )
    assert risposta.status_code == 200, risposta.text
    with pytest.raises(ChangeRefusal) as caught:
        await undo_recipe_change(db_session, change)
    assert caught.value.code == ChangeRefusalCode.STALE
    assert (await get_recipe(db_session, change.recipe_id)).title == "Titolo corretto"
    assert await change_is_undoable(db_session, change) is False


async def test_annulla_solo_l_ultima(db_session, voci, meal):
    first, second = await _two_writes(db_session, voci, meal)
    with pytest.raises(ChangeRefusal) as caught:
        await undo_recipe_change(db_session, first)
    assert caught.value.code == ChangeRefusalCode.STALE
    await undo_recipe_change(db_session, second)


async def test_annullare_due_volte(db_session, voci, meal):
    change = await write_meal_recipe(db_session, meal, draft(line(voci["uova"])))
    await undo_recipe_change(db_session, change)
    with pytest.raises(ChangeRefusal) as caught:
        await undo_recipe_change(db_session, change)
    assert caught.value.code == ChangeRefusalCode.ALREADY_UNDONE
    assert caught.value.message == "Questa modifica è già stata annullata."


async def test_annulla_con_un_ingrediente_sparito(db_session, voci, meal):
    await write_meal_recipe(
        db_session, meal, draft(line(voci["uova"]), line(voci["parmigiano"], text="30 g"))
    )
    change = await write_meal_recipe(db_session, meal, draft(line(voci["uova"])))
    await merge_ingredients(db_session, voci["parmigiano"].id, voci["spinaci"].id)
    before = await meal_snapshot(db_session, meal)
    with pytest.raises(ChangeRefusal) as caught:
        await undo_recipe_change(db_session, change)
    assert caught.value.code == ChangeRefusalCode.STALE
    assert caught.value.message == (
        "Un ingrediente della versione di prima non c'è più: correggi la ricetta dal modulo."
    )
    assert await meal_snapshot(db_session, meal) == before
