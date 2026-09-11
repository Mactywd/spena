import uuid

from pydantic import BaseModel, Field

from app.domain.rules import PantryStatus


class TransitionIn(BaseModel):
    pantry_item_id: uuid.UUID
    to_status: PantryStatus
    restock: bool = False


class CookRequest(BaseModel):
    servings: int | None = Field(default=None, ge=1, le=50)
    transitions: list[TransitionIn] = Field(default_factory=list)


class CookResultOut(BaseModel):
    event_id: uuid.UUID
    updated: int
    restocked: int
