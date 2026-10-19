"""Scrivere e rileggere l'attività da Health Connect (H2). Il commit resta di chi chiama."""

import uuid
from collections.abc import Sequence
from datetime import date, datetime

from sqlalchemy import delete, func, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.activity import (
    ActivityExercise,
    ActivityStepsDay,
    ActivitySync,
    ActivityToken,
    ActivityWeight,
)
from app.domain.activity import Exercise, StepsDay, Weight, merge_steps_day

# Le sincronizzazioni che restano nel registro: a una ogni 15 minuti sono due giorni,
# abbastanza per vedere quando le cose hanno smesso di arrivare.
SYNCS_KEPT = 200
# La chiave dell'advisory lock del webhook: un numero qualunque, purché solo suo.
WEBHOOK_LOCK_KEY = 180_018


async def lock_webhook(session: AsyncSession) -> None:
    """Un corpo alla volta, fino alla fine della transazione.

    Due invii che si sovrappongono (HC Webhook riprova dopo un timeout mentre il primo
    sta ancora scrivendo) leggerebbero lo stesso totale del giorno e l'ultimo vincerebbe
    senza averlo confrontato con l'altro.
    """
    await session.execute(text("SELECT pg_advisory_xact_lock(:key)"), {"key": WEBHOOK_LOCK_KEY})


async def get_token(session: AsyncSession) -> ActivityToken | None:
    return await session.get(ActivityToken, 1)


async def save_token(session: AsyncSession, hashed: str, now: datetime) -> ActivityToken:
    """Crea la chiave, o la sostituisce: la vecchia smette di valere subito."""
    row = await session.get(ActivityToken, 1)
    if row is None:
        row = ActivityToken(id=1, token_hash=hashed, created_at=now, last_used_at=None)
        session.add(row)
    else:
        row.token_hash = hashed
        row.created_at = now
        row.last_used_at = None
    await session.flush()
    return row


async def upsert_steps_day(session: AsyncSession, reading: StepsDay) -> None:
    row = await session.get(ActivityStepsDay, reading.day)
    if row is None:
        session.add(
            ActivityStepsDay(
                day=reading.day,
                steps=reading.steps,
                covered_from=reading.covered_from,
                covered_to=reading.covered_to,
            )
        )
        return
    stored = StepsDay(
        day=row.day, steps=row.steps, covered_from=row.covered_from, covered_to=row.covered_to
    )
    merged = merge_steps_day(stored, reading)
    row.steps = merged.steps
    row.covered_from = merged.covered_from
    row.covered_to = merged.covered_to


async def upsert_exercise(session: AsyncSession, exercise: Exercise) -> None:
    values = {
        "source": exercise.source,
        "started_at": exercise.started_at,
        "ended_at": exercise.ended_at,
        "day": exercise.day,
        "exercise_type": exercise.exercise_type,
        "title": exercise.title,
        "distance_m": exercise.distance_m,
        "steps": exercise.steps,
    }
    statement = pg_insert(ActivityExercise).values(id=uuid.uuid4(), **values)
    await session.execute(
        statement.on_conflict_do_update(
            constraint="uq_activity_exercises_source_started_at",
            set_={
                "ended_at": statement.excluded.ended_at,
                "day": statement.excluded.day,
                "exercise_type": statement.excluded.exercise_type,
                "title": statement.excluded.title,
                "distance_m": statement.excluded.distance_m,
                "steps": statement.excluded.steps,
                "updated_at": func.now(),
            },
        )
    )


async def upsert_weight(session: AsyncSession, weight: Weight) -> None:
    statement = pg_insert(ActivityWeight).values(
        id=uuid.uuid4(),
        source=weight.source,
        measured_at=weight.measured_at,
        day=weight.day,
        kilograms=weight.kilograms,
    )
    await session.execute(
        statement.on_conflict_do_update(
            constraint="uq_activity_weights_source_measured_at",
            set_={"kilograms": statement.excluded.kilograms, "updated_at": func.now()},
        )
    )


async def record_sync(
    session: AsyncSession,
    *,
    status: str,
    received_at: datetime,
    body_bytes: int,
    app_version: str | None = None,
    sent_at: datetime | None = None,
    steps_days: int = 0,
    exercises: int = 0,
    weights: int = 0,
    ignored_keys: Sequence[str] = (),
    problems: Sequence[str] = (),
) -> None:
    session.add(
        ActivitySync(
            received_at=received_at,
            status=status,
            app_version=app_version,
            sent_at=sent_at,
            body_bytes=body_bytes,
            steps_days=steps_days,
            exercises=exercises,
            weights=weights,
            ignored_keys=list(ignored_keys),
            problems=list(problems),
        )
    )
    await session.flush()


async def prune_syncs(session: AsyncSession) -> None:
    """Tiene le ultime `SYNCS_KEPT` sincronizzazioni, toglie le altre."""
    keep = (
        select(ActivitySync.id)
        .order_by(ActivitySync.received_at.desc(), ActivitySync.id.desc())
        .limit(SYNCS_KEPT)
    )
    await session.execute(delete(ActivitySync).where(ActivitySync.id.not_in(keep)))


async def latest_sync(session: AsyncSession) -> ActivitySync | None:
    return await session.scalar(
        select(ActivitySync).order_by(ActivitySync.received_at.desc()).limit(1)
    )


async def steps_between(session: AsyncSession, first: date, last: date) -> dict[date, int]:
    rows = await session.execute(
        select(ActivityStepsDay.day, ActivityStepsDay.steps).where(
            ActivityStepsDay.day >= first, ActivityStepsDay.day <= last
        )
    )
    return {day: steps for day, steps in rows.all()}


async def exercises_since(
    session: AsyncSession, first: date, limit: int
) -> list[ActivityExercise]:
    rows = await session.scalars(
        select(ActivityExercise)
        .where(ActivityExercise.day >= first)
        .order_by(ActivityExercise.started_at.desc(), ActivityExercise.source)
        .limit(limit)
    )
    return list(rows)


async def latest_weights(session: AsyncSession, limit: int) -> list[ActivityWeight]:
    rows = await session.scalars(
        select(ActivityWeight)
        .order_by(ActivityWeight.measured_at.desc(), ActivityWeight.source)
        .limit(limit)
    )
    return list(rows)
