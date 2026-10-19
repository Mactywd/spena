"""I valori nutrizionali di un ingrediente, e la ricerca in CIQUAL (S4, fetta 1).

Rotte a sé, e non un campo della scheda dell'ingrediente (`IngredientDetailOut`): quella
la cambiano altri piani della stessa notte, e un campo obbligatorio in più costringerebbe
a riscrivere ogni oggetto di prova del frontend (spec §4.17). Il rifiuto è un 409 con
`code` e `detail`, la forma dei rifiuti dell'anagrafica: lo schermo lo legge con
`registryRefusal`.
"""

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import require_session
from app.domain.ciqual import CIQUAL_CITATION, CIQUAL_SOURCE
from app.domain.recipe_nutrition import PIECE_LABEL
from app.repositories.ciqual import search_foods
from app.schemas.nutrition import (
    CiqualFoodOut,
    GramsIn,
    IngredientNutritionOut,
    NutritionChoiceIn,
    RecipeNutritionOut,
    nutrient_rows,
    recipe_nutrition_out,
    weight_rows,
)
from app.services.ingredient_nutrition import (
    NutritionRefusal,
    NutritionState,
    NutritionView,
    choose_food,
    forget_choice,
    nutrition_of,
)
from app.services.recipe_nutrition import recipe_nutrition_of
from app.services.unit_grams import Weight, clear_grams, set_grams, weights_of

router = APIRouter(
    prefix="/api/v1/ingredients", tags=["nutrition"], dependencies=[Depends(require_session)]
)
ciqual_router = APIRouter(
    prefix="/api/v1/ciqual", tags=["nutrition"], dependencies=[Depends(require_session)]
)
recipe_router = APIRouter(
    prefix="/api/v1/recipes", tags=["nutrition"], dependencies=[Depends(require_session)]
)

_CONFLICT = {status.HTTP_409_CONFLICT: {"description": "rifiuto: `code` e `detail`"}}


def nutrition_out(view: NutritionView, weights: Sequence[Weight] = ()) -> IngredientNutritionOut:
    return IngredientNutritionOut(
        state=view.state.value,
        decided_by=view.decided_by,
        food=CiqualFoodOut.model_validate(view.food) if view.food is not None else None,
        nutrients=nutrient_rows(view.food.nutrients if view.food is not None else None),
        weights=weight_rows(weights),
        source=CIQUAL_SOURCE,
        citation=CIQUAL_CITATION,
    )


async def _full_out(session: AsyncSession, ingredient_id: uuid.UUID, view: NutritionView) -> IngredientNutritionOut:
    """La risposta intera: i valori e, per un alimento, i pesi delle sue coppie."""
    weights = [] if view.state == NutritionState.NON_FOOD else await weights_of(session, ingredient_id)
    return nutrition_out(view, weights)


def _pair_unit(unit: str) -> uuid.UUID | None:
    """`pezzo` è la coppia senza unità; ogni altra cosa dev'essere l'id di un'unità."""
    if unit == PIECE_LABEL:
        return None
    try:
        return uuid.UUID(unit)
    except ValueError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unità inesistente") from exc


def _refusal(exc: NutritionRefusal) -> JSONResponse:
    return JSONResponse(
        {"detail": exc.message, "code": exc.code}, status_code=status.HTTP_409_CONFLICT
    )


def _missing(exc: LookupError) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente")


@ciqual_router.get("/foods", response_model=list[CiqualFoodOut])
async def foods(
    q: str = Query(min_length=1, max_length=80),
    limit: int = Query(default=20, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> list[CiqualFoodOut]:
    return [CiqualFoodOut.model_validate(food) for food in await search_foods(session, q, limit)]


@router.get("/{ingredient_id}/nutrition", response_model=IngredientNutritionOut)
async def read_nutrition(
    ingredient_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> IngredientNutritionOut:
    try:
        return await _full_out(session, ingredient_id, await nutrition_of(session, ingredient_id))
    except LookupError as exc:
        raise _missing(exc) from exc


@router.put(
    "/{ingredient_id}/nutrition", response_model=IngredientNutritionOut, responses=_CONFLICT
)
async def choose_nutrition(
    ingredient_id: uuid.UUID,
    payload: NutritionChoiceIn,
    session: AsyncSession = Depends(get_session),
) -> IngredientNutritionOut | JSONResponse:
    try:
        view = await choose_food(session, ingredient_id, payload.ciqual_code)
    except LookupError as exc:
        await session.rollback()
        raise _missing(exc) from exc
    except NutritionRefusal as exc:
        await session.rollback()
        return _refusal(exc)
    out = await _full_out(session, ingredient_id, view)
    await session.commit()
    return out


@router.delete("/{ingredient_id}/nutrition", response_model=IngredientNutritionOut)
async def forget_nutrition(
    ingredient_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> IngredientNutritionOut:
    try:
        view = await forget_choice(session, ingredient_id)
    except LookupError as exc:
        await session.rollback()
        raise _missing(exc) from exc
    out = await _full_out(session, ingredient_id, view)
    await session.commit()
    return out


@router.put("/{ingredient_id}/unit-grams/{unit}", response_model=IngredientNutritionOut, responses=_CONFLICT)
async def write_grams(
    ingredient_id: uuid.UUID,
    unit: str,
    payload: GramsIn,
    session: AsyncSession = Depends(get_session),
) -> IngredientNutritionOut | JSONResponse:
    unit_id = _pair_unit(unit)
    try:
        await set_grams(session, ingredient_id, unit_id, payload.grams)
        out = await _full_out(session, ingredient_id, await nutrition_of(session, ingredient_id))
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente o unità inesistente") from exc
    except NutritionRefusal as exc:
        await session.rollback()
        return _refusal(exc)
    await session.commit()
    return out


@router.delete("/{ingredient_id}/unit-grams/{unit}", response_model=IngredientNutritionOut, responses=_CONFLICT)
async def forget_grams(
    ingredient_id: uuid.UUID, unit: str, session: AsyncSession = Depends(get_session)
) -> IngredientNutritionOut | JSONResponse:
    unit_id = _pair_unit(unit)
    try:
        await clear_grams(session, ingredient_id, unit_id)
        out = await _full_out(session, ingredient_id, await nutrition_of(session, ingredient_id))
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente o unità inesistente") from exc
    except NutritionRefusal as exc:
        await session.rollback()
        return _refusal(exc)
    await session.commit()
    return out


@recipe_router.get("/{recipe_id}/nutrition", response_model=RecipeNutritionOut)
async def read_recipe_nutrition(
    recipe_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> RecipeNutritionOut:
    try:
        result = await recipe_nutrition_of(session, recipe_id)
    except LookupError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ricetta inesistente") from exc
    return recipe_nutrition_out(result, CIQUAL_SOURCE)
