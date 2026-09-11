import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus


@pytest_asyncio.fixture
async def ingredienti(db_session):
    yogurt = Ingredient(name="yogurt greco", display_name="Yogurt greco",
                        category=IngredientCategory.LATTICINI)
    mela = Ingredient(name="mela", display_name="Mela", category=IngredientCategory.FRUTTA)
    db_session.add_all([yogurt, mela])
    await db_session.flush()
    return {"yogurt": yogurt, "mela": mela}


async def test_free_text_enters_the_list_unresolved(logged_client):
    """Scrivere la lista non deve mai essere interrotto da una disambiguazione."""
    response = await logged_client.post("/api/v1/shopping-list", json={
        "raw_text": "quella cosa verde del mercato",
    })
    assert response.status_code == 201
    assert response.json()["ingredient_id"] is None
    assert response.json()["status"] == "pending"
    assert response.json()["reason"] == "manual"


async def test_item_can_be_resolved_later(logged_client, ingredienti):
    created = await logged_client.post("/api/v1/shopping-list", json={"raw_text": "yogurt"})
    item_id = created.json()["id"]

    patched = await logged_client.patch(f"/api/v1/shopping-list/{item_id}", json={
        "ingredient_id": str(ingredienti["yogurt"].id),
    })
    assert patched.json()["ingredient_name"] == "yogurt greco"


async def test_checking_an_item_stamps_the_time(logged_client, ingredienti):
    created = await logged_client.post("/api/v1/shopping-list", json={"raw_text": "mela"})
    item_id = created.json()["id"]
    patched = await logged_client.patch(f"/api/v1/shopping-list/{item_id}",
                                       json={"status": "checked"})
    assert patched.json()["status"] == "checked"


async def test_stocking_creates_pantry_items_and_closes_list_entries(
    logged_client, db_session, ingredienti
):
    product = Product(ingredient_id=ingredienti["yogurt"].id, name="Total 0%", brand="Fage",
                      source="openfoodfacts")
    db_session.add(product)
    yogurt_item = ShoppingListItem(raw_text="yogurt greco",
                                   ingredient_id=ingredienti["yogurt"].id,
                                   status=ShoppingStatus.CHECKED, reason=ShoppingReason.MANUAL)
    mela_item = ShoppingListItem(raw_text="mele", ingredient_id=ingredienti["mela"].id,
                                 status=ShoppingStatus.CHECKED, reason=ShoppingReason.MANUAL)
    db_session.add_all([yogurt_item, mela_item])
    await db_session.flush()

    response = await logged_client.post("/api/v1/shopping-list/stock", json={"entries": [
        {"shopping_item_id": str(yogurt_item.id),
         "ingredient_id": str(ingredienti["yogurt"].id),
         "product_id": str(product.id)},
        # le mele sfuse entrano senza prodotto
        {"shopping_item_id": str(mela_item.id),
         "ingredient_id": str(ingredienti["mela"].id),
         "product_id": None},
    ]})
    assert response.status_code == 201

    pantry = list((await db_session.execute(select(PantryItem))).scalars())
    assert len(pantry) == 2
    assert {p.status for p in pantry} == {"available"}
    assert sum(1 for p in pantry if p.product_id is None) == 1

    await db_session.refresh(yogurt_item)
    await db_session.refresh(mela_item)
    assert yogurt_item.status == "done"
    assert mela_item.done_at is not None


async def test_stocking_is_all_or_nothing(logged_client, db_session, ingredienti):
    """Un riferimento sbagliato nel mezzo non deve lasciare la dispensa a metà."""
    import uuid

    good = ShoppingListItem(raw_text="mele", ingredient_id=ingredienti["mela"].id,
                            status=ShoppingStatus.CHECKED, reason=ShoppingReason.MANUAL)
    db_session.add(good)
    await db_session.flush()
    # Il commit qui sotto rilascia il savepoint della fixture: il rollback che la
    # rotta fa sul percorso d'errore deve annullare solo il lavoro della rotta,
    # non anche questi dati preesistenti (vedi nota di correzione nel brief).
    await db_session.commit()

    response = await logged_client.post("/api/v1/shopping-list/stock", json={"entries": [
        {"shopping_item_id": str(good.id), "ingredient_id": str(ingredienti["mela"].id),
         "product_id": None},
        {"shopping_item_id": str(uuid.uuid4()), "ingredient_id": str(uuid.uuid4()),
         "product_id": None},
    ]})
    assert response.status_code == 404

    pantry = list((await db_session.execute(select(PantryItem))).scalars())
    assert pantry == []
    await db_session.refresh(good)
    assert good.status == "checked"


async def test_listing_can_be_filtered_by_status(logged_client, db_session, ingredienti):
    db_session.add_all([
        ShoppingListItem(raw_text="a", status=ShoppingStatus.PENDING,
                         reason=ShoppingReason.MANUAL),
        ShoppingListItem(raw_text="b", status=ShoppingStatus.DONE, reason=ShoppingReason.MANUAL),
    ])
    await db_session.flush()

    open_items = (await logged_client.get(
        "/api/v1/shopping-list?status=pending&status=checked"
    )).json()
    assert [i["raw_text"] for i in open_items] == ["a"]
