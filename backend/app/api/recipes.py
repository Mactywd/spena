import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session, is_missing_reference, is_unique_violation
from app.core.security import require_session
from app.db.models.recipe import Recipe
from app.domain.rules import (
    Availability,
    IngredientRole,
    is_cookable,
    is_satisfied,
    missing_count,
)
from app.repositories.pantry import availability_map
from app.repositories.recipes import create_recipe, get_recipe
from app.schemas.ai import DraftIngredientOut, DraftOut, DraftRequest
from app.schemas.recipe import (
    RecipeCreate,
    RecipeIngredientOut,
    RecipeOut,
    RecipeSummaryOut,
    SearchModeOut,
)
from app.services.ai_recipes import AiUnavailable, draft_recipe
from app.services.embeddings import (
    EmbeddingUnavailable,
    get_embedding_provider,
    log_degradation_once,
    recipe_document,
)
from app.services.recipe_search import search_recipes, semantic_search_usable

router = APIRouter(
    prefix="/api/v1/recipes", tags=["recipes"], dependencies=[Depends(require_session)]
)


async def _to_out(session: AsyncSession, recipe: Recipe) -> RecipeOut:
    ingredient_ids = [ri.ingredient_id for ri in recipe.ingredients]
    availability = await availability_map(session, ingredient_ids)

    lines: list[RecipeIngredientOut] = []
    requirements: list[tuple[IngredientRole, Availability]] = []
    for ri in recipe.ingredients:
        have = availability.get(ri.ingredient_id, Availability.MISSING)
        role = IngredientRole(ri.role)
        requirements.append((role, have))
        lines.append(
            RecipeIngredientOut(
                ingredient_id=ri.ingredient_id,
                ingredient_name=ri.ingredient.name,
                role=role,
                quantity_text=ri.quantity_text,
                note=ri.note,
                availability=have,
                satisfied=is_satisfied(role, have),
            )
        )
    # il conteggio e il verdetto arrivano da app/domain/rules.py, non da un `sum`
    # qui: ricalcolarli in linea fa sì che il test a tabella difenda una copia che
    # non gira, ed è la metà aggregata della regola del capitolo 7 della spec
    return RecipeOut(
        id=recipe.id, title=recipe.title, description=recipe.description,
        instructions=recipe.instructions, servings=recipe.servings, source=recipe.source,
        source_ref=recipe.source_ref, ingredients=lines,
        missing=missing_count(requirements), cookable=is_cookable(requirements),
        image_url=recipe.image_url, prep_minutes=recipe.prep_minutes,
        cook_minutes=recipe.cook_minutes, category=recipe.category,
    )


@router.get("/search", response_model=list[RecipeSummaryOut])
async def search(
    q: str | None = None,
    only_cookable: bool = False,
    category: str | None = None,
    limit: int = Query(default=30, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[RecipeSummaryOut]:
    results = await search_recipes(session, q, only_cookable, limit, category=category)
    return [
        RecipeSummaryOut(
            id=r.recipe.id, title=r.recipe.title, description=r.recipe.description,
            source=r.recipe.source, missing=r.missing, cookable=r.cookable,
            image_url=r.recipe.image_url, prep_minutes=r.recipe.prep_minutes,
            cook_minutes=r.recipe.cook_minutes, category=r.recipe.category,
        )
        for r in results
    ]


@router.get("/search-mode", response_model=SearchModeOut)
async def search_mode(session: AsyncSession = Depends(get_session)) -> SearchModeOut:
    """Dichiarata prima di `/{recipe_id}`, altrimenti la rotta col parametro la mangia.

    La sessione serve dalla terza condizione di `semantic_search_usable`: la risposta
    parla anche del ricettario, non solo del fornitore di vettori.
    """
    return SearchModeOut(semantic=await semantic_search_usable(session))


@router.get("/categories", response_model=list[str])
async def categories(session: AsyncSession = Depends(get_session)) -> list[str]:
    """Le categorie presenti nel ricettario, per il filtro.

    Solo quelle che esistono davvero: un filtro che offre voci vuote è un filtro che
    porta a una schermata vuota.
    """
    rows = await session.execute(
        select(Recipe.category)
        .where(Recipe.category.is_not(None))
        .distinct()
        .order_by(Recipe.category)
    )
    return list(rows.scalars())


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
    text = recipe_document(payload.title, payload.description)
    try:
        embedding = (await get_embedding_provider().embed_passages([text]))[0]
    except EmbeddingUnavailable as exc:
        embedding = None
        log_degradation_once(exc)

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
        # solo un duplicato è un "ripetuto": qualunque altra violazione è un difetto
        # nostro e deve restare visibile come 500, come in shopping.py e pantry.py
        if not is_unique_violation(exc):
            raise
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
