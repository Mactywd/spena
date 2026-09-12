import uuid
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


class ProposalsRequest(BaseModel):
    term_ids: list[uuid.UUID] = Field(min_length=1, max_length=40)


class ProposalOut(BaseModel):
    term_id: uuid.UUID
    action: Literal["map", "create", "ignore"]
    ingredient_id: uuid.UUID | None = None
    name: str | None = None
    display_name: str | None = None
    category: str | None = None


class ProposalsOut(BaseModel):
    proposals: list[ProposalOut]


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
