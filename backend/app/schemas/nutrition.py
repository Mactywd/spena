"""I valori nutrizionali di un ingrediente in HTTP (S4, fetta 1).

Il server dice tutto quel che lo schermo deve mostrare: quali nutrienti, con che nome,
che unità, in che ordine, e quali sono «principali» (le otto righe dell'etichetta, che si
mostrano anche vuote). Il frontend non tiene una seconda copia del vocabolario.
"""

from collections.abc import Mapping
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.domain.ciqual import CODE_MAX_LENGTH
from app.domain.nutrients import MAIN_FIELDS, NUTRIENT_FIELDS


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


class IngredientNutritionOut(BaseModel):
    state: Literal["undecided", "none", "food", "non_food"]
    decided_by: Literal["ai", "human"] | None
    food: CiqualFoodOut | None
    # per 100 g di parte edibile; vuoto se non c'è un alimento
    nutrients: list[NutrientValueOut]
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
