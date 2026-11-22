"""L'AI abbina gli ingredienti alla tabella CIQUAL (S4, fetta 1), e la verifica delle sue
risposte.

Come per le unità, i termini dell'import e le figure di S12, la parte che conta è la
verifica: una risposta che non si può controllare non si applica, e l'ingrediente resta
da decidere. In più qui l'AI sceglie solo fra candidati veri, trovati nel database con le
sue parole francesi: un codice che non è fra quelli non passa.

Il finto è il client vero con il trasporto sostituito (`llm_fakes.py`): sotto prova c'è
`complete_json` per intero. Le risposte arrivano nell'ordine in cui il servizio chiede:
le parole di un lotto, poi le scelte di quel lotto.
"""

import json

import httpx
import pytest
from sqlalchemy import select

from app.db.models.ingredient import Ingredient
from app.db.models.llm_call import LlmCall
from app.db.models.nutrition import IngredientNutrition
from app.domain.ciqual import CiqualRow
from app.repositories.ciqual import upsert_foods
from app.services.ai_spend import Spend
from app.services.ciqual_match import (
    CHOICE_SYSTEM_PROMPT,
    CiqualRun,
    Matched,
    NameToMatch,
    Searched,
    decide_ciqual,
    match_names,
)
from app.services.ingredient_nutrition import apply_ai_choice, choose_food
from ciqual_veri import ALIMENTI_VERI
from llm_fakes import COSTO_FINTO, FakeLlm, schema_of, system_of, user_of

ALIMENTI = [
    CiqualRow("90001", "Tomate, crue", "légumes", {"kcal": 18.0}),
    CiqualRow("90002", "Tomate, concentré", "légumes", {"kcal": 77.0}),
    CiqualRow("90008", "Beurre doux", "beurres", {"kcal": 745.0}),
    CiqualRow("90011", "Riz blanc, cru", "pâtes, riz et céréales", {"kcal": 354.0}),
]


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


async def _mondo(db_session, *voci: tuple[str, str]) -> dict[str, Ingredient]:
    await upsert_foods(db_session, ALIMENTI)
    creati = {
        nome: Ingredient(name=nome, display_name=nome.capitalize(), category=reparto)
        for nome, reparto in voci
    }
    db_session.add_all(creati.values())
    await db_session.flush()
    return creati


async def _mondo_vero(db_session, *voci: tuple[str, str]) -> dict[str, Ingredient]:
    """Come `_mondo`, ma con gli alimenti veri del 2025: le parità di `word_similarity`
    e il rumore del nome italiano si vedono solo lì."""
    await upsert_foods(db_session, ALIMENTI_VERI)
    creati = {
        nome: Ingredient(name=nome, display_name=nome.capitalize(), category=reparto)
        for nome, reparto in voci
    }
    db_session.add_all(creati.values())
    await db_session.flush()
    return creati


async def _scelta(db_session, ingrediente: Ingredient):
    riga = (
        await db_session.execute(
            select(IngredientNutrition.ciqual_code, IngredientNutrition.decided_by).where(
                IngredientNutrition.ingredient_id == ingrediente.id
            )
        )
    ).first()
    return None if riga is None else tuple(riga)


def _termini(*righe: tuple[int, str, list[str]]) -> dict:
    return {"ingredienti": [{"n": n, "nome": nome, "termini": termini} for n, nome, termini in righe]}


def _scelte(*righe: tuple[int, str, str | None]) -> dict:
    return {"scelte": [{"n": n, "nome": nome, "codice": codice} for n, nome, codice in righe]}


def _domanda(corpo: dict) -> dict:
    return json.loads(user_of(corpo))


async def test_abbina_in_due_passi(db_session):
    voci = await _mondo(db_session, ("pomodoro", "verdura"), ("burro", "latticini"))
    finto = FakeLlm(
        _termini((1, "burro", ["beurre doux"]), (2, "pomodoro", ["tomate crue"])),
        _scelte((1, "burro", "90008"), (2, "pomodoro", "90001")),
    )

    esito = await decide_ciqual(db_session, client=finto)

    assert esito == CiqualRun(matched=2, none=0, refused=0, pending=0, unavailable=None, asked=2)
    assert await _scelta(db_session, voci["burro"]) == ("90008", "ai")
    assert await _scelta(db_session, voci["pomodoro"]) == ("90001", "ai")


