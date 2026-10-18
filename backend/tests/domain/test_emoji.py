"""L'elenco chiuso delle figure (S12) e la sua verifica: senza database, come le regole.

L'elenco è il confine fra quel che l'AI o una persona possono scrivere nella colonna e
quel che no. La bozza lo ferma a Emoji 14.0 perché una figura più recente, su un
telefono non aggiornato, diventa un quadratino vuoto (§5.2): le prove qui sotto
guardano proprio le figure che un modello proporrebbe per prime e che non ci devono
essere.
"""

import pytest

from app.domain.emoji import (
    EMOJI_MAX_LENGTH,
    INGREDIENT_EMOJI,
    NO_EMOJI,
    canonical_emoji,
    shown_emoji,
)

VS16 = "️"


@pytest.mark.parametrize(
    ("scritta", "attesa"),
    [
        ("🥕", "🥕"),
        # il peperoncino è nell'elenco col selettore di variante, e lo si accetta con e senza
        ("\U0001F336️", "\U0001F336️"),
        ("\U0001F336", "\U0001F336️"),
        (" 🥕 ", "🥕"),
        ("🚗", None),
        ("", None),
        ("🥕🥕", None),
        # Emoji 15.0: zenzero e baccello, le prime che un modello proporrebbe
        ("\U0001FADA", None),
        ("\U0001FADB", None),
        # la parola con cui l'AI dice «nessuna» non è una figura
        ("nessuna", None),
    ],
)
def test_canonical_emoji_accetta_solo_l_elenco(scritta, attesa):
    assert canonical_emoji(scritta) == attesa


@pytest.mark.parametrize(
    ("colonna", "a_video"),
    [(None, None), (NO_EMOJI, None), ("🥕", "🥕")],
)
def test_shown_emoji_tiene_la_stringa_vuota_nel_backend(colonna, a_video):
    """«Non deciso» e «nessuna» sono lo stesso ripiego per chi guarda: la differenza
    serve solo al comando dell'AI, e fuori dal backend non esce."""
    assert shown_emoji(colonna) == a_video


def test_l_elenco_non_ha_doppioni():
    """Nemmeno uno che differisca solo per il selettore di variante: la verifica li
    tratterebbe come la stessa figura, e la griglia ne mostrerebbe due."""
    nude = [voce.replace(VS16, "") for voce in INGREDIENT_EMOJI]
    assert len(nude) == len(set(nude))
    assert len(INGREDIENT_EMOJI) == 148


def test_l_elenco_e_fermo_a_emoji_14():
    """Le figure della 15.0 e della 15.1 che riguardano la cucina restano fuori, e con
    loro ogni sequenza ZWJ (U+200D): fino alla 14.0 nessuna figura di cibo, bevande o
    casa ne usa una, dalla 15.1 il lime e il fungo marrone sì."""
    vietate = {"\U0001FADA", "\U0001FADB", "\U0001FAAD", "\U0001FAAE"}
    for voce in INGREDIENT_EMOJI:
        assert "‍" not in voce, voce
        assert not (set(voce) & vietate), voce


def test_le_tre_figure_col_selettore_lo_portano():
    """Peperoncino, candela e cestino si disegnano come emoji solo col selettore di
    variante: senza, alcuni sistemi li mostrano come simboli in bianco e nero. Una copia
    dell'elenco che lo perdesse cambierebbe figura senza che niente fallisca."""
    for voce in ("\U0001F336️", "\U0001F56F️", "\U0001F5D1️"):
        assert voce in INGREDIENT_EMOJI


def test_ogni_figura_sta_nella_colonna():
    assert all(0 < len(voce) <= EMOJI_MAX_LENGTH for voce in INGREDIENT_EMOJI)


def test_nessuna_non_e_una_figura():
    """La stringa vuota è «nessuna» nella colonna: se fosse anche una voce dell'elenco,
    una figura scelta e una non scelta sarebbero la stessa cosa."""
    assert NO_EMOJI not in INGREDIENT_EMOJI
    assert "nessuna" not in INGREDIENT_EMOJI
