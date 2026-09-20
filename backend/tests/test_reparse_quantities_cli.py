"""Il comando che riempie le colonne, e che le riempie di nuovo."""

from decimal import Decimal

import pytest_asyncio
from sqlalchemy import select, update

from app.cli.reparse_quantities import reparse
from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe import RecipeIngredient
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import create_recipe


@pytest_asyncio.fixture
async def ricetta_mista(db_session):
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
    await create_recipe(
        db_session,
        title="Mista", description=None, instructions="i", servings=4,
        source="dataset", source_ref=None,
        ingredients=[
            (pasta.id, "primary", "300 g", None),
            (cipolla.id, "primary", "1", None),
            (sale.id, "secondary", "q.b.", None),
        ],
        embedding=None,
    )
    await db_session.flush()


async def test_riempie_le_righe_svuotate(db_session, ricetta_mista):
    """Il caso della messa in produzione: la migrazione aggiunge le colonne vuote e
    questo comando le riempie rileggendo quantity_text, che non si perde mai."""
    await db_session.execute(
        update(RecipeIngredient).values(quantity_value=None, quantity_unit_id=None)
    )
    await db_session.flush()

    esito = await reparse(db_session)

    assert esito.parsed == 2 and esito.unparsed == 1
    righe = (await db_session.execute(select(RecipeIngredient))).scalars().all()
    per_testo = {ri.quantity_text: ri for ri in righe}
    assert per_testo["300 g"].quantity_value == Decimal("300")
    assert per_testo["300 g"].quantity_unit_id is not None
    assert per_testo["q.b."].quantity_value is None


async def test_e_rieseguibile(db_session, ricetta_mista):
    """Il parser migliorerà, e migliorarlo non deve voler dire una migrazione."""
    primo = await reparse(db_session)
    secondo = await reparse(db_session)
    assert (primo.parsed, primo.unparsed) == (secondo.parsed, secondo.unparsed)
    # la seconda passata non deposita niente: «g» c'è già
    assert secondo.new_units == 0
