"""Quanto è costata l'AI in un periodo, e come si divide (H1).

Tutto il calcolo sta qui e nel dominio: il frontend riceve somme, quote, nomi e giorni già
decisi, e li disegna.
"""

from datetime import date, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.spending import (
    PLAN_CALL_SITES,
    PLAN_NOTE,
    SpendingPeriod,
    call_site_label,
    daily_series,
    day_start,
    money,
    period_days,
    share,
)
from app.repositories.llm_calls import first_call_day, spend_by_day, spend_by_section
from app.schemas.spending import DaySpendOut, PlanSectionOut, SectionSpendOut, SpendingOut


async def spending_report(
    session: AsyncSession, period: SpendingPeriod, today: date
) -> SpendingOut:
    first_call = await first_call_day(session) if period is SpendingPeriod.ALL else None
    first, last = period_days(period, today, first_call)
    start, end = day_start(first), day_start(last + timedelta(days=1))

    all_sections = await spend_by_section(session, start, end)
    # le chiamate sul piano non hanno costo: non entrano nel conto a consumo
    sections = [s for s in all_sections if s.call_site not in PLAN_CALL_SITES]
    plan = sorted(
        (s for s in all_sections if s.call_site in PLAN_CALL_SITES), key=lambda s: s.call_site
    )
    by_day = await spend_by_day(session, start, end)
    total = money(sum(section.cost_usd for section in sections))
    # dalla più cara; a parità, quella con più chiamate, poi il nome: un ordine fisso, così
    # due periodi con le stesse cifre non si mostrano in due ordini
    ordered = sorted(
        sections,
        key=lambda section: (-section.cost_usd, -section.calls, call_site_label(section.call_site)),
    )
    return SpendingOut(
        period=period,
        first_day=first,
        last_day=last,
        total_usd=total,
        calls=sum(section.calls for section in sections),
        unpriced_calls=sum(section.unpriced_calls for section in sections),
        sections=[
            SectionSpendOut(
                call_site=section.call_site,
                label=call_site_label(section.call_site),
                cost_usd=money(section.cost_usd),
                share=share(section.cost_usd, total),
                calls=section.calls,
            )
            for section in ordered
        ],
        plan_sections=[
            PlanSectionOut(
                call_site=section.call_site,
                label=call_site_label(section.call_site),
                calls=section.calls,
                tokens=section.prompt_tokens + section.completion_tokens,
                note=PLAN_NOTE,
            )
            for section in plan
        ],
        days=[
            DaySpendOut(day=day, cost_usd=money(cost))
            for day, cost in daily_series(first, last, by_day)
        ],
    )