async def test_la_scelta_vede_i_candidati_delle_parole_francesi(db_session):
    await _mondo(db_session, ("pomodoro", "verdura"))
    finto = FakeLlm(_termini((1, "pomodoro", ["tomate crue"])), _scelte((1, "pomodoro", "90001")))

    await decide_ciqual(db_session, client=finto)

    assert _domanda(finto.bodies[0]) == {
        "ingredienti": [{"n": 1, "nome": "pomodoro", "reparto": "verdura"}]
    }
    voce = _domanda(finto.bodies[1])["ingredienti"][0]
    assert (voce["n"], voce["nome"]) == (1, "pomodoro")
    assert voce["candidati"][0] == {"codice": "90001", "nome": "Tomate, crue", "gruppo": "légumes"}
    assert "90008" not in {candidato["codice"] for candidato in voce["candidati"]}
    schema = schema_of(finto.bodies[1])
    assert schema["properties"]["scelte"]["items"]["properties"]["codice"] == {
        "anyOf": [{"type": "string"}, {"type": "null"}]
    }


async def test_nessun_alimento_adatto_si_scrive(db_session):
    """Deciso da Mattia il 2026-10-13: l'ingrediente è deciso, e il giro dopo non lo
    richiede."""
    voci = await _mondo(db_session, ("pomodoro", "verdura"))
    finto = FakeLlm(_termini((1, "pomodoro", ["tomate crue"])), _scelte((1, "pomodoro", None)))

    esito = await decide_ciqual(db_session, client=finto)

    assert (esito.none, esito.matched, esito.pending) == (1, 0, 0)
    assert await _scelta(db_session, voci["pomodoro"]) == (None, "ai")


async def test_senza_candidati_si_scrive_nessuno_senza_chiedere_la_scelta(db_session):
    voci = await _mondo(db_session, ("nduja", "carne"))
    finto = FakeLlm(_termini((1, "nduja", ["zzzz qqqq"])))

    esito = await decide_ciqual(db_session, client=finto)

    assert len(finto.bodies) == 1
    assert (esito.none, esito.pending) == (1, 0)
    assert esito.no_candidates == 1
    assert await _scelta(db_session, voci["nduja"]) == (None, "ai")


async def test_un_codice_fuori_dai_candidati_non_si_applica(db_session):
    """L'AI non può inventare un codice, né prenderne uno che esiste ma che non era fra
    i candidati di quell'ingrediente."""
    voci = await _mondo(db_session, ("pomodoro", "verdura"))
    finto = FakeLlm(_termini((1, "pomodoro", ["tomate crue"])), _scelte((1, "pomodoro", "90008")))

    esito = await decide_ciqual(db_session, client=finto)

    assert (esito.refused, esito.matched, esito.pending) == (1, 0, 1)
    assert await _scelta(db_session, voci["pomodoro"]) is None


async def test_un_numero_non_chiesto_un_nome_che_non_torna_e_un_doppione_non_si_applicano(
    db_session,
):
    voci = await _mondo(db_session, ("burro", "latticini"), ("pomodoro", "verdura"))
    finto = FakeLlm(
        _termini(
            (7, "burro", ["beurre doux"]),  # 7 non è stato chiesto
            (2, "burro", ["beurre doux"]),  # il 2 è il pomodoro
            (1, "Burro ", ["beurre doux"]),  # giusto: maiuscole e spazi ai lati non contano
            (1, "burro", ["beurre"]),  # doppione del primo
        ),
        _scelte((1, "burro", "90008")),
    )

    esito = await decide_ciqual(db_session, client=finto)

    assert (esito.refused, esito.matched, esito.pending) == (3, 1, 1)
    assert [voce["nome"] for voce in _domanda(finto.bodies[1])["ingredienti"]] == ["burro"]
    assert await _scelta(db_session, voci["pomodoro"]) is None


async def test_chi_e_gia_deciso_o_non_e_cibo_non_si_chiede(db_session):
    voci = await _mondo(
        db_session,
        ("pomodoro", "verdura"), ("burro", "latticini"), ("riso", "cereali"), ("detersivo", "casa"),
    )
    await choose_food(db_session, voci["burro"].id, "90008")
    await apply_ai_choice(db_session, voci["riso"].id, None)
    finto = FakeLlm(_termini((1, "pomodoro", ["tomate crue"])), _scelte((1, "pomodoro", "90001")))

    await decide_ciqual(db_session, client=finto)

    assert [voce["nome"] for voce in _domanda(finto.bodies[0])["ingredienti"]] == ["pomodoro"]
    di_nuovo = FakeLlm()
    assert await decide_ciqual(db_session, client=di_nuovo) == CiqualRun()
    assert di_nuovo.bodies == []


