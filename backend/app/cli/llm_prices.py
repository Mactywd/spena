"""I prezzi per provider del modello configurato, e il costo di un lotto vero.

Eseguire con `python -m app.cli.llm_prices` dentro il container del backend.

Non sta nel percorso caldo del riconoscimento, di proposito: l'instradamento vero lo
fa OpenRouter con `sort: "price"` e `require_parameters: true`, che è deterministico,
sempre aggiornato, e non costa una chiamata di rete in più a ogni import. Questo
comando serve a decidere se quel default va ancora bene — la documentazione di
OpenRouter non dichiara come `sort: "price"` pesi input contro output, e oggi la
lacuna non morde solo perché Darkbloom è il più economico su entrambe le voci. Il
giorno in cui qualcuno apre a 0,03 sull'input e 0,50 sull'output, il compromesso
esiste, e `OPENROUTER_PROVIDER_ONLY` è la leva.

Diagnostico, non nel percorso caldo: ma «mai un vicolo cieco» vale anche qui, non
solo per l'app che l'utente usa (vedi CLAUDE.md). Senza chiave, o con OpenRouter
irraggiungibile, questo comando stampa cosa fare e esce pulito — mai una traceback
in faccia a chi lo lancia per controllare un numero.
"""

import asyncio
from dataclasses import dataclass

import httpx

from app.core.config import get_settings
from app.services.llm import LlmUnavailable, build_headers

PER_MILLION = 1_000_000

# Il lotto di riferimento: misurati 169 ingredienti in anagrafica, 7,2 KB di JSON
# compatto, e col prompt di sistema un prefisso di ~3.100 token. Stimati 35 token di
# risposta per termine.
PREFIX_TOKENS = 3100
SUFFIX_TOKENS = 8
OUTPUT_TOKENS = 35
TERMS = 15
MAX_TERMS_PER_BATCH = 40


@dataclass(frozen=True)
class Endpoint:
    provider: str
    prompt: float       # dollari per milione di token
    completion: float
    cache_read: float | None
    structured: bool


def parse_endpoints(payload: dict) -> list[Endpoint]:
    """I prezzi di OpenRouter arrivano per token: qui diventano per milione.

    Per token sono numeri come 0.000000042, che non si confrontano a occhio e in cui
    uno zero in più o in meno non si vede. L'unità della tabella è quella con cui
    OpenRouter stessa scrive i listini.

    Il `round(..., 9)` non è un arrotondamento di comodo: 0.000000042 * 1_000_000 vale
    0.041999999999999996 in un double IEEE 754, un ultimo bit che sopravvive al
    confronto e fa fallire un test scritto sul numero atteso (misurato qui, non solo
    in astratto). Nove decimali sul dollaro-per-milione tengono ogni cifra che il
    listino di OpenRouter dichiara davvero e tolgono solo il rumore del bit.
    """
    endpoints = []
    for entry in payload.get("data", {}).get("endpoints", []):
        pricing = entry.get("pricing") or {}
        cache_read = pricing.get("input_cache_read")
        supported = entry.get("supported_parameters") or []
        endpoints.append(
            Endpoint(
                provider=str(entry.get("provider_name", "?")),
                prompt=round(float(pricing.get("prompt", 0)) * PER_MILLION, 9),
                completion=round(float(pricing.get("completion", 0)) * PER_MILLION, 9),
                cache_read=(
                    round(float(cache_read) * PER_MILLION, 9) if cache_read else None
                ),
                structured="structured_outputs" in supported,
            )
        )
    return endpoints


def usable(endpoints: list[Endpoint]) -> list[Endpoint]:
    """Solo chi regge lo schema, dal più economico.

    È ciò che `require_parameters: true` fa lato OpenRouter, riprodotto qui: senza il
    filtro la classifica per prezzo include endpoint che non possono rispettare
    `response_format`, e il secondo posto è uno di quelli.
    """
    return sorted(
        (e for e in endpoints if e.structured), key=lambda e: (e.prompt, e.completion)
    )


def batch_cost(
    endpoint: Endpoint,
    *,
    calls: int,
    prefix_tokens: int,
    suffix_tokens: int,
    output_tokens: int,
) -> float:
    """Il costo in dollari di `calls` chiamate con quel prefisso e quella risposta.

    La prima chiamata paga il prefisso a prezzo pieno; le successive lo pagano a
    prezzo di cache read, se quel provider ne ha uno. Il suffisso — il termine da
    giudicare — è sempre a prezzo pieno.

    Su questo modello la cache non conviene mai, e il calcolo lo mostra invece di
    affermarlo: il cache read più economico fra i provider con structured output è
    0,050, più caro dei 0,042 che Darkbloom chiede per un token a prezzo pieno.
    """
    prefix_full = prefix_tokens * endpoint.prompt / PER_MILLION
    prefix_cached = (
        prefix_tokens * endpoint.cache_read / PER_MILLION
        if endpoint.cache_read is not None
        else prefix_full
    )
    suffix = suffix_tokens * endpoint.prompt / PER_MILLION
    output = output_tokens * endpoint.completion / PER_MILLION
    first = prefix_full + suffix + output
    rest = (calls - 1) * (prefix_cached + suffix + output)
    return first + rest


