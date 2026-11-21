"""L'immagine deve contenere il binario di Claude Code, e il binario deve partire."""

import dataclasses
import os
import subprocess
from pathlib import Path

import claude_agent_sdk
from claude_agent_sdk import ResultError
from claude_agent_sdk._cli_version import __cli_version__

from app.core.config import get_settings
from app.services.claude.client import SdkClaudeClient, TurnFailed, build_options


def test_il_binario_di_claude_code_c_e_e_parte(tmp_path):
    binario = Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"
    assert binario.exists(), f"{binario}: il pacchetto non porta il binario"
    assert os.access(binario, os.X_OK), f"{binario}: non è eseguibile"
    # `--version` non autentica: nessuna rete, nessun token
    risultato = subprocess.run(
        [str(binario), "--version"],
        capture_output=True,
        text=True,
        timeout=30,
        env={**os.environ, "HOME": str(tmp_path)},
    )
    assert risultato.returncode == 0, risultato.stderr
    assert __cli_version__ in risultato.stdout


def _ambiente_senza_rete(tmp_path, monkeypatch):
    """Il binario vero contro una porta chiusa, con una casa tutta sua."""
    for nome in list(os.environ):
        if nome.startswith(("ANTHROPIC_", "CLAUDE_CODE_")):
            monkeypatch.delenv(nome)
    casa = tmp_path / "home"
    casa.mkdir(exist_ok=True)
    monkeypatch.setenv("HOME", str(casa))
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(casa / ".claude"))
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("CLAUDE_CODE_DISABLE_NONESSENTIAL_TRAFFIC", "1")
    monkeypatch.setenv("CLAUDE_CODE_MAX_RETRIES", "0")
    monkeypatch.setenv("API_TIMEOUT_MS", "3000")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "chiave-finta-per-i-test")
    monkeypatch.setenv("CLAUDE_WORKDIR", str(tmp_path / "lavoro"))
    get_settings.cache_clear()
    return casa / ".claude" / "projects"


_GIRO = {
    "system_prompt": "Rispondi solo: ok",
    "prompt": "ok?",
    "tools": [],
    "effort": "low",
    "max_turns": 1,
}


async def test_il_client_vero_non_lascia_trascrizioni(tmp_path, monkeypatch):
    progetti = _ambiente_senza_rete(tmp_path, monkeypatch)
    eventi = [e async for e in SdkClaudeClient().run(**_GIRO)]
    assert isinstance(eventi[-1], TurnFailed), eventi  # la porta è chiusa
    assert list(progetti.rglob("*.jsonl")) == []


async def _giro_con(options):
    try:
        async for _ in claude_agent_sdk.query(prompt=_GIRO["prompt"], options=options):
            pass
    except ResultError:
        pass  # la porta è chiusa: è il risultato previsto


def _opzioni_senza_la_cronologia(**cambi):
    """Le opzioni di produzione senza `CLAUDE_CODE_SKIP_PROMPT_HISTORY`: sul binario 2.1.321
    ferma da sola anche la trascrizione, e nasconderebbe quello che il flag fa o non fa."""
    options = build_options(**{k: v for k, v in _GIRO.items() if k != "prompt"})
    env = {k: v for k, v in options.env.items() if k != "CLAUDE_CODE_SKIP_PROMPT_HISTORY"}
    return dataclasses.replace(options, env=env, **cambi)


async def test_il_flag_da_solo_basta_a_non_lasciare_la_trascrizione(tmp_path, monkeypatch):
    progetti = _ambiente_senza_rete(tmp_path, monkeypatch)
    await _giro_con(_opzioni_senza_la_cronologia())
    assert list(progetti.rglob("*.jsonl")) == []


async def test_senza_il_flag_il_binario_scriverebbe_la_trascrizione(tmp_path, monkeypatch):
    """Il controllo dei due test sopra: senza questo, passerebbero anche su un binario che
    non scrive mai niente."""
    progetti = _ambiente_senza_rete(tmp_path, monkeypatch)
    await _giro_con(_opzioni_senza_la_cronologia(extra_args={}))
    assert len(list(progetti.rglob("*.jsonl"))) == 1
