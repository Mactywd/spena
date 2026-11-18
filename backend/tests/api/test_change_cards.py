"""Le rotte delle schede dei cambi (spec 2026-11-12 §6.2, piano 6c Task 4)."""

from datetime import date

import pytest_asyncio

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.domain.meals import MealSlot, MealStatus
from app.domain.rules import PantryStatus
from app.repositories.shopping import add_item
from app.services.change_cards import (
    ListProposal,
    PantryProposal,
    apply_card,
    create_empty_card,
    open_cards_for_meals,
    propose_card,
)
from app.services.meals import create_meal

C = "/api/v1/change-cards"
A, L, F = PantryStatus.AVAILABLE, PantryStatus.LOW, PantryStatus.FINISHED


@pytest_asyncio.fixture
async def mondo(db_session):
    def ing(name, category):
        return Ingredient(name=name, display_name=name.capitalize(), category=category)

    ingredienti = {
        "ricotta": ing("ricotta", IngredientCategory.LATTICINI),
        "parmigiano": ing("parmigiano", IngredientCategory.LATTICINI),
        "pasta": ing("pasta", IngredientCategory.CONDIMENTI),
    }
    db_session.add_all(ingredienti.values())
    await db_session.flush()
    voci = {n: PantryItem(ingredient_id=i.id, status=A) for n, i in ingredienti.items()}
    db_session.add_all(voci.values())
    await db_session.flush()
    pasto = await create_meal(
        db_session, day=date(2026, 11, 20), slot=MealSlot.DINNER, dish="Pasta alla ricotta"
    )
    altro = await create_meal(
        db_session, day=date(2026, 11, 21), slot=MealSlot.LUNCH, dish="Risotto"
    )
    bozza = await create_meal(
        db_session, day=date(2026, 11, 22), slot=MealSlot.DINNER, dish="Lasagne",
        status=MealStatus.DRAFT,
    )
    await db_session.commit()
    return {"ing": ingredienti, "voci": voci, "pasto": pasto, "altro": altro, "bozza": bozza}


async def scheda(session, mondo, *, lista_gia=False):
    v = mondo["voci"]
    if lista_gia:
        await add_item(session, "Ricotta", mondo["ing"]["ricotta"].id)
    card = await propose_card(
        session, meals=[mondo["pasto"]],
        pantry=[PantryProposal(v["ricotta"].id, F), PantryProposal(v["parmigiano"].id, L)],
        shopping=[ListProposal(mondo["ing"]["ricotta"].id, "Ricotta")],
    )
    await session.commit()
    return card.id


def riga(body, kind, label):
    (r,) = [r for r in body["rows"] if r["kind"] == kind and r["label"] == label]
    return r


async def test_leggere_una_scheda(logged_client, db_session, mondo):
    card_id = await scheda(db_session, mondo, lista_gia=True)
    body = (await logged_client.get(f"{C}/{card_id}")).json()
    assert body["status"] == "proposed" and body["kind"] == "forward"
    assert [m["dish"] for m in body["meals"]] == ["Pasta alla ricotta"]
    r = riga(body, "pantry", "ricotta")
    assert (r["from_status"], r["to_status"], r["checked"], r["editable"]) == (
        "available", "finished", True, True,
    )
    assert r["listed"] is False
    lista = riga(body, "list", "ricotta")
    assert lista["listed"] is True and lista["editable"] is False
    assert (await logged_client.get(f"{C}/{__import__('uuid').uuid4()}")).status_code == 404


async def test_ora_si_legge_dal_vivo(logged_client, db_session, mondo):
    card_id = await scheda(db_session, mondo)
    item = mondo["voci"]["ricotta"]
    res = await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"status": "low"})
    assert res.status_code == 200
    body = (await logged_client.get(f"{C}/{card_id}")).json()
    assert riga(body, "pantry", "ricotta")["from_status"] == "low"


async def test_applicare_dalla_rotta(logged_client, db_session, mondo):
    card_id = await scheda(db_session, mondo)
    body = (await logged_client.get(f"{C}/{card_id}")).json()
    parmigiano = riga(body, "pantry", "parmigiano")
    res = await logged_client.post(
        f"{C}/{card_id}/apply", json={"rows": [{"id": parmigiano["id"], "checked": False}]}
    )
    assert res.status_code == 200
    out = res.json()
    assert out["status"] == "applied" and out["applied_at"] is not None
    assert riga(out, "pantry", "ricotta")["from_status"] == "available"
    assert riga(out, "pantry", "parmigiano")["applied"] is False
    pantry = (await logged_client.get("/api/v1/pantry")).json()
    stati = {p["ingredient_name"]: p["status"] for p in pantry}
    assert stati["ricotta"] == "finished" and stati["parmigiano"] == "available"
    lista = (await logged_client.get("/api/v1/shopping-list")).json()
    assert [i["raw_text"].lower() for i in lista].count("ricotta") == 1


async def test_applicare_due_volte_dalla_rotta(logged_client, db_session, mondo):
    card_id = await scheda(db_session, mondo)
    assert (await logged_client.post(f"{C}/{card_id}/apply", json={"rows": []})).status_code == 200
    res = await logged_client.post(f"{C}/{card_id}/apply", json={"rows": []})
    assert res.status_code == 409
    body = res.json()
    assert body["code"] == "card_applied" and body["detail"] == "La scheda era già applicata."
    assert body["card"]["status"] == "applied"
    lista = (await logged_client.get("/api/v1/shopping-list")).json()
    assert [i["raw_text"].lower() for i in lista].count("ricotta") == 1


