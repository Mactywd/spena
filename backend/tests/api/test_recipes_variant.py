"""R8: la variante di una ricetta — il legame con l'originale, e la proposta dell'AI.

Il legame (`derived_from_id`) si prova per intero, sul database vero. La proposta
(`POST /recipes/{id}/ai-variant`, più sotto) si prova con il servizio sostituito: il
servizio vero, con i finti dell'LLM, lo prova `tests/services/test_ai_recipes.py`.
"""

import uuid

import pytest_asyncio
from sqlalchemy import func, select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe, RecipeSource
from app.db.models.recipe_import import RecipeImport
from app.domain.rules import IngredientRole
from app.repositories.recipes import create_recipe
from app.services.ai_recipes import DraftIngredient, RecipeDraft
from app.services.llm import LlmUnavailable

TITOLO_VARIANTE = "Pasta al pomodoro senza basilico"


@pytest_asyncio.fixture
async def cucina(db_session):
    def voce(name: str, category: str) -> Ingredient:
        return Ingredient(name=name, display_name=name.capitalize(), category=category)

    voci = {
        "pasta": voce("pasta", IngredientCategory.CEREALI),
        "pomodoro": voce("pomodoro", IngredientCategory.VERDURA),
        "basilico": voce("basilico", IngredientCategory.SPEZIE),
        "sapone": voce("sapone per le mani", IngredientCategory.IGIENE),
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    return voci


@pytest_asyncio.fixture
async def originale(db_session, cucina):
    return await create_recipe(
        db_session, title="Pasta al pomodoro", description="Di sempre", instructions="Cuoci.",
        servings=2, source=RecipeSource.MANUAL, source_ref=None,
        ingredients=[
            (cucina["pasta"].id, "primary", "180 g", None),
            (cucina["pomodoro"].id, "primary", "300 g", None),
            (cucina["basilico"].id, "secondary", "q.b.", None),
        ],
        embedding=None,
    )


def corpo_variante(cucina, originale_id, **altro) -> dict:
    """Il corpo che il modulo della variante manda a `POST /recipes`."""
    return {
        "title": TITOLO_VARIANTE, "description": None, "instructions": "Cuoci. Condisci.",
        "servings": 2, "source": "ai", "source_ref": "prompt: senza basilico", "cost": 1,
        "derived_from_id": str(originale_id),
        "ingredients": [
            {"ingredient_id": str(cucina["pasta"].id), "role": "primary", "quantity_text": "180 g"},
            {"ingredient_id": str(cucina["pomodoro"].id), "role": "primary", "quantity_text": "350 g"},
        ],
        **altro,
    }


async def test_salvare_una_variante_tiene_il_legame_e_non_tocca_l_originale(
    logged_client, db_session, cucina, originale, dal_database
):
    risposta = await logged_client.post("/api/v1/recipes", json=corpo_variante(cucina, originale.id))

    assert risposta.status_code == 201
    variante = risposta.json()
    assert variante["derived_from"] == {
        "id": str(originale.id), "title": "Pasta al pomodoro", "archived": False,
    }
    assert variante["source"] == "ai"
    assert variante["owned_by_import"] is False
    riga = await dal_database(Recipe, uuid.UUID(variante["id"]))
    assert riga.derived_from_id == originale.id

    # l'originale è com'era: il suo titolo, le sue tre righe con le sue dosi, nessun legame
    letta = (await logged_client.get(f"/api/v1/recipes/{originale.id}")).json()
    assert letta["title"] == "Pasta al pomodoro"
    assert sorted((r["ingredient_name"], r["quantity_text"]) for r in letta["ingredients"]) == [
        ("basilico", "q.b."), ("pasta", "180 g"), ("pomodoro", "300 g"),
    ]
    assert letta["derived_from"] is None
    # e la variante non è importata: nessuna pagina d'import
    pagine = (
        await db_session.execute(
            select(RecipeImport).where(RecipeImport.recipe_id == uuid.UUID(variante["id"]))
        )
    ).scalars().all()
    assert pagine == []


async def test_un_originale_eliminata_resta_nel_legame_e_lo_dice(logged_client, cucina, originale):
    """R10: un'eliminata si apre dalla lapide, quindi il legame resta e dice com'è."""
    prima = (await logged_client.post("/api/v1/recipes", json=corpo_variante(cucina, originale.id))).json()
    eliminata = await logged_client.patch(f"/api/v1/recipes/{originale.id}", json={"archived": True})
    assert eliminata.status_code == 200

    letta = (await logged_client.get(f"/api/v1/recipes/{prima['id']}")).json()
    assert letta["derived_from"] == {
        "id": str(originale.id), "title": "Pasta al pomodoro", "archived": True,
    }
    # e una variante salvata quando l'originale è già eliminata tiene il legame anche lei
    dopo = await logged_client.post("/api/v1/recipes", json=corpo_variante(cucina, originale.id))
    assert dopo.status_code == 201
    assert dopo.json()["derived_from"]["archived"] is True


async def test_un_originale_che_non_c_e_piu_non_ferma_la_variante(logged_client, cucina, dal_database):
    """Mai un vicolo cieco: l'import può aver rifatto l'originale mentre si correggeva la
    variante. Rifiutarla butterebbe il lavoro, e dal modulo il legame non si toglie."""
    risposta = await logged_client.post("/api/v1/recipes", json=corpo_variante(cucina, uuid.uuid4()))

    assert risposta.status_code == 201
    assert risposta.json()["derived_from"] is None
    riga = await dal_database(Recipe, uuid.UUID(risposta.json()["id"]))
    assert riga.derived_from_id is None


async def test_modificare_una_variante_tiene_il_legame(logged_client, cucina, originale):
    variante = (await logged_client.post("/api/v1/recipes", json=corpo_variante(cucina, originale.id))).json()
    corpo = corpo_variante(cucina, originale.id, title="Pasta al pomodoro, la mia")
    for chiave in ("derived_from_id", "source", "source_ref"):
        corpo.pop(chiave)

    risposta = await logged_client.put(f"/api/v1/recipes/{variante['id']}", json=corpo)

    assert risposta.status_code == 200
    assert risposta.json()["title"] == "Pasta al pomodoro, la mia"
    assert risposta.json()["derived_from"]["id"] == str(originale.id)


async def test_la_variante_parte_con_la_foto_e_i_tempi_dell_originale(
    logged_client, db_session, cucina, originale
):
    """Deciso da Mattia il 2026-10-13: «Sì, copiali». Li copia il server, perché il modulo
    non li ha (R10 §7): il client non li sceglie, e una modifica della variante li lascia."""
    originale.image_url = "https://esempio.invalid/pasta.jpg"
    originale.prep_minutes = 10
    originale.cook_minutes = 15
    await db_session.flush()

    # mandati dal client si ignorano: `RecipeCreate` non li dichiara
    corpo = corpo_variante(
        cucina, originale.id, image_url="https://altrove.invalid/altra.jpg", prep_minutes=1
    )
    risposta = await logged_client.post("/api/v1/recipes", json=corpo)

    assert risposta.status_code == 201
    variante = risposta.json()
    assert (variante["image_url"], variante["prep_minutes"], variante["cook_minutes"]) == (
        "https://esempio.invalid/pasta.jpg", 10, 15,
    )

    # la modifica della variante (R10) non li manda, e non li cancella
    modifica = corpo_variante(cucina, originale.id, title="Pasta al pomodoro, la mia")
    for chiave in ("derived_from_id", "source", "source_ref"):
        modifica.pop(chiave)
    modificata = await logged_client.put(f"/api/v1/recipes/{variante['id']}", json=modifica)
    assert modificata.status_code == 200
    assert (
        modificata.json()["image_url"], modificata.json()["prep_minutes"],
        modificata.json()["cook_minutes"],
    ) == ("https://esempio.invalid/pasta.jpg", 10, 15)

    # una ricetta nuova che non è una variante non prende niente da nessuno
    libero = corpo_variante(cucina, originale.id, title="Pasta mia")
    libero.pop("derived_from_id")
    libera = (await logged_client.post("/api/v1/recipes", json=libero)).json()
    assert (libera["image_url"], libera["prep_minutes"], libera["cook_minutes"]) == (
        None, None, None,
    )


async def test_una_variante_non_puo_avere_un_non_alimentare(logged_client, db_session, cucina, originale):
    """L'imbuto `write_recipe_ingredients` vale anche per lei: è l'ultima linea, se una
    riga non alimentare arrivasse fin qui."""
    corpo = corpo_variante(cucina, originale.id)
    corpo["ingredients"].append(
        {"ingredient_id": str(cucina["sapone"].id), "role": "secondary", "quantity_text": "1"}
    )

    risposta = await logged_client.post("/api/v1/recipes", json=corpo)

    assert risposta.status_code == 422
    assert "non è un alimento" in risposta.json()["detail"]
    salvate = (
        await db_session.execute(select(Recipe.id).where(Recipe.title == TITOLO_VARIANTE))
    ).scalars().all()
    assert salvate == []


# ---- la proposta: POST /recipes/{id}/ai-variant ----


def proposta() -> RecipeDraft:
    return RecipeDraft(
        title=TITOLO_VARIANTE, description=None, instructions="Cuoci. Condisci.",
        servings=2, cost=1,
        ingredients=[
            DraftIngredient(
                raw_name="zucchero", role=IngredientRole.SECONDARY, quantity_text="1 pizzico",
                ingredient_id=None, matched_name=None, confident=False, proposed_category="dolci",
            )
        ],
    )


async def test_la_proposta_passa_dal_servizio_e_non_salva_niente(
    logged_client, db_session, monkeypatch, originale
):
    import app.api.recipes as rotte

    chiamate = []

    async def variante_finta(_session, recipe, prompt):
        chiamate.append((recipe.id, recipe.title, len(recipe.ingredients), prompt))
        return proposta()

    monkeypatch.setattr(rotte, "draft_variant", variante_finta)
    risposta = await logged_client.post(
        f"/api/v1/recipes/{originale.id}/ai-variant", json={"prompt": "senza basilico"}
    )

    assert risposta.status_code == 200
    # il servizio riceve la ricetta con le sue righe, e la richiesta com'è
    assert chiamate == [(originale.id, "Pasta al pomodoro", 3, "senza basilico")]
    corpo = risposta.json()
    assert corpo["title"] == TITOLO_VARIANTE
    assert corpo["cost"] == 1
    assert corpo["ingredients"][0]["raw_name"] == "zucchero"
    assert corpo["ingredients"][0]["proposed_category"] == "dolci"
    # propone e non salva: nel ricettario c'è sempre e solo l'originale
    assert await db_session.scalar(select(func.count()).select_from(Recipe)) == 1


async def test_la_proposta_di_una_ricetta_che_non_c_e_e_un_404(logged_client):
    risposta = await logged_client.post(
        f"/api/v1/recipes/{uuid.uuid4()}/ai-variant", json={"prompt": "senza basilico"}
    )
    assert risposta.status_code == 404


async def test_una_ricetta_eliminata_non_propone_varianti(logged_client, monkeypatch, originale):
    """R10: un'eliminata si ripristina prima di modificarla, e la variante è una modifica."""
    import app.api.recipes as rotte

    async def mai(*_args):
        raise AssertionError("l'AI non si chiama per una ricetta eliminata")

    monkeypatch.setattr(rotte, "draft_variant", mai)
    await logged_client.patch(f"/api/v1/recipes/{originale.id}", json={"archived": True})

    risposta = await logged_client.post(
        f"/api/v1/recipes/{originale.id}/ai-variant", json={"prompt": "senza basilico"}
    )

    assert risposta.status_code == 409
    assert risposta.json()["detail"] == (
        "Questa ricetta è stata eliminata: ripristinala prima di modificarla."
    )


async def test_l_ai_che_non_risponde_e_un_503(logged_client, monkeypatch, originale):
    import app.api.recipes as rotte

    async def giu(*_args):
        raise LlmUnavailable("OPENROUTER_API_KEY non configurata")

    monkeypatch.setattr(rotte, "draft_variant", giu)
    risposta = await logged_client.post(
        f"/api/v1/recipes/{originale.id}/ai-variant", json={"prompt": "senza basilico"}
    )

    assert risposta.status_code == 503
    assert risposta.json()["detail"].startswith("variante AI non disponibile")


async def test_la_proposta_senza_sessione_e_rifiutata(client, originale):
    risposta = await client.post(
        f"/api/v1/recipes/{originale.id}/ai-variant", json={"prompt": "senza basilico"}
    )
    assert risposta.status_code == 401
