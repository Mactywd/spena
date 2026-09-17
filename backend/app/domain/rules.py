"""Regole di dominio di Spena. Modulo puro: nessun accesso al database.

La dispensa non conosce quantità. Un ingrediente è disponibile, quasi finito o
finito, e il ruolo che ha nella ricetta decide se quello stato basta.
"""

import re
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


# Il secondo pallino del cursore della dispensa: fin qui è «quasi finito», oltre è
# «disponibile». 30 e non 50: la zona gialla deve dire «comincia a mancare», non
# «siamo a metà».
#
# È una soglia display con una conseguenza che display non è: `low` è l'unico stato
# che cambia la risposta a «questa ricetta si può cucinare?» (vedi `is_satisfied`),
# quindi spostare questo numero sposta quali ricette risultano cucinabili. Va fatto
# sapendolo, e non in un foglio di stile.
LOW_MAX_FILL = 30


def status_for_fill(fill_percent: int) -> PantryStatus:
    """Dove sta il cursore → quale dei tre stati è la verità.

    La posizione è un'indicazione a occhio, utile in negozio per ricordarsi quanto
    ne resta; lo stato è l'unico giudizio su cui il resto dell'app ragiona. Vive qui
    e non nel frontend per la ragione di ogni altra regola di questo modulo: il
    client chiede, non calcola.
    """
    if fill_percent <= 0:
        return PantryStatus.FINISHED
    if fill_percent <= LOW_MAX_FILL:
        return PantryStatus.LOW
    return PantryStatus.AVAILABLE


# Le categorie i cui ingredienti si riducono senza snaturare il piatto. Sono valori
# di IngredientCategory, scritti come stringhe perché questo modulo è puro e non
# importa i modelli; un test del dominio li confronta con l'enum per impedire
# che diventino nomi di categorie che non esistono più.
SECONDARY_CATEGORIES = frozenset({"spezie", "condimenti"})


def default_role(category: str, quantity_text: str | None) -> IngredientRole:
    """Il ruolo dedotto per una riga di ricetta importata.

    La fonte non dichiara i ruoli, e il ruolo è ciò che rende utile lo stato «quasi
    finito»: un pomodoro agli sgoccioli non fa una pasta al pomodoro ma fa un
    soffritto. Due segnali, entrambi presenti nei dati veri: una dose «quanto
    basta» dice che l'ingrediente si aggiusta a piacere, e spezie e condimenti lo
    sono per natura.

    Dove il buon senso culinario non segue la categoria — l'aglio è verdura e quasi
    sempre secondario — la correzione arriva da `ImportTerm.role_override`, deciso
    una volta sola dalla persona che revisiona il termine.
    """
    compact = re.sub(r"[\s.]+", "", (quantity_text or "").lower())
    if compact.startswith("qb") or compact in {"apiacere", "quantobasta"}:
        return IngredientRole.SECONDARY
    if category in SECONDARY_CATEGORIES:
        return IngredientRole.SECONDARY
    return IngredientRole.PRIMARY
