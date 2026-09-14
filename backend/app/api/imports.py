"""Le rotte della revisione dell'import.

Una sola decisione per chiamata, e ogni decisione materializza subito le ricette che
aspettavano quel termine: il numero che torna — «sbloccate dodici ricette» — è ciò
che rende la revisione un lavoro con un risultato visibile invece di un modulo da
compilare.

Il riconoscimento con l'AI sta in una rotta separata dall'elenco di proposito: la coda
deve caricarsi subito, e un guasto del modello non deve poter svuotare una schermata
che funziona anche senza. Quella rotta applica, non propone: la revisione umana viene
dopo, dall'elenco «Deciso dall'AI», con un annullamento per ognuna.
"""

import uuid
from datetime import UTC, datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import require_session
from app.db.models.ingredient import Ingredient
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.imports import (
    counts,
    decided_terms,
    get_term,
    pending_terms,
    waiting_titles,
)
from app.repositories.ingredients import create_ingredient, remember_alias
from app.schemas.recipe_import import (
    DecideOut,
    DecideRequest,
    DecisionOut,
    ImportStatusOut,
    SuggestionOut,
    TermDecisionIn,
    TermOut,
    UndoOut,
    UndoRequest,
)
from app.services.ingredient_match import match_name
from app.services.llm import LlmUnavailable
from app.services.recipe_import.decide import decide_terms
from app.services.recipe_import.materialize import materialize_ready
from app.services.recipe_import.undo import CookedRecipesAffected, undo_decision

router = APIRouter(
    prefix="/api/v1/imports", tags=["imports"], dependencies=[Depends(require_session)]
)

# Quanti termini in un giro della rotta. Una chiamata a termine: il tetto è
# sull'attesa di chi ha premuto il bottone, non sulla correttezza.
MAX_TERMS_PER_CALL = 40


@router.get("/status", response_model=ImportStatusOut)
async def read_status(session: AsyncSession = Depends(get_session)) -> ImportStatusOut:
    numbers = await counts(session, GIALLOZAFFERANO)
    return ImportStatusOut(**vars(numbers))


@router.get("/terms", response_model=list[TermOut])
async def read_terms(
    limit: int = Query(default=20, le=50),
    decided_by: Literal["ai", "human", "auto"] | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[TermOut]:
    """Senza `decided_by`, la coda da decidere. Con, l'elenco di chi l'ha già deciso.

    Una rotta e una forma sola: due rotte con due schemi quasi uguali si scollano, e
    la prima cosa a scollarsi sarebbe il campo che dice cosa è stato deciso.
    """
    if decided_by is not None:
        terms = await decided_terms(session, GIALLOZAFFERANO, decided_by, limit=limit)
        return [
            TermOut(
                id=term.id, display_name=term.display_name, occurrences=term.occurrences,
                suggestion=None, waiting_titles=[], decided_by=term.decided_by,
                decided_action=_decided_action(term),
                decided_name=await _ingredient_name(session, term.ingredient_id),
            )
            for term in terms
        ]

    terms = await pending_terms(session, GIALLOZAFFERANO, limit=limit)
    titles = await waiting_titles(
        session, GIALLOZAFFERANO, [term.term_key for term in terms]
    )

    out: list[TermOut] = []
    for term in terms:
        match = await match_name(session, term.display_name)
        suggestion = (
            SuggestionOut(
                ingredient_id=match.ingredient_id, name=match.name, certain=match.certain
            )
            if match.ingredient_id is not None and match.name is not None
            else None
        )
        out.append(
            TermOut(
                id=term.id, display_name=term.display_name, occurrences=term.occurrences,
                suggestion=suggestion, waiting_titles=titles.get(term.term_key, []),
            )
        )
    return out


def _decided_action(term: ImportTerm) -> str | None:
    """«map» o «creato» non si distinguono, e non è una lacuna che si può colmare qui.

    `import_terms` non registra se la decisione ha creato l'ingrediente o ne ha usato
    uno già in anagrafica: quel fatto esiste solo nell'istante di `decide_terms`
    (o della decisione umana) e non è mai scritto da nessuna parte. Distinguerlo
    vorrebbe una colonna, e questo piano vieta ogni migrazione — quindi la
    distinzione non si calcola, si rinuncia a promettere di poterla fare.

    Non è nemmeno vero che si possa dedurre da un fatto già scritto. Sembra che si
    possa: «un ingrediente il cui unico alias dell'import è il nome di questo
    termine è nato con questa decisione». Non regge. «Rigatoni» che diventa un `map`
    su «pasta», ingrediente esistente da prima, scrive comunque l'alias `rigatoni`
    con `source="import"` (vedi `decide_terms`): se quello è l'unico alias «import»
    di pasta, la deduzione chiamerebbe «creato» un ingrediente che esisteva già.
    L'alias non distingue le due storie, perché entrambe lo scrivono allo stesso
    modo.

    Il valore che segue, quindi, è "map" per ogni decisione che punta a un
    ingrediente — creato o già esistente che sia — e "ignored" per chi non tiene
    l'ingrediente in dispensa. Chi deve sapere se un annullamento cancellerà un
    ingrediente lo scopre da cosa fa `undo_decision`, non da questa etichetta.
    """
    if term.decision == TermDecision.IGNORED:
        return "ignored"
    if term.decision == TermDecision.MAPPED:
        return "map"
    return None


async def _ingredient_name(
    session: AsyncSession, ingredient_id: uuid.UUID | None
) -> str | None:
    if ingredient_id is None:
        return None
    ingredient = await session.get(Ingredient, ingredient_id)
    return ingredient.name if ingredient is not None else None


@router.post("/terms/decide", response_model=DecideOut)
async def decide_with_ai(
    payload: DecideRequest, session: AsyncSession = Depends(get_session)
) -> DecideOut:
    """Fa decidere all'AI i termini in coda, e applica.

    Non torna proposte da confermare: le decisioni si applicano, con `decided_by="ai"`,
    e si rivedono dall'elenco «Deciso dall'AI» con un annullamento per ognuna. Un
    termine la cui risposta non passa la verifica resta in coda, e la coda manuale è
    identica a prima.
    """
    if payload.term_ids is not None:
        # `term_ids` accetta fino a 200 id (vedi lo schema): senza un limite qui, un
        # chiamante che ne manda 200 spende 200 chiamate al modello a pagamento in una
        # sola richiesta. Lo stesso `MAX_TERMS_PER_CALL` del ramo «tutti i pendenti».
        rows = await session.execute(
            select(ImportTerm).where(
                ImportTerm.id.in_(payload.term_ids),
                ImportTerm.decision == TermDecision.PENDING,
                ImportTerm.source == GIALLOZAFFERANO,
            ).limit(MAX_TERMS_PER_CALL)
        )
        terms = list(rows.scalars())
    else:
        terms = await pending_terms(session, GIALLOZAFFERANO, limit=MAX_TERMS_PER_CALL)

    try:
        outcome = await decide_terms(session, terms)
    except LlmUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"il riconoscimento non è disponibile ({exc}): decidi a mano, la coda funziona.",
        ) from exc

    materialized = await materialize_ready(session, GIALLOZAFFERANO)
    numbers = await counts(session, GIALLOZAFFERANO)
    await session.commit()
    return DecideOut(
        applied=outcome.applied, created=outcome.created, ignored=outcome.ignored,
        still_pending=outcome.still_pending, unlocked=materialized.created,
        remaining_terms=numbers.pending_terms,
    )


