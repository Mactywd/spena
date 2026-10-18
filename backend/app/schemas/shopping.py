import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field, model_validator

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


class ShoppingItemAddOut(ShoppingItemOut):
    """La risposta dell'aggiunta. `added` falso non è un errore: l'ingrediente era
    già da comprare e la voce è quella che c'era (S18) — lo stesso `added` di
    `RestockOut`, perché chi scrive possa dire «era già in lista»."""

    added: bool


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

    @model_validator(mode="after")
    def _one_ingredient_per_item(self) -> "StockRequest":
        # Più confezioni per voce sì (S3 §10.2), ma dello stesso ingrediente: la voce
        # ne ha uno, e `stock_items` lo riscrive a ogni riga — con due diversi
        # vincerebbe l'ultimo, in silenzio. L'interfaccia non manda mai questa
        # coppia; se arriva, è un client sbagliato, e si rifiuta prima di scrivere.
        seen: dict[uuid.UUID, uuid.UUID] = {}
        for entry in self.entries:
            if seen.setdefault(entry.shopping_item_id, entry.ingredient_id) != entry.ingredient_id:
                raise ValueError("le confezioni di una voce sono dello stesso ingrediente")
        return self
