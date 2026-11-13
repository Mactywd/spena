"""Gli utensili di cucina: gli strumenti che Mattia ha a casa.

Servono perché le ricette scritte dall'AI usino solo quelli. Non hanno nessun legame con
le righe delle ricette né con gli ingredienti (spec 2026-11-12 §4.4): la dispensa e le
ricette restano come sono. Il nome non è unico, di proposito (decisione 5): due padelle
diverse, con due note diverse, sono due utensili; fonderle sarebbe indovinare.
"""

from sqlalchemy import CheckConstraint, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.db.models.base import TimestampMixin, UUIDMixin

UTENSIL_NAME_MAX = 120
UTENSIL_NOTE_MAX = 200


class Utensil(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "utensils"
    __table_args__ = (
        CheckConstraint("btrim(name) <> ''", name="ck_utensils_name_not_blank"),
    )

    name: Mapped[str] = mapped_column(String(UTENSIL_NAME_MAX))
    note: Mapped[str | None] = mapped_column(String(UTENSIL_NOTE_MAX), nullable=True)
