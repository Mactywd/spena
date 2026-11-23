import uuid
from dataclasses import replace

import pytest

from app.domain.recipe_changes import (
    LineSnapshot,
    MealSnapshot,
    RecipeSnapshot,
    changed_parts,
    snapshot_from_json,
    snapshot_to_json,
)

A, B = uuid.uuid4(), uuid.uuid4()


def line(ingredient_id, role="primary", text="100 g", note=None):
    return LineSnapshot(ingredient_id, role, text, note)


def recipe(*lines, title="Frittata", instructions="Cuoci.", servings=1, description=None):
    return RecipeSnapshot(title, description, instructions, servings, tuple(lines))


BEFORE = recipe(line(A), line(B, "secondary", "q.b."))


@pytest.mark.parametrize(
    "after_lines, expected",
    [
        ([line(A), line(B, "secondary", "q.b."), line(uuid.UUID(int=7))], {uuid.UUID(int=7)}),
        ([line(A, text="150 g"), line(B, "secondary", "q.b.")], {A}),
        ([line(A), line(B, "secondary", "q.b.", note="fresco")], {B}),
        ([line(A, role="secondary"), line(B, "secondary", "q.b.")], {A}),
        ([line(A), line(B, "secondary", "q.b.")], set()),
        ([line(A)], set()),
    ],
    ids=["nuova", "dose", "nota", "ruolo", "uguale", "tolta"],
)
def test_changed_parts(after_lines, expected):
    parts = changed_parts(BEFORE, recipe(*after_lines))
    assert parts.ingredient_ids == frozenset(expected)
    assert not (parts.title or parts.servings or parts.instructions or parts.description)


def test_changed_parts_segna_titolo_e_procedimento():
    parts = changed_parts(BEFORE, replace(BEFORE, title="Altra", instructions="Nuovo."))
    assert parts.title and parts.instructions
    assert not parts.servings and not parts.description
    assert parts.ingredient_ids == frozenset()


def test_changed_parts_di_una_ricetta_nuova_segna_tutto():
    parts = changed_parts(None, BEFORE)
    assert parts.ingredient_ids == {A, B}
    assert parts.title and parts.servings and parts.instructions and parts.description


def test_lo_snapshot_va_e_torna_dal_json():
    snap = MealSnapshot("Frittata", "insalata", BEFORE)
    data = snapshot_to_json(snap)
    assert data["recipe"]["lines"][0]["ingredient_id"] == str(A)
    assert snapshot_from_json(data) == snap
    empty = MealSnapshot("Pasta", None, None)
    assert snapshot_from_json(snapshot_to_json(empty)) == empty


# --- la versione ---------------------------------------------------------------

from app.domain.recipe_changes import recipe_version  # noqa: E402


def test_la_stessa_ricetta_ha_la_stessa_versione():
    a = recipe(line(A), line(B, "secondary", "q.b."))
    b = recipe(line(B, "secondary", "q.b."), line(A))
    version = recipe_version(a, cost=None, category=None)
    assert version == recipe_version(b, cost=None, category=None)
    assert len(version) == 16
    int(version, 16)


@pytest.mark.parametrize(
    "changed",
    [
        recipe(line(A), line(B, "secondary", "q.b."), title="Altro"),
        recipe(line(A), line(B, "secondary", "q.b."), description="Nuova"),
        recipe(line(A), line(B, "secondary", "q.b."), instructions="Cuoci di più."),
        recipe(line(A), line(B, "secondary", "q.b."), servings=4),
        recipe(line(A, text="200 g"), line(B, "secondary", "q.b.")),
        recipe(line(A, "secondary"), line(B, "secondary", "q.b.")),
        recipe(line(A, note="a fuoco basso"), line(B, "secondary", "q.b.")),
    ],
    ids=["titolo", "descrizione", "procedimento", "porzioni", "dose", "ruolo", "nota"],
)
def test_ogni_campo_cambia_la_versione(changed):
    assert recipe_version(changed, cost=None, category=None) != recipe_version(
        BEFORE, cost=None, category=None
    )


@pytest.mark.parametrize(
    ("cost", "category"),
    [(3, None), (None, "Primi"), (2, "Secondi")],
    ids=["costo", "categoria", "tutti e due"],
)
def test_costo_e_categoria_cambiano_la_versione(cost, category):
    # non stanno nello snapshot (la chat non li tocca), ma un altro telefono sì
    assert "cost" not in RecipeSnapshot.__dataclass_fields__
    assert recipe_version(BEFORE, cost=cost, category=category) != recipe_version(
        BEFORE, cost=None, category=None
    )
    assert recipe_version(BEFORE, cost=cost, category=category) == recipe_version(
        replace(BEFORE), cost=cost, category=category
    )