"""La chat di pianificazione come la vede l'API (spec 2026-11-12 §5.2, piano 6c)."""

import uuid
from datetime import date

from pydantic import BaseModel

from app.domain.meals import MealSlot
from app.schemas.meal import MealOut
from app.schemas.meal_chat import ChatMessageOut
from app.schemas.meal_proposal import MealProposalOut, ProposalRowOut

__all__ = [
    "FocusIn",
    "FocusOut",
    "MealProposalOut",
    "PlaceIn",
    "PlaceOut",
    "PlanningChatOut",
    "PlanningCreateIn",
    "PlanningFocusIn",
    "ProposalRowOut",
]


class FocusOut(BaseModel):
    day: date
    slot: MealSlot


class PlanningChatOut(BaseModel):
    conversation_id: uuid.UUID | None
    focus: FocusOut | None
    messages: list[ChatMessageOut]
    replying: bool
    concluded: bool
    claude_ready: bool
    claude_notice: str | None


class FocusIn(BaseModel):
    """Il posto di partenza («Chiedilo a Claude» sul posto vuoto, decisione 25)."""

    day: date
    slot: MealSlot


class PlanningCreateIn(BaseModel):
    """«Nuova», anche con il posto."""

    focus: FocusIn | None = None


class PlanningFocusIn(BaseModel):
    """Il `PATCH` della conversazione: il posto nuovo, o `null` per toglierlo. Il campo è
    obbligatorio, così un corpo vuoto non toglie il posto per sbaglio."""

    focus: FocusIn | None


class PlaceIn(BaseModel):
    """«Metti nella settimana»: `replace` è la conferma per i posti occupati."""

    replace: bool = False


class PlaceOut(BaseModel):
    chat: PlanningChatOut
    meals: list[MealOut]
    # il messaggio che il telefono manda a Claude dopo la messa (decisione 14)
    follow_up: str
