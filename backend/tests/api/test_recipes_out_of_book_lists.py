"""Le ricette dei pasti stanno fuori dal ricettario (spec 2026-11-12 §4.2): ogni elenco e
ogni ricerca le esclude dentro la query che porta il limite, come le archiviate (sesta
lezione di CLAUDE.md). Gemello di `test_recipes_archived_lists.py`, con le ricette fuori
dal ricettario al posto delle eliminate. «Salvarla nel ricettario» qui è `in_book = True`
più un flush: la rotta arriva più avanti nel piano.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select, text

from app.cli.reindex import reindex
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.recipe import EMBEDDING_DIM, Recipe, RecipeSource
from app.domain.rules import PantryStatus
from app.repositories.recipes import create_recipe
from app.services.recipe_search import CANDIDATE_POOL


async def _ricetta(
    db_session, titolo, righe=(), *, embedding=None, category=None, fuori=False
) -> Recipe:
    return await create_recipe(
        db_session, title=titolo, description=None, instructions="Cuoci.", servings=2,
        source=RecipeSource.MANUAL, source_ref=None, ingredients=list(righe),
        embedding=embedding, category=category, in_book=not fuori,
    )


async def _salva_nel_ricettario(db_session, ricetta: Recipe) -> None:
    ricetta.in_book = True
    await db_session.flush()


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
    manca al più una cosa, e in «Primi piatti». Una è di un pasto."""
    pasta = Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    db_session.add(pasta)
    await db_session.flush()
    db_session.add(PantryItem(ingredient_id=pasta.id, status=PantryStatus.AVAILABLE))
    riga = [(pasta.id, "primary", "320 g", None)]
    await _ricetta(db_session, "Pasta in bianco", riga, category="Primi piatti")
    del_pasto = await _ricetta(
        db_session, "Pasta al burro", riga, category="Primi piatti", fuori=True
    )
    await db_session.flush()
    return pasta, del_pasto


FILTRI = {
    "senza filtri": lambda pasta: "",
    "per ingrediente": lambda pasta: f"ingredient_id={pasta.id}",
    "mancanti al più uno": lambda pasta: "max_missing=1",
    "categoria": lambda pasta: "category=Primi%20piatti",
}


@pytest.mark.parametrize("filtro", list(FILTRI))
async def test_lo_sfoglio_esclude_le_ricette_dei_pasti_e_le_ritrova_salvate(
    logged_client, db_session, ricettario, filtro
):
    pasta, del_pasto = ricettario
    query = FILTRI[filtro](pasta)
    assert await _titoli(logged_client, query) == {"Pasta in bianco"}
    risposta = await logged_client.get(f"/api/v1/recipes/search?{query}")
    assert risposta.headers["X-Total-Count"] == "1"

    await _salva_nel_ricettario(db_session, del_pasto)
    assert await _titoli(logged_client, query) == {"Pasta in bianco", "Pasta al burro"}
    risposta = await logged_client.get(f"/api/v1/recipes/search?{query}")
    assert risposta.headers["X-Total-Count"] == "2"


async def test_lo_sfoglio_esclude_le_ricette_dei_pasti_prima_della_pagina(
    logged_client, db_session
):
    for numero in range(3):
        await _ricetta(db_session, f"A fuori {numero}", fuori=True)
    await _ricetta(db_session, "Z viva")
    await db_session.flush()

    # a parità di mancanti l'ordine è per titolo: le tre fuori starebbero davanti
    assert await _titoli(logged_client, "limit=1") == {"Z viva"}


async def test_i_cucinabili_non_contano_le_ricette_dei_pasti(logged_client, db_session):
    uova = Ingredient(name="uova", display_name="Uova", category=IngredientCategory.LATTICINI)
    db_session.add(uova)
    await db_session.flush()
    db_session.add(PantryItem(ingredient_id=uova.id, status=PantryStatus.AVAILABLE))
    await _ricetta(db_session, "Uova del pasto", [(uova.id, "primary", "2", None)], fuori=True)
    await db_session.flush()

    assert await _titoli(logged_client, "max_missing=0") == set()
    risposta = await logged_client.get("/api/v1/recipes/search?max_missing=0")
    assert risposta.headers["X-Total-Count"] == "0"


async def test_la_ricerca_testuale_esclude_le_ricette_dei_pasti(logged_client, db_session):
    await _ricetta(db_session, "Frittata di spinaci", fuori=True)
    await _ricetta(db_session, "Frittata di zucchine")
    await db_session.flush()

    assert await _titoli(logged_client, "q=frittata") == {"Frittata di zucchine"}


async def test_la_ricerca_testuale_le_esclude_prima_della_piscina(logged_client, db_session):
    for numero in range(CANDIDATE_POOL + 5):
        await _ricetta(db_session, f"Zuppa zuppa zuppa {numero}", fuori=True)
    await _ricetta(db_session, "Zuppa di pane")
    await db_session.flush()

    assert await _titoli(logged_client, "q=zuppa") == {"Zuppa di pane"}


async def test_la_ricerca_semantica_esclude_le_ricette_dei_pasti(
    logged_client, db_session, query_nel_punto_zero
):
    await _ricetta(db_session, "Ricetta vicina", embedding=_vettore_a_distanza(0.10))
    await _ricetta(
        db_session, "Ricetta vicinissima", embedding=_vettore_a_distanza(0.05), fuori=True
    )
    await db_session.flush()

    assert await _titoli(logged_client, "q=xyzzy") == {"Ricetta vicina"}


async def test_la_ricerca_semantica_le_esclude_prima_della_piscina(
    logged_client, db_session, query_nel_punto_zero
):
    for numero in range(CANDIDATE_POOL + 5):
        # vettori distinti: HNSW deduplica gli identici (vedi il gemello delle archiviate)
        await _ricetta(
            db_session, f"Vicinissima {numero}",
            embedding=_vettore_a_distanza(0.05 + numero * 1e-4), fuori=True,
        )
    await _ricetta(db_session, "Ricetta vicina", embedding=_vettore_a_distanza(0.10))
    await db_session.flush()
    # come in produzione: indice HNSW e non scansione sequenziale
    await db_session.execute(text("SET LOCAL enable_seqscan = off"))

    assert await _titoli(logged_client, "q=xyzzy") == {"Ricetta vicina"}


async def test_la_ricerca_semantica_non_si_accende_per_una_ricetta_di_un_pasto(
    logged_client, db_session, query_nel_punto_zero
):
    await _ricetta(
        db_session, "Solo del pasto", embedding=_vettore_a_distanza(0.10), fuori=True
    )
    await db_session.flush()

    risposta = await logged_client.get("/api/v1/recipes/search-mode")
    assert risposta.json() == {"semantic": False}


async def test_le_categorie_non_contano_le_ricette_dei_pasti(logged_client, db_session):
    await _ricetta(db_session, "Pasta e fagioli", category="Primi piatti")
    await _ricetta(db_session, "Frittata", category="Frittate", fuori=True)
    await db_session.flush()

    risposta = await logged_client.get("/api/v1/recipes/categories")
    assert risposta.json() == ["Primi piatti"]


async def test_reindex_scrive_il_vettore_anche_delle_ricette_dei_pasti(db_session):
    ricetta = await _ricetta(db_session, "Senza vettore", fuori=True)
    await db_session.flush()

    assert await reindex(db_session) == 1
    await db_session.refresh(ricetta)
    assert ricetta.embedding is not None
