"""Le risposte di «Sostituisci» in HTTP (R5)."""

import uuid
from typing import Literal

from pydantic import BaseModel, Field

from app.domain.rules import Availability
from app.domain.substitutions import DecidedBy, SubstitutionContext, SubstitutionVerdict


class SubstituteOut(BaseModel):
    ingredient_id: uuid.UUID
    # il nome canonico, minuscolo: il frontend mette la maiuscola solo a inizio riga
    name: str
    note: str | None


class LineSubstituteOut(SubstituteOut):
    availability: Availability
    # se in dispensa soddisfa la stessa regola della riga (`is_satisfied`): «ce l'hai»
    satisfied: bool


class LineSubstitutionOut(BaseModel):
    ingredient_id: uuid.UUID
    ingredient_name: str
    context: SubstitutionContext
    # da dove viene la risposta: la correzione della ricetta o la voce generale
    scope: Literal["recipe", "general"] | None
    verdict: SubstitutionVerdict | None
    decided_by: DecidedBy | None
    substitutes: list[LineSubstituteOut]
    # `POST …/ask`: l'AI non ha risposto, o ha risposto qualcosa che non si applica
    ai_failed: bool = False


class SubstituteIn(BaseModel):
    ingredient_id: uuid.UUID
    # Il limite vero (60, dopo la pulizia degli spazi) lo controlla `checked_answer`, con
    # la sua frase; questo è solo un tetto al corpo della richiesta.
    note: str | None = Field(default=None, max_length=500)


class SubstitutionIn(BaseModel):
    verdict: SubstitutionVerdict
    # quanti, lo dice `checked_answer` con la sua frase; qui solo un tetto al corpo
    substitutes: list[SubstituteIn] = Field(default_factory=list, max_length=20)


class ContextSubstitutionOut(BaseModel):
    context: SubstitutionContext
    recipes: int
    verdict: SubstitutionVerdict | None
    decided_by: DecidedBy | None
    substitutes: list[SubstituteOut]


class IngredientSubstitutionsOut(BaseModel):
    ingredient_id: uuid.UUID
    contexts: list[ContextSubstitutionOut]
    recipe_overrides: int
