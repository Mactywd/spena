"""Il gesto che chiude il cerchio: cucini, la dispensa si svuota, la lista si riempie.

Tre effetti in una transazione sola. Il chiamante fa commit una volta alla fine:
se qualcosa manca a metà strada, non resta nulla a metà.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.pantry import PantryItem
from app.db.models.recipe import CookingEvent, Recipe
from app.db.models.shopping import ShoppingReason
from app.domain.quantities import decimal_text
from app.domain.rules import PantryStatus
from app.repositories.recipes import get_recipe
from app.services.rescale import AnchorRefused, find_anchor_line, resolve_anchor
from app.services.restock import restock

# il motivo con cui la voce rientra in lista dipende da come l'hai lasciata.
# Finito e basso hanno ciascuno il loro motivo di cottura; tutto il resto è
# una richiesta manuale ordinaria.
_RESTOCK_REASON = {
    PantryStatus.FINISHED: ShoppingReason.FINISHED_WHILE_COOKING,
    PantryStatus.LOW: ShoppingReason.LOW_WHILE_COOKING,
}

# il fattore nello storico: un appunto da rileggere, a sei decimali. Non ricostruisce ogni
# dose (su una base grande l'arrotondamento si vede): la verità è la quantità fissata, che
# l'ancora conserva a parte
FACTOR_PRECISION = Decimal("0.000001")


def anchor_record(
    recipe: Recipe, ingredient_id: uuid.UUID, amount: Decimal
) -> dict[str, str | None]:
    """Cosa si è cucinato quando si è riscalato da una dose (R2, secondo modo).

    Va nello `snapshot` e non in `servings`: le porzioni sono un intero che dice
    quante ne sono uscite dalla pentola, ed è un fatto solo quando lo si è scelto; «1,5»
    è un derivato, e scriverlo arrotondato sarebbe falso per sempre. Il fatto vero è la
    dose dell'ancora. Il fattore si ricalcola con la funzione del dettaglio; un'ancora
    che adesso non vale più (riga tolta, fuori scala) non blocca la cottura: si registra
    con `factor` nullo. Stringhe col punto e non `Decimal`: il JSONB non li sa scrivere.
    """
    line = find_anchor_line(recipe, ingredient_id)
    try:
        resolved = resolve_anchor(recipe, ingredient_id, amount)
    except AnchorRefused:
        resolved = None
    return {
        "ingredient_id": str(ingredient_id),
        "amount": decimal_text(amount),
        "unit": line.unit.key if line is not None and line.unit is not None else None,
        "factor": (
            decimal_text(resolved.factor.quantize(FACTOR_PRECISION))
            if resolved is not None
            else None
        ),
        "equivalent_servings": (
            decimal_text(resolved.equivalent_servings)
            if resolved is not None and resolved.equivalent_servings is not None
            else None
        ),
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
    anchor: tuple[uuid.UUID, Decimal] | None = None,
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
        # Una «transizione» allo stesso stato non cambia niente della voce: è il foglio
        # che rimette in lista una confezione già quasi finita senza toccarla (decisione
        # di Mattia del 2026-10-09). Riscrivere `status_changed_at`, o azzerare il
        # cursore, direbbe un cambio che non c'è stato. Il rientro qui sotto vale lo
        # stesso, col motivo dello stato, e l'istantanea la registra con `from` uguale a
        # `to`: la storia vera di quella sera.
        if transition.to_status != previous:
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

    record: dict[str, Any] = {"transitions": snapshot, "restocked": restocked}
    if anchor is not None:
        # le righe e le loro unità si caricano qui, come fa il dettaglio: `session.get`
        # non le porta se la ricetta è già nella sessione senza di esse
        loaded = await get_recipe(session, recipe_id)
        if loaded is None:  # l'abbiamo appena letta; se sparisce, la route risponde 404
            raise KeyError(recipe_id)
        record["anchor"] = anchor_record(loaded, *anchor)
    event = CookingEvent(
        recipe_id=recipe_id, cooked_at=now, servings=servings, snapshot=record,
    )
    session.add(event)
    await session.flush()
    return event
