"""`PUT /recipes/{id}`: la ricetta intera, righe comprese (R10 §5, §8.2).

Le righe passano dalla stessa strada della creazione: `_resolve_lines` per i nomi,
`write_recipe_ingredients` per l'imbuto e le quantità. Una ricetta importata che si
modifica diventa tua: la sua pagina passa ad `adopted` nella stessa transazione.
"""

import uuid
from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy import select

from app.cli.reindex import reindex
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.recipe import Recipe, RecipeIngredient, RecipeSource
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportState, RecipeImport
from app.domain.rules import PantryStatus
from app.repositories.recipes import create_recipe

SPAGHETTI = "https://ricette.giallozafferano.it/Spaghetti-al-pomodoro.html"


@pytest_asyncio.fixture
async def cucina(db_session):
    def voce(name: str, category: str) -> Ingredient:
        return Ingredient(name=name, display_name=name.capitalize(), category=category)

    voci = {
        "pasta": voce("pasta", IngredientCategory.CEREALI),
        "pomodoro": voce("pomodoro", IngredientCategory.VERDURA),
        "aglio": voce("aglio", IngredientCategory.VERDURA),
        "sapone": voce("sapone per le mani", IngredientCategory.IGIENE),
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    return voci


@pytest_asyncio.fixture
async def importata(db_session, cucina):
    """Una ricetta dell'import, con la sua pagina ancora `imported`."""
    ricetta = await create_recipe(
        db_session, title="Spaghetti al pomodoro", description=None, instructions="Cuoci.",
        servings=4, source=RecipeSource.DATASET, source_ref=SPAGHETTI,
        ingredients=[
            (cucina["pasta"].id, "primary", "320 g", None),
            (cucina["pomodoro"].id, "primary", "400 g", None),
        ],
        embedding=None, category="Primi piatti",
    )
    # foto e tempi vengono solo dall'import: il modulo non li tocca (spec §7)
    ricetta.image_url = "https://esempio.invalid/spaghetti.jpg"
    ricetta.prep_minutes = 10
    ricetta.cook_minutes = 15
    pagina = RecipeImport(
        source=GIALLOZAFFERANO, url=SPAGHETTI,
        payload={"title": "Spaghetti al pomodoro", "ingredients": []},
        state=ImportState.IMPORTED, recipe_id=ricetta.id,
    )
    db_session.add(pagina)
    await db_session.flush()
    return ricetta, pagina


def _riga(voce, role="primary", quantity=None):
    return {"ingredient_id": str(voce.id), "role": role, "quantity_text": quantity}


def _corpo(cucina, **extra):
    corpo = {
        "title": "Pasta al pomodoro", "description": "Di sempre", "category": None,
        "instructions": "Cuoci.", "servings": 2, "cost": None,
        "ingredients": [
            _riga(cucina["pasta"], quantity="320 g"),
            _riga(cucina["pomodoro"], quantity="400 g"),
            _riga(cucina["aglio"], "secondary"),
        ],
    }
    corpo.update(extra)
    return corpo


async def _scritta(client, cucina) -> dict:
    risposta = await client.post("/api/v1/recipes", json={**_corpo(cucina), "source": "manual"})
    assert risposta.status_code == 201, risposta.text
    return risposta.json()


async def _modifica(client, recipe_id, corpo):
    return await client.put(f"/api/v1/recipes/{recipe_id}", json=corpo)


async def _nomi(client, recipe_id) -> set[str]:
    dettaglio = (await client.get(f"/api/v1/recipes/{recipe_id}")).json()
    return {riga["ingredient_name"] for riga in dettaglio["ingredients"]}


async def _vettore(dal_database, recipe_id) -> list[float] | None:
    ricetta = await dal_database(Recipe, uuid.UUID(str(recipe_id)))
    return None if ricetta.embedding is None else [float(x) for x in ricetta.embedding]


async def test_una_ricetta_scritta_a_mano_si_modifica_tutta(logged_client, cucina):
    ricetta = await _scritta(logged_client, cucina)

    risposta = await _modifica(logged_client, ricetta["id"], _corpo(
        cucina, title="Pasta aglio e pomodoro", description="Più veloce",
        instructions="Soffriggi, poi cuoci.", servings=4, cost=2,
        ingredients=[
            _riga(cucina["pasta"], "primary", "200 g"),
            _riga(cucina["aglio"], "primary", "2 spicchi"),
            _riga(cucina["pomodoro"], "secondary"),
        ],
    ))

    assert risposta.status_code == 200, risposta.text
    corpo = risposta.json()
    assert (corpo["title"], corpo["description"], corpo["instructions"]) == (
        "Pasta aglio e pomodoro", "Più veloce", "Soffriggi, poi cuoci.",
    )
    assert (corpo["servings"], corpo["cost"]) == (4, 2)
    assert {r["ingredient_name"]: (r["role"], r["quantity_text"]) for r in corpo["ingredients"]} == {
        "pasta": ("primary", "200 g"),
        "aglio": ("primary", "2 spicchi"),
        "pomodoro": ("secondary", None),
    }
    # la provenienza non si tocca
    assert (corpo["source"], corpo["source_ref"]) == ("manual", None)
    dettaglio = (await logged_client.get(f"/api/v1/recipes/{ricetta['id']}")).json()
    assert dettaglio["title"] == "Pasta aglio e pomodoro"


async def test_una_riga_tolta_se_ne_va_e_la_ricetta_diventa_cucinabile(
    logged_client, db_session, cucina
):
    ricetta = await _scritta(logged_client, cucina)
    db_session.add_all([
        PantryItem(ingredient_id=cucina["pasta"].id, status=PantryStatus.AVAILABLE),
        PantryItem(ingredient_id=cucina["aglio"].id, status=PantryStatus.AVAILABLE),
    ])
    await db_session.flush()
    prima = (await logged_client.get(f"/api/v1/recipes/{ricetta['id']}")).json()
    assert prima["cookable"] is False  # manca il pomodoro

    risposta = await _modifica(logged_client, ricetta["id"], _corpo(
        cucina, ingredients=[_riga(cucina["pasta"], quantity="320 g"), _riga(cucina["aglio"], "secondary")],
    ))

    assert risposta.json()["cookable"] is True
    righe = (
        await db_session.execute(
            select(RecipeIngredient.ingredient_id).where(
                RecipeIngredient.recipe_id == uuid.UUID(ricetta["id"])
            )
        )
    ).scalars().all()
    assert set(righe) == {cucina["pasta"].id, cucina["aglio"].id}


async def test_una_ricetta_importata_modificata_diventa_tua(
    logged_client, dal_database, cucina, importata
):
    ricetta, pagina = importata

    risposta = await _modifica(
        logged_client, ricetta.id, _corpo(cucina, title="I miei spaghetti", category="Primi piatti")
    )

    assert risposta.status_code == 200, risposta.text
    # «tua» non è la provenienza: resta `dataset`, con il suo indirizzo
    assert (risposta.json()["source"], risposta.json()["source_ref"]) == ("dataset", SPAGHETTI)
    assert (await dal_database(RecipeImport, pagina.id)).state == ImportState.ADOPTED
    # foto e tempi non sono nel modulo, e una modifica non li cancella (spec §7)
    corpo = risposta.json()
    assert (corpo["image_url"], corpo["prep_minutes"], corpo["cook_minutes"]) == (
        "https://esempio.invalid/spaghetti.jpg", 10, 15,
    )


async def test_il_non_alimentare_e_rifiutato_e_la_ricetta_resta_com_era(logged_client, cucina):
    ricetta = await _scritta(logged_client, cucina)

    risposta = await _modifica(logged_client, ricetta["id"], _corpo(
        cucina, title="Altro titolo",
        ingredients=[_riga(cucina["pasta"]), _riga(cucina["sapone"])],
    ))

    assert risposta.status_code == 422
    assert "Sapone per le mani" in risposta.json()["detail"]
    dettaglio = (await logged_client.get(f"/api/v1/recipes/{ricetta['id']}")).json()
    assert dettaglio["title"] == "Pasta al pomodoro"
    assert await _nomi(logged_client, ricetta["id"]) == {"pasta", "pomodoro", "aglio"}


async def test_senza_modello_un_titolo_nuovo_lascia_l_embedding_a_null(
    logged_client, db_session, dal_database, cucina, monkeypatch
):
    from app.services.embeddings import EmbeddingUnavailable

    ricetta = await _scritta(logged_client, cucina)
    assert await _vettore(dal_database, ricetta["id"]) is not None

    class ProviderRotto:
        async def embed_passages(self, texts):
            raise EmbeddingUnavailable("modello non installato")

        async def embed_query(self, text):
            raise EmbeddingUnavailable("modello non installato")

    monkeypatch.setattr("app.api.recipes.get_embedding_provider", lambda: ProviderRotto())

    risposta = await _modifica(logged_client, ricetta["id"], _corpo(cucina, title="Titolo nuovo"))

    assert risposta.status_code == 200, risposta.text
    # un vettore del titolo vecchio sarebbe una bugia sulla ricetta nuova: meglio nessuno
    assert await _vettore(dal_database, ricetta["id"]) is None
    # e il comando che riempie i vettori mancanti la ritrova
    assert await reindex(db_session) == 1


async def test_un_titolo_nuovo_ricalcola_l_embedding_e_il_resto_no(
    logged_client, dal_database, cucina
):
    ricetta = await _scritta(logged_client, cucina)
    prima = await _vettore(dal_database, ricetta["id"])

    await _modifica(logged_client, ricetta["id"], _corpo(cucina, instructions="Solo questo cambia."))
    assert await _vettore(dal_database, ricetta["id"]) == prima

    await _modifica(logged_client, ricetta["id"], _corpo(cucina, title="Titolo nuovo"))
    assert await _vettore(dal_database, ricetta["id"]) != prima


async def test_una_ricetta_eliminata_non_si_modifica(logged_client, db_session, cucina):
    ricetta = await _scritta(logged_client, cucina)
    salvata = await db_session.get(Recipe, uuid.UUID(ricetta["id"]))
    salvata.archived_at = datetime.now(UTC)
    await db_session.flush()

    risposta = await _modifica(logged_client, ricetta["id"], _corpo(cucina, title="Non passa"))

    assert risposta.status_code == 409
    assert "ripristinala" in risposta.json()["detail"]


async def test_un_ingrediente_sparito_e_un_404_e_una_riga_doppia_un_409(
    logged_client, db_session, cucina
):
    ricetta = await _scritta(logged_client, cucina)

    fantasma = {"ingredient_id": str(uuid.uuid4()), "role": "primary"}
    assert (await _modifica(logged_client, ricetta["id"], _corpo(cucina, ingredients=[fantasma]))).status_code == 404
    # il 404 arriva da un `rollback()` sulla stessa sessione: scade gli oggetti della
    # fixture, e `_corpo` li rilegge tutti costruendo il corpo di base — si ricaricano
    # prima di riusarli, altrimenti l'accesso a `.id` qui sotto è un MissingGreenlet
    for voce in cucina.values():
        await db_session.refresh(voce)
    doppia = [_riga(cucina["pasta"]), _riga(cucina["pasta"], "secondary")]
    assert (await _modifica(logged_client, ricetta["id"], _corpo(cucina, ingredients=doppia))).status_code == 409

    # nessuno dei due ha lasciato la ricetta a metà
    assert await _nomi(logged_client, ricetta["id"]) == {"pasta", "pomodoro", "aglio"}


async def test_una_ricetta_che_non_c_e_e_un_404(logged_client, cucina):
    assert (await _modifica(logged_client, uuid.uuid4(), _corpo(cucina))).status_code == 404


async def test_la_provenienza_mandata_si_ignora(logged_client, cucina):
    ricetta = await _scritta(logged_client, cucina)

    risposta = await _modifica(
        logged_client, ricetta["id"], {**_corpo(cucina), "source": "ai", "source_ref": "prompt: altro"}
    )

    assert (risposta.json()["source"], risposta.json()["source_ref"]) == ("manual", None)


async def test_una_riga_per_nome_si_aggancia_come_alla_creazione(logged_client, db_session, cucina):
    """`match_name`, come nella POST: «pomodori» è un alias di «pomodoro», e crearne
    un secondo sarebbe un duplicato travestito."""
    from app.repositories.ingredients import add_alias

    await add_alias(db_session, cucina["pomodoro"].id, "pomodori", source="seed")
    ricetta = await _scritta(logged_client, cucina)

    risposta = await _modifica(logged_client, ricetta["id"], _corpo(cucina, ingredients=[
        _riga(cucina["pasta"]),
        {"name": "pomodori", "category": "verdura", "role": "primary"},
    ]))

    assert risposta.status_code == 200, risposta.text
    assert {r["ingredient_id"] for r in risposta.json()["ingredients"]} == {
        str(cucina["pasta"].id), str(cucina["pomodoro"].id),
    }


async def test_la_categoria_che_ha_gia_si_tiene_e_una_inventata_no(logged_client, cucina, importata):
    ricetta, _ = importata
    assert (await _modifica(logged_client, ricetta.id, _corpo(cucina, category="Primi piatti"))).status_code == 200
    assert (await _modifica(logged_client, ricetta.id, _corpo(cucina, category="Secondi inventati"))).status_code == 422
