"""La soglia della zona gialla è una sola, scritta in due linguaggi.

Il backend decide lo stato dalla posizione; il frontend usa lo stesso numero solo
per dipingere le tre zone del cursore. Se i due divergono, il cursore mostra il
giallo dove il server ha già detto verde: nessun test lo vedrebbe, perché ciascuna
metà è coerente con sé stessa. Stesso schema di tests/test_frontend_categories.py.
"""

import re
from pathlib import Path

from app.domain.rules import LOW_MAX_FILL

REPO_ROOT = Path(__file__).resolve().parents[2]
FILL_ZONES_TS = REPO_ROOT / "frontend" / "src" / "features" / "pantry" / "fillZones.ts"


def test_la_soglia_della_zona_gialla_e_la_stessa_nei_due_linguaggi():
    contenuto = FILL_ZONES_TS.read_text()
    trovato = re.search(r"export const LOW_MAX_FILL\s*=\s*(\d+)", contenuto)

    assert trovato is not None, f"{FILL_ZONES_TS}: non dichiara più LOW_MAX_FILL"
    assert int(trovato.group(1)) == LOW_MAX_FILL, (
        f"{FILL_ZONES_TS} dice {trovato.group(1)}, "
        f"app/domain/rules.py dice {LOW_MAX_FILL}"
    )
