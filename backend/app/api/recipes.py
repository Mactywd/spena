import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session, is_missing_reference
from app.core.security import require_session
from app.db.models.recipe import Recipe
from app.domain.rules import Availability, IngredientRole, is_satisfied
from app.repositories.pantry import availability_map
from app.repositories.recipes import create_recipe, get_recipe
from app.schemas.ai import DraftIngredientOut, DraftOut, DraftRequest
from app.schemas.recipe import RecipeCreate, RecipeIngredientOut, RecipeOut, RecipeSummaryOut
from app.services.ai_recipes import AiUnavailable, draft_recipe
from app.services.embeddings import EmbeddingUnavailable, get_embedding_provider
from app.services.recipe_search import search_recipes

router = APIRouter(
    prefix="/api/v1/recipes", tags=["recipes"], dependencies=[Depends(require_session)]
)


async def _to_out(session: AsyncSession, recipe: Recipe) -> RecipeOut:
    ingredient_ids = [ri.ingredient_id for ri in recipe.ingredients]
    availability = await availability_map(session, ingredient_ids)

    lines: list[RecipeIngredientOut] = []
    for ri in recipe.ingredients:
        have = availability.get(ri.ingredient_id, Availability.MISSING)
        lines.append(
            RecipeIngredientOut(
                ingredient_id=ri.ingredient_id,
                ingredient_name=ri.ingredient.name,
                role=IngredientRole(ri.role),
                quantity_text=ri.quantity_text,
                note=ri.note,
                availability=have,
                satisfied=is_satisfied(IngredientRole(ri.role), have),
            )
        )
    missing = sum(1 for line in lines if not line.satisfied)
    return RecipeOut(
        id=recipe.id, title=recipe.title, description=recipe.description,
        instructions=recipe.instructions, servings=recipe.servings, source=recipe.source,
        source_ref=recipe.source_ref, ingredients=lines, missing=missing, cookable=missing == 0,
    )


@router.get("/search", response_model=list[RecipeSummaryOut])
async def search(
    q: str | None = None,
    only_cookable: bool = False,
    limit: int = Query(default=30, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[RecipeSummaryOut]:
    results = await search_recipes(session, q, only_cookable, limit)
    return [
        RecipeSummaryOut(
            id=r.recipe.id, title=r.recipe.title, description=r.recipe.description,
            source=r.recipe.source, missing=r.missing, cookable=r.cookable,
        )
        for r in results
    ]


@router.get("/{recipe_id}", response_model=RecipeOut)
async def detail(
    recipe_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> RecipeOut:
    recipe = await get_recipe(session, recipe_id)
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ricetta inesistente")
    return await _to_out(session, recipe)


@router.post("", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
async def create(
    payload: RecipeCreate, session: AsyncSession = Depends(get_session)
) -> RecipeOut:
    """L'embedding è un ornamento: se il modello non c'è, la ricetta si salva comunque."""
    text = f"{payload.title}. {payload.description or ''}"
    try:
        embedding = (await get_embedding_provider().embed_passages([text]))[0]
    except EmbeddingUnavailable:
        embedding = None

    try:
        recipe = await create_recipe(
            session, title=payload.title, description=payload.description,
            instructions=payload.instructions, servings=payload.servings,
            source=payload.source, source_ref=payload.source_ref,
            ingredients=[
                (i.ingredient_id, i.role, i.quantity_text, i.note) for i in payload.ingredients
            ],
            embedding=embedding,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        if is_missing_reference(exc):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente") from exc
        raise HTTPException(
            status.HTTP_409_CONFLICT, "ingrediente ripetuto nella ricetta"
        ) from exc
    stored = await get_recipe(session, recipe.id)
    return await _to_out(session, stored)


@router.post("/ai-draft", response_model=DraftOut)
async def ai_draft(
    payload: DraftRequest, session: AsyncSession = Depends(get_session)
) -> DraftOut:
    """Propone, non salva. Il salvataggio passa da POST /recipes come le altre."""
    try:
        draft = await draft_recipe(session, payload.prompt)
    except AiUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"stesura AI non disponibile: {exc}"
        ) from exc
    return DraftOut(
        title=draft.title, description=draft.description, instructions=draft.instructions,
        servings=draft.servings,
        ingredients=[DraftIngredientOut(**vars(i)) for i in draft.ingredients],
    )
