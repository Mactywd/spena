"""Quale alimento CIQUAL dà i nutrienti a un ingrediente (S4, fetta 1).

L'unico posto che scrive `ingredient_nutrition`: la scelta a mano (Anagrafica, rotte di
`app/api/nutrition.py`) e quella dell'AI (`services/ciqual_match.py`). Non sta in
`registry.py` perché non tocca l'anagrafica — non rinomina, non sposta, non fonde — e
perché quel file lo cambiano altri piani della stessa notte (spec §4.16). Il rifiuto ha
la stessa forma di quelli dell'anagrafica: un codice e una frase da mostrare.

Tre stati (spec §4.5): nessuna riga = da decidere; `ciqual_code` NULL = «nessun alimento
adatto», deciso; un codice = quell'alimento. Una scelta a mano vince sempre: la scrive
anche sopra quella dell'AI, mentre l'AI scrive solo dove non c'è niente, e lo controlla
nella stessa INSERT (`ON CONFLICT DO NOTHING`). «Annulla la scelta» toglie la riga:
l'ingrediente torna da decidere, e l'AI lo riprenderà al giro dopo.
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient
from app.db.models.nutrition import CiqualFood, IngredientNutrition, NutritionDecider
from app.domain.rules import IngredientKind
from app.repositories.ciqual import get_food

NON_FOOD_CODE = "non_food"
UNKNOWN_FOOD_CODE = "unknown_food"


class NutritionState(StrEnum):
    UNDECIDED = "undecided"
    NONE = "none"
    FOOD = "food"
    NON_FOOD = "non_food"


class NutritionRefusal(Exception):
    """Una scelta che non si può salvare così com'è, detta col suo perché."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class NutritionView:
    state: NutritionState
    decided_by: str | None = None
    food: CiqualFood | None = None


async def _ingredient(session: AsyncSession, ingredient_id: uuid.UUID) -> Ingredient:
    ingredient = await session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise LookupError(f"nessun ingrediente {ingredient_id}")
    return ingredient


async def nutrition_of(session: AsyncSession, ingredient_id: uuid.UUID) -> NutritionView:
    ingredient = await _ingredient(session, ingredient_id)
    if ingredient.kind != IngredientKind.FOOD:
        return NutritionView(NutritionState.NON_FOOD)
    # le colonne e non l'oggetto: una INSERT … ON CONFLICT appena fatta non passa
    # dall'identity map, e un oggetto già in memoria sarebbe quello di prima
    row = (
        await session.execute(
            select(IngredientNutrition.ciqual_code, IngredientNutrition.decided_by).where(
                IngredientNutrition.ingredient_id == ingredient_id
            )
        )
    ).first()
    if row is None:
        return NutritionView(NutritionState.UNDECIDED)
    if row.ciqual_code is None:
        return NutritionView(NutritionState.NONE, row.decided_by)
    return NutritionView(NutritionState.FOOD, row.decided_by, await get_food(session, row.ciqual_code))


async def choose_food(
    session: AsyncSession, ingredient_id: uuid.UUID, code: str | None
) -> NutritionView:
    """La scelta a mano: un codice, o `None` per «nessun alimento adatto». Vince sempre."""
    ingredient = await _ingredient(session, ingredient_id)
    if ingredient.kind != IngredientKind.FOOD:
        raise NutritionRefusal(
            NON_FOOD_CODE,
            f"«{ingredient.display_name}» non è un alimento: non ha valori nutrizionali.",
        )
    if code is not None and await get_food(session, code) is None:
        raise NutritionRefusal(
            UNKNOWN_FOOD_CODE,
            "Questo alimento non è nella tabella CIQUAL caricata: cercane un altro.",
        )
    statement = pg_insert(IngredientNutrition).values(
        ingredient_id=ingredient_id,
        ciqual_code=code,
        decided_by=NutritionDecider.HUMAN,
        decided_at=func.now(),
    )
    await session.execute(
        statement.on_conflict_do_update(
            index_elements=[IngredientNutrition.ingredient_id],
            set_={
                "ciqual_code": statement.excluded.ciqual_code,
                "decided_by": statement.excluded.decided_by,
                "decided_at": statement.excluded.decided_at,
            },
        )
    )
    return await nutrition_of(session, ingredient_id)


async def forget_choice(session: AsyncSession, ingredient_id: uuid.UUID) -> NutritionView:
    """L'annullamento: la riga se ne va, e l'ingrediente torna da decidere."""
    await _ingredient(session, ingredient_id)
    await session.execute(
        delete(IngredientNutrition).where(IngredientNutrition.ingredient_id == ingredient_id)
    )
    return await nutrition_of(session, ingredient_id)


async def apply_ai_choice(
    session: AsyncSession, ingredient_id: uuid.UUID, code: str | None
) -> bool:
    """La scelta dell'AI, solo dove non c'è niente. `True` se l'ha scritta.

    Il controllo sta nella INSERT stessa: una scelta fatta a mano mentre il comando
    aspettava la risposta non si sovrascrive.
    """
    result = await session.execute(
        pg_insert(IngredientNutrition)
        .values(ingredient_id=ingredient_id, ciqual_code=code, decided_by=NutritionDecider.AI)
        .on_conflict_do_nothing(index_elements=[IngredientNutrition.ingredient_id])
    )
    return result.rowcount == 1
