import json
from pathlib import Path

import httpx
import pytest
import respx

from app.services.openfoodfacts import OffUnavailable, OpenFoodFactsClient

FIXTURES = Path(__file__).parent.parent / "fixtures" / "off"
BASE = "https://world.openfoodfacts.org"


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text())


@respx.mock
async def test_fetch_maps_a_complete_product():
    respx.get(f"{BASE}/api/v2/product/5201054000138.json").mock(
        return_value=httpx.Response(200, json=_fixture("complete"))
    )
    product = await OpenFoodFactsClient(base_url=BASE).fetch("5201054000138")

    assert product.name == "Total 0% Yogurt Greco"
    assert product.brand == "Fage"
    assert product.nutrients["kcal"] == 57.0
    assert product.nutrients["protein"] == 10.3
    assert product.nutrients["salt"] == 0.1
    assert product.image_url.endswith("fage.jpg")


@respx.mock
async def test_micronutrients_arrive_in_the_unit_the_vocabulary_declares():
    """Open Food Facts scrive ogni `_100g` in grammi, qualunque unità mostri
    l'etichetta: il ferro dei Chocapic arriva come `0.012`, cioè 12 mg.
    Salvato così sotto una chiave che il vocabolario dichiara in mg, sarebbe
    mille volte troppo poco."""
    respx.get(f"{BASE}/api/v2/product/5201054000138.json").mock(
        return_value=httpx.Response(200, json=_fixture("complete"))
    )
    product = await OpenFoodFactsClient(base_url=BASE).fetch("5201054000138")

    assert product.nutrients["vitamin_c"] == 0.5  # mg
    assert product.nutrients["calcium"] == 110  # mg
    assert product.nutrients["iron"] == 0.05  # mg
    assert product.nutrients["potassium"] == 140  # mg
    assert product.nutrients["kcal"] == 57.0  # l'energia non è in grammi
    # la vitamina D c'è nella risposta ma non è fra i campi raccolti
    assert "vitamin_d" not in product.nutrients


@respx.mock
async def test_missing_nutrients_are_absent_not_zero():
    """Zero e "non so" non sono la stessa cosa: inventarli falsa i totali."""
    respx.get(f"{BASE}/api/v2/product/8001120000000.json").mock(
        return_value=httpx.Response(200, json=_fixture("sparse"))
    )
    product = await OpenFoodFactsClient(base_url=BASE).fetch("8001120000000")

    assert product.nutrients == {"kcal": 29.0}
    assert product.brand is None


@respx.mock
async def test_unknown_barcode_returns_none():
    respx.get(f"{BASE}/api/v2/product/0000000000000.json").mock(
        return_value=httpx.Response(200, json=_fixture("not_found"))
    )
    assert await OpenFoodFactsClient(base_url=BASE).fetch("0000000000000") is None


@respx.mock
async def test_http_404_returns_none():
    respx.get(f"{BASE}/api/v2/product/1.json").mock(return_value=httpx.Response(404))
    assert await OpenFoodFactsClient(base_url=BASE).fetch("1") is None


@respx.mock
async def test_timeout_raises_off_unavailable():
    """Il chiamante deve poter degradare all'inserimento manuale."""
    respx.get(f"{BASE}/api/v2/product/1.json").mock(side_effect=httpx.ConnectTimeout("lento"))
    with pytest.raises(OffUnavailable):
        await OpenFoodFactsClient(base_url=BASE).fetch("1")


@respx.mock
async def test_server_error_raises_off_unavailable():
    respx.get(f"{BASE}/api/v2/product/1.json").mock(return_value=httpx.Response(503))
    with pytest.raises(OffUnavailable):
        await OpenFoodFactsClient(base_url=BASE).fetch("1")


@respx.mock
async def test_malformed_json_body_raises_off_unavailable():
    """Un 200 con body HTML è quello che torna da un captive portal o da un proxy
    configurato male. Deve degradare all'inserimento manuale, mai diventare errore."""
    respx.get(f"{BASE}/api/v2/product/1.json").mock(
        return_value=httpx.Response(200, text="<html>Captive Portal</html>", headers={"content-type": "text/html"})
    )
    with pytest.raises(OffUnavailable):
        await OpenFoodFactsClient(base_url=BASE).fetch("1")
