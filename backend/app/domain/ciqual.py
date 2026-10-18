"""La tabella CIQUAL dentro il vocabolario di Spena (S4, fetta 1). Modulo puro.

CIQUAL è la tabella di composizione degli alimenti dell'Anses: valori medi per 100 g di
parte edibile, uno per alimento generico — «Tomate, crue», non una marca. È la fonte dei
nutrienti dell'ingrediente generico, scelta da Mattia il 2026-10-13
(`docs/superpowers/specs/2026-10-13-s4-nutrienti-ingrediente-design.md`).

Qui sta come si legge il file senza aprirlo: quale colonna diventa quale chiave di
`NUTRIENT_FIELDS`, e come si legge un valore. Le colonne si riconoscono dal nome, mai
dalla posizione, e l'unità scritta nell'intestazione si confronta con quella del
vocabolario: un file che desse il ferro in µg invece che in mg si rifiuta intero, invece
di salvare tremila numeri sbagliati di mille volte.
"""

import math
import re
import unicodedata
from dataclasses import dataclass

from app.domain.nutrients import NUTRIENT_FIELDS

CIQUAL_VERSION = "2025"
CIQUAL_SOURCE = f"CIQUAL {CIQUAL_VERSION}"
# La citazione che la licenza (Etalab 2.0) chiede accanto a ogni riuso: va nel README e
# sotto i valori, in Anagrafica.
CIQUAL_CITATION = "Anses. 2025. Table de composition nutritionnelle des aliments Ciqual"
CIQUAL_URL = "https://doi.org/10.57745/RDMHWY"

CODE_MAX_LENGTH = 10
NAME_MAX_LENGTH = 300
GROUP_MAX_LENGTH = 200

CODE_COLUMN = "alim_code"
NAME_COLUMN = "alim_nom_fr"
GROUP_COLUMN = "alim_grp_nom_fr"
SUBGROUP_COLUMN = "alim_ssgrp_nom_fr"

# Il nome di ogni costituente com'è scritto nelle intestazioni di CIQUAL, già passato per
# `normalize_name` (senza accenti né maiuscole). Una tupla per chiave: se un'edizione
# nuova scrive lo stesso costituente in un altro modo, si aggiunge un nome, non una
# regola. Fuori la vitamina A (CIQUAL dà retinolo e beta-carotene separati, e la somma
# in equivalenti è un calcolo che non si fa senza dirlo), e biotina, fluoruro, cromo e
# molibdeno, che CIQUAL non ha (spec §4.3). La vitamina K è la K1.
CIQUAL_NAMES: dict[str, tuple[str, ...]] = {
    "kcal": ("energie, reglement ue n°1169/2011",),
    "protein": ("proteines, n x facteur de jones",),
    "carbs": ("glucides",),
    "sugars": ("sucres",),
    "fat": ("lipides",),
    "saturated_fat": ("ag satures",),
    "fiber": ("fibres alimentaires",),
    "salt": ("sel chlorure de sodium",),
    "vitamin_d": ("vitamine d",),
    "vitamin_e": ("vitamine e",),
    "vitamin_k": ("vitamine k1",),
    "vitamin_c": ("vitamine c",),
    "thiamin": ("vitamine b1 ou thiamine",),
    "riboflavin": ("vitamine b2 ou riboflavine",),
    "niacin": ("vitamine b3 ou pp ou niacine",),
    "vitamin_b6": ("vitamine b6",),
    "folate": ("vitamine b9 ou folates totaux",),
    "vitamin_b12": ("vitamine b12",),
    "pantothenic_acid": ("vitamine b5 ou acide pantothenique",),
    "potassium": ("potassium",),
    "chloride": ("chlorure",),
    "calcium": ("calcium",),
    "phosphorus": ("phosphore",),
    "magnesium": ("magnesium",),
    "iron": ("fer",),
    "zinc": ("zinc",),
    "copper": ("cuivre",),
    "manganese": ("manganese",),
    "selenium": ("selenium",),
    "iodine": ("iode",),
}

