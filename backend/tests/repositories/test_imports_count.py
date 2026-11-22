"""Le ricette in attesa che nominano una chiave, contate dal database.

`undo_decision` riconta `occurrences` per il termine annullato: prima caricava tutte le
pagine in attesa col loro `payload` intero per contare una chiave sola, e la fusione
dell'anagrafica lo fa una volta per termine. Il conto SQL deve dire esattamente quel che
dice `count_pending_keys`, la funzione di `sync_terms`: due conti scritti due volte
divergono, e la coda direbbe numeri diversi a seconda di chi l'ha toccata per ultimo.
"""

from app.db.models.recipe_import import GIALLOZAFFERANO, ImportState, RecipeImport
from app.repositories.imports import count_pending_recipes_with_key, pending_pages
from app.services.recipe_import.terms import count_pending_keys


async def test_il_conto_sql_e_quello_di_count_pending_keys(db_session):
    db_session.add_all([
        # la stessa chiave in due righe: la ricetta conta una volta
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/conto-1",
            payload={"title": "Speck due volte", "ingredients": [
                {"key": "k-speck", "name": "Speck"},
                {"key": "k-speck", "name": "Speck a cubetti"},
                {"key": "k-uova", "name": "Uova"},
            ]},
            state=ImportState.PENDING,
        ),
        # righe senza chiave o con la chiave vuota non contano
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/conto-2",
            payload={"title": "Senza chiavi", "ingredients": [
                {"name": "Sale"},
                {"key": "", "name": "Pepe"},
                {"key": "k-uova", "name": "Uova"},
            ]},
            state=ImportState.PENDING,
        ),
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/conto-3",
            payload={"title": "Senza ingredienti"},
            state=ImportState.PENDING,
        ),
        # non in attesa
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/conto-4",
            payload={"title": "Già dentro", "ingredients": [{"key": "k-speck", "name": "Speck"}]},
            state=ImportState.IMPORTED,
        ),
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/conto-5",
            payload={"title": "Scartata", "ingredients": [{"key": "k-speck", "name": "Speck"}]},
            state=ImportState.SKIPPED, skipped_reason="prova",
        ),
        # un'altra fonte
        RecipeImport(
            source="altra-fonte", url="https://altro.invalid/conto-6",
            payload={"title": "Altrove", "ingredients": [{"key": "k-speck", "name": "Speck"}]},
            state=ImportState.PENDING,
        ),
    ])
    await db_session.flush()

    attesi = count_pending_keys(await pending_pages(db_session, GIALLOZAFFERANO)).occurrences
    assert attesi == {"k-speck": 1, "k-uova": 2}
    for key in ["k-speck", "k-uova", "k-nessuno"]:
        assert (
            await count_pending_recipes_with_key(db_session, GIALLOZAFFERANO, key)
        ) == attesi.get(key, 0), key
