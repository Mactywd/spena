"""Il vocabolario di «Sostituisci» (R5), e il contesto di una ricetta.

Il contesto si ricava dalla categoria della ricetta, senza AI: dolce se la prima parola
è «dolci» (le categorie di GialloZafferano sono «Dolci e Desserts», «Primi piatti»…),
salato in ogni altro caso. Il burro nella besciamella non è il burro nei biscotti.
"""

import pytest

from app.domain.substitutions import (
    SUBSTITUTE_NOTE_MAX,
    SUBSTITUTES_MAX,
    SubstitutionContext,
    clean_note,
    recipe_context,
)


@pytest.mark.parametrize(
    "category,expected",
    [
        ("Dolci e Desserts", SubstitutionContext.SWEET),
        ("Dolci", SubstitutionContext.SWEET),
        ("  dolci e desserts ", SubstitutionContext.SWEET),
        ("DOLCI", SubstitutionContext.SWEET),
        ("Primi piatti", SubstitutionContext.SAVORY),
        ("Secondi piatti", SubstitutionContext.SAVORY),
        ("Antipasti", SubstitutionContext.SAVORY),
        # pane e pizza, ma anche brioche: la voce generale è salata, e dove sbaglia c'è la
        # correzione della ricetta (spec §3.1)
        ("Lievitati", SubstitutionContext.SAVORY),
        # la prima parola, non l'inizio della stringa
        ("Dolcificanti", SubstitutionContext.SAVORY),
        ("", SubstitutionContext.SAVORY),
        ("   ", SubstitutionContext.SAVORY),
        # le ricette scritte a mano e quelle del seme non hanno categoria
        (None, SubstitutionContext.SAVORY),
    ],
)
def test_il_contesto_viene_dalla_prima_parola_della_categoria(category, expected):
    assert recipe_context(category) is expected


@pytest.mark.parametrize(
    "note,expected",
    [
        (None, None),
        ("", None),
        ("   ", None),
        ("metà dose", "metà dose"),
        ("  metà   dose  ", "metà dose"),
        ("sciolto\nin acqua", "sciolto in acqua"),
    ],
)
def test_una_nota_si_pulisce_e_vuota_non_c_e(note, expected):
    assert clean_note(note) == expected


def test_i_limiti():
    assert SUBSTITUTES_MAX == 3
    assert SUBSTITUTE_NOTE_MAX == 60


def test_l_ordine_dei_contesti_e_salato_poi_dolce():
    """L'ordine delle schede in Anagrafica: la gran parte del ricettario è salata."""
    assert [c.value for c in SubstitutionContext] == ["salato", "dolce"]
