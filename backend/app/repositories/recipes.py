import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.recipe import Recipe, RecipeIngredient


async def create_recipe(
    session: AsyncSession,
    *,
    title: str,
    description: str | None,
    instructions: str,
    servings: int | None,
    source: str,
    source_ref: str | None,
    ingredients: list[tuple[uuid.UUID, str, str | None, str | None]],
    embedding: list[float] | None,
) -> Recipe:
    """`ingredients` è una lista di (ingredient_id, role, quantity_text, note)."""
    recipe = Recipe(
        title=title, description=description, instructions=instructions, servings=servings,
        source=source, source_ref=source_ref, embedding=embedding,
    )
    for ingredient_id, role, quantity_text, note in ingredients:
        recipe.ingredients.append(
            RecipeIngredient(
                ingredient_id=ingredient_id, role=role, quantity_text=quantity_text, note=note
            )
        )
    session.add(recipe)
    await session.flush()
    return recipe


async def get_recipe(session: AsyncSession, recipe_id: uuid.UUID) -> Recipe | None:
    statement = (
        select(Recipe)
        .options(selectinload(Recipe.ingredients).joinedload(RecipeIngredient.ingredient))
        .where(Recipe.id == recipe_id)
    )
    return (await session.execute(statement)).unique().scalar_one_or_none()
