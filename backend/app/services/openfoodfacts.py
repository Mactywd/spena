"""Accesso a Open Food Facts, isolato dal resto dell'applicazione.

Il resto del codice non sa che questo servizio esiste: conosce solo
`OffProduct` e `OffUnavailable`. Un guasto qui deve sempre tradursi in
inserimento manuale, mai in un vicolo cieco.
"""

import json
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings
from app.domain.nutrients import NUTRIENT_FIELDS

# le chiavi di Open Food Facts mappate sul nostro vocabolario
_NUTRIENT_MAP = {
    "energy-kcal_100g": "kcal",
    "proteins_100g": "protein",
    "carbohydrates_100g": "carbs",
    "sugars_100g": "sugars",
    "fat_100g": "fat",
    "saturated-fat_100g": "saturated_fat",
    "fiber_100g": "fiber",
    "salt_100g": "salt",
    "vitamin-c_100g": "vitamin_c",
    "calcium_100g": "calcium",
    "iron_100g": "iron",
    "potassium_100g": "potassium",
}

# Open Food Facts scrive ogni `_100g` in grammi, qualunque unità mostri
# l'etichetta (misurato il 2026-09-24: il ferro dei Chocapic è `0.012`, cioè
# 12 mg); l'energia in kcal è l'unica eccezione. Il fattore porta il valore
# all'unità che il vocabolario dichiara per quella chiave.
_FROM_GRAMS = {"g": 1, "mg": 1_000, "µg": 1_000_000}


def _in_vocabulary_unit(ours: str, value: float) -> float:
    unit = NUTRIENT_FIELDS[ours].unit
    if unit == "kcal":
        return value
    factor = _FROM_GRAMS[unit]
    # 0.00005 * 1000 fa 0.05000000000000001: si arrotonda solo dove si moltiplica
    return value if factor == 1 else round(value * factor, 6)


class OffUnavailable(Exception):
    """Open Food Facts non raggiungibile o in errore. Degradare al manuale."""


@dataclass(frozen=True)
class OffProduct:
    barcode: str
    name: str
    brand: str | None
    nutrients: dict[str, float]
    image_url: str | None
    raw: dict[str, Any]


class OpenFoodFactsClient:
    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.off_base_url).rstrip("/")
        self._timeout = timeout if timeout is not None else settings.off_timeout_seconds

    async def fetch(self, barcode: str) -> OffProduct | None:
        url = f"{self._base_url}/api/v2/product/{barcode}.json"
        try:
            async with httpx.AsyncClient(timeout=self._timeout) as http:
                response = await http.get(url, headers={"User-Agent": "Spena/0.1"})
        except httpx.HTTPError as exc:
            raise OffUnavailable(str(exc)) from exc

        if response.status_code == 404:
            return None
        if response.status_code >= 500:
            raise OffUnavailable(f"HTTP {response.status_code}")
        if response.status_code != 200:
            raise OffUnavailable(f"HTTP {response.status_code}")

        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise OffUnavailable(f"Invalid JSON response: {exc}") from exc
        if payload.get("status") != 1 or "product" not in payload:
            return None

        product = payload["product"]
        nutriments = product.get("nutriments") or {}
        # un nutriente assente resta assente: zero sarebbe un'informazione falsa
        nutrients = {
            ours: _in_vocabulary_unit(ours, float(nutriments[theirs]))
            for theirs, ours in _NUTRIENT_MAP.items()
            if nutriments.get(theirs) is not None
        }
        brand = (product.get("brands") or "").split(",")[0].strip() or None

        return OffProduct(
            barcode=barcode,
            name=(product.get("product_name") or "").strip() or f"Prodotto {barcode}",
            brand=brand,
            nutrients=nutrients,
            image_url=product.get("image_front_url") or None,
            raw=product,
        )
