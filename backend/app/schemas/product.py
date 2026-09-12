import uuid
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ProductOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    ingredient_id: uuid.UUID
    name: str
    brand: str | None
    barcode: str | None
    source: str
    nutrients: dict[str, float] | None
    image_url: str | None


class ProductCreate(BaseModel):
    """Il corpo con cui si conferma un prodotto, suggerito o inventato.

    `source`, `image_url` e `source_payload` esistono perché la conferma di un
    suggerimento Open Food Facts è l'unico momento in cui quei dati sono
    disponibili: non riportarli qui significa perderli per sempre, e la fase 2
    rielabora proprio `source_payload`. Il default resta `custom`, che è il caso
    della creazione manuale.
    """

    ingredient_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    brand: str | None = Field(default=None, max_length=120)
    barcode: str | None = Field(default=None, max_length=20)
    nutrients: dict[str, float] | None = None
    source: Literal["openfoodfacts", "custom"] = "custom"
    image_url: str | None = Field(default=None, max_length=500)
    source_payload: dict[str, Any] | None = None


class ProductSuggestion(BaseModel):
    """Prodotto trovato su Open Food Facts ma non ancora in catalogo.

    Non lo salviamo da soli: serve che l'utente dica a quale ingrediente
    canonico appartiene.
    """

    name: str
    brand: str | None
    barcode: str
    nutrients: dict[str, float]
    image_url: str | None


class BarcodeLookupOut(BaseModel):
    found: bool
    origin: str  # "catalog" | "openfoodfacts" | "unknown"
    product: ProductOut | None = None
    suggestion: ProductSuggestion | None = None
