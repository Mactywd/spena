import uuid
from enum import StrEnum

from sqlalchemy import ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.db.models.base import TimestampMixin, UUIDMixin


class IngredientCategory(StrEnum):
    """Reparti del supermercato: guidano il raggruppamento della lista."""

    VERDURA = "verdura"
    FRUTTA = "frutta"
    CARNE = "carne"
    PESCE = "pesce"
    LATTICINI = "latticini"
    CEREALI = "cereali"
    LEGUMI = "legumi"
    CONDIMENTI = "condimenti"
    SPEZIE = "spezie"
    BEVANDE = "bevande"
    DOLCI = "dolci"
    ALTRO = "altro"


class Ingredient(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ingredients"
    # dichiarato qui e non solo nella migrazione: l'autogenerate confronta i
    # modelli con il database e cancellerebbe ogni indice che i modelli non
    # conoscono, autocomplete trigram compreso
    __table_args__ = (
        Index(
            "ix_ingredients_name_trgm", "name",
            postgresql_using="gin", postgresql_ops={"name": "gin_trgm_ops"},
        ),
    )

    name: Mapped[str] = mapped_column(String(120), unique=True)
    display_name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(20))
    # popolato in fase 3, quando arrivano le tabelle di composizione
    composition_ref: Mapped[str | None] = mapped_column(String(60), nullable=True)

    aliases: Mapped[list["IngredientAlias"]] = relationship(
        back_populates="ingredient", cascade="all, delete-orphan", lazy="selectin"
    )


class IngredientAlias(UUIDMixin, Base):
    __tablename__ = "ingredient_aliases"
    __table_args__ = (
        UniqueConstraint("ingredient_id", "alias"),
        Index(
            "ix_aliases_alias_trgm", "alias",
            postgresql_using="gin", postgresql_ops={"alias": "gin_trgm_ops"},
        ),
    )

    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE")
    )
    alias: Mapped[str] = mapped_column(String(120))
    source: Mapped[str] = mapped_column(String(20))

    ingredient: Mapped[Ingredient] = relationship(back_populates="aliases")
