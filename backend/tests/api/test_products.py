import json
from pathlib import Path

import httpx
import pytest_asyncio
import respx
from sqlalchemy import select

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
    """Aggiungere parole deve restringere, e va provato su due insiemi diversi.

    La versione precedente di questo test asseriva `len(broad.json()) >= 1`, che è
    vero per costruzione: passava anche mentre la query allargava (`or_`) invece di
    restringere. Qui le due risposte sono confrontate fra loro, e la stretta deve
    essere un sottoinsieme proprio della larga.
    """
    db_session.add_all([
        Product(ingredient_id=yogurt.id, name="Yogurt greco naturale", brand="Fage",
                source="openfoodfacts"),
        Product(ingredient_id=yogurt.id, name="Yogurt greco pesca", brand="Carrefour",
                source="custom"),
        Product(ingredient_id=yogurt.id, name="Latte intero", brand="Granarolo",
                source="custom"),
    ])
    await db_session.flush()

    async def nomi(q: str) -> list[str]:
        response = await logged_client.get("/api/v1/products/search", params={"q": q})
        assert response.status_code == 200
        return [p["name"] for p in response.json()]

    larga = await nomi("yogurt greco")
    assert sorted(larga) == ["Yogurt greco naturale", "Yogurt greco pesca"]

    stretta = await nomi("yogurt greco carrefour")
    assert stretta == ["Yogurt greco pesca"]
    assert set(stretta) < set(larga), "affinare deve restringere, non allargare"

    # restringere non è azzerare: la somiglianza trigram regge l'errore di battitura
    assert sorted(await nomi("yogurtt greco")) == [
        "Yogurt greco naturale", "Yogurt greco pesca"
    ]

    # e una query che non somiglia a niente resta vuota, non ripesca il catalogo
    assert await nomi("bulloni") == []


async def test_confirming_a_suggestion_keeps_its_provenance(logged_client, db_session, yogurt):
    """La conferma è l'unico momento in cui foto, payload e provenienza esistono.

    La schermata "sistema la spesa" mostra la foto scaricata un passo prima e la
    fase 2 rielabora `source_payload`: scartarli qui li perde per sempre.
    """
    raw = json.loads((FIXTURES / "complete.json").read_text())
    image = "https://images.openfoodfacts.org/images/products/520/105/400/0138/front.jpg"
    response = await logged_client.post("/api/v1/products", json={
        "ingredient_id": str(yogurt.id),
        "name": "Total 0% Yogurt Greco",
        "brand": "Fage",
        "barcode": "5201054000138",
        "nutrients": {"protein": 10.3},
        "source": "openfoodfacts",
        "image_url": image,
        "source_payload": raw,
    })
    assert response.status_code == 201
    assert response.json()["source"] == "openfoodfacts"
    assert response.json()["image_url"] == image

    stored = (await db_session.execute(
        select(Product).where(Product.barcode == "5201054000138")
    )).scalar_one()
    assert stored.source_payload == raw
    assert stored.source == "openfoodfacts"


async def test_an_unknown_source_is_refused(logged_client, yogurt):
    """`source` ammette solo i due valori della spec, non testo libero."""
    response = await logged_client.post("/api/v1/products", json={
        "ingredient_id": str(yogurt.id), "name": "Qualcosa", "source": "inventato",
    })
    assert response.status_code == 422


async def test_product_on_a_missing_ingredient_is_404_not_409(logged_client):
    import uuid

    response = await logged_client.post("/api/v1/products", json={
        "ingredient_id": str(uuid.uuid4()), "name": "Fantasma", "barcode": "8000000000002",
    })
    assert response.status_code == 404
    assert "ingrediente" in response.json()["detail"]


async def test_duplicate_barcode_is_still_409(logged_client, yogurt):
    body = {"ingredient_id": str(yogurt.id), "name": "Total 0%", "barcode": "8000000000003"}
    assert (await logged_client.post("/api/v1/products", json=body)).status_code == 201
    conflict = await logged_client.post("/api/v1/products", json=body)
    assert conflict.status_code == 409
    assert "codice a barre" in conflict.json()["detail"]
