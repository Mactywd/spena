"""Una voce di dispensa che torna in lista della spesa.

Un solo posto per due chiamanti: la cottura, che rimette in lista quel che ha
finito, e il cursore portato a zero, che lo chiede. Stava tutto dentro `cook()`;
una seconda copia si sarebbe scollata sul punto che conta — il non duplicare.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.pantry import PantryItem
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus
from app.repositories.shopping import active_item_for


async def already_in_list(session: AsyncSession, ingredient_id: uuid.UUID) -> bool:
    """Se quell'ingrediente è già da comprare. Archiviato non conta: è cancellato.

    La regola sta in `active_item_for`, che usa anche l'aggiunta a mano in lista
    (S18): due copie di «che cosa è già in lista» si scollerebbero proprio sul
    punto per cui esistono, il non duplicare.
    """
    return await active_item_for(session, ingredient_id) is not None


async def restock(
    session: AsyncSession,
    item: PantryItem,
    reason: ShoppingReason = ShoppingReason.MANUAL,
) -> bool:
    """Scrive la voce in lista, se non c'è già. Torna se ha scritto davvero.

    Il falso non è un errore ed è un'informazione: chi chiede può dire «era già in
    lista» invece di far credere di aver aggiunto qualcosa.
    """
    if await already_in_list(session, item.ingredient_id):
        return False

    await session.refresh(item, ["ingredient", "product"])
    # la marca che avevi comprato è l'informazione più utile in negozio
    label = item.product.name if item.product else item.ingredient.name
    session.add(
        ShoppingListItem(
            raw_text=label,
            ingredient_id=item.ingredient_id,
            status=ShoppingStatus.PENDING,
            reason=reason,
        )
    )
    await session.flush()
    return True