# Senza queste quattro colonne un file non è la tabella che crediamo: niente si scrive.
REQUIRED_KEYS: tuple[str, ...] = ("kcal", "protein", "carbs", "fat")

_EMPTY = frozenset({"", "-", "–", "—"})
# «Fer (mg/100 g)»: il nome, poi fra parentesi l'unità per 100 g. Il nome può avere una
# barra sua («1169/2011»), l'unità no.
_HEADER = re.compile(r"^(?P<name>.+?)\s*\((?P<unit>[^()/]+)/\s*100\s*g\)\s*$")
_FLOAT_CODE = re.compile(r"^\d+\.0+$")


class CiqualFormatError(Exception):
    """Il file non è quello atteso: niente si scrive, e il messaggio dice perché."""


def normalize_name(text: str) -> str:
    """Minuscolo, senza accenti, spazi semplici, «N°» attaccato al numero."""
    text = text.replace("œ", "oe").replace("Œ", "Oe").replace("º", "°")
    plain = "".join(
        char for char in unicodedata.normalize("NFKD", text) if not unicodedata.combining(char)
    ).lower()
    plain = re.sub(r"n\s*°\s*", "n°", plain)
    return " ".join(plain.split())


def normalize_unit(unit: str) -> str:
    """«µg», «μg» (la lettera greca) e «mcg» sono la stessa unità: «ug»."""
    plain = unicodedata.normalize("NFKC", unit).strip().lower()
    return plain.replace("μ", "u").replace("mcg", "ug")


def split_header(header: str) -> tuple[str, str] | None:
    """Il nome normalizzato e l'unità di una colonna di costituente, o `None` per le
    altre (`alim_code`, `alim_nom_fr`, …)."""
    found = _HEADER.match(header.strip())
    if found is None:
        return None
    return normalize_name(found["name"]), normalize_unit(found["unit"])


def parse_teneur(raw: str | None) -> float | None:
    """Il valore di una cella. `None` vuol dire assente — mai zero (CLAUDE.md).

    «traces» è 0, perché la tabella dice che c'è, in quantità trascurabile; «< x» è x/2,
    la convenzione «middle bound» dell'EFSA: il valore vero sta fra 0 e il limite (spec
    §4.4). Qualunque altra cosa che non sia un numero solleva `ValueError`: chi legge il
    file la conta come illeggibile e la lascia assente.
    """
    if raw is None:
        return None
    text = raw.replace(" ", " ").strip()
    if text in _EMPTY:
        return None
    if text.lower() == "traces":
        return 0.0
    below = text.startswith("<")
    value = float(text.lstrip("<").strip().replace(",", "."))
    if not math.isfinite(value) or value < 0:
        raise ValueError(text)
    return value / 2 if below else value


def normalize_code(raw: str | None) -> str | None:
    """Il codice come testo. Un foglio che l'ha salvato come numero lo scrive «20047.0»."""
    if raw is None:
        return None
    text = raw.strip()
    if _FLOAT_CODE.match(text):
        text = text.split(".")[0]
    if not text or len(text) > CODE_MAX_LENGTH:
        return None
    return text


@dataclass(frozen=True)
class ColumnMap:
    code: int
    name: int
    group: int | None
    subgroup: int | None
    # chiave del vocabolario → indice della colonna
    nutrients: dict[str, int]
    # le chiavi di `CIQUAL_NAMES` che il file non ha
    absent: tuple[str, ...]
    # le colonne di costituente che nessuna chiave usa («Eau (g/100 g)»): si dicono
    unused: tuple[str, ...]


