"""Il client di Anthropic: la richiesta che costruisce, la risposta che legge, i guasti.

Il trasporto HTTP è un `httpx2.MockTransport`, e nient'altro è finto: il client è un
`AsyncAnthropic` con le opzioni di produzione (`client_options`), quindi l'SDK vero
costruisce la richiesta, legge la risposta e solleva le sue eccezioni. I test sulla
**forma della richiesta** sono quelli che contano di più: sono l'unico posto in cui si
dimostra che modello, schema, profilo e chiave arrivano davvero all'API.

I tentativi sono dell'SDK: dove un test parla di tentativi usa le opzioni vere, senza
toccare `max_retries`; altrove un finto (`max_retries=0`), così la suite non aspetta.
"""

import json

import httpx2
import pytest
from anthropic import AsyncAnthropic, DefaultAsyncHttpxClient

from app.core.config import get_settings
from app.services.ai_recipes import DRAFT_SCHEMA
from app.services.llm import (
    CLASSIFY,
    LLM_FAILURE_NOTICES,
    TERMINAL_LLM_FAILURES,
    CallProfile,
    LlmCallSite,
    LlmFailureKind,
    LlmUnavailable,
    LlmUsage,
    client_options,
    complete_json,
    open_client,
)
from app.services.ciqual_match import CHOICE_SCHEMA, TERMS_SCHEMA
from app.services.ingredient_emoji import EMOJI_SCHEMA
from app.services.recipe_import.decide import COLLAPSE_SCHEMA, TERM_SCHEMA
from app.services.substitutions import SUBSTITUTE_SCHEMA
from app.services.unit_forms import FORMS_SCHEMA
from app.services.unit_grams import GRAMS_SCHEMA
from llm_fakes import FakeLlm, errore_api, messaggio

CHIAVE = "chiave-finta-per-i-test"

SCHEMA = {
    "type": "object",
    "properties": {"esito": {"type": "string"}},
    "required": ["esito"],
    "additionalProperties": False,
}


