import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.domain.rules import PantryStatus


class PantryItemOut(BaseModel):
    id: uuid.UUID
    ingredient_id: uuid.UUID
    product_id: uuid.UUID | None
    ingredient_name: str
    ingredient_category: str
    product_name: str | None
    product_brand: str | None
    status: PantryStatus
    note: str | None
    added_at: datetime


class PantryItemCreate(BaseModel):
    ingredient_id: uuid.UUID
    product_id: uuid.UUID | None = None
    status: PantryStatus = PantryStatus.AVAILABLE
    note: str | None = Field(default=None, max_length=300)


class PantryItemPatch(BaseModel):
    status: PantryStatus | None = None
    # annullabile, e non `bool = False`: «non l'ho detto» e «mettilo a falso» sono
    # due richieste diverse, e la seconda è l'annulla della X rossa
    archived: bool | None = None
