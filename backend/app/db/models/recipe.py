import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.db.models.base import TimestampMixin, UUIDMixin
from app.db.models.ingredient import Ingredient

EMBEDDING_DIM = 384  # intfloat/multilingual-e5-small


class RecipeSource(StrEnum):
    DATASET = "dataset"
    MANUAL = "manual"
    AI = "ai"


class Recipe(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "recipes"
    __table_args__ = (
        CheckConstraint("source IN ('dataset', 'manual', 'ai')", name="ck_recipe_source"),
    )

    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    instructions: Mapped[str] = mapped_column(Text)
    servings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source: Mapped[str] = mapped_column(String(20))
    source_ref: Mapped[str | None] = mapped_column(String(500), nullable=True)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM), nullable=True)
    search_tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed(
            "to_tsvector('italian', coalesce(title, '') || ' ' || coalesce(description, ''))",
            persisted=True,
        ),
    )

    ingredients: Mapped[list["RecipeIngredient"]] = relationship(
        back_populates="recipe", cascade="all, delete-orphan", lazy="selectin"
    )


class RecipeIngredient(UUIDMixin, Base):
    """Il ruolo è il pezzo che rende utile lo stato "quasi finito".

    `quantity_text` è testo di sola visualizzazione: non entra mai in nessun
    calcolo, per scelta di progetto.
    """

    __tablename__ = "recipe_ingredients"
    __table_args__ = (
        UniqueConstraint("recipe_id", "ingredient_id"),
        CheckConstraint("role IN ('primary', 'secondary')", name="ck_recipe_ingredient_role"),
    )

    recipe_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="CASCADE")
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="RESTRICT")
    )
    role: Mapped[str] = mapped_column(String(20))
    quantity_text: Mapped[str | None] = mapped_column(String(100), nullable=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    recipe: Mapped[Recipe] = relationship(back_populates="ingredients")
    ingredient: Mapped["Ingredient"] = relationship(lazy="joined")


class CookingEvent(UUIDMixin, Base):
    """Non serve alla v1. Esiste perché la fase 3 costruisce il diario
    nutrizionale su questo storico e la fase 4 ci impara cosa cucini davvero.
    """

    __tablename__ = "cooking_events"

    # in v1 sempre valorizzato: il nullo è predisposizione per la cottura a braccio
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True
    )
    cooked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    servings: Mapped[int | None] = mapped_column(Integer, nullable=True)
    snapshot: Mapped[dict[str, Any]] = mapped_column(JSONB)
