"""Le dosi delle ricette: leggerle, scalarle, riscriverle. Modulo puro.

La dispensa non conosce quantità e non ne conoscerà mai: questo modulo esiste per
le ricette e basta (decisione fondante 1, ristretta il 2026-09-17). `quantity_text`
resta la verità da mostrare; qui si ricava quel che serve per riporzionare, e
quando non si ricava non si inventa.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation, ROUND_HALF_UP

# tre decimali bastano a un terzo, e `Numeric` invece di `Float` perché un giorno
# queste righe si sommeranno per la nutrizione
PRECISION = Decimal("0.001")

# Quanto può essere lunga la parola di un'unità. La costante nasce qui, nel modulo
# puro, e `app/db/models/unit.py` la importa da qui per dimensionare `units.key`:
# tenerne due copie vorrebbe dire che un giorno il parser accetta una parola che la
# colonna non regge, e quel giorno la scrittura intera fallisce. È già successo in
# prova: «2 cucchiai dioliaextravergineditolivapugliese» senza uno spazio dava una
# chiave di 42 caratteri, e Postgres rifiutava tutta la ricetta con un DataError che
# nessun `except` di questo progetto intercetta.
UNIT_MAX_LENGTH = 30

# numero in testa (intero, decimale con virgola o punto, frazione), e subito dopo
# la parola dell'unità se c'è. Tutto quel che segue è prosa e non ci riguarda:
# «1 litro di brodo» è un litro, e «di brodo» sta già in quantity_text.
_DOSE = re.compile(
    r"^\s*(?:(?P<num>\d+)\s*/\s*(?P<den>\d+)|(?P<dec>\d+(?:[.,]\d+)?))"
    r"\s*(?P<unit>[^\W\d_]+)?",
    re.UNICODE,
)


@dataclass(frozen=True)
class UnitForms:
    """Come si scrive un'unità. `singular`/`plural` sono `None` finché nessuno
    ha deciso: allora si mostra `key`, cioè la parola come è arrivata."""

    key: str
    singular: str | None = None
    plural: str | None = None


def parse_quantity(text: str | None) -> tuple[Decimal | None, str | None]:
    """Il numero e la parola dell'unità dentro una dose scritta a mano.

    Torna `(None, None)` per tutto ciò che non comincia con un numero — «q.b.»,
    «abbondante», «facoltativo» — e non solleva mai: una dose che non si capisce
    non è un errore, è una dose che non si scala.

    Lo stesso vale per le due cose che si capirebbero male: una dose che continua
    con un altro numero («2 1/2 cucchiai») e una parola d'unità più lunga di
    `UNIT_MAX_LENGTH`. Nessuna delle due si scala, e dirlo è meglio che scalarle.
    """
    if not text:
        return (None, None)

    # `merge_quantities` unisce con « + » due dosi della stessa fonte finite sullo
    # stesso ingrediente («500 g + 50 g»). Sommare è giusto solo a unità uguale.
    pieces = [_parse_one(piece) for piece in text.split("+")]
    if any(value is None for value, _ in pieces):
        return (None, None)
    units = {unit for _, unit in pieces}
    if len(units) != 1:
        return (None, None)
    total = sum((value for value, _ in pieces), start=Decimal(0))
    return (total.quantize(PRECISION).normalize(), units.pop())


def _parse_one(piece: str) -> tuple[Decimal | None, str | None]:
    found = _DOSE.match(piece)
    if not found:
        return (None, None)
    try:
        if found["den"] is not None:
            value = (Decimal(found["num"]) / Decimal(found["den"])).quantize(PRECISION)
        else:
            value = Decimal(found["dec"].replace(",", "."))
    except (InvalidOperation, DivisionByZero, ZeroDivisionError):
        return (None, None)
    unit = found["unit"].lower() if found["unit"] else None
    if unit is None and piece[found.end():][:1].isdigit():
        # «2 1/2 cucchiai»: il numero in testa è metà della dose, non la dose. Dire
        # 2 invece di 2,5 sarebbe il riporziona sbagliato in silenzio che la spec
        # §4.1 mette fra le cose che non devono succedere mai.
        return (None, None)
    if unit is not None and len(unit) > UNIT_MAX_LENGTH:
        # una parola più lunga della colonna che la depositerà non è un'unità: è un
        # incollaggio senza spazio. Rifiutarla qui è quel che tiene il parser
        # dentro il suo contratto — una dose che nessuno sa leggere non si scala —
        # e insieme quel che impedisce a una riga sola di far fallire la scrittura
        # di tutta la ricetta più a valle.
        return (None, None)
    return (value, unit)


def scale_quantity(value: Decimal, factor: Decimal) -> Decimal:
    return (value * factor).quantize(PRECISION, rounding=ROUND_HALF_UP).normalize()


def render_quantity(value: Decimal, unit: UnitForms | None) -> str:
    """La dose riscritta dopo una scala. Non si usa a 1×: là si mostra
    `quantity_text`, che dice la verità meglio di quanto sappiamo riscriverla."""
    number = format(value.normalize(), "f").replace(".", ",")
    if unit is None:
        return number
    word = (unit.singular if value == 1 else unit.plural) or unit.key
    return f"{number} {word}"


# Il secondo modo del riporziona (R2): la dose di una riga fissata a mano, e il resto
# che la segue. Quanto ci si può allontanare dalla ricetta: lo stesso che lo stepper
# delle porzioni permette al massimo (da 1 a 50 porzioni su ricette che ne dicono da 1
# a 50), cioè cinquanta volte in su o in giù. Una regola sola per i due modi; oltre, è
# quasi sempre uno zero di troppo, e le altre righe diventerebbero dosi che non si pesano.
ANCHOR_MAX_FACTOR = Decimal(50)

# Il tetto, escluso, di quel che si può scrivere come dose. Sta sopra la dose più grande
# che la colonna regge (99999,999) per cinquanta volte: non taglia mai una richiesta che
# il fattore accetterebbe, ferma solo i numeri che non sono dosi.
ANCHOR_AMOUNT_CEILING = Decimal(10_000_000)


class AnchorOutOfRange(ValueError):
    """La dose scritta porta la ricetta oltre `ANCHOR_MAX_FACTOR` volte la sua.

    Porta i due estremi già scalati, `low` e `high`: chi la intercetta li scrive a
    video con l'unità della riga, che questo modulo non conosce."""

    def __init__(self, low: Decimal, high: Decimal) -> None:
        super().__init__(f"fuori scala: fra {low} e {high}")
        self.low = low
        self.high = high


