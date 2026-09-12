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
from app.domain.rules import Availability, IngredientRole, is_cookable, missing_count
from app.repositories.pantry import availability_map
from app.services.embeddings import (
    EmbeddingUnavailable,
    get_embedding_provider,
    log_degradation_once,
)

RRF_K = 60
CANDIDATE_POOL = 100

# Soglia di distanza coseno oltre la quale un vicino non è un vicino. Senza, la
# ricerca vettoriale restituisce i primi CANDIDATE_POOL per distanza e basta: con 26
# ricette significa tutte, per qualunque query, e il ricettario risponde a una
# sciocchezza con l'intero catalogo.
#
# Il valore è misurato, non scelto: intfloat/multilingual-e5-small (il modello di
# default) sui 26 passaggi del seme v1, distanza del miglior risultato per query.
# Nove query pertinenti: 0,103–0,157 per la ricetta giusta. Sette query estranee
# («bulloni per impianto idraulico», «tassi di interesse ipotecari», «asdfgh qwerty»,
# «how to configure a kubernetes ingress», «il campionato di calcio di serie A»,
# «pneumatici invernali 205/55», «previsioni del tempo a Milano»): miglior risultato
# 0,174–0,252. 0,17 è il valore più stretto che tiene dentro la ricetta giusta di
# tutte e nove le query pertinenti (margine 0,014 sulla più lontana, «polpette» a
# 0,156) e lascia fuori tutte e sette le estranee; in più riduce il bacino da 26 a
# 1–14 ricette, che è il punto. A 0,16 «carbonara» e «polpette» perdono la ricetta
# giusta; a 0,20 tre query estranee ricominciano a pescare.
#
# Da rimisurare se cambia EMBEDDING_MODEL: la scala delle distanze è una proprietà
# del modello. L'errore è asimmetrico e mite in entrambe le direzioni: troppo
# stretta e la metà semantica si svuota, cioè la degradazione che la spec §11
# descrive già; troppo larga e si torna al catalogo intero, cioè a prima di questa riga.
SEMANTIC_MAX_DISTANCE = 0.17


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


SEMANTIC_PROBE = "prova"


async def semantic_search_available() -> bool:
    """Se un vettore si riesce davvero a calcolare, adesso, con questa configurazione.

    Passa dalla stessa funzione che usa la ricerca, quindi la risposta riguarda il
    percorso vero e non la configurazione dichiarata. Con il fornitore locale la
    prima chiamata carica il modello, che resta caricato (vedi embeddings.py): è un
    preriscaldamento, non uno spreco.
    """
    try:
        await _embed_query(SEMANTIC_PROBE)
    except EmbeddingUnavailable as exc:
        log_degradation_once(exc)
        return False
    return True


async def _semantic_ranking(session: AsyncSession, query: str) -> list[uuid.UUID]:
    try:
        vector = await _embed_query(query)
    except EmbeddingUnavailable as exc:
        # degradazione: resta la sola ricerca testuale, ma si deve sapere
        log_degradation_once(exc)
        return []
    distance = Recipe.embedding.cosine_distance(vector)
    statement = (
        select(Recipe.id)
        .where(Recipe.embedding.is_not(None), distance <= SEMANTIC_MAX_DISTANCE)
        .order_by(distance)
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


async def _requirements_by_recipe(
    session: AsyncSession, recipe_ids: list[uuid.UUID]
) -> dict[uuid.UUID, list[tuple[IngredientRole, Availability]]]:
    """Per ogni ricetta, le coppie (ruolo, disponibilità) su cui decidono le regole.

    Si ferma qui di proposito: il conteggio dei mancanti e il verdetto di
    cucinabilità sono le funzioni di app/domain/rules.py, non una somma ricopiata
    in questo modulo. Ricalcolarle in linea è la ragione per cui il test a tabella
    difendeva una copia che non girava.
    """
    requirements: dict[uuid.UUID, list[tuple[IngredientRole, Availability]]] = {
        recipe_id: [] for recipe_id in recipe_ids
    }
    if not recipe_ids:
        return requirements
    statement = select(
        RecipeIngredient.recipe_id, RecipeIngredient.ingredient_id, RecipeIngredient.role
    ).where(RecipeIngredient.recipe_id.in_(recipe_ids))
    rows = (await session.execute(statement)).all()

    availability = await availability_map(session, [row[1] for row in rows])
    for recipe_id, ingredient_id, role in rows:
        have = availability.get(ingredient_id, Availability.MISSING)
        requirements[recipe_id].append((IngredientRole(role), have))
    return requirements


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

    requirements = await _requirements_by_recipe(session, candidate_ids)
    recipes = {
        r.id: r
        for r in (
            await session.execute(select(Recipe).where(Recipe.id.in_(candidate_ids)))
        ).unique().scalars()
    }

    results = [
        RecipeSearchResult(
            recipe=recipes[recipe_id],
            missing=missing_count(requirements.get(recipe_id, [])),
            cookable=is_cookable(requirements.get(recipe_id, [])),
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
