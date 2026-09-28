"""Le rotte dell'anagrafica sull'ingrediente (S9 §4): la scheda, e i 409 con i loro
ostacoli accanto.

Il mondo di prova si salva con `commit`: una rotta che rifiuta fa `rollback`, e con
`join_transaction_mode="create_savepoint"` quel rollback porterebbe via quel che il
test avesse solo scritto con `flush`. Si restituiscono id e non oggetti, per lo stesso
motivo: dopo un rollback gli oggetti sono scaduti.
"""

import uuid
from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.recipe import Recipe, RecipeSource
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus
from app.domain.rules import PantryStatus
from app.repositories.ingredients import add_alias, remember_alias
from app.repositories.recipes import create_recipe

BASE = "/api/v1/ingredients"


@pytest_asyncio.fixture
async def anagrafica(db_session):
    def voce(name: str, display: str, category: str) -> Ingredient:
        return Ingredient(name=name, display_name=display, category=category)

    pomodoro = voce("pomodoro", "Pomodoro", IngredientCategory.VERDURA)
    pomodori = voce("pomodori", "Pomodori", IngredientCategory.VERDURA)
    burro = voce("burro", "Burro", IngredientCategory.LATTICINI)
    detersivo = voce("detersivo", "Detersivo", IngredientCategory.CASA)
    db_session.add_all([pomodoro, pomodori, burro, detersivo])
    await db_session.flush()

    manuale = await add_alias(db_session, pomodori.id, "pomodorini", source="manual")
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-pelati", display_name="Pomodori pelati",
        occurrences=1, decision=TermDecision.MAPPED, ingredient_id=pomodori.id,
        decided_by="ai", decided_at=datetime.now(UTC),
    )
    db_session.add(term)
    await db_session.flush()
    await remember_alias(db_session, pomodori.id, "Pomodori pelati")
    risotto = await create_recipe(
        db_session, title="Risotto al burro", description=None, instructions="Manteca.",
        servings=2, source=RecipeSource.AI, source_ref=None,
        ingredients=[(burro.id, "primary", "50 g", None)], embedding=None,
    )
    db_session.add(PantryItem(ingredient_id=pomodori.id, status=PantryStatus.AVAILABLE))
    db_session.add(ShoppingListItem(
        raw_text="pomodori", ingredient_id=pomodori.id,
        status=ShoppingStatus.PENDING, reason=ShoppingReason.MANUAL,
    ))
    db_session.add(Product(
        ingredient_id=pomodori.id, name="Pelati Cirio", brand="Cirio",
        barcode="8004567890120", source="custom",
    ))
    await db_session.flush()
    pelati = (
        await db_session.execute(
            select(IngredientAlias.id).where(IngredientAlias.alias == "pomodori pelati")
        )
    ).scalar_one()
    ids = {
        "pomodoro": pomodoro.id, "pomodori": pomodori.id, "burro": burro.id,
        "detersivo": detersivo.id, "manuale": manuale.id, "pelati": pelati,
        "term": term.id, "risotto": risotto.id,
    }
    await db_session.commit()
    return ids


def _alias_per_nome(corpo: dict) -> dict[str, dict]:
    """Per nome e non per posizione: l'ordine dipende dalla collazione del database."""
    return {alias["alias"]: alias for alias in corpo["aliases"]}


async def test_la_scheda_dice_alias_prodotti_e_uso(logged_client, anagrafica):
    risposta = await logged_client.get(f"{BASE}/{anagrafica['pomodori']}")

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert (corpo["name"], corpo["category"], corpo["kind"]) == ("pomodori", "verdura", "food")
    alias = _alias_per_nome(corpo)
    assert alias["pomodori pelati"]["source"] == "import"
    assert alias["pomodori pelati"]["decided_in_queue"] is True
    assert alias["pomodorini"]["decided_in_queue"] is False
    # il termine della decisione, perché «Deciso nella coda» porti a lui e non alla coda
    assert alias["pomodori pelati"]["term_id"] == str(anagrafica["term"])
    assert alias["pomodorini"]["term_id"] is None
    assert [(p["name"], p["brand"], p["barcode"]) for p in corpo["products"]] == [
        ("Pelati Cirio", "Cirio", "8004567890120")
    ]
    assert corpo["usage"] == {"recipes": 0, "pantry": 1, "shopping": 1}


