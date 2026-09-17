"""Ricerca ibrida sul ricettario.

Due graduatorie indipendenti, una semantica e una testuale, fuse con
Reciprocal Rank Fusion. Il numero di ingredienti mancanti interviene dopo, come
riordinamento: non nasconde nulla, perché una ricetta a cui manca una sola cosa
è un'informazione che vuoi vedere.
"""

import asyncio
import logging
import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.recipe import Recipe, RecipeIngredient
from app.domain.rules import Availability, IngredientRole, is_cookable, missing_count
from app.repositories.pantry import availability_map
from app.services.embeddings import (
    EmbeddingUnavailable,
    get_embedding_provider,
    log_degradation_once,
)

logger = logging.getLogger(__name__)

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

# Il modello su cui la misurazione qui sopra è stata fatta. La coppia
# (soglia, modello) è una cosa sola, e finora stava insieme solo in un commento:
# chi cambia EMBEDDING_MODEL lo fa in `.env`, dove la soglia non è nominata.
SEMANTIC_DISTANCE_MEASURED_ON = "intfloat/multilingual-e5-small"

# La scelta, quando il modello configurato non è quello misurato: si rinuncia alla
# metà semantica invece di applicarle la soglia comunque.
#
# Applicarla sarebbe una supposizione, e sbaglia in silenzio in entrambi i versi. Su
# un modello a scala più larga `_semantic_ranking` restituisce sempre `[]`: la
# ricerca è solo testuale mentre `/recipes/search-mode` continua a dire
# `semantic: true`, perché il vettore si calcola benissimo — cioè esattamente il
# degrado invisibile che la spec §11 vuole visibile. Su un modello a scala più
# stretta torna il ricettario intero per qualunque sciocchezza, cioè il difetto che
# la soglia esiste per chiudere. Rinunciare, invece, è la degradazione già prevista:
# si vede nei log, si vede nella riga grigia del ricettario, e nessuna delle due
# risposte è una bugia. Il costo per tornare indietro è una costante rimisurata, ed
# è un lavoro che solo una misurazione può fare.
SEMANTIC_OFF_MODEL = (
    "ricerca semantica non disponibile: EMBEDDING_MODEL è %r, ma SEMANTIC_MAX_DISTANCE "
    "(%s) è misurata su %r e la scala delle distanze è una proprietà del modello. Il "
    "ricettario resta sulla sola ricerca testuale. Per riaccenderla: rimisura la soglia "
    "in app/services/recipe_search.py per il modello nuovo, oppure rimetti %r in .env."
)

# Una volta per processo, per la stessa ragione di log_degradation_once: un avviso a
# ogni ricerca è rumore, e il rumore non lo legge nessuno.
_model_mismatch_logged = False

# Quanto si aspetta un vettore prima di considerare la ricerca semantica non pronta.
# Con il fornitore locale il primo calcolo scarica il modello (~500 MB) e solo dopo
# risponde, mentre Nginx davanti al backend chiude a 60 s (frontend/nginx.conf non
# imposta proxy_read_timeout, quindi vale il default): senza questo limite il primo
# ingresso nella scheda Ricette — che interroga /recipes/search-mode, cioè fa partire
# il download — resta appeso e finisce in «Non sono riuscito a cercare nel
# ricettario», che è un guasto apparente mentre dietro va tutto bene. Con il limite
# la prima visita degrada alla ricerca testuale e quella dopo il download trova il
# modello caricato: il thread che sta scaricando non viene fermato da questa scadenza
# (asyncio.wait_for annulla l'attesa, non il lavoro dentro asyncio.to_thread).
EMBED_TIMEOUT_SECONDS = 5.0


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


async def _embed_query_in_time(query: str) -> list[float]:
    """Il vettore, o EmbeddingUnavailable entro EMBED_TIMEOUT_SECONDS."""
    try:
        return await asyncio.wait_for(_embed_query(query), EMBED_TIMEOUT_SECONDS)
    except TimeoutError as exc:
        raise EmbeddingUnavailable(
            f"nessun vettore entro {EMBED_TIMEOUT_SECONDS:g} s: il modello "
            "probabilmente si sta ancora scaricando o caricando"
        ) from exc


