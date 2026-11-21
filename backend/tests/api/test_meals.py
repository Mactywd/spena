import uuid
from datetime import date, timedelta

import pytest

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.domain.meals import MealSlot, MealStatus
from app.domain.rules import today_in_pantry
from app.repositories.recipes import create_recipe
from app.services.meals import create_meal

M = "/api/v1/meals"
L, D = MealSlot.LUNCH, MealSlot.DINNER


def d(n: int) -> date:
    return date(2026, 11, n)


async def pasto(session, giorno, slot, dish="Pizza", **kw):
    meal = await create_meal(session, day=giorno, slot=slot, dish=dish, **kw)
    await session.commit()
    return meal


async def ricetta(session, title="Frittata"):
    uova = Ingredient(name="uova", display_name="Uova", category=IngredientCategory.LATTICINI)
    session.add(uova)
    await session.flush()
    recipe = await create_recipe(
        session, title=title, description=None, instructions="Sbatti.", servings=2,
        source="manual", source_ref=None, ingredients=[(uova.id, "primary", "4", None)],
        embedding=[0.5] * 384,
    )
    await session.commit()
    return recipe


async def test_la_settimana_di_oggi(logged_client):
    body = (await logged_client.get(f"{M}/week")).json()
    oggi = today_in_pantry()
    assert body["today"] == oggi.isoformat()
    monday, sunday = date.fromisoformat(body["monday"]), date.fromisoformat(body["sunday"])
    assert monday <= oggi <= sunday
    assert monday.weekday() == 0
    assert date.fromisoformat(body["previous"]) == monday - timedelta(days=7)
    assert date.fromisoformat(body["next"]) == monday + timedelta(days=7)


# Il piano scrive lunedì 2026-11-10, ma è un martedì: il lunedì è il 9.
async def test_la_settimana_di_una_data_e_i_suoi_pasti_in_ordine(logged_client, db_session):
    await pasto(db_session, d(10), D, "Cena 10")
    await pasto(db_session, d(10), L, "Pranzo 10")
    await pasto(db_session, d(17), L, "Fuori settimana")
    body = (await logged_client.get(f"{M}/week", params={"of": "2026-11-12"})).json()
    assert body["monday"] == "2026-11-09"
    assert body["sunday"] == "2026-11-15"
    assert body["days"] == [f"2026-11-{n:02d}" for n in range(9, 16)]
    assert [(m["slot"], m["dish"]) for m in body["meals"]] == [
        ("lunch", "Pranzo 10"), ("dinner", "Cena 10"),
    ]
    assert {m["week"] for m in body["meals"]} == {"2026-11-09"}


async def test_una_bozza_passata_e_non_registrata(logged_client, db_session):
    bozza = await pasto(db_session, date(2026, 1, 5), L, "Bozza", status=MealStatus.DRAFT)
    ufficiale = await pasto(db_session, date(2026, 1, 5), D, "Ufficiale")
    assert (await logged_client.get(f"{M}/{bozza.id}")).json()["unrecorded"] is True
    assert (await logged_client.get(f"{M}/{ufficiale.id}")).json()["unrecorded"] is False


async def test_scrivere_un_pasto_a_mano(logged_client):
    corpo = {
        "day": "2026-11-11", "slot": "dinner", "dish": "  Frittata di spinaci  ",
        "sides": "piadina · banana",
    }
    r = await logged_client.post(M, json=corpo)
    assert r.status_code == 201
    out = r.json()
    assert out["dish"] == "Frittata di spinaci"
    assert out["sides"] == "piadina · banana"
    assert out["status"] == "official"
    assert out["recipe"] is None and out["leftover_of"] is None
    r2 = await logged_client.post(M, json={**corpo, "slot": "lunch", "sides": "  "})
    assert r2.status_code == 201 and r2.json()["sides"] is None


@pytest.mark.parametrize("piatto", ["", "   "])
async def test_un_piatto_vuoto_e_422(logged_client, piatto):
    r = await logged_client.post(M, json={"day": "2026-11-11", "slot": "lunch", "dish": piatto})
    assert r.status_code == 422


@pytest.mark.parametrize(
    ("metodo", "corpo"),
    [
        ("post", {"dish": 123}),
        ("post", {"sides": 5}),
        ("patch", {"dish": [1]}),
        ("patch", {"dish": None}),
    ],
)
async def test_un_piatto_o_accompagnamenti_non_testo_e_422(logged_client, db_session, metodo, corpo):
    if metodo == "post":
        r = await logged_client.post(
            M, json={"day": "2026-11-11", "slot": "lunch", "dish": "Pizza", **corpo}
        )
    else:
        m = await pasto(db_session, d(11), L, "Pizza")
        r = await logged_client.patch(f"{M}/{m.id}", json=corpo)
    assert r.status_code == 422


