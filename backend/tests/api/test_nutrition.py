"""Le rotte dei valori nutrizionali di un ingrediente e della ricerca in CIQUAL (S4, fetta 1).

Il mondo di prova si salva con `commit`: una rotta che rifiuta fa `rollback`, e con
`join_transaction_mode="create_savepoint"` quel rollback porterebbe via quel che il test
avesse solo scritto con `flush` (come in `test_registry_ingredients.py`). Si tengono gli
id, non gli oggetti.
"""

import uuid

import pytest_asyncio

from app.db.models.ingredient import Ingredient
from app.domain.ciqual import CiqualRow
from app.repositories.ciqual import upsert_foods

CITAZIONE = "Anses. 2025. Table de composition nutritionnelle des aliments Ciqual"


@pytest_asyncio.fixture
async def mondo(db_session):
    await upsert_foods(
        db_session,
        [
            CiqualRow(
                "90001", "Tomate, crue", "légumes",
                {"kcal": 18.0, "protein": 0.86, "carbs": 2.5, "fat": 0.3, "iron": 0.3, "vitamin_c": 14.0},
            ),
            CiqualRow("90002", "Tomate, concentré", "légumes", {"kcal": 77.0}),
        ],
    )
    pomodoro = Ingredient(name="pomodoro", display_name="Pomodoro", category="verdura")
    detersivo = Ingredient(name="detersivo", display_name="Detersivo", category="casa")
    db_session.add_all([pomodoro, detersivo])
    await db_session.flush()
    ids = {"pomodoro": str(pomodoro.id), "detersivo": str(detersivo.id)}
    await db_session.commit()
    return ids


async def test_un_ingrediente_da_decidere(logged_client, mondo):
    risposta = await logged_client.get(f"/api/v1/ingredients/{mondo['pomodoro']}/nutrition")

    assert risposta.status_code == 200
    assert risposta.json() == {
        "state": "undecided", "decided_by": None, "food": None, "nutrients": [],
        "source": "CIQUAL 2025", "citation": CITAZIONE,
    }


async def test_la_scelta_a_mano_e_i_nutrienti_per_100_g(logged_client, mondo):
    risposta = await logged_client.put(
        f"/api/v1/ingredients/{mondo['pomodoro']}/nutrition", json={"ciqual_code": "90001"}
    )

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert (corpo["state"], corpo["decided_by"]) == ("food", "human")
    assert corpo["food"] == {"code": "90001", "name_fr": "Tomate, crue", "group_fr": "légumes"}
    # gli otto principali sempre, nell'ordine dell'etichetta, anche vuoti; poi gli altri
    # solo se ci sono, nell'ordine del vocabolario (le vitamine prima dei minerali)
    assert [(n["key"], n["main"], n["value"]) for n in corpo["nutrients"]] == [
        ("kcal", True, 18.0), ("protein", True, 0.86), ("carbs", True, 2.5),
        ("sugars", True, None), ("fat", True, 0.3), ("saturated_fat", True, None),
        ("fiber", True, None), ("salt", True, None),
        ("vitamin_c", False, 14.0), ("iron", False, 0.3),
    ]
    assert corpo["nutrients"][0] == {
        "key": "kcal", "label": "Energia", "unit": "kcal", "main": True, "value": 18.0,
    }


async def test_nessun_alimento_adatto(logged_client, mondo):
    risposta = await logged_client.put(
        f"/api/v1/ingredients/{mondo['pomodoro']}/nutrition", json={"ciqual_code": None}
    )

    assert risposta.status_code == 200
    assert (risposta.json()["state"], risposta.json()["food"], risposta.json()["nutrients"]) == (
        "none", None, [],
    )


async def test_una_voce_non_alimentare_si_rifiuta(logged_client, mondo):
    risposta = await logged_client.put(
        f"/api/v1/ingredients/{mondo['detersivo']}/nutrition", json={"ciqual_code": "90001"}
    )

    assert risposta.status_code == 409
    assert risposta.json() == {
        "code": "non_food",
        "detail": "«Detersivo» non è un alimento: non ha valori nutrizionali.",
    }
    stato = await logged_client.get(f"/api/v1/ingredients/{mondo['detersivo']}/nutrition")
    assert stato.json()["state"] == "non_food"


async def test_un_codice_sconosciuto_si_rifiuta(logged_client, mondo):
    risposta = await logged_client.put(
        f"/api/v1/ingredients/{mondo['pomodoro']}/nutrition", json={"ciqual_code": "12345"}
    )

    assert risposta.status_code == 409
    assert risposta.json()["code"] == "unknown_food"


async def test_annullare_torna_a_da_decidere(logged_client, mondo):
    percorso = f"/api/v1/ingredients/{mondo['pomodoro']}/nutrition"
    await logged_client.put(percorso, json={"ciqual_code": "90001"})

    risposta = await logged_client.delete(percorso)

    assert risposta.status_code == 200
    assert risposta.json()["state"] == "undecided"


async def test_un_ingrediente_che_non_c_e_e_un_404(logged_client, mondo):
    percorso = f"/api/v1/ingredients/{uuid.uuid4()}/nutrition"

    assert (await logged_client.get(percorso)).status_code == 404
    assert (await logged_client.put(percorso, json={"ciqual_code": None})).status_code == 404
    assert (await logged_client.delete(percorso)).status_code == 404


async def test_la_ricerca_nella_tabella(logged_client, mondo):
    risposta = await logged_client.get("/api/v1/ciqual/foods", params={"q": "90002"})

    assert risposta.status_code == 200
    assert risposta.json()[0] == {
        "code": "90002", "name_fr": "Tomate, concentré", "group_fr": "légumes",
    }
    trovati = await logged_client.get("/api/v1/ciqual/foods", params={"q": "tomate"})
    assert {alimento["code"] for alimento in trovati.json()} == {"90001", "90002"}


async def test_le_rotte_chiedono_l_accesso(client):
    assert (await client.get("/api/v1/ciqual/foods", params={"q": "tomate"})).status_code == 401
    percorso = f"/api/v1/ingredients/{uuid.uuid4()}/nutrition"
    assert (await client.get(percorso)).status_code == 401
