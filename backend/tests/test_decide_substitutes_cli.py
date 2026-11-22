"""Il comando che fa decidere all'AI i sostituti (R5): quel che dice a chi lo lancia.
Il lavoro vero lo provano i test del servizio, coi finti dell'LLM."""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.cli.decide_substitutes import main
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.llm_call import LlmCall
from app.db.models.recipe import RecipeSource
from app.db.models.substitution import IngredientSubstitution
from app.repositories.recipes import create_recipe
from llm_fakes import FakeLlm


class _SessioneFinta:
    """`SessionLocal()` nel test: consegna la sessione della fixture invece di aprirne una
    vera, così `main()` gira contro la stessa transazione annullabile degli altri test.
    Stessa forma di `test_decide_units_cli.py`."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


@pytest_asyncio.fixture
async def due_voci(db_session, monkeypatch):
    """Pollo in un secondo (salato), burro in un dolce: due voci, una ricetta ciascuna."""
    pollo = Ingredient(name="pollo", display_name="Pollo", category=IngredientCategory.CARNE)
    burro = Ingredient(name="burro", display_name="Burro", category=IngredientCategory.LATTICINI)
    db_session.add_all([pollo, burro])
    await db_session.flush()
    for titolo, categoria, voce in (("Pollo arrosto", "Secondi piatti", pollo), ("Biscotti", "Dolci", burro)):
        await create_recipe(
            db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
            source=RecipeSource.MANUAL, source_ref=None,
            ingredients=[(voce.id, "primary", None, None)], embedding=None, category=categoria,
        )
    monkeypatch.setattr(
        "app.cli.decide_substitutes.SessionLocal", lambda: _SessioneFinta(db_session)
    )
    return {"pollo": pollo, "burro": burro}


@pytest.fixture
def senza_chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    yield
    get_settings.cache_clear()


@pytest.fixture
def con_chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


async def test_un_argomento_sconosciuto_esce_con_errore(capsys):
    assert await main(["--tutto"]) == 2
    assert "argomento sconosciuto: --tutto" in capsys.readouterr().out


@pytest.mark.parametrize("argv", [["--limit"], ["--limit", "0"], ["--limit", "due"], ["--limit", "-3"]])
async def test_limit_vuole_un_numero_maggiore_di_zero(argv, capsys):
    assert await main(argv) == 2
    assert "uso: --limit" in capsys.readouterr().out


async def test_dry_run_dice_cosa_chiederebbe_e_non_chiama_nessuno(
    db_session, due_voci, con_chiave, monkeypatch, capsys
):
    finto = FakeLlm()
    monkeypatch.setattr("app.services.substitutions.open_client", lambda: finto)

    assert await main(["--dry-run"]) == 0

    stampato = capsys.readouterr().out
    assert "2 voci senza sostituti: 1 nei piatti salati, 1 nei dolci." in stampato
    assert "ne chiederei 2, dalle più usate:" in stampato
    assert "- burro (dolce, 1 ricetta)" in stampato
    assert "nessun costo misurato ancora: lancia con --limit 20 per misurarlo." in stampato
    assert finto.bodies == []
    assert (await db_session.execute(select(LlmCall.id))).all() == []


async def test_dry_run_stima_con_il_costo_misurato(db_session, due_voci, capsys):
    db_session.add_all([
        LlmCall(call_site="ingredient_substitutes", ok=True, cost_usd=0.0004, model="claude-haiku-5-5"),
        LlmCall(call_site="ingredient_substitutes", ok=True, cost_usd=0.0006, model="claude-haiku-5-5"),
        # una fallita, una d'altra sezione e una d'un altro modello non contano
        LlmCall(call_site="ingredient_substitutes", ok=True, cost_usd=0.5, model="google/gemma-4-26b-a4b-it"),
        LlmCall(call_site="ingredient_substitutes", ok=False, cost_usd=None),
        LlmCall(call_site="term_decision", ok=True, cost_usd=0.1),
    ])
    await db_session.flush()

    assert await main(["--dry-run", "--limit", "1"]) == 0

    stampato = capsys.readouterr().out
    assert "ne chiederei 1, dalle più usate:" in stampato
    assert "costo medio misurato: 0.00050 $ a voce su 2 chiamate; stima per 1: 0.0005 $." in stampato


async def test_senza_chiave_lo_dice_e_non_scrive(db_session, due_voci, senza_chiave, capsys):
    assert await main([]) == 0

    righe = capsys.readouterr().out.strip().splitlines()
    assert righe[0].startswith("sostituti non disponibili (ANTHROPIC_API_KEY")
    assert righe[-1] == "2 voci restano da decidere: rilancia questo comando."
    assert (await db_session.execute(select(IngredientSubstitution.id))).all() == []


async def test_con_l_ai_salva_stampa_e_dice_quanto_resta(db_session, due_voci, con_chiave, monkeypatch, capsys):
    finto = FakeLlm({"esito": "omettere", "sostituti": []})
    monkeypatch.setattr("app.services.substitutions.open_client", lambda: finto)

    assert await main(["--limit", "1"]) == 0

    righe = capsys.readouterr().out.strip().splitlines()
    # a parità di ricette, il primo per nome
    assert righe[0] == "burro (dolce): si può omettere"
    assert "1 voce salvata (0 con sostituti, 1 da omettere, 0 insostituibili), 0 risposte scartate." in righe
    assert "spesa di questo lancio: 0.00004 $ in 1 chiamata." in righe
    assert righe[-1] == "1 voce resta da decidere: rilancia questo comando."
    salvata = (await db_session.execute(select(IngredientSubstitution))).scalars().one()
    assert (salvata.ingredient_id, salvata.context, salvata.verdict, salvata.decided_by) == (
        due_voci["burro"].id, "dolce", "omit", "ai",
    )


async def test_senza_voci_l_ultima_riga_lo_dice(db_session, con_chiave, monkeypatch, capsys):
    monkeypatch.setattr(
        "app.cli.decide_substitutes.SessionLocal", lambda: _SessioneFinta(db_session)
    )
    assert await main([]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == "nessuna voce in attesa."