async def test_un_ingrediente_che_non_c_e_e_un_404(logged_client):
    assert (await logged_client.get(f"{BASE}/{uuid.uuid4()}")).status_code == 404


async def test_un_nome_gia_preso_e_un_409_con_l_omonimo(logged_client, anagrafica):
    risposta = await logged_client.patch(f"{BASE}/{anagrafica['pomodori']}", json={"name": "Pomodoro"})

    assert risposta.status_code == 409
    corpo = risposta.json()
    assert corpo["code"] == "name_taken"
    assert "già in anagrafica" in corpo["detail"]
    assert corpo["existing"]["id"] == str(anagrafica["pomodoro"])
    assert corpo["existing"]["display_name"] == "Pomodoro"


async def test_rinominare_a_un_alias_altrui_e_un_409_con_chi_lo_tiene(logged_client, anagrafica):
    """«Pomodorini» è alias di «pomodori» nel mondo di prova: rinominare «burro» lì è
    un 409 con «pomodori» come ostacolo, come un nome preso — «Uniscili» funziona senza
    che lo schermo debba distinguere i due casi."""
    risposta = await logged_client.patch(f"{BASE}/{anagrafica['burro']}", json={"name": "Pomodorini"})

    assert risposta.status_code == 409
    corpo = risposta.json()
    assert corpo["code"] == "name_taken"
    assert corpo["existing"]["id"] == str(anagrafica["pomodori"])


async def test_rinominare_scrive_i_nomi_e_tiene_il_vecchio_come_alias(logged_client, anagrafica):
    risposta = await logged_client.patch(
        f"{BASE}/{anagrafica['pomodori']}", json={"name": "Pomodori rossi"}
    )

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert (corpo["name"], corpo["display_name"]) == ("pomodori rossi", "Pomodori rossi")
    assert _alias_per_nome(corpo)["pomodori"]["source"] == "manual"


async def test_il_non_alimentare_con_ricette_e_un_409_che_le_elenca(logged_client, anagrafica):
    risposta = await logged_client.patch(f"{BASE}/{anagrafica['burro']}", json={"category": "casa"})

    assert risposta.status_code == 409
    corpo = risposta.json()
    assert corpo["code"] == "non_food_in_recipes"
    assert corpo["recipe_count"] == 1
    assert corpo["recipes"] == [
        {"id": str(anagrafica["risotto"]), "title": "Risotto al burro", "archived": False}
    ]
    assert corpo["pending_import_count"] == 0
    assert (corpo["pending_terms"], corpo["pending_term_count"]) == ([], 0)
    assert (await logged_client.get(f"{BASE}/{anagrafica['burro']}")).json()["category"] == "latticini"


async def test_il_rifiuto_segna_le_ricette_eliminate(logged_client, db_session, anagrafica):
    """R10: una ricetta eliminata usa ancora il burro, e il rifiuto la conta — ripristinata
    non deve tornare con una riga non alimentare. La segna, perché chi non la vede più nel
    ricettario capisca da dove viene il blocco (deviazione 6 del piano)."""
    risotto = await db_session.get(Recipe, anagrafica["risotto"])
    risotto.archived_at = datetime.now(UTC)
    await db_session.flush()

    risposta = await logged_client.patch(f"{BASE}/{anagrafica['burro']}", json={"category": "casa"})

    assert risposta.status_code == 409
    assert risposta.json()["recipes"] == [
        {"id": str(anagrafica["risotto"]), "title": "Risotto al burro", "archived": True}
    ]


