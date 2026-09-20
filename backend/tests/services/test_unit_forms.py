"""Le forme delle unità decise dall'AI, e la verifica della sua risposta.

Come per i termini dell'import, la parte che conta è la verifica: una risposta che
non si può controllare non si applica, e la parola resta non decisa — cioè si
continua a mostrarla grezza, che è brutto e non è rotto.

Il finto sostituisce `httpx.AsyncClient`, non il client di OpenRouter: sotto prova
c'è `complete_json` per intero, header e corpo compresi.
"""

import pytest
from sqlalchemy import select

from app.db.models.unit import Unit
from app.services.unit_forms import decide_unit_forms
from llm_fakes import FakeLlm


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


async def _unita(db_session, *keys: str) -> None:
    db_session.add_all([Unit(key=key) for key in keys])
    await db_session.flush()


async def _riletta(db_session, key: str) -> Unit:
    return (
        await db_session.execute(select(Unit).where(Unit.key == key))
    ).scalars().one()


async def test_applica_le_forme_decise(db_session):
    await _unita(db_session, "cucchiai", "costa")
    finto = FakeLlm({"units": [
        {"key": "cucchiai", "singular": "cucchiaio", "plural": "cucchiai"},
        {"key": "costa", "singular": "costa", "plural": "coste"},
    ]})

    esito = await decide_unit_forms(db_session, client=finto)

    assert esito.applied == 2 and esito.refused == 0
    costa = await _riletta(db_session, "costa")
    assert (costa.singular, costa.plural) == ("costa", "coste")
    assert costa.decided_by == "ai" and costa.decided_at is not None


async def test_una_chiave_non_chiesta_non_si_applica(db_session):
    await _unita(db_session, "costa")
    finto = FakeLlm({"units": [
        {"key": "spicchio", "singular": "spicchio", "plural": "spicchi"},
    ]})

    esito = await decide_unit_forms(db_session, client=finto)

    assert esito.applied == 0 and esito.refused == 1
    assert (await _riletta(db_session, "costa")).decided_by is None
    # e non è comparsa una riga per una parola che nessuna ricetta ha mai scritto
    assert (
        await db_session.execute(select(Unit).where(Unit.key == "spicchio"))
    ).scalars().first() is None


async def test_una_forma_vuota_non_si_applica(db_session):
    await _unita(db_session, "costa")
    finto = FakeLlm({"units": [{"key": "costa", "singular": "", "plural": "coste"}]})

    esito = await decide_unit_forms(db_session, client=finto)

    assert esito.applied == 0 and esito.refused == 1
    assert (await _riletta(db_session, "costa")).decided_by is None


async def test_il_singolare_che_esiste_gia_non_duplica(db_session):
    """«cucchiai» punta a «cucchiaio»: serve a S4, che riempirà il peso della coppia
    ingrediente×unità una volta sola invece di due."""
    cucchiaio = Unit(
        key="cucchiaio", singular="cucchiaio", plural="cucchiai", decided_by="ai"
    )
    db_session.add_all([cucchiaio, Unit(key="cucchiai")])
    await db_session.flush()
    finto = FakeLlm({"units": [
        {"key": "cucchiai", "singular": "cucchiaio", "plural": "cucchiai"},
    ]})

    await decide_unit_forms(db_session, client=finto)

    riga = await _riletta(db_session, "cucchiai")
    assert riga.canonical_id == cucchiaio.id
    # le forme si scrivono comunque sulla riga: il dettaglio della ricetta le legge
    # dirette, senza seguire il puntatore a ogni lettura
    assert riga.singular == "cucchiaio"


async def test_ai_irraggiungibile_non_scrive_niente(db_session):
    """Per l'utente non è successo niente: il riporziona scala lo stesso e mostra la
    parola come è arrivata."""
    import httpx

    await _unita(db_session, "costa")
    finto = FakeLlm(httpx.ReadTimeout("lento"))

    esito = await decide_unit_forms(db_session, client=finto)

    assert esito.applied == 0
    assert (await _riletta(db_session, "costa")).decided_by is None


async def test_senza_unita_in_attesa_non_chiama_nessuno(db_session):
    """Il comando si può lanciare due volte di fila senza spendere due volte."""
    db_session.add(Unit(key="g", singular="g", plural="g", decided_by="ai"))
    await db_session.flush()
    finto = FakeLlm({"units": []})

    esito = await decide_unit_forms(db_session, client=finto)

    assert (esito.applied, esito.refused) == (0, 0)
    assert finto.bodies == []
