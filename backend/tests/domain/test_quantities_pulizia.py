"""La pulizia delle dosi dell'import, nel dominio (spec 2026-10-13-pulizia-dosi-design.md).

In un file suo e non in `test_quantities.py`: l'import in cima a quello lo cambia R2, e due
rami che scrivono nello stesso punto si scontrano al merge.
"""

import pytest

from app.db.models.recipe import RecipeIngredient
from app.domain.quantities import (
    NOTE_MAX_CHARS,
    CleanDose,
    DoseShape,
    clean_dose,
    merge_notes,
    with_qb_tail,
)


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


@pytest.mark.parametrize(
    "text,quantity,note,shape",
    [
        # senza a capo né tabulazioni non è la forma dell'import: non si tocca
        (None, None, None, DoseShape.UNCHANGED),
        ("300 g", "300 g", None, DoseShape.UNCHANGED),
        ("q.b.", "q.b.", None, DoseShape.UNCHANGED),
        # scritta a mano con l'aggettivo davanti: resta com'è (decisione 3 di Mattia)
        ("freddo 50 g", "freddo 50 g", None, DoseShape.UNCHANGED),
        # solo gli spazi dell'import: la forma più comune in produzione, 2.947 righe
        ("100\n\t\t\tg", "100 g", None, DoseShape.SPACES),
        ("½\n\t\t\tcucchiaino", "½ cucchiaino", None, DoseShape.SPACES),
        ("10\n\t\t\tg + q.b.", "10 g + q.b.", None, DoseShape.SPACES),
        ("1\n\t\t\tconfezione da 250 g", "1 confezione da 250 g", None, DoseShape.SPACES),
        # davanti solo numeri: è tutta dose, nessuna nota inventata
        ("2\n\t\t\t1/2\n\t\t\tcucchiai", "2 1/2 cucchiai", None, DoseShape.SPACES),
        # solo spazi bianchi: nessuna dose
        ("\n\t\t\t", None, None, DoseShape.SPACES),
        # le parole davanti alla dose vanno nella nota (decisione 1 di Mattia)
        ("fredda\n\t\t\t330\n\t\t\tg", "330 g", "fredda", DoseShape.WORDS_BEFORE),
        ("da grattugiare\n\t\t\t50\n\t\t\tg", "50 g", "da grattugiare", DoseShape.WORDS_BEFORE),
        (
            "a temperatura ambiente\n\t\t\t100\n\t\t\tg",
            "100 g",
            "a temperatura ambiente",
            DoseShape.WORDS_BEFORE,
        ),
        ("medie\n\t\t\t3", "3", "medie", DoseShape.WORDS_BEFORE),
        # le parentesi della fonte se ne vanno, anche con un numero dentro
        ("(da pulire)\n\t\t\t2\n\t\t\tcespi", "2 cespi", "da pulire", DoseShape.WORDS_BEFORE),
        ("(circa 2 medie)\n\t\t\t110\n\t\t\tg", "110 g", "circa 2 medie", DoseShape.WORDS_BEFORE),
        # con «+ q.b.» la nota resta del suo pezzo
        (
            "da grattugiare\n\t\t\t50\n\t\t\tg + q.b.",
            "50 g + q.b.",
            "da grattugiare",
            DoseShape.WORDS_BEFORE,
        ),
        # due pezzi uniti da merge_quantities con la stessa nota: una volta sola
        (
            "freddo\n\t\t\t100\n\t\t\tg + freddo\n\t\t\t50\n\t\t\tg",
            "100 g + 50 g",
            "freddo",
            DoseShape.WORDS_BEFORE,
        ),
        # il numero nel nome non è la dose (Parte X, «36 mesi»)
        ("36 mesi\n\t\t\t50\n\t\t\tg", "50 g", "36 mesi", DoseShape.NUMBER_IN_NAME),
        ("380/420 W\n\t\t\t410\n\t\t\tg", "410 g", "380/420 W", DoseShape.NUMBER_IN_NAME),
        # una nota e «q.b.»
        ("secco\n\n\t\t\tq.b.", "q.b.", "secco", DoseShape.NOTE_QB),
        ("per friggere\n\n\t\t\tq.b.", "q.b.", "per friggere", DoseShape.NOTE_QB),
    ],
)
def test_clean_dose(text, quantity, note, shape):
    assert clean_dose(text) == CleanDose(quantity, note, shape)


def test_una_dose_pulita_non_si_pulisce_di_nuovo():
    """Il comando si rilancia senza danni perché la dose pulita non ha più la forma
    dell'import: nessun a capo, nessuna tabulazione."""
    for text in [
        "36 mesi\n\t\t\t50\n\t\t\tg",
        "secco\n\n\t\t\tq.b.",
        "100\n\t\t\tg",
        "fredda\n\t\t\t330\n\t\t\tg + q.b.",
    ]:
        pulita = clean_dose(text).quantity_text
        assert clean_dose(pulita) == CleanDose(pulita, None, DoseShape.UNCHANGED)


@pytest.mark.parametrize(
    "notes,expected",
    [
        ((None, None), None),
        (("da grattugiare", None), "da grattugiare"),
        (("freddo", "freddo"), "freddo"),
        # la nota già scritta resta davanti
        (("mia", "da grattugiare"), "mia; da grattugiare"),
        (("  ", "a fette"), "a fette"),
    ],
)
def test_merge_notes(notes, expected):
    assert merge_notes(*notes) == expected


def test_merge_notes_sta_nella_colonna():
    assert len(merge_notes("a" * 200, "b" * 200)) == NOTE_MAX_CHARS


def test_note_max_chars_e_la_colonna():
    """La colonna c'era prima della costante, e il modello non la importa da qui: un test
    le tiene uguali, perché una nota più lunga farebbe fallire la scrittura di tutta la
    ricetta, non solo di quella riga."""
    assert RecipeIngredient.__table__.c.note.type.length == NOTE_MAX_CHARS
