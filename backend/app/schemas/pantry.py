import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.domain.rules import ExpiryState, PantryStatus


class PantryItemOut(BaseModel):
    id: uuid.UUID
    ingredient_id: uuid.UUID
    product_id: uuid.UUID | None
    ingredient_name: str
    ingredient_category: str
    product_name: str | None
    product_brand: str | None
    status: PantryStatus
    fill_percent: int | None
    note: str | None
    # La data com'è stata scritta, e il verdetto già preso. Il secondo esiste perché
    # la soglia dei sette giorni non deve attraversare il confine: il client chiede,
    # non calcola.
    expires_on: date | None
    expiry: ExpiryState | None
    added_at: datetime


class PantryItemCreate(BaseModel):
    ingredient_id: uuid.UUID
    product_id: uuid.UUID | None = None
    status: PantryStatus = PantryStatus.AVAILABLE
    note: str | None = Field(default=None, max_length=300)


# Niente `fill_percent`: dal 2026-09-29 non si scrive più (D1 in docs/prossimi-passi.md).
# Il modello non vieta i campi in più, quindi chi lo mandasse lo vedrebbe ignorato: da
# solo la rotta risponde 400 «niente da modificare».
class PantryItemPatch(BaseModel):
    status: PantryStatus | None = None
    # annullabile, e non `bool = False`: «non l'ho detto» e «mettilo a falso» sono
    # due richieste diverse, e la seconda è l'annulla della X rossa
    archived: bool | None = None
    # `None` qui è una richiesta, non un'assenza: «cancella la scadenza». Per gli
    # altri campi l'annullabile bastava a distinguere le due cose (vedi `archived`);
    # per una data no, perché il valore nullo è esso stesso un comando. Chi legge
    # questo campo deve guardare `model_fields_set`.
    expires_on: date | None = None


class RestockOut(BaseModel):
    """`added` falso non è un errore: la voce era già da comprare."""

    added: bool
