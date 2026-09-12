"""Regole di dominio di Spena. Modulo puro: nessun accesso al database.

La dispensa non conosce quantità. Un ingrediente è disponibile, quasi finito o
finito, e il ruolo che ha nella ricetta decide se quello stato basta.
"""

from collections.abc import Iterable
from enum import StrEnum


class PantryStatus(StrEnum):
    AVAILABLE = "available"
    LOW = "low"
    FINISHED = "finished"


class Availability(StrEnum):
    AVAILABLE = "available"
    LOW = "low"
    MISSING = "missing"


class IngredientRole(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


def availability_of(statuses: Iterable[PantryStatus]) -> Availability:
    """Più voci di dispensa possono riferirsi allo stesso ingrediente.

    Vince la migliore: se un vasetto è pieno, non importa che l'altro sia agli
    sgoccioli. Le voci finite non contano, e l'assenza di voci equivale a
    ingrediente mancante.
    """
    best = Availability.MISSING
    for status in statuses:
        if status is PantryStatus.AVAILABLE:
            return Availability.AVAILABLE
        if status is PantryStatus.LOW:
            best = Availability.LOW
    return best


def is_satisfied(role: IngredientRole, availability: Availability) -> bool:
    """Un principale esige abbondanza, un secondario si accontenta del fondo."""
    if role is IngredientRole.PRIMARY:
        return availability is Availability.AVAILABLE
    return availability in (Availability.AVAILABLE, Availability.LOW)


def missing_count(requirements: Iterable[tuple[IngredientRole, Availability]]) -> int:
    return sum(1 for role, availability in requirements if not is_satisfied(role, availability))


def is_cookable(requirements: Iterable[tuple[IngredientRole, Availability]]) -> bool:
    return missing_count(requirements) == 0