def anchor_factor(base: Decimal, amount: Decimal) -> Decimal:
    """Il fattore che porta la dose della ricetta (`base`, più di zero) a quella scritta.

    Non arrotonda: si arrotonda una volta sola, riga per riga, in `scale_quantity`. Gli
    estremi si confrontano già arrotondati come li si mostrerebbe, così la frase che li
    cita non promette un numero che poi si rifiuta."""
    low = scale_quantity(base, 1 / ANCHOR_MAX_FACTOR)
    high = scale_quantity(base, ANCHOR_MAX_FACTOR)
    if not low <= amount <= high:
        raise AnchorOutOfRange(low, high)
    return amount / base


def equivalent_servings(servings: int, factor: Decimal) -> Decimal:
    """Le porzioni che fa una ricetta da `servings` porzioni scalata di `factor`.

    Un decimale da una porzione in su, due sotto («≈ 1,5», «≈ 0,75»): sotto l'unità un
    decimale solo direbbe «≈ 0,8» di tre quarti. Metà in su, come `scale_quantity`."""
    value = Decimal(servings) * factor
    step = Decimal("0.1") if value >= 1 else Decimal("0.01")
    return value.quantize(step, rounding=ROUND_HALF_UP).normalize()


def decimal_text(value: Decimal) -> str:
    """Un decimale scritto per una macchina: col punto, senza esponente né zeri di coda.

    `str(Decimal("1E+3"))` è «1E+3», e `normalize()` di 50 è `5E+1`: nello storico e nelle
    risposte va «1000» e «50»."""
    return format(value.normalize(), "f")
