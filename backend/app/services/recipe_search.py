"""Ricerca ibrida sul ricettario.

Due graduatorie indipendenti, una semantica e una testuale, fuse con
Reciprocal Rank Fusion. Il numero di ingredienti mancanti interviene dopo, come
riordinamento: non nasconde nulla, perché una ricetta a cui manca una sola cosa
è un'informazione che vuoi vedere.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.recipe import Recipe, RecipeIngredient
from app.domain.rules import Availability, IngredientRole, is_satisfied
from app.repositories.pantry import availability_map
from app.services.embeddings import EmbeddingUnavailable, get_embedding_provider

RRF_K = 60
CANDIDATE_POOL = 100


@dataclass
class RecipeSearchResult:
    recipe: Recipe
    missing: int
    cookable: bool
    score: float


def reciprocal_rank_fusion(
    rankings: list[list[uuid.UUID]], k: int = RRF_K
) -> dict[uuid.UUID, float]:
    """Premia ciò su cui le due graduatorie sono d'accordo.

    La costante k smorza il vantaggio delle prime posizioni, così un secondo
    posto in entrambe le liste batte un primo posto in una sola.
    """
    scores: dict[uuid.UUID, float] = {}
    for ranking in rankings:
        for position, recipe_id in enumerate(ranking, start=1):
            scores[recipe_id] = scores.get(recipe_id, 0.0) + 1.0 / (k + position)
    return scores


async def _embed_query(query: str) -> list[float]:
    """Isolato in una funzione per poter essere sostituito nei test."""
    return await get_embedding_provider().embed_query(query)


async def _semantic_ranking(session: AsyncSession, query: str) -> list[uuid.UUID]:
    try:
        vector = await _embed_query(query)
    except EmbeddingUnavailable:
        return []  # degradazione: resta la sola ricerca testuale
    statement = (
        select(Recipe.id)
        .where(Recipe.embedding.is_not(None))
        .order_by(Recipe.embedding.cosine_distance(vector))
        .limit(CANDIDATE_POOL)
    )
    return list((await session.execute(statement)).scalars())


async def _textual_ranking(session: AsyncSession, query: str) -> list[uuid.UUID]:
    ts_query = func.plainto_tsquery("italian", query)
    statement = (
        select(Recipe.id)
        .where(Recipe.search_tsv.op("@@")(ts_query))
        .order_by(func.ts_rank(Recipe.search_tsv, ts_query).desc())
        .limit(CANDIDATE_POOL)
    )
    return list((await session.execute(statement)).scalars())


async def _missing_by_recipe(
    session: AsyncSession, recipe_ids: list[uuid.UUID]
) -> dict[uuid.UUID, int]:
    if not recipe_ids:
        return {}
    statement = select(
        RecipeIngredient.recipe_id, RecipeIngredient.ingredient_id, RecipeIngredient.role
    ).where(RecipeIngredient.recipe_id.in_(recipe_ids))
    rows = (await session.execute(statement)).all()

    availability = await availability_map(session, [row[1] for row in rows])
    missing = {recipe_id: 0 for recipe_id in recipe_ids}
    for recipe_id, ingredient_id, role in rows:
        have = availability.get(ingredient_id, Availability.MISSING)
        if not is_satisfied(IngredientRole(role), have):
            missing[recipe_id] += 1
    return missing


async def search_recipes(
    session: AsyncSession,
    query: str | None = None,
    only_cookable: bool = False,
    limit: int = 30,
) -> list[RecipeSearchResult]:
    if query and query.strip():
        semantic = await _semantic_ranking(session, query)
        textual = await _textual_ranking(session, query)
        fused = reciprocal_rank_fusion([semantic, textual])
        candidate_ids = list(fused)
    else:
        statement = select(Recipe.id).order_by(Recipe.created_at.desc()).limit(CANDIDATE_POOL)
        candidate_ids = list((await session.execute(statement)).scalars())
        fused = {recipe_id: 0.0 for recipe_id in candidate_ids}

    if not candidate_ids:
        return []

    missing = await _missing_by_recipe(session, candidate_ids)
    recipes = {
        r.id: r
        for r in (
            await session.execute(select(Recipe).where(Recipe.id.in_(candidate_ids)))
        ).unique().scalars()
    }

    results = [
        RecipeSearchResult(
            recipe=recipes[recipe_id],
            missing=missing.get(recipe_id, 0),
            cookable=missing.get(recipe_id, 0) == 0,
            score=fused.get(recipe_id, 0.0),
        )
        for recipe_id in candidate_ids
        if recipe_id in recipes
    ]
    if only_cookable:
        results = [r for r in results if r.cookable]

    # prima ciò che puoi davvero cucinare, poi la pertinenza
    results.sort(key=lambda r: (r.missing, -r.score, r.recipe.title))
    return results[:limit]