class _LlmMentreUnaManoCorregge(FakeLlm):
    """Prima di rispondere, qualcuno sceglie l'alimento in Anagrafica."""

    def __init__(self, mano, *payloads: object) -> None:
        super().__init__(*payloads)
        self._mano = mano

    async def answer(self, body: dict) -> object:
        await self._mano()
        return await super().answer(body)


async def test_una_scelta_a_mano_fatta_mentre_l_ai_risponde_non_si_riscrive(db_session):
    voci = await _mondo(db_session, ("pomodoro", "verdura"))

    async def mano():
        await choose_food(db_session, voci["pomodoro"].id, "90002")

    finto = _LlmMentreUnaManoCorregge(
        mano, _termini((1, "pomodoro", ["tomate crue"])), _scelte((1, "pomodoro", "90001"))
    )

    esito = await decide_ciqual(db_session, client=finto)

    assert esito.matched == 0
    assert await _scelta(db_session, voci["pomodoro"]) == ("90002", "human")


async def test_va_a_lotti_e_dopo_ogni_lotto_chiama_after_batch(db_session):
    """Il comando fa commit dopo ogni lotto: un guasto al quinto non butta i primi
    quattro. Ogni lotto numera da 1."""
    voci = await _mondo(
        db_session, ("aglio", "verdura"), ("burro", "latticini"), ("pomodoro", "verdura")
    )
    finto = FakeLlm(
        _termini((1, "aglio", ["ail"]), (2, "burro", ["beurre doux"])),
        _scelte((1, "burro", "90008")),
        _termini((1, "pomodoro", ["tomate crue"])),
        _scelte((1, "pomodoro", "90001")),
    )
    giri: list[int] = []

    async def dopo():
        giri.append(len(finto.bodies))

    esito = await decide_ciqual(db_session, client=finto, batch_size=2, after_batch=dopo)

    assert giri == [2, 4]
    assert (esito.matched, esito.none, esito.pending) == (2, 1, 0)
    assert [(v["n"], v["nome"]) for v in _domanda(finto.bodies[2])["ingredienti"]] == [(1, "pomodoro")]
    assert await _scelta(db_session, voci["aglio"]) == (None, "ai")


async def test_l_ai_che_non_risponde_non_scrive_niente_e_lo_dice(db_session):
    voci = await _mondo(db_session, ("pomodoro", "verdura"))

    esito = await decide_ciqual(db_session, client=FakeLlm(httpx.ConnectError("rete giù")))

    assert (esito.matched, esito.pending, esito.asked) == (0, 1, 1)
    assert esito.unavailable is not None and "rete giù" in esito.unavailable
    assert await _scelta(db_session, voci["pomodoro"]) is None


async def test_un_guasto_sulla_scelta_ferma_il_giro_e_ogni_chiamata_si_registra(db_session):
    await _mondo(db_session, ("pomodoro", "verdura"))
    finto = FakeLlm(_termini((1, "pomodoro", ["tomate crue"])), httpx.ConnectError("rete giù"))

    esito = await decide_ciqual(db_session, client=finto)

    assert esito.unavailable is not None and esito.pending == 1
    righe = (await db_session.execute(select(LlmCall.call_site, LlmCall.ok))).all()
    assert sorted(tuple(riga) for riga in righe) == [("ciqual_match", False), ("ciqual_terms", True)]


async def test_limit_chiede_solo_i_primi_per_nome(db_session):
    await _mondo(db_session, ("pomodoro", "verdura"), ("burro", "latticini"))
    finto = FakeLlm(_termini((1, "burro", ["beurre doux"])), _scelte((1, "burro", "90008")))

    esito = await decide_ciqual(db_session, client=finto, limit=1)

    assert [voce["nome"] for voce in _domanda(finto.bodies[0])["ingredienti"]] == ["burro"]
    assert (esito.asked, esito.matched, esito.pending) == (1, 1, 1)


