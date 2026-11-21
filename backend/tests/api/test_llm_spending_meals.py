"""I Pasti hanno un costo vero e contano nelle spese come ogni altra sezione."""

from datetime import UTC, date, datetime

import pytest

from app.db.models.llm_call import LlmCall
from app.domain.spending import SpendingPeriod
from app.services.spending import spending_report

OGGI = date(2026, 10, 13)
QUANDO = datetime(2026, 10, 13, 10, tzinfo=UTC)


def chiamata(
    call_site: str, cost: float | None, ok: bool = True, quando: datetime = QUANDO
) -> LlmCall:
    return LlmCall(call_site=call_site, ok=ok, cost_usd=cost, created_at=quando)


async def test_i_pasti_contano_nel_totale(logged_client, db_session):
    adesso = datetime.now(UTC)
    db_session.add_all(
        [chiamata("meal_chat", 0.30, quando=adesso), chiamata("term_decision", 0.10, quando=adesso)]
    )
    await db_session.flush()

    corpo = (await logged_client.get("/api/v1/llm-spending?period=30d")).json()

    assert "plan_sections" not in corpo
    assert corpo["total_usd"] == pytest.approx(0.4)
    assert corpo["calls"] == 2
    assert (corpo["sections"][0]["call_site"], corpo["sections"][0]["label"]) == (
        "meal_chat",
        "Chat dei piatti",
    )
    assert corpo["sections"][0]["share"] == pytest.approx(0.75)
    assert corpo["days"][-1]["cost_usd"] == pytest.approx(0.4)


async def test_un_giro_dei_pasti_senza_costo_sta_fra_quelli_senza_costo(db_session):
    db_session.add_all([chiamata("meal_planning", None, ok=False)])
    await db_session.flush()

    report = await spending_report(db_session, SpendingPeriod.MONTH, OGGI)

    assert (report.calls, report.unpriced_calls) == (1, 1)
    assert report.total_usd == 0
