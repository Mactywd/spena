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
from app.domain.rules import today_in_pantry
from app.schemas.ingredient import IngredientOut, ProductBriefOut
from app.services.meals import MealRefusal, MealRefusalCode
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
        content["pending_terms"] = [
            {"id": str(term.id), "display_name": term.display_name}
            for term in obstacle.pending_terms
        ]
        content["pending_term_count"] = obstacle.pending_term_count
        content["recipes"] = [
            {
                "id": str(recipe.id),
                "title": recipe.title,
                "archived": recipe.archived,
                "from_meal": recipe.from_meal,
            }
            for recipe in obstacle.recipes
        ]
    elif isinstance(obstacle, ImportTerm):
        content["term"] = {"id": str(obstacle.id), "display_name": obstacle.display_name.strip()}
    return JSONResponse(content, status_code=status.HTTP_409_CONFLICT)


_MEAL_STATUS = {
    MealRefusalCode.SLOT_TAKEN: 409,
    MealRefusalCode.HAS_RECIPE: 409,
    MealRefusalCode.NO_RECIPE_HERE: 409,
    MealRefusalCode.RECIPE_ARCHIVED: 409,
    MealRefusalCode.LEFTOVER_AFTER: 409,
    MealRefusalCode.ORIGIN_OUT_OF_REACH: 409,
    MealRefusalCode.BAD_LEFTOVER: 422,
    MealRefusalCode.STAYS_OFFICIAL: 422,
}


def meal_refusal_response(exc: MealRefusal) -> JSONResponse:
    """Il rifiuto di un pasto. Come `refusal_response`: da chiamare con l'occupante già letto,
    cioè prima del rollback (qui si serializza subito, e `meal_out` non tocca il database)."""
    from app.api.meals import meal_out  # import tardivo: meals.py importa questo modulo

    content: dict[str, object] = {"detail": exc.message, "code": exc.code.value}
    if exc.code == MealRefusalCode.SLOT_TAKEN and exc.occupant is not None:
        content["occupant"] = meal_out(exc.occupant, today_in_pantry()).model_dump(mode="json")
    if exc.code == MealRefusalCode.LEFTOVER_AFTER:
        content["leftovers"] = exc.leftovers
    return JSONResponse(content, status_code=_MEAL_STATUS[exc.code])
