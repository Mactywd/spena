"""Rimettere in coda una pagina scartata (spec 2026-10-09-scartate-in-coda §2, §3.3).

Una pagina `skipped` non tornava indietro da nessuna strada dell'app: `undo_decision`
riprende solo le pagine `imported` con la loro ricetta. Qui la si rimette `pending` e la
si lascia alla strada di tutte, `materialize_ready`, che la fa ricetta se la causa è
stata corretta — rilegando le cotture che aspettano nel `payload` — o la scarta di nuovo
col suo motivo. Nessun percorso parallelo: lo stesso codice che materializza dopo una
decisione.

Si materializza subito, nella stessa chiamata, e non al giro dopo: `materialize_ready`
gira solo quando si decide un termine o si scarica, e una pagina rimessa resterebbe
`pending` senza un esito da dire a chi ha toccato il pulsante.
"""

import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.recipe import CookingEvent
from app.db.models.recipe_import import ImportState, RecipeImport, TermDecision
from app.repositories.imports import terms_by_key
from app.services.recipe_import.materialize import (
    SkipExplained,
    explain_skip,
    materialize_ready,
)
from app.services.recipe_import.terms import sync_terms


class RequeueRefusal(StrEnum):
    NOT_SKIPPED = "not_skipped"
    UNREADABLE = "unreadable"


class NotRequeueable(Exception):
    """La pagina non si rimette in coda. `message` è la frase per chi ha toccato."""

    def __init__(self, refusal: RequeueRefusal, message: str) -> None:
        super().__init__(message)
        self.refusal = refusal
        self.message = message


@dataclass(frozen=True)
class Requeued:
    """Com'è finita questa pagina, e solo lei: `materialize_ready` può aver fatto
    ricette anche di altre pagine pronte, ma chi ha toccato chiede di questa."""

    outcome: Literal["imported", "skipped", "waiting"]
    recipe_id: uuid.UUID | None = None
    # le cotture che ora stanno sulla ricetta rifatta: tutte arrivate dal `payload`,
    # perché la ricetta è appena nata
    cooking_relinked: int = 0
    skip: SkipExplained | None = None
    # i termini della pagina ancora da decidere, nell'ordine delle righe
    waiting_terms: list[str] = field(default_factory=list)


async def requeue_page(session: AsyncSession, page: RecipeImport) -> Requeued:
    if page.state != ImportState.SKIPPED:
        raise NotRequeueable(
            RequeueRefusal.NOT_SKIPPED,
            "Questa pagina non è più scartata: l'elenco era vecchio.",
        )
    if not explain_skip(page.payload, page.skipped_reason).requeueable:
        raise NotRequeueable(
            RequeueRefusal.UNREADABLE,
            "La pagina non aveva una ricetta leggibile: rimetterla in coda non "
            "cambierebbe niente.",
        )

    page.state = ImportState.PENDING
    page.skipped_reason = None
    await session.flush()
    # Prima: un termine della pagina sparito dal dizionario rinasce — in coda, o deciso
    # da sé se coincide con l'anagrafica — invece di far aspettare la pagina un termine
    # che la coda non mostra, il vicolo cieco.
    await sync_terms(session, page.source)
    await materialize_ready(session, page.source)
    # Dopo: `occurrences` conta le ricette davvero in attesa, e questa forse non lo è più.
    await sync_terms(session, page.source)

    if page.state == ImportState.IMPORTED:
        relinked = await session.scalar(
            select(func.count())
            .select_from(CookingEvent)
            .where(CookingEvent.recipe_id == page.recipe_id)
        )
        return Requeued("imported", recipe_id=page.recipe_id, cooking_relinked=relinked or 0)
    if page.state == ImportState.SKIPPED:
        return Requeued("skipped", skip=explain_skip(page.payload, page.skipped_reason))

    terms = await terms_by_key(session, page.source)
    waiting: list[str] = []
    for line in page.payload.get("ingredients") or []:
        term = terms.get(line.get("key"))
        if (
            term is not None
            and term.decision == TermDecision.PENDING
            and term.display_name not in waiting
        ):
            waiting.append(term.display_name)
    return Requeued("waiting", waiting_terms=waiting)
