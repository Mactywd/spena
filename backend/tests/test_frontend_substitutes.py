"""I limiti dei sostituti copiati nel frontend devono essere quelli del dominio (R5).

Il frontend li usa per non offrire il quarto selettore e per tagliare la nota; il server
li controlla comunque. Due copie si scollano, e la prima a scollarsi sarebbe un modulo
che lascia scrivere una nota che il salvataggio poi rifiuta. Nello stile di
`test_frontend_categories.py`.
"""

import re
from pathlib import Path

from app.domain.substitutions import SUBSTITUTE_NOTE_MAX, SUBSTITUTES_MAX

TYPES_TS = (
    Path(__file__).resolve().parents[2] / "frontend" / "src" / "features" / "substitutes" / "types.ts"
)


def _costante(nome: str) -> int:
    trovata = re.search(rf"export const {nome} = (\d+);", TYPES_TS.read_text())
    assert trovata is not None, f"{TYPES_TS}: manca la costante {nome}"
    return int(trovata.group(1))


def test_i_limiti_del_frontend_sono_quelli_del_dominio():
    assert _costante("SUBSTITUTES_MAX") == SUBSTITUTES_MAX
    assert _costante("SUBSTITUTE_NOTE_MAX") == SUBSTITUTE_NOTE_MAX
