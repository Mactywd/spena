"""L'attività da Health Connect (H2): ricevere quel che manda HC Webhook, e mostrarlo.

Nessuna funzione qui fa commit: lo fa la rotta, una volta per richiesta, così il registro
della sincronizzazione e i dati che racconta entrano insieme o per niente.
"""

from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.webhook_token import looks_like_token, token_matches
from app.db.models.activity import ActivityToken
from app.domain.activity import ParsedPayload
from app.repositories.activity import (
    get_token,
    lock_webhook,
    prune_syncs,
    record_sync,
    upsert_exercise,
    upsert_steps_day,
    upsert_weight,
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
