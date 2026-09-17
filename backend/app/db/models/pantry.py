import uuid
from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    func,
    text,
)
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
        CheckConstraint(
            "fill_percent BETWEEN 0 AND 100", name="ck_pantry_fill_percent"
        ),
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
    # Dove sta il cursore a tre zone, 0–100. È un'indicazione a occhio — utile in
    # negozio, e per seguire qualcosa che si consuma senza mai finire — non una
    # quantità: niente unità, niente conversioni, nessun conto la usa. Lo stato qui
    # sopra resta la verità, e `status_for_fill` è ciò che li tiene d'accordo.
    # NULL per chi non l'ha mai mosso.
    fill_percent: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    status_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    ingredient: Mapped["Ingredient"] = relationship(lazy="joined")
    product: Mapped["Product | None"] = relationship(lazy="joined")
