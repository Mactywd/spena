"""Scrivere e rileggere lo storico delle chiamate all'LLM."""

from dataclasses import dataclass
from datetime import date, datetime

from sqlalchemy import Date, cast, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.llm_call import LlmCall
from app.domain.rules import PANTRY_TZ
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


@dataclass(frozen=True)
class SectionSpend:
    """Una sezione in un periodo: quante chiamate, quante senza costo, quanto.

    `cost_usd` è la somma dei soli costi dichiarati: una chiamata senza costo sta in
    `unpriced_calls`, non nella somma come zero.
    """

    call_site: str
    calls: int
    unpriced_calls: int
    cost_usd: float


def _rome_day():
    """Il giorno di calendario a Roma di una chiamata.

    Il fuso è scritto nella query come costante e non passato come parametro: questa
    espressione sta sia nel SELECT sia nel GROUP BY, e due parametri (`$1`, `$2`) con lo
    stesso valore per Postgres sono due espressioni diverse («must appear in the GROUP BY
    clause»). Il valore viene dal codice, mai da chi chiama.
    """
    return cast(func.timezone(literal_column(f"'{PANTRY_TZ.key}'"), LlmCall.created_at), Date)


async def spend_by_section(
    session: AsyncSession, start: datetime, end: datetime
) -> list[SectionSpend]:
    """Le chiamate in `[start, end)`, sezione per sezione. L'ordine lo decide chi chiama."""
    rows = await session.execute(
        select(
            LlmCall.call_site,
            func.count(),
            func.count(LlmCall.cost_usd),
            func.coalesce(func.sum(LlmCall.cost_usd), 0.0),
        )
        .where(LlmCall.created_at >= start, LlmCall.created_at < end)
        .group_by(LlmCall.call_site)
    )
    return [
        SectionSpend(
            call_site=call_site,
            calls=calls,
            unpriced_calls=calls - priced,
            cost_usd=float(cost),
        )
        for call_site, calls, priced, cost in rows.all()
    ]


async def spend_by_day(session: AsyncSession, start: datetime, end: datetime) -> dict[date, float]:
    """La spesa dichiarata di ogni giorno di Roma in `[start, end)` che ha chiamate."""
    day = _rome_day()
    rows = await session.execute(
        select(day, func.coalesce(func.sum(LlmCall.cost_usd), 0.0))
        .where(LlmCall.created_at >= start, LlmCall.created_at < end)
        .group_by(day)
    )
    return {spent_on: float(cost) for spent_on, cost in rows.all()}


async def first_call_day(session: AsyncSession) -> date | None:
    """Il giorno di Roma della prima chiamata registrata, o `None` se non ce n'è."""
    first = await session.scalar(select(func.min(LlmCall.created_at)))
    return None if first is None else first.astimezone(PANTRY_TZ).date()
