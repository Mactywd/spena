"""Regole di dominio di Spena. Modulo puro: nessun accesso al database.

La dispensa non conosce quantità. Un ingrediente è disponibile, quasi finito o
finito, e il ruolo che ha nella ricetta decide se quello stato basta.
"""

import re
from collections.abc import Iterable
from datetime import UTC, date, datetime
from enum import StrEnum
from zoneinfo import ZoneInfo


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


class IngredientKind(StrEnum):
    """Se una voce dell'anagrafica è cibo o no.

    Non lo sceglie nessuno a mano: discende dal reparto, e l'unico posto che lo
    calcola è `kind_for_category` qui sotto.
    """

    FOOD = "food"
    NON_FOOD = "non_food"


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


def within_budget(
    requirements: Iterable[tuple[IngredientRole, Availability]], budget: int
) -> bool:
    """Se quel che manca sta dentro quante cose si è disposti a comprare.

    La soglia si applica *dopo* la regola del ruolo, non al posto suo: «al massimo
    due mancanti» vuol dire due cose da comprare davvero, non due righe gialle — un
    secondario quasi finito non manca e non consuma soglia.
    """
    return missing_count(requirements) <= budget


def is_cookable(requirements: Iterable[tuple[IngredientRole, Availability]]) -> bool:
    """Il caso `budget = 0`, e scritto così di proposito.

    «Cucinabile» resta una parola sola in tutta l'app: il giorno in cui la regola di
    `is_satisfied` cambiasse, la risposta al filtro e la risposta alla scheda non
    potrebbero divergere, perché sono la stessa funzione.
    """
    return within_budget(requirements, 0)


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


# La scadenza: un segnale, non uno stato. Sta accanto a `status_for_fill` perché è
# lo stesso genere di cosa — un fatto che il client chiede invece di calcolare — ma
# non entra in quella funzione e non ne esce: una voce scaduta resta disponibile, e
# nessuna ricetta diventa non cucinabile di notte senza che nessuno abbia toccato
# niente. È la decisione D5 di docs/prossimi-passi.md.
EXPIRY_SOON_DAYS = 7

# Dove sta la dispensa. Tutto il resto del backend lavora in UTC ed è giusto così:
# sono istanti. Questo è un giorno di calendario, e un giorno in UTC non è il giorno
# di chi apre l'app a Milano a mezzanotte e mezza.
PANTRY_TZ = ZoneInfo("Europe/Rome")


class ExpiryState(StrEnum):
    SOON = "soon"
    EXPIRED = "expired"


def expiry_state(expires_on: date | None, today: date) -> ExpiryState | None:
    """Nessuna data → nessun segnale: è il caso normale e non deve costare niente.

    `today` entra come argomento invece di essere letto qui dentro: è quel che rende
    questa funzione provabile su date scritte a mano, e quel che impedisce
    all'orologio di entrare in un modulo puro.
    """
    if expires_on is None:
        return None
    if expires_on < today:
        return ExpiryState.EXPIRED
    if (expires_on - today).days <= EXPIRY_SOON_DAYS:
        return ExpiryState.SOON
    return None


def today_in_pantry(now: datetime | None = None) -> date:
    """Che giorno è, dove sta la dispensa."""
    return (now or datetime.now(UTC)).astimezone(PANTRY_TZ).date()


# Le categorie i cui ingredienti si riducono senza snaturare il piatto. Sono valori
# di IngredientCategory, scritti come stringhe perché questo modulo è puro e non
# importa i modelli; un test del dominio li confronta con l'enum per impedire
# che diventino nomi di categorie che non esistono più.
SECONDARY_CATEGORIES = frozenset({"spezie", "condimenti"})

# I reparti che non sono cibo. La partizione è dichiarata su questa metà e non
# sull'altra perché è la metà che cresce: un reparto alimentare nuovo è cibo per
# omissione, ed è la risposta giusta. Stringhe e non valori dell'enum, come
# SECONDARY_CATEGORIES qui sotto e per la stessa ragione: questo modulo è puro e
# non importa i modelli delle tabelle.
NON_FOOD_CATEGORIES = frozenset({"casa", "igiene"})


def kind_for_category(category: str) -> IngredientKind:
    """A quale mondo appartiene una voce, dedotto dalla sua corsia.

    Il reparto lo sceglie la persona; questo asse discende, e non c'è quindi modo
    di creare una riga che dica insieme «igiene» e «è cibo». Stessa forma di
    `status_for_fill`: là una posizione del cursore si proietta nei tre stati su
    cui ragiona il resto dell'app, qui una corsia del supermercato si proietta
    nell'asse su cui ragionano le guardie delle ricette.
    """
    if category in NON_FOOD_CATEGORIES:
        return IngredientKind.NON_FOOD
    return IngredientKind.FOOD


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
