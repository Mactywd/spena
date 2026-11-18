"""La ricetta di un pasto com'era, e che cosa una modifica ha toccato (spec 2026-11-12 §5.3).

Puro, senza database. Lo snapshot è la ricetta (e il piatto) com'erano prima o dopo una
modifica di Claude: «Annulla» lo confronta con lo stato di adesso e, se è ancora
quello, rimette `before`. `changed_parts` dice che cosa evidenziare a video.
"""

import uuid
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class LineSnapshot:
    ingredient_id: uuid.UUID
    role: str
    quantity_text: str | None
    note: str | None


@dataclass(frozen=True)
class RecipeSnapshot:
    title: str
    description: str | None
    instructions: str
    servings: int | None
    lines: tuple[LineSnapshot, ...]


@dataclass(frozen=True)
class MealSnapshot:
    dish: str
    sides: str | None
    recipe: RecipeSnapshot | None


@dataclass(frozen=True)
class ChangedParts:
    ingredient_ids: frozenset[uuid.UUID]
    title: bool
    servings: bool
    instructions: bool
    description: bool


def snapshot_to_json(s: MealSnapshot) -> dict[str, Any]:
    recipe = None
    if s.recipe is not None:
        recipe = {
            "title": s.recipe.title,
            "description": s.recipe.description,
            "instructions": s.recipe.instructions,
            "servings": s.recipe.servings,
            "lines": [
                {
                    "ingredient_id": str(line.ingredient_id),
                    "role": line.role,
                    "quantity_text": line.quantity_text,
                    "note": line.note,
                }
                for line in s.recipe.lines
            ],
        }
    return {"dish": s.dish, "sides": s.sides, "recipe": recipe}


def snapshot_from_json(d: dict[str, Any]) -> MealSnapshot:
    raw = d["recipe"]
    recipe = None
    if raw is not None:
        recipe = RecipeSnapshot(
            title=raw["title"],
            description=raw["description"],
            instructions=raw["instructions"],
            servings=raw["servings"],
            lines=tuple(
                LineSnapshot(
                    ingredient_id=uuid.UUID(line["ingredient_id"]),
                    role=line["role"],
                    quantity_text=line["quantity_text"],
                    note=line["note"],
                )
                for line in raw["lines"]
            ),
        )
    return MealSnapshot(dish=d["dish"], sides=d["sides"], recipe=recipe)


def changed_parts(before: RecipeSnapshot | None, after: RecipeSnapshot) -> ChangedParts:
    """Le righe nuove o cambiate (ruolo, dose o nota) e i segni su titolo, porzioni,
    procedimento e descrizione. Una riga tolta non c'è più da evidenziare."""
    if before is None:
        return ChangedParts(
            ingredient_ids=frozenset(line.ingredient_id for line in after.lines),
            title=True, servings=True, instructions=True, description=True,
        )
    old = {line.ingredient_id: line for line in before.lines}
    changed = frozenset(
        line.ingredient_id for line in after.lines if old.get(line.ingredient_id) != line
    )
    return ChangedParts(
        ingredient_ids=changed,
        title=before.title != after.title,
        servings=before.servings != after.servings,
        instructions=before.instructions != after.instructions,
        description=before.description != after.description,
    )


def changed_to_json(parts: ChangedParts, order: tuple[LineSnapshot, ...]) -> dict[str, Any]:
    """Gli id in stringa, nell'ordine delle righe di `order`."""
    return {
        "ingredient_ids": [
            str(line.ingredient_id) for line in order if line.ingredient_id in parts.ingredient_ids
        ],
        "title": parts.title,
        "servings": parts.servings,
        "instructions": parts.instructions,
        "description": parts.description,
    }
