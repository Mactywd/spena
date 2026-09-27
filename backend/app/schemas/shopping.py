import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.db.models.shopping import ShoppingStatus


class ShoppingItemOut(BaseModel):
    id: uuid.UUID
    raw_text: str
    ingredient_id: uuid.UUID | None
    ingredient_name: str | None
    ingredient_category: str | None
    ingredient_kind: str | None
    status: str
    reason: str
    created_at: datetime


class ShoppingItemCreate(BaseModel):
    raw_text: str = Field(min_length=1, max_length=200)
    ingredient_id: uuid.UUID | None = None


class ShoppingItemPatch(BaseModel):
    status: ShoppingStatus | None = None
    ingredient_id: uuid.UUID | None = None


class StockEntryIn(BaseModel):
    shopping_item_id: uuid.UUID
    ingredient_id: uuid.UUID
    product_id: uuid.UUID | None = None
    # facoltativa per voce, non per l'intera sistemazione: la maggior parte
    # delle voci (frutta sfusa, ecc.) non porta una scadenza
    expires_on: date | None = None
    # il codice a barre appena letto per questa voce, se la scelta è poi passata
    # dal catalogo (S8). Senza max_length di proposito: un codice che non entra in
    # colonna non si lega e basta (give_barcode_if_missing), mentre un 422 qui
    # respingerebbe l'intera sistemazione per un di più
    barcode: str | None = None


class StockRequest(BaseModel):
    entries: list[StockEntryIn] = Field(min_length=1)
