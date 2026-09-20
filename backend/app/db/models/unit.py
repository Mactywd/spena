"""Il vocabolario delle dosi, che cresce da sé.

Non è un enum nel codice perché la fonte è un ricettario vero: ogni catalogo nuovo
porta parole che non avevamo previsto, e una parola non prevista non deve poter
bloccare una ricetta. Una riga senza `singular` è una parola incontrata e non ancora
decisa: si mostra così com'è arrivata, e il riporziona la scala lo stesso.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.db.models.base import TimestampMixin, UUIDMixin
from app.domain.quantities import UNIT_MAX_LENGTH

# `UNIT_MAX_LENGTH` si importa dal parser e non si ridichiara qui: è lui a decidere
# quali parole possono diventare una chiave, e due numeri separati divergerebbero il
# giorno in cui uno dei due cambia. Chi lo importa da questo modulo continua a
# trovarlo (`app/services/unit_forms.py`).


class Unit(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "units"

    # la parola come è arrivata dal testo: è quel che si è visto, non quel che si
    # vorrebbe aver visto
    key: Mapped[str] = mapped_column(String(UNIT_MAX_LENGTH), unique=True)
    singular: Mapped[str | None] = mapped_column(String(UNIT_MAX_LENGTH), nullable=True)
    plural: Mapped[str | None] = mapped_column(String(UNIT_MAX_LENGTH), nullable=True)
    # "ai" o "human", come in ImportTerm: le due decisioni AI del progetto hanno la
    # stessa forma
    decided_by: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # «cucchiai» punta a «cucchiaio» quando l'AI dice che è il suo singolare e quella
    # chiave esiste già. Serve a S4: senza, il peso della coppia ingrediente×unità
    # andrebbe riempito due volte per la stessa unità, e la seconda divergerebbe.
    canonical_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units.id", ondelete="RESTRICT"), nullable=True
    )
