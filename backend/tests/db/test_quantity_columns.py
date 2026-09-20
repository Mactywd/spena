"""I tre stati validi di una dose, e il quarto che il database rifiuta."""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.exc import IntegrityError

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe import Recipe, RecipeIngredient
from app.db.models.unit import Unit
from app.repositories.ingredients import create_ingredient


@pytest_asyncio.fixture
async def cucina(db_session):
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta",
        category=IngredientCategory.CEREALI,
    )
    cipolla = await create_ingredient(
        db_session, name="cipolla", display_name="Cipolla",
        category=IngredientCategory.VERDURA,
    )
    sale = await create_ingredient(
        db_session, name="sale", display_name="Sale", category=IngredientCategory.SPEZIE,
    )
    return {"pasta": pasta, "cipolla": cipolla, "sale": sale}


async def test_unita_senza_numero_e_vietata(db_session, cucina):
    """La quarta combinazione non ha senso: un'unità senza un numero davanti non è
    una dose. Il vincolo sta nel database e non solo nel codice perché il riparsare
    e una futura migrazione scrivono queste colonne senza passare da create_recipe."""
    unit = Unit(key="g")
    db_session.add(unit)
    await db_session.flush()

    recipe = Recipe(title="vietata", instructions="i", source="dataset")
    recipe.ingredients.append(
        RecipeIngredient(
            ingredient_id=cucina["pasta"].id,
            role="primary",
            quantity_text="g",
            quantity_value=None,
            quantity_unit_id=unit.id,
        )
    )
    db_session.add(recipe)
    with pytest.raises(IntegrityError):
        await db_session.flush()


async def test_i_tre_stati_validi_si_scrivono(db_session, cucina):
    unit = Unit(key="g", singular="g", plural="g")
    db_session.add(unit)
    await db_session.flush()

    recipe = Recipe(title="valida", instructions="i", source="dataset")
    righe = [
        (cucina["sale"], None, None, "q.b."),            # non parsata
        (cucina["cipolla"], Decimal("1"), None, "1"),     # numero nudo
        (cucina["pasta"], Decimal("300"), unit.id, "300 g"),  # dose piena
    ]
    for ingredient, value, unit_id, text in righe:
        recipe.ingredients.append(
            RecipeIngredient(
                ingredient_id=ingredient.id, role="secondary", quantity_text=text,
                quantity_value=value, quantity_unit_id=unit_id,
            )
        )
    db_session.add(recipe)
    await db_session.flush()  # non solleva
