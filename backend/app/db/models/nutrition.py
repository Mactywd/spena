"""I nutrienti dell'ingrediente generico (S4).

`ciqual_foods` è la tabella CIQUAL caricata dal file dell'Anses (`app.cli.load_ciqual`):
un alimento per codice, coi valori per 100 g di parte edibile nelle chiavi del vocabolario
(`app/domain/nutrients.py`). Un nutriente che CIQUAL non dà non c'è nel dizionario: mai
uno zero al suo posto.

`ingredient_nutrition` lega un ingrediente al suo alimento. Tre stati: nessuna riga =
non ancora deciso; `ciqual_code` NULL = deciso «nessun alimento adatto»; un codice =
quell'alimento. I valori non si copiano qui: si leggono da `ciqual_foods` con una join,
così un caricamento più nuovo li aggiorna tutti. L'unico che scrive questa tabella è
`app/services/ingredient_nutrition.py`.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.db.models.base import UUIDMixin
from app.domain.ciqual import CODE_MAX_LENGTH, GROUP_MAX_LENGTH, NAME_MAX_LENGTH


class CiqualFood(Base):
    __tablename__ = "ciqual_foods"

    # il codice dell'Anses, come testo: è un identificatore, non un numero da sommare
    code: Mapped[str] = mapped_column(String(CODE_MAX_LENGTH), primary_key=True)
    name_fr: Mapped[str] = mapped_column(String(NAME_MAX_LENGTH))
    group_fr: Mapped[str | None] = mapped_column(String(GROUP_MAX_LENGTH), nullable=True)
    nutrients: Mapped[dict[str, Any]] = mapped_column(JSONB)
    # l'edizione della tabella: un caricamento del 2027 si distinguerà da questo
    version: Mapped[str] = mapped_column(String(10))


class NutritionDecider(StrEnum):
    """Chi ha scelto: come `decided_by` dei termini dell'import e delle unità."""

    AI = "ai"
    HUMAN = "human"


class IngredientNutrition(Base):
    __tablename__ = "ingredient_nutrition"
    __table_args__ = (
        CheckConstraint(
            "decided_by IN ('ai', 'human')", name="ck_ingredient_nutrition_decided_by"
        ),
    )

    # `CASCADE`: un ingrediente cancellato (una fusione, un annullamento dell'import) si
    # porta via la sua scelta. La fusione la perde (spec §4.15, deciso da Mattia il
    # 2026-10-13).
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE"), primary_key=True
    )
    # NULL = «nessun alimento adatto», deciso. `RESTRICT`: un alimento scelto non sparisce
    # da sotto un ingrediente (il caricamento aggiorna, non cancella).
    ciqual_code: Mapped[str | None] = mapped_column(
        String(CODE_MAX_LENGTH),
        ForeignKey("ciqual_foods.code", ondelete="RESTRICT"),
        nullable=True,
    )
    decided_by: Mapped[str] = mapped_column(String(20))
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IngredientUnitGrams(UUIDMixin, Base):
    """Quanti grammi pesa una unità di un ingrediente, per coppia (S4, fetta 2).

    Sempre sull'unità **canonica** (`units.canonical_id`, o l'unità stessa): «cucchiai» e
    «cucchiaio» hanno un peso solo. `unit_id` NULL è il «pezzo», la dose senza unità («2»
    uova). `grams` NULL è «nessun peso sensato», deciso: non si richiede. Le unità di
    massa e di volume non hanno righe qui: i loro grammi si contano da sé
    (`app/domain/recipe_nutrition.py`). L'unico che scrive è `app/services/unit_grams.py`.

    `CASCADE` sull'unità, non `RESTRICT`: la pulizia delle dosi toglie le unità spurie, e
    il peso di un'unità che non c'è più non serve a niente.
    """

    __tablename__ = "ingredient_unit_grams"
    __table_args__ = (
        UniqueConstraint(
            "ingredient_id",
            "unit_id",
            name="uq_ingredient_unit_grams",
            postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint("grams IS NULL OR grams > 0", name="ck_ingredient_unit_grams_positive"),
        CheckConstraint(
            "decided_by IN ('ai', 'human')", name="ck_ingredient_unit_grams_decided_by"
        ),
    )

    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE")
    )
    unit_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units.id", ondelete="CASCADE"), nullable=True
    )
    grams: Mapped[Decimal | None] = mapped_column(Numeric(8, 2), nullable=True)
    decided_by: Mapped[str] = mapped_column(String(20))
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
