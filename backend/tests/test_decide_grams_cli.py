"""Il comando che fa pesare all'AI le dosi (S4, fetta 2): quel che dice a chi lo lancia."""

from sqlalchemy import select

from app.cli import decide_grams as comando
from app.cli.decide_grams import main
from app.db.models.ingredient import Ingredient
from app.db.models.nutrition import IngredientUnitGrams
from app.db.models.recipe import RecipeSource
from app.repositories.recipes import create_recipe


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
    for argomenti in (["--limit"], ["--limit", "0"], ["--limit", "x"]):
        assert await main(argomenti) == 2, argomenti


async def test_senza_niente_da_pesare_l_ultima_riga_lo_dice(db_session, monkeypatch, capsys):
    monkeypatch.setattr(comando, "SessionLocal", lambda: _SessioneFinta(db_session))

    assert await main([]) == 0
    assert capsys.readouterr().out.rstrip().endswith("nessuna coppia in attesa di un peso.")


async def test_senza_chiave_dice_quante_ne_restano_e_non_scrive(db_session, monkeypatch, capsys):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        aglio = Ingredient(name="aglio", display_name="Aglio", category="verdura")
        db_session.add(aglio)
        await db_session.flush()
        await create_recipe(
            db_session, title="Prova", description=None, instructions="x", servings=2,
            source=RecipeSource.MANUAL, source_ref=None, embedding=None,
            ingredients=[(aglio.id, "secondary", "1 spicchio", None)],
        )
        monkeypatch.setattr(comando, "SessionLocal", lambda: _SessioneFinta(db_session))

        assert await main([]) == 0

        stampato = capsys.readouterr().out
        assert "pesi non disponibili (OPENROUTER_API_KEY non configurata)" in stampato
        assert "0 pesi scritti, 0 senza un peso sensato, 0 risposte rifiutate" in stampato
        assert "1 coppia resta da pesare: rilancia questo comando." in stampato
        assert (await db_session.execute(select(IngredientUnitGrams))).first() is None
    finally:
        get_settings.cache_clear()
