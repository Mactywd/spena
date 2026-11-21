from datetime import UTC, date, datetime

import pytest

from app.domain.meals import (
    MealSlot,
    MealStatus,
    is_before,
    is_unrecorded,
    place_words,
    week_bounds,
)
from app.domain.rules import today_in_pantry


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        # il 9 novembre 2026 è lunedì (il 10 della scheda è un martedì)
        (date(2026, 11, 9), (date(2026, 11, 9), date(2026, 11, 15))),
        (date(2026, 11, 15), (date(2026, 11, 9), date(2026, 11, 15))),
        (date(2026, 11, 12), (date(2026, 11, 9), date(2026, 11, 15))),
        (date(2026, 12, 31), (date(2026, 12, 28), date(2027, 1, 3))),
    ],
)
def test_week_bounds(day, expected):
    assert week_bounds(day) == expected


L, D = MealSlot.LUNCH, MealSlot.DINNER


@pytest.mark.parametrize(
    ("a", "b", "expected"),
    [
        ((10, L), (10, D), True),
        ((10, D), (10, L), False),
        ((10, D), (10, D), False),
        ((9, D), (10, L), True),
        ((11, L), (10, D), False),
    ],
)
def test_is_before(a, b, expected):
    assert is_before(date(2026, 11, a[0]), a[1], date(2026, 11, b[0]), b[1]) is expected


@pytest.mark.parametrize(
    ("status", "day", "expected"),
    [
        (MealStatus.DRAFT, date(2026, 11, 11), True),
        (MealStatus.DRAFT, date(2026, 11, 12), False),
        (MealStatus.DRAFT, date(2026, 11, 13), False),
        (MealStatus.OFFICIAL, date(2026, 11, 11), False),
    ],
)
def test_is_unrecorded(status, day, expected):
    assert is_unrecorded(status, day, date(2026, 11, 12)) is expected


def test_la_settimana_di_oggi_e_quella_di_roma():
    today = today_in_pantry(datetime(2026, 11, 15, 23, 30, tzinfo=UTC))
    assert week_bounds(today) == (date(2026, 11, 16), date(2026, 11, 22))


def test_place_words():
    assert place_words(date(2026, 11, 10), MealSlot.LUNCH) == "martedì pranzo"
    assert place_words(date(2026, 11, 15), MealSlot.DINNER) == "domenica cena"
