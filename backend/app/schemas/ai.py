import uuid

from pydantic import BaseModel, Field

from app.domain.rules import IngredientRole


class DraftRequest(BaseModel):
    prompt: str = Field(min_length=3, max_length=1000)


class DraftIngredientOut(BaseModel):
    raw_name: str
    role: IngredientRole
    quantity_text: str | None
    ingredient_id: uuid.UUID | None
    matched_name: str | None
    confident: bool
    proposed_category: str | None = None


class DraftOut(BaseModel):
    title: str
    description: str | None
    instructions: str
    servings: int | None
    ingredients: list[DraftIngredientOut]
    cost: int | None = None
