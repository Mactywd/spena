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


async def test_la_seconda_passata_sostituisce_quel_che_decide_la_prima(
    db_session, ricetta_mista
):
    """Il motivo per cui questo è un comando e non un passo di migrazione: il
    parser migliora, `quantity_text` no, e rilanciarlo deve sostituire la
    decisione vecchia, non affiancarla. `quantity_text` qui è mutato solo come
    finzione di test per simulare un testo cambiato a monte: il comando non lo
    scrive mai."""
    await reparse(db_session)
    righe = (await db_session.execute(select(RecipeIngredient))).scalars().all()
    per_testo = {ri.quantity_text: ri for ri in righe}
    pasta_id = per_testo["300 g"].id
    sale_id = per_testo["q.b."].id

    # una dose che prima si leggeva ora non si legge più: deve tornare vuota,
    # non restare quella di prima. Un valore rimasto lì mentirebbe a chi lo
    # legge (l'API `?servings=` del Task 5 lo riscalerebbe senza saperlo).
    await db_session.execute(
        update(RecipeIngredient)
        .where(RecipeIngredient.id == pasta_id)
        .values(quantity_text="abbondante")
    )
    # una dose che prima non si leggeva ora si legge, e con un valore diverso
    # da qualunque altro già visto: deve arrivare quello nuovo, non un residuo.
    await db_session.execute(
        update(RecipeIngredient)
        .where(RecipeIngredient.id == sale_id)
        .values(quantity_text="5 g")
    )
    await db_session.flush()

    await reparse(db_session)

    righe = (await db_session.execute(select(RecipeIngredient))).scalars().all()
    per_id = {ri.id: ri for ri in righe}
    pasta_dopo = per_id[pasta_id]
    sale_dopo = per_id[sale_id]
    assert pasta_dopo.quantity_value is None
    assert pasta_dopo.quantity_unit_id is None
    assert sale_dopo.quantity_value == Decimal("5")
    assert sale_dopo.quantity_unit_id is not None
