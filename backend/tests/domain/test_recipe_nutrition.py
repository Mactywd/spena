"""I nutrienti di una ricetta, la parte pura (S4, fetta 2): senza database, come le regole.

Una riga si conta se ha una dose letta, un alimento CIQUAL e un peso; altrimenti è fuori
dal conto e dice perché — «q.b.» per primo (decisione di Mattia del 2026-10-13). Un
nutriente che una riga contata non ha non diventa zero: si dice su quante righe c'è.
"""

import uuid
from decimal import Decimal

import pytest

from app.domain.recipe_nutrition import (
    NutritionLine,
    classify_unit,
    density_for,
    line_grams,
    recipe_nutrition,
    round_nutrient,
)

PASTA = {"kcal": 357.0, "protein": 12.5, "iron": 1.4}
POMODORO = {"kcal": 18.0, "protein": 0.86, "iron": 0.3}
AGLIO = {"kcal": 131.0, "protein": 5.8}
OLIO = {"kcal": 900.0, "protein": 0.0}
BASILICO = {"kcal": 31.0}


def _riga(nome, testo, valore, chiave=None, singolare=None, coppia=None, per_100g=None):
    return NutritionLine(
        ingredient_id=uuid.uuid4(),
        ingredient_name=nome,
        quantity_text=testo,
        value=None if valore is None else Decimal(str(valore)),
        unit_key=chiave,
        unit_singular=singolare,
        pair_grams=None if coppia is None else Decimal(str(coppia)),
        per_100g=per_100g,
    )


@pytest.mark.parametrize(
    ("chiave", "singolare", "atteso"),
    [
        ("g", None, ("mass", Decimal("1"), False)),
        ("gr", "gr", ("mass", Decimal("1"), False)),
        ("grammi", "grammo", ("mass", Decimal("1"), False)),
        ("kg", None, ("mass", Decimal("1000"), False)),
        ("etti", "etto", ("mass", Decimal("100"), False)),
        ("mg", None, ("mass", Decimal("0.001"), False)),
        ("ml", None, ("volume", Decimal("1"), False)),
        ("cl", None, ("volume", Decimal("10"), False)),
        ("dl", None, ("volume", Decimal("100"), False)),
        ("litri", "litro", ("volume", Decimal("1000"), False)),
        # la dose senza unità («2» uova) e «pezzo» sono la stessa coppia
        (None, None, ("pair", None, True)),
        ("pezzi", "pezzo", ("pair", None, True)),
        ("cucchiai", "cucchiaio", ("pair", None, False)),
        ("spicchio", None, ("pair", None, False)),
    ],
)
def test_classify_unit(chiave, singolare, atteso):
    tipo = classify_unit(chiave, singolare)
    assert (tipo.measure, tipo.factor, tipo.piece) == atteso


@pytest.mark.parametrize(
    ("nome", "densita"),
    [
        ("olio di oliva", Decimal("0.92")),
        ("Olio extravergine di oliva", Decimal("0.92")),
        ("miele", Decimal("1.42")),
        ("sciroppo d'acero", Decimal("1.33")),
        ("latte condensato", Decimal("1.29")),
        ("latte", Decimal("1")),
    ],
)
def test_density_for(nome, densita):
    assert density_for(nome) == densita


def test_line_grams():
    grammi = classify_unit("g", None)
    decilitri = classify_unit("dl", None)
    litri = classify_unit("l", None)
    cucchiai = classify_unit("cucchiai", None)
    pezzo = classify_unit(None, None)

    assert line_grams(value=Decimal("180"), kind=grammi, pair_grams=None, ingredient_name="pasta") == Decimal("180")
    # l'olio pesa meno dell'acqua: 2 dl sono 184 g
    assert line_grams(value=Decimal("2"), kind=decilitri, pair_grams=None, ingredient_name="olio di oliva") == Decimal("184.00")
    assert line_grams(value=Decimal("1"), kind=litri, pair_grams=None, ingredient_name="latte") == Decimal("1000")
    assert line_grams(value=Decimal("2"), kind=cucchiai, pair_grams=Decimal("12"), ingredient_name="olio") == Decimal("24")
    assert line_grams(value=Decimal("2"), kind=cucchiai, pair_grams=None, ingredient_name="olio") is None
    assert line_grams(value=Decimal("2"), kind=pezzo, pair_grams=Decimal("50"), ingredient_name="uova") == Decimal("100")


