import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.db.models.base import UUIDMixin
from app.db.models.ingredient import Ingredient


class ShoppingStatus(StrEnum):
    PENDING = "pending"      # da comprare
    CHECKED = "checked"      # nel carrello
    DONE = "done"            # sistemato in dispensa
    ARCHIVED = "archived"


class ShoppingReason(StrEnum):
    MANUAL = "manual"
    FINISHED_WHILE_COOKING = "finished_while_cooking"
    LOW_WHILE_COOKING = "low_while_cooking"


class ShoppingListItem(UUIDMixin, Base):
    __tablename__ = "shopping_list_items"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'checked', 'done', 'archived')", name="ck_shopping_status"
        ),
        CheckConstraint(
            "reason IN ('manual', 'finished_while_cooking', 'low_while_cooking')",
            name="ck_shopping_reason",
        ),
    )

    raw_text: Mapped[str] = mapped_column(String(200))
    # deliberatamente opzionale: scrivere la lista non deve mai essere interrotto
    ingredient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20))
    reason: Mapped[str] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    ingredient: Mapped["Ingredient | None"] = relationship(lazy="joined")
