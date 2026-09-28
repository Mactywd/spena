"""La presa in carico contro l'import (R10 §4, §8.3).

Due pagine dell'import con gli stessi due termini: la carbonara diventa tua con una
PUT, come la rende tua l'app; l'amatriciana resta dell'import. Ogni percorso che rifà
le ricette deve toccare la seconda e lasciare la prima.
"""

from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy import func, select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.repositories.imports import counts, known_urls, store_page
from app.repositories.ingredients import remember_alias
from app.services.recipe_import.materialize import materialize_ready
from app.services.registry import merge_ingredients

CARBONARA = "https://ricette.giallozafferano.it/Spaghetti-alla-Carbonara.html"
AMATRICIANA = "https://ricette.giallozafferano.it/Bucatini-all-Amatriciana.html"


def _payload(titolo: str) -> dict:
    return {
        "title": titolo, "description": None, "instructions": "Cuoci.", "servings": 4,
        "ingredients": [
            {"key": "k-spaghetti", "name": "Spaghetti", "quantity_text": "320 g"},
            {"key": "k-guanciale", "name": "Guanciale", "quantity_text": "150 g"},
        ],
    }


@pytest_asyncio.fixture
async def mondo(db_session):
    def voce(name: str, category: str) -> Ingredient:
        return Ingredient(name=name, display_name=name.capitalize(), category=category)

    voci = {
        "pasta": voce("pasta", IngredientCategory.CEREALI),
        "guanciale": voce("guanciale", IngredientCategory.CARNE),
        "pancetta": voce("pancetta", IngredientCategory.CARNE),
    }
    db_session.add_all(voci.values())
    await db_session.flush()

    def termine(key: str, display: str, voce_: str, *, creato: bool) -> ImportTerm:
        return ImportTerm(
            source=GIALLOZAFFERANO, term_key=key, display_name=display, occurrences=2,
            decision=TermDecision.MAPPED, ingredient_id=voci[voce_].id, decided_by="ai",
            decided_at=datetime.now(UTC), created_ingredient=creato,
        )

    termini = {
        # «Spaghetti» agganciato alla pasta che c'era già; «Guanciale» ha creato il suo
        # ingrediente: è quello che l'annullamento cancellerebbe, se niente lo usasse
        "spaghetti": termine("k-spaghetti", "Spaghetti", "pasta", creato=False),
        "t-guanciale": termine("k-guanciale", "Guanciale", "guanciale", creato=True),
    }
    db_session.add_all(termini.values())
    await db_session.flush()
    for term in termini.values():
        await remember_alias(db_session, term.ingredient_id, term.display_name)
    for url, titolo in ((CARBONARA, "Spaghetti alla carbonara"), (AMATRICIANA, "Bucatini all'amatriciana")):
        await store_page(db_session, source=GIALLOZAFFERANO, url=url, payload=_payload(titolo))
    await materialize_ready(db_session, GIALLOZAFFERANO)
    return {**voci, **termini}


async def _pagina(db_session, url: str) -> RecipeImport:
    return (
        await db_session.execute(select(RecipeImport).where(RecipeImport.url == url))
    ).scalar_one()


async def _adotta(client, db_session, url: str, titolo: str) -> str:
    """Rende tua la ricetta di quella pagina come la rende tua l'app: con una PUT."""
    pagina = await _pagina(db_session, url)
    dettaglio = (await client.get(f"/api/v1/recipes/{pagina.recipe_id}")).json()
    corpo = {
        "title": titolo, "description": dettaglio["description"],
        "category": dettaglio["category"], "instructions": dettaglio["instructions"],
        "servings": dettaglio["servings"], "cost": dettaglio["cost"],
        "ingredients": [
            {"ingredient_id": r["ingredient_id"], "role": r["role"],
             "quantity_text": r["quantity_text"], "note": r["note"]}
            for r in dettaglio["ingredients"]
        ],
    }
    risposta = await client.put(f"/api/v1/recipes/{pagina.recipe_id}", json=corpo)
    assert risposta.status_code == 200, risposta.text
    return dettaglio["id"]


