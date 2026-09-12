import pytest

from app.services.recipe_import.giallozafferano import (
    clean_instructions,
    normalize_steps,
    strip_photo_references,
)


@pytest.mark.parametrize(
    "testo, atteso",
    [
        # i casi veri, copiati dalla forma che la fonte produce
        (
            "Lasciate rosolare lo speck per circa 5 minuti 2 .",
            "Lasciate rosolare lo speck per circa 5 minuti.",
        ),
        ("Riducetele a striscioline di circa 1 cm 1 .", "Riducetele a striscioline di circa 1 cm."),
        ("Di tanto in tanto mescolate 3", "Di tanto in tanto mescolate"),
        ("Unite il Parmigiano grattugiato 7 , poi mescolate.",
         "Unite il Parmigiano grattugiato, poi mescolate."),
        # più rimandi di fila
        ("Versate il latte e mescolate 6 7 .", "Versate il latte e mescolate."),
        # lo spazio insecabile che la fonte usa davvero
        ("Mettetelo da parte 4 .\xa0", "Mettetelo da parte."),
        # i casi che NON devono cambiare: è qui che una regola generosa fa danni
        ("Dividete l'impasto in 4.", "Dividete l'impasto in 4."),
        ("Cuocete per 10 minuti, poi scolate.", "Cuocete per 10 minuti, poi scolate."),
        ("Aggiungete 2 uova intere.", "Aggiungete 2 uova intere."),
        ("Infornate a 180 °C.", "Infornate a 180 °C."),
    ],
)
def test_strip_photo_references(testo, atteso):
    assert strip_photo_references(testo) == atteso


def test_normalize_steps_accetta_una_lista_di_stringhe():
    assert normalize_steps(["Primo.", "Secondo."]) == ["Primo.", "Secondo."]


def test_normalize_steps_accetta_gli_oggetti_howtostep():
    raw = [
        {"@type": "HowToStep", "text": "Primo."},
        {"@type": "HowToStep", "text": "Secondo."},
    ]
    assert normalize_steps(raw) == ["Primo.", "Secondo."]


def test_normalize_steps_accetta_una_stringa_sola():
    assert normalize_steps("Tutto in un paragrafo.") == ["Tutto in un paragrafo."]


def test_normalize_steps_su_niente_non_esplode():
    assert normalize_steps(None) == []
    assert normalize_steps([]) == []


def test_clean_instructions_unisce_i_passaggi_con_una_riga_vuota():
    raw = ["Scaldate l'olio 1 .", "Unite i pomodori 2 .", "   "]
    assert clean_instructions(raw) == "Scaldate l'olio.\n\nUnite i pomodori."
