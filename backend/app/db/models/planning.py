"""Le proposte di pasti di Claude nella chat di pianificazione (spec 2026-11-12).

Una proposta è un elenco di pasti per posti della settimana, `rows`: ogni elemento è
`{"day": "AAAA-MM-GG", "slot": "lunch"|"dinner", "dish", "sides", "meal_id": null|uuid}`.
`meal_id` resta nullo finché la proposta è aperta e si riempie quando Mattia la mette
in settimana (`placed`); una nuova proposta rende `superseded` la precedente.
"""

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.db.models.base import UUIDMixin


class ProposalKind(StrEnum):
    OFFICIAL = "official"
    DRAFT = "draft"


class ProposalStatus(StrEnum):
    OPEN = "open"
    PLACED = "placed"
    SUPERSEDED = "superseded"


class MealProposal(UUIDMixin, Base):
    __tablename__ = "meal_proposals"
    __table_args__ = (
        CheckConstraint("kind IN ('official', 'draft')", name="ck_proposal_kind"),
        CheckConstraint(
            "status IN ('open', 'placed', 'superseded')", name="ck_proposal_status"
        ),
        Index("ix_meal_proposals_conversation_created", "conversation_id", "created_at"),
    )

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("conversations.id", ondelete="CASCADE")
    )
    turn_message_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("conversation_messages.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(String(10))  # official | draft
    status: Mapped[str] = mapped_column(
        String(12), server_default="open", default="open"
    )  # open | placed | superseded
    rows: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    placed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