@pytest.fixture
def con_chiave(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", CHIAVE)
    yield
    get_settings.cache_clear()


class Registro:
    """Un trasporto che registra le richieste e risponde con quel che gli si dà."""

    def __init__(self, *risposte: object) -> None:
        self._risposte = list(risposte)
        self.richieste: list[httpx2.Request] = []

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.richieste.append(request)
        risposta = self._risposte.pop(0) if self._risposte else messaggio('{"esito": "ok"}')
        if isinstance(risposta, Exception):
            raise risposta
        if isinstance(risposta, httpx2.Response):
            return risposta
        return httpx2.Response(200, json=risposta)


def client_vero(registro: Registro) -> AsyncAnthropic:
    """Il client con le opzioni di produzione, tentativi compresi: cambia il trasporto."""
    return AsyncAnthropic(
        **client_options(
            http_client=DefaultAsyncHttpxClient(transport=httpx2.MockTransport(registro))
        )
    )


async def chiedi(client, **altro):
    return await complete_json(
        call_site=LlmCallSite.TERM_DECISION,
        system="s",
        user="u",
        schema=SCHEMA,
        max_tokens=100,
        client=client,
        **altro,
    )


async def test_la_richiesta_e_quella_dell_api_messages(con_chiave):
    registro = Registro()
    await chiedi(client_vero(registro))

    (richiesta,) = registro.richieste
    assert str(richiesta.url) == "https://api.anthropic.com/v1/messages"
    corpo = json.loads(richiesta.content)
    assert corpo["model"] == "claude-haiku-5-5"
    assert corpo["max_tokens"] == 100
    assert corpo["system"] == [{"type": "text", "text": "s"}]
    assert corpo["messages"] == [{"role": "user", "content": "u"}]
    assert corpo["thinking"] == {"type": "disabled"}
    assert corpo["output_config"] == {
        "effort": "low",
        "format": {"type": "json_schema", "schema": SCHEMA},
    }
    for assente in ("temperature", "top_p", "top_k", "response_format", "provider"):
        assert assente not in corpo
    # le due forme documentate della chiave: l'SDK 1.x usa `x-api-key`, il 2.x
    # `Authorization: Bearer`; nessun'altra
    assert (
        richiesta.headers.get("x-api-key") == CHIAVE
        or richiesta.headers.get("authorization") == f"Bearer {CHIAVE}"
    )


async def test_con_la_cache_il_sistema_porta_il_segno(con_chiave):
    registro = Registro()
    await chiedi(client_vero(registro), cache_system=True)
    corpo = json.loads(registro.richieste[0].content)
    assert corpo["system"][0]["cache_control"] == {"type": "ephemeral"}


async def test_un_profilo_che_pensa(con_chiave):
    registro = Registro()
    await chiedi(client_vero(registro), profile=CallProfile(thinking=True, effort="low"))
    corpo = json.loads(registro.richieste[0].content)
    assert corpo["thinking"] == {"type": "adaptive"}


async def test_il_profilo_porta_il_suo_tempo(con_chiave):
    profilo = CallProfile(thinking=True, effort="low", timeout_seconds=50.0, max_retries=0)

    registro = Registro()
    await chiedi(client_vero(registro), profile=profilo)
    assert registro.richieste[0].extensions["timeout"]["read"] == 50.0

    # max_retries=0 del profilo: un 529 non si ritenta
    registro = Registro(errore_api(529, "overloaded_error"))
    with pytest.raises(LlmUnavailable) as preso:
        await chiedi(client_vero(registro), profile=profilo)
    assert preso.value.kind == LlmFailureKind.TRANSIENT
    assert len(registro.richieste) == 1

    registro = Registro()
    await chiedi(client_vero(registro), profile=CLASSIFY)
    assert registro.richieste[0].extensions["timeout"]["read"] == 45.0


async def test_la_risposta_porta_uso_e_costo(con_chiave):
    uso = {
        "input_tokens": 200,
        "cache_read_input_tokens": 8000,
        "cache_creation_input_tokens": 0,
        "output_tokens": 30,
    }
    esito = await chiedi(FakeLlm(messaggio('{"esito": "ok"}', usage=uso)))

    assert esito.data == {"esito": "ok"}
    assert esito.call_site == LlmCallSite.TERM_DECISION
    assert esito.usage == LlmUsage(
        generation_id="gen-finta",
        model="claude-haiku-5-5",
        prompt_tokens=8200,
        completion_tokens=30,
        cost_usd=pytest.approx(0.000115),
        cache_read_tokens=8000,
        cache_write_tokens=0,
    )


async def test_si_legge_il_blocco_di_testo_non_il_primo(con_chiave):
    contenuto = [
        {"type": "thinking", "thinking": "", "signature": "firma-finta"},
        {"type": "text", "text": '{"esito": "ok"}'},
    ]
    esito = await chiedi(FakeLlm(messaggio("", content=contenuto)))
    assert esito.data == {"esito": "ok"}


async def test_l_ambiente_non_sceglie_indirizzo_ne_credenziale(con_chiave, monkeypatch):
    """Le shell degli agenti hanno ANTHROPIC_BASE_URL: l'indirizzo e la chiave sono
    espliciti, e l'ambiente non li sceglie."""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "token-dell-ambiente")
    registro = Registro()
    await chiedi(client_vero(registro))

    (richiesta,) = registro.richieste
    assert richiesta.url.host == "api.anthropic.com"
    assert not [v for v in richiesta.headers.values() if "token-dell-ambiente" in v]


async def test_senza_chiave_nessuna_richiesta(con_chiave, monkeypatch):
    """La degradazione dichiarata, e prima della rete: non si spreca un giro.

    Il finto si costruisce con la chiave, che poi si toglie: l'assenza è nelle
    impostazioni, ed è lì che `complete_json` guarda prima di aprire qualunque cosa.
    """
    finto = FakeLlm({"esito": "ok"})
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    with pytest.raises(LlmUnavailable) as preso:
        await chiedi(finto)
    assert preso.value.kind == LlmFailureKind.NOT_CONFIGURED
    assert str(preso.value) == "ANTHROPIC_API_KEY non configurata"
    assert finto.calls == 0