def map_columns(headers: list[str | None]) -> ColumnMap:
    """Quale colonna è quale. Solleva `CiqualFormatError` se il file non va."""
    wanted = {name: key for key, names in CIQUAL_NAMES.items() for name in names}
    identity: dict[str, int] = {}
    # (posizione, intestazione) delle colonne di costituente che nessuna chiave usa
    skipped: list[tuple[int, str]] = []
    # chiave → le colonne con quel nome, nell'ordine del file: (posizione, intestazione, unità)
    candidates: dict[str, list[tuple[int, str, str]]] = {}
    for index, header in enumerate(headers):
        if header is None:
            continue
        plain = header.strip()
        if plain in (CODE_COLUMN, NAME_COLUMN, GROUP_COLUMN, SUBGROUP_COLUMN):
            identity.setdefault(plain, index)
            continue
        split = split_header(plain)
        if split is None:
            continue
        name, unit = split
        key = wanted.get(name)
        if key is None:
            skipped.append((index, plain))
            continue
        candidates.setdefault(key, []).append((index, plain, unit))
    # Nel CIQUAL l'energia compare due volte con lo stesso nome, in kJ e in kcal, una
    # accanto all'altra: una colonna nell'unità sbagliata si rifiuta solo se il file non ne
    # ha una nell'unità giusta per la stessa chiave. Se c'è, quella sbagliata è una colonna
    # non usata e si usa la prima in unità giusta.
    nutrients: dict[str, int] = {}
    for key, columns in candidates.items():
        field = NUTRIENT_FIELDS[key]
        right = normalize_unit(field.unit)
        found = next((index for index, _, unit in columns if unit == right), None)
        if found is None:
            _, plain, unit = columns[0]
            raise CiqualFormatError(
                f"la colonna «{plain}» è in {unit}, ma «{field.label}» si conta in "
                f"{field.unit}: il file non è quello atteso"
            )
        nutrients[key] = found
        skipped.extend((index, plain) for index, plain, unit in columns if unit != right)
    unused = [plain for _, plain in sorted(skipped)]
    missing = [column for column in (CODE_COLUMN, NAME_COLUMN) if column not in identity]
    if missing:
        raise CiqualFormatError(
            f"mancano le colonne {', '.join(missing)}: il file non è la tabella CIQUAL"
        )
    required = [NUTRIENT_FIELDS[key].label for key in REQUIRED_KEYS if key not in nutrients]
    if required:
        raise CiqualFormatError(
            f"non trovo le colonne di {', '.join(required)}: il file non è quello atteso"
        )
    return ColumnMap(
        code=identity[CODE_COLUMN],
        name=identity[NAME_COLUMN],
        group=identity.get(GROUP_COLUMN),
        subgroup=identity.get(SUBGROUP_COLUMN),
        nutrients=nutrients,
        absent=tuple(key for key in CIQUAL_NAMES if key not in nutrients),
        unused=tuple(unused),
    )


@dataclass(frozen=True)
class CiqualRow:
    code: str
    name_fr: str
    group_fr: str | None
    # chiave del vocabolario → valore per 100 g; un nutriente assente non c'è
    nutrients: dict[str, float]


def _text(cells: list[str | None], index: int | None) -> str:
    if index is None or index >= len(cells):
        return ""
    value = (cells[index] or "").strip()
    return "" if value in _EMPTY else value


def food_from_row(
    cells: list[str | None], columns: ColumnMap
) -> tuple[CiqualRow | None, list[str]]:
    """L'alimento di una riga, e le chiavi con un valore illeggibile.

    `None` per una riga senza codice o senza nome: le righe vuote in fondo a un foglio,
    o una riga di titolo.
    """
    code = normalize_code(cells[columns.code] if columns.code < len(cells) else None)
    name = _text(cells, columns.name)
    if not code or not name:
        return None, []
    group = _text(cells, columns.subgroup) or _text(cells, columns.group) or None
    values: dict[str, float] = {}
    unreadable: list[str] = []
    for key, index in columns.nutrients.items():
        try:
            value = parse_teneur(cells[index] if index < len(cells) else None)
        except ValueError:
            unreadable.append(key)
            continue
        if value is not None:
            values[key] = value
    return (
        CiqualRow(
            code=code,
            name_fr=name[:NAME_MAX_LENGTH],
            group_fr=group[:GROUP_MAX_LENGTH] if group else None,
            nutrients=values,
        ),
        unreadable,
    )
