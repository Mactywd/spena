import pytest_asyncio

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, TermDecision
from app.repositories.imports import (
    counts,
    pending_terms,
    store_page,
    terms_by_key,
    waiting_titles,
)
from app.services.recipe_import.terms import sync_terms


def payload(title: str, ingredients: list[tuple[str, str, str]]) -> dict:
    """`ingredients` è una lista di (key, name, quantity_text)."""
    return {
        "title": title,
        "description": None,
        "instructions": "Cuoci.",
        "servings": 2,
        "category": "Primi piatti",
        "image_url": None,
        "prep_minutes": 5,
        "cook_minutes": 10,
        "ingredients": [
            {"key": key, "name": name, "quantity_text": quantity}
            for key, name, quantity in ingredients
        ],
        "nutrition": None,
    }


@pytest_asyncio.fixture
async def anagrafica(db_session):
    pasta = Ingredient(
        name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    pasta.aliases.append(IngredientAlias(alias="rigatoni", source="import"))
    db_session.add(pasta)
    db_session.add(
        Ingredient(name="speck", display_name="Speck", category=IngredientCategory.CARNE)
    )
    await db_session.flush()


async def test_ogni_termine_distinto_diventa_una_riga(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Uno.html",
        payload=payload("Uno", [
            ("ricette-con-i-Rigatoni", "Rigatoni", "320 g"),
            ("ricette-con-lo-Speck", "Speck", "80 g"),
        ]),
    )

    synced = await sync_terms(db_session)

    assert synced.created == 2


async def test_un_termine_che_coincide_con_un_nome_si_decide_da_se(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Uno.html",
        payload=payload("Uno", [("ricette-con-lo-Speck", "Speck", "80 g")]),
    )

    synced = await sync_terms(db_session)

    assert synced.auto_decided == 1
    term = (await pending_terms(db_session, GIALLOZAFFERANO, limit=10))
    assert term == [], "un termine certo non deve finire nella coda"


async def test_un_termine_che_coincide_con_un_alias_si_decide_da_se(db_session, anagrafica):
    """`Rigatoni` è un alias di `pasta`: l'uguaglianza è un fatto, non una proposta."""
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Uno.html",
        payload=payload("Uno", [("ricette-con-i-Rigatoni", "Rigatoni", "320 g")]),
    )

    await sync_terms(db_session)

    term = (await terms_by_key(db_session, GIALLOZAFFERANO))["ricette-con-i-Rigatoni"]
    assert term.decision == TermDecision.MAPPED
    assert term.decided_by == "auto"


async def test_un_termine_sconosciuto_aspetta(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Uno.html",
        payload=payload("Uno", [("ricette-con-la-Bottarga", "Bottarga", "20 g")]),
    )

    synced = await sync_terms(db_session)

    assert synced.pending == 1
    coda = await pending_terms(db_session, GIALLOZAFFERANO, limit=10)
    assert [t.display_name for t in coda] == ["Bottarga"]


async def test_la_coda_e_ordinata_per_quante_ricette_sblocca(db_session, anagrafica):
    for numero in range(3):
        await store_page(
            db_session, source=GIALLOZAFFERANO,
            url=f"https://ricette.giallozafferano.it/Tre-{numero}.html",
            payload=payload(f"Tre {numero}", [("ricette-con-la-Bottarga", "Bottarga", "20 g")]),
        )
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Uno.html",
        payload=payload("Uno", [("ricette-con-il-Nasello", "Nasello", "200 g")]),
    )

    await sync_terms(db_session)

    coda = await pending_terms(db_session, GIALLOZAFFERANO, limit=10)
    assert [(t.display_name, t.occurrences) for t in coda] == [("Bottarga", 3), ("Nasello", 1)]


async def test_il_conteggio_si_ricalcola_e_non_si_accumula(db_session, anagrafica):
    """Due sincronizzazioni non raddoppiano niente: è la ragione per cui
    `occurrences` si ricalcola invece di essere incrementato."""
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Uno.html",
        payload=payload("Uno", [("ricette-con-la-Bottarga", "Bottarga", "20 g")]),
    )

    await sync_terms(db_session)
    seconda = await sync_terms(db_session)

    assert seconda.created == 0
    coda = await pending_terms(db_session, GIALLOZAFFERANO, limit=10)
    assert coda[0].occurrences == 1


async def test_lo_stesso_termine_due_volte_nella_stessa_ricetta_conta_una(db_session, anagrafica):
    """La frolla e la crema vogliono entrambe lo zucchero a velo, ma la ricetta in
    attesa è una: `occurrences` conta ricette, non righe."""
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Torta.html",
        payload=payload("Torta", [
            ("ricette-con-Zucchero-a-velo", "Zucchero a velo", "150 g"),
            ("ricette-con-Zucchero-a-velo", "Zucchero a velo", "q.b."),
        ]),
    )

    await sync_terms(db_session)

    coda = await pending_terms(db_session, GIALLOZAFFERANO, limit=10)
    assert [(t.display_name, t.occurrences) for t in coda] == [("Zucchero a velo", 1)]


async def test_i_titoli_in_attesa_aiutano_a_decidere(db_session, anagrafica):
    """«Scorza di limone» si giudica diversamente in una torta e in un arrosto."""
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Torta.html",
        payload=payload("Torta della nonna", [("ricette-con-Scorza", "Scorza di limone", "½")]),
    )
    await sync_terms(db_session)

    titoli = await waiting_titles(db_session, GIALLOZAFFERANO, ["ricette-con-Scorza"])

    assert titoli["ricette-con-Scorza"] == ["Torta della nonna"]


async def test_i_conteggi_dicono_dove_sta_l_import(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO,
        url="https://ricette.giallozafferano.it/Uno.html",
        payload=payload("Uno", [("ricette-con-la-Bottarga", "Bottarga", "20 g")]),
    )
    await sync_terms(db_session)

    numeri = await counts(db_session, GIALLOZAFFERANO)

    assert numeri.fetched == 1
    assert numeri.pending_recipes == 1
    assert numeri.imported == 0
    assert numeri.skipped == 0
    assert numeri.pending_terms == 1