async def _ricetta(client, recipe_id: str) -> dict:
    return (await client.get(f"/api/v1/recipes/{recipe_id}")).json()


async def test_annullare_il_termine_lascia_intatta_la_ricetta_tua_e_la_conta(
    logged_client, db_session, mondo
):
    mia = await _adotta(logged_client, db_session, CARBONARA, "La mia carbonara")

    risposta = await logged_client.post(f"/api/v1/imports/terms/{mondo['t-guanciale'].id}/undo")

    assert risposta.status_code == 200, risposta.text
    esito = risposta.json()
    assert esito["recipes_requeued"] == 1  # l'amatriciana, ancora dell'import
    assert esito["adopted_untouched"] == 1  # la carbonara, tua
    assert esito["ingredient_deleted"] is False
    assert esito["ingredient_kept_for_adopted"] is True
    ricetta = await _ricetta(logged_client, mia)
    assert ricetta["title"] == "La mia carbonara"
    assert {r["ingredient_name"] for r in ricetta["ingredients"]} == {"pasta", "guanciale"}
    assert (await _pagina(db_session, CARBONARA)).state == ImportState.ADOPTED
    assert (await _pagina(db_session, AMATRICIANA)).state == ImportState.PENDING


async def test_un_aggancio_annullato_non_dice_di_tenere_un_ingrediente_che_non_aveva_creato(
    logged_client, db_session, mondo
):
    """«Spaghetti» agganciato alla pasta che c'era già: la ricetta tua usa la pasta, ma
    l'annullamento non l'avrebbe cancellata comunque, e dire «resta per una ricetta tua»
    sarebbe falso. La guardia è `created_ingredient`: senza, questo test diventa rosso."""
    await _adotta(logged_client, db_session, CARBONARA, "La mia carbonara")

    risposta = await logged_client.post(f"/api/v1/imports/terms/{mondo['spaghetti'].id}/undo")

    assert risposta.status_code == 200, risposta.text
    esito = risposta.json()
    assert esito["adopted_untouched"] == 1  # la carbonara contiene il termine, ed è tua
    assert esito["ingredient_deleted"] is False
    assert esito["ingredient_kept_for_adopted"] is False


async def test_l_erede_annullato_dice_che_l_ingrediente_resta_per_la_ricetta_tua(
    logged_client, db_session, mondo
):
    """Dopo il passaggio del creatore: «Guanciale» aveva creato il guanciale, un secondo
    termine vi è agganciato. Annullato il creatore, l'ingrediente resta (lo usano la
    carbonara tua e l'altro termine) e la cancellazione passa all'altro termine. Annullato
    anche quello, l'ingrediente resta ancora, per la carbonara — che però contiene il
    primo termine, non questo: cercarla solo fra le pagine di questo termine rispondeva
    «non cancellato, e non per una ricetta tua», cioè senza un perché."""
    await _adotta(logged_client, db_session, CARBONARA, "La mia carbonara")
    erede = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-guanciale-dolce", display_name="Guanciale dolce",
        occurrences=1, decision=TermDecision.MAPPED, ingredient_id=mondo["guanciale"].id,
        decided_by="ai", decided_at=datetime.now(UTC), created_ingredient=False,
    )
    db_session.add(erede)
    await db_session.flush()
    await remember_alias(db_session, erede.ingredient_id, erede.display_name)

    primo = (
        await logged_client.post(f"/api/v1/imports/terms/{mondo['t-guanciale'].id}/undo")
    ).json()
    assert (primo["ingredient_deleted"], primo["ingredient_kept_for_adopted"]) == (False, True)
    await db_session.refresh(erede)
    assert erede.created_ingredient is True  # la cancellazione è passata a lui

    risposta = await logged_client.post(f"/api/v1/imports/terms/{erede.id}/undo")

    assert risposta.status_code == 200, risposta.text
    esito = risposta.json()
    assert esito["adopted_untouched"] == 0  # nessuna pagina tua contiene questo termine
    assert esito["ingredient_deleted"] is False
    assert esito["ingredient_kept_for_adopted"] is True
    assert await db_session.get(Ingredient, mondo["guanciale"].id) is not None


