"""H1: quanto è costata l'AI nel periodo, per sezione e giorno per giorno.

Il servizio si prova con «oggi» scritto a mano (il 13 ottobre 2026) e le chiamate datate
a mano in UTC: è il solo modo di provare i bordi dei giorni di Roma. La rotta si prova con
l'oggi vero, solo dove il risultato non dipende da che giorno è.

Il `created_at` si scrive sempre: dentro la transazione del test `now()` di Postgres è
l'ora d'inizio della transazione, uguale per tutte le righe.
"""

from datetime import UTC, date, datetime, timedelta

import pytest

from app.db.models.llm_call import LlmCall
from app.domain.rules import PANTRY_TZ, today_in_pantry
from app.domain.spending import SpendingPeriod
from app.services.spending import spending_report

OGGI = date(2026, 10, 13)


def utc(*parti: int) -> datetime:
    return datetime(*parti, tzinfo=UTC)


def chiamata(
    call_site: str, created_at: datetime, cost_usd: float | None, ok: bool = True
) -> LlmCall:
    return LlmCall(call_site=call_site, ok=ok, cost_usd=cost_usd, created_at=created_at)


async def semina(db_session, *chiamate: LlmCall) -> None:
    db_session.add_all(chiamate)
    await db_session.flush()


async def test_il_mese_somma_i_costi_dichiarati_per_sezione_dalla_piu_cara(db_session):
    await semina(
        db_session,
        chiamata("recipe_draft", utc(2026, 10, 5, 10), 0.012),
        chiamata("recipe_draft", utc(2026, 10, 13, 9), 0.008),
        # una fallita: costo NULL, come la registra ogni punto di chiamata
        chiamata("recipe_draft", utc(2026, 10, 13, 9, 5), None, ok=False),
        chiamata("term_decision", utc(2026, 10, 5, 11), 0.004),
        # settembre: fuori dal mese
        chiamata("term_decision", utc(2026, 9, 20, 10), 0.5),
    )

    report = await spending_report(db_session, SpendingPeriod.MONTH, OGGI)

    assert report.period == SpendingPeriod.MONTH
    assert (report.first_day, report.last_day) == (date(2026, 10, 1), OGGI)
    assert report.total_usd == pytest.approx(0.024)
    assert (report.calls, report.unpriced_calls) == (4, 1)
    assert [(s.call_site, s.label, s.calls) for s in report.sections] == [
        ("recipe_draft", "Ricette scritte con l'AI", 3),
        ("term_decision", "Abbinare gli ingredienti dell'import", 1),
    ]
    assert [s.cost_usd for s in report.sections] == pytest.approx([0.02, 0.004])
    assert [s.share for s in report.sections] == pytest.approx([0.8333, 0.1667])


async def test_i_giorni_si_contano_a_roma(db_session):
    await semina(
        db_session,
        chiamata("unit_forms", utc(2026, 10, 12, 22, 30), 0.001),  # 00:30 del 13 a Roma
        chiamata("unit_forms", utc(2026, 9, 30, 22, 30), 0.002),  # 00:30 dell'1 ottobre
        chiamata("unit_forms", utc(2026, 9, 30, 21, 30), 0.004),  # 23:30 del 30 settembre
    )

    report = await spending_report(db_session, SpendingPeriod.MONTH, OGGI)

    assert report.total_usd == pytest.approx(0.003)
    assert len(report.days) == 13
    assert report.days[0].day == date(2026, 10, 1)
    assert report.days[0].cost_usd == pytest.approx(0.002)
    assert report.days[-1].day == OGGI
    assert report.days[-1].cost_usd == pytest.approx(0.001)
    assert all(giorno.cost_usd == 0 for giorno in report.days[1:-1])


async def test_gli_ultimi_30_giorni_finiscono_oggi(db_session):
    await semina(
        db_session,
        chiamata("term_collapse", utc(2026, 9, 13, 22, 30), 0.001),  # 00:30 del 14 settembre
        chiamata("term_collapse", utc(2026, 9, 13, 21, 30), 0.5),  # 23:30 del 13: fuori
    )

    report = await spending_report(db_session, SpendingPeriod.LAST_30_DAYS, OGGI)

    assert (report.first_day, report.last_day) == (date(2026, 9, 14), OGGI)
    assert len(report.days) == 30
    assert report.total_usd == pytest.approx(0.001)
    assert report.days[0].cost_usd == pytest.approx(0.001)


async def test_da_sempre_parte_dal_giorno_della_prima_chiamata(db_session):
    await semina(
        db_session,
        chiamata("term_decision", utc(2026, 9, 16, 22, 30), 0.002),  # il 17 a Roma
        chiamata("recipe_draft", utc(2026, 10, 13, 8), 0.003),
    )

    report = await spending_report(db_session, SpendingPeriod.ALL, OGGI)

    assert (report.first_day, report.last_day) == (date(2026, 9, 17), OGGI)
    assert len(report.days) == 27
    assert report.total_usd == pytest.approx(0.005)


