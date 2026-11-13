import uuid
from datetime import date

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe, RecipeIngredient
from app.domain.meals import MealSlot
from app.services.claude.prompts import (
    COMMON_PROMPT,
    DISH_PANTRY_RULE,
    DISH_PROMPT,
    DishContext,
    HistoryItem,
    dish_system_prompt,
    render_turn_prompt,
)
from app.services.utensils import render_utensils_block


def test_il_prompt_del_piatto_senza_utensili():
    assert dish_system_prompt(None) == COMMON_PROMPT + "\n\n" + DISH_PROMPT + "\n\n" + DISH_PANTRY_RULE


def test_il_prompt_del_piatto_con_gli_utensili():
    block = render_utensils_block([("frusta elettrica", None)])
    prompt = dish_system_prompt(block)
    assert prompt.endswith(block)
    assert prompt.startswith(COMMON_PROMPT)


def test_il_prompt_dice_le_regole_della_skill():
    prompt = dish_system_prompt(None)
    for frase in (
        "già al netto dei pasti pianificati",
        "vasetto avviato",
        "5 g al giorno",
        "1 porzione",
        "Il ricettario di spena non lo leggi",
        "Il giorno e il pasto non li cambi tu",
    ):
        assert frase in prompt


def _recipe():
    spinaci = Ingredient(
        id=uuid.uuid4(), name="spinaci", display_name="Spinaci", category=IngredientCategory.VERDURA
    )
    uova = Ingredient(
        id=uuid.uuid4(), name="uova", display_name="Uova", category=IngredientCategory.LATTICINI
    )
    recipe = Recipe(
        title="Frittata di spinaci", description=None, instructions="1. Sbatti.\n2. Cuoci.",
        servings=1, source="ai",
    )
    recipe.ingredients = [
        RecipeIngredient(
            ingredient_id=spinaci.id, ingredient=spinaci, role="primary",
            quantity_text="150 g", note="congelati",
        ),
        RecipeIngredient(
            ingredient_id=uova.id, ingredient=uova, role="primary", quantity_text="2", note=None
        ),
    ]
    return recipe, spinaci, uova


def test_render_turn_prompt():
    recipe, spinaci, uova = _recipe()
    ctx = DishContext(
        today=date(2026, 11, 12), day=date(2026, 11, 10), slot=MealSlot.DINNER,
        dish="Frittata", sides="insalata", recipe=recipe,
    )
    history = [
        HistoryItem("user", "Metti più verdura", ()),
        HistoryItem("assistant", "Fatto.", ("Ricetta aggiornata: più spinaci — annullata",)),
    ]
    text = render_turn_prompt(ctx, history, "E se non ho le uova?")
    assert "Oggi: giovedì 12 novembre 2026" in text
    assert "martedì 10 novembre, cena" in text
    assert "Frittata" in text and "insalata" in text
    assert f"ingredient_id {spinaci.id}" in text and "150 g" in text
    assert f"ingredient_id {uova.id}" in text
    assert "1. Sbatti." in text
    assert text.index("Metti più verdura") < text.index("Ricetta aggiornata: più spinaci — annullata")
    assert text.index("annullata") < text.index("E se non ho le uova?")
    assert text.rstrip().endswith("E se non ho le uova?")

    senza = DishContext(
        today=date(2026, 11, 12), day=date(2026, 11, 10), slot=MealSlot.DINNER,
        dish="Frittata", sides=None, recipe=None,
    )
    assert "Il pasto non ha ancora una ricetta." in render_turn_prompt(senza, [], "ciao")
