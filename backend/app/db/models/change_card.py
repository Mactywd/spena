"""Le schede dei cambi: dispensa e lista della spesa, proposte da Claude (spec §6.2).

Claude propone, Mattia applica: la scheda è una proposta di cambiare dispensa e lista, e
niente si muove finché lui non la applica (`status`: proposed → applied | discarded |
superseded: messa da parte da una scheda nuova di Claude per gli stessi pasti). Una scheda
`inverse` rimette le cose com'erano: lo stato di prima (`before_status`) resta sulla
riga della scheda diretta e la scheda inversa lo riusa. `list_only` è una scheda che tocca
solo la lista.

`meal_ids` (decisione 18): sulla scheda sono i pasti per cui è stata chiesta; su ogni riga
sono i pasti per cui quella voce serve, di norma tutti quelli della scheda. Se Claude
nomina due volte la stessa voce le righe si fondono e i pasti si uniscono.
"""

import uuid
from datetime import datetime
from enum import StrEnum

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    false,
    func,
    text,
    true,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.db.models.base import UUIDMixin

_STATI = "('available', 'low', 'finished')"


class CardKind(StrEnum):
    FORWARD = "forward"
    INVERSE = "inverse"


class CardStatus(StrEnum):
    PROPOSED = "proposed"
    APPLIED = "applied"
    DISCARDED = "discarded"
    SUPERSEDED = "superseded"


class RowKind(StrEnum):
    PANTRY = "pantry"
    LIST = "list"
    UNLIST = "unlist"


def _fk(target: str, ondelete: str = "SET NULL") -> Mapped[uuid.UUID | None]:
    return mapped_column(
        UUID(as_uuid=True), ForeignKey(target, ondelete=ondelete), nullable=True
    )


class ChangeCard(UUIDMixin, Base):
    __tablename__ = "change_cards"
    __table_args__ = (
        CheckConstraint("kind IN ('forward', 'inverse')", name="ck_card_kind"),
        CheckConstraint(
            "status IN ('proposed', 'applied', 'discarded', 'superseded')",
            name="ck_card_status",
        ),
        Index("ix_change_cards_status", "status"),
    )

    kind: Mapped[str] = mapped_column(String(10))  # forward | inverse
    status: Mapped[str] = mapped_column(
        String(10), server_default="proposed", default="proposed"
    )  # proposed | applied | discarded | superseded
    list_only: Mapped[bool] = mapped_column(Boolean, server_default=false(), default=False)
    title: Mapped[str] = mapped_column(String(300))
    meal_ids: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list
    )
    conversation_id: Mapped[uuid.UUID | None] = _fk("conversations.id")
    turn_message_id: Mapped[uuid.UUID | None] = _fk("conversation_messages.id")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    applied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    discarded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    rows: Mapped[list["ChangeCardRow"]] = relationship(
        lazy="raise", order_by="ChangeCardRow.position"
    )


class ChangeCardRow(UUIDMixin, Base):
    __tablename__ = "change_card_rows"
    __table_args__ = (
        CheckConstraint("kind IN ('pantry', 'list', 'unlist')", name="ck_card_row_kind"),
        CheckConstraint(
            f"(to_status IS NULL OR to_status IN {_STATI}) "
            f"AND (before_status IS NULL OR before_status IN {_STATI})",
            name="ck_card_row_status",
        ),
        CheckConstraint(
            "kind <> 'pantry' OR to_status IS NOT NULL", name="ck_card_row_pantry_has_status"
        ),
    )

    card_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("change_cards.id", ondelete="CASCADE")
    )
    position: Mapped[int] = mapped_column(Integer)
    kind: Mapped[str] = mapped_column(String(10))  # pantry | list | unlist
    label: Mapped[str] = mapped_column(String(300))
    pantry_item_id: Mapped[uuid.UUID | None] = _fk("pantry_items.id")
    ingredient_id: Mapped[uuid.UUID | None] = _fk("ingredients.id")
    shopping_item_id: Mapped[uuid.UUID | None] = _fk("shopping_list_items.id")
    to_status: Mapped[str | None] = mapped_column(String(10), nullable=True)
    before_status: Mapped[str | None] = mapped_column(String(10), nullable=True)
    checked: Mapped[bool] = mapped_column(Boolean)
    editable: Mapped[bool] = mapped_column(Boolean, server_default=true(), default=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    meal_ids: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list
    )
    applied: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    list_added: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    source_row_id: Mapped[uuid.UUID | None] = _fk("change_card_rows.id")
    # Tutte le righe della scheda diretta da cui viene un'inversa (id come stringhe).
    source_row_ids: Mapped[list[str]] = mapped_column(
        JSONB, server_default=text("'[]'::jsonb"), default=list
    )
    reversed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
