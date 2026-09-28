"""Le rotte della revisione dell'import.

Una sola decisione per chiamata, e ogni decisione materializza subito le ricette che
aspettavano quel termine: il numero che torna — «sbloccate dodici ricette» — è ciò
che rende la revisione un lavoro con un risultato visibile invece di un modulo da
compilare.

Il riconoscimento con l'AI sta in una rotta separata dall'elenco di proposito: la coda
deve caricarsi subito, e un guasto del modello non deve poter svuotare una schermata
che funziona anche senza. Quella rotta applica, non propone: la revisione umana viene
dopo, dall'elenco «Decisioni recenti», con un annullamento per ognuna.
"""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import require_session
from app.db.models.ingredient import Ingredient
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.domain.rules import IngredientKind
from app.repositories.imports import (
    counts,
    decided_terms,
    get_term,
    pending_terms,
    waiting_titles,
)
from app.schemas.recipe_import import (
    DecideOut,
    DecideRequest,
    DecisionOut,
    ImportStatusOut,
    SuggestionOut,
    TermDecisionIn,
    TermOut,
    UndoOut,
)
from app.services.ingredient_match import match_name
from app.services.llm import LlmUnavailable
from app.services.recipe_import.decide import decide_terms
from app.services.recipe_import.manual import (
    DecisionRefused,
    ManualDecision,
    Refusal,
    decide_by_hand,
)
from app.services.recipe_import.materialize import materialize_ready
from app.services.recipe_import.undo import undo_decision

router = APIRouter(
    prefix="/api/v1/imports", tags=["imports"], dependencies=[Depends(require_session)]
)

# Quanti termini in un giro della rotta. Una chiamata a termine: il tetto è
# sull'attesa di chi ha premuto il bottone, non sulla correttezza.
MAX_TERMS_PER_CALL = 40

_REFUSAL_STATUS = {
    Refusal.INVALID: status.HTTP_422_UNPROCESSABLE_ENTITY,
    Refusal.NOT_FOUND: status.HTTP_404_NOT_FOUND,
    Refusal.CONFLICT: status.HTTP_409_CONFLICT,
}


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
        return [await _decided_out(session, term) for term in terms]

    terms = await pending_terms(session, GIALLOZAFFERANO, limit=limit)
    titles = await waiting_titles(
        session, GIALLOZAFFERANO, [term.term_key for term in terms]
    )
    return [
        await _pending_out(session, term, titles.get(term.term_key, [])) for term in terms
    ]


@router.get("/terms/{term_id:uuid}", response_model=TermOut)
async def read_term(
    term_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> TermOut:
    """Un termine solo, deciso o no: quello a cui porta un rifiuto dell'anagrafica.

    «Decisioni recenti» ne mostra al più cento, e nessuno deciso `auto`: senza questa
    rotta un termine deciso tempo fa non si ritroverebbe in coda, e il rifiuto che
    dice «annullalo lì» sarebbe un vicolo cieco. La forma è quella dell'elenco a cui il
    termine appartiene, così la schermata lo disegna con la stessa riga.

    `:uuid` nel percorso: senza, `/terms/proposals` — la vecchia rotta tolta, che deve
    restare un 404 — combacerebbe con questa e risponderebbe 405.
    """
    term = await get_term(session, term_id)
    if term is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "termine inesistente")
    if term.decision != TermDecision.PENDING:
        return await _decided_out(session, term)
    titles = await waiting_titles(session, GIALLOZAFFERANO, [term.term_key])
    return await _pending_out(session, term, titles.get(term.term_key, []))


async def _decided_out(session: AsyncSession, term: ImportTerm) -> TermOut:
    return TermOut(
        id=term.id, display_name=term.display_name, occurrences=term.occurrences,
        suggestion=None, waiting_titles=[], decided_by=term.decided_by,
        decided_action=_decided_action(term),
        decided_name=await _ingredient_name(session, term.ingredient_id),
        created_ingredient=term.created_ingredient,
        decided_at=term.decided_at,
    )


