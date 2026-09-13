"""Il calcolo dei prezzi: l'ordinamento, l'esclusione e il costo di un lotto.

Serve ad accorgersi del giorno in cui il compromesso input/output comparirà davvero —
oggi Darkbloom è il più economico su entrambe le voci, quindi qualunque formula dà lo
stesso vincitore, e la documentazione di OpenRouter non dichiara la sua.
"""

import httpx
import pytest
import respx

from app.cli.llm_prices import Endpoint, batch_cost, main, parse_endpoints, usable
from app.core.config import get_settings

PAYLOAD = {
    "data": {
        "endpoints": [
            {
                "provider_name": "Darkbloom",
                "pricing": {"prompt": "0.000000042", "completion": "0.00000022"},
                "supported_parameters": ["response_format", "structured_outputs"],
            },
            {
                "provider_name": "DekaLLM",
                "pricing": {"prompt": "0.00000006", "completion": "0.00000033"},
                "supported_parameters": ["max_tokens", "temperature"],
            },
            {
                "provider_name": "NextBit",
                "pricing": {
                    "prompt": "0.00000009",
                    "completion": "0.0000003",
                    "input_cache_read": "0.00000005",
                },
                "supported_parameters": ["response_format", "structured_outputs"],
            },
        ]
    }
}


def test_i_prezzi_si_leggono_per_milione_di_token():
    endpoints = parse_endpoints(PAYLOAD)
    darkbloom = next(e for e in endpoints if e.provider == "Darkbloom")
    assert darkbloom.prompt == 0.042
    assert darkbloom.completion == 0.22
    assert darkbloom.cache_read is None
    assert darkbloom.structured is True

    nextbit = next(e for e in endpoints if e.provider == "NextBit")
    assert nextbit.cache_read == 0.05


def test_chi_non_regge_lo_schema_e_escluso_anche_se_costa_meno_del_secondo():
    """Il difetto che `require_parameters` previene, dimostrato sui numeri veri.

    DekaLLM a 0,060 è più economico di NextBit a 0,090, e senza il filtro finirebbe
    secondo in classifica — su un endpoint che non può rispettare `response_format`.
    """
    nomi = [e.provider for e in usable(parse_endpoints(PAYLOAD))]
    assert nomi == ["Darkbloom", "NextBit"]
    assert "DekaLLM" not in nomi


def test_il_lotto_unico_costa_meno_del_fan_out_sugli_stessi_termini():
    """Il calcolo che ha deciso la spec §12: il parallelo si sceglie per accuratezza.

    15 termini, prefisso di 3.100 token (anagrafica + prompt di sistema), 8 token di
    termine, 35 di risposta.
    """
    darkbloom = next(e for e in parse_endpoints(PAYLOAD) if e.provider == "Darkbloom")
    lotto = batch_cost(
        darkbloom, calls=1, prefix_tokens=3100, suffix_tokens=15 * 8, output_tokens=15 * 35
    )
    fan_out = batch_cost(
        darkbloom, calls=15, prefix_tokens=3100, suffix_tokens=8, output_tokens=35
    )
    assert lotto < fan_out
    # otto volte circa: l'ordine di grandezza è il dato che conta, non la cifra
    assert 5 < fan_out / lotto < 12


def test_un_endpoint_senza_cache_non_finge_di_averla():
    senza = Endpoint(
        provider="X", prompt=0.042, completion=0.22, cache_read=None, structured=True
    )
    con = Endpoint(
        provider="Y", prompt=0.042, completion=0.22, cache_read=0.01, structured=True
    )
    # a parità di tutto il resto, la cache può solo abbassare: se non c'è, il costo
    # resta quello del prezzo pieno, non zero e non un default inventato
    molte = dict(calls=10, prefix_tokens=1000, suffix_tokens=10, output_tokens=20)
    assert batch_cost(con, **molte) < batch_cost(senza, **molte)


# --- `main()`: la regola «mai un vicolo cieco» applicata a un comando diagnostico ---
#
# Nessuna chiamata vera: `respx` intercetta httpx (vedi tests/services/test_llm.py per
# lo stesso schema), e senza chiave la richiesta non deve nemmeno partire.

URL = "https://openrouter.ai/api/v1/models/google/gemma-4-26b-a4b-it/endpoints"


@pytest.fixture
def con_chiave(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


async def test_senza_chiave_stampa_un_avviso_e_non_esplode(monkeypatch, capsys):
    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        async with respx.mock:
            route = respx.get(URL).mock(
                return_value=httpx.Response(200, json=PAYLOAD)
            )
            await main()  # non deve sollevare
            assert route.call_count == 0
    finally:
        get_settings.cache_clear()

    catturato = capsys.readouterr()
    assert "OPENROUTER_API_KEY" in catturato.out


async def test_openrouter_irraggiungibile_stampa_un_avviso_e_non_esplode(
    con_chiave, capsys
):
    async with respx.mock:
        respx.get(URL).mock(side_effect=httpx.ConnectError("dns ko"))
        await main()  # non deve sollevare

    catturato = capsys.readouterr()
    assert "non raggiungibile" in catturato.out.lower()


async def test_con_dati_veri_sceglie_il_piu_economico_che_regge_lo_schema(
    con_chiave, capsys
):
    async with respx.mock:
        respx.get(URL).mock(return_value=httpx.Response(200, json=PAYLOAD))
        await main()

    catturato = capsys.readouterr()
    assert "Darkbloom" in catturato.out
    assert "lotto unico" in catturato.out
