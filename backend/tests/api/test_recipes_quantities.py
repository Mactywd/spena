"""Le colonne si riempiono passando dall'imbuto vero.

Costruire la riga a mano proverebbe una copia che non gira: è la prima lezione di
CLAUDE.md, e qui conta doppio, perché tutto il valore di questo lavoro sta nel fatto
che nessuno scrittore possa scordarsi di parsare.
"""

from decimal import Decimal

import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import IngredientCategory
from app.db.models.unit import Unit
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import create_recipe


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


async def test_create_recipe_riempie_le_colonne(db_session, cucina):
    recipe = await create_recipe(
        db_session,
        title="prova", description=None, instructions="i", servings=4,
        source="dataset", source_ref=None,
        ingredients=[
            (cucina["pasta"].id, "primary", "300 g", None),
            (cucina["cipolla"].id, "primary", "1", None),
            (cucina["sale"].id, "secondary", "q.b.", None),
        ],
        embedding=None,
    )
    await db_session.flush()

    righe = {ri.ingredient_id: ri for ri in recipe.ingredients}
    assert righe[cucina["pasta"].id].quantity_value == Decimal("300")
    assert righe[cucina["pasta"].id].quantity_unit_id is not None
    # numero nudo: valore sì, unità no — non se ne inventa una che la fonte non ha
    assert righe[cucina["cipolla"].id].quantity_value == Decimal("1")
    assert righe[cucina["cipolla"].id].quantity_unit_id is None
    # non parsata
    assert righe[cucina["sale"].id].quantity_value is None
    assert righe[cucina["sale"].id].quantity_unit_id is None
    # e quantity_text non è stato toccato: resta la verità da mostrare
    assert righe[cucina["pasta"].id].quantity_text == "300 g"


async def test_una_unita_nuova_si_deposita_non_decisa(db_session, cucina):
    await create_recipe(
        db_session,
        title="prova2", description=None, instructions="i", servings=2,
        source="dataset", source_ref=None,
        ingredients=[(cucina["pasta"].id, "primary", "1 costa", None)],
        embedding=None,
    )
    await db_session.flush()

    unit = (
        await db_session.execute(select(Unit).where(Unit.key == "costa"))
    ).scalars().one()
    # nessuna chiamata di rete è partita: la decisione arriva dopo, da un comando
    assert unit.singular is None and unit.decided_by is None


async def test_la_stessa_unita_non_si_duplica(db_session, cucina):
    for title, nome in [("a", "pasta"), ("b", "cipolla")]:
        await create_recipe(
            db_session,
            title=title, description=None, instructions="i", servings=2,
            source="dataset", source_ref=None,
            ingredients=[(cucina[nome].id, "primary", "200 g", None)],
            embedding=None,
        )
    await db_session.flush()
    units = (
        await db_session.execute(select(Unit).where(Unit.key == "g"))
    ).scalars().all()
    assert len(units) == 1
