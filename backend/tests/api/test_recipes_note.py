"""La nota di una riga si corregge e si toglie dal modulo (piano 20).

Il modulo non manda una nota vuota; ma l'autorità è qui: una nota vuota o di soli spazi si
salva `null`, e gli spazi ai bordi non fanno parte della nota.
"""

import pytest
import pytest_asyncio

from app.db.models.ingredient import IngredientCategory
from app.repositories.ingredients import create_ingredient


@pytest_asyncio.fixture
async def pasta(db_session):
    voce = await create_ingredient(db_session, "pasta", "Pasta", IngredientCategory.CEREALI)
    await db_session.commit()
    return voce


def _corpo(righe):
    return {
        "title": "Pasta al burro", "description": None, "category": None,
        "instructions": "Cuoci.", "servings": 2, "cost": None, "ingredients": righe,
    }


def _riga(pasta, note):
    return {"ingredient_id": str(pasta.id), "role": "primary", "quantity_text": "320 g", "note": note}


async def _scritta(client, pasta, note="al dente"):
    risposta = await client.post(
        "/api/v1/recipes", json={**_corpo([_riga(pasta, note)]), "source": "manual"}
    )
    assert risposta.status_code == 201, risposta.text
    return risposta.json()


async def _modifica(client, ricetta_id, pasta, note):
    return await client.put(f"/api/v1/recipes/{ricetta_id}", json=_corpo([_riga(pasta, note)]))


async def test_la_nota_si_corregge_con_la_modifica(logged_client, pasta):
    ricetta = await _scritta(logged_client, pasta)

    risposta = await _modifica(logged_client, ricetta["id"], pasta, "molto al dente")

    assert risposta.status_code == 200, risposta.text
    assert risposta.json()["ingredients"][0]["note"] == "molto al dente"
    riletta = (await logged_client.get(f"/api/v1/recipes/{ricetta['id']}")).json()
    assert riletta["ingredients"][0]["note"] == "molto al dente"


@pytest.mark.parametrize("vuota", ["", "   "])
async def test_una_nota_vuota_o_di_soli_spazi_si_salva_null(logged_client, pasta, vuota):
    ricetta = await _scritta(logged_client, pasta)

    risposta = await _modifica(logged_client, ricetta["id"], pasta, vuota)

    assert risposta.status_code == 200, risposta.text
    assert risposta.json()["ingredients"][0]["note"] is None


async def test_gli_spazi_ai_bordi_della_nota_non_si_salvano(logged_client, pasta):
    ricetta = await _scritta(logged_client, pasta, note="  da grattugiare  ")

    assert ricetta["ingredients"][0]["note"] == "da grattugiare"


async def test_la_nota_arriva_a_300_caratteri_e_non_oltre(logged_client, pasta):
    ricetta = await _scritta(logged_client, pasta)

    assert (await _modifica(logged_client, ricetta["id"], pasta, "a" * 301)).status_code == 422
    assert (await _modifica(logged_client, ricetta["id"], pasta, "a" * 300)).status_code == 200


async def test_una_riga_nuova_porta_la_sua_nota(logged_client):
    risposta = await logged_client.post("/api/v1/recipes", json={
        **_corpo([{"name": "zz nota", "category": "verdura", "role": "primary", "note": "a cubetti"}]),
        "source": "manual",
    })

    assert risposta.status_code == 201, risposta.text
    assert risposta.json()["ingredients"][0]["note"] == "a cubetti"