@router.post("/terms/{term_id}/decision", response_model=DecisionOut)
async def decide(
    term_id: uuid.UUID,
    payload: TermDecisionIn,
    session: AsyncSession = Depends(get_session),
) -> DecisionOut:
    term = await get_term(session, term_id)
    if term is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "termine inesistente")

    if payload.action == "ignore":
        term.decision = TermDecision.IGNORED
        term.ingredient_id = None
    else:
        if payload.action == "map":
            if payload.ingredient_id is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "per collegare serve l'ingrediente",
                )
            ingredient = await session.get(Ingredient, payload.ingredient_id)
            if ingredient is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente")
        else:
            if not payload.name or payload.category is None:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY,
                    "per creare un ingrediente servono nome e categoria",
                )
            existing = (
                await session.execute(
                    select(Ingredient).where(Ingredient.name == payload.name.strip().lower())
                )
            ).scalars().first()
            if existing is not None:
                raise HTTPException(
                    status.HTTP_409_CONFLICT,
                    f"«{existing.name}» è già in anagrafica: collega il termine invece "
                    "di creare un doppione.",
                )
            ingredient = await create_ingredient(
                session, name=payload.name,
                display_name=payload.display_name or payload.name,
                category=payload.category,
            )

        term.decision = TermDecision.MAPPED
        term.ingredient_id = ingredient.id
        await remember_alias(session, ingredient.id, term.display_name)

    term.role_override = payload.role_override
    term.decided_by = "human"
    term.decided_at = datetime.now(UTC)
    await session.flush()

    materialized = await materialize_ready(session, GIALLOZAFFERANO)
    numbers = await counts(session, GIALLOZAFFERANO)
    await session.commit()
    return DecisionOut(unlocked=materialized.created, remaining_terms=numbers.pending_terms)


@router.post("/terms/{term_id}/undo", response_model=UndoOut)
async def undo(
    term_id: uuid.UUID,
    payload: UndoRequest,
    session: AsyncSession = Depends(get_session),
) -> UndoOut:
    """Rimette un termine deciso in coda, e con lui il mondo che quella decisione ha mosso.

    Non è un editor: dopo questo, il termine si decide a mano con la scheda di sempre.
    """
    term = await get_term(session, term_id)
    if term is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "termine inesistente")
    if term.decision == TermDecision.PENDING:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"«{term.display_name}» è già in coda: non c'è nessuna decisione da disfare.",
        )

    try:
        undone = await undo_decision(session, term, force=payload.force)
    except CookedRecipesAffected as exc:
        # `undo_decision` controlla la ricetta cucinata e lancia prima di qualunque
        # mutazione, così non c'è niente da annullare. Inoltre, `get_session()` avvolge
        # la sessione con `async with`, che la chiude e scarta ogni mutazione: questo ramo
        # non arriva mai a `commit()`.
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{exc.count} di queste ricette le hai già cucinate: rifacendole lo storico "
            "resta ma perde il collegamento. Conferma per procedere.",
        ) from exc

    numbers = await counts(session, GIALLOZAFFERANO)
    await session.commit()
    return UndoOut(
        recipes_requeued=undone.recipes_requeued,
        ingredient_deleted=undone.ingredient_deleted,
        remaining_terms=numbers.pending_terms,
    )
