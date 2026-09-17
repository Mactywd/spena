"""Il rientro in lista, condiviso fra la cottura e il cursore a zero."""

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus
from app.domain.rules import PantryStatus
from app.services.restock import restock
from sqlalchemy import select


async def _voce(db_session, *, con_marca: bool = False) -> PantryItem:
    ingrediente = Ingredient(
        name="pomodoro", display_name="Pomodoro", category=IngredientCategory.VERDURA
    )
    db_session.add(ingrediente)
    await db_session.flush()
    prodotto = None
    if con_marca:
        prodotto = Product(ingredient_id=ingrediente.id, name="Pelati Mutti", source="custom")
        db_session.add(prodotto)
        await db_session.flush()
    item = PantryItem(
        ingredient_id=ingrediente.id,
        product_id=prodotto.id if prodotto else None,
        status=PantryStatus.FINISHED,
    )
    db_session.add(item)
    await db_session.flush()
    return item


async def test_una_voce_finita_torna_in_lista(db_session):
    item = await _voce(db_session)

    assert await restock(db_session, item) is True

    righe = (await db_session.execute(select(ShoppingListItem))).scalars().all()
    assert [(r.raw_text, r.status, r.reason) for r in righe] == [
        ("pomodoro", ShoppingStatus.PENDING, ShoppingReason.MANUAL)
    ]


async def test_in_lista_ci_va_la_marca_che_avevi_comprato(db_session):
    """In negozio «Pelati Mutti» dice più di «pomodoro»."""
    item = await _voce(db_session, con_marca=True)

    await restock(db_session, item)

    riga = (await db_session.execute(select(ShoppingListItem))).scalars().one()
    assert riga.raw_text == "Pelati Mutti"


async def test_quel_che_è_già_in_lista_non_si_duplica(db_session):
    """Due righe identiche in lista sono due giri nello stesso reparto."""
    item = await _voce(db_session)
    await restock(db_session, item)

    assert await restock(db_session, item) is False

    righe = (await db_session.execute(select(ShoppingListItem))).scalars().all()
    assert len(righe) == 1


async def test_una_riga_archiviata_non_conta_come_già_in_lista(db_session):
    """«C'è già» vale per pending e checked: archiviata vuol dire cancellata."""
    item = await _voce(db_session)
    db_session.add(
        ShoppingListItem(
            raw_text="pomodoro", ingredient_id=item.ingredient_id,
            status=ShoppingStatus.ARCHIVED, reason=ShoppingReason.MANUAL,
        )
    )
    await db_session.flush()

    assert await restock(db_session, item) is True


async def test_il_motivo_si_può_dichiarare(db_session):
    """La cottura dice perché la voce rientra; il cursore no, ed è una richiesta a mano."""
    item = await _voce(db_session)

    await restock(db_session, item, reason=ShoppingReason.FINISHED_WHILE_COOKING)

    riga = (await db_session.execute(select(ShoppingListItem))).scalars().one()
    assert riga.reason == ShoppingReason.FINISHED_WHILE_COOKING
