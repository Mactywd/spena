"""Il pilota di S4 (spec §4.18–4.19): casi con la risposta nota, chiesti all'AI con gli
stessi servizi del lancio vero, senza scrivere niente sugli ingredienti."""

import json
import re

import httpx
import pytest

from app.db.models.ingredient import IngredientCategory
from app.domain.ciqual import CiqualRow
from app.domain.rules import kind_for_category
from app.repositories.ciqual import upsert_foods
from app.cli.load_ciqual import CANDIDATE_FILES
from app.domain.ciqual import normalize_name
from app.services.ai_spend import Spend
from app.services.ciqual_file import read_ciqual
from app.services.ciqual_match import Searched
from app.services.s4_pilot import (
    MATCH_THRESHOLD,
    PILOT_FILE,
    MatchCase,
    Verdict,
    final_line,
    load_cases,
    match_report,
    passes,
    run_match_pilot,
    score,
    spend_line,
)
from ciqual_veri import ALIMENTI_VERI
from llm_fakes import FakeLlm, user_of

ALIMENTI = [
    CiqualRow("90001", "Tomate, crue", "légumes", {"kcal": 18.0}),
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


def _termini(*righe):
    return {"ingredienti": [{"n": n, "nome": nome, "termini": t} for n, nome, t in righe]}


def _scelte(*righe):
    return {"scelte": [{"n": n, "nome": nome, "codice": c} for n, nome, c in righe]}


def test_i_casi_del_repository_sono_ben_fatti():
    casi = load_cases(PILOT_FILE)

    assert len(casi.matches) == 30
    nomi = [caso.ingredient for caso in casi.matches]
    assert len(nomi) == len(set(nomi))
    for caso in casi.matches:
        assert kind_for_category(IngredientCategory(caso.category)) == "food", caso
        assert caso.expected is not None and caso.expected.startswith("^"), caso


def test_un_espressione_rotta_non_si_carica(tmp_path):
    casi = tmp_path / "casi.json"
    casi.write_text(json.dumps({"abbinamenti": [{"ingrediente": "x", "reparto": "verdura", "atteso": "("}]}))

    with pytest.raises(re.error):
        load_cases(casi)


async def test_il_verdetto_di_ogni_caso(db_session):
    await upsert_foods(db_session, ALIMENTI)
    casi = [
        MatchCase("pomodoro", "verdura", "^tomate, crue"),
        MatchCase("burro", "latticini", "^beurre"),
        MatchCase("riso", "cereali", "^riz"),
        # nessun alimento della tabella corrisponde: da rivedere, e non si chiede
        MatchCase("nduja", "carne", "^nduja"),
    ]
    finto = FakeLlm(
        _termini((1, "pomodoro", ["tomate crue"]), (2, "burro", ["beurre doux"]), (3, "riso", ["riz blanc cru"])),
        _scelte((1, "pomodoro", "90001"), (2, "burro", None), (3, "risotto", "90011")),
    )

    esiti, guasto = await run_match_pilot(db_session, casi, client=finto)

    assert guasto is None
    assert [(e.case.ingredient, e.verdict) for e in esiti] == [
        ("pomodoro", Verdict.RIGHT),
        ("burro", Verdict.WRONG),
        ("riso", Verdict.UNANSWERED),
        ("nduja", Verdict.REVIEW),
    ]
    assert (esiti[0].code, esiti[0].name) == ("90001", "Tomate, crue")
    chiesti = json.loads(user_of(finto.bodies[0]))["ingredienti"]
    assert [voce["nome"] for voce in chiesti] == ["pomodoro", "burro", "riso"]
    assert score(esiti) == (1, 3)


async def test_un_caso_che_aspetta_nessun_alimento_e_giusto_se_l_ai_non_ne_trova(db_session):
    await upsert_foods(db_session, ALIMENTI)
    finto = FakeLlm(_termini((1, "acqua frizzante", ["zzzz qqqq"])))

    esiti, _ = await run_match_pilot(db_session, [MatchCase("acqua frizzante", "bevande", None)], client=finto)

    assert esiti[0].verdict == Verdict.RIGHT


async def test_l_ai_che_non_risponde_lo_dice(db_session):
    await upsert_foods(db_session, ALIMENTI)
    spesa = Spend()

    _, guasto = await run_match_pilot(
        db_session, [MatchCase("pomodoro", "verdura", "^tomate")],
        client=FakeLlm(httpx.ConnectError("rete giù")), spend=spesa,
    )

    assert guasto is not None and "rete giù" in guasto
    assert (spesa.calls, spesa.unpriced) == (1, 1)


def test_il_rapporto_dice_soglia_casi_e_spesa():
    from app.services.s4_pilot import MatchOutcome

    esiti = [
        MatchOutcome(MatchCase("pomodoro", "verdura", "^tomate, crue"), Verdict.RIGHT, "90001", "Tomate, crue"),
        MatchOutcome(MatchCase("burro", "latticini", "^beurre"), Verdict.WRONG, "90013", "Lait entier"),
        MatchOutcome(
            MatchCase("uova", "altro", "^oeuf"), Verdict.WRONG, searched=Searched(("oeuf cru",), 0)
        ),
        MatchOutcome(MatchCase("riso", "cereali", "^riz"), Verdict.UNANSWERED),
        MatchOutcome(MatchCase("nduja", "carne", "^nduja"), Verdict.REVIEW),
    ]

    assert match_report(esiti) == [
        "Abbinamenti: 1 giusti su 4 (25%): non bastano (soglia 90%).",
        "  ✗ «burro»: scelto «Lait entier» (90013); atteso ^beurre",
        "  ✗ «uova»: nessun candidato (le parole oeuf cru e il nome italiano non trovano alimenti); atteso ^oeuf",
        "  – «riso»: le parole di ricerca dell'AI non si sono potute verificare",
        "  ? «nduja»: nessun alimento della tabella corrisponde a ^nduja: il caso va rivisto",
    ]
    assert passes(9, 10, MATCH_THRESHOLD) and not passes(8, 10, MATCH_THRESHOLD)
    assert not passes(0, 0, MATCH_THRESHOLD)
    assert spend_line(Spend(calls=7, cost_usd=0.00312, unpriced=0)) == "Spesa del pilota: 0,0031 $ in 7 chiamate."
    assert spend_line(Spend(calls=1, cost_usd=0.0, unpriced=1)) == (
        "Spesa del pilota: 0,0000 $ in 1 chiamata, 1 senza costo dichiarato."
    )
    assert final_line(True) == "Il pilota passa: si può lanciare l'AI su tutto il catalogo."
    assert final_line(False) == (
        "Il pilota non passa: non lanciare l'AI su tutto il catalogo. "
        "Le righe ✗ e – qui sopra dicono se è mancato il candidato o la scelta."
    )


def test_il_pomodoro_aspetta_il_pomodoro_crudo_generico():
    caso = next(c for c in load_cases().matches if c.ingredient == "pomodoro")

    assert caso.expected == "^tomate (sans precision|ronde), crue"
    for nome in ("Tomate sans précision, crue (aliment moyen)", "Tomate ronde, crue"):
        assert re.search(caso.expected, normalize_name(nome)), nome
    for nome in (
        "Tomate, chair et peau, cuite (aliment moyen)",
        "Tomate cerise, crue",
        "Tomate verte, crue",
    ):
        assert not re.search(caso.expected, normalize_name(nome)), nome


def test_ogni_caso_trova_un_alimento_nella_tabella_vera():
    nomi = [normalize_name(f.name_fr) for f in read_ciqual(CANDIDATE_FILES[0]).foods]

    for caso in load_cases().matches:
        if caso.expected is not None:
            assert any(re.search(caso.expected, nome) for nome in nomi), caso


async def test_il_rapporto_dice_perche(db_session):
    await upsert_foods(db_session, ALIMENTI_VERI)
    casi = [
        MatchCase("riso", "cereali", "^riz.*cru"),
        MatchCase("tonno in scatola", "pesce", "^thon.*appertise"),
        MatchCase("pomodoro", "verdura", "^tomate (sans precision|ronde), crue"),
        MatchCase("patata", "verdura", "^pomme de terre.*crue"),
        MatchCase("salmone", "pesce", "^saumon"),
    ]
    finto = FakeLlm(
        _termini(
            (1, "riso", ["riz"]),
            (2, "tonno in scatola", ["zzzz qqqq"]),
            (3, "pomodori", ["tomate"]),
            (4, "patata", ["pomme de terre"]),
            (5, "salmone", ["saumon"]),
        ),
        _scelte((1, "riso", None), (2, "patata", "4003"), (3, "salmone", "9100")),
    )

    esiti, guasto = await run_match_pilot(db_session, casi, client=finto)

    assert guasto is None
    assert match_report(esiti)[1:] == [
        "  ✗ «riso»: l'AI non ha scelto fra 7 candidati (parole: riz); atteso ^riz.*cru",
        "  ✗ «tonno in scatola»: nessun candidato (le parole zzzz qqqq e il nome italiano non trovano alimenti); atteso ^thon.*appertise",
        "  – «pomodoro»: le parole di ricerca dell'AI non si sono potute verificare",
        "  ✗ «patata»: scelto «Pomme de terre, bouillie/cuite à l'eau» (4003) fra 5 candidati (parole: pomme de terre); atteso ^pomme de terre.*crue",
        "  – «salmone»: la scelta dell'AI fra 7 candidati non si è potuta verificare (parole: saumon)",
    ]
