"""Le chiamate sul piano di Claude (la chat dei piatti) si contano a parte: niente costo."""

from datetime import UTC, date, datetime

import pytest

from app.db.models.llm_call import LlmCall
from app.domain.spending import SpendingPeriod
from app.services.spending import spending_report

OGGI = date(2026, 10, 13)
QUANDO = datetime(2026, 10, 5, 10, tzinfo=UTC)


def chat(prompt: int | None, completion: int | None, ok: bool = True) -> LlmCall:
    return LlmCall(
        call_site="meal_chat",
        ok=ok,
        cost_usd=None,
        prompt_tokens=prompt,
        completion_tokens=completion,
        created_at=QUANDO,
    )


def bozza() -> LlmCall:
    return LlmCall(call_site="recipe_draft", ok=True, cost_usd=0.01, created_at=QUANDO)


async def test_le_chiamate_sul_piano_stanno_a_parte(db_session):
    db_session.add_all([bozza(), bozza(), chat(1000, 200), chat(1000, 200), chat(1000, 200, ok=False)])
    await db_session.flush()

    report = await spending_report(db_session, SpendingPeriod.MONTH, OGGI)

    assert report.total_usd == pytest.approx(0.02)
    assert (report.calls, report.unpriced_calls) == (2, 0)
    assert [s.call_site for s in report.sections] == ["recipe_draft"]
    assert [p.model_dump() for p in report.plan_sections] == [
        {
            "call_site": "meal_chat",
            "label": "Chat dei piatti",
            "calls": 3,
            "tokens": 3600,
            "note": "sul piano di Claude, non a consumo",
        }
    ]


async def test_solo_chiamate_sul_piano(db_session):
    db_session.add_all([chat(2000, 400), chat(1000, 200), chat(None, None, ok=False)])
    await db_session.flush()

    report = await spending_report(db_session, SpendingPeriod.MONTH, OGGI)

    assert report.calls == 0
    assert report.total_usd == 0
    assert report.sections == []
    assert [(p.call_site, p.calls, p.tokens) for p in report.plan_sections] == [("meal_chat", 3, 3600)]
