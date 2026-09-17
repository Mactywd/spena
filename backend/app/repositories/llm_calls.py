"""Scrivere e rileggere lo storico delle chiamate all'LLM."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.llm_call import LlmCall
from app.services.llm import LlmCallSite, LlmUsage


async def record_llm_call(
    session: AsyncSession,
    *,
    call_site: LlmCallSite,
    usage: LlmUsage,
    ok: bool,
) -> None:
    """Aggiunge la riga alla sessione. Il commit resta di chi chiama.

    Non committa di proposito: il fan-out della decisione dei termini fa N chiamate in
    parallelo e scrive in una sola passata sequenziale, e una commit qui dentro
    spezzerebbe quella passata in N transazioni indipendenti — cioè renderebbe
    possibile uno storico di spesa che registra decisioni mai applicate.
    """
    session.add(
        LlmCall(
            call_site=call_site,
            ok=ok,
            model=usage.model,
            generation_id=usage.generation_id,
            prompt_tokens=usage.prompt_tokens,
            completion_tokens=usage.completion_tokens,
            cost_usd=usage.cost_usd,
        )
    )
