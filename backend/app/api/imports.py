"""Le rotte della revisione dell'import.

Una sola decisione per chiamata, e ogni decisione materializza subito le ricette che
aspettavano quel termine: il numero che torna — «sbloccate dodici ricette» — è ciò
che rende la revisione un lavoro con un risultato visibile invece di un modulo da
compilare.

Le proposte di Claude stanno in una rotta separata dall'elenco di proposito: la coda
deve caricarsi subito, e un guasto del modello non deve poter svuotare una schermata
che funziona anche senza.
"""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import require_session
from app.db.models.ingredient import Ingredient
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.imports import counts, get_term, pending_terms, waiting_titles
from app.repositories.ingredients import create_ingredient, remember_alias
from app.schemas.recipe_import import (
    DecisionOut,
    ImportStatusOut,
    ProposalOut,
    ProposalsOut,
    ProposalsRequest,
    SuggestionOut,
    TermDecisionIn,
    TermOut,
)
from app.services.ai_recipes import AiUnavailable
from app.services.ingredient_match import match_name
from app.services.recipe_import.materialize import materialize_ready
from app.services.recipe_import.terms import propose_decisions

router = APIRouter(
    prefix="/api/v1/imports", tags=["imports"], dependencies=[Depends(require_session)]
)


@router.get("/status", response_model=ImportStatusOut)
async def read_status(session: AsyncSession = Depends(get_session)) -> ImportStatusOut:
    numbers = await counts(session, GIALLOZAFFERANO)
    return ImportStatusOut(**vars(numbers))


@router.get("/terms", response_model=list[TermOut])
async def read_terms(
    limit: int = Query(default=20, le=50),
    session: AsyncSession = Depends(get_session),
) -> list[TermOut]:
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


@router.post("/terms/proposals", response_model=ProposalsOut)
async def read_proposals(
    payload: ProposalsRequest, session: AsyncSession = Depends(get_session)
) -> ProposalsOut:
    rows = await session.execute(
        select(ImportTerm).where(ImportTerm.id.in_(payload.term_ids))
    )
    terms = list(rows.scalars())
    if not terms:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "nessuno di questi termini esiste")

    try:
        proposals = await propose_decisions(session, terms)
    except AiUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"le proposte non sono disponibili ({exc}): decidi a mano, la coda funziona.",
        ) from exc
    return ProposalsOut(proposals=[ProposalOut(**vars(p)) for p in proposals])


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
