"""I sostituti decisi dall'AI (R5), e la verifica della sua risposta.

Come per i termini dell'import, la parte che conta è la verifica: una risposta che non
si può controllare non si applica (decisione 2 di Mattia), e la voce resta da chiedere.
L'AI scrive solo dove non c'è una risposta (decisione 4).

Il finto sostituisce `httpx.AsyncClient`, non il client di OpenRouter: sotto prova c'è
`complete_json` per intero. Risponde guardando la domanda e non l'ordine d'arrivo,
perché le chiamate di un lotto partono insieme (lo stesso motivo di `ScriptedLlm`).
"""

import json as _json
import uuid

import httpx
import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.llm_call import LlmCall
from app.db.models.recipe import RecipeSource
from app.domain.substitutions import SubstitutionContext, SubstitutionVerdict
from app.repositories import substitutions as repo
from app.repositories.recipes import create_recipe
from app.repositories.substitutions import Answer
from app.services.substitutions import (
    SUBSTITUTE_SCHEMA,
    PairOutcome,
    Rejected,
    SubstitutionRun,
    decide_pair,
    decide_substitutions,
    verify_answer,
)
from llm_fakes import COSTO_FINTO, USAGE_FINTO

SALATO = SubstitutionContext.SAVORY
DOLCE = SubstitutionContext.SWEET


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


class SostitutiFinti:
    """Una risposta per (ingrediente, ricetta), scelta guardando la domanda.

    `prima`, se c'è, gira prima di rispondere: è il modo di far scrivere qualcuno mentre
    il modello «pensa». Un'`Exception` fra le risposte si solleva invece di rispondere.
    """

    def __init__(self, risposte: dict[tuple[str, str], object], prima=None) -> None:
        self._risposte = risposte
        self._prima = prima
        self.bodies: list[dict] = []

    async def post(self, url, json, headers):  # noqa: A002
        self.bodies.append(json)
        if self._prima is not None:
            await self._prima()
        domanda = _json.loads(json["messages"][1]["content"])
        payload = self._risposte[(domanda["ingrediente"], domanda["ricetta"])]
        if isinstance(payload, Exception):
            raise payload
        corpo = {
            "id": "gen-finta",
            "model": "google/gemma-4-26b-a4b-it",
            "choices": [{"message": {"content": _json.dumps(payload)}}],
            "usage": dict(USAGE_FINTO),
        }
        return httpx.Response(200, json=corpo, request=httpx.Request("POST", url))

    async def aclose(self):
        return None

    def domande(self) -> list[tuple[str, str]]:
        return sorted(
            (domanda["ingrediente"], domanda["ricetta"])
            for domanda in (_json.loads(corpo["messages"][1]["content"]) for corpo in self.bodies)
        )


def sostituti(*righe: tuple[str, str]) -> dict:
    return {"esito": "sostituti", "sostituti": [{"nome": nome, "nota": nota} for nome, nota in righe]}


OMETTERE = {"esito": "omettere", "sostituti": []}
INSOSTITUIBILE = {"esito": "insostituibile", "sostituti": []}


