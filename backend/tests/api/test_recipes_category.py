"""Una ricetta scritta qui esce filtrando per categoria (R10 §6.2, giro di T3).

La categoria si sceglie fra quelle già nel ricettario, o nessuna: senza testo libero,
per non creare «Primi» e «primi». Il modulo non offre altro; la rotta è l'ultima linea.
"""

import pytest_asyncio
from sqlalchemy import func, select

from app.db.models.recipe import Recipe, RecipeSource
from app.repositories.recipes import create_recipe


@pytest_asyncio.fixture
async def primi(db_session):
    """Una categoria che il ricettario ha già, portata da una ricetta importata."""
    await create_recipe(
        db_session, title="Pasta e fagioli", description=None, instructions="Cuoci.",
        servings=2, source=RecipeSource.DATASET, source_ref=None, ingredients=[],
        embedding=None, category="Primi piatti",
    )
    await db_session.flush()


def _corpo(**extra):
    return {"title": "Pasta e ceci", "instructions": "Cuoci.", "source": "manual", **extra}


async def test_una_categoria_esistente_si_scrive_e_si_ritrova_filtrando(logged_client, primi):
    creata = await logged_client.post("/api/v1/recipes", json=_corpo(category="Primi piatti"))

    assert creata.status_code == 201, creata.text
    assert creata.json()["category"] == "Primi piatti"
    trovate = (
        await logged_client.get("/api/v1/recipes/search?category=Primi%20piatti")
    ).json()
    assert "Pasta e ceci" in [r["title"] for r in trovate]


async def test_una_categoria_che_il_ricettario_non_ha_e_un_422(logged_client, db_session, primi):
    risposta = await logged_client.post("/api/v1/recipes", json=_corpo(category="primi"))

    assert risposta.status_code == 422
    assert "scegline una dall'elenco" in risposta.json()["detail"]
    quante = await db_session.scalar(
        select(func.count()).select_from(Recipe).where(Recipe.title == "Pasta e ceci")
    )
    assert quante == 0


async def test_senza_categoria_resta_senza(logged_client):
    creata = await logged_client.post("/api/v1/recipes", json=_corpo())
    assert creata.status_code == 201
    assert creata.json()["category"] is None
