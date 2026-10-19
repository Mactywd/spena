"""L'attività che arriva da Health Connect via HC Webhook (H2, migrazione 0018).

I giorni (`day`) sono giorni di calendario a Roma, come la scadenza (`PANTRY_TZ`): li
calcola `app.domain.activity` dall'istante, e si scrivono accanto a lui perché P2 conterà
per giorno. Le righe le scrive solo `app.services.activity`.
"""

from datetime import date, datetime

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Float,
    Integer,
    SmallInteger,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.db.models.base import UUIDMixin


class ActivityToken(Base):
    """La chiave del webhook: una sola, quindi una riga sola (`id = 1`).

    Si tiene l'impronta (`app.core.webhook_token.token_hash`), mai la chiave: si vede una
    volta, quando si crea, e chi legge il database non la ritrova.
    """

    __tablename__ = "activity_tokens"
    __table_args__ = (CheckConstraint("id = 1", name="ck_activity_token_single"),)

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ActivityStepsDay(Base):
    """Il totale dei passi di un giorno di Roma, con l'intervallo che copre.

    L'intervallo serve a `merge_steps_day`: un totale arrivato dopo sostituisce questo
    solo se ne copre almeno l'intervallo, e i due non si sommano mai (spec H2 §3.2).
    """

    __tablename__ = "activity_steps_days"
    __table_args__ = (
        CheckConstraint("steps >= 0", name="ck_activity_steps_non_negative"),
        CheckConstraint("covered_to > covered_from", name="ck_activity_steps_span"),
    )

    day: Mapped[date] = mapped_column(Date, primary_key=True)
    steps: Mapped[int] = mapped_column(Integer, nullable=False)
    covered_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    covered_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ActivityExercise(UUIDMixin, Base):
    """Un allenamento, uno per app (`source`, il `data_origin` di Health Connect) e inizio.

    `exercise_type` è la costante intera di Health Connect, non tradotta: è la chiave su
    cui P2 metterà i MET. Il nome a video lo dà `exercise_label`.
    """

    __tablename__ = "activity_exercises"
    __table_args__ = (
        UniqueConstraint("source", "started_at", name="uq_activity_exercises_source_started_at"),
        CheckConstraint("ended_at >= started_at", name="ck_activity_exercise_span"),
    )

    source: Mapped[str] = mapped_column(String(120), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    ended_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    exercise_type: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    distance_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    # i passi dentro l'allenamento: a P2 servono per non contarli due volte col totale
    steps: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ActivityWeight(UUIDMixin, Base):
    __tablename__ = "activity_weights"
    __table_args__ = (
        UniqueConstraint("source", "measured_at", name="uq_activity_weights_source_measured_at"),
        CheckConstraint("kilograms > 0", name="ck_activity_weight_positive"),
    )

    source: Mapped[str] = mapped_column(String(120), nullable=False)
    measured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    kilograms: Mapped[float] = mapped_column(Float, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class ActivitySync(UUIDMixin, Base):
    """Una sincronizzazione arrivata con la chiave giusta: com'è andata, mai cosa portava.

    `received_at` lo scrive chi chiama, non `now()`: dentro una transazione `now()` è
    fermo, e due righe della stessa prova non avrebbero un ordine.
    """

    __tablename__ = "activity_syncs"
    __table_args__ = (
        CheckConstraint("status IN ('ok', 'test', 'rejected')", name="ck_activity_sync_status"),
    )

    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    app_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    body_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    steps_days: Mapped[int] = mapped_column(Integer, nullable=False)
    exercises: Mapped[int] = mapped_column(Integer, nullable=False)
    weights: Mapped[int] = mapped_column(Integer, nullable=False)
    # i nomi delle chiavi del corpo che Spena non usa, e i problemi in italiano
    ignored_keys: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
    problems: Mapped[list[str]] = mapped_column(JSONB, nullable=False)