@pytest.mark.parametrize(
    ("status", "tipo", "messaggio_api", "atteso"),
    [
        (401, "authentication_error", "errore finto", LlmFailureKind.AUTH),
        (403, "permission_error", "errore finto", LlmFailureKind.AUTH),
        (402, "billing_error", "errore finto", LlmFailureKind.CREDIT),
        (
            400,
            "invalid_request_error",
            "Your credit balance is too low to access the Anthropic API.",
            LlmFailureKind.CREDIT,
        ),
        (429, "rate_limit_error", "errore finto", LlmFailureKind.RATE_LIMIT),
        (
            400,
            "invalid_request_error",
            "output_config.format.schema: invalid",
            LlmFailureKind.REJECTED,
        ),
        (404, "not_found_error", "errore finto", LlmFailureKind.REJECTED),
        (500, "api_error", "errore finto", LlmFailureKind.TRANSIENT),
        (529, "overloaded_error", "errore finto", LlmFailureKind.TRANSIENT),
    ],
)
async def test_i_guasti_http(con_chiave, status, tipo, messaggio_api, atteso):
    with pytest.raises(LlmUnavailable) as preso:
        await chiedi(FakeLlm(errore_api(status, tipo, messaggio_api)))

    exc = preso.value
    assert exc.kind == atteso
    assert exc.usage == LlmUsage()
    assert exc.terminal is (atteso in {
        LlmFailureKind.AUTH,
        LlmFailureKind.CREDIT,
        LlmFailureKind.RATE_LIMIT,
        LlmFailureKind.REJECTED,
    })
    assert exc.notice == LLM_FAILURE_NOTICES[atteso]
    assert str(exc).startswith(LLM_FAILURE_NOTICES[atteso])
    assert f"HTTP {status}" in str(exc)


@pytest.mark.parametrize(
    "guasto",
    [httpx2.ConnectError("rete giù"), httpx2.ReadTimeout("troppo lento")],
    ids=["ConnectError", "ReadTimeout"],
)
async def test_rete_e_tempo_sono_passeggeri(con_chiave, guasto):
    with pytest.raises(LlmUnavailable) as preso:
        await chiedi(FakeLlm(guasto))
    assert preso.value.kind == LlmFailureKind.TRANSIENT
    assert not preso.value.terminal


async def test_il_messaggio_di_rete_si_tronca(con_chiave):
    """Il dettaglio va nei log e nei comandi: un messaggio di rete lungo non li invade."""
    with pytest.raises(LlmUnavailable) as preso:
        await chiedi(FakeLlm(httpx2.ConnectError("x" * 500)))
    assert "ConnectError: " + "x" * 200 + ")" in str(preso.value)
    assert "x" * 201 not in str(preso.value)


async def test_una_risposta_tagliata_porta_l_uso(con_chiave):
    uso = {"input_tokens": 300, "output_tokens": 300,
           "cache_creation_input_tokens": 0, "cache_read_input_tokens": 0}
    with pytest.raises(LlmUnavailable) as preso:
        await chiedi(FakeLlm(messaggio('{"esito": "o', stop_reason="max_tokens", usage=uso)))
    exc = preso.value
    assert exc.kind == LlmFailureKind.TRUNCATED
    assert exc.usage.completion_tokens == 300
    assert exc.usage.cost_usd is not None
    assert "stop_reason max_tokens" in str(exc)


async def test_un_rifiuto_porta_l_uso(con_chiave):
    with pytest.raises(LlmUnavailable) as preso:
        await chiedi(FakeLlm(messaggio("", stop_reason="refusal")))
    exc = preso.value
    assert exc.kind == LlmFailureKind.REFUSAL
    assert exc.usage.completion_tokens == 20
    assert exc.usage.cost_usd is not None


@pytest.mark.parametrize(
    "risposta",
    [
        messaggio("mi dispiace, ma"),
        messaggio("[1]"),
        messaggio("", content=[]),
    ],
    ids=["non-json", "non-un-oggetto", "nessun-blocco-di-testo"],
)
async def test_le_risposte_inutilizzabili(con_chiave, risposta):
    with pytest.raises(LlmUnavailable) as preso:
        await chiedi(FakeLlm(risposta))
    exc = preso.value
    assert exc.kind == LlmFailureKind.INVALID
    assert exc.usage.completion_tokens == 20
    assert exc.usage.cost_usd is not None


@pytest.mark.parametrize(
    "risposta",
    [
        httpx2.Response(200, text="<html>", headers={"content-type": "text/html"}),
        httpx2.Response(200, json={"foo": 1}),
    ],
    ids=["html", "json-estraneo"],
)
async def test_una_risposta_di_forma_inattesa_e_inutilizzabile(con_chiave, risposta):
    """Un 200 che non è un messaggio (una pagina di un proxy, un corpo estraneo) non
    scappa come `AttributeError`: i chiamanti prendono solo `LlmUnavailable`, e senza
    quello la spesa non si registra e la rotta risponde 500 invece della frase."""
    with pytest.raises(LlmUnavailable) as preso:
        await chiedi(FakeLlm(risposta))
    exc = preso.value
    assert exc.kind == LlmFailureKind.INVALID
    assert exc.usage == LlmUsage()
    assert "risposta non riconosciuta" in str(exc)


