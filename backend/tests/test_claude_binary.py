"""L'immagine deve contenere il binario di Claude Code, e il binario deve partire."""

import os
import subprocess
from pathlib import Path

import claude_agent_sdk
from claude_agent_sdk._cli_version import __cli_version__


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
