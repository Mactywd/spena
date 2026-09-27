"""I rifiuti dell'anagrafica in HTTP: un 409 con il motivo e l'ostacolo accanto.

La forma è quella che `POST /ingredients` usa da S19 — `detail` con il messaggio, e
l'oggetto d'ostacolo in `existing` — più `code`, che dice allo schermo quale passo
offrire (spec §7). Un posto solo perché le rotte dell'ingrediente e del prodotto devono
dire lo stesso rifiuto nello stesso modo.
"""

from fastapi import status
from fastapi.responses import JSONResponse

from app.db.models.ingredient import Ingredient
from app.db.models.product import Product
from app.db.models.recipe_import import ImportTerm
from app.schemas.ingredient import IngredientOut, ProductBriefOut
from app.services.registry import RecipesInUse, RegistryRefusal


def refusal_response(exc: RegistryRefusal) -> JSONResponse:
    """Da chiamare **prima** del rollback: dopo, l'ostacolo è un oggetto scaduto, e
    leggerlo in una sessione async è un MissingGreenlet."""
    content: dict[str, object] = {"detail": exc.message, "code": exc.code.value}
    obstacle = exc.obstacle
    if isinstance(obstacle, Ingredient):
        content["existing"] = IngredientOut.model_validate(obstacle).model_dump(mode="json")
    elif isinstance(obstacle, Product):
        content["existing"] = ProductBriefOut.model_validate(obstacle).model_dump(mode="json")
    elif isinstance(obstacle, RecipesInUse):
        content["recipe_count"] = obstacle.count
        content["pending_import_count"] = obstacle.pending_imports
        content["recipes"] = [
            {"id": str(recipe.id), "title": recipe.title} for recipe in obstacle.recipes
        ]
    elif isinstance(obstacle, ImportTerm):
        content["term"] = {"id": str(obstacle.id), "display_name": obstacle.display_name.strip()}
    return JSONResponse(content, status_code=status.HTTP_409_CONFLICT)
