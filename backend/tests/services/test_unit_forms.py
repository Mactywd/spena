"""Le forme delle unità decise dall'AI, e la verifica della sua risposta.

Come per i termini dell'import, la parte che conta è la verifica: una risposta che
non si può controllare non si applica, e la parola resta non decisa — cioè si
continua a mostrarla grezza, che è brutto e non è rotto.

Il finto sostituisce `httpx.AsyncClient`, non il client di OpenRouter: sotto prova
c'è `complete_json` per intero, header e corpo compresi.
"""

import json

import pytest
from sqlalchemy import select

from app.db.models.unit import Unit
from app.services.unit_forms import MAX_UNITS_PER_RUN, decide_unit_forms
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


async def test_una_risposta_buona_e_una_rifiutata_non_si_trascinano(db_session):
    """Un lotto misto: la riga verificabile si scrive, l'altra no, e nessuna delle due
    decide della sorte dell'altra.

    L'indipendenza fin qui stava solo nel `continue`, che è un dettaglio di scrittura:
    è precisamente il caso che l'AI produce più spesso — quasi tutto giusto e una
    parola storta — e senza un test qui, rendere quel rifiuto un `return` non
    romperebbe niente di verde.
    """
    await _unita(db_session, "cucchiai", "costa")
    finto = FakeLlm({"units": [
        {"key": "cucchiai", "singular": "cucchiaio", "plural": "cucchiai"},
        {"key": "costa", "singular": "", "plural": "coste"},
    ]})

    esito = await decide_unit_forms(db_session, client=finto)

    assert (esito.applied, esito.refused, esito.pending) == (1, 1, 1)
    assert (await _riletta(db_session, "cucchiai")).singular == "cucchiaio"
    assert (await _riletta(db_session, "costa")).decided_by is None


async def test_il_lotto_ha_un_tetto_e_il_resto_aspetta_il_giro_dopo(db_session):
    """Il quinto insegnamento di CLAUDE.md: `FORMS_MAX_TOKENS` era dimensionato sulle
    22 unità del seme, e un catalogo nuovo ne porta altre. Oltre il tetto la risposta
    arriva tagliata, `complete_json` non la sa leggere e non si applica niente — in
    silenzio e identicamente a ogni rilancio."""
    chiavi = [f"unita{n:02d}" for n in range(MAX_UNITS_PER_RUN + 3)]
    await _unita(db_session, *chiavi)
    finto = FakeLlm({"units": []})

    esito = await decide_unit_forms(db_session, client=finto)

    chieste = json.loads(finto.bodies[0]["messages"][1]["content"])["units"]
    assert len(chieste) == MAX_UNITS_PER_RUN
    # e quel che è rimasto fuori non è sparito: il comando lo dice e il giro dopo lo prende
    assert esito.pending == len(chiavi)


async def test_ai_irraggiungibile_non_scrive_niente_e_lo_dice(db_session, capsys):
    """Per l'utente non è successo niente: il riporziona scala lo stesso e mostra la
    parola come è arrivata. Per chi ha lanciato il comando invece è successo tutto, e
    va detto a voce: `app/` non configura nessun logging, quindi la riga a
    `logger.info` di prima non usciva da nessuna parte e «0 unità decise» sembrava
    «non c'era niente da fare»."""
    import httpx

    await _unita(db_session, "costa")
    finto = FakeLlm(httpx.ReadTimeout("lento"))

    esito = await decide_unit_forms(db_session, client=finto)

    assert (esito.applied, esito.pending) == (0, 1)
    assert "non disponibili" in capsys.readouterr().out
    assert (await _riletta(db_session, "costa")).decided_by is None


async def test_senza_unita_in_attesa_non_chiama_nessuno(db_session):
    """Il comando si può lanciare due volte di fila senza spendere due volte."""
    db_session.add(Unit(key="g", singular="g", plural="g", decided_by="ai"))
    await db_session.flush()
    finto = FakeLlm({"units": []})

    esito = await decide_unit_forms(db_session, client=finto)

    assert (esito.applied, esito.refused, esito.pending) == (0, 0, 0)
    assert finto.bodies == []
