import uuid
from types import SimpleNamespace

from llm_fakes import FakeLlm

import app.services.llm as llm
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import RecipeSource
from app.repositories.recipes import create_recipe
from app.services.ai_recipes import SYSTEM_PROMPT, VARIANT_SYSTEM_PROMPT

U = "/api/v1/utensils"


async def test_senza_utensili_l_elenco_e_vuoto(logged_client):
    risposta = await logged_client.get(U)
    assert risposta.status_code == 200
    assert risposta.json() == []


async def test_aggiungere_correggere_togliere(logged_client):
    creato = await logged_client.post(U, json={"name": "padella antiaderente", "note": "da 24 cm"})
    assert creato.status_code == 201
    utensile = creato.json()
    assert utensile["name"] == "padella antiaderente" and utensile["note"] == "da 24 cm"
    assert set(utensile) == {"id", "name", "note"}

    corretto = await logged_client.patch(f"{U}/{utensile['id']}", json={"note": "da 28 cm"})
    assert corretto.status_code == 200
    assert corretto.json() == {**utensile, "note": "da 28 cm"}

    rinominato = await logged_client.patch(f"{U}/{utensile['id']}", json={"name": "padella"})
    assert rinominato.json() == {**utensile, "name": "padella", "note": "da 28 cm"}

    assert (await logged_client.get(U)).json() == [rinominato.json()]
    assert (await logged_client.delete(f"{U}/{utensile['id']}")).status_code == 204
    assert (await logged_client.get(U)).json() == []


async def test_l_elenco_va_per_nome_senza_badare_alle_maiuscole(logged_client):
    for nome in ["padella", "Frusta elettrica", "colino"]:
        await logged_client.post(U, json={"name": nome})
    assert [u["name"] for u in (await logged_client.get(U)).json()] == [
        "colino", "Frusta elettrica", "padella",
    ]


async def test_il_nome_e_la_nota_si_scrivono_su_una_riga_sola(logged_client):
    # un testo incollato non deve portare righe nuove nel prompt (decisione 6)
    creato = await logged_client.post(
        U, json={"name": "  padella\n\n\tantiaderente  ", "note": "\n da 24\tcm "}
    )
    assert creato.json()["name"] == "padella antiaderente"
    assert creato.json()["note"] == "da 24 cm"
    corretto = await logged_client.patch(
        f"{U}/{creato.json()['id']}", json={"name": "frusta\r\nelettrica"}
    )
    assert corretto.json()["name"] == "frusta elettrica"


async def test_un_nome_vuoto_o_troppo_lungo_e_un_422(logged_client):
    assert (await logged_client.post(U, json={"name": "   "})).status_code == 422
    assert (await logged_client.post(U, json={"name": "x" * 121})).status_code == 422
    assert (await logged_client.post(U, json={"name": "x" * 120})).status_code == 201
    assert (await logged_client.post(U, json={"name": "colino", "note": "y" * 201})).status_code == 422
    creato = (await logged_client.post(U, json={"name": "colino"})).json()
    assert (await logged_client.patch(f"{U}/{creato['id']}", json={"name": "  "})).status_code == 422
    assert (await logged_client.patch(f"{U}/{creato['id']}", json={"name": None})).status_code == 422


async def test_una_nota_vuota_e_nessuna_nota(logged_client):
    creato = (await logged_client.post(U, json={"name": "colino", "note": "   "})).json()
    assert creato["note"] is None
    con_nota = (await logged_client.patch(f"{U}/{creato['id']}", json={"note": "a maglia fine"})).json()
    assert con_nota["note"] == "a maglia fine"
    assert (await logged_client.patch(f"{U}/{creato['id']}", json={"note": None})).json()["note"] is None
    await logged_client.patch(f"{U}/{creato['id']}", json={"note": "a maglia fine"})
    assert (await logged_client.patch(f"{U}/{creato['id']}", json={"note": ""})).json()["note"] is None


async def test_una_patch_senza_campi_e_un_400(logged_client):
    creato = (await logged_client.post(U, json={"name": "colino"})).json()
    assert (await logged_client.patch(f"{U}/{creato['id']}", json={})).status_code == 400


