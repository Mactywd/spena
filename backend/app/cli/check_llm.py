"""Controlla che l'LLM sia pronto, nell'immagine in cui gira.

    python -m app.cli.check_llm
    python -m app.cli.check_llm --prova

Senza argomenti non usa la rete: stampa la versione dell'SDK `anthropic`, il modello, se
il listino di `llm_pricing` lo conosce (se no il costo resterà vuoto) e se la chiave API
c'è, mai il suo valore. Esce con 1 se la chiave manca. Con `--prova` fa una sola chiamata
minima, per Mattia dopo il deploy: costa una frazione di centesimo.

La prova è un controllo, non una sezione: non si registra in `llm_calls`, e quindi non
compare in «Spese dell'AI». Prende il posto del comando che, prima del 2026-11-21,
mostrava i provider e i prezzi dell'instradamento di allora.
"""

import argparse
import asyncio
import sys

import anthropic
from anthropic import AsyncAnthropic

from app.core.config import get_settings
from app.domain.llm_pricing import PRICES
from app.services.llm import CLASSIFY, LlmCallSite, LlmUnavailable, complete_json

_SCHEMA = {
    "type": "object",
    "properties": {"esito": {"type": "string"}},
    "required": ["esito"],
    "additionalProperties": False,
}


async def _prova(client: AsyncAnthropic | None) -> int:
    """Una chiamata minima: «prova: ok (…)» o «prova: fallita — …»."""
    try:
        result = await complete_json(
            call_site=LlmCallSite.TERM_DECISION,
            system="Rispondi con esito ok.",
            user="ok?",
            schema=_SCHEMA,
            max_tokens=50,
            profile=CLASSIFY,
            client=client,
        )
    except LlmUnavailable as exc:
        print(f"prova: fallita — {exc}")
        return 1
    usage = result.usage
    costo = f"{usage.cost_usd:.6f} $" if usage.cost_usd is not None else "costo sconosciuto"
    print(
        f"prova: ok ({usage.prompt_tokens} token in ingresso, "
        f"{usage.completion_tokens} in uscita, {costo})"
    )
    return 0


def main(argv: list[str] | None = None, *, client: AsyncAnthropic | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli.check_llm")
    parser.add_argument("--prova", action="store_true", help="una chiamata vera al modello")
    args = parser.parse_args(argv)

    settings = get_settings()
    print(f"anthropic {anthropic.__version__}")
    print(f"modello: {settings.llm_model}")
    if settings.llm_model in PRICES:
        print("listino: noto")
    else:
        print("listino: sconosciuto (il costo resterà vuoto)")
    chiave = bool(settings.anthropic_api_key)
    print("chiave API: presente" if chiave else "chiave API: assente")

    if args.prova:
        return asyncio.run(_prova(client))
    return 0 if chiave else 1


if __name__ == "__main__":
    raise SystemExit(main())
