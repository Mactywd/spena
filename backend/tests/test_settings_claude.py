"""Le impostazioni di Claude per i Pasti, e il comando che le controlla."""

import pytest

from app.cli import check_claude
from app.core.config import Settings, get_settings

TOKEN_FINTO = "finto-token-per-il-test"


@pytest.fixture(autouse=True)
def _cache_pulita():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def test_il_token_si_legge_da_claude_code_oauth_token(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", TOKEN_FINTO)
    get_settings.cache_clear()
    assert get_settings().claude_code_oauth_token == TOKEN_FINTO


def test_senza_token_e_none(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN", raising=False)
    # `_env_file=None`: un .env di chi lancia i test non deve decidere l'esito
    assert Settings(_env_file=None).claude_code_oauth_token is None


def test_il_modello_di_default_e_opus():
    assert type(get_settings()).model_fields["claude_model"].default == "claude-opus-5-5"


def test_il_token_vuoto_conta_come_assente(monkeypatch, capsys):
    """`.env.example` ha `CLAUDE_CODE_OAUTH_TOKEN=`: la stringa vuota è «non collegato»."""
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", "")
    get_settings.cache_clear()
    assert not get_settings().claude_code_oauth_token
    check_claude.main([])
    assert "token: assente" in capsys.readouterr().out


def test_check_claude_non_stampa_il_token(monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", TOKEN_FINTO)
    get_settings.cache_clear()
    assert check_claude.main([]) == 0
    fuori = capsys.readouterr()
    assert "token: presente" in fuori.out
    assert TOKEN_FINTO not in fuori.out + fuori.err
    assert "claude-agent-sdk" in fuori.out


def test_check_claude_avvisa_della_chiave_api_senza_stamparla(monkeypatch, capsys):
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", TOKEN_FINTO)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "finta-chiave-per-il-test")
    get_settings.cache_clear()
    assert check_claude.main([]) == 0
    fuori = capsys.readouterr()
    assert (
        "attenzione: ANTHROPIC_API_KEY è nell'ambiente; la chat la ignora e usa il token "
        "del piano." in fuori.out
    )
    assert "finta-chiave-per-il-test" not in fuori.out + fuori.err


def test_check_claude_senza_chiave_api_non_avvisa(monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    get_settings.cache_clear()
    check_claude.main([])
    assert "ANTHROPIC_API_KEY" not in capsys.readouterr().out
