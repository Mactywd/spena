import uuid

from pydantic import BaseModel, Field

from app.db.models.recipe import RecipeSource
from app.domain.rules import Availability, IngredientRole


class RecipeIngredientIn(BaseModel):
    ingredient_id: uuid.UUID
    role: IngredientRole
    quantity_text: str | None = Field(default=None, max_length=100)
    note: str | None = Field(default=None, max_length=300)


class RecipeCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    instructions: str = Field(min_length=1)
    servings: int | None = Field(default=None, ge=1, le=50)
    source: RecipeSource
    source_ref: str | None = Field(default=None, max_length=500)
    ingredients: list[RecipeIngredientIn] = Field(default_factory=list)


class RecipeIngredientOut(BaseModel):
    ingredient_id: uuid.UUID
    ingredient_name: str
    role: IngredientRole
    quantity_text: str | None
    note: str | None
    availability: Availability
    satisfied: bool


class RecipeOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    instructions: str
    servings: int | None
    source: str
    source_ref: str | None
    ingredients: list[RecipeIngredientOut]
    missing: int
    cookable: bool
    # stesse quattro righe di RecipeSummaryOut: RecipeOut non eredita da lei oggi,
    # e introdurre una gerarchia per risparmiarle non sarebbe YAGNI rispettato
    image_url: str | None = None
    prep_minutes: int | None = None
    cook_minutes: int | None = None
    category: str | None = None


class RecipeSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    source: str
    missing: int
    cookable: bool
    image_url: str | None = None
    prep_minutes: int | None = None
    cook_minutes: int | None = None
    category: str | None = None


class SearchModeOut(BaseModel):
    """Se la ricerca del ricettario è ibrida o solo testuale, in questo momento.

    La spec §11 vuole un avviso discreto quando il modello di embedding non si
    carica. Sta in una rotta sua e non nella risposta di /recipes/search perché
    quella è un elenco e incartarla cambierebbe un contratto che funziona; lo schermo
    Ricette la chiede una volta e mostra la riga se `semantic` è falso.
    """

    semantic: bool
