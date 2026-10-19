"""I nutrienti di una ricetta, letti dal database (S4, fetta 2).

Una query per le righe — con l'unità canonica, l'alimento CIQUAL scelto e i suoi valori —
e una per i pesi delle coppie; poi la funzione pura (`app/domain/recipe_nutrition.py`),
che decide cosa si conta e cosa no. È ciò che P1 e P2 leggeranno.
"""

import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.models.ingredient import Ingredient
from app.db.models.nutrition import CiqualFood, IngredientNutrition
from app.db.models.recipe import Recipe, RecipeIngredient
from app.db.models.unit import Unit
from app.domain.recipe_nutrition import NutritionLine, RecipeNutrition, classify_unit, recipe_nutrition
from app.services.unit_grams import decided_grams


async def nutrition_lines(
    session: AsyncSession, recipe_id: uuid.UUID
) -> tuple[int | None, list[NutritionLine]]:
    recipe = await session.get(Recipe, recipe_id)
    if recipe is None:
        raise LookupError(f"nessuna ricetta {recipe_id}")
    seen = aliased(Unit)
    canonical = aliased(Unit)
    rows = (
        await session.execute(
            select(
                RecipeIngredient.ingredient_id,
                Ingredient.name.label("ingredient_name"),
                RecipeIngredient.quantity_text,
                RecipeIngredient.quantity_value,
                canonical.id.label("unit_id"),
                canonical.key.label("unit_key"),
                canonical.singular.label("unit_singular"),
                IngredientNutrition.ciqual_code,
                CiqualFood.nutrients,
            )
            .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
            .outerjoin(seen, seen.id == RecipeIngredient.quantity_unit_id)
            .outerjoin(canonical, canonical.id == func.coalesce(seen.canonical_id, seen.id))
            .outerjoin(IngredientNutrition, IngredientNutrition.ingredient_id == RecipeIngredient.ingredient_id)
            .outerjoin(CiqualFood, CiqualFood.code == IngredientNutrition.ciqual_code)
            .where(RecipeIngredient.recipe_id == recipe_id)
            .order_by(Ingredient.name)
        )
    ).all()
    grams = await decided_grams(session, [row.ingredient_id for row in rows])
    lines = []
    for row in rows:
        kind = classify_unit(row.unit_key, row.unit_singular)
        pair_grams = None
        if kind.measure == "pair":
            pair_unit = None if kind.piece else row.unit_id
            pair_grams = grams.get((row.ingredient_id, pair_unit), (None, None))[0]
        lines.append(
            NutritionLine(
                ingredient_id=row.ingredient_id,
                ingredient_name=row.ingredient_name,
                quantity_text=row.quantity_text,
                value=row.quantity_value,
                unit_key=row.unit_key,
                unit_singular=row.unit_singular,
                pair_grams=pair_grams,
                # «nessun alimento adatto» (codice NULL) e «da decidere» sono la stessa
                # cosa per il conto: la riga non ha valori
                per_100g=row.nutrients if row.ciqual_code is not None else None,
            )
        )
    return recipe.servings, lines


async def recipe_nutrition_of(session: AsyncSession, recipe_id: uuid.UUID) -> RecipeNutrition:
    servings, lines = await nutrition_lines(session, recipe_id)
    return recipe_nutrition(lines, servings)
