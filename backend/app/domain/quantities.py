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