async def test_un_avanzo_valido_via_api(logged_client, db_session):
    origine = (await pasto(db_session, d(10), D, "Lasagne")).id
    r = await logged_client.post(
        M, json={"day": "2026-11-11", "slot": "lunch", "dish": "Lasagne fredde",
                 "leftover_of_id": str(origine)},
    )
    assert r.status_code == 201
    assert r.json()["leftover_of"]["id"] == str(origine)


async def test_un_avanzo_con_origine_dopo_il_posto_e_422(logged_client, db_session):
    dopo = (await pasto(db_session, d(12), D, "Dopo")).id
    r = await logged_client.post(
        M, json={"day": "2026-11-11", "slot": "lunch", "dish": "Avanzo",
                 "leftover_of_id": str(dopo)},
    )
    assert r.status_code == 422
    assert r.json()["code"] == "bad_leftover"


async def test_una_bozza_ufficiale_non_torna_bozza(logged_client, db_session):
    m = await pasto(db_session, d(11), L, "Pizza")
    r = await logged_client.patch(f"{M}/{m.id}", json={"status": "draft"})
    assert r.status_code == 422
    assert r.json()["code"] == "stays_official"


async def test_un_posto_occupato_e_409_con_chi_c_e(logged_client, db_session):
    await pasto(db_session, d(11), D, "Pizza")
    r = await logged_client.post(M, json={"day": "2026-11-11", "slot": "dinner", "dish": "Altro"})
    assert r.status_code == 409
    body = r.json()
    assert body["code"] == "slot_taken"
    assert body["detail"] == "C'è già «Pizza» in questo posto."
    assert body["occupant"]["dish"] == "Pizza"


async def test_correggere_e_spostare(logged_client, db_session):
    m = await pasto(db_session, d(11), D, "Frittata di spinaci", sides="banana")
    r = await logged_client.patch(
        f"{M}/{m.id}", json={"dish": "Frittata di zucchine", "sides": None}
    )
    assert r.status_code == 200
    assert r.json()["dish"] == "Frittata di zucchine" and r.json()["sides"] is None
    r = await logged_client.patch(f"{M}/{m.id}", json={"day": "2026-11-13", "slot": "lunch"})
    assert r.status_code == 200
    assert (r.json()["day"], r.json()["slot"], r.json()["week"]) == (
        "2026-11-13", "lunch", "2026-11-09",
    )


async def test_spostare_su_un_posto_occupato_con_replace(logged_client, db_session):
    m = (await pasto(db_session, d(11), D, "Mio")).id
    occupante = (await pasto(db_session, d(12), D, "Vecchio")).id  # il rollback scade gli oggetti
    corpo = {"day": "2026-11-12"}
    r = await logged_client.patch(f"{M}/{m}", json=corpo)
    assert r.status_code == 409
    assert r.json()["occupant"]["dish"] == "Vecchio"
    r = await logged_client.patch(f"{M}/{m}", json={**corpo, "replace": True})
    assert r.status_code == 200
    assert (await logged_client.get(f"{M}/{occupante}")).status_code == 404


async def test_eliminare_e_204_e_la_ricetta_fuori_dal_ricettario_si_archivia(
    logged_client, db_session
):
    origine = await ricetta(db_session)
    m = await pasto(db_session, d(11), D)
    r = await logged_client.post(f"{M}/{m.id}/recipe/copy", json={"recipe_id": str(origine.id)})
    copia = r.json()["recipe"]["id"]
    assert (await logged_client.delete(f"{M}/{m.id}")).status_code == 204
    dettaglio = (await logged_client.get(f"/api/v1/recipes/{copia}")).json()
    assert dettaglio["archived_at"] is not None


async def test_copiare_una_ricetta_del_ricettario_nel_pasto(logged_client, db_session):
    origine = await ricetta(db_session, "Frittata unica")
    m = await pasto(db_session, d(11), D)
    r = await logged_client.post(f"{M}/{m.id}/recipe/copy", json={"recipe_id": str(origine.id)})
    assert r.status_code == 201
    recipe = r.json()["recipe"]
    assert recipe["title"] == "Frittata unica"
    assert recipe["in_book"] is False
    assert recipe["id"] != str(origine.id)
    cerca = await logged_client.get("/api/v1/recipes/search", params={"q": "Frittata unica"})
    assert [x["id"] for x in cerca.json()] == [str(origine.id)]


