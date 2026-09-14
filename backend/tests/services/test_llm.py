"""Il client di OpenRouter: la richiesta che costruisce e i modi in cui degrada.

`respx` intercetta httpx senza rete: è già fra le dipendenze `dev`. I test sulla
**forma della richiesta** sono quelli che contano di più — sono l'unico posto in cui
si dimostra che gli header di attribuzione, lo schema stretto e l'instradamento per
prezzo arrivano davvero a OpenRouter. Nessun test che inietta un client finto potrebbe
vederlo.
"""

import json

import httpx
import pytest
import respx

from app.core.config import get_settings
from app.services.ai_recipes import DRAFT_SCHEMA
from app.services.llm import LlmUnavailable, complete_json
from app.services.recipe_import.decide import COLLAPSE_SCHEMA, TERM_SCHEMA

URL = "https://openrouter.ai/api/v1/chat/completions"

SCHEMA = {
    "type": "object",
    "properties": {"esito": {"type": "string"}},
    "required": ["esito"],
    "additionalProperties": False,
}


def risposta(contenuto: dict) -> httpx.Response:
    return httpx.Response(
        200, json={"choices": [{"message": {"content": json.dumps(contenuto)}}]}
    )


@pytest.fixture
def con_chiave(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    monkeypatch.setenv("OPENROUTER_APP_URL", "https://esempio.invalid")
    yield
    get_settings.cache_clear()


async def test_una_risposta_valida_torna_il_dizionario(con_chiave):
    async with respx.mock:
        respx.post(URL).mock(return_value=risposta({"esito": "va bene"}))
        assert await complete_json(
            system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
        ) == {"esito": "va bene"}


async def test_la_richiesta_porta_attribuzione_schema_e_instradamento(con_chiave):
    async with respx.mock:
        route = respx.post(URL).mock(return_value=risposta({"esito": "ok"}))
        await complete_json(
            system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
        )

    richiesta = route.calls.last.request
    assert richiesta.headers["authorization"] == "Bearer chiave-finta"
    assert richiesta.headers["x-title"] == "Spena Import Ricette"
    assert richiesta.headers["http-referer"] == "https://esempio.invalid"

    corpo = json.loads(richiesta.content)
    assert corpo["model"] == "google/gemma-4-26b-a4b-it"
    formato = corpo["response_format"]
    assert formato["type"] == "json_schema"
    assert formato["json_schema"]["strict"] is True
    assert formato["json_schema"]["name"] == "prova"
    assert formato["json_schema"]["schema"] == SCHEMA
    # require_parameters è la riga che porta il peso: quattro degli undici endpoint di
    # questo modello non supportano structured_outputs, e uno di quelli è il secondo
    # più economico. Senza il flag, l'ordinamento per prezzo ci manda addosso.
    assert corpo["provider"] == {"sort": "price", "require_parameters": True}
    # allow_fallbacks non si manda: il suo default `true` è la ragione per cui non
    # pinniamo un provider, e scriverlo esplicitamente inviterebbe a cambiarlo
    assert "allow_fallbacks" not in corpo["provider"]


async def test_app_url_vuota_omette_lheader_invece_di_mandarlo_vuoto(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    monkeypatch.setenv("OPENROUTER_APP_URL", "")
    try:
        async with respx.mock:
            route = respx.post(URL).mock(return_value=risposta({"esito": "ok"}))
            await complete_json(
                system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
            )
        assert "http-referer" not in route.calls.last.request.headers
    finally:
        get_settings.cache_clear()


async def test_provider_only_valorizzata_pinna_e_non_ordina(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    monkeypatch.setenv("OPENROUTER_PROVIDER_ONLY", "darkbloom, deepinfra")
    try:
        async with respx.mock:
            route = respx.post(URL).mock(return_value=risposta({"esito": "ok"}))
            await complete_json(
                system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
            )
        corpo = json.loads(route.calls.last.request.content)
        assert corpo["provider"] == {
            "only": ["darkbloom", "deepinfra"], "require_parameters": True
        }
    finally:
        get_settings.cache_clear()


async def test_senza_chiave_non_parte_nessuna_richiesta(monkeypatch):
    """La degradazione dichiarata, e prima della rete: non si spreca un giro."""
    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        async with respx.mock:
            route = respx.post(URL).mock(return_value=risposta({"esito": "ok"}))
            with pytest.raises(LlmUnavailable, match="OPENROUTER_API_KEY"):
                await complete_json(
                    system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
                )
            assert route.call_count == 0
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("codice", [400, 402, 429, 500, 503])
async def test_ogni_codice_derrore_diventa_llm_unavailable(con_chiave, codice):
    async with respx.mock:
        respx.post(URL).mock(return_value=httpx.Response(codice, text="no"))
        with pytest.raises(LlmUnavailable, match=str(codice)):
            await complete_json(
                system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
            )


async def test_un_corpo_senza_choices_diventa_llm_unavailable(con_chiave):
    async with respx.mock:
        respx.post(URL).mock(return_value=httpx.Response(200, json={"error": "boh"}))
        with pytest.raises(LlmUnavailable):
            await complete_json(
                system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
            )


async def test_un_contenuto_non_json_diventa_llm_unavailable(con_chiave):
    """Con lo schema stretto non dovrebbe capitare, e se capita non deve esplodere."""
    async with respx.mock:
        respx.post(URL).mock(
            return_value=httpx.Response(
                200, json={"choices": [{"message": {"content": "mi dispiace, ma"}}]}
            )
        )
        with pytest.raises(LlmUnavailable):
            await complete_json(
                system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
            )


async def test_un_json_che_non_e_un_oggetto_diventa_llm_unavailable(con_chiave):
    async with respx.mock:
        respx.post(URL).mock(
            return_value=httpx.Response(
                200, json={"choices": [{"message": {"content": "[1, 2, 3]"}}]}
            )
        )
        with pytest.raises(LlmUnavailable, match="oggetto JSON"):
            await complete_json(
                system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
            )


async def test_un_timeout_diventa_llm_unavailable(con_chiave):
    async with respx.mock:
        respx.post(URL).mock(side_effect=httpx.ReadTimeout("troppo lento"))
        with pytest.raises(LlmUnavailable):
            await complete_json(
                system="s", user="u", schema=SCHEMA, schema_name="prova", max_tokens=100
            )


def _sotto_oggetti(schema: dict):
    """Genera ogni sotto-schema di tipo "object", in profondità.

    Basta per le forme che le tre schede reali usano: oggetti con "properties" e
    array con "items". Non serve altro perché nessuna delle tre ricorre a "anyOf",
    "oneOf" o "$ref".
    """
    if not isinstance(schema, dict):
        return
    if schema.get("type") == "object":
        yield schema
        for sotto_schema in (schema.get("properties") or {}).values():
            yield from _sotto_oggetti(sotto_schema)
    elif schema.get("type") == "array":
        yield from _sotto_oggetti(schema.get("items") or {})


@pytest.mark.parametrize(
    "schema",
    [TERM_SCHEMA, COLLAPSE_SCHEMA, DRAFT_SCHEMA],
    ids=["TERM_SCHEMA", "COLLAPSE_SCHEMA", "DRAFT_SCHEMA"],
)
def test_gli_schemi_veri_rispettano_lo_strict_mode(schema):
    """Le tre schede che l'app manda davvero, non delle copie.

    Sta qui perché questo file è già dove il vincolo dello strict mode di
    OpenRouter — ogni proprietà in "required", "additionalProperties" a false a ogni
    livello — si dichiara e si prova, finora solo sulla scheda giocattolo del file
    (`SCHEMA`). Importare le costanti vere da `decide.py` e da `ai_recipes.py`, invece
    di riscriverle qui, è ciò che rende la prova vera: una copia si scollerebbe dalla
    scheda che la richiesta manda davvero, e la suite resterebbe verde mentre
    OpenRouter rifiuta con un 400 che qui diventa `LlmUnavailable` in silenzio.
    """
    for oggetto in _sotto_oggetti(schema):
        proprieta = set((oggetto.get("properties") or {}).keys())
        assert oggetto.get("additionalProperties") is False
        assert set(oggetto.get("required") or []) == proprieta
