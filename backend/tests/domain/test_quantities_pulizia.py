"""La pulizia delle dosi dell'import, nel dominio (spec 2026-10-13-pulizia-dosi-design.md).

In un file suo e non in `test_quantities.py`: l'import in cima a quello lo cambia R2, e due
rami che scrivono nello stesso punto si scontrano al merge.
"""

import pytest

from app.domain.quantities import with_qb_tail


@pytest.mark.parametrize(
    "display,text,expected",
    [
        ("100 g", "50 g + q.b.", "100 g + q.b."),
        ("2 pizzichi", "1 pizzico + q.b.", "2 pizzichi + q.b."),
        # il «q.b.» torna con le sue parole, in fondo
        ("100 g", "q.b. per spolverare + 50 g", "100 g + q.b. per spolverare"),
        # senza «q.b.» la dose riscalata è quella e basta
        ("100 g", "50 g", "100 g"),
        ("100 g", None, "100 g"),
    ],
)
def test_with_qb_tail(display, text, expected):
    assert with_qb_tail(display, text) == expected
