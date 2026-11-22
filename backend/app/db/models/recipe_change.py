"""Una modifica della ricetta di un pasto fatta da Claude (spec 2026-11-12 §4.3, §5.3).

`before` è la ricetta (e il piatto) com'erano prima della modifica, `after` com'erano
subito dopo, `changed` le righe e i campi toccati (la forma è nel Task 3). «Annulla» li
confronta con lo stato di adesso: rimette `before` solo se ricetta e piatto sono ancora
esattamente `after`, così non sovrascrive mai un lavoro più nuovo (decisione 16).
"""

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.db.models.base import UUIDMixin


class RecipeChange(UUIDMixin, Base):
    __tablename__ = "recipe_changes"
    __table_args__ = (Index("ix_recipe_changes_meal_created", "meal_id", "created_at"),)

    meal_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meals.id", ondelete="CASCADE")
    )
    recipe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="CASCADE")
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="SET NULL"), nullable=True
    )
    turn_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_recipe: Mapped[bool] = mapped_column(Boolean)
    summary: Mapped[str] = mapped_column(String(200))
    before: Mapped[dict[str, Any]] = mapped_column(JSONB)
    after: Mapped[dict[str, Any]] = mapped_column(JSONB)
    changed: Mapped[dict[str, Any]] = mapped_column(JSONB)
    undone_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
