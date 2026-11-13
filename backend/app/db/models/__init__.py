"""Importa tutti i modelli perché `Base.metadata` sia completa.

Non è un file da "ripulire": Alembic importa questo pacchetto in `alembic/env.py`
e senza questi import vedrebbe uno schema vuoto, quindi il primo
`alembic revision --autogenerate` proporrebbe di cancellare tutte le tabelle.
"""

from app.db.models.activity import (
    ActivityExercise,
    ActivityStepsDay,
    ActivitySync,
    ActivityToken,
    ActivityWeight,
)
from app.db.models.ingredient import Ingredient, IngredientAlias
from app.db.models.llm_call import LlmCall
from app.db.models.meal import Meal
from app.db.models.nutrition import CiqualFood, IngredientNutrition, IngredientUnitGrams
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.recipe import CookingEvent, Recipe, RecipeIngredient
from app.db.models.recipe_import import ImportTerm, RecipeImport
from app.db.models.shopping import ShoppingListItem
from app.db.models.substitution import IngredientSubstitution, SubstitutionOption
from app.db.models.unit import Unit
from app.db.models.utensil import Utensil

__all__ = [
    "ActivityExercise",
    "ActivityStepsDay",
    "ActivitySync",
    "ActivityToken",
    "ActivityWeight",
    "CiqualFood",
    "CookingEvent",
    "ImportTerm",
    "Ingredient",
    "IngredientAlias",
    "IngredientNutrition",
    "IngredientSubstitution",
    "IngredientUnitGrams",
    "LlmCall",
    "Meal",
    "PantryItem",
    "Product",
    "Recipe",
    "RecipeImport",
    "RecipeIngredient",
    "ShoppingListItem",
    "SubstitutionOption",
    "Unit",
    "Utensil",
]
