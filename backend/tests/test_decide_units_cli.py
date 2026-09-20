"""Il comando che fa decidere le unità: l'undo, e quel che dice a chi lo lancia."""

from sqlalchemy import select

from app.cli.decide_units import main
from app.db.models.unit import Unit
from app.repositories.units import reset_unit


async def test_azzerare_riporta_una_unita_a_non_decisa(db_session):
    """L'undo di una decisione AI: la chiamata successiva la ridecide."""
    db_session.add(
        Unit(key="costa", singular="costa", plural="cost", decided_by="ai")
    )
    await db_session.flush()

    assert await reset_unit(db_session, "costa") is True

    costa = (await db_session.execute(select(Unit).where(Unit.key == "costa"))).scalars().one()
    assert costa.decided_by is None and costa.singular is None and costa.plural is None


async def test_azzerare_una_chiave_che_non_esiste_lo_dice(db_session):
    assert await reset_unit(db_session, "inesistente") is False


class _SessioneFinta:
    """`SessionLocal()` nel test: consegna la sessione della fixture invece di
    aprirne una vera, così `main()` gira contro la stessa transazione annullabile
    che usano tutti gli altri test. Stessa forma di `test_reindex_cli.py`."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


async def test_un_argomento_sconosciuto_esce_con_errore(capsys):
    """Un refuso non deve passare per un successo: chi lancia questo comando da uno
    script legge l'exit code, e `--azzerra` scritto male non ha azzerato niente."""
    assert await main(["--azzerra"]) == 2
    assert "sconosciuto" in capsys.readouterr().out


async def test_azzera_senza_chiave_dice_come_si_usa(capsys):
    """Senza la parola da azzerare non c'è niente da fare, e dirlo costa una riga."""
    assert await main(["--azzera"]) == 2
    assert "uso: --azzera <chiave>" in capsys.readouterr().out


async def test_azzera_una_chiave_che_non_esiste_esce_diverso_da_zero(
    db_session, monkeypatch, capsys
):
    """«nessuna unità con quella chiave» non è un lavoro fatto: la differenza fra
    l'undo riuscito e l'undo a vuoto deve arrivare anche a chi guarda solo l'uscita."""
    monkeypatch.setattr(
        "app.cli.decide_units.SessionLocal", lambda: _SessioneFinta(db_session)
    )

    assert await main(["--azzera", "inesistente"]) == 1
    assert "nessuna unità" in capsys.readouterr().out


async def test_azzera_una_chiave_vera_la_riporta_a_non_decisa(
    db_session, monkeypatch, capsys
):
    """Il percorso felice per intero, comando compreso: fin qui il file provava solo
    `reset_unit` e non importava nemmeno il modulo del comando."""
    db_session.add(Unit(key="costa", singular="costa", plural="coste", decided_by="ai"))
    await db_session.flush()
    monkeypatch.setattr(
        "app.cli.decide_units.SessionLocal", lambda: _SessioneFinta(db_session)
    )

    assert await main(["--azzera", "costa"]) == 0
    assert "azzerata" in capsys.readouterr().out
    costa = (
        await db_session.execute(select(Unit).where(Unit.key == "costa"))
    ).scalars().one()
    assert costa.decided_by is None


async def test_senza_niente_da_fare_l_ultima_riga_lo_dice(
    db_session, monkeypatch, capsys
):
    """«0 unità decise» da solo non distingue «non c'era niente da fare» da «l'AI non
    ha risposto»: è il finding 3, e la riga in fondo è quel che lo chiude."""
    db_session.add(Unit(key="g", singular="g", plural="g", decided_by="ai"))
    await db_session.flush()
    monkeypatch.setattr(
        "app.cli.decide_units.SessionLocal", lambda: _SessioneFinta(db_session)
    )

    assert await main([]) == 0
    assert "nessuna parola in attesa" in capsys.readouterr().out


async def test_senza_chiave_configurata_dice_quante_ne_restano(
    db_session, monkeypatch, capsys
):
    """La degradazione dichiarata: nessuna chiave, nessuna rete, e l'ultima riga dice
    che c'è ancora del lavoro — altrimenti la messa in produzione non distingue
    questo caso da un comando riuscito."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        db_session.add(Unit(key="costa"))
        await db_session.flush()
        monkeypatch.setattr(
            "app.cli.decide_units.SessionLocal", lambda: _SessioneFinta(db_session)
        )

        assert await main([]) == 0

        stampato = capsys.readouterr().out
        assert "1 parola resta da decidere" in stampato
        assert (
            await db_session.execute(select(Unit).where(Unit.key == "costa"))
        ).scalars().one().decided_by is None
    finally:
        get_settings.cache_clear()
