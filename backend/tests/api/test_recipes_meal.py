"""La ricetta di un pasto, dalla parte delle ricette (piano Pasti e settimana, Task 5)."""

from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import func, select

from app.db.models.ingredient import IngredientCategory
from app.db.models.recipe import Recipe
from app.domain.meals import MealSlot, MealStatus
from app.repositories.ingredients import create_ingredient
from app.services.meal_recipes import DraftLine, MealRecipeDraft, write_meal_recipe
from app.services.meals import create_meal
from app.services.recipe_jobs import NOT_WRITTEN_NOTICE

R = "/api/v1/recipes"
M = "/api/v1/meals"
FRASE_SENZA_PASTO = "Questa ricetta non è di un pasto: per toglierla dal ricettario eliminala."


@pytest_asyncio.fixture
async def pasta(db_session):
    voce = await create_ingredient(db_session, "pasta", "Pasta", IngredientCategory.CEREALI)
    await db_session.commit()
    return voce


def _corpo(pasta, titolo="Pasta al burro", **extra):
    return {
        "title": titolo, "description": None, "category": None, "instructions": "Cuoci.",
        "servings": 2, "cost": None, "source": "manual",
        "ingredients": [
            {"ingredient_id": str(pasta.id), "role": "primary", "quantity_text": "320 g",
             "note": None}
        ],
        **extra,
    }


async def _pasto(session, giorno=11, slot=MealSlot.DINNER, dish="Pasta al burro", **kw):
    meal = await create_meal(
        session, day=date(2026, 11, giorno), slot=slot, dish=dish, **kw
    )
    await session.commit()
    return meal


async def _scritta_per(client, pasta, meal, titolo="Pasta al burro"):
    r = await client.post(R, json=_corpo(pasta, titolo, meal_id=str(meal.id)))
    assert r.status_code == 201, r.text
    return r.json()


async def _del_ricettario(client, pasta, titolo="Pasta al ragù"):
    r = await client.post(R, json=_corpo(pasta, titolo))
    assert r.status_code == 201, r.text
    return r.json()


async def _cerca(client, q):
    return (await client.get(f"{R}/search", params={"q": q})).json()


async def test_scrivere_la_ricetta_di_un_pasto(logged_client, db_session, pasta):
    meal = await _pasto(db_session)
    ricetta = await _scritta_per(logged_client, pasta, meal, "Spaghetti alla nerano")

    assert ricetta["in_book"] is False
    assert ricetta["meal"]["id"] == str(meal.id)
    pasto = (await logged_client.get(f"{M}/{meal.id}")).json()
    assert pasto["recipe"]["id"] == ricetta["id"]
    assert await _cerca(logged_client, "Spaghetti alla nerano") == []


@pytest.mark.parametrize(
    ("kw", "codice"),
    [
        ({"recipe": True}, "has_recipe"),
        ({"leftover": True}, "no_recipe_here"),
        ({"away": True}, "no_recipe_here"),
        ({"status": MealStatus.DRAFT}, "no_recipe_here"),
    ],
)
async def test_la_ricetta_non_si_scrive_per_chi_non_puo_riceverla(
    logged_client, db_session, pasta, kw, codice
):
    kw = dict(kw)
    if kw.pop("leftover", False):
        origine = await _pasto(db_session, 10, MealSlot.DINNER, "Origine")
        meal = await _pasto(db_session, 11, MealSlot.LUNCH, "Avanzo", leftover_of_id=origine.id)
    elif kw.pop("recipe", False):
        meal = await _pasto(db_session)
        await _scritta_per(logged_client, pasta, meal, "Già scritta")
    else:
        meal = await _pasto(db_session, **kw)
    prima = (await db_session.execute(select(func.count()).select_from(Recipe))).scalar_one()

    r = await logged_client.post(R, json=_corpo(pasta, "Nuova", meal_id=str(meal.id)))

    assert r.status_code == 409
    assert r.json()["code"] == codice
    dopo = (await db_session.execute(select(func.count()).select_from(Recipe))).scalar_one()
    assert dopo == prima


async def test_un_pasto_inesistente_e_404_e_niente_si_crea(logged_client, db_session, pasta):
    prima = (await db_session.execute(select(func.count()).select_from(Recipe))).scalar_one()
    r = await logged_client.post(
        R, json=_corpo(pasta, meal_id="00000000-0000-0000-0000-000000000001")
    )
    assert r.status_code == 404
    assert r.json()["detail"] == "pasto inesistente"
    dopo = (await db_session.execute(select(func.count()).select_from(Recipe))).scalar_one()
    assert dopo == prima


async def test_salva_e_togli_dal_ricettario(logged_client, db_session, pasta):
    meal = await _pasto(db_session)
    ricetta = await _scritta_per(logged_client, pasta, meal, "Spaghetti alla nerano")

    r = await logged_client.patch(f"{R}/{ricetta['id']}", json={"in_book": True})
    assert r.status_code == 200, r.text
    assert r.json()["in_book"] is True
    assert [x["id"] for x in await _cerca(logged_client, "Spaghetti alla nerano")] == [
        ricetta["id"]
    ]

    r = await logged_client.patch(f"{R}/{ricetta['id']}", json={"in_book": False})
    assert r.status_code == 200, r.text
    assert r.json()["in_book"] is False
    assert await _cerca(logged_client, "Spaghetti alla nerano") == []


