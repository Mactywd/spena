"""Ogni chiamata all'AI di S4 si registra, anche quella fallita, e si somma nel conto."""

import httpx
import pytest
from sqlalchemy import select

from app.db.models.llm_call import LlmCall
from app.services.ai_spend import Spend, complete_recorded
from app.services.llm import LlmCallSite, LlmUnavailable
from llm_fakes import COSTO_FINTO, FakeLlm

SCHEMA = {
    "type": "object",
    "properties": {"x": {"type": "integer"}},
    "required": ["x"],
    "additionalProperties": False,
}


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


async def _chiama(db_session, finto, spesa):
    return await complete_recorded(
        db_session, call_site=LlmCallSite.CIQUAL_TERMS, system="s", user="u",
        schema=SCHEMA, max_tokens=10, client=finto, spend=spesa,
    )


async def test_una_chiamata_riuscita_si_registra_e_si_somma(db_session):
    spesa = Spend()

    assert await _chiama(db_session, FakeLlm({"x": 1}), spesa) == {"x": 1}

    assert (spesa.calls, spesa.unpriced) == (1, 0)
    assert spesa.cost_usd == pytest.approx(COSTO_FINTO)
    riga = (await db_session.execute(select(LlmCall))).scalars().one()
    assert (riga.call_site, riga.ok, riga.cost_usd) == ("ciqual_terms", True, COSTO_FINTO)


async def test_una_chiamata_fallita_si_registra_e_si_conta_senza_costo(db_session):
    spesa = Spend()

    with pytest.raises(LlmUnavailable):
        await _chiama(db_session, FakeLlm(httpx.ConnectError("rete giù")), spesa)

    assert (spesa.calls, spesa.unpriced, spesa.cost_usd) == (1, 1, 0.0)
    riga = (await db_session.execute(select(LlmCall))).scalars().one()
    assert (riga.call_site, riga.ok, riga.cost_usd) == ("ciqual_terms", False, None)