async def test_un_utensile_che_non_c_e_e_un_404(logged_client):
    assente = uuid.uuid4()
    assert (await logged_client.patch(f"{U}/{assente}", json={"name": "colino"})).status_code == 404
    assert (await logged_client.delete(f"{U}/{assente}")).status_code == 404


async def test_due_utensili_con_lo_stesso_nome_convivono(logged_client):
    # due padelle di misure diverse sono due utensili veri (decisione 5)
    await logged_client.post(U, json={"name": "padella antiaderente", "note": "da 24 cm"})
    await logged_client.post(U, json={"name": "padella antiaderente", "note": "da 28 cm"})
    assert sorted(u["note"] for u in (await logged_client.get(U)).json()) == ["da 24 cm", "da 28 cm"]


async def test_senza_sessione_non_si_legge_ne_si_scrive(client):
    assert (await client.get(U)).status_code == 401
    assert (await client.post(U, json={"name": "colino"})).status_code == 401


async def test_un_valore_che_non_e_testo_e_un_422(logged_client):
    assert (await logged_client.post(U, json={"name": 123})).status_code == 422
    assert (await logged_client.post(U, json={"name": ["a"]})).status_code == 422
    assert (await logged_client.post(U, json={"name": "a", "note": 5})).status_code == 422
    creato = (await logged_client.post(U, json={"name": "colino"})).json()
    assert (await logged_client.patch(f"{U}/{creato['id']}", json={"name": 123})).status_code == 422
    assert (await logged_client.patch(f"{U}/{creato['id']}", json={"note": 5})).status_code == 422


BOZZA = {
    "title": "Frittata", "description": None, "instructions": "1. Sbatti le uova.",
    "servings": 1, "cost": 1, "ingredients": [],
}


def _trasporto_finto(monkeypatch, *risposte) -> FakeLlm:
    """Sostituisce il trasporto HTTP solo dentro `app.services.llm`: la rotta, la
    sessione e `complete_json` sono quelli veri. Non si tocca `httpx.AsyncClient` nel
    modulo `httpx`, che è lo stesso nome del client di prova di `conftest.py`."""
    from app.core.config import get_settings

    finto = FakeLlm(*risposte)
    monkeypatch.setattr(llm, "httpx", SimpleNamespace(AsyncClient=lambda **_: finto))
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    get_settings.cache_clear()
    return finto


async def test_la_rotta_della_bozza_manda_gli_utensili_scritti_dalla_rotta(logged_client, monkeypatch):
    await logged_client.post(U, json={"name": "frusta elettrica"})
    finto = _trasporto_finto(monkeypatch, BOZZA)
    risposta = await logged_client.post("/api/v1/recipes/ai-draft", json={"prompt": "una frittata"})
    assert risposta.status_code == 200
    sistema = finto.bodies[0]["messages"][0]["content"]
    assert "\n- frusta elettrica\n" in sistema
    assert sistema.startswith(SYSTEM_PROMPT)


async def test_la_rotta_della_variante_manda_gli_utensili(logged_client, db_session, monkeypatch):
    await logged_client.post(U, json={"name": "padella antiaderente", "note": "da 24 cm"})
    uova = Ingredient(name="uova", display_name="Uova", category=IngredientCategory.ALTRO)
    db_session.add(uova)
    await db_session.flush()
    ricetta = await create_recipe(
        db_session, title="Frittata", description=None, instructions="1. Sbatti le uova.",
        servings=1, source=RecipeSource.MANUAL, source_ref=None,
        ingredients=[(uova.id, "primary", "2", None)], embedding=None,
    )
    finto = _trasporto_finto(monkeypatch, BOZZA)
    risposta = await logged_client.post(
        f"/api/v1/recipes/{ricetta.id}/ai-variant", json={"prompt": "senza forno"}
    )
    assert risposta.status_code == 200
    sistema = finto.bodies[0]["messages"][0]["content"]
    assert "\n- padella antiaderente (da 24 cm)\n" in sistema
    assert sistema.startswith(VARIANT_SYSTEM_PROMPT)