def _wrong_model_for_the_threshold() -> str | None:
    """Il modello configurato, se non è quello su cui la soglia è misurata.

    Logga una volta per processo: chi cambia EMBEDDING_MODEL non ha nessun altro
    posto in cui scoprire che la soglia non vale più per lui.
    """
    global _model_mismatch_logged
    configured = get_settings().embedding_model
    if configured == SEMANTIC_DISTANCE_MEASURED_ON:
        return None
    if not _model_mismatch_logged:
        _model_mismatch_logged = True
        logger.warning(
            SEMANTIC_OFF_MODEL,
            configured,
            SEMANTIC_MAX_DISTANCE,
            SEMANTIC_DISTANCE_MEASURED_ON,
            SEMANTIC_DISTANCE_MEASURED_ON,
        )
    return configured


SEMANTIC_PROBE = "prova"


async def semantic_search_usable(session: AsyncSession) -> bool:
    """Se la ricerca semantica serve davvero a qualcosa, adesso, su questo ricettario.

    Tre condizioni, e tutte e tre devono valere perché la risposta descriva ciò che
    l'utente sperimenta cercando:

    1. la soglia vale per il modello configurato (vedi SEMANTIC_OFF_MODEL);
    2. un vettore si riesce a calcolare, passando dalla stessa funzione che usa la
       ricerca — quindi è il percorso vero e non la configurazione dichiarata. Con il
       fornitore locale la prima chiamata carica il modello, che resta caricato (vedi
       embeddings.py): è un preriscaldamento, non uno spreco;
    3. esiste almeno una ricetta con un vettore. Senza questa terza condizione la
       rotta descriveva il fornitore e non il ricettario, e le due cose divergono
       proprio sul percorso che il README racconta: accendere INSTALL_EMBEDDINGS=1
       dopo aver seminato lascia le 26 ricette del seme con `embedding` a NULL (il
       seme è idempotente e non le riscrive). L'avviso spariva dallo schermo mentre
       la metà semantica restava vuota su tutto il ricettario tranne le ricette
       scritte dopo.
    """
    if _wrong_model_for_the_threshold() is not None:
        return False
    try:
        await _embed_query_in_time(SEMANTIC_PROBE)
    except EmbeddingUnavailable as exc:
        log_degradation_once(exc)
        return False
    return await _any_recipe_has_a_vector(session)


async def _any_recipe_has_a_vector(session: AsyncSession) -> bool:
    statement = select(Recipe.id).where(Recipe.embedding.is_not(None)).limit(1)
    return await session.scalar(statement) is not None


async def _semantic_ranking(session: AsyncSession, query: str) -> list[uuid.UUID]:
    if _wrong_model_for_the_threshold() is not None:
        # la soglia non vale per questo modello: filtrare con un numero misurato su
        # un altro è una supposizione, e qui si preferisce la sola ricerca testuale
        return []
    try:
        vector = await _embed_query_in_time(query)
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


def _containing_all(statement, ingredient_ids: list[uuid.UUID]):
    """«Contiene questi ingredienti»: tutti quanti, in qualunque ruolo.

    La congiunzione è il punto del filtro al plurale: un EXISTS per ciascun
    ingrediente, in AND, così ogni ingrediente aggiunto restringe. Con l'OR il
    secondo tocco allargherebbe l'elenco, cioè farebbe il contrario di quel che il
    gesto promette.

    Un EXISTS e non una join: la join moltiplicherebbe le righe per ogni
    ingrediente corrispondente, e il limite più avanti conterebbe righe invece di
    ricette.

    Il ruolo non entra, e fino al 2026-09-17 entrava. La ragione di allora era buona
    per la domanda di allora: il filtro si chiamava «cosa hai in casa», cioè «ho
    questo, cosa ci faccio», e lì un secondario non caratterizza il piatto — col sale
    avrebbe risposto «tutto», che non è una risposta. La domanda di oggi è un'altra e
    si combina: chi vuole restringere aggiunge il secondo ingrediente, e nascondergli
    una ricetta che quell'ingrediente ce l'ha davvero sarebbe una risposta sbagliata,
    non una prudenza. La regola primario/secondario resta intera dove serve, cioè
    nel decidere se una ricetta si può cucinare (`domain/rules.py`).
    """
    for ingredient_id in ingredient_ids:
        statement = statement.where(
            select(RecipeIngredient.recipe_id)
            .where(
                RecipeIngredient.recipe_id == Recipe.id,
                RecipeIngredient.ingredient_id == ingredient_id,
            )
            .exists()
        )
    return statement


