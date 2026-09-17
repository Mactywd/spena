"""Lo storico delle chiamate all'LLM: quanto è costata ogni sezione dell'app.

Esiste perché l'attribuzione di OpenRouter non sa fare questa domanda. Per loro
un'app è un indirizzo — «your app's URL becomes its unique identifier» — e `X-Title`
ne cambia solo il nome visualizzato. Cinque titoli diversi non farebbero cinque voci
di spesa: farebbero un'app sola con il nome che sfarfalla. La divisione per sezione la
teniamo noi, sul costo che OpenRouter ci dichiara a ogni risposta.
"""

import pytest
from sqlalchemy import select

from app.db.models.llm_call import LlmCall
from app.repositories.llm_calls import record_llm_call
from app.services.llm import LlmCallSite, LlmUsage

pytestmark = pytest.mark.asyncio


async def test_una_chiamata_registrata_si_rilegge_con_la_sua_sezione(db_session):
    await record_llm_call(
        db_session,
        call_site=LlmCallSite.TERM_DECISION,
        usage=LlmUsage(
            generation_id="gen-1",
            model="google/gemma-4-26b-a4b-it",
            prompt_tokens=3100,
            completion_tokens=35,
            cost_usd=0.000123,
        ),
        ok=True,
    )
    await db_session.commit()

    riga = (await db_session.execute(select(LlmCall))).scalar_one()
    assert riga.call_site == LlmCallSite.TERM_DECISION
    assert riga.cost_usd == pytest.approx(0.000123)
    assert riga.prompt_tokens == 3100
    assert riga.completion_tokens == 35
    assert riga.generation_id == "gen-1"
    assert riga.model == "google/gemma-4-26b-a4b-it"
    assert riga.ok is True
    assert riga.created_at is not None


async def test_una_chiamata_fallita_si_registra_col_costo_sconosciuto(db_session):
    """Un modello giù è spesa sprecata, e va vista.

    Non registrarla renderebbe invisibile proprio il caso che si vuole scoprire: un
    giro dell'import che ritenta e non conclude. Il costo resta nullo-sconosciuto, non
    zero: di una richiesta rifiutata non sappiamo se ci è stata addebitata.
    """
    await record_llm_call(
        db_session, call_site=LlmCallSite.RECIPE_DRAFT, usage=LlmUsage(), ok=False
    )
    await db_session.commit()

    riga = (await db_session.execute(select(LlmCall))).scalar_one()
    assert riga.ok is False
    assert riga.cost_usd is None
    assert riga.prompt_tokens is None
