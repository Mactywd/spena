import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.ingredient import Ingredient
from app.db.models.recipe import Recipe, RecipeIngredient
from app.domain.quantities import parse_quantity
from app.domain.rules import IngredientKind
from app.repositories.units import ensure_unit

# Una riga di ricetta come la scrivono i chiamanti: (ingredient_id, role,
# quantity_text, note). Una tupla e non un modello perché è la forma che la
# materializzazione, il seme e i test passano da sempre a `create_recipe`.
IngredientLine = tuple[uuid.UUID, str, str | None, str | None]


class NonFoodInRecipe(Exception):
    """Una riga di ricetta punta a una voce non alimentare.

    Porta il nome visibile della voce perché il messaggio all'utente deve dire
    **quale**: su una ricetta di dodici righe, «una voce non alimentare» non è
    un'indicazione, è un indovinello.
    """

    def __init__(self, display_name: str) -> None:
        super().__init__(display_name)
        self.display_name = display_name


async def _refuse_non_food(session: AsyncSession, ingredients: list[IngredientLine]) -> None:
    # Una query sola per tutta la ricetta, e sul `kind` invece che sulla lista dei
    # reparti: la partizione vive in un posto solo (`kind_for_category`), e qui si
    # legge il suo risultato.
    #
    # Solleva, e non salta la riga: se le guardie a monte tengono — la decisione
    # della coda, l'AI dell'import, i selettori `kind=food` del modulo — questa non è
    # raggiungibile. È l'ultima linea, e ci si arriva solo perché qualcosa più in alto
    # ha un buco; una riga saltata in silenzio produrrebbe una ricetta mutilata che
    # nessuno ha chiesto.
    if not ingredients:
        return
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


async def write_recipe_ingredients(
    session: AsyncSession, recipe: Recipe, ingredients: list[IngredientLine]
) -> None:
    """L'unico punto che scrive `recipe_ingredients`, alla creazione e alla modifica.

    Sostituisce le righe: quelle che non ci sono più si cancellano, le altre si
    riscrivono (R10 §5). Il controllo sul non alimentare viene prima di ogni
    scrittura, così un rifiuto lascia la ricetta esattamente com'era.

    Su una ricetta già salvata la collezione `recipe.ingredients` dev'essere caricata
    (`get_recipe` la carica): leggerla pigra in una sessione async è un MissingGreenlet.
    """
    await _refuse_non_food(session, ingredients)
    if recipe.ingredients:
        # le vecchie righe se ne vanno con un flush loro, prima che arrivino le nuove:
        # in un flush unico SQLAlchemy inserisce prima di cancellare, e lo stesso
        # ingrediente riscritto violerebbe l'unicità (recipe_id, ingredient_id)
        recipe.ingredients.clear()
        await session.flush()
    for ingredient_id, role, quantity_text, note in ingredients:
        # Il parser gira qui e non nei chiamanti: questo è l'unico punto che scrive
        # recipe_ingredients, e chiedere a ogni chiamante di ricordarsene
        # significherebbe che il prossimo — quello non ancora scritto — se ne
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


async def create_recipe(
    session: AsyncSession,
    *,
    title: str,
    description: str | None,
    instructions: str,
    servings: int | None,
    source: str,
    source_ref: str | None,
    ingredients: list[IngredientLine],
    embedding: list[float] | None,
    cost: int | None = None,
    category: str | None = None,
) -> Recipe:
    recipe = Recipe(
        title=title, description=description, instructions=instructions, servings=servings,
        source=source, source_ref=source_ref, embedding=embedding, cost=cost,
        category=category,
    )
    await write_recipe_ingredients(session, recipe, ingredients)
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


async def recipe_categories(session: AsyncSession) -> list[str]:
    """Le categorie presenti nel ricettario, una volta ciascuna e in ordine.

    Un posto solo per due domande: il filtro del ricettario (`GET /recipes/categories`)
    e il controllo sulla categoria scelta nel modulo (R10). Solo quelle che esistono
    davvero: un filtro che offre voci vuote porta a una schermata vuota.

    Le ricette eliminate non contano: una categoria che resta solo su quelle
    porterebbe a un filtro vuoto (R10).
    """
    rows = await session.execute(
        select(Recipe.category)
        .where(Recipe.category.is_not(None), Recipe.archived_at.is_(None))
        .distinct()
        .order_by(Recipe.category)
    )
    return list(rows.scalars())
