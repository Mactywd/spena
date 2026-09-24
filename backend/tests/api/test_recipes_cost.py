"""R9: il costo della ricetta, da 1 a 5, annullabile.

Spec: docs/superpowers/specs/2026-09-24-costo-ricetta-design.md
"""

import pytest
from sqlalchemy.exc import IntegrityError

from app.db.models.recipe import Recipe, RecipeSource


async def _create(client, **extra):
    response = await client.post("/api/v1/recipes", json={
        "title": "Pasta e ceci", "instructions": "Cuoci.", "source": "manual", **extra,
    })
    assert response.status_code == 201, response.text
    return response.json()


async def test_una_ricetta_senza_costo_non_e_una_ricetta_da_uno(logged_client):
    body = await _create(logged_client)
    assert body["cost"] is None


async def test_il_costo_si_scrive_creando(logged_client):
    body = await _create(logged_client, cost=2)
    assert body["cost"] == 2
    detail = (await logged_client.get(f"/api/v1/recipes/{body['id']}")).json()
    assert detail["cost"] == 2


@pytest.mark.parametrize("cost", [0, 6, -1])
async def test_fuori_scala_e_un_422(logged_client, cost):
    response = await logged_client.post("/api/v1/recipes", json={
        "title": "x", "instructions": "x", "source": "manual", "cost": cost,
    })
    assert response.status_code == 422


async def test_la_scheda_del_ricettario_porta_il_costo(logged_client):
    created = await _create(logged_client, cost=4)
    found = (await logged_client.get("/api/v1/recipes/search")).json()
    assert [r["cost"] for r in found if r["id"] == created["id"]] == [4]


async def test_il_costo_si_cambia_dal_dettaglio(logged_client):
    created = await _create(logged_client)
    response = await logged_client.patch(
        f"/api/v1/recipes/{created['id']}", json={"cost": 3}
    )
    assert response.status_code == 200
    assert response.json()["cost"] == 3
    detail = (await logged_client.get(f"/api/v1/recipes/{created['id']}")).json()
    assert detail["cost"] == 3


async def test_il_costo_si_toglie_con_null(logged_client):
    created = await _create(logged_client, cost=5)
    response = await logged_client.patch(
        f"/api/v1/recipes/{created['id']}", json={"cost": None}
    )
    assert response.status_code == 200
    assert response.json()["cost"] is None


async def test_una_patch_senza_costo_non_lo_tocca(logged_client):
    """Assente e `null` sono due cose: la prima non chiede niente, la seconda azzera."""
    created = await _create(logged_client, cost=2)
    response = await logged_client.patch(f"/api/v1/recipes/{created['id']}", json={})
    assert response.status_code == 200
    assert response.json()["cost"] == 2


@pytest.mark.parametrize("cost", [0, 6, "tre", 2.5])
async def test_una_patch_fuori_scala_e_un_422(logged_client, cost):
    created = await _create(logged_client, cost=2)
    response = await logged_client.patch(
        f"/api/v1/recipes/{created['id']}", json={"cost": cost}
    )
    assert response.status_code == 422
    detail = (await logged_client.get(f"/api/v1/recipes/{created['id']}")).json()
    assert detail["cost"] == 2


async def test_una_patch_su_una_ricetta_che_non_esiste_e_un_404(logged_client):
    response = await logged_client.patch(
        "/api/v1/recipes/00000000-0000-0000-0000-000000000000", json={"cost": 1}
    )
    assert response.status_code == 404


async def test_una_patch_senza_sessione_e_rifiutata(client):
    response = await client.patch(
        "/api/v1/recipes/00000000-0000-0000-0000-000000000000", json={"cost": 1}
    )
    assert response.status_code == 401


async def test_il_database_rifiuta_un_costo_fuori_scala(db_session):
    """L'ultima linea: una scrittura che non passa dalla rotta non può metterne uno da 7."""
    db_session.add(Recipe(title="x", instructions="x", source=RecipeSource.MANUAL, cost=7))
    with pytest.raises(IntegrityError):
        await db_session.flush()
