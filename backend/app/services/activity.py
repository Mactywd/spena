"""L'attività da Health Connect (H2): ricevere quel che manda HC Webhook, e mostrarlo.

Nessuna funzione qui fa commit: lo fa la rotta, una volta per richiesta, così il registro
della sincronizzazione e i dati che racconta entrano insieme o per niente.
"""

from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.webhook_token import looks_like_token, new_token, token_hash, token_matches
from app.db.models.activity import (
    ActivityExercise,
    ActivitySync,
    ActivityToken,
    ActivityWeight,
)
from app.domain.activity import (
    ParsedPayload,
    exercise_label,
    hc_type_label,
    rome_clock,
    rome_day,
    source_label,
)
from app.domain.rules import today_in_pantry
from app.repositories.activity import (
    exercises_since,
    get_token,
    latest_sync,
    latest_weights,
    lock_webhook,
    prune_syncs,
    record_sync,
    save_token,
    steps_between,
    upsert_exercise,
    upsert_steps_day,
    upsert_weight,
)
from app.schemas.activity import (
    ActivityOut,
    ConnectionOut,
    ExerciseOut,
    StepsDayOut,
    SyncOut,
    WeightOut,
)


async def authenticate_webhook(
    session: AsyncSession, candidate: str | None
) -> ActivityToken | None:
    """La riga della chiave se `candidate` è quella giusta, `None` altrimenti.

    Una forma sbagliata si rifiuta senza leggere il database; senza una chiave configurata
    il confronto si fa lo stesso (`token_matches`), così il tempo non dice se c'è.
    """
    if candidate is None or not looks_like_token(candidate):
        return None
    stored = await get_token(session)
    if not token_matches(candidate, stored.token_hash if stored else None):
        return None
    return stored


async def receive_payload(
    session: AsyncSession, parsed: ParsedPayload, body_bytes: int, now: datetime
) -> dict[str, object]:
    """Salva quel che `parse_payload` ha capito, registra la sincronizzazione, e risponde.

    La prova di HC Webhook («Testa Webhook», `"test": true`) porta dati inventati: non si
    salva niente, e i problemi non si contano (non sono quelli del telefono di Mattia).
    """
    await lock_webhook(session)
    if parsed.is_test:
        saved = {"steps_days": 0, "exercises": 0, "weights": 0}
        problems: list[str] = []
    else:
        for reading in parsed.steps_days:
            await upsert_steps_day(session, reading)
        for exercise in parsed.exercises:
            await upsert_exercise(session, exercise)
        for weight in parsed.weights:
            await upsert_weight(session, weight)
        saved = {
            "steps_days": len(parsed.steps_days),
            "exercises": len(parsed.exercises),
            "weights": len(parsed.weights),
        }
        problems = parsed.problems
    await record_sync(
        session,
        status="test" if parsed.is_test else "ok",
        received_at=now,
        body_bytes=body_bytes,
        app_version=parsed.app_version,
        sent_at=parsed.sent_at,
        ignored_keys=parsed.ignored_keys,
        problems=problems,
        **saved,
    )
    await prune_syncs(session)
    return {
        "test": parsed.is_test,
        "saved": saved,
        "ignored": parsed.ignored_keys,
        "problems": problems,
    }


async def reject_payload(
    session: AsyncSession, problem: str, body_bytes: int, now: datetime
) -> None:
    """Un corpo autenticato ma rifiutato: si registra, perché in «Attività» si veda."""
    await lock_webhook(session)
    await record_sync(
        session, status="rejected", received_at=now, body_bytes=body_bytes, problems=[problem]
    )
    await prune_syncs(session)


SUMMARY_DAYS = 7
EXERCISES_SHOWN = 20
WEIGHTS_SHOWN = 5
# Oltre, «Attività» avvisa: con l'intervallo di HC Webhook a 15 minuti o un'ora, un
# giorno intero senza niente vuol dire che Android lo sta fermando.
STALE_AFTER = timedelta(hours=24)


def _moment(instant: datetime) -> tuple[date, str]:
    return rome_day(instant), rome_clock(instant)


def _sync_out(sync: ActivitySync, now: datetime) -> SyncOut:
    day, clock = _moment(sync.received_at)
    return SyncOut(
        day=day,
        time=clock,
        status=sync.status,
        stale=now - sync.received_at > STALE_AFTER,
        steps_days=sync.steps_days,
        exercises=sync.exercises,
        weights=sync.weights,
        ignored=[hc_type_label(key) for key in sync.ignored_keys],
        problems=list(sync.problems),
    )


def _exercise_out(exercise: ActivityExercise) -> ExerciseOut:
    seconds = (exercise.ended_at - exercise.started_at).total_seconds()
    distance_km = round(exercise.distance_m / 1000, 1) if exercise.distance_m else None
    return ExerciseOut(
        day=exercise.day,
        time=rome_clock(exercise.started_at),
        label=exercise_label(exercise.exercise_type),
        title=exercise.title,
        minutes=round(seconds / 60),
        # zero metri, o pochi metri che arrotondano a zero, è «nessuna distanza», non «0,0 km»
        distance_km=distance_km or None,
        source=source_label(exercise.source),
    )


def _weight_out(weight: ActivityWeight) -> WeightOut:
    day, clock = _moment(weight.measured_at)
    return WeightOut(day=day, time=clock, kilograms=round(weight.kilograms, 1))


def _connection_out(token: ActivityToken | None) -> ConnectionOut:
    if token is None:
        return ConnectionOut(
            has_token=False,
            created_day=None,
            created_time=None,
            last_used_day=None,
            last_used_time=None,
        )
    created_day, created_time = _moment(token.created_at)
    used = _moment(token.last_used_at) if token.last_used_at else (None, None)
    return ConnectionOut(
        has_token=True,
        created_day=created_day,
        created_time=created_time,
        last_used_day=used[0],
        last_used_time=used[1],
    )


async def activity_summary(session: AsyncSession, now: datetime) -> ActivityOut:
    """Quel che mostra «Attività»: tutto in giorni e ore di Roma, coi nomi a video."""
    today = today_in_pantry(now)
    first = today - timedelta(days=SUMMARY_DAYS - 1)
    steps = await steps_between(session, first, today)
    sync = await latest_sync(session)
    return ActivityOut(
        today=today,
        last_sync=_sync_out(sync, now) if sync is not None else None,
        steps_days=[
            StepsDayOut(day=day, steps=steps.get(day))
            for day in (today - timedelta(days=back) for back in range(SUMMARY_DAYS))
        ],
        exercises=[
            _exercise_out(exercise)
            for exercise in await exercises_since(session, first, EXERCISES_SHOWN)
        ],
        weights=[_weight_out(weight) for weight in await latest_weights(session, WEIGHTS_SHOWN)],
        connection=_connection_out(await get_token(session)),
    )


async def regenerate_token(session: AsyncSession, now: datetime) -> str:
    """Una chiave nuova: si torna a chi la chiede, e nel database va solo l'impronta."""
    token = new_token()
    await save_token(session, token_hash(token), now)
    return token
