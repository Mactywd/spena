"""I client finti per le chiamate all'LLM. La suite non tocca la rete.

Stanno qui e non in un file di test perché cinque file li usano, e perché
`backend/tests/` non è un package: importarli da un altro file di test non
risolverebbe. Questo modulo sì — pytest inserisce `tests/` in `sys.path`, dato che le
sottocartelle sono package e questa no.

Entrambi i finti sostituiscono `httpx.AsyncClient`, non il client di OpenRouter: il
codice sotto prova è `complete_json` per intero, header e corpo compresi. Un finto più
in alto lascerebbe fuori proprio le righe che nessun altro test attraversa.
"""

import json as _json

import httpx

# Il consumo che OpenRouter allega a ogni risposta vera. Sta anche nei finti perché
# senza, la suite proverebbe la registrazione delle spese contro un corpo che non
# somiglia a quello che arriva in produzione — e un finto più povero del vero è il
# modo in cui un test smette di provare quel che crede.
COSTO_FINTO = 0.00004
USAGE_FINTO = {"prompt_tokens": 300, "completion_tokens": 20, "cost": COSTO_FINTO}


def _corpo(testo: str) -> dict:
    return {
        "id": "gen-finta",
        "model": "google/gemma-4-26b-a4b-it",
        "choices": [{"message": {"content": testo}}],
        "usage": dict(USAGE_FINTO),
    }


class FakeLlm:
    """Risponde una cosa per volta, nell'ordine dato. Registra i corpi mandati.

    Una `Exception` fra i payload viene sollevata invece di risposta: è così che si
    prova la degradazione senza rete.
    """

    def __init__(self, *payloads: object) -> None:
        self._payloads = list(payloads)
        self.bodies: list[dict] = []

    async def post(self, url, json: dict, headers):  # noqa: A002
        self.bodies.append(json)
        payload = self._payloads.pop(0) if self._payloads else {}
        if isinstance(payload, Exception):
            raise payload
        text = payload if isinstance(payload, str) else _json.dumps(payload)
        return httpx.Response(200, json=_corpo(text), request=httpx.Request("POST", url))

    async def aclose(self):
        return None


class ScriptedLlm:
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
        self.calls = 0
        self.bodies: list[dict] = []

    async def post(self, url, json: dict, headers):  # noqa: A002
        self.calls += 1
        self.bodies.append(json)
        question = _json.loads(json["messages"][1]["content"])
        if "nuovi" in question:
            payload = self._collapse if self._collapse is not None else {"groups": []}
        else:
            payload = self._per_term[question["termine"]]
        if isinstance(payload, Exception):
            raise payload
        return httpx.Response(
            200, json=_corpo(_json.dumps(payload)), request=httpx.Request("POST", url)
        )

    async def aclose(self):
        return None


def llm_map(name: str) -> dict:
    """Il corpo di una risposta `map`, con i campi nulli che lo strict mode esige."""
    return {"action": "map", "ingredient": name, "name": None,
            "display_name": None, "category": None}


def llm_create(name: str, display_name: str, category: str) -> dict:
    return {"action": "create", "ingredient": None, "name": name,
            "display_name": display_name, "category": category}


LLM_IGNORE = {"action": "ignore", "ingredient": None, "name": None,
              "display_name": None, "category": None}
