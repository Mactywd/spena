"""Il gesto che chiude il cerchio: cucini, la dispensa si svuota, la lista si riempie.

Tre effetti in una transazione sola. Il chiamante fa commit una volta alla fine:
se qualcosa manca a metà strada, non resta nulla a metà.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.pantry import PantryItem
from app.db.models.recipe import CookingEvent, Recipe
from app.db.models.shopping import ShoppingReason
from app.domain.rules import PantryStatus
from app.services.restock import restock

# il motivo con cui la voce rientra in lista dipende da come l'hai lasciata.
# Finito e basso hanno ciascuno il loro motivo di cottura; tutto il resto è
# una richiesta manuale ordinaria.
_RESTOCK_REASON = {
    PantryStatus.FINISHED: ShoppingReason.FINISHED_WHILE_COOKING,
    PantryStatus.LOW: ShoppingReason.LOW_WHILE_COOKING,
}


@dataclass(frozen=True)
class Transition:
    pantry_item_id: uuid.UUID
    to_status: PantryStatus
    restock: bool


async def cook(
    session: AsyncSession,
    *,
    recipe_id: uuid.UUID,
    servings: int | None,
    transitions: list[Transition],
) -> CookingEvent:
    recipe = await session.get(Recipe, recipe_id)
    if recipe is None:
        raise KeyError(recipe_id)

    now = datetime.now(UTC)
    snapshot: list[dict[str, str | None]] = []
    restocked = 0

    for transition in transitions:
        item = await session.get(PantryItem, transition.pantry_item_id)
        if item is None:
            raise KeyError(transition.pantry_item_id)

        previous = item.status
        item.status = transition.to_status
        # la posizione del cursore non sopravvive a uno stato deciso qui: restare a
        # 80 mentre lo stato dice «finito» mostrerebbe un barattolo pieno per
        # qualcosa che non c'è più (stesso motivo di `set_status`)
        item.fill_percent = None
        item.status_changed_at = now

        if transition.restock and await restock(
            session,
            item,
            reason=_RESTOCK_REASON.get(transition.to_status, ShoppingReason.MANUAL),
        ):
            restocked += 1

        snapshot.append({
            "pantry_item_id": str(item.id),
            "ingredient_id": str(item.ingredient_id),
            "from": previous,
            "to": str(transition.to_status),
            "restocked": transition.restock,
        })

    event = CookingEvent(
        recipe_id=recipe_id, cooked_at=now, servings=servings,
        snapshot={"transitions": snapshot, "restocked": restocked},
    )
    session.add(event)
    await session.flush()
    return event
