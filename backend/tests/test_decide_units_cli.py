"""Il comando che fa decidere le unità: l'undo, e quel che dice a chi lo lancia."""

from sqlalchemy import select

from app.cli.decide_units import main
from app.db.models.unit import UNIT_MAX_LENGTH, Unit
from app.repositories.units import reset_unit, set_unit_forms, undecided_units


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


async def test_imposta_scrive_le_forme_a_mano(db_session):
    """La correzione che l'`--azzera` da solo non sa fare.

    Misurato in produzione il 2026-09-20: azzerare «cucchiai» e rilanciare ha
    riprodotto lo stesso errore del modello («cchiaio», con la «u» mangiata). Un
    annulla senza un «invece è così» è mezzo strumento, e per una parola che
    sbaglia in modo ripetibile era l'unica strada rimasta una UPDATE a mano.
    """
    db_session.add(Unit(key="cucchiai", singular="cchiaio", plural="cucchiai", decided_by="ai"))
    await db_session.flush()

    assert await set_unit_forms(db_session, "cucchiai", "cucchiaio", "cucchiai") is True

    riga = (
        await db_session.execute(select(Unit).where(Unit.key == "cucchiai"))
    ).scalars().one()
    assert riga.singular == "cucchiaio" and riga.plural == "cucchiai"
    # «human» e non «ai»: chi legge il registro deve poter distinguere una riga che
    # il modello ha deciso da una che qualcuno ha corretto, altrimenti la seconda
    # sembra un successo del primo.
    assert riga.decided_by == "human"
    assert riga.decided_at is not None


async def test_imposta_una_chiave_che_non_esiste_lo_dice(db_session):
    assert await set_unit_forms(db_session, "inesistente", "uno", "due") is False


async def test_una_forma_messa_a_mano_non_torna_in_coda(db_session):
    """Una decisione umana è definitiva finché non la si azzera: se `decide_units`
    la ripescasse, il modello rifarebbe l'errore che qualcuno è appena andato a
    correggere — e la correzione durerebbe fino al comando dopo."""
    db_session.add(Unit(key="cucchiai"))
    await db_session.flush()

    await set_unit_forms(db_session, "cucchiai", "cucchiaio", "cucchiai")

    assert [u.key for u in await undecided_units(db_session)] == []


async def test_imposta_punta_al_canonico_come_fa_l_ai(db_session):
    """Stessa regola di `apply_forms`, perché è lo stesso fatto: «cucchiai» il cui
    singolare è «cucchiaio», che in anagrafica esiste già, ci punta — così S4
    riempirà il peso di quell'unità una volta sola. Scriverla due volte in due
    funzioni sarebbe il modo di farle divergere."""
    canonico = Unit(key="cucchiaio", singular="cucchiaio", plural="cucchiai", decided_by="ai")
    db_session.add_all([canonico, Unit(key="cucchiai")])
    await db_session.flush()

    await set_unit_forms(db_session, "cucchiai", "cucchiaio", "cucchiai")

    riga = (
        await db_session.execute(select(Unit).where(Unit.key == "cucchiai"))
    ).scalars().one()
    assert riga.canonical_id == canonico.id


async def test_imposta_con_gli_argomenti_sbagliati_dice_come_si_usa(capsys):
    assert await main(["--imposta", "cucchiai"]) == 2
    assert "uso: --imposta <chiave> <singolare> <plurale>" in capsys.readouterr().out


async def test_imposta_una_forma_vuota_o_troppo_lunga_non_passa(capsys):
    """Lo stesso rifiuto che `decide_unit_forms` applica alla risposta dell'AI: le
    colonne sono `String(UNIT_MAX_LENGTH)`, e una parola più lunga non produrrebbe
    un errore leggibile ma un troncamento di Postgres a metà della scrittura."""
    assert await main(["--imposta", "cucchiai", "", "cucchiai"]) == 2
    assert "vuota" in capsys.readouterr().out

    troppo = "c" * (UNIT_MAX_LENGTH + 1)
    assert await main(["--imposta", "cucchiai", troppo, "cucchiai"]) == 2
    assert str(UNIT_MAX_LENGTH) in capsys.readouterr().out


async def test_imposta_una_chiave_che_non_esiste_esce_diverso_da_zero(
    db_session, monkeypatch, capsys
):
    monkeypatch.setattr(
        "app.cli.decide_units.SessionLocal", lambda: _SessioneFinta(db_session)
    )

    assert await main(["--imposta", "inesistente", "uno", "due"]) == 1
    assert "nessuna unità" in capsys.readouterr().out


async def test_imposta_una_chiave_vera_scrive_e_lo_dice(db_session, monkeypatch, capsys):
    """Il percorso felice per intero, comando compreso."""
    db_session.add(Unit(key="cucchiai", singular="cchiaio", plural="cucchiai", decided_by="ai"))
    await db_session.flush()
    monkeypatch.setattr(
        "app.cli.decide_units.SessionLocal", lambda: _SessioneFinta(db_session)
    )

    assert await main(["--imposta", "cucchiai", "cucchiaio", "cucchiai"]) == 0
    assert "cucchiaio" in capsys.readouterr().out
    riga = (
        await db_session.execute(select(Unit).where(Unit.key == "cucchiai"))
    ).scalars().one()
    assert riga.singular == "cucchiaio" and riga.decided_by == "human"
