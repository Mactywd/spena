import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from app.db.models.ingredient import IngredientCategory
from app.domain.rules import IngredientRole


class ImportStatusOut(BaseModel):
    fetched: int
    pending_recipes: int
    imported: int
    skipped: int
    pending_terms: int


class SuggestionOut(BaseModel):
    ingredient_id: uuid.UUID
    name: str
    certain: bool


class TermOut(BaseModel):
    id: uuid.UUID
    display_name: str
    occurrences: int
    suggestion: SuggestionOut | None
    # qualche titolo in attesa: «Scorza di limone» si giudica diversamente in una
    # torta e in un arrosto
    waiting_titles: list[str]
    # Valorizzati solo per un termine già deciso. Servono all'elenco della revisione,
    # che deve dire in una riga cosa è stato fatto: «Rigatoni → pasta», «Acqua →
    # ignorato». `decided_action` distingue solo "map" da "ignored"; se un "map" ha
    # creato l'ingrediente lo dice `created_ingredient`, scritto alla decisione dal
    # 2026-09-28 e NULL per quelle di prima (vedi `_decided_action` in
    # `app/api/imports.py`).
    decided_by: str | None = None
    decided_action: Literal["map", "ignored"] | None = None
    decided_name: str | None = None
    created_ingredient: bool | None = None
    # Quando la decisione è stata presa. La schermata mette in un elenco solo le
    # decisioni dell'AI e quelle a mano (R11), e le ordina con questa data: senza,
    # due elenchi già ordinati ciascuno per conto suo non si fondono.
    decided_at: datetime | None = None


class DecideRequest(BaseModel):
    """`term_ids` assente significa «tutti quelli in coda».

    È il caso normale: il bottone della schermata non ha una selezione da mandare, e
    obbligarlo a costruirla lo farebbe sbagliare appena la coda si accorcia sotto di
    lui. La lista esiste per chi vuole insistere su un termine preciso.
    """

    term_ids: list[uuid.UUID] | None = Field(default=None, max_length=200)


class DecideOut(BaseModel):
    applied: int
    created: int
    ignored: int
    still_pending: int
    # le ricette entrate grazie a queste decisioni: è il numero che rende il
    # riconoscimento un lavoro con un risultato visibile
    unlocked: int
    remaining_terms: int


class TermDecisionIn(BaseModel):
    """Le tre azioni in un solo corpo: l'API le distingue su `action`.

    Un corpo per azione avrebbe significato tre rotte per una decisione sola, e tre
    posti da cui far partire la materializzazione.
    """

    action: Literal["map", "create", "ignore"]
    ingredient_id: uuid.UUID | None = None
    name: str | None = Field(default=None, max_length=120)
    display_name: str | None = Field(default=None, max_length=120)
    category: IngredientCategory | None = None
    role_override: IngredientRole | None = None


class DecisionOut(BaseModel):
    unlocked: int
    remaining_terms: int


class UndoOut(BaseModel):
    recipes_requeued: int
    ingredient_deleted: bool
    remaining_terms: int