async def test_togliere_dal_ricettario_una_ricetta_senza_pasto_e_409(logged_client, pasta):
    ricetta = await _del_ricettario(logged_client, pasta)
    r = await logged_client.patch(f"{R}/{ricetta['id']}", json={"in_book": False})
    assert r.status_code == 409
    assert r.json()["detail"] == FRASE_SENZA_PASTO


async def test_il_ricettario_di_una_ricetta_eliminata_non_si_cambia(logged_client, pasta):
    ricetta = await _del_ricettario(logged_client, pasta)
    assert (
        await logged_client.patch(f"{R}/{ricetta['id']}", json={"archived": True})
    ).status_code == 200
    r = await logged_client.patch(f"{R}/{ricetta['id']}", json={"in_book": True})
    assert r.status_code == 409
    # anche insieme al ripristino non conta lo stato di prima: conta quello dopo
    r = await logged_client.patch(
        f"{R}/{ricetta['id']}", json={"in_book": True, "archived": True}
    )
    assert r.status_code == 409


async def test_in_book_non_booleano_e_422(logged_client, pasta):
    ricetta = await _del_ricettario(logged_client, pasta)
    r = await logged_client.patch(f"{R}/{ricetta['id']}", json={"in_book": "sì"})
    assert r.status_code == 422


async def test_ripristinare_una_ricetta_senza_pasto_la_rimette_nel_ricettario(
    logged_client, db_session, pasta
):
    meal = await _pasto(db_session)
    ricetta = await _scritta_per(logged_client, pasta, meal, "Spaghetti alla nerano")
    assert (await logged_client.delete(f"{M}/{meal.id}")).status_code == 204

    r = await logged_client.patch(f"{R}/{ricetta['id']}", json={"archived": False})

    assert r.status_code == 200, r.text
    assert r.json()["in_book"] is True
    assert r.json()["meal"] is None
    assert [x["id"] for x in await _cerca(logged_client, "Spaghetti alla nerano")] == [
        ricetta["id"]
    ]


async def test_ripristinare_la_ricetta_di_un_pasto_la_lascia_fuori(
    logged_client, db_session, pasta
):
    meal = await _pasto(db_session)
    ricetta = await _scritta_per(logged_client, pasta, meal)
    assert (
        await logged_client.patch(f"{R}/{ricetta['id']}", json={"archived": True})
    ).status_code == 200

    r = await logged_client.patch(f"{R}/{ricetta['id']}", json={"archived": False})

    assert r.status_code == 200, r.text
    assert r.json()["in_book"] is False
    assert r.json()["meal"]["id"] == str(meal.id)


async def test_il_dettaglio_dice_ricettario_e_pasto(logged_client, db_session, pasta):
    del_ricettario = await _del_ricettario(logged_client, pasta)
    dettaglio = (await logged_client.get(f"{R}/{del_ricettario['id']}")).json()
    assert dettaglio["in_book"] is True
    assert dettaglio["meal"] is None

    meal = await _pasto(db_session, dish="Spaghetti")
    scritta = await _scritta_per(logged_client, pasta, meal)
    assert (
        await logged_client.patch(f"{R}/{scritta['id']}", json={"in_book": True})
    ).status_code == 200
    dettaglio = (await logged_client.get(f"{R}/{scritta['id']}")).json()
    assert dettaglio["in_book"] is True
    assert dettaglio["meal"]["dish"] == "Spaghetti"


async def test_la_modifica_della_ricetta_di_un_pasto_la_lascia_fuori_dal_ricettario(
    logged_client, db_session, pasta
):
    meal = await _pasto(db_session)
    ricetta = await _scritta_per(logged_client, pasta, meal)
    corpo = _corpo(pasta, "Titolo nuovo")
    corpo.pop("source")

    r = await logged_client.put(f"{R}/{ricetta['id']}", json=corpo)

    assert r.status_code == 200, r.text
    assert r.json()["title"] == "Titolo nuovo"
    assert r.json()["in_book"] is False
    assert r.json()["meal"]["id"] == str(meal.id)


async def test_l_avviso_vecchio_non_ricompare(logged_client, db_session, pasta):
    """«Annulla» di una «Ricetta scritta» riporta il pasto senza ricetta (`release_recipe`):
    un avviso rimasto dalla coda non deve tornare a dire «La ricetta non è arrivata»."""
    meal = await _pasto(db_session)
    change = await write_meal_recipe(
        db_session, meal,
        MealRecipeDraft(
            title="Pasta al burro", description=None, instructions="Cuoci.", servings=2,
            lines=(DraftLine(pasta.id, None, None, "primary", "320 g", None),),
            summary="x",
        ),
    )
    meal.recipe_notice = NOT_WRITTEN_NOTICE  # l'avviso di una richiesta di prima
    await db_session.commit()

    r = await logged_client.post(f"{M}/{meal.id}/chat/changes/{change.id}/undo")
    assert r.status_code == 200, r.text

    body = (await logged_client.get(f"{M}/{meal.id}")).json()
    assert body["recipe"] is None
    assert body["recipe_state"] == "none"
    assert body["can_ask_recipe"] is True
    assert body["recipe_notice"] is None
