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
