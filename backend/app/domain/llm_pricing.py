"""Il listino di Claude Haiku 5.5 e il costo di una risposta dai suoi token.

I numeri vengono dal listino di Claude Haiku 5.5 della skill `claude-api`, aggiornato al
2026-11-03: due listini secondo la lunghezza del prompt, letture della cache a 0,1×
l'ingresso, scritture a 5 minuti a 1,25×. Le scritture a un'ora (2×) spena non le usa.

La soglia dei 100.000 token si misura su tutto il prompt, cache compresa
(P = input + scritture + letture): è un'assunzione, scritta nella spec §4. `input_tokens`
è quello che l'API chiama così, cioè solo la parte non in cache; `output_tokens` comprende
il pensiero.

Un modello che il listino non conosce non ha costo (`None`): zero direbbe «gratis», e
l'assenza è la verità, come per i nutrienti.

Puro come `rules.py`: niente impostazioni, niente rete.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    """Dollari per milione di token, nei due listini."""

    input_per_mtok: float
    output_per_mtok: float
    long_input_per_mtok: float
    long_output_per_mtok: float
    long_prompt_above: int


PRICES: dict[str, ModelPrice] = {
    "claude-haiku-5-5": ModelPrice(0.10, 0.50, 0.50, 2.50, 100_000),
}

CACHE_READ_MULTIPLIER = 0.1
CACHE_WRITE_MULTIPLIER = 1.25


def cost_usd(
    model: str,
    *,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
) -> float | None:
    price = PRICES.get(model)
    if price is None:
        return None
    prompt = input_tokens + cache_write_tokens + cache_read_tokens
    if prompt > price.long_prompt_above:
        rate_in, rate_out = price.long_input_per_mtok, price.long_output_per_mtok
    else:
        rate_in, rate_out = price.input_per_mtok, price.output_per_mtok
    total = (
        input_tokens * rate_in
        + cache_write_tokens * rate_in * CACHE_WRITE_MULTIPLIER
        + cache_read_tokens * rate_in * CACHE_READ_MULTIPLIER
        + output_tokens * rate_out
    )
    return total / 1_000_000
