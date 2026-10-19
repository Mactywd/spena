from decimal import Decimal

import pytest

from app.domain.quantities import (
    UNIT_MAX_LENGTH,
    AnchorOutOfRange,
    UnitForms,
    anchor_factor,
    decimal_text,
    equivalent_servings,
    parse_quantity,
    render_quantity,
    scale_quantity,
)


@pytest.mark.parametrize(
    "text,expected",
    [
        # non parsabili: nessun numero in testa
        ("q.b.", (None, None)),
        ("abbondante", (None, None)),
        ("facoltativo", (None, None)),
        ("alcune foglie", (None, None)),
        (None, (None, None)),
        ("", (None, None)),
        # numero nudo: la fonte non ha scritto un'unità, e non la inventiamo
        ("1", (Decimal("1"), None)),
        ("10", (Decimal("10"), None)),
        ("1/2", (Decimal("0.5"), None)),
        # dose piena
        ("300 g", (Decimal("300"), "g")),
        ("80 ml", (Decimal("80"), "ml")),
        ("1 kg", (Decimal("1"), "kg")),
        ("3 cucchiai", (Decimal("3"), "cucchiai")),
        ("1 spicchio", (Decimal("1"), "spicchio")),
        ("8 fette", (Decimal("8"), "fette")),
        ("1/2 bicchiere", (Decimal("0.5"), "bicchiere")),
        # la prosa dopo l'unità si ignora: sta in quantity_text, che resta intatto
        ("1 litro di brodo", (Decimal("1"), "litro")),
        ("500 ml per la besciamella", (Decimal("500"), "ml")),
        ("1 confezione di sfoglie per lasagne", (Decimal("1"), "confezione")),
        ("1 scatola piccola", (Decimal("1"), "scatola")),
        # «2 medie» sono due zucchine medie: l'aggettivo diventa unità, ed è giusto
        # così — «4 medie» a ×2 si legge bene, e distinguere un aggettivo da
        # un'unità sarebbe analisi grammaticale dentro un parser di numeri
        ("2 medie", (Decimal("2"), "medie")),
        # le somme di merge_quantities: stessa unità si sommano...
        ("500 g + 50 g", (Decimal("550"), "g")),
        ("1 + 2", (Decimal("3"), None)),
        # ...unità diverse no: la somma di due cose diverse non è un numero
        ("500 g + 2 cucchiai", (None, None)),
        # «q.b.» accanto a una dose non la rende illeggibile: i 300 g si riscalano, e il
        # «+ q.b.» lo rimette accanto `with_qb_tail` (Mattia, 2026-10-13)
        ("300 g + q.b.", (Decimal("300"), "g")),
        ("10 g + q.b.", (Decimal("10"), "g")),
        ("1 pizzico + q.b.", (Decimal("1"), "pizzico")),
        ("q.b. per spolverare + 50 g", (Decimal("50"), "g")),
        # solo «q.b.», o «q.b.» con quel che non si legge: niente da riscalare
        ("q.b. + q.b.", (None, None)),
        ("abbondante + q.b.", (None, None)),
        # maiuscole e spazi non contano
        ("  300  G  ", (Decimal("300"), "g")),
        # numero misto: «2 1/2» sono due e mezzo, e leggerne solo il 2 vorrebbe dire
        # riporzionare una dose dimezzata senza dirlo a nessuno
        ("2 1/2 cucchiai", (None, None)),
        ("1 1/2", (None, None)),
        ("2  1/2 tazze", (None, None)),
        # le frazioni di un carattere solo, come le scrive GialloZafferano
        ("½", (Decimal("0.5"), None)),
        ("½ cucchiaino", (Decimal("0.5"), "cucchiaino")),
        ("¼ cucchiaino", (Decimal("0.25"), "cucchiaino")),
        ("¾ tazza", (Decimal("0.75"), "tazza")),
        # col numero intero davanti è una dose sola, e «½» non è mai un'unità
        ("1 ½ cucchiai", (Decimal("1.5"), "cucchiai")),
        ("1½", (Decimal("1.5"), None)),
        ("1 ½", (Decimal("1.5"), None)),
        # le somme di merge_quantities con le frazioni: «½ + ½» sono due metà dello
        # stesso limone, cioè uno
        ("1 + ½", (Decimal("1.5"), None)),
        ("½ + ½", (Decimal("1"), None)),
    ],
)
def test_parse_quantity(text, expected):
    assert parse_quantity(text) == expected


def test_una_frazione_impossibile_non_solleva():
    """Una dose che non si capisce non è un errore: è una dose che non si scala."""
    assert parse_quantity("1/0 bicchiere") == (None, None)


