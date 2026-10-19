"""L'aiutante delle prove e2e delle spese non parte fuori dallo stack e2e.

`tests/e2e_spese.py` scrive e cancella in `llm_calls`: lanciato nel container di
produzione, `clean` toglierebbe righe vere se un giorno una avesse quel segno, e `seed`
gonfierebbe le spese vere. Il contrassegno `SPENA_E2E=1` sta solo in `.env.e2e`; qui si
prova che senza, il file esce con errore prima di toccare `app`. Un processo a parte,
perché il controllo sta in cima al modulo (come `test_e2e_ricettario_guard.py`).
"""

import os
import subprocess
import sys
from pathlib import Path

AIUTANTE = Path(__file__).with_name("e2e_spese.py")


def test_senza_il_contrassegno_e2e_non_parte():
    env = {chiave: valore for chiave, valore in os.environ.items() if chiave != "SPENA_E2E"}

    esito = subprocess.run(
        [sys.executable, str(AIUTANTE), "clean"],
        env=env, capture_output=True, text=True, timeout=30,
    )

    assert esito.returncode != 0
    assert "SPENA_E2E=1" in esito.stderr
    assert esito.stdout == ""
