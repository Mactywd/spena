"""Il comando che fa abbinare all'AI gli ingredienti a CIQUAL (S4, fetta 1): quel che dice
a chi lo lancia. Il lavoro vero lo provano i test del servizio, coi finti dell'LLM."""

from sqlalchemy import select

from app.cli import decide_ciqual as comando
from app.cli.decide_ciqual import main
from app.db.models.ingredient import Ingredient
from app.db.models.nutrition import IngredientNutrition
from app.domain.ciqual import CiqualRow
from app.repositories.ciqual import upsert_foods


class _SessioneFinta:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


async def test_argomenti_sbagliati_escono_con_errore(capsys):
    assert await main(["--azzera"]) == 2
    assert "argomento sconosciuto: --azzera" in capsys.readouterr().out
    for argomenti in (["--limit"], ["--limit", "0"], ["--limit", "x"], ["--limit", "2", "3"]):
        assert await main(argomenti) == 2, argomenti


async def test_con_la_tabella_vuota_dice_di_caricarla(db_session, monkeypatch, capsys):
    monkeypatch.setattr(comando, "SessionLocal", lambda: _SessioneFinta(db_session))

    assert await main([]) == 1
    assert "La tabella CIQUAL è vuota: prima python -m app.cli.load_ciqual." in capsys.readouterr().out


async def test_senza_niente_da_decidere_l_ultima_riga_lo_dice(db_session, monkeypatch, capsys):
    await upsert_foods(db_session, [CiqualRow("90001", "Tomate, crue", "légumes", {"kcal": 18.0})])
    monkeypatch.setattr(comando, "SessionLocal", lambda: _SessioneFinta(db_session))

    assert await main([]) == 0

    stampato = capsys.readouterr().out
    assert stampato.rstrip().endswith("nessun ingrediente alimentare in attesa.")
    assert "non disponibili" not in stampato


async def test_senza_chiave_dice_quanti_ne_restano_e_non_scrive(db_session, monkeypatch, capsys):
    """La degradazione dichiarata: è quel che il comando fa sullo stack e2e (Task 11)."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    try:
        await upsert_foods(db_session, [CiqualRow("90001", "Tomate, crue", "légumes", {"kcal": 18.0})])
        db_session.add(Ingredient(name="pomodoro", display_name="Pomodoro", category="verdura"))
        await db_session.flush()
        monkeypatch.setattr(comando, "SessionLocal", lambda: _SessioneFinta(db_session))

        assert await main(["--limit", "5"]) == 0

        stampato = capsys.readouterr().out
        assert "abbinamenti non disponibili (ANTHROPIC_API_KEY non configurata)" in stampato
        assert "0 ingredienti abbinati, 0 senza un alimento adatto, 0 risposte rifiutate" in stampato
        assert "1 ingrediente alimentare resta da decidere: rilancia questo comando." in stampato
        assert (await db_session.execute(select(IngredientNutrition))).first() is None
    finally:
        get_settings.cache_clear()
