"""Le rotte dei pesi e dei nutrienti di una ricetta (S4, fetta 2).

Il mondo di prova si salva con `commit`, come in `test_nutrition.py`: una rotta che
rifiuta fa `rollback`. Si tengono gli id.
"""

import uuid
from decimal import Decimal

import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient
from app.db.models.recipe import RecipeSource
from app.db.models.unit import Unit
from app.domain.ciqual import CiqualRow
from app.repositories.ciqual import upsert_foods
from app.repositories.recipes import create_recipe
from app.services.ingredient_nutrition import choose_food
from app.services.unit_grams import set_grams

BASE = "/api/v1/ingredients"


@pytest_asyncio.fixture
async def mondo(db_session):
    await upsert_foods(
        db_session,
        [
            CiqualRow("90003", "Pâtes sèches, crues", None, {"kcal": 357.0}),
            CiqualRow("90001", "Tomate, crue", None, {"kcal": 18.0}),
            CiqualRow("90005", "Ail, cru", None, {"kcal": 131.0}),
            CiqualRow("90006", "Huile d'olive vierge extra", None, {"kcal": 900.0}),
            CiqualRow("90009", "Oeuf, cru", None, {"kcal": 140.0}),
        ],
    )
    voci = {
        nome: Ingredient(name=nome, display_name=nome.capitalize(), category=reparto)
        for nome, reparto in [
            ("pasta", "cereali"), ("pomodoro", "verdura"), ("aglio", "verdura"),
            ("olio di oliva", "condimenti"), ("basilico", "spezie"), ("uova", "altro"), ("detersivo", "casa"),
        ]
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    ricetta = await create_recipe(
        db_session, title="Pasta al pomodoro", description=None, instructions="Si cucina.", servings=2,
        source=RecipeSource.MANUAL, source_ref=None, embedding=None,
        ingredients=[
            (voci["pasta"].id, "primary", "180 g", None), (voci["pomodoro"].id, "primary", "400 g", None),
            (voci["aglio"].id, "secondary", "1 spicchio", None),
            (voci["olio di oliva"].id, "secondary", "2 cucchiai", None),
            (voci["basilico"].id, "secondary", "q.b.", None), (voci["uova"].id, "primary", "2", None),
        ],
    )
    unita = {
        chiave: (await db_session.execute(select(Unit.id).where(Unit.key == chiave))).scalar_one()
        for chiave in ("g", "spicchio", "cucchiai")
    }
    for nome, codice in [("pasta", "90003"), ("pomodoro", "90001"), ("aglio", "90005"), ("olio di oliva", "90006")]:
        await choose_food(db_session, voci[nome].id, codice)
    await set_grams(db_session, voci["olio di oliva"].id, unita["cucchiai"], Decimal("12"))
    ids = {nome: str(voce.id) for nome, voce in voci.items()} | {
        f"unita {chiave}": str(valore) for chiave, valore in unita.items()
    } | {"ricetta": str(ricetta.id)}
    await db_session.commit()
    return ids


async def test_i_valori_portano_i_pesi(logged_client, mondo):
    risposta = await logged_client.get(f"{BASE}/{mondo['aglio']}/nutrition")

    assert risposta.status_code == 200
    assert risposta.json()["weights"] == [
        {"unit": mondo["unita spicchio"], "unit_label": "spicchio", "grams": None,
         "state": "undecided", "decided_by": None},
    ]


async def test_un_peso_a_mano_si_scrive_e_si_annulla(logged_client, mondo):
    percorso = f"{BASE}/{mondo['aglio']}/unit-grams/{mondo['unita spicchio']}"

    scritto = await logged_client.put(percorso, json={"grams": 5})
    assert scritto.status_code == 200
    assert scritto.json()["weights"][0] == {
        "unit": mondo["unita spicchio"], "unit_label": "spicchio", "grams": 5.0,
        "state": "decided", "decided_by": "human",
    }

    annullato = await logged_client.delete(percorso)
    assert annullato.status_code == 200
    assert annullato.json()["weights"][0]["state"] == "undecided"


async def test_il_pezzo_si_scrive_con_la_parola(logged_client, mondo):
    risposta = await logged_client.put(f"{BASE}/{mondo['uova']}/unit-grams/pezzo", json={"grams": 50})

    assert risposta.status_code == 200
    assert [(p["unit"], p["grams"]) for p in risposta.json()["weights"]] == [("pezzo", 50.0)]


async def test_i_rifiuti_e_le_unita_che_non_ci_sono(logged_client, mondo):
    grammi = await logged_client.put(f"{BASE}/{mondo['pasta']}/unit-grams/{mondo['unita g']}", json={"grams": 1})
    assert grammi.status_code == 409
    assert grammi.json() == {
        "code": "measured_unit", "detail": "«g» è un'unità di peso o di volume: i grammi si contano da sé.",
    }

    troppi = await logged_client.put(f"{BASE}/{mondo['aglio']}/unit-grams/{mondo['unita spicchio']}", json={"grams": 6000})
    assert troppi.status_code == 409
    assert troppi.json()["code"] == "bad_grams"

    non_cibo = await logged_client.put(f"{BASE}/{mondo['detersivo']}/unit-grams/pezzo", json={"grams": 10})
    assert (non_cibo.status_code, non_cibo.json()["code"]) == (409, "non_food")

    for unita in (str(uuid.uuid4()), "abc"):
        assert (await logged_client.put(f"{BASE}/{mondo['aglio']}/unit-grams/{unita}", json={"grams": 5})).status_code == 404
    assert (await logged_client.put(f"{BASE}/{uuid.uuid4()}/unit-grams/pezzo", json={"grams": 5})).status_code == 404


async def test_i_nutrienti_di_una_ricetta(logged_client, mondo):
    risposta = await logged_client.get(f"/api/v1/recipes/{mondo['ricetta']}/nutrition")

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert (corpo["basis"], corpo["servings"], corpo["lines_total"], corpo["lines_counted"]) == (
        "serving", 2, 6, 3,
    )
    # pasta 642,6 + pomodoro 72 + olio 216 = 930,6 su due porzioni
    assert corpo["nutrients"][0] == {
        "key": "kcal", "label": "Energia", "unit": "kcal", "main": True, "value": 465.0, "lines": 3,
    }
    assert corpo["nutrients"][1] == {
        "key": "protein", "label": "Proteine", "unit": "g", "main": True, "value": None, "lines": 0,
    }
    assert corpo["missing"] == [
        {"ingredient_id": mondo["aglio"], "ingredient_name": "aglio", "quantity_text": "1 spicchio",
         "reason": "no_weight", "unit_label": "spicchio"},
        {"ingredient_id": mondo["basilico"], "ingredient_name": "basilico", "quantity_text": "q.b.",
         "reason": "no_quantity", "unit_label": None},
        {"ingredient_id": mondo["uova"], "ingredient_name": "uova", "quantity_text": "2",
         "reason": "no_nutrients", "unit_label": None},
    ]
    assert corpo["source"] == "CIQUAL 2025"


async def test_una_ricetta_che_non_c_e_e_un_404(logged_client, mondo):
    assert (await logged_client.get(f"/api/v1/recipes/{uuid.uuid4()}/nutrition")).status_code == 404


async def test_le_rotte_nuove_chiedono_l_accesso(client, mondo):
    assert (await client.get(f"/api/v1/recipes/{mondo['ricetta']}/nutrition")).status_code == 401
    percorso = f"{BASE}/{mondo['uova']}/unit-grams/pezzo"
    assert (await client.put(percorso, json={"grams": 50})).status_code == 401