def test_la_pasta_al_pomodoro():
    """La ricetta del seme: quattro righe contate, il basilico «q.b.» fuori e detto."""
    righe = [
        _riga("pasta", "180 g", 180, "g", per_100g=PASTA),
        _riga("pomodoro", "400 g", 400, "g", per_100g=POMODORO),
        _riga("aglio", "1 spicchio", 1, "spicchio", coppia=5, per_100g=AGLIO),
        _riga("olio di oliva", "2 cucchiai", 2, "cucchiai", coppia=12, per_100g=OLIO),
        _riga("basilico", "q.b.", None, per_100g=BASILICO),
    ]

    conto = recipe_nutrition(righe, servings=2)

    assert (conto.lines_total, conto.lines_counted) == (5, 4)
    # 642,6 + 72 + 6,55 + 216
    assert conto.totals["kcal"] == pytest.approx(937.15)
    assert conto.per_serving["kcal"] == pytest.approx(468.575)
    assert conto.lines_with == {"kcal": 4, "protein": 4, "iron": 2}
    assert [(m.ingredient_name, m.quantity_text, m.reason) for m in conto.missing] == [
        ("basilico", "q.b.", "no_quantity"),
    ]


def test_ogni_riga_fuori_dal_conto_dice_perche():
    righe = [
        _riga("sale", "q.b.", None, per_100g={"kcal": 0.0}),
        _riga("zafferano", "1 bustina", 1, "bustina", coppia=0.1, per_100g=None),
        _riga("aglio", "1 spicchio", 1, "spicchio", singolare="spicchio", per_100g=AGLIO),
        _riga("uova", "2", 2, per_100g={"kcal": 140.0}),
    ]

    conto = recipe_nutrition(righe, servings=4)

    assert conto.lines_counted == 0
    assert [(m.ingredient_name, m.reason, m.unit_label) for m in conto.missing] == [
        ("sale", "no_quantity", None),
        ("zafferano", "no_nutrients", None),
        ("aglio", "no_weight", "spicchio"),
        ("uova", "no_weight", "pezzo"),
    ]


def test_un_nutriente_che_una_riga_non_ha_resta_parziale_mai_zero():
    righe = [
        _riga("pasta", "100 g", 100, "g", per_100g={"kcal": 357.0, "iron": 1.4}),
        _riga("aglio", "1 spicchio", 1, "spicchio", coppia=5, per_100g={"kcal": 131.0}),
    ]

    conto = recipe_nutrition(righe, servings=None)

    assert conto.totals["iron"] == pytest.approx(1.4)
    assert conto.lines_with["iron"] == 1 and conto.lines_with["kcal"] == 2
    assert "vitamin_d" not in conto.totals
    assert conto.per_serving is None


def test_nessuna_riga_contata():
    conto = recipe_nutrition([_riga("basilico", "q.b.", None, per_100g=BASILICO)], servings=2)

    assert (conto.lines_counted, conto.totals, conto.lines_with) == (0, {}, {})
    assert conto.per_serving == {}


def test_porzioni_zero_o_assenti_non_dividono():
    righe = [_riga("pasta", "100 g", 100, "g", per_100g=PASTA)]

    assert recipe_nutrition(righe, servings=0).per_serving is None
    assert recipe_nutrition(righe, servings=None).per_serving is None


@pytest.mark.parametrize(
    ("valore", "unita", "atteso"),
    [(937.15, "kcal", 937.0), (468.575, "kcal", 469.0), (12.345, "g", 12.3), (0.256, "mg", 0.26), (0.0, "g", 0.0)],
)
def test_round_nutrient(valore, unita, atteso):
    assert round_nutrient(valore, unita) == atteso
