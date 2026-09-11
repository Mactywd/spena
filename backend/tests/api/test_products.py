import json
from pathlib import Path

import httpx
import pytest_asyncio
import respx

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.product import Product

FIXTURES = Path(__file__).parent.parent / "fixtures" / "off"
BASE = "https://world.openfoodfacts.org"


@pytest_asyncio.fixture
async def yogurt(db_session):
    ingredient = Ingredient(name="yogurt greco", display_name="Yogurt greco",
                            category=IngredientCategory.LATTICINI)
    db_session.add(ingredient)
    await db_session.flush()
    return ingredient


async def test_known_barcode_comes_from_the_local_catalog(logged_client, db_session, yogurt):
    """Nessuna chiamata di rete se il prodotto è già nostro."""
    db_session.add(Product(ingredient_id=yogurt.id, name="Fage Total 0%", brand="Fage",
                           barcode="5201054000138", source="openfoodfacts"))
    await db_session.flush()

    response = await logged_client.get("/api/v1/products/barcode/5201054000138")
    body = response.json()
    assert body["found"] is True
    assert body["origin"] == "catalog"
    assert body["product"]["name"] == "Fage Total 0%"


@respx.mock
async def test_unknown_barcode_falls_back_to_openfoodfacts(logged_client, monkeypatch):
    monkeypatch.setenv("OFF_BASE_URL", BASE)
    from app.core.config import get_settings

    get_settings.cache_clear()
    respx.get(f"{BASE}/api/v2/product/5201054000138.json").mock(
        return_value=httpx.Response(200, json=json.loads((FIXTURES / "complete.json").read_text()))
    )

    response = await logged_client.get("/api/v1/products/barcode/5201054000138")
    body = response.json()
    assert body["found"] is True
    assert body["origin"] == "openfoodfacts"
    # non è ancora in catalogo: serve che l'utente scelga l'ingrediente canonico
    assert body["product"] is None
    assert body["suggestion"]["name"] == "Total 0% Yogurt Greco"
    assert body["suggestion"]["nutrients"]["protein"] == 10.3
    get_settings.cache_clear()


@respx.mock
async def test_barcode_unknown_everywhere_is_not_an_error(logged_client, monkeypatch):
    """Deve aprire la creazione manuale, non restituire un errore."""
    monkeypatch.setenv("OFF_BASE_URL", BASE)
    from app.core.config import get_settings

    get_settings.cache_clear()
    respx.get(f"{BASE}/api/v2/product/0000000000000.json").mock(
        return_value=httpx.Response(200, json=json.loads((FIXTURES / "not_found.json").read_text()))
    )
    response = await logged_client.get("/api/v1/products/barcode/0000000000000")
    assert response.status_code == 200
    assert response.json() == {"found": False, "origin": "unknown",
                               "product": None, "suggestion": None}
    get_settings.cache_clear()


@respx.mock
async def test_openfoodfacts_down_degrades_instead_of_failing(logged_client, monkeypatch):
    monkeypatch.setenv("OFF_BASE_URL", BASE)
    from app.core.config import get_settings

    get_settings.cache_clear()
    respx.get(f"{BASE}/api/v2/product/1.json").mock(side_effect=httpx.ConnectTimeout("lento"))
    response = await logged_client.get("/api/v1/products/barcode/1")
    assert response.status_code == 200
    assert response.json()["found"] is False
    assert response.json()["origin"] == "unknown"
    get_settings.cache_clear()


async def test_create_custom_product(logged_client, yogurt):
    response = await logged_client.post("/api/v1/products", json={
        "ingredient_id": str(yogurt.id),
        "name": "Yogurt greco pesca",
        "brand": "Carrefour",
        "barcode": "8000000000001",
        "nutrients": {"kcal": 95.0, "protein": 7.0},
    })
    assert response.status_code == 201
    assert response.json()["source"] == "custom"


async def test_catalog_search_refines_progressively(logged_client, db_session, yogurt):
    db_session.add_all([
        Product(ingredient_id=yogurt.id, name="Total 0%", brand="Fage", source="openfoodfacts"),
        Product(ingredient_id=yogurt.id, name="Yogurt greco pesca", brand="Carrefour",
                source="custom"),
    ])
    await db_session.flush()

    broad = await logged_client.get("/api/v1/products/search?q=yogurt greco")
    assert len(broad.json()) >= 1

    narrow = await logged_client.get("/api/v1/products/search?q=carrefour pesca")
    assert narrow.json()[0]["brand"] == "Carrefour"
