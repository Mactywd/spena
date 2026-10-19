"""La chiave del webhook di H2: lunga, casuale, conservata solo come impronta.

256 bit casuali non si indovinano, quindi l'impronta è un SHA-256 semplice (un hash lento
serve alle password, che si indovinano). Il confronto è a tempo costante.
"""

import pytest

from app.core.webhook_token import (
    TOKEN_LENGTH,
    looks_like_token,
    new_token,
    token_hash,
    token_matches,
)


def test_una_chiave_nuova_e_lunga_casuale_e_ben_fatta():
    prima, seconda = new_token(), new_token()

    assert len(prima) == TOKEN_LENGTH == 43
    assert looks_like_token(prima)
    assert prima != seconda


@pytest.mark.parametrize(
    "candidata",
    ["", "a" * 42, "a" * 44, "a" * 42 + "!", "a" * 42 + " ", "à" * 43],
)
def test_cosa_non_ha_la_forma_di_una_chiave(candidata):
    assert not looks_like_token(candidata)


def test_la_chiave_giusta_passa():
    chiave = new_token()

    assert token_matches(chiave, token_hash(chiave))


def test_una_chiave_sbagliata_no():
    assert not token_matches(new_token(), token_hash(new_token()))


def test_senza_una_chiave_configurata_niente_passa():
    assert not token_matches(new_token(), None)


def test_si_conserva_solo_l_impronta():
    chiave = new_token()
    impronta = token_hash(chiave)

    assert len(impronta) == 64
    assert chiave not in impronta
    assert impronta == token_hash(chiave)