async def test_il_non_alimentare_con_pagine_in_attesa_e_un_409_che_le_conta(
    logged_client, db_session, anagrafica
):
    """«Pomodori pelati» è deciso su `pomodori` e sta su una pagina che aspetta un altro
    termine: nessuna ricetta la usa ancora, ma una arriverà. Il 409 lo dice con
    `pending_import_count`, accanto a `recipe_count` che resta 0."""
    db_session.add_all([
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="k-basilico", display_name="Basilico",
            occurrences=1, decision=TermDecision.PENDING,
        ),
        RecipeImport(
            source=GIALLOZAFFERANO, url="https://esempio.invalid/sugo", state=ImportState.PENDING,
            payload={"title": "Sugo", "ingredients": [{"key": "k-pelati"}, {"key": "k-basilico"}]},
        ),
    ])
    await db_session.commit()

    risposta = await logged_client.patch(
        f"{BASE}/{anagrafica['pomodori']}", json={"category": "casa"}
    )

    assert risposta.status_code == 409
    corpo = risposta.json()
    assert corpo["code"] == "non_food_in_recipes"
    assert (corpo["recipe_count"], corpo["recipes"], corpo["pending_import_count"]) == (0, [], 1)
    assert corpo["pending_terms"] == [
        {"id": str(anagrafica["term"]), "display_name": "Pomodori pelati"}
    ]
    assert corpo["pending_term_count"] == 1
    assert "1 ricetta dell'import ancora in attesa" in corpo["detail"]


async def test_cambiare_reparto_riflette_categoria_e_kind(logged_client, anagrafica):
    """Un cambio di reparto che passa (`pomodoro` non è in nessuna ricetta) si vede
    nella risposta su entrambi i campi: `category` è quel che si è scritto, `kind` è
    quel che `kind_for_category` ne deriva — qui un reparto alimentare che diventa
    non alimentare, cambio visibile su entrambi insieme."""
    risposta = await logged_client.patch(
        f"{BASE}/{anagrafica['pomodoro']}", json={"category": "casa"}
    )

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert (corpo["category"], corpo["kind"]) == ("casa", "non_food")


async def test_un_corpo_vuoto_e_un_400(logged_client, anagrafica):
    risposta = await logged_client.patch(f"{BASE}/{anagrafica['pomodori']}", json={})
    assert risposta.status_code == 400


async def test_un_nome_esplicitamente_nullo_e_un_422(logged_client, anagrafica):
    """F17: `name` non può mai essere nullo. Un `null` scritto a mano è un errore di
    validazione dello schema, non un «nessun cambiamento» silenzioso con 200."""
    risposta = await logged_client.patch(f"{BASE}/{anagrafica['pomodori']}", json={"name": None})
    assert risposta.status_code == 422


async def test_un_reparto_esplicitamente_nullo_e_un_422(logged_client, anagrafica):
    """Come sopra, per `category`: anche il reparto non può mai essere nullo in
    colonna (F17)."""
    risposta = await logged_client.patch(
        f"{BASE}/{anagrafica['pomodori']}", json={"category": None}
    )
    assert risposta.status_code == 422


async def test_l_anteprima_non_cambia_niente_e_la_fusione_dice_gli_stessi_numeri(
    logged_client, anagrafica
):
    url = f"{BASE}/{anagrafica['pomodori']}/merge"

    prova = await logged_client.post(url, json={"into": str(anagrafica["pomodoro"]), "dry_run": True})
    assert prova.status_code == 200
    assert prova.json()["dry_run"] is True
    assert (await logged_client.get(f"{BASE}/{anagrafica['pomodori']}")).status_code == 200

    vera = await logged_client.post(url, json={"into": str(anagrafica["pomodoro"])})
    assert vera.status_code == 200
    assert vera.json() == {**prova.json(), "dry_run": False}
    assert vera.json()["pantry_items"] == 1
    assert vera.json()["winner_id"] == str(anagrafica["pomodoro"])
    assert (await logged_client.get(f"{BASE}/{anagrafica['pomodori']}")).status_code == 404
    vincitore = (await logged_client.get(f"{BASE}/{anagrafica['pomodoro']}")).json()
    assert {"pomodori", "pomodorini", "pomodori pelati"} <= set(_alias_per_nome(vincitore))


