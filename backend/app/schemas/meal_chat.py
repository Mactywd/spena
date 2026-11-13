"""La chat del piatto come la vede l'API (spec 2026-11-12 §5.3, §9).

Il giro (`app.services.meal_chat`) li usa anche per i dati degli eventi SSE, in
`model_dump(mode="json")`.
"""

import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, StringConstraints

from app.domain.meal_chat import MESSAGE_MAX_CHARS


class RecipeChangeOut(BaseModel):
    id: uuid.UUID
    summary: str
    created_recipe: bool
    undone: bool
    undoable: bool


class ChatMessageOut(BaseModel):
    id: uuid.UUID
    role: Literal["user", "assistant"]
    text: str
    status: Literal["pending", "sent", "failed"]
    notice: str | None
    created_at: datetime
    changes: list[RecipeChangeOut]


class HighlightOut(BaseModel):
    ingredient_ids: list[uuid.UUID]
    title: bool
    servings: bool
    instructions: bool
    description: bool


class DishChatOut(BaseModel):
    meal_id: uuid.UUID
    conversation_id: uuid.UUID | None
    messages: list[ChatMessageOut]
    replying: bool
    highlight: HighlightOut | None
    claude_ready: bool
    claude_notice: str | None


class ChatMessageIn(BaseModel):
    text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=MESSAGE_MAX_CHARS)
    ]
    retry_of: uuid.UUID | None = None
