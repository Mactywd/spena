"""Le categorie scritte nel frontend devono essere quelle che il backend accetta.

Una categoria inventata nel frontend non è un errore visibile: la creazione
dell'ingrediente tornerebbe 422 su una schermata che fino a quel momento sembrava
funzionare. Nello stile di tests/test_compose.py, che legge i file di build per
difendere una forma.
"""

import re
from pathlib import Path

from app.db.models.ingredient import IngredientCategory
from app.domain.rules import IngredientKind, kind_for_category

REPO_ROOT = Path(__file__).resolve().parents[2]
CATEGORIES_TS = REPO_ROOT / "frontend" / "src" / "domain" / "categories.ts"


def _elenco(nome: str) -> set[str]:
    """Le stringhe di una delle due costanti del file.

    Una regex sola su tutto il file non basta più: con due elenchi direbbe solo
    che l'unione è giusta, e lascerebbe passare «igiene» finito fra gli
    alimentari — cioè proprio il difetto che questo file esiste per impedire.
    """
    contenuto = CATEGORIES_TS.read_text()
    blocco = re.search(rf"export const {nome} = \[(.*?)\]", contenuto, re.DOTALL)
    assert blocco is not None, f"{CATEGORIES_TS}: manca la costante {nome}"
    return set(re.findall(r'"([a-z_]+)"', blocco.group(1)))


def test_il_frontend_offre_esattamente_le_categorie_del_backend():
    tutte = _elenco("FOOD_CATEGORIES") | _elenco("NON_FOOD_CATEGORIES")

    assert tutte == {str(value) for value in IngredientCategory}, (
        f"{CATEGORIES_TS}: l'elenco è {sorted(tutte)}, il backend accetta "
        f"{sorted(str(v) for v in IngredientCategory)}"
    )


def test_le_due_meta_del_frontend_seguono_la_partizione_del_dominio():
    """Non basta che l'unione torni: un reparto nella metà sbagliata verrebbe
    offerto mentre si scrive una ricetta, e il salvataggio lo rifiuterebbe."""
    for nome, atteso in (
        ("FOOD_CATEGORIES", IngredientKind.FOOD),
        ("NON_FOOD_CATEGORIES", IngredientKind.NON_FOOD),
    ):
        for categoria in _elenco(nome):
            assert kind_for_category(categoria) is atteso, f"{nome}: {categoria}"