async def test_rideciso_il_termine_l_import_rifa_solo_la_sua(logged_client, db_session, mondo):
    mia = await _adotta(logged_client, db_session, CARBONARA, "La mia carbonara")
    termine = mondo["t-guanciale"]
    await logged_client.post(f"/api/v1/imports/terms/{termine.id}/undo")

    risposta = await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "map", "ingredient_id": str(mondo["pancetta"].id)},
    )

    assert risposta.status_code == 200, risposta.text
    assert risposta.json()["unlocked"] == 1  # l'amatriciana torna, con la pancetta
    quante = await db_session.scalar(
        select(func.count()).select_from(Recipe).where(Recipe.source_ref == CARBONARA)
    )
    assert quante == 1  # la carbonara resta una, la tua
    ricetta = await _ricetta(logged_client, mia)
    assert {r["ingredient_name"] for r in ricetta["ingredients"]} == {"pasta", "guanciale"}


async def test_una_fusione_sposta_in_loco_la_riga_della_ricetta_tua(
    logged_client, db_session, mondo
):
    mia = await _adotta(logged_client, db_session, CARBONARA, "La mia carbonara")

    conti = await merge_ingredients(db_session, mondo["guanciale"].id, mondo["pancetta"].id)
    await db_session.flush()

    assert conti.recipe_lines_moved == 1  # la tua, spostata dov'è
    assert conti.recipes_rebuilt == 1  # l'amatriciana, rifatta dal payload
    ricetta = await _ricetta(logged_client, mia)
    assert ricetta["title"] == "La mia carbonara"
    assert {r["ingredient_name"] for r in ricetta["ingredients"]} == {"pasta", "pancetta"}


async def test_materialize_ready_non_tocca_la_pagina_presa_in_carico(
    logged_client, db_session, mondo
):
    mia = await _adotta(logged_client, db_session, CARBONARA, "La mia carbonara")

    esito = await materialize_ready(db_session, GIALLOZAFFERANO)

    assert esito.created == 0
    pagina = await _pagina(db_session, CARBONARA)
    assert (pagina.state, str(pagina.recipe_id)) == (ImportState.ADOPTED, mia)


async def test_la_risincronizzazione_salta_l_indirizzo_della_ricetta_tua(
    logged_client, db_session, mondo
):
    """DOCUMENTAZIONE, non guardia: passava prima di R10 e non può fallire per R10.

    `_new_urls` di `import_gz` scarta ogni indirizzo che `known_urls` conosce, e
    `known_urls` li restituisce tutti, in qualunque stato. Sta qui perché la spec §4
    elenca la risincronizzazione fra i percorsi che lasciano stare una pagina `adopted`,
    e chi legge questo file cerca la prova accanto alle altre. Se un giorno `known_urls`
    filtrasse per stato, questo test diventerebbe una guardia vera.
    """
    await _adotta(logged_client, db_session, CARBONARA, "La mia carbonara")
    assert CARBONARA in await known_urls(db_session, GIALLOZAFFERANO)


async def test_la_coda_conta_la_ricetta_tua_fra_quelle_gia_dentro(
    logged_client, db_session, mondo
):
    """«N ricette scaricate aspettano, M sono già dentro»: una pagina presa in carico è
    stata importata una volta, e i conti per stato devono tornare a `fetched`
    (deviazione 13)."""
    await _adotta(logged_client, db_session, CARBONARA, "La mia carbonara")

    numeri = await counts(db_session, GIALLOZAFFERANO)

    assert (numeri.fetched, numeri.pending_recipes, numeri.imported, numeri.skipped) == (2, 0, 2, 0)
