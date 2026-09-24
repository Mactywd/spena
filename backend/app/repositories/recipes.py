import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.ingredient import Ingredient
from app.db.models.recipe import Recipe, RecipeIngredient
from app.domain.quantities import parse_quantity
from app.domain.rules import IngredientKind
from app.repositories.units import ensure_unit


class NonFoodInRecipe(Exception):
    """Una riga di ricetta punta a una voce non alimentare.

    Porta il nome visibile della voce perché il messaggio all'utente deve dire
    **quale**: su una ricetta di dodici righe, «una voce non alimentare» non è
    un'indicazione, è un indovinello.
    """

    def __init__(self, display_name: str) -> None:
        super().__init__(display_name)
        self.display_name = display_name


async def create_recipe(
    session: AsyncSession,
    *,
    title: str,
    description: str | None,
    instructions: str,
    servings: int | None,
    source: str,
    source_ref: str | None,
    ingredients: list[tuple[uuid.UUID, str, str | None, str | None]],
    embedding: list[float] | None,
    cost: int | None = None,
) -> Recipe:
    """`ingredients` è una lista di (ingredient_id, role, quantity_text, note)."""
    # Prima di scrivere qualunque cosa. Una query sola per tutta la ricetta, e sul
    # `kind` invece che sulla lista dei reparti: la partizione vive in un posto
    # solo (`kind_for_category`), e qui si legge il suo risultato.
    #
    # Solleva, e non salta la riga: se le guardie a monte tengono — la decisione
    # della coda e l'AI dell'import — questa non è raggiungibile né dalla
    # materializzazione né dal seme. È l'ultima linea, e ci si arriva solo perché
    # qualcosa più in alto ha un buco; una materializzazione che saltasse la riga
    # in silenzio produrrebbe una ricetta mutilata che nessuno ha chiesto.
    if ingredients:
        non_food = (
            await session.execute(
                select(Ingredient.display_name)
                .where(
                    Ingredient.id.in_({line[0] for line in ingredients}),
                    Ingredient.kind == IngredientKind.NON_FOOD,
                )
                .limit(1)
            )
        ).scalars().first()
        if non_food is not None:
            raise NonFoodInRecipe(non_food)

    recipe = Recipe(
        title=title, description=description, instructions=instructions, servings=servings,
        source=source, source_ref=source_ref, embedding=embedding, cost=cost,
    )
    for ingredient_id, role, quantity_text, note in ingredients:
        # Il parser gira qui e non nei chiamanti: questo è già l'unico punto che
        # scrive recipe_ingredients, e chiedere a ogni chiamante di ricordarsene
        # significherebbe che il quinto — quello non ancora scritto — se ne
        # dimentica.
        value, unit_key = parse_quantity(quantity_text)
        unit = await ensure_unit(session, unit_key) if unit_key else None
        recipe.ingredients.append(
            RecipeIngredient(
                ingredient_id=ingredient_id,
                role=role,
                quantity_text=quantity_text,
                note=note,
                quantity_value=value,
                quantity_unit_id=unit.id if unit else None,
            )
        )
    session.add(recipe)
    await session.flush()
    return recipe


async def get_recipe(session: AsyncSession, recipe_id: uuid.UUID) -> Recipe | None:
    statement = (
        select(Recipe)
        .options(selectinload(Recipe.ingredients).joinedload(RecipeIngredient.ingredient))
        .where(Recipe.id == recipe_id)
    )
    return (await session.execute(statement)).unique().scalar_one_or_none()
