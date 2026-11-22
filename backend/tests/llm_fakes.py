"""I client finti per le chiamate all'LLM. La suite non tocca la rete.

Stanno qui e non in un file di test perché molti file li usano, e perché
`backend/tests/` non è un package: importarli da un altro file di test non
risolverebbe. Questo modulo sì — pytest inserisce `tests/` in `sys.path`, dato che le
sottocartelle sono package e questa no.

I finti **sono il client vero**: un `AsyncAnthropic` costruito con le opzioni di
produzione (`client_options`, lo stesso posto da cui le prende `open_client`), a cui si
sostituisce solo il trasporto HTTP. Sotto prova l'SDK costruisce davvero la richiesta,
la manda, legge la risposta e solleva le sue eccezioni: un finto più in alto lascerebbe
fuori proprio le righe che nessun altro test attraversa (la prima lezione di CLAUDE.md).

L'unica opzione cambiata è `max_retries=0`: i tentativi sono dell'SDK, e si provano una
volta sola, con le opzioni vere, in `tests/services/test_llm.py`. Qui farebbero solo
aspettare le sue pause.

`with_options` e `copy` tornano il finto stesso: l'SDK li implementa ricostruendo il
client con il costruttore della classe, che qui non prende argomenti, e i corpi e le
chiamate registrati finirebbero sulla copia. Le opzioni del profilo (tempo e tentativi)
si provano col client vero in `test_llm.py`.

`client_options` legge la chiave: chi costruisce un finto ha già `ANTHROPIC_API_KEY`
nell'ambiente.
"""

import json as _json

import httpx2
from anthropic import AsyncAnthropic, DefaultAsyncHttpxClient

from app.services.llm import client_options

# Il consumo che Anthropic dichiara su ogni risposta vera, e il costo che ne fa il
# listino. Sta anche nei finti perché senza, la suite proverebbe la registrazione delle
# spese contro un corpo che non somiglia a quello che arriva in produzione — e un finto
# più povero del vero è il modo in cui un test smette di provare quel che crede.
COSTO_FINTO = 0.00004  # 300 token in ingresso e 20 in uscita, al listino di Haiku 5.5
USAGE_FINTO = {
    "input_tokens": 300,
    "output_tokens": 20,
    "cache_creation_input_tokens": 0,
    "cache_read_input_tokens": 0,
}


def messaggio(testo, *, stop_reason="end_turn", usage=None, content=None) -> dict:
    """Il corpo di una risposta dell'API Messages."""
    return {
        "id": "gen-finta",
        "type": "message",
        "role": "assistant",
        "model": "claude-haiku-5-5",
        "content": content if content is not None else [{"type": "text", "text": testo}],
        "stop_reason": stop_reason,
        "stop_sequence": None,
        "usage": dict(usage if usage is not None else USAGE_FINTO),
    }


def errore_api(status: int, error_type: str, message: str = "errore finto") -> httpx2.Response:
    """Una risposta d'errore nella forma dell'API."""
    return httpx2.Response(
        status, json={"type": "error", "error": {"type": error_type, "message": message}}
    )


def system_of(body: dict) -> str:
    return body["system"][0]["text"]


def user_of(body: dict) -> str:
    return body["messages"][0]["content"]


def schema_of(body: dict) -> dict:
    return body["output_config"]["format"]["schema"]


class _Finto(AsyncAnthropic):
    """Il client vero, con le opzioni di produzione; cambia solo il trasporto."""

    def __init__(self) -> None:
        self.bodies: list[dict] = []
        self.calls = 0
        # le opzioni con cui `complete_json` ha chiesto la copia del client (tempo, tentativi)
        self.options: list[dict] = []
        trasporto = httpx2.MockTransport(self._handle)
        super().__init__(
            **{
                **client_options(http_client=DefaultAsyncHttpxClient(transport=trasporto)),
                "max_retries": 0,
            }
        )

    def copy(self, **options) -> "_Finto":  # type: ignore[override]
        self.options.append(options)
        return self

    with_options = copy  # type: ignore[assignment]

    async def _handle(self, request: httpx2.Request) -> httpx2.Response:
        body = _json.loads(request.content)
        self.calls += 1
        self.bodies.append(body)
        payload = await self.answer(body)
        if isinstance(payload, Exception):
            raise payload
        if isinstance(payload, httpx2.Response):
            return payload
        if isinstance(payload, dict) and payload.get("type") == "message":
            return httpx2.Response(200, json=payload)
        testo = payload if isinstance(payload, str) else _json.dumps(payload)
        return httpx2.Response(200, json=messaggio(testo))

    async def answer(self, body: dict) -> object:
        raise NotImplementedError


class FakeLlm(_Finto):
    """Risponde una cosa per volta, nell'ordine dato. Registra i corpi mandati.

    Un payload è un dizionario o una stringa (il testo della risposta), un corpo di
    `messaggio(...)`, una `httpx2.Response` (per esempio `errore_api(...)`), o una
    `Exception`, sollevata dal trasporto: è così che si prova la degradazione senza
    rete. Finiti i payload, risponde `{}`.
    """

    def __init__(self, *payloads: object) -> None:
        self._payloads = list(payloads)
        super().__init__()

    async def answer(self, body: dict) -> object:
        return self._payloads.pop(0) if self._payloads else {}


class ScriptedLlm(_Finto):
    """Una risposta per ogni domanda, scelta guardando **cosa** la domanda chiede.

    Non una coda ordinata: il fan-out è parallelo e l'ordine di arrivo non è garantito.
    Una coda renderebbe il test sensibile a uno scheduling che non controlliamo, ed è il
    modo classico di scrivere un test che fallisce a caso.

    La domanda del collasso si riconosce dalla chiave `nuovi`; tutte le altre portano
    `termine`.
    """

    def __init__(self, per_term: dict[str, object], collapse: object | None = None) -> None:
        self._per_term = per_term
        self._collapse = collapse
        super().__init__()

    async def answer(self, body: dict) -> object:
        question = _json.loads(user_of(body))
        if "nuovi" in question:
            return self._collapse if self._collapse is not None else {"groups": []}
        return self._per_term[question["termine"]]


def llm_map(name: str) -> dict:
    """Il corpo di una risposta `map`, con i campi nulli che lo strict mode esige."""
    return {"action": "map", "ingredient": name, "name": None,
            "display_name": None, "category": None}


def llm_create(name: str, display_name: str, category: str) -> dict:
    return {"action": "create", "ingredient": None, "name": name,
            "display_name": display_name, "category": category}


LLM_IGNORE = {"action": "ignore", "ingredient": None, "name": None,
              "display_name": None, "category": None}
