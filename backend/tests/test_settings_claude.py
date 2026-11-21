"""Le impostazioni di Claude per i Pasti, e il comando che le controlla."""

import pytest

from app.cli import check_claude
from app.core.config import get_settings
from app.services.claude.client import claude_configured

CHIAVE_FINTA = "chiave-finta-per-i-test"
TOKEN_FINTO = "finto-token-per-il-test"


@pytest.fixture(autouse=True)
def _cache_pulita():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_la_chiave_si_legge_da_anthropic_api_key(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", CHIAVE_FINTA)
    get_settings.cache_clear()
    assert get_settings().anthropic_api_key == CHIAVE_FINTA


def test_senza_chiave_e_none():
    # il fixture automatico di conftest.py toglie la chiave dall'ambiente
    assert get_settings().anthropic_api_key is None


def test_la_suite_parte_senza_chiave():
    """Qualunque cosa abbia l'ambiente della shell, i test partono senza chiave."""
    assert get_settings().anthropic_api_key is None
    assert not claude_configured()


def test_il_modello_di_default_e_opus():
    assert type(get_settings()).model_fields["claude_model"].default == "claude-opus-5-5"


def test_la_chiave_vuota_conta_come_assente(monkeypatch, capsys):
    """`.env.example` ha `ANTHROPIC_API_KEY=`: la stringa vuota è «non collegato»."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    assert not claude_configured()
    check_claude.main([])
    assert "chiave API: assente" in capsys.readouterr().out


def test_check_claude_non_stampa_la_chiave(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", CHIAVE_FINTA)
    get_settings.cache_clear()
    assert check_claude.main([]) == 0
    fuori = capsys.readouterr()
    assert "chiave API: presente" in fuori.out
    assert CHIAVE_FINTA not in fuori.out + fuori.err
    assert "claude-agent-sdk" in fuori.out


def test_check_claude_avvisa_del_token_senza_stamparlo(monkeypatch, capsys):
    monkeypatch.setenv("ANTHROPIC_API_KEY", CHIAVE_FINTA)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", TOKEN_FINTO)
    get_settings.cache_clear()
    assert check_claude.main([]) == 0
    fuori = capsys.readouterr()
    assert (
        "attenzione: CLAUDE_CODE_OAUTH_TOKEN è nell'ambiente; la chat lo ignora e usa la "
        "chiave API." in fuori.out
    )
    assert TOKEN_FINTO not in fuori.out + fuori.err


def test_check_claude_senza_token_non_avvisa(monkeypatch, capsys):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    get_settings.cache_clear()
    check_claude.main([])
    assert "CLAUDE_CODE_OAUTH_TOKEN" not in capsys.readouterr().out
