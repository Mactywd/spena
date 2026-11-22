"""«Sostituisci» (R5): la risposta di una riga di ricetta, e quelle di un ingrediente.

Le regole stanno altrove — quale risposta vale per una riga e cosa conta come risposta
in `repositories/substitutions.py`, la domanda all'AI e la sua verifica in
`services/substitutions.py`, se un sostituto in dispensa basta in `domain/rules.py`
(`is_satisfied`, la stessa regola delle righe): qui si legge, si scrive e si risponde.

Dalla ricetta si scrive solo la correzione di quella ricetta; la voce generale si
scrive dalla scheda dell'ingrediente (spec §3.10).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import require_session
from app.db.models.ingredient import Ingredient
from app.db.models.recipe import Recipe, RecipeIngredient
from app.domain.rules import Availability, IngredientKind, IngredientRole, is_satisfied
from app.domain.substitutions import SubstitutionContext, SubstitutionVerdict, recipe_context
from app.repositories.pantry import availability_map
from app.repositories.substitutions import (
    Answer,
    SubstitutionRefused,
    checked_answer,
    delete_override,
    effective_row,
    ingredient_view,
    visible_options,
    write_general,
    write_override,
)
from app.schemas.substitution import (
    ContextSubstitutionOut,
    IngredientSubstitutionsOut,
    LineSubstituteOut,
    LineSubstitutionOut,
    SubstituteOut,
    SubstitutionIn,
)
from app.services.substitutions import decide_pair

recipe_router = APIRouter(
    prefix="/api/v1/recipes", tags=["substitutions"], dependencies=[Depends(require_session)]
)
ingredient_router = APIRouter(
    prefix="/api/v1/ingredients", tags=["substitutions"], dependencies=[Depends(require_session)]
)

LINE_GONE = "Questo ingrediente non è nella ricetta."


async def _line(
    session: AsyncSession, recipe_id: uuid.UUID, ingredient_id: uuid.UUID
) -> tuple[Recipe, RecipeIngredient]:
    recipe = await session.get(Recipe, recipe_id)
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ricetta inesistente")
    line = (
        await session.execute(
            select(RecipeIngredient).where(
                RecipeIngredient.recipe_id == recipe_id,
                RecipeIngredient.ingredient_id == ingredient_id,
            )
        )
    ).scalars().first()
    if line is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, LINE_GONE)
    return recipe, line


async def _line_out(
    session: AsyncSession, recipe: Recipe, line: RecipeIngredient, *, ai_failed: bool = False
) -> LineSubstitutionOut:
    context = recipe_context(recipe.category)
    row = await effective_row(session, recipe.id, line.ingredient_id, context)
    common = {
        "ingredient_id": line.ingredient_id,
        "ingredient_name": line.ingredient.name,
        "context": context,
        "ai_failed": ai_failed,
    }
    if row is None:
        return LineSubstitutionOut(
            **common, scope=None, verdict=None, decided_by=None, substitutes=[]
        )
    options = visible_options(row)
    have = await availability_map(session, [option.substitute_id for option in options])
    role = IngredientRole(line.role)
    substitutes = []
    for option in options:
        availability = have.get(option.substitute_id, Availability.MISSING)
        substitutes.append(
            LineSubstituteOut(
                ingredient_id=option.substitute_id,
                name=option.substitute.name,
                note=option.note,
                availability=availability,
                satisfied=is_satisfied(role, availability),
            )
        )
    return LineSubstitutionOut(
        **common,
        scope="recipe" if row.recipe_id is not None else "general",
        verdict=SubstitutionVerdict(row.verdict),
        decided_by=row.decided_by,
        substitutes=substitutes,
    )


async def _checked(
    session: AsyncSession, ingredient_id: uuid.UUID, payload: SubstitutionIn
) -> Answer:
    try:
        return await checked_answer(
            session,
            ingredient_id,
            payload.verdict,
            [(substitute.ingredient_id, substitute.note) for substitute in payload.substitutes],
        )
    except SubstitutionRefused as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.message) from exc


@recipe_router.get("/{recipe_id}/substitutes/{ingredient_id}", response_model=LineSubstitutionOut)
async def line_substitution(
    recipe_id: uuid.UUID, ingredient_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> LineSubstitutionOut:
    recipe, line = await _line(session, recipe_id, ingredient_id)
    return await _line_out(session, recipe, line)


@recipe_router.post(
    "/{recipe_id}/substitutes/{ingredient_id}/ask", response_model=LineSubstitutionOut
)
async def ask_line_substitution(
    recipe_id: uuid.UUID, ingredient_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> LineSubstitutionOut:
    """La voce generale della riga, chiesta all'AI sul momento se manca, e salvata.

    Mai un 503: l'AI che non risponde è `ai_failed`, e lo schermo offre la strada a mano.
    """
    recipe, line = await _line(session, recipe_id, ingredient_id)
    outcome = await decide_pair(session, line.ingredient_id, recipe_context(recipe.category))
    await session.commit()
    return await _line_out(session, recipe, line, ai_failed=outcome.failed)


@recipe_router.put("/{recipe_id}/substitutes/{ingredient_id}", response_model=LineSubstitutionOut)
async def correct_line_substitution(
    recipe_id: uuid.UUID,
    ingredient_id: uuid.UUID,
    payload: SubstitutionIn,
    session: AsyncSession = Depends(get_session),
) -> LineSubstitutionOut:
    """«Non va bene qui»: la correzione di questa ricetta, e solo di questa."""
    recipe, line = await _line(session, recipe_id, ingredient_id)
    answer = await _checked(session, line.ingredient_id, payload)
    await write_override(session, recipe.id, line.ingredient_id, answer)
    await session.commit()
    return await _line_out(session, recipe, line)


@recipe_router.delete(
    "/{recipe_id}/substitutes/{ingredient_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def reset_line_substitution(
    recipe_id: uuid.UUID, ingredient_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    """«Torna al suggerimento generale». Togliere quel che non c'è non è un errore."""
    recipe, line = await _line(session, recipe_id, ingredient_id)
    await delete_override(session, recipe.id, line.ingredient_id)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


