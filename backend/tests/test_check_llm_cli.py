"""`python -m app.cli.check_llm`: versione dell'SDK, modello, listino, chiave, e la prova.

Il finto è `FakeLlm`, il client vero col trasporto sostituito: la prova attraversa
davvero `complete_json`, senza rete.
"""

import anthropic
import pytest

from app.cli.check_llm import main
from app.core.config import get_settings
from app.services.llm import LLM_FAILURE_NOTICES, LlmFailureKind
from llm_fakes import FakeLlm, errore_api

CHIAVE = "chiave-finta-per-i-test"


@pytest.fixture
def con_chiave(monkeypatch):
    get_settings.cache_clear()
    monkeypatch.setenv("ANTHROPIC_API_KEY", CHIAVE)
    yield
    get_settings.cache_clear()


def test_senza_chiave(capsys):
    assert main([]) == 1
    out = capsys.readouterr().out
    assert f"anthropic {anthropic.__version__}" in out
    assert "modello: claude-haiku-5-5" in out
    assert "listino: noto" in out
    assert "chiave API: assente" in out


def test_con_la_chiave_non_usa_la_rete(con_chiave, capsys):
    assert main([]) == 0
    visto = capsys.readouterr()
    assert "chiave API: presente" in visto.out
    assert CHIAVE not in visto.out
    assert CHIAVE not in visto.err


def test_un_modello_senza_listino(con_chiave, monkeypatch, capsys):
    monkeypatch.setenv("LLM_MODEL", "claude-sconosciuto")
    get_settings.cache_clear()
    main([])
    out = capsys.readouterr().out
    assert "modello: claude-sconosciuto" in out
    assert "listino: sconosciuto (il costo resterà vuoto)" in out


def test_la_prova_senza_chiave(capsys):
    assert main(["--prova"]) == 1
    assert "prova: fallita — ANTHROPIC_API_KEY non configurata" in capsys.readouterr().out


def test_la_prova(con_chiave, capsys):
    fake = FakeLlm({"esito": "ok"})
    assert main(["--prova"], client=fake) == 0
    out = capsys.readouterr().out
    assert "prova: ok (300 token in ingresso, 20 in uscita, 0.000040 $)" in out.splitlines()
    assert fake.calls == 1


def test_la_prova_fallita(con_chiave, capsys):
    assert main(["--prova"], client=FakeLlm(errore_api(402, "billing_error"))) == 1
    righe = capsys.readouterr().out.splitlines()
    frase = LLM_FAILURE_NOTICES[LlmFailureKind.CREDIT]
    assert any(r.startswith(f"prova: fallita — {frase}") for r in righe)
