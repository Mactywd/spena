from decimal import Decimal

import pytest

from app.domain.quantities import parse_quantity


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
        ("300 g + q.b.", (None, None)),
        # maiuscole e spazi non contano
        ("  300  G  ", (Decimal("300"), "g")),
    ],
)
def test_parse_quantity(text, expected):
    assert parse_quantity(text) == expected


def test_una_frazione_impossibile_non_solleva():
    """Una dose che non si capisce non è un errore: è una dose che non si scala."""
    assert parse_quantity("1/0 bicchiere") == (None, None)
