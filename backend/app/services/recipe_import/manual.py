"""La decisione a mano su un termine, in un posto solo.

La prende la scheda della revisione (`POST /imports/terms/{id}/decision`) e la prende
`app.cli.fix_registry`, che corregge l'anagrafica a lotti. Due copie delle guardie qui
sotto si scollerebbero, e la prima a scollarsi sarebbe quella sul non alimentare.

Non materializza e non fa commit: chi chiama decide quando, perché la rotta sblocca
subito le ricette di quel termine e il comando lo fa una volta sola a fine lotto.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient
from app.db.models.recipe_import import ImportTerm, TermDecision
from app.domain.rules import NON_FOOD_CATEGORIES, IngredientKind
from app.repositories.ingredients import create_ingredient, remember_alias


class Refusal(StrEnum):
    """Perché una decisione non si può applicare; la rotta ne ricava lo status HTTP."""

    INVALID = "invalid"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"


class DecisionRefused(Exception):
    def __init__(self, refusal: Refusal, message: str) -> None:
        super().__init__(message)
        self.refusal = refusal
        self.message = message


@dataclass(frozen=True)
class ManualDecision:
    action: str  # "map" | "create" | "ignore"
    ingredient_id: uuid.UUID | None = None
    name: str | None = None
    display_name: str | None = None
    category: str | None = None
    role_override: str | None = None


async def decide_by_hand(
    session: AsyncSession, term: ImportTerm, decision: ManualDecision
) -> Ingredient | None:
    """Applica la decisione al termine e torna l'ingrediente a cui ora punta."""
    ingredient: Ingredient | None = None
    if decision.action == "ignore":
        term.decision = TermDecision.IGNORED
        term.ingredient_id = None
    else:
        if decision.action == "map":
            if decision.ingredient_id is None:
                raise DecisionRefused(Refusal.INVALID, "per collegare serve l'ingrediente")
            ingredient = await session.get(Ingredient, decision.ingredient_id)
            if ingredient is None:
                raise DecisionRefused(Refusal.NOT_FOUND, "ingrediente inesistente")
            # Presto, e non alla materializzazione: chi chiama materializza nella
            # stessa transazione, e quel ciclo non protegge le singole ricette — una
            # riga non alimentare farebbe fallire tutto il lotto pronto, non solo la
            # ricetta colpevole, con la decisione già scritta. Un rifiuto a fine lotto
            # è il vicolo cieco peggiore.
            if ingredient.kind == IngredientKind.NON_FOOD:
                raise DecisionRefused(
                    Refusal.INVALID,
                    f"«{ingredient.display_name}» non è un alimento: un termine di "
                    "ricetta non può collegarsi a una voce non alimentare. "
                    "Scegline un'altra, oppure ignora il termine.",
                )
        else:
            if not decision.name or decision.category is None:
                raise DecisionRefused(
                    Refusal.INVALID, "per creare un ingrediente servono nome e categoria"
                )
            if decision.category in NON_FOOD_CATEGORIES:
                raise DecisionRefused(
                    Refusal.INVALID,
                    f"«{decision.category}» non è un reparto alimentare: un termine "
                    "di ricetta non può creare una voce non alimentare. "
                    "Scegli un altro reparto, oppure ignora il termine.",
                )
            existing = (
                await session.execute(
                    select(Ingredient).where(
                        Ingredient.name == decision.name.strip().lower()
                    )
                )
            ).scalars().first()
            if existing is not None:
                raise DecisionRefused(
                    Refusal.CONFLICT,
                    f"«{existing.name}» è già in anagrafica: collega il termine invece "
                    "di creare un doppione.",
                )
            ingredient = await create_ingredient(
                session, name=decision.name,
                display_name=decision.display_name or decision.name,
                category=decision.category,
            )

        term.decision = TermDecision.MAPPED
        term.ingredient_id = ingredient.id
        await remember_alias(session, ingredient.id, term.display_name)

    term.role_override = decision.role_override
    term.decided_by = "human"
    term.decided_at = datetime.now(UTC)
    await session.flush()
    return ingredient