async def test_copiare_in_un_pasto_che_ha_gia_la_ricetta_e_409(logged_client, db_session):
    origine = await ricetta(db_session)
    m = await pasto(db_session, d(11), D)
    corpo = {"recipe_id": str(origine.id)}
    assert (await logged_client.post(f"{M}/{m.id}/recipe/copy", json=corpo)).status_code == 201
    r = await logged_client.post(f"{M}/{m.id}/recipe/copy", json=corpo)
    assert r.status_code == 409 and r.json()["code"] == "has_recipe"


async def test_la_ricetta_d_origine_inesistente_e_404(logged_client, db_session):
    m = await pasto(db_session, d(11), D)
    r = await logged_client.post(
        f"{M}/{m.id}/recipe/copy", json={"recipe_id": str(uuid.uuid4())}
    )
    assert r.status_code == 404 and r.json()["detail"] == "ricetta inesistente"


async def test_gli_avanzi_possibili_dalla_rotta(logged_client, db_session):
    cena9 = await pasto(db_session, d(9), D, "Lasagne")
    fuori = await pasto(db_session, d(10), L, "Pizzeria", away=True)
    await pasto(db_session, d(10), D, "Avanzo", leftover_of_id=cena9.id)
    await pasto(db_session, d(1), D, "Troppo vecchio")
    pranzo11 = await pasto(db_session, d(11), L, "Risotto")
    url = f"{M}/leftover-candidates"
    r = await logged_client.get(url, params={"day": "2026-11-11", "slot": "lunch"})
    assert r.status_code == 200
    assert [x["id"] for x in r.json()] == [str(cena9.id)]
    assert str(fuori.id) not in [x["id"] for x in r.json()]
    r = await logged_client.get(url, params={"day": "2026-11-11", "slot": "dinner"})
    assert [x["id"] for x in r.json()][0] == str(pranzo11.id)


@pytest.mark.parametrize("metodo", ["get", "patch", "delete"])
async def test_un_pasto_inesistente_e_404(logged_client, metodo):
    kw = {"json": {"dish": "x"}} if metodo == "patch" else {}
    r = await getattr(logged_client, metodo)(f"{M}/{uuid.uuid4()}", **kw)
    assert r.status_code == 404


async def test_senza_accesso_401(client):
    assert (await client.get(f"{M}/week")).status_code == 401


async def test_un_pasto_fuori_casa_ha_la_ricetta_nel_pasto(logged_client, db_session):
    from app.services.meals import link_recipe, update_meal

    m = await pasto(db_session, d(10), D, "Frittata")
    r = await ricetta(db_session)
    await link_recipe(db_session, m, r)
    await update_meal(db_session, m, {"away": True})
    await db_session.commit()
    out = (await logged_client.get(f"{M}/{m.id}")).json()
    assert out["away"] is True
    assert out["recipe"]["id"] == str(r.id)
    assert out["can_chat"] is False
    assert out["can_ask_recipe"] is False


async def test_patch_dopo_l_avanzo_e_409_con_quanti(logged_client, db_session):
    origine = await pasto(db_session, d(9), D, "Lasagne")
    await pasto(db_session, d(10), L, "Avanzo", leftover_of_id=origine.id)
    r = await logged_client.patch(f"{M}/{origine.id}", json={"day": "2026-11-11"})
    assert r.status_code == 409
    assert r.json() == {
        "code": "leftover_after", "detail": "Martedì pranzo è un suo avanzo.", "leftovers": 1,
    }


async def test_patch_con_detach_leftovers_sposta(logged_client, db_session):
    origine = await pasto(db_session, d(9), D, "Lasagne")
    avanzo = await pasto(db_session, d(10), L, "Avanzo", leftover_of_id=origine.id)
    r = await logged_client.patch(
        f"{M}/{origine.id}", json={"day": "2026-11-11", "detach_leftovers": True}
    )
    assert r.status_code == 200
    assert r.json()["day"] == "2026-11-11"
    week = (await logged_client.get(f"{M}/week", params={"of": "2026-11-10"})).json()
    got = next(m for m in week["meals"] if m["id"] == str(avanzo.id))
    assert got["leftover_of"] is None
