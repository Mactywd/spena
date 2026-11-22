"""Il comando che fa decidere all'AI le figure degli ingredienti (S12): quel che dice a
chi lo lancia. Il lavoro vero lo provano i test del servizio, con i finti dell'LLM."""

from sqlalchemy import select

from app.cli.decide_emoji import main
from app.db.models.ingredient import Ingredient


class _SessioneFinta:
    """`SessionLocal()` nel test: consegna la sessione della fixture invece di
    aprirne una vera, così `main()` gira contro la stessa transazione annullabile
    che usano tutti gli altri test. Stessa forma di `test_decide_units_cli.py`."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


async def test_un_argomento_qualsiasi_esce_con_errore(capsys):
    """Il comando non ha opzioni: la correzione è in Anagrafica. Un `--azzera` copiato
    da `decide_units` non deve passare per un successo."""
    assert await main(["--azzera"]) == 2
    assert "sconosciuto" in capsys.readouterr().out


async def test_senza_niente_da_decidere_l_ultima_riga_lo_dice(db_session, monkeypatch, capsys):
    db_session.add(Ingredient(name="carota", display_name="Carota", category="verdura", emoji="🥕"))
    await db_session.flush()
    monkeypatch.setattr("app.cli.decide_emoji.SessionLocal", lambda: _SessioneFinta(db_session))

    assert await main([]) == 0

    stampato = capsys.readouterr().out
    assert "nessun ingrediente in attesa" in stampato
    assert "non disponibili" not in stampato


async def test_senza_chiave_dice_quanti_ne_restano_e_non_scrive(db_session, monkeypatch, capsys):
    """La degradazione dichiarata: nessuna chiave, nessuna rete, nessuna scrittura, e
    l'ultima riga dice che c'è ancora del lavoro. È quel che il comando fa sullo stack
    e2e, dove la chiave è vuota (Task 9)."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        carota = Ingredient(name="carota", display_name="Carota", category="verdura")
        db_session.add(carota)
        await db_session.flush()
        monkeypatch.setattr("app.cli.decide_emoji.SessionLocal", lambda: _SessioneFinta(db_session))

        assert await main([]) == 0

        stampato = capsys.readouterr().out
        assert "figure non disponibili" in stampato
        assert "1 ingrediente resta da decidere" in stampato
        assert (
            await db_session.execute(select(Ingredient.emoji).where(Ingredient.id == carota.id))
        ).scalar_one() is None
    finally:
        get_settings.cache_clear()
