"""Il file della tabella CIQUAL, letto da un XLSX con la sola libreria standard (S4, fetta 1).

Un XLSX è un archivio zip di XML: il foglio, e a parte le stringhe che il foglio cita per
numero (`sharedStrings.xml`). Leggerlo con `zipfile` e `xml.etree` evita una dipendenza
(`openpyxl`) per un file che si carica una volta all'anno (spec §4.2). Il foglio si legge
a righe, in streaming (`iterparse`).

Le celle vuote un XLSX non le scrive: la posizione di una cella sta nel suo riferimento
(`r="AB12"`), e una riga si ricostruisce da lì, non dall'ordine in cui arrivano. Senza,
una vitamina mancante sposterebbe di una colonna tutti i valori dopo di lei.

Il file viene da Mattia, scaricato dalla scheda ufficiale (spec §3): non è un file che
arriva da uno sconosciuto. Il parser di `xml.etree` (expat) rifiuta comunque l'espansione
ricorsiva delle entità.
"""

import re
import zipfile
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from xml.etree.ElementTree import Element, ParseError, iterparse, parse

from app.domain.ciqual import (
    CODE_COLUMN,
    CiqualFormatError,
    CiqualRow,
    food_from_row,
    map_columns,
)

_MAIN = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
_DOC_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
_PKG_REL = "{http://schemas.openxmlformats.org/package/2006/relationships}"
_COLUMN = re.compile(r"^([A-Z]+)")

# Dove si cerca la riga con `alim_code`: un foglio può avere un titolo sopra.
HEADER_SEARCH_ROWS = 10


def _column_index(reference: str) -> int | None:
    found = _COLUMN.match(reference)
    if found is None:
        return None
    index = 0
    for letter in found.group(1):
        index = index * 26 + (ord(letter) - ord("A") + 1)
    return index - 1


def _shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []
    strings: list[str] = []
    with archive.open("xl/sharedStrings.xml") as stream:
        for _, element in iterparse(stream):
            if element.tag == f"{_MAIN}si":
                strings.append("".join(text.text or "" for text in element.iter(f"{_MAIN}t")))
                element.clear()
    return strings


def _first_sheet(archive: zipfile.ZipFile) -> str:
    workbook = parse(archive.open("xl/workbook.xml")).getroot()
    sheet = workbook.find(f"{_MAIN}sheets/{_MAIN}sheet")
    if sheet is None:
        raise CiqualFormatError("il file XLSX non ha fogli")
    rel_id = sheet.get(f"{_DOC_REL}id")
    relations = parse(archive.open("xl/_rels/workbook.xml.rels")).getroot()
    for relation in relations.iter(f"{_PKG_REL}Relationship"):
        if relation.get("Id") == rel_id:
            target = relation.get("Target") or ""
            return target.lstrip("/") if target.startswith("/") else f"xl/{target}"
    raise CiqualFormatError("il file XLSX non dice dove sta il suo primo foglio")


def _cell_value(cell: Element, strings: list[str]) -> str | None:
    kind = cell.get("t")
    if kind == "inlineStr":
        return "".join(text.text or "" for text in cell.iter(f"{_MAIN}t"))
    raw = cell.findtext(f"{_MAIN}v")
    if raw is None:
        return None
    if kind == "s":
        return strings[int(raw)]
    return raw


def read_xlsx_rows(path: Path) -> Iterator[list[str | None]]:
    """Le righe del primo foglio, ogni cella al suo posto (`None` dove non è scritta)."""
    with zipfile.ZipFile(path) as archive:
        strings = _shared_strings(archive)
        with archive.open(_first_sheet(archive)) as stream:
            for _, element in iterparse(stream):
                if element.tag != f"{_MAIN}row":
                    continue
                cells: dict[int, str | None] = {}
                position = 0
                for cell in element.iter(f"{_MAIN}c"):
                    index = _column_index(cell.get("r", ""))
                    if index is None:
                        index = position
                    position = index + 1
                    cells[index] = _cell_value(cell, strings)
                element.clear()
                width = max(cells) + 1 if cells else 0
                yield [cells.get(index) for index in range(width)]


@dataclass(frozen=True)
class CiqualFile:
    foods: list[CiqualRow]
    # chiave → quanti alimenti hanno un valore
    with_value: dict[str, int]
    # chiave → quante celle non si sono lette
    unreadable: dict[str, int]
    # le chiavi del vocabolario che il file non ha
    absent: tuple[str, ...]
    # le colonne di costituente che nessuna chiave usa
    unused: tuple[str, ...]
    # righe con qualcosa scritto ma senza codice o senza nome
    skipped_rows: int
    # righe con un codice già letto: vale la prima
    duplicate_codes: int


def read_ciqual(path: Path) -> CiqualFile:
    """Tutto il file, o `CiqualFormatError` col perché. Non tocca il database."""
    try:
        return _read(path)
    except CiqualFormatError:
        raise
    except (OSError, zipfile.BadZipFile, KeyError, IndexError, ValueError, ParseError) as exc:
        raise CiqualFormatError(
            f"«{path.name}» non si legge come il file XLSX di CIQUAL ({exc})"
        ) from exc


def _read(path: Path) -> CiqualFile:
    rows = read_xlsx_rows(path)
    try:
        headers = None
        for _ in range(HEADER_SEARCH_ROWS):
            candidate = next(rows, None)
            if candidate is None:
                break
            if any((cell or "").strip() == CODE_COLUMN for cell in candidate):
                headers = candidate
                break
        if headers is None:
            raise CiqualFormatError(
                f"nelle prime {HEADER_SEARCH_ROWS} righe non c'è l'intestazione con "
                f"«{CODE_COLUMN}»: il file non è la tabella CIQUAL"
            )
        columns = map_columns(headers)
        foods: dict[str, CiqualRow] = {}
        with_value: Counter[str] = Counter()
        unreadable: Counter[str] = Counter()
        skipped = duplicates = 0
        for cells in rows:
            food, bad = food_from_row(cells, columns)
            if food is None:
                if any((cell or "").strip() for cell in cells):
                    skipped += 1
                continue
            if food.code in foods:
                duplicates += 1
                continue
            foods[food.code] = food
            unreadable.update(bad)
            with_value.update(food.nutrients.keys())
    finally:
        rows.close()
    if not foods:
        raise CiqualFormatError("il file non ha nemmeno un alimento con codice e nome")
    return CiqualFile(
        foods=list(foods.values()),
        with_value=dict(with_value),
        unreadable=dict(unreadable),
        absent=columns.absent,
        unused=columns.unused,
        skipped_rows=skipped,
        duplicate_codes=duplicates,
    )
