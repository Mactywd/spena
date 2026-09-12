import uuid
from typing import Any

from sqlalchemy import ForeignKey, Index, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.db.models.base import TimestampMixin, UUIDMixin


class Product(UUIDMixin, TimestampMixin, Base):
    """La referenza concreta: marca, codice a barre, valori per 100 g.

    `ingredient_id` è obbligatorio per tenere pulite le query di disponibilità.
    Il principio "mai un vicolo cieco" è garantito dall'interfaccia, che crea
    l'ingrediente canonico dal nome del prodotto con un tocco.
    """

    __tablename__ = "products"
    __table_args__ = (
        Index(
            "ix_products_name_trgm", "name",
            postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index("ix_products_ingredient_id", "ingredient_id"),
    )

    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="RESTRICT")
    )
    name: Mapped[str] = mapped_column(String(200))
    brand: Mapped[str | None] = mapped_column(String(120), nullable=True)
    barcode: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    source: Mapped[str] = mapped_column(String(20))
    source_payload: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    nutrients: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
