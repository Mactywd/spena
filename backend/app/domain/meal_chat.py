"""Le regole pure della chat dei pasti (spec 2026-11-12 §9): chi può chattare, gli avvisi
quando Claude non c'è, il messaggio rimasto appeso. Niente database, niente SDK."""

from datetime import datetime, timedelta
from enum import StrEnum
from typing import Protocol

from app.domain.meals import MealStatus
from app.domain.rules import PANTRY_TZ

# Un messaggio in attesa oltre il tempo massimo più questo margine, e senza un giro vivo,
# conta come interrotto.
STALE_MARGIN_SECONDS = 60
MESSAGE_MAX_CHARS = 4000
MAX_MEALS_RANGE_DAYS = 28
# Quanti messaggi salvati si rimandano a Claude in testa a ogni giro (decisione 9)
HISTORY_MESSAGES = 40
DISH_EFFORT = "medium"
DISH_MAX_TURNS = 12
PLANNING_EFFORT = "high"
PLANNING_MAX_TURNS = 20
RECIPE_EFFORT = "medium"
RECIPE_MAX_TURNS = 12

BUSY_NOTICE = "Claude sta ancora rispondendo al messaggio di prima."

_MESI = [
    "gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
    "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre",
]  # fmt: skip


class FailureKind(StrEnum):
    NOT_CONFIGURED = "not_configured"
    RATE_LIMIT = "rate_limit"
    CREDIT = "credit"
    AUTH = "auth"
    MAX_TURNS = "max_turns"
    TIMEOUT = "timeout"
    UNAVAILABLE = "unavailable"
    INTERRUPTED = "interrupted"


class _ChatMeal(Protocol):
    status: str
    away: bool
    leftover_of_id: object | None


def can_chat(meal: _ChatMeal) -> bool:
    """La chat c'è per un pasto ufficiale, non fuori casa e non avanzo (decisione 18)."""
    return (
        meal.status == MealStatus.OFFICIAL.value
        and not meal.away
        and meal.leftover_of_id is None
    )


def pending_is_stale(created_at: datetime, now: datetime, timeout_seconds: float) -> bool:
    return now - created_at > timedelta(seconds=timeout_seconds + STALE_MARGIN_SECONDS)


def _limit_notice(resets_at: datetime | None, now: datetime) -> str:
    base = "Claude non risponde: hai raggiunto il limite di frequenza della chiave API, "
    if resets_at is None:
        return base + "riprova tra qualche minuto."
    local = resets_at.astimezone(PANTRY_TZ)
    ora = f"{local.hour}:{local.minute:02d}"
    giorni = (local.date() - now.astimezone(PANTRY_TZ).date()).days
    if giorni <= 0:
        return f"{base}riprova dopo le {ora}"
    if giorni == 1:
        return f"{base}riprova domani dopo le {ora}"
    return f"{base}riprova dopo le {ora} del {local.day} {_MESI[local.month - 1]}"


def failure_notice(kind: FailureKind, resets_at: datetime | None, now: datetime) -> str:
    """La frase che Mattia legge quando Claude non risponde."""
    match kind:
        case FailureKind.NOT_CONFIGURED:
            return "Claude non è collegato: manca la chiave API sul server."
        case FailureKind.RATE_LIMIT:
            return _limit_notice(resets_at, now)
        case FailureKind.CREDIT:
            return (
                "Claude non risponde: il credito della chiave API è finito. "
                "Va ricaricato nella console di Anthropic."
            )
        case FailureKind.AUTH:
            return (
                "Claude non risponde: la chiave API non vale più (sbagliata o revocata). "
                "Va sostituita nel .env del server."
            )
        case FailureKind.MAX_TURNS:
            return (
                "Claude si è fermato prima di finire: questo messaggio gli chiedeva "
                "troppi passaggi. Scrivigli come andare avanti."
            )
        case FailureKind.TIMEOUT:
            return "Claude non risponde: ci sta mettendo troppo. Riprova tra poco."
        case FailureKind.UNAVAILABLE:
            return "Claude non risponde in questo momento. Riprova tra poco."
        case FailureKind.INTERRUPTED:
            return "La risposta si è interrotta. Riprova."
