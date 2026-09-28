"""Tutto quel che elenca ricette esclude le archiviate (R10 §5, §8.4).

Un test per voce, perché una voce dimenticata è il modo più facile di mostrare una
ricetta eliminata (spec §9). Ognuno elimina e ripristina passando dalla rotta vera.

Tre test in più mettono l'esclusione davanti al limite: più ricette archiviate che
posti nella piscina dei candidati (o nella pagina), tutte davanti alla viva
nell'ordine. Un filtro applicato dopo il `.limit()` perderebbe la viva: la sesta
lezione di CLAUDE.md.

Lo sfoglio non ha un filtro per costo (R9 ha deciso di non averne): i filtri provati
sono quelli che `_browse` ha davvero (deviazione 1 del piano).
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text

from app.cli.reindex import reindex
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.recipe import EMBEDDING_DIM, Recipe, RecipeSource
from app.domain.rules import PantryStatus
from app.repositories.recipes import create_recipe
from app.services.recipe_search import CANDIDATE_POOL


async def _ricetta(db_session, titolo, righe=(), *, embedding=None, category=None) -> Recipe:
    return await create_recipe(
        db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
        source=RecipeSource.MANUAL, source_ref=None, ingredients=list(righe),
        embedding=embedding, category=category,
    )


def _archiviata_da_sempre(ricetta: Recipe) -> None:
    """Per i mondi di cento ricette la data si scrive direttamente: cento PATCH non
    proverebbero niente di più. Le prove per voce passano dalla rotta."""
    ricetta.archived_at = datetime.now(UTC)


async def _archivia(client, ricetta, archived=True):
    risposta = await client.patch(f"/api/v1/recipes/{ricetta.id}", json={"archived": archived})
    assert risposta.status_code == 200, risposta.text


async def _titoli(client, query="") -> set[str]:
    risposta = await client.get(f"/api/v1/recipes/search?{query}")
    assert risposta.status_code == 200, risposta.text
    return {r["title"] for r in risposta.json()}


def _vettore_a_distanza(distanza: float) -> list[float]:
    """Unitario, nel piano dei primi due assi, a `distanza` coseno dal punto 0: la
    distanza che il database calcolerà si verifica a mente. È la stessa costruzione di
    `tests/api/test_recipes.py`, ricopiata perché i file di test non si importano fra
    loro."""
    coseno = 1.0 - distanza
    vettore = [0.0] * EMBEDDING_DIM
    vettore[0] = coseno
    vettore[1] = (1.0 - coseno**2) ** 0.5
    return vettore


@pytest.fixture
def query_nel_punto_zero(monkeypatch):
    from app.services import recipe_search

    async def embed(_: str) -> list[float]:
        return _vettore_a_distanza(0.0)

    monkeypatch.setattr(recipe_search, "_embed_query", embed)


@pytest_asyncio.fixture
async def ricettario(db_session):
    """Due ricette che ogni filtro dello sfoglio trova: cucinabili, con la pasta, a cui
    manca al più una cosa, e in «Primi piatti». Una delle due si eliminerà."""
    pasta = Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    db_session.add(pasta)
    await db_session.flush()
    db_session.add(PantryItem(ingredient_id=pasta.id, status=PantryStatus.AVAILABLE))
    riga = [(pasta.id, "primary", "320 g", None)]
    await _ricetta(db_session, "Pasta in bianco", riga, category="Primi piatti")
    eliminata = await _ricetta(db_session, "Pasta al burro", riga, category="Primi piatti")
    await db_session.flush()
    return pasta, eliminata


FILTRI = {
    "senza filtri": lambda pasta: "",
    "cucinabili": lambda pasta: "max_missing=0",
    "per ingrediente": lambda pasta: f"ingredient_id={pasta.id}",
    "mancanti al più uno": lambda pasta: "max_missing=1",
    "categoria": lambda pasta: "category=Primi%20piatti",
}


@pytest.mark.parametrize("filtro", list(FILTRI))
async def test_lo_sfoglio_esclude_le_eliminate_e_le_ritrova_ripristinate(
    logged_client, ricettario, filtro
):
    pasta, eliminata = ricettario
    query = FILTRI[filtro](pasta)
    entrambe = {"Pasta in bianco", "Pasta al burro"}
    assert await _titoli(logged_client, query) == entrambe

    await _archivia(logged_client, eliminata)
    assert await _titoli(logged_client, query) == {"Pasta in bianco"}

    await _archivia(logged_client, eliminata, archived=False)
    assert await _titoli(logged_client, query) == entrambe


async def test_lo_sfoglio_esclude_le_eliminate_prima_della_pagina(logged_client, db_session):
    for numero in range(35):
        _archiviata_da_sempre(await _ricetta(db_session, f"Anguria {numero:02d}"))
    await _ricetta(db_session, "Zucca al forno")
    await db_session.flush()

    # la pagina è di 30 e l'ordine, a parità di mancanti, è per titolo: le 35
    # archiviate starebbero tutte davanti alla viva
    assert await _titoli(logged_client, "limit=30") == {"Zucca al forno"}


async def test_la_ricerca_testuale_esclude_le_eliminate(logged_client, db_session):
    await _ricetta(db_session, "Zuppa di pane")
    eliminata = await _ricetta(db_session, "Zuppa di ceci")
    await db_session.flush()
    entrambe = {"Zuppa di pane", "Zuppa di ceci"}
    # senza vettori: le trova solo la metà testuale
    assert await _titoli(logged_client, "q=zuppa") == entrambe

    await _archivia(logged_client, eliminata)
    assert await _titoli(logged_client, "q=zuppa") == {"Zuppa di pane"}

    await _archivia(logged_client, eliminata, archived=False)
    assert await _titoli(logged_client, "q=zuppa") == entrambe


async def test_la_ricerca_testuale_esclude_le_eliminate_prima_della_piscina(
    logged_client, db_session
):
    for numero in range(CANDIDATE_POOL + 5):
        _archiviata_da_sempre(await _ricetta(db_session, f"Zuppa zuppa zuppa {numero}"))
    await _ricetta(db_session, "Zuppa di pane")
    await db_session.flush()

    # le archiviate dicono «zuppa» tre volte, e `ts_rank` le metterebbe tutte davanti
    assert await _titoli(logged_client, "q=zuppa") == {"Zuppa di pane"}


async def test_la_ricerca_semantica_esclude_le_eliminate(
    logged_client, db_session, query_nel_punto_zero
):
    await _ricetta(db_session, "Ricetta vicina", embedding=_vettore_a_distanza(0.10))
    eliminata = await _ricetta(db_session, "Ricetta vicinissima", embedding=_vettore_a_distanza(0.05))
    await db_session.flush()
    entrambe = {"Ricetta vicina", "Ricetta vicinissima"}
    # «xyzzy» non compare in nessun titolo: le trova solo la metà semantica
    assert await _titoli(logged_client, "q=xyzzy") == entrambe

    await _archivia(logged_client, eliminata)
    assert await _titoli(logged_client, "q=xyzzy") == {"Ricetta vicina"}

    await _archivia(logged_client, eliminata, archived=False)
    assert await _titoli(logged_client, "q=xyzzy") == entrambe


async def test_la_ricerca_semantica_esclude_le_eliminate_prima_della_piscina(
    logged_client, db_session, query_nel_punto_zero
):
    for numero in range(CANDIDATE_POOL + 5):
        _archiviata_da_sempre(
            await _ricetta(db_session, f"Vicinissima {numero}", embedding=_vettore_a_distanza(0.05))
        )
    await _ricetta(db_session, "Ricetta vicina", embedding=_vettore_a_distanza(0.10))
    await db_session.flush()
    # Con 106 righe il pianificatore sceglierebbe la scansione sequenziale, che è
    # esatta; in produzione, con migliaia di vettori, sceglie l'indice HNSW, che è
    # approssimato e con un filtro vede solo i primi `ef_search` vicini (40). Si segue
    # il piano di produzione: senza la scansione iterativa, i 40 vicini sono tutti
    # eliminati e la viva non arriva (deviazione 14).
    await db_session.execute(text("SET LOCAL enable_seqscan = off"))

    assert await _titoli(logged_client, "q=xyzzy") == {"Ricetta vicina"}


async def test_le_categorie_non_contano_le_eliminate(logged_client, db_session):
    await _ricetta(db_session, "Pasta e fagioli", category="Primi piatti")
    dolce = await _ricetta(db_session, "Tiramisù", category="Dolci")
    await db_session.flush()

    async def categorie():
        return (await logged_client.get("/api/v1/recipes/categories")).json()

    assert await categorie() == ["Dolci", "Primi piatti"]
    await _archivia(logged_client, dolce)
    assert await categorie() == ["Primi piatti"]
    await _archivia(logged_client, dolce, archived=False)
    assert await categorie() == ["Dolci", "Primi piatti"]


async def test_reindex_salta_le_eliminate_e_le_ritrova_ripristinate(logged_client, db_session):
    ricetta = await _ricetta(db_session, "Senza vettore")
    await db_session.flush()

    await _archivia(logged_client, ricetta)
    assert await reindex(db_session) == 0

    await _archivia(logged_client, ricetta, archived=False)
    assert await reindex(db_session) == 1
