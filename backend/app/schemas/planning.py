"""La chat di pianificazione come la vede l'API (spec 2026-11-12 §5.2, piano 6c)."""

import uuid
from datetime import date

from pydantic import BaseModel

from app.domain.meals import MealSlot
from app.schemas.meal_chat import ChatMessageOut
from app.schemas.meal_proposal import MealProposalOut, ProposalRowOut

__all__ = ["FocusOut", "MealProposalOut", "PlanningChatOut", "ProposalRowOut"]


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
