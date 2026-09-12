"""Le due tabelle dell'import: le pagine scaricate e il dizionario dei termini.

`recipe_imports` è l'area di sosta fra lo scarico e il ricettario, e resta dopo
come registro di ciò che si è preso. `import_terms` è il dizionario dal catalogo
della fonte al nostro: il catalogo di un sito di cucina è più fine di
un'anagrafica fatta per rispondere «ce l'ho in casa?», e colmare quella distanza
è l'unica parte di questo lavoro che non si può automatizzare.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.db.models.base import UUIDMixin

GIALLOZAFFERANO = "giallozafferano"


class ImportState(StrEnum):
    PENDING = "pending"
    IMPORTED = "imported"
    SKIPPED = "skipped"


class TermDecision(StrEnum):
    PENDING = "pending"
    MAPPED = "mapped"
    IGNORED = "ignored"


class RecipeImport(UUIDMixin, Base):
    """Una pagina scaricata, con la sua lettura strutturata.

    Non conserva l'HTML: sull'archivio intero sarebbe mezzo gigabyte, e analizzata
    la pagina non serve più. `payload` tiene anche i valori nutrizionali della
    fonte alla lettera, che nessuno usa oggi: è ciò che permetterà alla fase 3 di
    non riscaricare niente.
    """

    __tablename__ = "recipe_imports"
    __table_args__ = (
        UniqueConstraint("source", "url"),
        CheckConstraint(
            "state IN ('pending', 'imported', 'skipped')", name="ck_recipe_import_state"
        ),
        Index("ix_recipe_imports_state", "state"),
    )

    source: Mapped[str] = mapped_column(String(40))
    url: Mapped[str] = mapped_column(String(500))
    fetched_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    payload: Mapped[dict] = mapped_column(JSONB)
    state: Mapped[str] = mapped_column(String(20), default=ImportState.PENDING)
    skipped_reason: Mapped[str | None] = mapped_column(String(200), nullable=True)
    # SET NULL e non CASCADE: se l'utente cancella una ricetta importata, questa
    # riga deve sopravvivere con state='imported', altrimenti la materializzazione
    # successiva la ricrea e la cancellazione non è mai definitiva. È lo stato, non
    # la presenza della chiave, a dire «già importata una volta».
    recipe_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("recipes.id", ondelete="SET NULL"), nullable=True
    )


class ImportTerm(UUIDMixin, Base):
    """Un ingrediente del catalogo della fonte, e cosa abbiamo deciso che sia.

    L'identità è la chiave del loro indirizzo, non il nome scritto: il nome cambia
    con un refuso corretto, l'indirizzo no.
    """

    __tablename__ = "import_terms"
    __table_args__ = (
        UniqueConstraint("source", "term_key"),
        CheckConstraint(
            "decision IN ('pending', 'mapped', 'ignored')", name="ck_import_term_decision"
        ),
        CheckConstraint(
            "role_override IS NULL OR role_override IN ('primary', 'secondary')",
            name="ck_import_term_role",
        ),
        # Il vincolo che conta: un termine «collegato» a niente produrrebbe ricette
        # con una riga in meno, e una disponibilità calcolata su una ricetta che non
        # è quella scritta.
        CheckConstraint(
            "decision <> 'mapped' OR ingredient_id IS NOT NULL",
            name="ck_import_term_mapped_has_ingredient",
        ),
        # la coda si legge per decisione e frequenza: è l'unico ordine in cui si
        # revisiona, perché decidere prima i termini frequenti sblocca più ricette
        Index("ix_import_terms_queue", "decision", "occurrences"),
    )

    source: Mapped[str] = mapped_column(String(40))
    term_key: Mapped[str] = mapped_column(String(200))
    display_name: Mapped[str] = mapped_column(String(200))
    # ricalcolato a ogni scarico, mai incrementato: un contatore incrementato
    # divergerebbe al primo ri-scarico, e un ordinamento della coda basato su un
    # numero sbagliato è un difetto che nessuno nota
    occurrences: Mapped[int] = mapped_column(Integer, default=0)
    decision: Mapped[str] = mapped_column(String(20), default=TermDecision.PENDING)
    ingredient_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=True
    )
    # la deduzione del ruolo sbaglia dove il buon senso culinario non segue la
    # categoria: l'aglio è verdura e quasi sempre secondario. Sta qui e non su
    # `ingredients` perché è una correzione alla deduzione dell'import, non una
    # proprietà dell'ingrediente.
    role_override: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
