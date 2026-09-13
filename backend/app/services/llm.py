"""Una chiamata a un LLM, via OpenRouter, che torna JSON o solleva.

Un fornitore solo e un client solo. Non c'è un'interfaccia a due implementazioni
scelta da una variabile, come per gli embedding: il secondo percorso non girerebbe
mai in produzione, e sarebbe esattamente il difetto in cima a CLAUDE.md — un test che
costruisce il proprio oggetto non prova quello che gira. Quel che resta configurabile
è il modello, e poiché OpenRouter fa da proxy anche a Claude, passare a un modello
grosso è una riga di `.env`.

Questo file non sa niente di ricette, di ingredienti e di import: prende un prompt e
uno schema, torna un dizionario. È ciò che permette di provarlo per intero contro
`respx`, senza database.
"""

import json
from typing import Any

import httpx

from app.core.config import get_settings


class LlmUnavailable(Exception):
    """Modello non raggiungibile o risposta inutilizzabile.

    Non è un errore da propagare: chi chiama la traduce in «decidi a mano», che è
    sempre possibile. Vedi la regola «mai un vicolo cieco» in CLAUDE.md.
    """


def build_headers() -> dict[str, str]:
    settings = get_settings()
    if not settings.openrouter_api_key:
        raise LlmUnavailable("OPENROUTER_API_KEY non configurata")
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }
    # Identificano l'app nelle classifiche e nei consumi di OpenRouter: è come si
    # distingue questo traffico da qualunque altro sulla stessa chiave. Opzionali per
    # loro, obbligatori per noi — ma un header vuoto non è attribuzione, è rumore.
    if settings.openrouter_app_url:
        headers["HTTP-Referer"] = settings.openrouter_app_url
    if settings.openrouter_app_title:
        headers["X-Title"] = settings.openrouter_app_title
    return headers


def build_provider_preferences() -> dict[str, Any]:
    """Il provider più economico che sappia onorare lo schema.

    `require_parameters` porta il peso. Misurato il 2026-09-13 su
    `/models/google/gemma-4-26b-a4b-it/endpoints`: quattro degli undici endpoint non
    supportano `structured_outputs`, e uno di quelli (DekaLLM, 0,060 contro i 0,042 di
    Darkbloom) è il **secondo più economico**. Senza il flag, l'ordinamento per prezzo
    instrada verso un endpoint che non può rispettare `response_format`.

    `sort: "price"` spegne il bilanciamento di default, che pesa sull'inverso del
    quadrato del prezzo e quindi a volte sceglie un endpoint caro.

    `allow_fallbacks` non si manda: il suo default è `true`, cioè un errore o un rate
    limit sul primo scende al secondo più economico da sé. È esattamente ciò che si
    perde pinnando un provider a mano, ed è il motivo per cui `openrouter_provider_only`
    nasce vuota.
    """
    settings = get_settings()
    only = [name.strip() for name in settings.openrouter_provider_only.split(",") if name.strip()]
    if only:
        return {"only": only, "require_parameters": True}
    return {"sort": "price", "require_parameters": True}


async def complete_json(
    *,
    system: str,
    user: str,
    schema: dict[str, Any],
    schema_name: str,
    max_tokens: int,
    client: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """Una risposta JSON conforme a `schema`, o `LlmUnavailable`.

    Lo schema stretto è ciò che rende inutile qualunque scrostatore di blocchi di
    codice: la risposta è JSON o è un errore. Vincolo dello strict mode da rispettare
    negli schemi che si passano qui — ogni proprietà deve stare in `required` e
    `additionalProperties` deve essere `false` — quindi i campi che valgono per una
    sola azione si dichiarano nullable, non opzionali.

    `client` si passa quando il chiamante ne ha già uno aperto: il riconoscimento
    parallelo fa N chiamate insieme, e aprire N connessioni separate sarebbe uno
    spreco che il semaforo non compensa.
    """
    settings = get_settings()
    headers = build_headers()  # prima della rete: senza chiave non si spreca un giro
    body = {
        "model": settings.openrouter_model,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "response_format": {
            "type": "json_schema",
            "json_schema": {"name": schema_name, "strict": True, "schema": schema},
        },
        "provider": build_provider_preferences(),
    }
    url = f"{settings.openrouter_base_url.rstrip('/')}/chat/completions"

    owned = client is None
    api = client if client is not None else httpx.AsyncClient(timeout=settings.llm_timeout_seconds)
    try:
        response = await api.post(url, json=body, headers=headers)
        if response.status_code >= 400:
            raise LlmUnavailable(
                f"OpenRouter ha risposto {response.status_code}: {response.text[:200]}"
            )
        content = response.json()["choices"][0]["message"]["content"]
        parsed = json.loads(content)
        if not isinstance(parsed, dict):
            raise LlmUnavailable("la risposta non è un oggetto JSON")
        return parsed
    except LlmUnavailable:
        raise
    except Exception as exc:  # rete, timeout, corpo senza choices, JSON malformato
        raise LlmUnavailable(str(exc)) from exc
    finally:
        if owned:
            await api.aclose()


def open_client() -> httpx.AsyncClient:
    """Un client col timeout configurato, per chi fa più chiamate di seguito."""
    return httpx.AsyncClient(timeout=get_settings().llm_timeout_seconds)
