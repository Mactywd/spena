import pytest

from app.domain.llm_pricing import cost_usd

HAIKU = "claude-haiku-5-5"


def test_il_costo_di_una_risposta_semplice():
    # È il COSTO_FINTO di tests/llm_fakes.py.
    assert cost_usd(HAIKU, input_tokens=300, output_tokens=20) == pytest.approx(0.00004)


def test_la_lettura_della_cache_costa_un_decimo():
    got = cost_usd(HAIKU, input_tokens=200, cache_read_tokens=8000, output_tokens=30)
    assert got == pytest.approx(0.000115)


def test_la_scrittura_della_cache_costa_un_quarto_in_piu():
    got = cost_usd(HAIKU, input_tokens=200, cache_write_tokens=8000, output_tokens=30)
    assert got == pytest.approx(0.001035)


def test_oltre_i_centomila_token_vale_l_altro_listino():
    assert cost_usd(HAIKU, input_tokens=150_000, output_tokens=1000) == pytest.approx(0.0775)
    # la soglia conta anche la cache
    got = cost_usd(HAIKU, input_tokens=1000, cache_read_tokens=100_000, output_tokens=0)
    assert got == pytest.approx(0.0055)


def test_centomila_esatti_sono_ancora_il_primo_listino():
    assert cost_usd(HAIKU, input_tokens=100_000, output_tokens=0) == pytest.approx(0.01)


def test_un_modello_sconosciuto_non_ha_costo():
    assert cost_usd("google/gemma-4-26b-a4b-it", input_tokens=10, output_tokens=10) is None
