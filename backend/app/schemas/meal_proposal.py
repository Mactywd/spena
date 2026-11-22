"""Le proposte di pasti come le vede l'API (piano 6c, decisioni 11–13).

Stanno in un modulo loro, e `app.schemas.planning` le riesporta: `ChatMessageOut` (della
chat) le porta sotto i messaggi e `PlanningChatOut` (della pianificazione) porta i
messaggi, e messi nello stesso modulo i due si importerebbero a vicenda.
"""

import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel

from app.domain.meals import MealSlot
from app.schemas.meal import MealRefOut


class ProposalRowOut(BaseModel):
    day: date
    slot: MealSlot
    dish: str
    sides: str | None
    # che cosa la riga fa al suo posto, letto dal vivo finché la proposta è aperta
    effect: Literal["new", "officialize", "replace"]
    occupant: MealRefOut | None
    meal_id: uuid.UUID | None


class MealProposalOut(BaseModel):
    id: uuid.UUID
    kind: Literal["official", "draft"]
    status: Literal["open", "placed", "superseded"]
    rows: list[ProposalRowOut]
    created_at: datetime