@pytest_asyncio.fixture
async def cucina(db_session):
    """Quattro voci: pollo salato (2 ricette), burro dolce, burro salato, zucchero dolce."""

    def voce(nome: str, reparto: str) -> Ingredient:
        return Ingredient(name=nome, display_name=nome.capitalize(), category=reparto)

    voci = {
        "pollo": voce("pollo", IngredientCategory.CARNE),
        "tacchino": voce("tacchino", IngredientCategory.CARNE),
        "coniglio": voce("coniglio", IngredientCategory.CARNE),
        "burro": voce("burro", IngredientCategory.LATTICINI),
        "margarina": voce("margarina", IngredientCategory.CONDIMENTI),
        "zucchero": voce("zucchero", IngredientCategory.DOLCI),
        "detersivo": voce("detersivo", IngredientCategory.CASA),
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    for titolo, categoria, nomi in (
        ("Pollo al burro", "Secondi piatti", ("pollo", "burro")),
        ("Pollo arrosto", "Secondi piatti", ("pollo",)),
        ("Biscotti", "Dolci e Desserts", ("burro", "zucchero")),
    ):
        await create_recipe(
            db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
            source=RecipeSource.MANUAL, source_ref=None,
            ingredients=[(voci[nome].id, "primary", None, None) for nome in nomi],
            embedding=None, category=categoria,
        )
    return voci


TUTTE = {
    ("pollo", "salata"): sostituti(("tacchino", "metà dose"), ("coniglio", "")),
    ("burro", "dolce"): sostituti(("margarina", "")),
    ("burro", "salata"): OMETTERE,
    ("zucchero", "dolce"): INSOSTITUIBILE,
}


async def _spese(db_session) -> list[bool]:
    righe = await db_session.execute(
        select(LlmCall.ok).where(LlmCall.call_site == "ingredient_substitutes")
    )
    return sorted(righe.scalars().all())


# --- la verifica, pura ------------------------------------------------------------------

P, T, C, B = (uuid.uuid4() for _ in range(4))
CIBO = {"burro": B, "coniglio": C, "pollo": P, "tacchino": T}


def test_una_risposta_giusta_si_applica_con_le_note_pulite():
    risposta = verify_answer(sostituti(("Tacchino ", " metà  dose "), ("coniglio", "")), P, CIBO)
    assert risposta == Answer(SubstitutionVerdict.SUBSTITUTES, ((T, "metà dose"), (C, None)))


def test_maiuscole_e_spazi_non_contano_ma_un_doppione_si():
    """Review Focus 4: «Tacchino » è tacchino, e «TACCHINO» dopo «tacchino» è un doppione."""
    assert isinstance(verify_answer(sostituti(("tacchino", ""), ("TACCHINO ", "")), P, CIBO), Rejected)


@pytest.mark.parametrize(
    "risposta",
    [
        {"esito": "forse", "sostituti": []},
        {"esito": "sostituti", "sostituti": "tacchino"},
        {"esito": "omettere", "sostituti": [{"nome": "tacchino", "nota": ""}]},
        {"esito": "sostituti", "sostituti": []},
        sostituti(("tacchino", ""), ("coniglio", ""), ("burro", ""), ("pollo", "")),
        {"esito": "sostituti", "sostituti": ["tacchino"]},
        sostituti(("seitan", "")),        # fuori anagrafica
        sostituti(("detersivo", "")),     # non alimentare: non è fra il cibo
        sostituti(("pollo", "")),         # l'ingrediente stesso
        sostituti(("tacchino", "x" * 61)),
    ],
)
def test_una_risposta_che_non_si_verifica_si_scarta_intera(risposta):
    assert isinstance(verify_answer(risposta, P, CIBO), Rejected)


def test_omettere_e_insostituibile_si_applicano():
    assert verify_answer(OMETTERE, P, CIBO) == Answer(SubstitutionVerdict.OMIT)
    assert verify_answer(INSOSTITUIBILE, P, CIBO) == Answer(SubstitutionVerdict.IRREPLACEABLE)


# --- il giro del comando ---------------------------------------------------------------


async def test_applica_le_risposte_verificate_e_registra_la_spesa(db_session, cucina):
    righe: list[str] = []

    esito = await decide_substitutions(db_session, client=SostitutiFinti(TUTTE), report=righe.append)

    assert (esito.substitutes, esito.omit, esito.irreplaceable, esito.rejected) == (2, 1, 1, 0)
    assert (esito.calls, esito.pending, esito.unavailable) == (4, 0, None)
    assert esito.cost_usd == pytest.approx(4 * COSTO_FINTO)
    pollo = await repo.general_row(db_session, cucina["pollo"].id, SALATO)
    assert pollo.decided_by == "ai"
    assert [(o.substitute.name, o.note) for o in repo.visible_options(pollo)] == [
        ("tacchino", "metà dose"), ("coniglio", None),
    ]
    assert await _spese(db_session) == [True, True, True, True]
    assert "pollo (salato): tacchino (metà dose), coniglio" in righe
    assert "burro (salato): si può omettere" in righe
    assert "zucchero (dolce): insostituibile" in righe


async def test_una_risposta_che_non_si_verifica_lascia_la_voce_scoperta(db_session, cucina):
    risposte = {**TUTTE, ("pollo", "salata"): sostituti(("seitan", ""))}
    righe: list[str] = []

    esito = await decide_substitutions(db_session, client=SostitutiFinti(risposte), report=righe.append)

    assert (esito.rejected, esito.pending) == (1, 1)
    assert await repo.general_row(db_session, cucina["pollo"].id, SALATO) is None
    assert "pollo (salato): scartata («seitan» non è un alimento dell'anagrafica)" in righe


async def test_chiede_solo_le_voci_scoperte(db_session, cucina):
    await repo.write_general(db_session, cucina["pollo"].id, SALATO, Answer(SubstitutionVerdict.OMIT))
    await repo.store_ai_answer(
        db_session, cucina["burro"].id, DOLCE, Answer(SubstitutionVerdict.IRREPLACEABLE)
    )
    finto = SostitutiFinti(TUTTE)

    await decide_substitutions(db_session, client=finto)

    assert finto.domande() == [("burro", "salata"), ("zucchero", "dolce")]
    di_nuovo = SostitutiFinti({})
    assert await decide_substitutions(db_session, client=di_nuovo) == SubstitutionRun()
    assert di_nuovo.bodies == []


async def test_una_correzione_a_mano_fatta_mentre_l_ai_risponde_non_si_riscrive(db_session, cucina):
    """Review Focus 3: il comando gira minuti, e Mattia corregge in Anagrafica."""

    async def mano():
        await repo.write_general(
            db_session, cucina["pollo"].id, SALATO, Answer(SubstitutionVerdict.IRREPLACEABLE)
        )

    righe: list[str] = []
    esito = await decide_substitutions(
        db_session, client=SostitutiFinti(TUTTE, prima=mano), limit=1, report=righe.append
    )

    assert esito.substitutes == 0
    riga = await repo.general_row(db_session, cucina["pollo"].id, SALATO)
    assert (riga.verdict, riga.decided_by) == ("irreplaceable", "human")
    assert righe == ["pollo (salato): già decisa, lasciata com'era"]


async def test_va_a_lotti_e_dopo_ogni_lotto_chiama_after_batch(db_session, cucina):
    finto = SostitutiFinti(TUTTE)
    giri: list[int] = []

    async def dopo():
        giri.append(len(finto.bodies))

    esito = await decide_substitutions(db_session, client=finto, batch_size=2, after_batch=dopo)

    assert giri == [2, 4]
    assert esito.pending == 0


async def test_limit_chiede_le_voci_piu_usate(db_session, cucina):
    finto = SostitutiFinti(TUTTE)

    esito = await decide_substitutions(db_session, client=finto, limit=2)

    # pollo salato (2 ricette) e, a parità, il primo per nome: burro dolce
    assert finto.domande() == [("burro", "dolce"), ("pollo", "salata")]
    assert esito.pending == 2


async def test_il_primo_lotto_con_un_guasto_ferma_il_giro(db_session, cucina):
    risposte = {**TUTTE, ("pollo", "salata"): httpx.ConnectError("rete giù")}
    finto = SostitutiFinti(risposte)

    esito = await decide_substitutions(db_session, client=finto, batch_size=2)

    assert len(finto.bodies) == 2  # il secondo lotto non parte
    assert esito.unavailable is not None and "rete giù" in esito.unavailable
    assert (esito.substitutes, esito.calls, esito.pending) == (1, 2, 3)
    assert await _spese(db_session) == [False, True]


async def test_senza_chiave_non_chiama_e_non_registra(db_session, cucina, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    finto = SostitutiFinti(TUTTE)

    esito = await decide_substitutions(db_session, client=finto)

    assert finto.bodies == []
    assert esito.unavailable is not None and "OPENROUTER_API_KEY" in esito.unavailable
    assert esito.pending == 4
    assert await _spese(db_session) == []


async def test_la_domanda_porta_l_ingrediente_il_contesto_e_il_cibo_dell_anagrafica(db_session, cucina):
    finto = SostitutiFinti(TUTTE)

    await decide_substitutions(db_session, client=finto, limit=1)

    corpo = finto.bodies[0]
    assert _json.loads(corpo["messages"][1]["content"]) == {
        "ingrediente": "pollo",
        "ricetta": "salata",
        # solo il cibo, per nome, senza l'ingrediente stesso
        "anagrafica": ["burro", "coniglio", "margarina", "tacchino", "zucchero"],
    }
    assert "insostituibile" in corpo["messages"][0]["content"]
    assert corpo["response_format"]["json_schema"]["schema"] == SUBSTITUTE_SCHEMA


# --- la voce sul momento ---------------------------------------------------------------


async def test_una_voce_sul_momento_si_salva(db_session, cucina):
    finto = SostitutiFinti({("pollo", "salata"): OMETTERE})

    esito = await decide_pair(db_session, cucina["pollo"].id, SALATO, client=finto)

    assert esito == PairOutcome(stored=True, failed=False)
    riga = await repo.general_row(db_session, cucina["pollo"].id, SALATO)
    assert (riga.verdict, riga.decided_by) == ("omit", "ai")
    assert await _spese(db_session) == [True]


async def test_una_voce_che_ha_gia_una_risposta_non_chiama(db_session, cucina):
    await repo.write_general(db_session, cucina["pollo"].id, SALATO, Answer(SubstitutionVerdict.OMIT))
    finto = SostitutiFinti({})

    assert await decide_pair(db_session, cucina["pollo"].id, SALATO, client=finto) == PairOutcome()
    assert finto.bodies == []


async def test_l_ai_giu_sul_momento_lo_dice_e_registra_la_chiamata(db_session, cucina):
    finto = SostitutiFinti({("pollo", "salata"): httpx.ConnectError("rete giù")})

    assert await decide_pair(db_session, cucina["pollo"].id, SALATO, client=finto) == PairOutcome(failed=True)
    assert await repo.general_row(db_session, cucina["pollo"].id, SALATO) is None
    assert await _spese(db_session) == [False]


async def test_una_risposta_scartata_sul_momento_lo_dice(db_session, cucina):
    finto = SostitutiFinti({("pollo", "salata"): sostituti(("pollo", ""))})

    assert await decide_pair(db_session, cucina["pollo"].id, SALATO, client=finto) == PairOutcome(failed=True)
    assert await repo.general_row(db_session, cucina["pollo"].id, SALATO) is None
    assert await _spese(db_session) == [True]  # pagata anche se inutile


async def test_senza_chiave_sul_momento_non_chiama(db_session, cucina, monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    finto = SostitutiFinti({})

    assert await decide_pair(db_session, cucina["pollo"].id, SALATO, client=finto) == PairOutcome(failed=True)
    assert finto.bodies == [] and await _spese(db_session) == []