async def fetch_endpoints(client: httpx.AsyncClient) -> dict:
    settings = get_settings()
    url = f"{settings.openrouter_base_url.rstrip('/')}/models/{settings.openrouter_model}/endpoints"
    # Stessi header di attribuzione della chiamata vera (build_headers in
    # app/services/llm.py): questo è l'endpoint pubblico dei listini, non serve una
    # chiave per leggerlo, ma mandare comunque Authorization/X-Title fa comparire
    # anche queste letture nei consumi di OpenRouter invece che come traffico anonimo.
    # `build_headers` solleva `LlmUnavailable` se la chiave manca — è la stessa
    # degradazione dichiarata della chiamata vera, riprodotta qui prima della rete.
    response = await client.get(url, headers=build_headers())
    response.raise_for_status()
    return response.json()


def render(endpoints: list[Endpoint]) -> str:
    righe = [f"{'PROVIDER':<14}{'INPUT':>8}{'OUTPUT':>9}{'CACHE R':>9}  SCHEMA"]
    for e in sorted(endpoints, key=lambda e: (e.prompt, e.completion)):
        cache = f"{e.cache_read:.3f}" if e.cache_read is not None else "—"
        schema = "sì" if e.structured else "NO"
        righe.append(f"{e.provider:<14}{e.prompt:>8.3f}{e.completion:>9.3f}{cache:>9}  {schema}")
    return "\n".join(righe)


async def main() -> None:
    """Stampa la tabella dei prezzi e il confronto lotto/fan-out, o come procedere.

    «Mai un vicolo cieco» (CLAUDE.md) vale anche per un comando diagnostico: senza
    chiave, o con OpenRouter irraggiungibile, chi lo lancia deve leggere cosa fare,
    non una traceback. Le due degradazioni sono distinte apposta — la prima si
    risolve in `.env`, la seconda riprovando fra un minuto.
    """
    settings = get_settings()
    try:
        async with httpx.AsyncClient(timeout=settings.llm_timeout_seconds) as client:
            payload = await fetch_endpoints(client)
    except LlmUnavailable as exc:
        print(f"Impossibile interrogare OpenRouter: {exc}")
        return
    except httpx.HTTPStatusError as exc:
        print(
            f"OpenRouter ha risposto {exc.response.status_code}: "
            f"{exc.response.text[:200]}"
        )
        return
    except httpx.HTTPError as exc:
        print(f"OpenRouter non raggiungibile ({exc}). Riprova fra un minuto.")
        return

    endpoints = parse_endpoints(payload)
    print(f"{settings.openrouter_model} — dollari per milione di token\n")
    print(render(endpoints))

    candidati = usable(endpoints)
    if not candidati:
        print(
            "\nNessun provider di questo modello supporta structured_outputs: con "
            "`require_parameters: true` ogni chiamata fallirebbe. Cambia OPENROUTER_MODEL."
        )
        return

    scelto = candidati[0]
    esclusi = [e.provider for e in endpoints if not e.structured]
    print(f"\nPiù economico fra quelli che reggono lo schema: {scelto.provider}")
    if esclusi:
        print(f"Esclusi perché senza structured_outputs: {', '.join(esclusi)}")

    lotti = -(-TERMS // MAX_TERMS_PER_BATCH)  # divisione per eccesso
    lotto_unico = batch_cost(
        scelto, calls=lotti, prefix_tokens=PREFIX_TOKENS,
        suffix_tokens=TERMS * SUFFIX_TOKENS, output_tokens=TERMS * OUTPUT_TOKENS,
    )
    fan_out = batch_cost(
        scelto, calls=TERMS, prefix_tokens=PREFIX_TOKENS,
        suffix_tokens=SUFFIX_TOKENS, output_tokens=OUTPUT_TOKENS,
    )
    print(f"\nSu {TERMS} termini, prefisso di {PREFIX_TOKENS} token:")
    print(f"  lotto unico            ${lotto_unico:.6f}")
    print(f"  una chiamata a termine ${fan_out:.6f}  ({fan_out / lotto_unico:.1f}×)")
    print(
        "\nIl fan-out si usa comunque: un modello con 3,8 miliardi di parametri attivi\n"
        "sbaglia un JSON di 40 elementi e non sbaglia una domanda sola (spec §4.2)."
    )


if __name__ == "__main__":
    asyncio.run(main())
