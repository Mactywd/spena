"""Le figure che la griglia dell'Anagrafica offre devono essere quelle che il backend
accetta, nello stesso ordine (S12).

Come `test_frontend_categories.py`: una figura offerta dal frontend e sconosciuta al
backend tornerebbe un 409 su una scelta che sembrava valida; una che il backend conosce
e la griglia no non si potrebbe mai scegliere a mano. L'ordine conta anche lui: è quello
delle famiglie della griglia, e la copia deve dire la stessa cosa dell'originale. Il
confronto è carattere per carattere: una copia che perdesse il selettore di variante di
🌶️ sembrerebbe giusta a occhio.
"""

import re
from pathlib import Path

from app.domain.emoji import INGREDIENT_EMOJI

REPO_ROOT = Path(__file__).resolve().parents[2]
EMOJI_TS = REPO_ROOT / "frontend" / "src" / "domain" / "emoji.ts"


def test_il_frontend_offre_le_figure_del_backend_nello_stesso_ordine():
    contenuto = EMOJI_TS.read_text(encoding="utf-8")
    blocco = re.search(r"export const INGREDIENT_EMOJI = \[(.*?)\] as const", contenuto, re.DOTALL)
    assert blocco is not None, f"{EMOJI_TS}: manca la costante INGREDIENT_EMOJI"
    assert re.findall(r'"([^"]+)"', blocco.group(1)) == list(INGREDIENT_EMOJI)
