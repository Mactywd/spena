"""I nutrienti di una ricetta, la parte pura (S4, fetta 2). Nessun accesso al database.

Una ricetta dice dosi, non grammi: «180 g», «2 cucchiai», «1 spicchio», «2» uova, «q.b.».
Qui sta come una dose diventa grammi, e come i grammi diventano nutrienti:

- **massa** (g, kg, hg, mg e le loro parole): i grammi si contano da sé;
- **volume** (ml, cl, dl, l e le loro parole): millilitri × densità — 1, dichiarata
  approssimata, salvo le eccezioni di `DENSITIES` sull'inizio del nome dell'ingrediente;
- **tutto il resto** (cucchiaio, spicchio, bicchiere, e la dose senza unità, il «pezzo»):
  il peso della coppia ingrediente × unità canonica, deciso una volta
  (`ingredient_unit_grams`).

Una riga si conta se ha una dose letta, un alimento CIQUAL e un peso; altrimenti è fuori
dal conto **col suo perché**: «q.b.» resta fuori, e la copertura lo dice (decisione di
Mattia del 2026-10-13). Un nutriente che una riga contata non ha non diventa zero: si dice
su quante righe c'è (CLAUDE.md, «missing nutrients stay missing»).

La dispensa non entra qui e non conosce pesi (decisione fondante 1): questo modulo è per
le ricette, come `quantities.py`.
"""

import uuid
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Literal

GRAMS_PER_MASS_UNIT: dict[str, Decimal] = {
    "g": Decimal("1"),
    "gr": Decimal("1"),
    "grammo": Decimal("1"),
    "grammi": Decimal("1"),
    "kg": Decimal("1000"),
    "chilo": Decimal("1000"),
    "chili": Decimal("1000"),
    "chilogrammo": Decimal("1000"),
    "chilogrammi": Decimal("1000"),
    "hg": Decimal("100"),
    "etto": Decimal("100"),
    "etti": Decimal("100"),
    "mg": Decimal("0.001"),
}

ML_PER_VOLUME_UNIT: dict[str, Decimal] = {
    "ml": Decimal("1"),
    "millilitro": Decimal("1"),
    "millilitri": Decimal("1"),
    "cl": Decimal("10"),
    "centilitro": Decimal("10"),
    "centilitri": Decimal("10"),
    "dl": Decimal("100"),
    "decilitro": Decimal("100"),
    "decilitri": Decimal("100"),
    "l": Decimal("1000"),
    "lt": Decimal("1000"),
    "litro": Decimal("1000"),
    "litri": Decimal("1000"),
}

# «1 pezzo» e «1» sono la stessa dose: la coppia si scrive col «pezzo» (unità NULL)
PIECE_WORDS = frozenset({"pezzo", "pezzi"})
PIECE_LABEL = "pezzo"

# Le densità che si discostano da 1 abbastanza da contare, sull'inizio del nome
# dell'ingrediente. La prima che combacia vince: «latte condensato» prima di tutto.
DENSITIES: tuple[tuple[str, Decimal], ...] = (
    ("latte condensato", Decimal("1.29")),
    ("olio", Decimal("0.92")),
    ("miele", Decimal("1.42")),
    ("sciroppo", Decimal("1.33")),
)
DEFAULT_DENSITY = Decimal("1")

# Il peso più grande che un'unità di un ingrediente possa avere: un'anguria intera
# sta sotto. Oltre, è un errore di battitura o di modello.
GRAMS_MAX = Decimal("5000")

MissingReason = Literal["no_quantity", "no_nutrients", "no_weight"]


@dataclass(frozen=True)
class UnitKind:
    measure: Literal["mass", "volume", "pair"]
    # grammi (massa) o millilitri (volume) per unità; None per una coppia
    factor: Decimal | None
    # la coppia si scrive col «pezzo», cioè senza unità
    piece: bool


def _words(key: str | None, singular: str | None) -> list[str]:
    return [word.strip().lower() for word in (key, singular) if word]


def classify_unit(key: str | None, singular: str | None) -> UnitKind:
    """Che cosa vuol dire l'unità canonica di una dose. `key` None = dose senza unità."""
    words = _words(key, singular)
    if not words:
        return UnitKind("pair", None, True)
    for word in words:
        if word in GRAMS_PER_MASS_UNIT:
            return UnitKind("mass", GRAMS_PER_MASS_UNIT[word], False)
    for word in words:
        if word in ML_PER_VOLUME_UNIT:
            return UnitKind("volume", ML_PER_VOLUME_UNIT[word], False)
    if any(word in PIECE_WORDS for word in words):
        return UnitKind("pair", None, True)
    return UnitKind("pair", None, False)