async def test_i_tentativi_sono_dell_sdk(con_chiave):
    """Le opzioni vere: due 529 e poi la risposta. Aspetta le pause dell'SDK."""
    registro = Registro(
        errore_api(529, "overloaded_error"),
        errore_api(529, "overloaded_error"),
        messaggio('{"esito": "ok"}'),
    )
    esito = await chiedi(client_vero(registro))
    assert esito.data == {"esito": "ok"}
    assert len(registro.richieste) == 3


async def test_open_client_senza_chiave(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    try:
        with pytest.raises(LlmUnavailable) as preso:
            open_client()
    finally:
        get_settings.cache_clear()
    assert preso.value.kind == LlmFailureKind.NOT_CONFIGURED


async def test_open_client_con_la_chiave(con_chiave):
    client = open_client()
    try:
        assert isinstance(client, AsyncAnthropic)
        assert str(client.base_url).startswith("https://api.anthropic.com")
    finally:
        await client.close()


def test_i_tipi_terminali():
    assert TERMINAL_LLM_FAILURES == {
        LlmFailureKind.NOT_CONFIGURED,
        LlmFailureKind.AUTH,
        LlmFailureKind.CREDIT,
        LlmFailureKind.RATE_LIMIT,
        LlmFailureKind.REJECTED,
    }
    assert set(LLM_FAILURE_NOTICES) == set(LlmFailureKind)


def _sotto_oggetti(schema: dict):
    """Genera ogni sotto-schema di tipo "object", in profondità.

    Scende nelle proprietà, negli "items" e negli "anyOf" (dove stanno i campi
    nullable). Nessuno schema reale ricorre a "oneOf" o "$ref".
    """
    if not isinstance(schema, dict):
        return
    if schema.get("type") == "object":
        yield schema
        for sotto_schema in (schema.get("properties") or {}).values():
            yield from _sotto_oggetti(sotto_schema)
    elif schema.get("type") == "array":
        yield from _sotto_oggetti(schema.get("items") or {})
    for ramo in schema.get("anyOf") or []:
        yield from _sotto_oggetti(ramo)


def _tutti_i_sotto_schemi(schema):
    """Ogni dizionario dentro `schema`, a qualunque profondità."""
    if isinstance(schema, dict):
        yield schema
        for valore in schema.values():
            yield from _tutti_i_sotto_schemi(valore)
    elif isinstance(schema, list):
        for elemento in schema:
            yield from _tutti_i_sotto_schemi(elemento)


CHIAVI_NON_ACCETTATE = {
    "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum", "multipleOf",
    "minLength", "maxLength", "minItems", "maxItems", "pattern",
}


@pytest.mark.parametrize(
    "schema",
    [
        TERM_SCHEMA, COLLAPSE_SCHEMA, DRAFT_SCHEMA, SUBSTITUTE_SCHEMA, FORMS_SCHEMA,
        EMOJI_SCHEMA, TERMS_SCHEMA, CHOICE_SCHEMA, GRAMS_SCHEMA,
    ],
    ids=[
        "TERM_SCHEMA", "COLLAPSE_SCHEMA", "DRAFT_SCHEMA", "SUBSTITUTE_SCHEMA",
        "FORMS_SCHEMA", "EMOJI_SCHEMA", "TERMS_SCHEMA", "CHOICE_SCHEMA", "GRAMS_SCHEMA",
    ],
)
def test_gli_schemi_veri_sono_accettati_dalle_structured_outputs(schema):
    """Gli schemi che l'app manda davvero, non delle copie (spec §2.12).

    Le structured outputs di Anthropic vogliono, a ogni livello: ogni proprietà in
    "required" e "additionalProperties" a false; nessun "type" che sia una lista (un
    campo nullable è un "anyOf" con "null"); nessun vincolo numerico o di lunghezza.
    Le costanti si importano, non si copiano: una copia si scollerebbe dallo schema che
    la richiesta manda davvero, e la suite resterebbe verde mentre l'API rifiuta con un
    400 che qui diventa `LlmUnavailable` in silenzio.
    """
    for oggetto in _sotto_oggetti(schema):
        proprieta = set((oggetto.get("properties") or {}).keys())
        assert oggetto.get("additionalProperties") is False
        assert set(oggetto.get("required") or []) == proprieta
    for sotto in _tutti_i_sotto_schemi(schema):
        assert not isinstance(sotto.get("type"), list), sotto
        assert not (CHIAVI_NON_ACCETTATE & set(sotto)), sotto
