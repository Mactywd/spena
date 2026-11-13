"""Controlla che Claude sia pronto per i Pasti, nell'immagine in cui gira.

    python -m app.cli.check_claude
    python -m app.cli.check_claude --prova

Senza argomenti non usa la rete: stampa la versione dell'SDK, lancia il binario di
Claude Code con `--version` (con un HOME temporaneo) e dice se il token c'è, mai il suo
valore. Esce con 1 se il binario manca o non parte. Con `--prova` fa una sola chiamata
minima a Claude, per Mattia dopo il deploy.
"""

import argparse
import asyncio
import os
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from importlib.metadata import version
from pathlib import Path

import claude_agent_sdk

from app.core.config import get_settings
from app.domain.meal_chat import FailureKind, failure_notice
from app.services.claude.client import SdkClaudeClient, TurnFailed, TurnFinished


async def _prova() -> int:
    """Un giro minimo con il client di produzione: «prova: ok» o «prova: <avviso>»."""
    client = SdkClaudeClient()
    async for event in client.run(
        system_prompt="Rispondi solo: ok", prompt="ok?", tools=[], effort="low", max_turns=1
    ):
        if isinstance(event, TurnFinished):
            print("prova: ok")
            return 0
        if isinstance(event, TurnFailed):
            f = event.failure
            print(f"prova: {failure_notice(f.kind, f.resets_at, datetime.now(UTC))}")
            return 1
    print(f"prova: {failure_notice(FailureKind.INTERRUPTED, None, datetime.now(UTC))}")
    return 1


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli.check_claude")
    parser.add_argument("--prova", action="store_true", help="una chiamata vera a Claude")
    args = parser.parse_args(argv)

    print(f"claude-agent-sdk {version('claude-agent-sdk')}")
    binario = Path(claude_agent_sdk.__file__).parent / "_bundled" / "claude"
    try:
        with tempfile.TemporaryDirectory() as home:
            risultato = subprocess.run(
                [str(binario), "--version"],
                capture_output=True,
                text=True,
                timeout=30,
                env={**os.environ, "HOME": home},
            )
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"binario: {binario} → non parte ({exc})")
        return 1
    if risultato.returncode != 0:
        print(f"binario: {binario} → esce con {risultato.returncode}: {risultato.stderr.strip()}")
        return 1
    print(f"binario: {binario} → {risultato.stdout.strip()}")

    token = bool(get_settings().claude_code_oauth_token)
    print("token: presente" if token else "token: assente")

    if args.prova:
        return asyncio.run(_prova())
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
