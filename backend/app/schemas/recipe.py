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


class RecipeSummaryOut(BaseModel):
    id: uuid.UUID
    title: str
    description: str | None
    source: str
    missing: int
    cookable: bool
