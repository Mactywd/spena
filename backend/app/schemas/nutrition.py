"""I valori nutrizionali di un ingrediente in HTTP (S4, fetta 1).

Il server dice tutto quel che lo schermo deve mostrare: quali nutrienti, con che nome,
che unità, in che ordine, e quali sono «principali» (le otto righe dell'etichetta, che si
mostrano anche vuote). Il frontend non tiene una seconda copia del vocabolario.
"""

import uuid
from collections.abc import Mapping, Sequence
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.ciqual import CODE_MAX_LENGTH
from app.domain.nutrients import MAIN_FIELDS, NUTRIENT_FIELDS
from app.domain.recipe_nutrition import RecipeNutrition, round_nutrient
from app.services.unit_grams import Weight


class CiqualFoodOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    code: str
    name_fr: str
    group_fr: str | None


class NutrientValueOut(BaseModel):
    key: str
    label: str
    unit: str
    main: bool
    # `None` solo per un principale che CIQUAL non dà: a video «—», mai zero
    value: float | None


class UnitWeightOut(BaseModel):
    # l'id dell'unità canonica, o «pezzo»: è il pezzo d'indirizzo di `/unit-grams/{unit}`
    unit: str
    unit_label: str
    grams: float | None
    state: Literal["undecided", "decided", "none"]
    decided_by: Literal["ai", "human"] | None


class GramsIn(BaseModel):
    # il servizio controlla il campo (più di 0, al più 5000) e rifiuta con la frase:
    # un 422 non direbbe a chi scrive cosa ha sbagliato
    grams: Decimal


class IngredientNutritionOut(BaseModel):
    state: Literal["undecided", "none", "food", "non_food"]
    decided_by: Literal["ai", "human"] | None
    food: CiqualFoodOut | None
    # per 100 g di parte edibile; vuoto se non c'è un alimento
    nutrients: list[NutrientValueOut]
    # i pesi delle sue coppie ingrediente × unità (fetta 2); vuoto per un non alimentare
    weights: list[UnitWeightOut]
    source: str
    citation: str


class NutritionChoiceIn(BaseModel):
    # obbligatorio, anche `null`: `null` vuol dire «nessun alimento adatto», che è una
    # scelta, non una dimenticanza
    ciqual_code: str | None = Field(max_length=CODE_MAX_LENGTH)


def nutrient_rows(values: Mapping[str, float] | None) -> list[NutrientValueOut]:
    """I principali sempre, gli altri se presenti, nell'ordine del vocabolario."""
    if values is None:
        return []
    rows = []
    for key, field in NUTRIENT_FIELDS.items():
        main = key in MAIN_FIELDS
        if main or key in values:
            rows.append(
                NutrientValueOut(
                    key=key, label=field.label, unit=field.unit, main=main, value=values.get(key)
                )
            )
    return rows


def weight_rows(weights: Sequence[Weight]) -> list[UnitWeightOut]:
    return [
        UnitWeightOut(
            unit=weight.unit,
            unit_label=weight.unit_label,
            grams=float(weight.grams) if weight.grams is not None else None,
            state=weight.state,
            decided_by=weight.decided_by,
        )
        for weight in weights
    ]


class RecipeNutrientOut(BaseModel):
    key: str
    label: str
    unit: str
    main: bool
    # a porzione, o per tutta la ricetta (`basis`); None solo per un principale che
    # nessuna riga contata ha
    value: float | None
    # quante righe contate hanno questo valore: se sono meno di `lines_counted`, il
    # valore è parziale, e lo schermo lo dice
    lines: int


class MissingLineOut(BaseModel):
    ingredient_id: uuid.UUID
    ingredient_name: str
    quantity_text: str | None
    reason: Literal["no_quantity", "no_nutrients", "no_weight"]
    unit_label: str | None


class RecipeNutritionOut(BaseModel):
    basis: Literal["serving", "recipe"]
    servings: int | None
    lines_total: int
    lines_counted: int
    # vuoto se nessuna riga si conta: niente tabella di zeri
    nutrients: list[RecipeNutrientOut]
    missing: list[MissingLineOut]
    source: str


def recipe_nutrition_out(result: RecipeNutrition, source: str) -> RecipeNutritionOut:
    """La porzione la sceglie il server (decisione 14 del piano): a porzione se la
    ricetta le dice, altrimenti per tutta la ricetta."""
    values = result.per_serving if result.per_serving is not None else result.totals
    nutrients = []
    if result.lines_counted:
        for key, field in NUTRIENT_FIELDS.items():
            main = key in MAIN_FIELDS
            if main or key in values:
                value = values.get(key)
                nutrients.append(
                    RecipeNutrientOut(
                        key=key,
                        label=field.label,
                        unit=field.unit,
                        main=main,
                        value=None if value is None else round_nutrient(value, field.unit),
                        lines=result.lines_with.get(key, 0),
                    )
                )
    return RecipeNutritionOut(
        basis="serving" if result.per_serving is not None else "recipe",
        servings=result.servings,
        lines_total=result.lines_total,
        lines_counted=result.lines_counted,
        nutrients=nutrients,
        missing=[
            MissingLineOut(
                ingredient_id=line.ingredient_id,
                ingredient_name=line.ingredient_name,
                quantity_text=line.quantity_text,
                reason=line.reason,
                unit_label=line.unit_label,
            )
            for line in result.missing
        ],
        source=source,
    )