async def test_un_mese_senza_chiamate_ha_i_giorni_a_zero(db_session):
    report = await spending_report(db_session, SpendingPeriod.MONTH, OGGI)

    assert (report.calls, report.unpriced_calls, report.total_usd) == (0, 0, 0)
    assert report.sections == []
    assert len(report.days) == 13
    assert all(giorno.cost_usd == 0 for giorno in report.days)


async def test_da_sempre_senza_chiamate_e_solo_oggi(db_session):
    report = await spending_report(db_session, SpendingPeriod.ALL, OGGI)

    assert (report.first_day, report.last_day) == (OGGI, OGGI)
    assert [(giorno.day, giorno.cost_usd) for giorno in report.days] == [(OGGI, 0.0)]


async def test_una_sezione_sconosciuta_arriva_col_suo_nome(db_session):
    await semina(db_session, chiamata("sezione_di_un_altro_ramo", utc(2026, 10, 10, 10), 0.001))

    report = await spending_report(db_session, SpendingPeriod.MONTH, OGGI)

    assert [(s.call_site, s.label) for s in report.sections] == [
        ("sezione_di_un_altro_ramo", "sezione_di_un_altro_ramo")
    ]


async def test_una_riuscita_senza_costo_si_conta_e_non_vale_zero(db_session):
    """`usage.cost` è annullabile anche in una risposta buona: si conta, non si somma."""
    await semina(
        db_session,
        chiamata("recipe_draft", utc(2026, 10, 10, 10), None, ok=True),
        chiamata("unit_forms", utc(2026, 10, 10, 11), 0.002),
    )

    report = await spending_report(db_session, SpendingPeriod.MONTH, OGGI)

    assert (report.calls, report.unpriced_calls) == (2, 1)
    assert report.total_usd == 0.002
    assert [(s.call_site, s.cost_usd, s.share, s.calls) for s in report.sections] == [
        ("unit_forms", 0.002, 1.0, 1),
        ("recipe_draft", 0.0, 0.0, 1),
    ]


async def test_la_rotta_chiede_la_sessione(client):
    assert (await client.get("/api/v1/llm-spending")).status_code == 401


async def test_la_rotta_parte_da_questo_mese(logged_client, db_session):
    adesso = datetime.now(UTC)
    await semina(
        db_session,
        chiamata("recipe_draft", adesso, 0.003),
        chiamata("recipe_draft", adesso - timedelta(days=40), 0.5),
    )
    oggi = today_in_pantry()

    risposta = await logged_client.get("/api/v1/llm-spending")

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["period"] == "month"
    assert (corpo["first_day"], corpo["last_day"]) == (
        oggi.replace(day=1).isoformat(),
        oggi.isoformat(),
    )
    assert len(corpo["days"]) == oggi.day
    assert corpo["total_usd"] == pytest.approx(0.003)
    assert corpo["sections"] == [
        {
            "call_site": "recipe_draft",
            "label": "Ricette scritte con l'AI",
            "cost_usd": 0.003,
            "share": 1.0,
            "calls": 1,
        }
    ]


async def test_la_rotta_gli_ultimi_30_giorni(logged_client, db_session):
    adesso = datetime.now(UTC)
    await semina(
        db_session,
        chiamata("recipe_draft", adesso, 0.003),
        chiamata("recipe_draft", adesso - timedelta(days=40), 0.5),
    )
    oggi = today_in_pantry()

    corpo = (await logged_client.get("/api/v1/llm-spending?period=30d")).json()

    assert corpo["period"] == "30d"
    assert corpo["first_day"] == (oggi - timedelta(days=29)).isoformat()
    assert len(corpo["days"]) == 30
    assert corpo["total_usd"] == pytest.approx(0.003)


async def test_la_rotta_da_sempre(logged_client, db_session):
    adesso = datetime.now(UTC)
    prima = adesso - timedelta(days=40)
    await semina(
        db_session,
        chiamata("recipe_draft", adesso, 0.003),
        chiamata("recipe_draft", prima, 0.5),
    )

    corpo = (await logged_client.get("/api/v1/llm-spending?period=all")).json()

    assert corpo["period"] == "all"
    assert corpo["first_day"] == prima.astimezone(PANTRY_TZ).date().isoformat()
    assert corpo["total_usd"] == pytest.approx(0.503)


async def test_un_periodo_sconosciuto_e_422(logged_client):
    assert (await logged_client.get("/api/v1/llm-spending?period=year")).status_code == 422
