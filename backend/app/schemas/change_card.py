"""Le schede dei cambi, come le vede l'API (spec 2026-11-12 §6.2)."""

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, model_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.change_card import CardStatus, ChangeCard, RowKind
from app.db.models.meal import Meal
from app.db.models.pantry import PantryItem
from app.domain.meals import MealSlot
from app.domain.rules import PantryStatus
from app.schemas.meal import TEXT_MAX, MealRefOut
from app.services.change_cards import ALREADY_LISTED_NOTE


class ChangeRowOut(BaseModel):
    id: uuid.UUID
    kind: Literal["pantry", "list", "unlist"]
    label: str
    # per `pantry`: lo stato di adesso finché la scheda è proposta, quello di prima dopo
    from_status: PantryStatus | None
    to_status: PantryStatus | None
    listed: bool  # riga di lista con una voce già in lista
    checked: bool
    editable: bool
    note: str | None
    applied: bool | None


class ChangeCardOut(BaseModel):
    id: uuid.UUID
    kind: Literal["forward", "inverse"]
    status: Literal["proposed", "applied", "discarded", "superseded"]
    list_only: bool
    title: str
    meals: list[MealRefOut]  # i pasti che ci sono ancora
    rows: list[ChangeRowOut]
    created_at: datetime
    applied_at: datetime | None


class RowOverrideIn(BaseModel):
    id: uuid.UUID
    checked: bool
    to_status: PantryStatus | None = None


class CardApplyIn(BaseModel):
    rows: list[RowOverrideIn] = []


class CardRowIn(BaseModel):
    pantry_item_id: uuid.UUID | None = None
    raw_text: str | None = None

    @model_validator(mode="after")
    def _one_of_two(self) -> "CardRowIn":
        if self.raw_text is not None:
            self.raw_text = self.raw_text.strip()
            if not 1 <= len(self.raw_text) <= TEXT_MAX:
                raise ValueError(f"il testo va da 1 a {TEXT_MAX} caratteri")
        if (self.pantry_item_id is None) == (self.raw_text is None):
            raise ValueError("serve una voce di dispensa oppure un testo, non entrambi")
        return self


async def card_out(session: AsyncSession, card: ChangeCard) -> ChangeCardOut:
    """`card` con le righe già caricate (`get_card`)."""
    item_ids = [r.pantry_item_id for r in card.rows if r.pantry_item_id is not None]
    live: dict[uuid.UUID, str] = {}
    if item_ids:
        live = dict(
            (
                await session.execute(
                    select(PantryItem.id, PantryItem.status)
                    .where(PantryItem.id.in_(item_ids))
                    .execution_options(populate_existing=True)
                )
            ).all()
        )
    meal_ids = [uuid.UUID(m) for m in card.meal_ids]
    meals: list[Meal] = []
    if meal_ids:
        found = (
            await session.execute(select(Meal).where(Meal.id.in_(meal_ids)))
        ).scalars()
        by_id = {m.id: m for m in found}
        meals = [by_id[i] for i in meal_ids if i in by_id]
    applied = card.status == CardStatus.APPLIED.value

    def from_status(row) -> str | None:
        if row.kind != RowKind.PANTRY.value:
            return None
        if applied and row.before_status is not None:
            return row.before_status
        return live.get(row.pantry_item_id) if row.pantry_item_id is not None else None

    return ChangeCardOut(
        id=card.id,
        kind=card.kind,
        status=card.status,
        list_only=card.list_only,
        title=card.title,
        meals=[
            MealRefOut(
                id=m.id, day=m.day, slot=MealSlot(m.slot), dish=m.dish, recipe_id=m.recipe_id
            )
            for m in meals
        ],
        rows=[
            ChangeRowOut(
                id=r.id, kind=r.kind, label=r.label, from_status=from_status(r),
                to_status=r.to_status,
                listed=r.kind == RowKind.LIST.value and r.note == ALREADY_LISTED_NOTE,
                checked=r.checked, editable=r.editable, note=r.note, applied=r.applied,
            )
            for r in card.rows
        ],
        created_at=card.created_at,
        applied_at=card.applied_at,
    )
