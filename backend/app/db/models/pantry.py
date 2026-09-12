import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.db.models.base import UUIDMixin
from app.db.models.ingredient import Ingredient
from app.db.models.product import Product


class PantryItem(UUIDMixin, Base):
    """Una voce concreta in dispensa. Nessuna quantità, solo uno dei tre stati.

    `product_id` è nullo per gli sfusi. Più voci possono riferirsi allo stesso
    ingrediente: la disponibilità è la migliore fra i loro stati.
    """

    __tablename__ = "pantry_items"
    __table_args__ = (
        CheckConstraint("status IN ('available', 'low', 'finished')", name="ck_pantry_status"),
        # parziale: le query di disponibilità guardano solo le voci attive
        Index(
            "ix_pantry_active", "ingredient_id",
            postgresql_where=text("archived_at IS NULL AND status <> 'finished'"),
        ),
    )

    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="RESTRICT")
    )
    product_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    ingredient: Mapped["Ingredient"] = relationship(lazy="joined")
    product: Mapped["Product | None"] = relationship(lazy="joined")
