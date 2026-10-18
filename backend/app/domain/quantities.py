"""Le dosi delle ricette: leggerle, scalarle, riscriverle. Modulo puro.

La dispensa non conosce quantità e non ne conoscerà mai: questo modulo esiste per
le ricette e basta (decisione fondante 1, ristretta il 2026-09-17). `quantity_text`
resta la verità da mostrare; qui si ricava quel che serve per riporzionare, e
quando non si ricava non si inventa.
"""

import re
from dataclasses import dataclass
from decimal import Decimal, DivisionByZero, InvalidOperation, ROUND_HALF_UP
from enum import StrEnum

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

# Le frazioni scritte con un carattere solo, come le scrive GialloZafferano («½
# cucchiaino»). Solo le tre misurate in produzione il 2026-10-13: un'altra resta una
# dose che non si legge, che è il contratto di questo parser.
VULGAR_FRACTIONS = {"½": Decimal("0.5"), "¼": Decimal("0.25"), "¾": Decimal("0.75")}
_FRACTION_CHARS = "".join(VULGAR_FRACTIONS)

# numero in testa (intero, decimale con virgola o punto, frazione con la barra, intero
# seguito da ½ ¼ ¾, oppure ½ ¼ ¾ da soli), e subito dopo la parola dell'unità se c'è.
# Tutto quel che segue è prosa e non ci riguarda: «1 litro di brodo» è un litro, e «di
# brodo» sta già in quantity_text. ½ ¼ ¾ sono «lettere» per `\w`: senza escluderle
# dall'unità, «1 ½» sarebbe un ½ come unità.
_DOSE = re.compile(
    rf"^\s*(?:(?P<num>\d+)\s*/\s*(?P<den>\d+)"
    rf"|(?P<dec>\d+(?:[.,]\d+)?)(?:\s*(?P<mixed>[{_FRACTION_CHARS}]))?"
    rf"|(?P<vulgar>[{_FRACTION_CHARS}]))"
    rf"\s*(?P<unit>[^\W\d_{_FRACTION_CHARS}]+)?",
    re.UNICODE,
)

