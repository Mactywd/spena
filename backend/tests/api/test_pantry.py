import pytest_asyncio

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.domain.rules import Availability, PantryStatus
from app.repositories.pantry import availability_map


@pytest_asyncio.fixture
async def dispensa(db_session):
    yogurt = Ingredient(name="yogurt greco", display_name="Yogurt greco",
                        category=IngredientCategory.LATTICINI)
    pomodoro = Ingredient(name="pomodoro", display_name="Pomodoro",
                          category=IngredientCategory.VERDURA)
    aglio = Ingredient(name="aglio", display_name="Aglio", category=IngredientCategory.VERDURA)
    db_session.add_all([yogurt, pomodoro, aglio])
    await db_session.flush()
    return {"yogurt": yogurt, "pomodoro": pomodoro, "aglio": aglio}


async def test_availability_map_takes_the_best_status(db_session, dispensa):
    """Due yogurt, uno pieno e uno agli sgoccioli: l'ingrediente è disponibile."""
    fage = Product(ingredient_id=dispensa["yogurt"].id, name="Fage", source="custom")
    carrefour = Product(ingredient_id=dispensa["yogurt"].id, name="Carrefour", source="custom")
    db_session.add_all([fage, carrefour])
    await db_session.flush()
    db_session.add_all([
        PantryItem(ingredient_id=dispensa["yogurt"].id, product_id=fage.id,
                   status=PantryStatus.LOW),
        PantryItem(ingredient_id=dispensa["yogurt"].id, product_id=carrefour.id,
                   status=PantryStatus.AVAILABLE),
        PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.LOW),
    ])
    await db_session.flush()

    result = await availability_map(db_session)
    assert result[dispensa["yogurt"].id] is Availability.AVAILABLE
    assert result[dispensa["pomodoro"].id] is Availability.LOW
    assert result.get(dispensa["aglio"].id, Availability.MISSING) is Availability.MISSING


async def test_finished_and_archived_items_do_not_count(db_session, dispensa):
    from datetime import UTC, datetime

    db_session.add_all([
        PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.FINISHED),
        PantryItem(ingredient_id=dispensa["aglio"].id, status=PantryStatus.AVAILABLE,
                   archived_at=datetime.now(UTC)),
    ])
    await db_session.flush()

    result = await availability_map(db_session)
    assert result.get(dispensa["pomodoro"].id, Availability.MISSING) is Availability.MISSING
    assert result.get(dispensa["aglio"].id, Availability.MISSING) is Availability.MISSING


async def test_availability_map_can_be_restricted_to_some_ingredients(db_session, dispensa):
    db_session.add_all([
        PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE),
        PantryItem(ingredient_id=dispensa["aglio"].id, status=PantryStatus.AVAILABLE),
    ])
    await db_session.flush()
    result = await availability_map(db_session, [dispensa["pomodoro"].id])
    assert set(result) == {dispensa["pomodoro"].id}


async def test_pantry_listing_carries_names_for_display(logged_client, db_session, dispensa):
    product = Product(ingredient_id=dispensa["yogurt"].id, name="Total 0%", brand="Fage",
                      source="openfoodfacts")
    db_session.add(product)
    await db_session.flush()
    db_session.add(PantryItem(ingredient_id=dispensa["yogurt"].id, product_id=product.id,
                              status=PantryStatus.AVAILABLE))
    await db_session.flush()

    body = (await logged_client.get("/api/v1/pantry")).json()
    entry = next(e for e in body if e["ingredient_name"] == "yogurt greco")
    assert entry["product_name"] == "Total 0%"
    assert entry["product_brand"] == "Fage"
    assert entry["ingredient_category"] == "latticini"


async def test_loose_produce_enters_without_a_product(logged_client, dispensa):
    response = await logged_client.post("/api/v1/pantry", json={
        "ingredient_id": str(dispensa["pomodoro"].id), "status": "available",
    })
    assert response.status_code == 201
    assert response.json()["product_id"] is None


async def test_patch_changes_status_and_stamps_the_time(logged_client, db_session, dispensa):
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()
    before = item.status_changed_at

    response = await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"status": "low"})
    assert response.status_code == 200
    assert response.json()["status"] == "low"
    await db_session.refresh(item)
    assert item.status_changed_at >= before


async def test_patch_rejects_an_invalid_status(logged_client, db_session, dispensa):
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()
    response = await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"status": "mezzo"})
    assert response.status_code == 422


async def test_availability_endpoint_returns_a_map(logged_client, db_session, dispensa):
    db_session.add(PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.LOW))
    await db_session.flush()
    body = (await logged_client.get("/api/v1/pantry/availability")).json()
    assert body[str(dispensa["pomodoro"].id)] == "low"


async def test_creating_with_a_dangling_ingredient_is_404_not_500(logged_client):
    """Un id che non esiste più (cache della PWA) deve dare 404, non un muro."""
    import uuid

    response = await logged_client.post("/api/v1/pantry", json={
        "ingredient_id": str(uuid.uuid4()), "status": "available",
    })
    assert response.status_code == 404
    assert "inesistente" in response.json()["detail"]
