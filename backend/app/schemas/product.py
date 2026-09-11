import uuid

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
    ingredient_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    brand: str | None = Field(default=None, max_length=120)
    barcode: str | None = Field(default=None, max_length=20)
    nutrients: dict[str, float] | None = None


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
