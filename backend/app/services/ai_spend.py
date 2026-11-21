"""Una chiamata all'AI che si registra sempre, e il conto di un giro (S4).

`complete_recorded` è `complete_json` più la riga in `llm_calls` — anche per la chiamata
fallita, come fanno `unit_forms.py` e `decide_emoji` — e più la somma della spesa in uno
`Spend`, se chi chiama ne passa uno: il pilota la stampa (spec §4.19). Un posto solo, perché
i comandi di S4 e il pilota non ne tengano tre copie.
"""

from dataclasses import dataclass
from typing import Any

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.llm_calls import record_llm_call
from app.services.llm import LlmCallSite, LlmUnavailable, LlmUsage, complete_json


@dataclass
class Spend:
    calls: int = 0
    cost_usd: float = 0.0
    # chiamate senza un costo dichiarato: le fallite, e quelle senza `usage.cost`
    unpriced: int = 0

    def add(self, usage: LlmUsage) -> None:
        self.calls += 1
        if usage.cost_usd is None:
            self.unpriced += 1
        else:
            self.cost_usd += usage.cost_usd


async def complete_recorded(
    session: AsyncSession,
    *,
    call_site: LlmCallSite,
    system: str,
    user: str,
    schema: dict[str, Any],
    max_tokens: int,
    client: AsyncAnthropic | None = None,
    spend: Spend | None = None,
) -> dict[str, Any]:
    """La risposta, o `LlmUnavailable` — in tutti e due i casi dopo averla registrata.
    Il commit resta di chi chiama, come in `record_llm_call`."""
    try:
        esito = await complete_json(
            call_site=call_site,
            system=system,
            user=user,
            schema=schema,
            max_tokens=max_tokens,
            client=client,
        )
    except LlmUnavailable:
        await record_llm_call(session, call_site=call_site, usage=LlmUsage(), ok=False)
        if spend is not None:
            spend.add(LlmUsage())
        raise
    await record_llm_call(session, call_site=call_site, usage=esito.usage, ok=True)
    if spend is not None:
        spend.add(esito.usage)
    return esito.data
