"""Il comando che fa pesare all'AI le dosi (S4, fetta 2): quel che dice a chi lo lancia."""

from sqlalchemy import select

from app.cli import decide_grams as comando
from app.cli.decide_grams import main
from app.db.models.ingredient import Ingredient
from app.db.models.nutrition import IngredientUnitGrams
from app.db.models.recipe import RecipeSource
from app.repositories.recipes import create_recipe
from app.services.unit_grams import GramsRun


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
    for argomenti in (["--limit"], ["--limit", "0"], ["--limit", "x"], ["--limit", "²"]):
        assert await main(argomenti) == 2, argomenti


async def test_senza_niente_da_pesare_l_ultima_riga_lo_dice(db_session, monkeypatch, capsys):
    monkeypatch.setattr(comando, "SessionLocal", lambda: _SessioneFinta(db_session))

    assert await main([]) == 0
    assert capsys.readouterr().out.rstrip().endswith("nessuna coppia in attesa di un peso.")


async def test_senza_chiave_dice_quante_ne_restano_e_non_scrive(db_session, monkeypatch, capsys):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
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
        assert "pesi non disponibili (ANTHROPIC_API_KEY non configurata)" in stampato
        assert "0 pesi scritti, 0 senza un peso sensato, 0 risposte rifiutate" in stampato
        assert "1 coppia resta da pesare: rilancia questo comando." in stampato
        assert (await db_session.execute(select(IngredientUnitGrams))).first() is None
    finally:
        get_settings.cache_clear()


def _con_esito(monkeypatch, db_session, esito: GramsRun) -> None:
    async def finta(session, **_):
        return esito

    monkeypatch.setattr(comando, "decide_grams", finta)
    monkeypatch.setattr(comando, "SessionLocal", lambda: _SessioneFinta(db_session))


async def test_nomina_le_coppie_saltate(db_session, monkeypatch, capsys):
    _con_esito(
        monkeypatch,
        db_session,
        GramsRun(
            weighed=5, none=1, refused=0, pending=2, asked=8,
            skipped=("aceto di mele × di", "acqua × bicchiere"),
            last_error="Expecting ':' delimiter",
        ),
    )

    assert await main([]) == 0

    righe = capsys.readouterr().out.rstrip().splitlines()
    assert righe == [
        "5 pesi scritti, 1 senza un peso sensato, 0 risposte rifiutate",
        "2 coppie saltate in questo giro, perché la risposta dell'AI non si leggeva nemmeno "
        "da sole (Expecting ':' delimiter): aceto di mele × di, acqua × bicchiere. Restano da "
        "pesare: un altro giro le richiede, o si pesano in Anagrafica, «Pesi per unità».",
        "2 coppie restano da pesare: rilancia questo comando.",
    ]


async def test_nomina_una_coppia_saltata(db_session, monkeypatch, capsys):
    _con_esito(
        monkeypatch,
        db_session,
        GramsRun(weighed=1, pending=1, asked=2, skipped=("acqua × bicchiere",), last_error="JSON rotto"),
    )

    assert await main([]) == 0

    assert (
        "1 coppia saltata in questo giro, perché la risposta dell'AI non si leggeva nemmeno "
        "da sola (JSON rotto): acqua × bicchiere. Resta da pesare: un altro giro la richiede, "
        "o si pesa in Anagrafica, «Pesi per unità».\n"
        "1 coppia resta da pesare: rilancia questo comando."
    ) in capsys.readouterr().out


async def test_oltre_venti_coppie_saltate_nomina_le_prime_venti(db_session, monkeypatch, capsys):
    saltate = tuple(f"voce {n} × pezzo" for n in range(1, 24))
    _con_esito(
        monkeypatch,
        db_session,
        GramsRun(pending=23, asked=23, skipped=saltate, last_error="x"),
    )

    assert await main([]) == 0

    stampato = capsys.readouterr().out
    assert (
        "23 coppie saltate in questo giro, perché la risposta dell'AI non si leggeva nemmeno "
        f"da sole (x): {', '.join(saltate[:20])}, e altre 3. Restano da pesare:"
    ) in stampato
    assert "voce 21 × pezzo" not in stampato


async def test_senza_coppie_saltate_non_ne_parla(db_session, monkeypatch, capsys):
    _con_esito(monkeypatch, db_session, GramsRun(weighed=3, asked=3))

    assert await main([]) == 0

    assert "saltat" not in capsys.readouterr().out


async def test_dice_quanti_pesi_ha_spostato(db_session, monkeypatch, capsys):
    _con_esito(monkeypatch, db_session, GramsRun(realigned=1))
    assert await main([]) == 0
    assert capsys.readouterr().out.splitlines()[0] == "1 peso spostato sull'unità canonica."

    _con_esito(monkeypatch, db_session, GramsRun(realigned=3))
    assert await main([]) == 0
    assert capsys.readouterr().out.splitlines()[0] == "3 pesi spostati sull'unità canonica."

    _con_esito(monkeypatch, db_session, GramsRun())
    assert await main([]) == 0
    assert "sull'unità canonica" not in capsys.readouterr().out
