"""Le categorie scritte nel frontend devono essere quelle che il backend accetta.

Una categoria inventata nel frontend non è un errore visibile: la creazione
dell'ingrediente tornerebbe 422 su una schermata che fino a quel momento sembrava
funzionare. Nello stile di tests/test_compose.py, che legge i file di build per
difendere una forma.
"""

import re
from pathlib import Path

from app.db.models.ingredient import IngredientCategory

REPO_ROOT = Path(__file__).resolve().parents[2]
CATEGORIES_TS = REPO_ROOT / "frontend" / "src" / "domain" / "categories.ts"


def test_il_frontend_offre_esattamente_le_categorie_del_backend():
    contenuto = CATEGORIES_TS.read_text()
    elencate = set(re.findall(r'"([a-z]+)"', contenuto))

    assert elencate == {str(value) for value in IngredientCategory}, (
        f"{CATEGORIES_TS}: l'elenco è {sorted(elencate)}, il backend accetta "
        f"{sorted(str(v) for v in IngredientCategory)}"
    )
