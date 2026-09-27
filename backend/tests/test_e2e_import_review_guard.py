"""L'aiutante della prova e2e della revisione non parte fuori dallo stack e2e.

`tests/e2e_import_review.py` scrive e cancella termini, ingredienti e righe di spesa: se
qualcuno lo lanciasse nel container di produzione, `clean` passerebbe per l'annulla vero
sul database vero. Il contrassegno `SPENA_E2E=1` sta solo in `.env.e2e`; qui si prova che
senza, il file esce con errore prima di toccare `app` — cioè prima di aprire una sessione.
Un processo a parte, perché il controllo sta in cima al modulo, al momento dell'import.
"""

import os
import subprocess
import sys
from pathlib import Path

AIUTANTE = Path(__file__).with_name("e2e_import_review.py")


def test_senza_il_contrassegno_e2e_non_parte():
    env = {chiave: valore for chiave, valore in os.environ.items() if chiave != "SPENA_E2E"}

    esito = subprocess.run(
        [sys.executable, str(AIUTANTE), "clean"],
        env=env, capture_output=True, text=True, timeout=30,
    )

    assert esito.returncode != 0
    assert "SPENA_E2E=1" in esito.stderr
    assert esito.stdout == ""
