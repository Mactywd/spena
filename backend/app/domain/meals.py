"""Le regole pure dei pasti (spec 2026-11-12 §4): il posto, la settimana, la bozza.

Niente database: il posto di un pasto è una data più pranzo o cena, e qui si decide solo
l'ordine fra posti e che cosa è «non registrato».
"""

from datetime import date, timedelta
from enum import StrEnum

# Un avanzo si sceglie fra i pasti dei giorni prima del suo posto, non oltre questi
LEFTOVER_WINDOW_DAYS = 3


class MealSlot(StrEnum):
    LUNCH = "lunch"
    DINNER = "dinner"


class MealStatus(StrEnum):
    DRAFT = "draft"
    OFFICIAL = "official"


def week_bounds(day: date) -> tuple[date, date]:
    """Il lunedì e la domenica della settimana di `day`."""
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def slot_rank(slot: MealSlot) -> int:
    """Pranzo prima di cena."""
    return 0 if slot == MealSlot.LUNCH else 1


def is_before(day: date, slot: MealSlot, other_day: date, other_slot: MealSlot) -> bool:
    """Il primo posto viene strettamente prima del secondo."""
    return (day, slot_rank(slot)) < (other_day, slot_rank(other_slot))


def is_unrecorded(status: MealStatus, day: date, today: date) -> bool:
    """Una bozza nel passato: nessuno l'ha confermata, e a video è «non registrata»."""
    return status == MealStatus.DRAFT and day < today
