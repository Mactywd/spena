"""Le conversazioni con Claude e i loro messaggi (spec 2026-11-12 §4.3).

Una conversazione è di due tipi: `dish` (la chat di un pasto, una sola per pasto,
`uq_conversations_meal`) o `planning` (la pianificazione della settimana, senza pasto).
I messaggi stanno in spena, non nelle sessioni dell'SDK, perché la cronologia sopravviva
ai riavvii del container: ogni giro ricostruisce il contesto da qui (decisione 9).
"""

import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.db.models.base import TimestampMixin, UUIDMixin
from app.db.models.meal import Meal


class ConversationKind(StrEnum):
    DISH = "dish"
    PLANNING = "planning"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"


class MessageStatus(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"


class Conversation(UUIDMixin, TimestampMixin, Base):
    """Due tipi, una chat del piatto per pasto; i messaggi in spena (decisione 9)."""

    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("meal_id", name="uq_conversations_meal"),
        CheckConstraint("kind IN ('dish', 'planning')", name="ck_conversation_kind"),
        CheckConstraint(
            "kind <> 'dish' OR meal_id IS NOT NULL", name="ck_conversation_dish_has_meal"
        ),
        CheckConstraint(
            "kind <> 'planning' OR meal_id IS NULL", name="ck_conversation_planning_no_meal"
        ),
        CheckConstraint(
            "(focus_day IS NULL) = (focus_slot IS NULL) "
            "AND (focus_slot IS NULL OR focus_slot IN ('lunch', 'dinner'))",
            name="ck_conversation_focus",
        ),
    )

    kind: Mapped[str] = mapped_column(String(10))  # dish | planning
    meal_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("meals.id", ondelete="CASCADE"), nullable=True
    )
    # il posto (data + pranzo/cena) su cui sta lavorando la chat di pianificazione
    focus_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    focus_slot: Mapped[str | None] = mapped_column(String(10), nullable=True)  # lunch | dinner

    meal: Mapped[Meal | None] = relationship(lazy="raise")
    messages: Mapped[list["ConversationMessage"]] = relationship(
        lazy="raise", order_by="ConversationMessage.created_at"
    )


class ConversationMessage(UUIDMixin, Base):
    __tablename__ = "conversation_messages"
    __table_args__ = (
        CheckConstraint("role IN ('user', 'assistant')", name="ck_message_role"),
        CheckConstraint("status IN ('pending', 'sent', 'failed')", name="ck_message_status"),
        Index("ix_conversation_messages_conversation_created", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    role: Mapped[str] = mapped_column(String(10))  # user | assistant
    text: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(
        String(10), server_default="sent", default="sent"
    )  # pending | sent | failed
    failure: Mapped[str | None] = mapped_column(String(20), nullable=True)
    notice: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation_messages.id", ondelete="CASCADE"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