async def test_un_alimento_e_una_voce_non_alimentare_sono_un_409_kind_mismatch(logged_client, anagrafica):
    risposta = await logged_client.post(
        f"{BASE}/{anagrafica['pomodori']}/merge",
        json={"into": str(anagrafica["detersivo"]), "dry_run": True},
    )

    assert risposta.status_code == 409
    corpo = risposta.json()
    assert corpo["code"] == "kind_mismatch"
    assert corpo["existing"]["id"] == str(anagrafica["detersivo"])
    assert "poi uniscili" in corpo["detail"]


async def test_una_fusione_rifiutata_non_cambia_il_database(logged_client, anagrafica, dal_database):
    """Contratto Task 5: un rifiuto lascia la sessione a metà scritta, e la rotta deve
    fare `rollback` e mai `commit`. `decision_refused` è il rifiuto che scrive prima
    di rifiutare (a differenza di `kind_mismatch`, che è il primo controllo e non
    scrive niente): `pomodori` porta il termine dell'import «k-pelati», MAPPED su di
    lei. Ricategorizzarla su un reparto non alimentare passa (nessuna ricetta la usa,
    solo `recipes_using` blocca quel PATCH) e la rende non alimentare quanto
    `detersivo`, così la fusione supera `kind_mismatch` ed entra nel giro dei termini
    — dove `undo_decision` annulla la decisione e dimentica l'alias «pomodori pelati»
    *prima* che `decide_by_hand` rifiuti di rimapparla su un vincitore non alimentare.
    Solo una sessione nuova, sulla stessa connessione, vede se quella scrittura a metà
    è arrivata davvero al database invece di restare nella sola identity map di
    `db_session` (spec S9 §10)."""
    ricategorizzato = await logged_client.patch(
        f"{BASE}/{anagrafica['pomodori']}", json={"category": "casa"}
    )
    assert ricategorizzato.status_code == 200

    risposta = await logged_client.post(
        f"{BASE}/{anagrafica['pomodori']}/merge",
        json={"into": str(anagrafica["detersivo"])},
    )
    assert risposta.status_code == 409
    assert risposta.json()["code"] == "decision_refused"

    pomodori = await dal_database(Ingredient, anagrafica["pomodori"])
    assert pomodori is not None
    termine = await dal_database(ImportTerm, anagrafica["term"])
    assert termine is not None
    assert (termine.decision, termine.ingredient_id) == (
        TermDecision.MAPPED, anagrafica["pomodori"],
    )
    assert "pomodori pelati" in {a.alias for a in pomodori.aliases}


async def test_un_alias_scritto_a_mano_si_sposta(logged_client, anagrafica):
    risposta = await logged_client.patch(
        f"{BASE}/{anagrafica['pomodori']}/aliases/{anagrafica['manuale']}",
        json={"ingredient_id": str(anagrafica["pomodoro"])},
    )

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["alias"]["alias"] == "pomodorini"
    assert corpo["ingredient"]["id"] == str(anagrafica["pomodoro"])


async def test_un_alias_della_coda_e_un_409_che_porta_il_termine(logged_client, anagrafica):
    url = f"{BASE}/{anagrafica['pomodori']}/aliases/{anagrafica['pelati']}"

    spostamento = await logged_client.patch(url, json={"ingredient_id": str(anagrafica["pomodoro"])})
    rimozione = await logged_client.delete(url)

    for risposta in (spostamento, rimozione):
        assert risposta.status_code == 409
        assert risposta.json()["code"] == "import_alias"
        assert risposta.json()["term"] == {
            "id": str(anagrafica["term"]), "display_name": "Pomodori pelati",
        }


async def test_togliere_un_alias_scritto_a_mano(logged_client, anagrafica):
    risposta = await logged_client.delete(
        f"{BASE}/{anagrafica['pomodori']}/aliases/{anagrafica['manuale']}"
    )

    assert risposta.status_code == 204
    scheda = (await logged_client.get(f"{BASE}/{anagrafica['pomodori']}")).json()
    assert "pomodorini" not in _alias_per_nome(scheda)


async def test_un_alias_di_un_altro_ingrediente_e_un_404(logged_client, anagrafica):
    risposta = await logged_client.delete(
        f"{BASE}/{anagrafica['pomodoro']}/aliases/{anagrafica['manuale']}"
    )
    assert risposta.status_code == 404
