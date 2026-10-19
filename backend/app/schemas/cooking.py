import uuid
from decimal import Decimal

from pydantic import BaseModel, Field, model_validator

from app.domain.quantities import ANCHOR_AMOUNT_CEILING
from app.domain.rules import PantryStatus


class TransitionIn(BaseModel):
    pantry_item_id: uuid.UUID
    to_status: PantryStatus
    restock: bool = False


class CookRequest(BaseModel):
    servings: int | None = Field(default=None, ge=1, le=50)
    # R2, secondo modo: la dose fissata da cui si è riscalato, con le regole del dettaglio
    # (`GET /recipes/{id}`): insieme o niente, mai con `servings`
    anchor: uuid.UUID | None = None
    amount: Decimal | None = Field(
        default=None, gt=0, lt=ANCHOR_AMOUNT_CEILING, decimal_places=3
    )
    transitions: list[TransitionIn] = Field(default_factory=list)

    @model_validator(mode="after")
    def _one_scale_at_a_time(self) -> "CookRequest":
        if (self.anchor is None) != (self.amount is None):
            raise ValueError("`anchor` e `amount` vanno insieme")
        if self.anchor is not None and self.servings is not None:
            raise ValueError("un modo alla volta: `servings` oppure `anchor` con `amount`")
        return self


class CookResultOut(BaseModel):
    event_id: uuid.UUID
    # quante confezioni hanno cambiato stato (una transizione allo stesso stato no)
    updated: int
    restocked: int
