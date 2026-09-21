from datetime import date

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


async def test_la_sistemazione_porta_in_dispensa_anche_le_scadenze(
    logged_client, db_session, ingredienti
):
    """Una voce con la data e una senza, nella stessa richiesta: la scadenza è
    facoltativa per voce, non per sistemazione. Lo yogurt ha una scadenza vera e
    corta, le mele sfuse no — ed è il caso normale."""
    yogurt_item = ShoppingListItem(raw_text="yogurt greco",
                                   ingredient_id=ingredienti["yogurt"].id,
                                   status=ShoppingStatus.CHECKED,
                                   reason=ShoppingReason.MANUAL)
    mela_item = ShoppingListItem(raw_text="mele", ingredient_id=ingredienti["mela"].id,
                                 status=ShoppingStatus.CHECKED,
                                 reason=ShoppingReason.MANUAL)
    db_session.add_all([yogurt_item, mela_item])
    await db_session.flush()

    response = await logged_client.post("/api/v1/shopping-list/stock", json={"entries": [
        {"shopping_item_id": str(yogurt_item.id),
         "ingredient_id": str(ingredienti["yogurt"].id),
         "product_id": None, "expires_on": "2026-10-02"},
        # le mele sfuse entrano senza data, e non è un errore
        {"shopping_item_id": str(mela_item.id),
         "ingredient_id": str(ingredienti["mela"].id), "product_id": None},
    ]})
    assert response.status_code == 201

    voci = list((await db_session.execute(select(PantryItem))).scalars())
    per_ingrediente = {v.ingredient_id: v for v in voci}
    assert per_ingrediente[ingredienti["yogurt"].id].expires_on == date(2026, 10, 2)
    assert per_ingrediente[ingredienti["mela"].id].expires_on is None


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


async def test_stocking_rejects_a_product_of_another_ingredient(
    logged_client, db_session, ingredienti
):
    """La strada dello scontrino/catalogo ha lo stesso buco della diretta: un
    prodotto di pomodoro non deve poter entrare come yogurt greco (brief)."""
    pomodoro = Ingredient(name="pomodoro", display_name="Pomodoro",
                          category=IngredientCategory.VERDURA)
    db_session.add(pomodoro)
    await db_session.flush()
    product = Product(ingredient_id=pomodoro.id, name="Pomodori pelati", source="openfoodfacts")
    db_session.add(product)
    yogurt_item = ShoppingListItem(raw_text="yogurt greco",
                                   ingredient_id=ingredienti["yogurt"].id,
                                   status=ShoppingStatus.CHECKED, reason=ShoppingReason.MANUAL)
    db_session.add(yogurt_item)
    await db_session.flush()

    response = await logged_client.post("/api/v1/shopping-list/stock", json={"entries": [
        {"shopping_item_id": str(yogurt_item.id),
         "ingredient_id": str(ingredienti["yogurt"].id),
         "product_id": str(product.id)},
    ]})
    assert response.status_code == 409
    assert "altro ingrediente" in response.json()["detail"]

    pantry = list((await db_session.execute(select(PantryItem))).scalars())
    assert pantry == []


async def test_stocking_with_a_dangling_product_is_404_not_500(
    logged_client, db_session, ingredienti
):
    """Un product_id che non esiste più resta un 404, non un muro (come già per
    l'ingrediente inesistente)."""
    import uuid

    yogurt_item = ShoppingListItem(raw_text="yogurt greco",
                                   ingredient_id=ingredienti["yogurt"].id,
                                   status=ShoppingStatus.CHECKED, reason=ShoppingReason.MANUAL)
    db_session.add(yogurt_item)
    await db_session.flush()

    response = await logged_client.post("/api/v1/shopping-list/stock", json={"entries": [
        {"shopping_item_id": str(yogurt_item.id),
         "ingredient_id": str(ingredienti["yogurt"].id),
         "product_id": str(uuid.uuid4())},
    ]})
    assert response.status_code == 404
    assert "inesistente" in response.json()["detail"]


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


async def test_creating_with_a_dangling_ingredient_is_404_not_500(logged_client):
    import uuid

    response = await logged_client.post("/api/v1/shopping-list", json={
        "raw_text": "yogurt", "ingredient_id": str(uuid.uuid4()),
    })
    assert response.status_code == 404
    assert "inesistente" in response.json()["detail"]


async def test_resolving_to_a_dangling_ingredient_is_404_not_500(logged_client):
    """Risolvere una voce su un ingrediente cancellato non deve essere un muro."""
    import uuid

    created = await logged_client.post("/api/v1/shopping-list", json={"raw_text": "yogurt"})
    item_id = created.json()["id"]
    response = await logged_client.patch(f"/api/v1/shopping-list/{item_id}", json={
        "ingredient_id": str(uuid.uuid4()),
    })
    assert response.status_code == 404
    assert "inesistente" in response.json()["detail"]


async def test_una_voce_di_lista_porta_il_kind_del_suo_ingrediente(logged_client, db_session):
    """Serve alla sistemazione della spesa, che deve sapere se nascondere i campi
    dei nutrienti — e deve saperlo senza ricalcolare la partizione nel client."""
    from app.repositories.ingredients import create_ingredient

    candeggina = await create_ingredient(db_session, "candeggina", "Candeggina", "casa")
    await db_session.commit()

    await logged_client.post(
        "/api/v1/shopping-list",
        json={"raw_text": "candeggina", "ingredient_id": str(candeggina.id)},
    )
    voci = (await logged_client.get("/api/v1/shopping-list")).json()

    assert voci[0]["ingredient_kind"] == "non_food"