# Un pezzo «quanto basta»: «q.b.», «qb», «Q. B.», anche seguito da parole («q.b. per
# spolverare»). Non si somma e non si scala: accanto a una dose, la dose resta leggibile.
_QB = re.compile(r"^\s*q\s*\.?\s*b\b\.?", re.IGNORECASE)


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

    Un pezzo «q.b.» accanto a una dose non conta: «50 g + q.b.» sono 50 g. Le
    frazioni ½ ¼ ¾ si leggono, da sole («½ cucchiaino») e dopo un intero («1 ½»).
    """
    if not text:
        return (None, None)

    # `merge_quantities` unisce con « + » due dosi della stessa fonte finite sullo
    # stesso ingrediente («500 g + 50 g»). Sommare è giusto solo a unità uguale.
    # Un pezzo «q.b.» non è una dose da sommare: «50 g + q.b.» sono 50 g che si
    # riscalano, e il «+ q.b.» lo rimette accanto `with_qb_tail` (Mattia, 2026-10-13).
    measured = [piece for piece in text.split("+") if not _QB.match(piece)]
    if not measured:
        return (None, None)
    pieces = [_parse_one(piece) for piece in measured]
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
        elif found["vulgar"] is not None:
            value = VULGAR_FRACTIONS[found["vulgar"]]
        else:
            value = Decimal(found["dec"].replace(",", "."))
            if found["mixed"] is not None:
                value += VULGAR_FRACTIONS[found["mixed"]]
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


def with_qb_tail(display: str, text: str | None) -> str:
    """La dose riscalata, con accanto i pezzi «q.b.» che la riga scriveva.

    `parse_quantity` legge «50 g + q.b.» come 50 g; riscalata, la riga direbbe «100 g»
    e perderebbe il «q.b.». Mattia (2026-10-13): «+ q.b.» resta scritto accanto.
    """
    if not text:
        return display
    tails = [" ".join(piece.split()) for piece in text.split("+") if _QB.match(piece)]
    return " + ".join([display, *tails])


# --- La pulizia delle dosi dell'import (spec 2026-10-13-pulizia-dosi-design.md) -------

# La lunghezza di `recipe_ingredients.note`. Il modello non la importa da qui (la colonna
# c'era prima): la tiene allineata `test_note_max_chars_e_la_colonna`.
NOTE_MAX_CHARS = 300

# Una dose «nella forma dell'import»: GialloZafferano la scrive con gli a capo e le
# tabulazioni del suo HTML («fredda\n\t\t\t330\n\t\t\tg»). Il campo del modulo è una riga
# sola, quindi una dose senza è scritta a mano, o è già pulita, e non si tocca: la
# decisione 3 di Mattia (2026-10-13) resa misurabile.
_IMPORT_WHITESPACE = re.compile(r"[\n\r\t]")
_STARTS_A_DOSE = re.compile(rf"^[\d{_FRACTION_CHARS}]")


class DoseShape(StrEnum):
    """Che cosa la pulizia ha trovato in una dose: il comando conta per forma."""

    UNCHANGED = "unchanged"  # non ha la forma dell'import: non si tocca
    SPACES = "spaces"  # solo a capo e tabulazioni
    WORDS_BEFORE = "words_before"  # parole davanti alla dose, ora nella nota
    NUMBER_IN_NAME = "number_in_name"  # «36 mesi ⏎ 50 ⏎ g»: la nota comincia con un numero
    NOTE_QB = "note_qb"  # «secco ⏎⏎ q.b.»: una nota e «q.b.»


@dataclass(frozen=True)
class CleanDose:
    quantity_text: str | None
    note: str | None
    shape: DoseShape


def clean_dose(text: str | None) -> CleanDose:
    """La dose dell'import ripulita: le parole davanti nella nota, gli spazi a uno.

    Non legge numeri e non sa di unità: separa e basta. Leggere resta di
    `parse_quantity`, che sulla dose pulita trova il numero in testa.
    """
    if text is None or not _IMPORT_WHITESPACE.search(text):
        return CleanDose(text, None, DoseShape.UNCHANGED)
    doses: list[str] = []
    notes: list[str] = []
    # le dosi unite da `merge_quantities` si puliscono pezzo per pezzo
    for piece in text.split("+"):
        dose, note = _split_note(piece)
        if dose:
            doses.append(dose)
        if note:
            notes.append(note)
    quantity = " + ".join(doses) or None
    return CleanDose(quantity, merge_notes(*notes), _shape(quantity, notes))


def _split_note(piece: str) -> tuple[str, str | None]:
    lines = [" ".join(line.split()) for line in piece.splitlines()]
    lines = [line for line in lines if line]
    starts = [
        index
        for index, line in enumerate(lines)
        if _STARTS_A_DOSE.match(line) or _QB.match(line)
    ]
    if not starts:
        return (" ".join(lines), None)
    # l'ultima riga che comincia come una dose: in «36 mesi ⏎ 50 ⏎ g» anche la prima
    # comincia con un numero, ma è il nome
    first = starts[-1]
    # il numero della dose può essere esso stesso spezzato su più righe, «1 ⏎ ½»: una
    # riga senza lettere accanto alla dose è dose, non nota. Si risale finché le righe
    # non hanno lettere; la prima con una lettera (il nome, «36 mesi») ferma la salita
    while first > 0 and not any(char.isalpha() for char in lines[first - 1]):
        first -= 1
    before = " ".join(lines[:first])
    if not any(char.isalpha() for char in before):
        # «2 ⏎ 1/2 ⏎ cucchiai»: davanti solo numeri, è tutta dose. Una nota fatta di
        # numeri sarebbe un'invenzione, e il parser dirà da sé che non la legge
        return (" ".join(lines), None)
    return (" ".join(lines[first:]), _unwrap(before))


def _unwrap(note: str) -> str:
    """«(da pulire)» → «da pulire»: in una nota le parentesi della fonte non servono."""
    if note.startswith("(") and note.endswith(")") and note.count("(") == note.count(")") == 1:
        return note[1:-1].strip()
    return note


def _shape(quantity: str | None, notes: list[str]) -> DoseShape:
    if not notes:
        return DoseShape.SPACES
    if any(note[:1].isdigit() for note in notes):
        return DoseShape.NUMBER_IN_NAME
    if quantity is not None and all(_QB.match(piece) for piece in quantity.split("+")):
        return DoseShape.NOTE_QB
    return DoseShape.WORDS_BEFORE


def merge_notes(*notes: str | None) -> str | None:
    """Più note sulla stessa riga diventano una: nell'ordine, senza ripetersi, con «; »
    fra l'una e l'altra, dentro i caratteri della colonna. La prima resta davanti: chi
    chiama ci mette la nota già scritta."""
    kept: list[str] = []
    for note in notes:
        cleaned = note.strip() if note else ""
        if cleaned and cleaned not in kept:
            kept.append(cleaned)
    return "; ".join(kept)[:NOTE_MAX_CHARS] or None


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