def unit_label(key: str | None, singular: str | None) -> str:
    """Come si chiama a video l'unità di una coppia: «spicchio», «pezzo»."""
    if classify_unit(key, singular).piece:
        return PIECE_LABEL
    return (singular or key or PIECE_LABEL).strip()


def density_for(ingredient_name: str) -> Decimal:
    name = ingredient_name.strip().lower()
    for prefix, density in DENSITIES:
        if name.startswith(prefix):
            return density
    return DEFAULT_DENSITY


def line_grams(
    *, value: Decimal, kind: UnitKind, pair_grams: Decimal | None, ingredient_name: str
) -> Decimal | None:
    """I grammi di una dose, o None se manca il peso della coppia."""
    if kind.measure == "mass":
        return value * kind.factor
    if kind.measure == "volume":
        return value * kind.factor * density_for(ingredient_name)
    if pair_grams is None:
        return None
    return value * pair_grams


@dataclass(frozen=True)
class NutritionLine:
    ingredient_id: uuid.UUID
    ingredient_name: str
    quantity_text: str | None
    # la dose letta (`quantity_value`); None = «q.b.» o una dose che il parser non legge
    value: Decimal | None
    # chiave e singolare dell'unità **canonica**; None = dose senza unità
    unit_key: str | None
    unit_singular: str | None
    # i grammi decisi per la coppia; None se non decisi o decisi «nessun peso»
    pair_grams: Decimal | None
    # i valori per 100 g dell'alimento CIQUAL; None = nessun alimento
    per_100g: Mapping[str, float] | None


@dataclass(frozen=True)
class MissingLine:
    ingredient_id: uuid.UUID
    ingredient_name: str
    quantity_text: str | None
    reason: MissingReason
    # solo per `no_weight`: l'unità di cui manca il peso
    unit_label: str | None


@dataclass(frozen=True)
class RecipeNutrition:
    lines_total: int
    lines_counted: int
    # per tutta la ricetta, solo le chiavi che almeno una riga contata ha
    totals: dict[str, float]
    # chiave → quante righe contate hanno quel valore
    lines_with: dict[str, int]
    missing: tuple[MissingLine, ...]
    servings: int | None
    # i totali divisi per le porzioni; None se la ricetta non le dice
    per_serving: dict[str, float] | None


def recipe_nutrition(lines: Sequence[NutritionLine], servings: int | None) -> RecipeNutrition:
    totals: dict[str, float] = {}
    lines_with: Counter[str] = Counter()
    missing: list[MissingLine] = []
    counted = 0
    for line in lines:
        reason: MissingReason | None = None
        label: str | None = None
        grams: Decimal | None = None
        if line.value is None:
            reason = "no_quantity"
        elif line.per_100g is None:
            reason = "no_nutrients"
        else:
            kind = classify_unit(line.unit_key, line.unit_singular)
            grams = line_grams(
                value=line.value,
                kind=kind,
                pair_grams=line.pair_grams,
                ingredient_name=line.ingredient_name,
            )
            if grams is None:
                reason = "no_weight"
                label = unit_label(line.unit_key, line.unit_singular)
        if reason is not None:
            missing.append(
                MissingLine(line.ingredient_id, line.ingredient_name, line.quantity_text, reason, label)
            )
            continue
        counted += 1
        for key, per_100g in line.per_100g.items():
            totals[key] = totals.get(key, 0.0) + float(grams) * per_100g / 100
            lines_with[key] += 1
    per_serving = (
        {key: value / servings for key, value in totals.items()}
        if servings is not None and servings > 0
        else None
    )
    return RecipeNutrition(
        lines_total=len(lines),
        lines_counted=counted,
        totals=totals,
        lines_with=dict(lines_with),
        missing=tuple(missing),
        servings=servings,
        per_serving=per_serving,
    )


def round_nutrient(value: float, unit: str) -> float:
    """Come si dice un valore: kcal all'intero, il resto a un decimale, due sotto l'unità."""
    if unit == "kcal":
        return float(round(value))
    return round(value, 2 if abs(value) < 1 else 1)