async def test_match_names_lavora_sui_nomi_e_somma_la_spesa(db_session):
    """Il pilota usa questa, senza ingredienti nel database: lavora sui nomi."""
    await upsert_foods(db_session, ALIMENTI)
    finto = FakeLlm(_termini((1, "pomodoro", ["tomate crue"])), _scelte((1, "pomodoro", "90001")))
    spesa = Spend()

    esito = await match_names(db_session, [NameToMatch("pomodoro", "verdura")], client=finto, spend=spesa)

    assert esito.decided["pomodoro"].code == "90001"
    assert esito.decided["pomodoro"].candidates >= 1
    assert (spesa.calls, spesa.unpriced) == (2, 0)
    assert spesa.cost_usd == pytest.approx(2 * COSTO_FINTO)


def _candidati_chiesti(corpo: dict) -> list[str]:
    return [c["codice"] for c in _domanda(corpo)["ingredienti"][0]["candidati"]]


async def test_il_nome_italiano_non_entra_fra_i_candidati(db_session):
    """Aggiunto sempre, «sale» portava «Eau minérale Salvetat» e «Salers» fra i sali."""
    await _mondo_vero(db_session, ("sale", "condimenti"))
    finto = FakeLlm(_termini((1, "sale", ["sel"])), _scelte((1, "sale", "11083")))

    await decide_ciqual(db_session, client=finto)

    assert _candidati_chiesti(finto.bodies[1]) == ["11083", "11017", "11082", "9104"]


async def test_senza_candidati_dalle_parole_si_cerca_col_nome_italiano(db_session):
    """Il ripiego della decisione 6: CIQUAL scrive in italiano mozzarella, ricotta,
    bresaola; se le parole dell'AI non trovano niente, il nome li trova."""
    await upsert_foods(db_session, ALIMENTI_VERI)
    finto = FakeLlm(
        _termini((1, "mozzarella", ["zzzz qqqq"])), _scelte((1, "mozzarella", "19590"))
    )

    esito = await match_names(db_session, [NameToMatch("mozzarella", "latticini")], client=finto)

    assert esito.decided["mozzarella"] == Matched(code="19590", candidates=1)
    assert _candidati_chiesti(finto.bodies[1]) == ["19590"]
    assert esito.searched["mozzarella"] == Searched(
        terms=("zzzz qqqq",), candidates=1, by_italian_name=True
    )


async def test_match_names_dice_cosa_ha_cercato(db_session):
    """Per ogni nome con le parole verificate, le parole e quanti candidati ha visto la
    scelta; un nome con le parole rifiutate non c'è."""
    await upsert_foods(db_session, ALIMENTI_VERI)
    finto = FakeLlm(
        _termini((1, "riso", ["riz"]), (2, "mieli", ["miel"])),
        _scelte((1, "riso", None)),
    )

    esito = await match_names(
        db_session,
        [NameToMatch("riso", "cereali"), NameToMatch("miele", "dolci")],
        client=finto,
    )

    assert esito.searched["riso"] == Searched(("riz",), 7, False)
    assert esito.decided["riso"] == Matched(None, 7)
    assert "miele" not in esito.searched
    assert "miele" not in esito.decided


async def test_un_candidato_mancato_si_conta_a_parte(db_session):
    """Dentro «senza un alimento adatto», quelli senza nemmeno un candidato: è la
    ricerca che ha mancato, non l'AI che ha detto no."""
    voci = await _mondo_vero(db_session, ("nduja", "carne"), ("riso", "cereali"))
    finto = FakeLlm(
        _termini((1, "nduja", ["zzzz qqqq"]), (2, "riso", ["riz"])),
        _scelte((1, "riso", None)),
    )

    esito = await decide_ciqual(db_session, client=finto)

    assert (esito.none, esito.no_candidates, esito.matched) == (2, 1, 0)
    assert await _scelta(db_session, voci["nduja"]) == (None, "ai")
    assert await _scelta(db_session, voci["riso"]) == (None, "ai")


PELLE_E_OSSA = (
    "- Carne e pesce: senza pelle né ossa, se il nome non dice altro (per esempio "
    '"petto di pollo" è "filet sans peau", non "viande et peau").'
)


async def test_la_scelta_dice_senza_pelle_ne_ossa(db_session):
    """Il pilota del 2026-10-20: per il petto di pollo l'AI ha scelto «Poulet blanc,
    viande et peau crues»."""
    await _mondo(db_session, ("pomodoro", "verdura"))
    finto = FakeLlm(_termini((1, "pomodoro", ["tomate crue"])), _scelte((1, "pomodoro", "90001")))

    await decide_ciqual(db_session, client=finto)

    assert PELLE_E_OSSA in CHOICE_SYSTEM_PROMPT
    assert PELLE_E_OSSA in system_of(finto.bodies[1])