async def test_scartare_e_poi_applicare(logged_client, db_session, mondo):
    card_id = await scheda(db_session, mondo)
    res = await logged_client.post(f"{C}/{card_id}/discard")
    assert res.status_code == 200 and res.json()["status"] == "discarded"
    res = await logged_client.post(f"{C}/{card_id}/apply", json={"rows": []})
    assert res.status_code == 409
    assert res.json()["code"] == "card_discarded"
    assert res.json()["detail"] == "La scheda è stata scartata."


async def test_righe_a_mano(logged_client, db_session, mondo):
    card = await create_empty_card(db_session, mondo["pasto"])
    bozza = await propose_card(
        db_session, meals=[mondo["bozza"]], pantry=[], shopping=[ListProposal(None, "basilico")]
    )
    await db_session.commit()
    # dopo un 409 la sessione è annullata: gli id si tengono prima
    card_id, bozza_id, item_id = card.id, bozza.id, mondo["voci"]["pasta"].id
    res = await logged_client.post(f"{C}/{card_id}/rows", json={"pantry_item_id": str(item_id)})
    assert res.status_code == 200
    assert [r["label"] for r in res.json()["rows"]] == ["pasta"]
    res = await logged_client.post(f"{C}/{card_id}/rows", json={"pantry_item_id": str(item_id)})
    assert res.status_code == 409 and res.json()["code"] == "row_exists"
    assert res.json()["detail"] == "Questa voce è già nella scheda."
    assert len(res.json()["card"]["rows"]) == 1
    res = await logged_client.post(f"{C}/{card_id}/rows", json={"raw_text": "  Olio  "})
    assert res.status_code == 200
    assert riga(res.json(), "list", "Olio")["checked"] is True
    res = await logged_client.post(f"{C}/{bozza_id}/rows", json={"pantry_item_id": str(item_id)})
    assert res.status_code == 409 and res.json()["code"] == "list_only"
    assert res.json()["detail"] == "Per una bozza la scheda ha solo le righe della lista."
    res = await logged_client.post(f"{C}/{card_id}/rows", json={})
    assert res.status_code == 422


async def test_le_schede_proposte(logged_client, db_session, mondo):
    proposta = await scheda(db_session, mondo)
    v = mondo["voci"]
    altra = await propose_card(
        db_session, meals=[mondo["altro"]], pantry=[PantryProposal(v["pasta"].id, L)], shopping=[]
    )
    await apply_card(db_session, altra.id, [])
    await db_session.commit()
    ids = [c["id"] for c in (await logged_client.get(f"{C}?status=proposed")).json()]
    assert ids == [str(proposta)]
    applicate = [c["id"] for c in (await logged_client.get(f"{C}?status=applied")).json()]
    assert applicate == [str(altra.id)]


async def test_rendere_ufficiale_una_bozza_apre_la_scheda_vuota(
    logged_client, db_session, mondo
):
    bozza = mondo["bozza"]
    res = await logged_client.patch(
        f"/api/v1/meals/{bozza.id}", json={"status": "official"}
    )
    assert res.status_code == 200
    open_id = res.json()["open_card_id"]
    assert open_id is not None
    card = (await logged_client.get(f"{C}/{open_id}")).json()
    assert card["title"] == "Per «Lasagne»: compila a mano" and card["rows"] == []
    # correggere solo il piatto di un ufficiale non crea schede
    res = await logged_client.patch(
        f"/api/v1/meals/{mondo['altro'].id}", json={"dish": "Risotto allo zafferano"}
    )
    assert res.status_code == 200 and res.json()["open_card_id"] is None
    proposte = (await logged_client.get(f"{C}?status=proposed")).json()
    assert [c["id"] for c in proposte] == [open_id]
    # e la scheda aperta si vede anche dalla settimana
    week = (await logged_client.get("/api/v1/meals/week?of=2026-11-20")).json()
    aperte = {m["dish"]: m["open_card_id"] for m in week["meals"]}
    assert aperte["Lasagne"] == open_id and aperte["Risotto allo zafferano"] is None


async def test_cancellare_un_pasto_lascia_l_inversa_fra_le_proposte(
    logged_client, db_session, mondo
):
    card_id = await scheda(db_session, mondo)
    await apply_card(db_session, card_id, [])
    await db_session.commit()
    res = await logged_client.delete(f"/api/v1/meals/{mondo['pasto'].id}")
    assert res.status_code == 204
    proposte = (await logged_client.get(f"{C}?status=proposed")).json()
    assert [c["kind"] for c in proposte] == ["inverse"]


async def test_la_scheda_aperta_piu_recente_per_pasto_con_una_query_sola(db_session, mondo):
    v = mondo["voci"]
    vecchia = await propose_card(
        db_session, meals=[mondo["pasto"], mondo["altro"]],
        pantry=[PantryProposal(v["pasta"].id, L)], shopping=[],
    )
    nuova = await propose_card(
        db_session, meals=[mondo["pasto"]], pantry=[PantryProposal(v["ricotta"].id, L)],
        shopping=[],
    )
    applicata = await propose_card(
        db_session, meals=[mondo["bozza"], mondo["altro"]], pantry=[],
        shopping=[ListProposal(None, "basilico")],
    )
    await apply_card(db_session, applicata.id, [])
    found = await open_cards_for_meals(
        db_session, [mondo["pasto"].id, mondo["altro"].id, mondo["bozza"].id]
    )
    assert found == {mondo["pasto"].id: nuova.id, mondo["altro"].id: vecchia.id}
    assert await open_cards_for_meals(db_session, []) == {}
