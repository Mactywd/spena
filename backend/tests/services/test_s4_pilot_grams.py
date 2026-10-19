"""Il pilota dei pesi (S4, fetta 2): 20 coppie con l'intervallo noto, chieste con lo
stesso `ask_grams` del lancio vero, senza scrivere niente."""

import json
from decimal import Decimal

import pytest

from app.services.s4_pilot import (
    PILOT_FILE,
    GramsCase,
    GramsOutcome,
    MatchCase,
    MatchOutcome,
    Verdict,
    grams_report,
    load_cases,
    pilot_passed,
    run_grams_pilot,
)
from llm_fakes import FakeLlm


@pytest.fixture(autouse=True)
def chiave(monkeypatch):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    yield
    get_settings.cache_clear()


def test_i_pesi_del_repository_sono_ben_fatti():
    casi = load_cases(PILOT_FILE)

    assert len(casi.grams) == 20
    assert len(casi.matches) == 30
    for caso in casi.grams:
        assert caso.ingredient and Decimal("0") < caso.low < caso.high, caso
        assert caso.unit is None or caso.unit.strip(), caso


async def test_il_verdetto_dei_pesi(db_session):
    casi = [
        GramsCase("aglio", "spicchio", Decimal("3"), Decimal("7")),
        GramsCase("uova", None, Decimal("45"), Decimal("60")),
        GramsCase("sale", "pizzico", Decimal("0.2"), Decimal("1.5")),
        GramsCase("burro", "noce", Decimal("5"), Decimal("15")),
    ]
    finto = FakeLlm(
        {
            "pesi": [
                {"n": 1, "ingrediente": "aglio", "unita": "spicchio", "grammi": 5},
                {"n": 2, "ingrediente": "uova", "unita": "pezzo", "grammi": 70},
                {"n": 3, "ingrediente": "sale", "unita": "pizzico", "grammi": None},
                {"n": 4, "ingrediente": "burro", "unita": "cucchiaio", "grammi": 10},
            ]
        }
    )

    esiti, guasto = await run_grams_pilot(db_session, casi, client=finto)

    assert guasto is None
    assert [(e.case.ingredient, e.verdict, e.grams) for e in esiti] == [
        ("aglio", Verdict.RIGHT, Decimal("5.00")),
        ("uova", Verdict.WRONG, Decimal("70.00")),
        ("sale", Verdict.WRONG, None),
        ("burro", Verdict.UNANSWERED, None),
    ]
    coppie = json.loads(finto.bodies[0]["messages"][1]["content"])["coppie"]
    assert coppie[1] == {"n": 2, "ingrediente": "uova", "unita": "pezzo", "esempio": None}


def test_il_rapporto_dei_pesi():
    esiti = [
        GramsOutcome(GramsCase("aglio", "spicchio", Decimal("3"), Decimal("7")), Verdict.RIGHT, Decimal("5")),
        GramsOutcome(GramsCase("uova", None, Decimal("45"), Decimal("60")), Verdict.WRONG, Decimal("70.00")),
        GramsOutcome(GramsCase("sale", "pizzico", Decimal("0.2"), Decimal("1.5")), Verdict.WRONG),
        GramsOutcome(GramsCase("burro", "noce", Decimal("5"), Decimal("15")), Verdict.UNANSWERED),
    ]

    assert grams_report(esiti) == [
        "Pesi: 1 nell'intervallo su 4 (25%): non bastano (soglia 80%).",
        "  ✗ «uova», 1 pezzo: 70 g; atteso 45–60 g",
        "  ✗ «sale», 1 pizzico: nessun peso; atteso 0,2–1,5 g",
        "  – «burro», 1 noce: nessuna risposta verificabile dall'AI",
    ]


def test_il_pilota_passa_solo_se_passano_tutti_e_due():
    giusto = MatchOutcome(MatchCase("pomodoro", "verdura", "^tomate"), Verdict.RIGHT)
    sbagliato = MatchOutcome(MatchCase("burro", "latticini", "^beurre"), Verdict.WRONG)
    peso_giusto = GramsOutcome(GramsCase("aglio", "spicchio", Decimal("3"), Decimal("7")), Verdict.RIGHT)
    peso_sbagliato = GramsOutcome(GramsCase("uova", None, Decimal("45"), Decimal("60")), Verdict.WRONG)

    assert pilot_passed([giusto], [peso_giusto])
    assert pilot_passed([giusto], [])
    assert not pilot_passed([giusto, sbagliato], [peso_giusto])
    assert not pilot_passed([giusto], [peso_giusto, peso_sbagliato])