async def _pending_out(
    session: AsyncSession, term: ImportTerm, titles: list[str]
) -> TermOut:
    match = await match_name(session, term.display_name)
    # Una voce non alimentare non si propone mai come scorciatoia: il tasto
    # «Collega» chiamerebbe comunque la guardia 4.4 più sotto e tornerebbe un
    # 422 garantito (finding 2 della revisione finale). Meglio nessuna
    # scorciatoia che una che non porta da nessuna parte.
    suggestion = (
        SuggestionOut(
            ingredient_id=match.ingredient_id, name=match.name, certain=match.certain
        )
        if match.ingredient_id is not None
        and match.name is not None
        and match.kind != IngredientKind.NON_FOOD
        else None
    )
    return TermOut(
        id=term.id, display_name=term.display_name, occurrences=term.occurrences,
        suggestion=suggestion, waiting_titles=titles,
    )


def _decided_action(term: ImportTerm) -> str | None:
    """«map» per ogni decisione che punta a un ingrediente, «ignored» per chi non lo
    tiene in dispensa. Se il «map» ha creato l'ingrediente non lo dice questa etichetta
    ma `created_ingredient`, accanto a lei in `TermOut`.

    Quel fatto si scrive alla decisione dal 2026-09-28 (`import_terms.created_ingredient`,
    migrazione 0011): prima esisteva solo nell'istante di `decide_terms` o della
    decisione a mano, e per le decisioni di allora resta NULL. Non si ricava dopo.
    Sembrerebbe: «un ingrediente il cui unico alias dell'import è il nome di questo
    termine è nato con questa decisione». Non regge: «Rigatoni» agganciato a «pasta»,
    che c'era da prima, scrive comunque l'alias `rigatoni` con `source="import"`, e le
    due storie lasciano lo stesso segno. Per questo il NULL resta un «non si sa», e
    `undo_decision` su NULL non cancella niente.
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
    e si rivedono dall'elenco «Decisioni recenti» con un annullamento per ognuna. Un
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

    try:
        await decide_by_hand(
            session,
            term,
            ManualDecision(
                action=payload.action,
                ingredient_id=payload.ingredient_id,
                name=payload.name,
                display_name=payload.display_name,
                category=payload.category,
                role_override=payload.role_override,
            ),
        )
    except DecisionRefused as exc:
        raise HTTPException(_REFUSAL_STATUS[exc.refusal], exc.message) from exc

    materialized = await materialize_ready(session, GIALLOZAFFERANO)
    numbers = await counts(session, GIALLOZAFFERANO)
    await session.commit()
    return DecisionOut(unlocked=materialized.created, remaining_terms=numbers.pending_terms)


@router.post("/terms/{term_id}/undo", response_model=UndoOut)
async def undo(
    term_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> UndoOut:
    """Rimette un termine deciso in coda, e con lui il mondo che quella decisione ha mosso.

    Non è un editor: dopo questo, il termine si decide a mano con la scheda di sempre.
    Non chiede conferma per le ricette già cucinate: le loro cotture aspettano nel
    `payload` della pagina e tornano sulla ricetta rifatta (S9 §5.2). Un corpo con
    `force`, mandato da una PWA con la cache di prima, si ignora.
    """
    term = await get_term(session, term_id)
    if term is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "termine inesistente")
    if term.decision == TermDecision.PENDING:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"«{term.display_name}» è già in coda: non c'è nessuna decisione da disfare.",
        )

    undone = await undo_decision(session, term)
    numbers = await counts(session, GIALLOZAFFERANO)
    await session.commit()
    return UndoOut(
        recipes_requeued=undone.recipes_requeued,
        ingredient_deleted=undone.ingredient_deleted,
        remaining_terms=numbers.pending_terms,
    )
