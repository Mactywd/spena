"""Un pasto è un posto della settimana (spec 2026-11-12 §4.1, §4.2).

Un posto è una data più pranzo o cena, e tiene al più un pasto. Il pasto ha un piatto, gli
accompagnamenti (testo breve), il segno «fuori casa» e, facoltativa, una ricetta. È una
bozza o ufficiale: una bozza non ha ricetta. Un avanzo è un pasto senza ricetta propria,
legato al pasto d'origine. Pasto e ricetta stanno uno a uno: una ricetta appartiene a un
pasto solo (`uq_meals_recipe`), e le regole sono vincoli del database, non solo del codice.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    false,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.db.models.base import TimestampMixin, UUIDMixin
from app.db.models.recipe import Recipe


class Meal(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "meals"
    __table_args__ = (
        UniqueConstraint("day", "slot", name="uq_meals_day_slot"),
        UniqueConstraint("recipe_id", name="uq_meals_recipe"),
        CheckConstraint("slot IN ('lunch', 'dinner')", name="ck_meal_slot"),
        CheckConstraint("status IN ('draft', 'official')", name="ck_meal_status"),
        CheckConstraint("length(btrim(dish)) > 0", name="ck_meal_dish_not_blank"),
        CheckConstraint(
            "leftover_of_id IS NULL OR recipe_id IS NULL", name="ck_meal_leftover_no_recipe"
        ),
        CheckConstraint("NOT away OR leftover_of_id IS NULL", name="ck_meal_away_not_leftover"),
        CheckConstraint(
            "status = 'official' OR recipe_id IS NULL", name="ck_meal_draft_no_recipe"
        ),
        CheckConstraint(
            "leftover_of_id IS NULL OR leftover_of_id <> id", name="ck_meal_not_own_leftover"
        ),
    )

    day: Mapped[date] = mapped_column(Date)
    slot: Mapped[str] = mapped_column(String(10))  # lunch | dinner
    dish: Mapped[str] = mapped_column(String(200))
    sides: Mapped[str | None] = mapped_column(String(200), nullable=True)
    away: Mapped[bool] = mapped_column(Boolean, server_default=false(), default=False)
    status: Mapped[str] = mapped_column(
        String(10), server_default="official", default="official"
    )  # draft | official
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True
    )
    leftover_of_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meals.id", ondelete="SET NULL"), nullable=True
    )
    recipe_requested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    recipe_notice: Mapped[str | None] = mapped_column(Text, nullable=True)

    # `lazy="raise"`: le letture le caricano con `selectinload`, mai per caso
    recipe: Mapped[Recipe | None] = relationship(lazy="raise")
    leftover_of: Mapped["Meal | None"] = relationship(
        remote_side="Meal.id", lazy="raise"
    )
