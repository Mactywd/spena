"""I pasti e la settimana, come li vede l'API (spec 2026-11-12 §4, §5)."""

import uuid
from datetime import date

from pydantic import BaseModel, field_validator

from app.domain.meals import MealSlot, MealStatus

TEXT_MAX = 200


class MealRefOut(BaseModel):
    id: uuid.UUID
    day: date
    slot: MealSlot
    dish: str
    recipe_id: uuid.UUID | None


class MealRecipeOut(BaseModel):
    id: uuid.UUID
    title: str
    in_book: bool


class MealOut(BaseModel):
    id: uuid.UUID
    day: date
    slot: MealSlot
    week: date  # il lunedì di `day`
    dish: str
    sides: str | None
    away: bool
    status: MealStatus
    unrecorded: bool
    recipe: MealRecipeOut | None
    leftover_of: MealRefOut | None
    can_chat: bool
    open_card_id: uuid.UUID | None = None  # la scheda dei cambi ancora da applicare


class WeekOut(BaseModel):
    monday: date
    sunday: date
    today: date
    previous: date
    next: date
    days: list[date]
    meals: list[MealOut]


def _clean_dish(value: str | None) -> str:
    if value is None:
        raise ValueError("il piatto non può mancare")
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("il piatto non può essere vuoto")
    if len(cleaned) > TEXT_MAX:
        raise ValueError(f"il piatto supera {TEXT_MAX} caratteri")
    return cleaned


def _clean_sides(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    if len(cleaned) > TEXT_MAX:
        raise ValueError(f"gli accompagnamenti superano {TEXT_MAX} caratteri")
    return cleaned or None


class MealCreate(BaseModel):
    day: date
    slot: MealSlot
    dish: str
    sides: str | None = None
    away: bool = False
    status: MealStatus = MealStatus.OFFICIAL
    leftover_of_id: uuid.UUID | None = None
    replace: bool = False

    @field_validator("dish", mode="after")
    @classmethod
    def _dish(cls, v: str | None) -> str:
        return _clean_dish(v)

    @field_validator("sides", mode="after")
    @classmethod
    def _sides(cls, v: str | None) -> str | None:
        return _clean_sides(v)


class MealUpdate(BaseModel):
    """Si usano solo i campi mandati (`model_fields_set`); `replace` non è un cambio."""

    day: date | None = None
    slot: MealSlot | None = None
    dish: str | None = None
    sides: str | None = None
    away: bool | None = None
    status: MealStatus | None = None
    replace: bool = False

    @field_validator("dish", mode="after")
    @classmethod
    def _dish(cls, v: str | None) -> str:
        return _clean_dish(v)

    @field_validator("sides", mode="after")
    @classmethod
    def _sides(cls, v: str | None) -> str | None:
        return _clean_sides(v)

    @field_validator("day", "slot", "away", "status", mode="before")
    @classmethod
    def _not_null(cls, v: object) -> object:
        if v is None:
            raise ValueError("il valore non può essere nullo")
        return v


class RecipeCopyIn(BaseModel):
    recipe_id: uuid.UUID