@pytest.mark.parametrize(
    "lunghezza,atteso_unita",
    [
        (UNIT_MAX_LENGTH, "c" * UNIT_MAX_LENGTH),
        (UNIT_MAX_LENGTH + 1, None),
    ],
)
def test_una_parola_piu_lunga_della_colonna_non_e_una_unita(lunghezza, atteso_unita):
    """Il confine è quello di `units.key`, e sta qui perché la colonna lo prende da qui.

    Una parola oltre il limite arriva da un incollaggio senza spazio — «2 cucchiai
    dioliaextravergine…» — e depositarla farebbe fallire con un DataError la
    scrittura di tutta la ricetta, non solo di quella riga.
    """
    testo = f"2 {'c' * lunghezza}"
    atteso_valore = Decimal("2") if atteso_unita else None
    assert parse_quantity(testo) == (atteso_valore, atteso_unita)


CUCCHIAIO = UnitForms(key="cucchiai", singular="cucchiaio", plural="cucchiai")
GRAMMO = UnitForms(key="g", singular="g", plural="g")
NON_DECISA = UnitForms(key="costa")


@pytest.mark.parametrize(
    "value,factor,expected",
    [
        (Decimal("300"), Decimal("2"), Decimal("600")),
        (Decimal("300"), Decimal("0.5"), Decimal("150")),
        (Decimal("3"), Decimal("2") / Decimal("3"), Decimal("2")),
        (Decimal("1"), Decimal("0.5"), Decimal("0.5")),
    ],
)
def test_scale_quantity(value, factor, expected):
    assert scale_quantity(value, factor) == expected


@pytest.mark.parametrize(
    "value,unit,expected",
    [
        # il plurale si sceglie sul valore: singolare solo a 1 esatto
        (Decimal("1"), CUCCHIAIO, "1 cucchiaio"),
        (Decimal("6"), CUCCHIAIO, "6 cucchiai"),
        (Decimal("0.5"), CUCCHIAIO, "0,5 cucchiai"),
        # virgola decimale e zeri di coda tolti
        (Decimal("1.500"), CUCCHIAIO, "1,5 cucchiai"),
        (Decimal("550"), GRAMMO, "550 g"),
        # unità non ancora decisa: si mostra la parola come è arrivata, mai un errore
        (Decimal("2"), NON_DECISA, "2 costa"),
        # numero nudo: «1» di una cipolla è una cipolla, non «1 pezzo»
        (Decimal("2"), None, "2"),
    ],
)
def test_render_quantity(value, unit, expected):
    assert render_quantity(value, unit) == expected


# R2, secondo modo: la dose di una riga fissata a mano, e il resto che la segue


@pytest.mark.parametrize(
    "base,amount,expected",
    [
        (Decimal("400"), Decimal("150"), Decimal("0.375")),
        (Decimal("300"), Decimal("112.5"), Decimal("0.375")),
        # un mezzo bicchiere fissato a uno: il doppio
        (Decimal("0.5"), Decimal("1"), Decimal("2")),
        (Decimal("300"), Decimal("300"), Decimal("1")),
        # gli estremi sono dentro: cinquanta volte in giù e in su
        (Decimal("300"), Decimal("6"), Decimal("0.02")),
        (Decimal("300"), Decimal("15000"), Decimal("50")),
    ],
)
def test_anchor_factor(base, amount, expected):
    assert anchor_factor(base, amount) == expected


@pytest.mark.parametrize("amount", [Decimal("5.999"), Decimal("15000.001"), Decimal("0.001")])
def test_anchor_factor_oltre_50_volte(amount):
    with pytest.raises(AnchorOutOfRange) as caught:
        anchor_factor(Decimal("300"), amount)
    # gli estremi arrivano già scalati come si mostrano: la frase che li cita non
    # promette un numero che poi si rifiuta
    assert caught.value.low == Decimal("6")
    assert caught.value.high == Decimal("15000")


@pytest.mark.parametrize(
    "servings,factor,expected",
    [
        (4, Decimal("0.375"), Decimal("1.5")),
        # sotto una porzione, due decimali: «≈ 0,75» e non «≈ 0,8»
        (2, Decimal("0.375"), Decimal("0.75")),
        (4, Decimal("1"), Decimal("4")),
        (3, Decimal(1) / Decimal(3), Decimal("1")),
        (2, Decimal(1) / Decimal(3), Decimal("0.67")),
        (1, Decimal("0.02"), Decimal("0.02")),
        # metà in su: 1,85 → 1,9
        (4, Decimal("0.4625"), Decimal("1.9")),
        (50, Decimal("50"), Decimal("2500")),
    ],
)
def test_equivalent_servings(servings, factor, expected):
    assert equivalent_servings(servings, factor) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (Decimal("150"), "150"),
        (Decimal("150.500"), "150.5"),
        # un «1e3» arrivato dalla query: niente esponenti nello storico
        (Decimal("1E+3"), "1000"),
        (Decimal("0.375"), "0.375"),
        (Decimal("50.000000"), "50"),
    ],
)
def test_decimal_text(value, expected):
    assert decimal_text(value) == expected