async def _ingredient(session: AsyncSession, ingredient_id: uuid.UUID) -> Ingredient:
    ingredient = await session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente")
    return ingredient


async def _ingredient_out(
    session: AsyncSession, ingredient_id: uuid.UUID
) -> IngredientSubstitutionsOut:
    view = await ingredient_view(session, ingredient_id)
    contexts = []
    for item in view.contexts:
        row = item.row
        contexts.append(
            ContextSubstitutionOut(
                context=item.context,
                recipes=item.recipes,
                verdict=SubstitutionVerdict(row.verdict) if row is not None else None,
                decided_by=row.decided_by if row is not None else None,
                substitutes=[
                    SubstituteOut(
                        ingredient_id=option.substitute_id,
                        name=option.substitute.name,
                        note=option.note,
                    )
                    for option in (visible_options(row) if row is not None else [])
                ],
            )
        )
    return IngredientSubstitutionsOut(
        ingredient_id=ingredient_id, contexts=contexts, recipe_overrides=view.recipe_overrides
    )


@ingredient_router.get("/{ingredient_id}/substitutes", response_model=IngredientSubstitutionsOut)
async def ingredient_substitutions(
    ingredient_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> IngredientSubstitutionsOut:
    await _ingredient(session, ingredient_id)
    return await _ingredient_out(session, ingredient_id)


@ingredient_router.put(
    "/{ingredient_id}/substitutes/{context}", response_model=IngredientSubstitutionsOut
)
async def correct_ingredient_substitution(
    ingredient_id: uuid.UUID,
    context: SubstitutionContext,
    payload: SubstitutionIn,
    session: AsyncSession = Depends(get_session),
) -> IngredientSubstitutionsOut:
    """La voce generale, scritta a mano in Anagrafica: «Correggi», «Scrivi tu», e «Va
    bene così», che rimanda la risposta dell'AI com'è e la fa diventare `human`."""
    ingredient = await _ingredient(session, ingredient_id)
    if ingredient.kind != IngredientKind.FOOD:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"«{ingredient.display_name}» non è un alimento: non ha sostituti.",
        )
    answer = await _checked(session, ingredient_id, payload)
    await write_general(session, ingredient_id, context, answer)
    await session.commit()
    return await _ingredient_out(session, ingredient_id)
