"""`GET /ingredients/match`: il passo del nome del modulo chiede, prima di aggiungere la
riga, dove finirebbe quel nome salvando (piano 20).

La risposta è `ingredient_for_new_name`, la stessa funzione di `_resolve_lines`: le ultime
due prove lo verificano dal lato che conta, cioè che quel che la rotta dice è quel che il
salvataggio fa.
"""

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.repositories.ingredients import add_alias, create_ingredient

MATCH = "/api/v1/ingredients/match"


@pytest_asyncio.fixture
async def anagrafica(db_session):
    pasta = await create_ingredient(db_session, "pasta", "Pasta", IngredientCategory.CEREALI)
    await add_alias(db_session, pasta.id, "pennette", "manual")
    detersivo = await create_ingredient(
        db_session, "detersivo per i piatti", "Detersivo per i piatti", IngredientCategory.CASA
    )
    await add_alias(db_session, detersivo.id, "sapone piatti", "manual")
    await db_session.commit()
    return {"pasta": pasta, "detersivo": detersivo}


async def test_un_non_alimentare_torna_col_suo_nome_e_il_kind(logged_client, anagrafica):
    risposta = await logged_client.get(MATCH, params={"name": "Detersivo per i piatti"})

    assert risposta.status_code == 200
    trovato = risposta.json()["ingredient"]
    assert trovato["id"] == str(anagrafica["detersivo"].id)
    assert trovato["display_name"] == "Detersivo per i piatti"
    assert trovato["kind"] == "non_food"


async def test_un_alias_porta_all_ingrediente_che_lo_ha(logged_client, anagrafica):
    risposta = await logged_client.get(MATCH, params={"name": "sapone piatti"})

    trovato = risposta.json()["ingredient"]
    assert (trovato["id"], trovato["kind"]) == (str(anagrafica["detersivo"].id), "non_food")


async def test_un_alimento_torna_col_kind_food(logged_client, anagrafica):
    risposta = await logged_client.get(MATCH, params={"name": "pasta"})

    trovato = risposta.json()["ingredient"]
    assert (trovato["id"], trovato["kind"]) == (str(anagrafica["pasta"].id), "food")


async def test_un_nome_che_non_c_e_torna_null(logged_client, anagrafica):
    risposta = await logged_client.get(MATCH, params={"name": "zz mai visto"})

    assert risposta.status_code == 200
    assert risposta.json() == {"ingredient": None}


async def test_una_somiglianza_non_basta_torna_null(logged_client, anagrafica):
    """«detersivo» somiglia a «detersivo per i piatti», ma salvando nascerebbe un
    ingrediente nuovo: il passo del nome non deve dire «non alimentare»."""
    risposta = await logged_client.get(MATCH, params={"name": "detersivo"})

    assert risposta.json() == {"ingredient": None}


@pytest.mark.parametrize("params", [{}, {"name": ""}, {"name": "x" * 121}])
async def test_un_nome_mancante_vuoto_o_troppo_lungo_e_422(logged_client, params):
    assert (await logged_client.get(MATCH, params=params)).status_code == 422


async def test_senza_sessione_e_401(client):
    assert (await client.get(MATCH, params={"name": "pasta"})).status_code == 401


async def test_quel_che_la_rotta_dice_non_alimentare_il_salvataggio_lo_rifiuta(
    logged_client, anagrafica
):
    detto = (await logged_client.get(MATCH, params={"name": "sapone piatti"})).json()
    assert detto["ingredient"]["kind"] == "non_food"

    risposta = await logged_client.post("/api/v1/recipes", json={
        "title": "Pasta e sapone", "instructions": "1. no", "servings": 2, "source": "manual",
        "ingredients": [{"name": "sapone piatti", "category": "altro", "role": "primary"}],
    })

    assert risposta.status_code == 422
    assert "non è un alimento" in risposta.json()["detail"]


async def test_quel_che_la_rotta_collega_il_salvataggio_lo_collega(
    logged_client, db_session, anagrafica
):
    detto = (await logged_client.get(MATCH, params={"name": "pennette"})).json()
    assert detto["ingredient"]["id"] == str(anagrafica["pasta"].id)

    risposta = await logged_client.post("/api/v1/recipes", json={
        "title": "Pennette", "instructions": "1. cuoci", "servings": 2, "source": "manual",
        "ingredients": [{"name": "pennette", "category": "cereali", "role": "primary"}],
    })

    assert risposta.status_code == 201, risposta.text
    assert risposta.json()["ingredients"][0]["ingredient_id"] == str(anagrafica["pasta"].id)
    nuovi = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "pennette"))
    ).scalars().all()
    assert nuovi == []
