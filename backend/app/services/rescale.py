"""Il riporziona da una dose (R2, secondo modo): quale riga fa da ancora, e cosa ne segue.

Lo chiamano il dettaglio della ricetta (`_to_out` in `app/api/recipes.py`) e la cottura
(`app/services/cooking.py`): una funzione sola, perché la riga che il dettaglio ha
mostrato come ancora sia la stessa che la cottura registra (prima lezione di
`CLAUDE.md`). La matematica sta nel dominio (`app/domain/quantities.py`); qui si sa cos'è
una riga di ricetta.
"""

import uuid
from dataclasses import dataclass
from decimal import Decimal

from app.db.models.recipe import Recipe, RecipeIngredient
from app.domain.quantities import (
    ANCHOR_MAX_FACTOR,
    AnchorOutOfRange,
    UnitForms,
    anchor_factor,
    equivalent_servings,
    render_quantity,
)


class AnchorRefused(ValueError):
    """La dose scritta porta la ricetta oltre 50 volte la sua. `sentence` è la frase da
    mostrare sotto il campo, con gli estremi e l'unità della riga."""

    def __init__(self, sentence: str) -> None:
        super().__init__(sentence)
        self.sentence = sentence


@dataclass(frozen=True)
class ResolvedAnchor:
    line: RecipeIngredient
    amount: Decimal
    factor: Decimal
    # `None` quando la ricetta non dice per quante porzioni è
    equivalent_servings: Decimal | None


def unit_forms(line: RecipeIngredient) -> UnitForms | None:
    if line.unit is None:
        return None
    return UnitForms(line.unit.key, line.unit.singular, line.unit.plural)


def is_anchorable(line: RecipeIngredient) -> bool:
    """Una riga da cui si riscala: ha una dose strutturata, e più di zero — da zero non
    si ricava nessun fattore. «q.b.» e le righe senza dose no."""
    return line.quantity_value is not None and line.quantity_value > 0


def anchor_unit(line: RecipeIngredient) -> str | None:
    """La parola dell'unità accanto al campo «Quanto ne fai?»: il plurale, se deciso, se
    no la chiave com'è arrivata. `None` per un numero nudo («1» cipolla)."""
    if line.unit is None:
        return None
    return line.unit.plural or line.unit.key


def find_anchor_line(recipe: Recipe, ingredient_id: uuid.UUID) -> RecipeIngredient | None:
    # (recipe_id, ingredient_id) è unico: una riga per ingrediente, quindi l'ingrediente
    # basta a dire quale riga
    return next(
        (
            line
            for line in recipe.ingredients
            if line.ingredient_id == ingredient_id and is_anchorable(line)
        ),
        None,
    )


def resolve_anchor(
    recipe: Recipe, ingredient_id: uuid.UUID, amount: Decimal
) -> ResolvedAnchor | None:
    """Il fattore che porta la riga di `ingredient_id` ad `amount`, e le porzioni che fa.

    `None` se la ricetta non ha (più) una riga di quell'ingrediente da cui riscalare: chi
    chiama mostra la ricetta com'è invece di un errore — una ricetta modificata in
    un'altra scheda non deve diventare un vicolo cieco. Solleva `AnchorRefused` oltre
    `ANCHOR_MAX_FACTOR` volte."""
    line = find_anchor_line(recipe, ingredient_id)
    if line is None or line.quantity_value is None:
        return None
    try:
        factor = anchor_factor(line.quantity_value, amount)
    except AnchorOutOfRange as exc:
        forms = unit_forms(line)
        raise AnchorRefused(
            f"Così la ricetta cambierebbe più di {ANCHOR_MAX_FACTOR} volte: scrivi un "
            f"numero fra {render_quantity(exc.low, forms)} e "
            f"{render_quantity(exc.high, forms)}."
        ) from exc
    equivalent = (
        equivalent_servings(recipe.servings, factor) if recipe.servings is not None else None
    )
    return ResolvedAnchor(line=line, amount=amount, factor=factor, equivalent_servings=equivalent)
