"""I nutrienti di una ricetta letti dal database (S4, fetta 2): le righe, gli alimenti
CIQUAL scelti, i pesi delle coppie, sull'unità canonica e col pezzo."""

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select

from app.db.models.ingredient import Ingredient
from app.db.models.recipe import RecipeSource
from app.db.models.unit import Unit
from app.domain.ciqual import CiqualRow
from app.repositories.ciqual import upsert_foods
from app.repositories.recipes import create_recipe
from app.repositories.units import set_unit_forms
from app.services.ingredient_nutrition import choose_food
from app.services.recipe_nutrition import recipe_nutrition_of
from app.services.unit_grams import set_grams

ALIMENTI = [
    CiqualRow("90003", "Pâtes sèches, crues", None, {"kcal": 357.0}),
    CiqualRow("90001", "Tomate, crue", None, {"kcal": 18.0}),
    CiqualRow("90005", "Ail, cru", None, {"kcal": 131.0}),
    CiqualRow("90006", "Huile d'olive vierge extra", None, {"kcal": 900.0}),
    CiqualRow("90009", "Oeuf, cru", None, {"kcal": 140.0}),
]


async def _voci(db_session, *nomi_reparti):
    voci = {nome: Ingredient(name=nome, display_name=nome.capitalize(), category=reparto) for nome, reparto in nomi_reparti}
    db_session.add_all(voci.values())
    await db_session.flush()
    return voci


async def _ricetta(db_session, voci, titolo, righe, porzioni=2):
    ricetta = await create_recipe(
        db_session, title=titolo, description=None, instructions="Si cucina.", servings=porzioni,
        source=RecipeSource.MANUAL, source_ref=None, embedding=None,
        ingredients=[(voci[nome].id, ruolo, dose, None) for nome, ruolo, dose in righe],
    )
    return ricetta.id


async def _unita(db_session, chiave):
    return (await db_session.execute(select(Unit.id).where(Unit.key == chiave))).scalar_one()


async def test_la_pasta_al_pomodoro_dal_database(db_session):
    await upsert_foods(db_session, ALIMENTI)
    voci = await _voci(
        db_session, ("pasta", "cereali"), ("pomodoro", "verdura"), ("aglio", "verdura"),
        ("olio di oliva", "condimenti"), ("basilico", "spezie"),
    )
    ricetta = await _ricetta(db_session, voci, "Pasta al pomodoro", [
        ("pasta", "primary", "180 g"), ("pomodoro", "primary", "400 g"),
        ("aglio", "secondary", "1 spicchio"), ("olio di oliva", "secondary", "2 cucchiai"),
        ("basilico", "secondary", "q.b."),
    ])
    for nome, codice in [("pasta", "90003"), ("pomodoro", "90001"), ("aglio", "90005"), ("olio di oliva", "90006")]:
        await choose_food(db_session, voci[nome].id, codice)
    await set_grams(db_session, voci["aglio"].id, await _unita(db_session, "spicchio"), Decimal("5"))
    await set_grams(db_session, voci["olio di oliva"].id, await _unita(db_session, "cucchiai"), Decimal("12"))

    conto = await recipe_nutrition_of(db_session, ricetta)

    assert (conto.lines_total, conto.lines_counted, conto.servings) == (5, 4, 2)
    assert conto.per_serving["kcal"] == pytest.approx(468.575)
    assert [(m.ingredient_name, m.reason) for m in conto.missing] == [("basilico", "no_quantity")]


async def test_il_pezzo_e_le_unita_canoniche_pesano_uguale(db_session):
    await upsert_foods(db_session, ALIMENTI)
    voci = await _voci(db_session, ("uova", "altro"), ("aglio", "verdura"))
    a = await _ricetta(db_session, voci, "A", [("uova", "primary", "2"), ("aglio", "secondary", "1 spicchio")])
    b = await _ricetta(db_session, voci, "B", [("uova", "primary", "1 pezzo"), ("aglio", "secondary", "2 spicchi")])
    await set_unit_forms(db_session, "spicchi", "spicchio", "spicchi")
    await choose_food(db_session, voci["uova"].id, "90009")
    await choose_food(db_session, voci["aglio"].id, "90005")
    await set_grams(db_session, voci["uova"].id, None, Decimal("50"))
    await set_grams(db_session, voci["aglio"].id, await _unita(db_session, "spicchio"), Decimal("5"))

    conto_a = await recipe_nutrition_of(db_session, a)
    conto_b = await recipe_nutrition_of(db_session, b)

    # A: 100 g d'uovo (140) e 5 g d'aglio (6,55); B: 50 g d'uovo (70) e 10 g d'aglio (13,1)
    assert conto_a.totals["kcal"] == pytest.approx(146.55)
    assert conto_b.totals["kcal"] == pytest.approx(83.1)
    assert conto_a.lines_counted == conto_b.lines_counted == 2


async def test_una_ricetta_che_non_c_e(db_session):
    with pytest.raises(LookupError):
        await recipe_nutrition_of(db_session, uuid.uuid4())
