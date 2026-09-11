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
