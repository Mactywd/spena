import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import (
    EMBEDDING_DIM,
    CookingEvent,
    Recipe,
    RecipeIngredient,
    RecipeSource,
)
from app.domain.rules import IngredientRole


async def _ingredient(db_session, name="pomodoro"):
    ingredient = Ingredient(name=name, display_name=name.capitalize(),
                            category=IngredientCategory.VERDURA)
    db_session.add(ingredient)
    await db_session.flush()
    return ingredient


async def test_search_tsv_is_generated_from_title_and_description(db_session):
    recipe = Recipe(title="Pasta al pomodoro", description="Il piatto di sempre",
                    instructions="Cuoci la pasta.", source=RecipeSource.MANUAL)
    db_session.add(recipe)
    await db_session.flush()
    result = await db_session.execute(
        text("SELECT search_tsv::text FROM recipes WHERE id = :id"), {"id": recipe.id}
    )
    tsv = result.scalar_one()
    assert "pomodor" in tsv  # lo stemmer italiano tronca la desinenza
    assert "piatt" in tsv


async def test_embedding_roundtrip_at_the_expected_dimension(db_session):
    recipe = Recipe(title="Soffritto", instructions="Taglia.", source=RecipeSource.MANUAL,
                    embedding=[0.1] * EMBEDDING_DIM)
    db_session.add(recipe)
    await db_session.flush()
    await db_session.refresh(recipe)
    assert len(recipe.embedding) == EMBEDDING_DIM


async def test_embedding_rejects_the_wrong_dimension(db_session):
    db_session.add(Recipe(title="Sbagliata", instructions="x", source=RecipeSource.MANUAL,
                          embedding=[0.1] * 10))
    with pytest.raises(Exception):
        await db_session.flush()


async def test_an_ingredient_appears_once_per_recipe(db_session):
    ingredient = await _ingredient(db_session)
    recipe = Recipe(title="Pasta al pomodoro", instructions="x", source=RecipeSource.MANUAL)
    db_session.add(recipe)
    await db_session.flush()
    db_session.add(RecipeIngredient(recipe_id=recipe.id, ingredient_id=ingredient.id,
                                    role=IngredientRole.PRIMARY, quantity_text="400 g"))
    await db_session.flush()
    db_session.add(RecipeIngredient(recipe_id=recipe.id, ingredient_id=ingredient.id,
                                    role=IngredientRole.SECONDARY))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_recipe_ingredients_cascade_on_recipe_delete(db_session):
    ingredient = await _ingredient(db_session)
    recipe = Recipe(title="Pasta", instructions="x", source=RecipeSource.MANUAL)
    recipe.ingredients.append(
        RecipeIngredient(ingredient_id=ingredient.id, role=IngredientRole.PRIMARY)
    )
    db_session.add(recipe)
    await db_session.flush()
    await db_session.delete(recipe)
    await db_session.flush()
    remaining = await db_session.execute(select(RecipeIngredient))
    assert remaining.scalars().all() == []


async def test_recipe_rejects_an_unknown_role(db_session):
    ingredient = await _ingredient(db_session)
    recipe = Recipe(title="Pasta", instructions="x", source=RecipeSource.MANUAL)
    db_session.add(recipe)
    await db_session.flush()
    db_session.add(RecipeIngredient(recipe_id=recipe.id, ingredient_id=ingredient.id,
                                    role="facoltativo"))
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_cooking_event_keeps_a_snapshot(db_session):
    recipe = Recipe(title="Pasta", instructions="x", source=RecipeSource.MANUAL)
    db_session.add(recipe)
    await db_session.flush()
    event = CookingEvent(
        recipe_id=recipe.id, servings=2,
        snapshot={"transitions": [{"pantry_item": "x", "from": "available", "to": "low"}]},
    )
    db_session.add(event)
    await db_session.flush()
    await db_session.refresh(event)
    assert event.snapshot["transitions"][0]["to"] == "low"
    assert event.cooked_at is not None


async def test_not_null_columns_are_enforced_in_physical_schema(db_session):
    """Recipe.created_at/updated_at/search_tsv e CookingEvent.cooked_at sono non opzionali
    nell'ORM: la migrazione deve rispecchiarlo con nullable=False, non solo
    dichiararlo lato modello."""
    result = await db_session.execute(text(
        """
        SELECT table_name, column_name, is_nullable
        FROM information_schema.columns
        WHERE (table_name = 'recipes' AND column_name IN ('created_at', 'updated_at', 'search_tsv'))
           OR (table_name = 'cooking_events' AND column_name = 'cooked_at')
        """
    ))
    rows = {(row.table_name, row.column_name): row.is_nullable for row in result}
    assert rows == {
        ("recipes", "created_at"): "NO",
        ("recipes", "updated_at"): "NO",
        ("recipes", "search_tsv"): "NO",
        ("cooking_events", "cooked_at"): "NO",
    }


async def test_una_ricetta_non_puo_nominare_una_voce_non_alimentare(db_session):
    """La guardia sta nell'imbuto, quindi vale anche per il seme e per l'import.

    E non scrive niente: se sollevasse dopo aver aggiunto la ricetta, resterebbe
    un titolo senza ingredienti a seconda di dove il chiamante fa il commit.
    """
    import pytest
    from sqlalchemy import select

    from app.db.models.recipe import Recipe
    from app.repositories.ingredients import create_ingredient
    from app.repositories.recipes import NonFoodInRecipe, create_recipe

    sapone = await create_ingredient(db_session, "sapone", "Sapone", "igiene")

    with pytest.raises(NonFoodInRecipe) as caduta:
        await create_recipe(
            db_session,
            title="Pasta al sapone", description=None, instructions="1. no",
            servings=2, source="manual", source_ref=None,
            ingredients=[(sapone.id, "primary", None, None)],
            embedding=None,
        )

    assert caduta.value.display_name == "Sapone"
    rimaste = (
        await db_session.execute(select(Recipe).where(Recipe.title == "Pasta al sapone"))
    ).scalars().all()
    assert rimaste == []
