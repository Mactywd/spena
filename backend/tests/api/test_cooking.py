import uuid

import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.recipe import CookingEvent, Recipe, RecipeIngredient, RecipeSource
from app.db.models.shopping import ShoppingListItem
from app.domain.rules import IngredientRole, PantryStatus


@pytest_asyncio.fixture
async def scenario(db_session):
    pomodoro = Ingredient(name="pomodoro", display_name="Pomodoro",
                          category=IngredientCategory.VERDURA)
    pasta = Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    db_session.add_all([pomodoro, pasta])
    await db_session.flush()

    recipe = Recipe(title="Pasta al pomodoro", instructions="Cuoci.", source=RecipeSource.MANUAL)
    recipe.ingredients.append(
        RecipeIngredient(ingredient_id=pasta.id, role=IngredientRole.PRIMARY)
    )
    recipe.ingredients.append(
        RecipeIngredient(ingredient_id=pomodoro.id, role=IngredientRole.PRIMARY)
    )
    db_session.add(recipe)

    pasta_item = PantryItem(ingredient_id=pasta.id, status=PantryStatus.AVAILABLE)
    pomodoro_item = PantryItem(ingredient_id=pomodoro.id, status=PantryStatus.AVAILABLE)
    db_session.add_all([pasta_item, pomodoro_item])
    await db_session.flush()
    return {"recipe": recipe, "pasta_item": pasta_item, "pomodoro_item": pomodoro_item,
            "pomodoro": pomodoro, "pasta": pasta}


async def test_cooking_updates_statuses_and_records_the_event(logged_client, db_session, scenario):
    response = await logged_client.post(
        f"/api/v1/recipes/{scenario['recipe'].id}/cook",
        json={"servings": 2, "transitions": [
            {"pantry_item_id": str(scenario["pomodoro_item"].id), "to_status": "finished",
             "restock": True},
            {"pantry_item_id": str(scenario["pasta_item"].id), "to_status": "low",
             "restock": False},
        ]},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["updated"] == 2
    assert body["restocked"] == 1

    await db_session.refresh(scenario["pomodoro_item"])
    await db_session.refresh(scenario["pasta_item"])
    assert scenario["pomodoro_item"].status == "finished"
    assert scenario["pasta_item"].status == "low"

    events = list((await db_session.execute(select(CookingEvent))).scalars())
    assert len(events) == 1
    assert events[0].recipe_id == scenario["recipe"].id
    assert events[0].servings == 2
    assert len(events[0].snapshot["transitions"]) == 2
    assert events[0].snapshot["transitions"][0]["from"] == "available"


async def test_restock_creates_a_list_entry_with_the_right_reason(
    logged_client, db_session, scenario
):
    await logged_client.post(
        f"/api/v1/recipes/{scenario['recipe'].id}/cook",
        json={"transitions": [
            {"pantry_item_id": str(scenario["pomodoro_item"].id), "to_status": "finished",
             "restock": True},
        ]},
    )
    items = list((await db_session.execute(select(ShoppingListItem))).scalars())
    assert len(items) == 1
    assert items[0].ingredient_id == scenario["pomodoro"].id
    assert items[0].raw_text == "pomodoro"
    assert items[0].reason == "finished_while_cooking"
    assert items[0].status == "pending"


async def test_restocking_a_low_item_uses_its_own_reason(logged_client, db_session, scenario):
    await logged_client.post(
        f"/api/v1/recipes/{scenario['recipe'].id}/cook",
        json={"transitions": [
            {"pantry_item_id": str(scenario["pasta_item"].id), "to_status": "low",
             "restock": True},
        ]},
    )
    items = list((await db_session.execute(select(ShoppingListItem))).scalars())
    assert items[0].reason == "low_while_cooking"


async def test_no_restock_means_no_list_entry(logged_client, db_session, scenario):
    await logged_client.post(
        f"/api/v1/recipes/{scenario['recipe'].id}/cook",
        json={"transitions": [
            {"pantry_item_id": str(scenario["pomodoro_item"].id), "to_status": "finished",
             "restock": False},
        ]},
    )
    items = list((await db_session.execute(select(ShoppingListItem))).scalars())
    assert items == []


async def test_already_in_list_is_not_duplicated(logged_client, db_session, scenario):
    """Se il pomodoro è già in lista, cucinare non deve aggiungerlo due volte."""
    await logged_client.post(
        f"/api/v1/recipes/{scenario['recipe'].id}/cook",
        json={"transitions": [
            {"pantry_item_id": str(scenario["pomodoro_item"].id), "to_status": "finished",
             "restock": True},
        ]},
    )
    await logged_client.post(
        f"/api/v1/recipes/{scenario['recipe'].id}/cook",
        json={"transitions": [
            {"pantry_item_id": str(scenario["pomodoro_item"].id), "to_status": "finished",
             "restock": True},
        ]},
    )
    items = list((await db_session.execute(select(ShoppingListItem))).scalars())
    assert len(items) == 1


async def test_cooking_is_all_or_nothing(logged_client, db_session, scenario):
    """Una voce inesistente nel mezzo non deve lasciare metà degli stati cambiati."""
    # Il commit qui sotto rilascia il savepoint della fixture: il rollback che la
    # rotta fa sul percorso d'errore deve annullare solo il lavoro della rotta,
    # non anche questi dati preesistenti (vedi nota di correzione nel brief).
    await db_session.commit()

    response = await logged_client.post(
        f"/api/v1/recipes/{scenario['recipe'].id}/cook",
        json={"transitions": [
            {"pantry_item_id": str(scenario["pomodoro_item"].id), "to_status": "finished",
             "restock": True},
            {"pantry_item_id": str(uuid.uuid4()), "to_status": "low", "restock": False},
        ]},
    )
    assert response.status_code == 404

    await db_session.refresh(scenario["pomodoro_item"])
    assert scenario["pomodoro_item"].status == "available"
    assert list((await db_session.execute(select(CookingEvent))).scalars()) == []
    assert list((await db_session.execute(select(ShoppingListItem))).scalars()) == []


async def test_cooking_an_unknown_recipe_is_404(logged_client):
    response = await logged_client.post(
        f"/api/v1/recipes/{uuid.uuid4()}/cook", json={"transitions": []}
    )
    assert response.status_code == 404


async def test_restock_uses_the_product_name_when_there_is_one(
    logged_client, db_session, scenario
):
    """Se hai comprato una marca precisa, la lista te la ricorda."""
    product = Product(ingredient_id=scenario["pomodoro"].id, name="Passata Mutti",
                      brand="Mutti", source="openfoodfacts")
    db_session.add(product)
    await db_session.flush()
    scenario["pomodoro_item"].product_id = product.id
    await db_session.flush()

    await logged_client.post(
        f"/api/v1/recipes/{scenario['recipe'].id}/cook",
        json={"transitions": [
            {"pantry_item_id": str(scenario["pomodoro_item"].id), "to_status": "finished",
             "restock": True},
        ]},
    )
    items = list((await db_session.execute(select(ShoppingListItem))).scalars())
    assert items[0].raw_text == "Passata Mutti"


async def test_restocking_an_available_item_uses_manual_reason(
    logged_client, db_session, scenario
):
    """Chiedere più di un ingrediente ancora disponibile è una richiesta manuale."""
    await logged_client.post(
        f"/api/v1/recipes/{scenario['recipe'].id}/cook",
        json={"transitions": [
            {"pantry_item_id": str(scenario["pomodoro_item"].id),
             "to_status": "available", "restock": True},
        ]},
    )
    items = list((await db_session.execute(select(ShoppingListItem))).scalars())
    assert items[0].reason == "manual"
