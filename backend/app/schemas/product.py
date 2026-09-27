import uuid
from datetime import date
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

    `name` è assente quando Open Food Facts non lo conosce: il modulo parte vuoto e
    lo chiede, invece di proporre un segnaposto che sembri un nome.
    """

    name: str | None
    brand: str | None
    barcode: str
    nutrients: dict[str, float]
    image_url: str | None


class BarcodeLookupOut(BaseModel):
    found: bool
    origin: str  # "catalog" | "openfoodfacts" | "unknown"
    product: ProductOut | None = None
    suggestion: ProductSuggestion | None = None
    # il verdetto di `has_valid_check_digit`, detto e mai applicato: il lookup si fa
    # comunque, e decidere se proseguire con un codice che non torna spetta a chi ha
    # la confezione in mano (codici interni di negozio, etichette rovinate)
    valid_checksum: bool


class IngredientRefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str


class ProductPantryItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    status: str
    expires_on: date | None


class ProductDetailOut(BaseModel):
    """La scheda del prodotto (spec §6.4): la scheda dell'elemento di dispensa è questa,
    e l'ingrediente sta qui come link."""

    id: uuid.UUID
    name: str
    brand: str | None
    barcode: str | None
    # il verdetto di `has_valid_check_digit`, detto e mai applicato; `None` senza codice
    valid_checksum: bool | None
    ingredient: IngredientRefOut
    # solo gli attivi: sono quelli che chi guarda la dispensa vede
    pantry_items: list[ProductPantryItemOut]


class ProductPatch(BaseModel):
    """Ogni campo si legge da `model_fields_set`: `brand: null` e `barcode: null` sono
    richieste («toglila», «toglilo»), non assenze.

    `name` e `ingredient_id` non possono mai essere nulli in colonna (F17), quindi
    portano l'annotazione non annullabile con default `None` — la stessa tecnica di
    `IngredientPatch`: un campo assente resta `None` («non l'ho detto»), mentre un
    `null` scritto a mano è validato contro il tipo vero e respinto con un 422.
    `brand` e `barcode` si possono legittimamente svuotare, quindi restano `| None`.

    `take_barcode` prende il codice a chi l'ha già; `accept_bad_checksum` lo usa anche se
    la cifra di controllo non torna. Sono le due uscite dei due rifiuti del codice
    (spec §7).
    """

    name: str = Field(default=None, min_length=1, max_length=200)  # type: ignore[assignment]
    brand: str | None = Field(default=None, max_length=120)
    ingredient_id: uuid.UUID = Field(default=None)  # type: ignore[assignment]
    barcode: str | None = Field(default=None, max_length=20)
    take_barcode: bool = False
    accept_bad_checksum: bool = False


class ProductDeletedOut(BaseModel):
    """Quanti elementi di dispensa attivi sono rimasti, sfusi: è quel che la conferma
    aveva promesso."""

    loose_pantry_items: int
