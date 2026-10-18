"""Le risposte di «Sostituisci» (R5): una tabella per due ambiti, e i sostituti.

`ingredient_substitutions` tiene:

- la **voce generale** di un ingrediente in un contesto — `recipe_id` NULL, `context`
  «dolce» o «salato» —, scritta dall'AI (`decided_by = "ai"`) o da una persona in
  Anagrafica (`"human"`);
- la **correzione di una ricetta** — `recipe_id` presente, `context` NULL —, sempre di
  una persona: «Non va bene qui».

`ck_substitution_scope` tiene separati i due ambiti; due indici unici **parziali** ne
fanno rispettare l'unicità (una voce per ingrediente e contesto, una correzione per
ricetta e ingrediente). Le chiavi esterne sono in CASCADE: un ingrediente o una ricetta
che spariscono — un annullamento della coda, l'import che rifà una ricetta — si portano
via le loro righe, e chi legge tratta una risposta rimasta senza sostituti come nessuna
risposta (`is_answered` in `repositories/substitutions.py`).
"""

import uuid

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.db.models.base import TimestampMixin, UUIDMixin
from app.db.models.ingredient import Ingredient
from app.domain.substitutions import SUBSTITUTE_NOTE_MAX


class IngredientSubstitution(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "ingredient_substitutions"
    __table_args__ = (
        CheckConstraint(
            "verdict IN ('substitutes', 'omit', 'irreplaceable')", name="ck_substitution_verdict"
        ),
        CheckConstraint("decided_by IN ('ai', 'human')", name="ck_substitution_decided_by"),
        CheckConstraint(
            "context IS NULL OR context IN ('dolce', 'salato')", name="ck_substitution_context"
        ),
        # o generale (un contesto, nessuna ricetta) o di una ricetta (nessun contesto)
        CheckConstraint("(recipe_id IS NULL) <> (context IS NULL)", name="ck_substitution_scope"),
        # la correzione di una ricetta la scrive solo una persona
        CheckConstraint(
            "recipe_id IS NULL OR decided_by = 'human'", name="ck_substitution_recipe_is_human"
        ),
        # dichiarati qui e non solo nella migrazione: l'autogenerate cancellerebbe ogni
        # indice che i modelli non conoscono. Il predicato Alembic non lo confronta: lo
        # provano i doppioni di `tests/db/test_substitution_schema.py`
        Index(
            "uq_substitution_general", "ingredient_id", "context",
            unique=True, postgresql_where=text("recipe_id IS NULL"),
        ),
        Index(
            "uq_substitution_recipe", "recipe_id", "ingredient_id",
            unique=True, postgresql_where=text("recipe_id IS NOT NULL"),
        ),
    )

    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE")
    )
    context: Mapped[str | None] = mapped_column(String(10), nullable=True)
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="CASCADE"), nullable=True
    )
    verdict: Mapped[str] = mapped_column(String(20))
    decided_by: Mapped[str] = mapped_column(String(10))

    options: Mapped[list["SubstitutionOption"]] = relationship(
        back_populates="substitution",
        cascade="all, delete-orphan",
        passive_deletes=True,
        lazy="selectin",
        order_by="SubstitutionOption.position",
    )


class SubstitutionOption(UUIDMixin, Base):
    """Un sostituto di una risposta, con la sua nota e il suo posto (dal migliore)."""

    __tablename__ = "substitution_options"
    __table_args__ = (
        UniqueConstraint("substitution_id", "substitute_id"),
        # la fusione e le cancellazioni cercano per sostituto
        Index("ix_substitution_options_substitute", "substitute_id"),
    )

    substitution_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredient_substitutions.id", ondelete="CASCADE")
    )
    substitute_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE")
    )
    note: Mapped[str | None] = mapped_column(String(SUBSTITUTE_NOTE_MAX), nullable=True)
    position: Mapped[int] = mapped_column(SmallInteger)

    substitution: Mapped[IngredientSubstitution] = relationship(back_populates="options")
    substitute: Mapped[Ingredient] = relationship(lazy="joined")
