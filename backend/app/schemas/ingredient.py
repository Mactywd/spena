import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.db.models.ingredient import IngredientCategory


class IngredientOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    display_name: str
    category: str
    # detto dal server e non calcolato dal client: la partizione dei reparti vive
    # in `kind_for_category`, e una seconda copia nel frontend si scollerebbe
    kind: str


class IngredientCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    display_name: str = Field(min_length=1, max_length=120)
    category: IngredientCategory


class AliasCreate(BaseModel):
    alias: str = Field(min_length=1, max_length=120)
    source: str = Field(default="manual", max_length=20)


class AliasOut(BaseModel):
    id: uuid.UUID
    alias: str
    source: str
    # vero se l'alias è la metà di una decisione della coda: si corregge da lì (§4)
    decided_in_queue: bool


class ProductBriefOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    brand: str | None
    barcode: str | None


class IngredientUsageOut(BaseModel):
    recipes: int
    pantry: int
    shopping: int


class IngredientDetailOut(IngredientOut):
    """La scheda dell'ingrediente: cos'è, i suoi alias, i suoi prodotti, e dove è
    usato — così il peso di una correzione si vede prima di farla (spec §6.3)."""

    aliases: list[AliasOut]
    products: list[ProductBriefOut]
    usage: IngredientUsageOut


class IngredientPatch(BaseModel):
    """`name` scrive il nome canonico e il nome a video insieme: nell'app si rinomina
    una cosa sola. Il nome a video da solo resta della CLI.

    L'annotazione di entrambi i campi è quella non annullabile (`str`, `IngredientCategory`),
    non `| None`, anche se il default è `None`: Pydantic non valida un default omesso,
    quindi il campo assente resta `None` — «non l'ho detto» — ma un `null` scritto a
    mano viene validato contro il tipo vero e respinto con un 422, invece di passare
    come «nessun cambiamento» in silenzio. Né il nome né il reparto di un ingrediente
    possono mai essere nulli in colonna (F17): chi manda `null` ha sbagliato, e deve
    saperlo subito."""

    name: str = Field(default=None, min_length=1, max_length=120)  # type: ignore[assignment]
    category: IngredientCategory = Field(default=None)  # type: ignore[assignment]


class MergeIn(BaseModel):
    into: uuid.UUID
    dry_run: bool = False


class MergeOut(BaseModel):
    dry_run: bool
    loser_name: str
    winner_id: uuid.UUID
    winner_name: str
    recipes_rebuilt: int
    recipe_lines_moved: int
    pantry_items: int
    shopping_items: int
    shopping_items_dropped: int
    products: int
    aliases: int
    cooking_events_relinked: int


class AliasMoveIn(BaseModel):
    ingredient_id: uuid.UUID


class AliasMovedOut(BaseModel):
    # `None` se l'alias era il nome stesso dell'ingrediente d'arrivo, e quindi è sparito
    alias: AliasOut | None
    ingredient: IngredientOut