async def search_recipes(
    session: AsyncSession,
    query: str | None = None,
    only_cookable: bool = False,
    limit: int = 30,
    category: str | None = None,
    ingredient_ids: list[uuid.UUID] | None = None,
) -> list[RecipeSearchResult]:
    if query and query.strip():
        semantic = await _semantic_ranking(session, query)
        textual = await _textual_ranking(session, query)
        fused = reciprocal_rank_fusion([semantic, textual])
        candidate_ids = list(fused)
    else:
        # `Recipe.id.desc()` come secondo criterio: un import in blocco scrive
        # centinaia di righe nella stessa transazione, quindi con lo stesso
        # `created_at` (vedi il commento sopra CANDIDATE_POOL). Senza un secondo
        # criterio `ORDER BY created_at DESC` non ha modo di spareggiare, e quali
        # cento righe (e in che ordine) finiscono nella piscina non è definito:
        # due richieste identiche potrebbero vedere ricettari diversi.
        statement = select(Recipe.id).order_by(Recipe.created_at.desc(), Recipe.id.desc())
        if category is not None:
            statement = statement.where(Recipe.category == category)
        if ingredient_ids:
            statement = _containing_all(statement, ingredient_ids)
        # Senza `only_cookable` la piscina basta: è uno scorrimento, e cento ricette
        # recenti sono più di quante se ne guardino. Con `only_cookable` no: il
        # filtro lavora sul risultato, quindi limitare prima significa filtrare
        # dentro un campione, e «cosa posso cucinare» risponderebbe guardando solo
        # le ricette entrate ieri. Misurato: a cinquecento ricette la passata
        # completa non si distingue; oltre qualche migliaio va misurata di nuovo, e
        # se non regge la regola scende in SQL.
        if not only_cookable:
            statement = statement.limit(CANDIDATE_POOL)
        candidate_ids = list((await session.execute(statement)).scalars())
        fused = {recipe_id: 0.0 for recipe_id in candidate_ids}

    if not candidate_ids:
        return []

    requirements = await _requirements_by_recipe(session, candidate_ids)
    recipe_statement = select(Recipe).where(Recipe.id.in_(candidate_ids))
    if category is not None:
        # vale anche sul percorso con le parole cercate: lì i candidati arrivano dal
        # riordino, e far cadere fuori i fuori-categoria qui costa zero query
        recipe_statement = recipe_statement.where(Recipe.category == category)
    if ingredient_ids:
        # vale anche quando i candidati arrivano dal riordino: far cadere fuori chi
        # non li ha tutti costa zero query.
        #
        # Qui sta il limite, scritto dove esiste. Sul ramo senza parole cercate il
        # filtro è già in SQL prima della piscina (vedi `_containing_all` sopra) e
        # vede tutto il ricettario. Su QUESTO ramo no: i candidati sono al massimo i
        # primi CANDIDATE_POOL di ciascuna graduatoria, e il filtro lavora dentro
        # quel campione — una ricetta che contiene il pomodoro ma non entra nella
        # piscina delle parole cercate non compare.
        #
        # Si accetta perché le parole cercate sono già un ordinamento: «fra le
        # ricette che parlano di questo, quelle che contengono anche il pomodoro» è
        # una domanda sul risultato della ricerca, non sul ricettario intero — non è
        # il caso della sesta lezione di CLAUDE.md, dove il filtro era l'unico
        # criterio e la piscina un taglio arbitrario. Ma è una scelta, non un fatto
        # provato: nessun test ha più ricette pertinenti di CANDIDATE_POOL, quindi
        # nessuno vedrebbe il giorno in cui smettesse di andare bene. Il filtro al
        # plurale stringe più di quello singolo, quindi il caso è semmai meno
        # frequente di prima, non di più. Se il ricettario cresce, è questo il punto
        # da rimisurare.
        recipe_statement = _containing_all(recipe_statement, ingredient_ids)
    recipes = {
        r.id: r
        for r in (await session.execute(recipe_statement)).unique().scalars()
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
