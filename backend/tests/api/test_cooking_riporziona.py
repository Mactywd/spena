"""La cottura riscalata da una dose (R2, secondo modo): cosa resta nello storico.

In file suo e non in `test_cooking.py`, che stanotte cambia anche un altro ramo."""

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe import CookingEvent
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import create_recipe


@pytest_asyncio.fixture
async def ricetta(db_session):
    pasta = await create_ingredient(
        db_session, name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI
    )
    sale = await create_ingredient(
        db_session, name="sale", display_name="Sale", category=IngredientCategory.SPEZIE
    )
    recipe = await create_recipe(
        db_session,
        title="Pasta in bianco", description=None, instructions="Cuoci.", servings=4,
        source="dataset", source_ref=None,
        ingredients=[
            (pasta.id, "primary", "400 g", None),
            (sale.id, "secondary", "q.b.", None),
        ],
        embedding=None,
    )
    await db_session.flush()
    return {"id": recipe.id, "pasta": pasta.id, "sale": sale.id}


async def _cucina(client, recipe_id, **body):
    return await client.post(
        f"/api/v1/recipes/{recipe_id}/cook", json={"transitions": [], **body}
    )


async def _evento(dal_database, risposta):
    # da una sessione nuova: lo `snapshot` com'è nel JSONB, non com'è in memoria
    return await dal_database(CookingEvent, uuid.UUID(risposta.json()["event_id"]))


async def test_cucinata_da_una_dose_lo_snapshot_ha_l_ancora(logged_client, dal_database, ricetta):
    risposta = await _cucina(
        logged_client, ricetta["id"], anchor=str(ricetta["pasta"]), amount="150"
    )
    assert risposta.status_code == 201
    evento = await _evento(dal_database, risposta)
    # «≈ 1,5» non è un numero di porzioni uscito dalla pentola: la colonna resta vuota,
    # e il fatto vero — la dose — sta nello storico
    assert evento.servings is None
    assert evento.snapshot["anchor"] == {
        "ingredient_id": str(ricetta["pasta"]),
        "amount": "150",
        "unit": "g",
        "factor": "0.375",
        "equivalent_servings": "1.5",
    }
    # il resto dello snapshot è quello di sempre
    assert evento.snapshot["transitions"] == []
    assert evento.snapshot["restocked"] == 0


async def test_per_porzioni_lo_snapshot_non_cambia_forma(logged_client, dal_database, ricetta):
    risposta = await _cucina(logged_client, ricetta["id"], servings=2)
    assert risposta.status_code == 201
    evento = await _evento(dal_database, risposta)
    assert evento.servings == 2
    assert "anchor" not in evento.snapshot


@pytest.mark.parametrize(
    "ancora,amount,unita",
    [
        # una riga senza dose da cui riscalare (tolta, o diventata «q.b.», in un'altra scheda)
        ("sale", "1", None),
        # oltre le 50 volte: il dettaglio l'avrebbe rifiutata, ma la ricetta può essere
        # cambiata fra la vista e la cottura
        ("pasta", "100000", "g"),
    ],
)
async def test_un_ancora_che_non_vale_piu_non_blocca_la_cottura(
    logged_client, dal_database, ricetta, ancora, amount, unita
):
    risposta = await _cucina(
        logged_client, ricetta["id"], anchor=str(ricetta[ancora]), amount=amount
    )
    assert risposta.status_code == 201
    assert (await _evento(dal_database, risposta)).snapshot["anchor"] == {
        "ingredient_id": str(ricetta[ancora]),
        "amount": amount,
        "unit": unita,
        "factor": None,
        "equivalent_servings": None,
    }


@pytest.mark.parametrize(
    "body",
    [
        {"anchor": "PASTA"},
        {"amount": "150"},
        {"anchor": "PASTA", "amount": "150", "servings": 2},
        {"anchor": "PASTA", "amount": "0"},
        {"anchor": "PASTA", "amount": "1.2345"},
    ],
)
async def test_la_cottura_rifiuta_quel_che_il_dettaglio_rifiuta(
    logged_client, db_session, ricetta, body
):
    body = {k: (str(ricetta["pasta"]) if v == "PASTA" else v) for k, v in body.items()}
    risposta = await _cucina(logged_client, ricetta["id"], **body)
    assert risposta.status_code == 422
    eventi = (
        await db_session.execute(select(func.count()).select_from(CookingEvent))
    ).scalar_one()
    assert eventi == 0
