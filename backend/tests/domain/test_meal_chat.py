"""Le regole pure della chat dei pasti: gli avvisi, chi può chattare, il messaggio rimasto appeso."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest

from app.domain.meal_chat import (
    BUSY_NOTICE,
    FailureKind,
    can_chat,
    failure_notice,
    pending_is_stale,
)
from app.domain.meals import MealStatus

NOW = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)
LIMITE = "Claude non risponde: hai raggiunto il limite di frequenza della chiave API, "


@pytest.mark.parametrize(
    ("resets_at", "expected"),
    [
        (datetime(2026, 11, 12, 17, 40, tzinfo=UTC), LIMITE + "riprova dopo le 18:40"),
        (datetime(2026, 11, 12, 23, 30, tzinfo=UTC), LIMITE + "riprova domani dopo le 0:30"),
        (datetime(2026, 11, 14, 8, 0, tzinfo=UTC), LIMITE + "riprova dopo le 9:00 del 14 novembre"),
        (None, LIMITE + "riprova tra qualche minuto."),
    ],
)
def test_l_avviso_del_limite(resets_at, expected):
    assert failure_notice(FailureKind.RATE_LIMIT, resets_at, NOW) == expected


def test_gli_altri_avvisi():
    esatti = {
        FailureKind.NOT_CONFIGURED: "Claude non è collegato: manca la chiave API sul server.",
        FailureKind.CREDIT: "Claude non risponde: il credito della chiave API è finito. "
        "Va ricaricato nella console di Anthropic.",
        FailureKind.AUTH: "Claude non risponde: la chiave API non vale più (sbagliata o revocata). "
        "Va sostituita nel .env del server.",
        FailureKind.MAX_TURNS: "Claude si è fermato prima di finire: questo messaggio gli "
        "chiedeva troppi passaggi. Scrivigli come andare avanti.",
        FailureKind.TIMEOUT: "Claude non risponde: ci sta mettendo troppo. Riprova tra poco.",
        FailureKind.UNAVAILABLE: "Claude non risponde in questo momento. Riprova tra poco.",
        FailureKind.INTERRUPTED: "La risposta si è interrotta. Riprova.",
    }
    assert set(esatti) | {FailureKind.RATE_LIMIT} == set(FailureKind)
    for kind, frase in esatti.items():
        assert failure_notice(kind, None, NOW) == frase
    assert BUSY_NOTICE == "Claude sta ancora rispondendo al messaggio di prima."


@pytest.mark.parametrize(
    ("status", "away", "leftover", "expected"),
    [
        (MealStatus.OFFICIAL, False, None, True),
        (MealStatus.DRAFT, False, None, False),
        (MealStatus.OFFICIAL, True, None, False),
        (MealStatus.OFFICIAL, False, uuid4(), False),
    ],
)
def test_can_chat(status, away, leftover, expected):
    meal = SimpleNamespace(status=status.value, away=away, leftover_of_id=leftover)
    assert can_chat(meal) is expected


def test_pending_is_stale():
    creato = datetime(2026, 11, 12, 15, 0, tzinfo=UTC)
    assert not pending_is_stale(creato, datetime(2026, 11, 12, 15, 4, 59, tzinfo=UTC), 240)
    assert pending_is_stale(creato, datetime(2026, 11, 12, 15, 5, 1, tzinfo=UTC), 240)
