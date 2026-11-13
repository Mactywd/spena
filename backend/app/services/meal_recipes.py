"""La ricetta di un pasto scritta da Claude, e «Annulla» (spec 2026-11-12 §4.3, §5.3, §6.3).

Fanno `flush`, mai `commit`: il commit è del chiamante.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.meal import Meal
from app.db.models.recipe import Recipe, RecipeSource
from app.db.models.recipe_change import RecipeChange
from app.domain.meals import MealStatus
from app.domain.recipe_changes import (
    LineSnapshot,
    MealSnapshot,
    RecipeSnapshot,
    changed_parts,
    changed_to_json,
    snapshot_from_json,
    snapshot_to_json,
)
from app.domain.rules import IngredientRole
from app.repositories.meals import get_meal
from app.repositories.recipes import (
    IngredientLine,
    NonFoodInRecipe,
    create_recipe,
    get_recipe,
    write_recipe_ingredients,
)
from app.schemas.recipe import RecipeIngredientIn
from app.services.meals import (
    MealRefusal,
    MealRefusalCode,
    link_recipe,
    release_recipe,
)
from app.services.recipe_writing import RepeatedIngredient, embedding_for, resolve_lines


class Unset:
    """Il valore «non cambiare», distinto da `None` («togli»)."""

    _instance: "Unset | None" = None

    def __new__(cls) -> "Unset":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __repr__(self) -> str:
        return "UNSET"

    def __bool__(self) -> bool:
        return False


UNSET = Unset()


@dataclass(frozen=True)
class DraftLine:
    ingredient_id: uuid.UUID | None
    name: str | None
    category: IngredientCategory | None
    role: IngredientRole
    quantity_text: str | None
    note: str | None


@dataclass(frozen=True)
class MealRecipeDraft:
    title: str
    description: str | None
    instructions: str
    servings: int
    lines: tuple[DraftLine, ...]
    summary: str
    dish: str | None = None
    sides: str | None | Unset = UNSET  # UNSET = non cambiare; None = togli


class RecipeWriteRefused(Exception):
    """Una ricetta che non si scrive. `message` è la frase per Claude (o per il chiamante)."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class ChangeRefusalCode(StrEnum):
    ALREADY_UNDONE = "change_undone"
    STALE = "change_stale"


class ChangeRefusal(Exception):
    def __init__(self, code: ChangeRefusalCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


ALREADY_UNDONE_MESSAGE = "Questa modifica è già stata annullata."
STALE_MESSAGE = "La ricetta è cambiata dopo questa modifica: non si può più annullare."
INGREDIENT_GONE_MESSAGE = (
    "Un ingrediente della versione di prima non c'è più: correggi la ricetta dal modulo."
)
RECIPE_DELETED_MESSAGE = (
    "La ricetta di questo pasto è stata eliminata: Mattia deve ripristinarla prima."
)


async def meal_snapshot(session: AsyncSession, meal: Meal) -> MealSnapshot:
    """Piatto, accompagnamenti e ricetta com'è adesso nel database (la ricetta si rilegge
    con `get_recipe`, e si aggiorna se la sessione la teneva già in memoria).

    Le righe non hanno una posizione in tabella: stanno ordinate per ingrediente, così due
    letture della stessa ricetta danno lo stesso snapshot."""
    recipe_snapshot: RecipeSnapshot | None = None
    if meal.recipe_id is not None:
        recipe = await get_recipe(session, meal.recipe_id)
        if recipe is not None:
            await session.refresh(recipe)
            recipe_snapshot = RecipeSnapshot(
                title=recipe.title,
                description=recipe.description,
                instructions=recipe.instructions,
                servings=recipe.servings,
                lines=tuple(
                    LineSnapshot(ri.ingredient_id, ri.role, ri.quantity_text, ri.note)
                    for ri in sorted(recipe.ingredients, key=lambda ri: str(ri.ingredient_id))
                ),
            )
    return MealSnapshot(dish=meal.dish, sides=meal.sides, recipe=recipe_snapshot)


def _check_meal_can_have_recipe(meal: Meal) -> None:
    """Come `check_can_take_recipe`, ma un pasto che ha già la ricetta si riscrive."""
    if meal.leftover_of_id is not None:
        message = "Un avanzo usa la ricetta del pasto da cui viene."
    elif meal.away:
        message = "Un pasto fuori casa non ha una ricetta."
    elif meal.status == MealStatus.DRAFT:
        message = "È una bozza: la ricetta arriva quando diventa ufficiale."
    else:
        return
    raise MealRefusal(MealRefusalCode.NO_RECIPE_HERE, message)


def _to_form_lines(lines: tuple[DraftLine, ...]) -> list[RecipeIngredientIn]:
    # `model_construct`: il modulo esige `category` con un nome nuovo, ma un nome che
    # l'anagrafica già conosce si aggancia senza reparto (`ingredient_for_new_name`), e
    # `resolve_lines` legge soltanto i campi
    return [
        RecipeIngredientIn.model_construct(
            ingredient_id=line.ingredient_id,
            name=None if line.ingredient_id is not None else line.name,
            category=None if line.ingredient_id is not None else line.category,
            role=line.role,
            quantity_text=line.quantity_text,
            note=line.note,
        )
        for line in lines
    ]


def _apply_meal_fields(
    meal: Meal, *, dish: str | None, sides: str | None | Unset
) -> None:
    if dish is not None and dish.strip():
        meal.dish = dish.strip()
    if not isinstance(sides, Unset):
        meal.sides = (sides or "").strip() or None


async def write_meal_recipe(
    session: AsyncSession,
    meal: Meal,
    draft: MealRecipeDraft,
    *,
    conversation_id: uuid.UUID | None = None,
    turn_message_id: uuid.UUID | None = None,
) -> RecipeChange:
    """La sola strada con cui Claude scrive la ricetta di un pasto: la chat del piatto ora,
    la generazione dopo l'ufficializzazione nel piano 4.

    Crea la ricetta (`source = 'ai'`, fuori dal ricettario, legata al pasto) se il pasto non
    ce l'ha, altrimenti la riscrive. Le righe passano da `resolve_lines` e da
    `write_recipe_ingredients`, l'imbuto del modulo: un nome nuovo passa da
    `ingredient_for_new_name` e poi dalla creazione, e un non alimentare si rifiuta.

    Tutto sta in un SAVEPOINT: un rifiuto (`MealRefusal`, `RecipeWriteRefused`) non lascia
    niente di scritto, nemmeno gli ingredienti creati da una riga precedente, e un
    chiamante che scrive più pasti in una transazione perde solo quello rifiutato. Salva la
    versione di prima in un `RecipeChange`, per «Annulla». Fa `flush`, mai `commit`.
    """
    _check_meal_can_have_recipe(meal)
    meal_id = meal.id
    before = await meal_snapshot(session, meal)
    recipe: Recipe | None = None
    if meal.recipe_id is not None:
        recipe = await get_recipe(session, meal.recipe_id)
        assert recipe is not None
        if recipe.archived_at is not None:
            raise RecipeWriteRefused(RECIPE_DELETED_MESSAGE)
    created = recipe is None
    title = draft.title.strip()
    description = draft.description
    # il vettore nasce da titolo e descrizione: si rifà solo se cambiano, come in `replace`
    embedding: list[float] | None = None
    new_text = recipe is None or (title, description) != (recipe.title, recipe.description)
    if new_text:
        embedding = await embedding_for(title, description)

    try:
        async with session.begin_nested():
            for line in draft.lines:
                if line.ingredient_id is None and not (line.name or "").strip():
                    raise RecipeWriteRefused(
                        "Una riga non dice quale ingrediente è: serve `ingredient_id` "
                        "oppure il nome."
                    )
                if line.ingredient_id is not None and (
                    await session.get(Ingredient, line.ingredient_id) is None
                ):
                    raise RecipeWriteRefused(
                        f"L'ingrediente {line.ingredient_id} non esiste: "
                        "cercalo di nuovo con search_ingredients."
                    )
            lines = await resolve_lines(session, _to_form_lines(draft.lines))
            if recipe is None:
                recipe = await create_recipe(
                    session,
                    title=title,
                    description=description,
                    instructions=draft.instructions,
                    servings=draft.servings,
                    source=RecipeSource.AI,
                    source_ref=None,
                    ingredients=lines,
                    embedding=embedding,
                    in_book=False,
                )
                await link_recipe(session, meal, recipe)
            else:
                await write_recipe_ingredients(session, recipe, lines)
                recipe.title = title
                recipe.description = description
                recipe.instructions = draft.instructions
                recipe.servings = draft.servings
                if new_text:
                    recipe.embedding = embedding
            _apply_meal_fields(meal, dish=draft.dish, sides=draft.sides)
            await session.flush()
    except (NonFoodInRecipe, RepeatedIngredient, RecipeWriteRefused) as exc:
        # il rollback del SAVEPOINT scade gli oggetti: il pasto che chi chiama ha in mano
        # si ricarica, o la prima lettura dopo il rifiuto sarebbe un MissingGreenlet
        await get_meal(session, meal_id)
        if isinstance(exc, NonFoodInRecipe):
            raise RecipeWriteRefused(
                f"{exc.display_name} non è un alimento: una ricetta non può averlo. "
                "Togli quella riga o scegli un altro ingrediente."
            ) from exc
        if isinstance(exc, RepeatedIngredient):
            raise RecipeWriteRefused(
                f"Due righe puntano allo stesso ingrediente, {exc.display_name}: tienine una."
            ) from exc
        raise

    assert recipe is not None
    meal = (await get_meal(session, meal_id)) or meal
    after = await meal_snapshot(session, meal)
    assert after.recipe is not None
    change = RecipeChange(
        meal_id=meal_id,
        recipe_id=recipe.id,
        conversation_id=conversation_id,
        turn_message_id=turn_message_id,
        created_recipe=created,
        summary=" ".join(draft.summary.split())[:200],
        before=snapshot_to_json(before),
        after=snapshot_to_json(after),
        changed=changed_to_json(
            changed_parts(before.recipe, after.recipe), after.recipe.lines
        ),
    )
    session.add(change)
    await session.flush()
    return change


async def change_is_undoable(session: AsyncSession, change: RecipeChange) -> bool:
    """Non annullata, e ricetta e piatto sono ancora esattamente come li ha lasciati."""
    if change.undone_at is not None:
        return False
    meal = await get_meal(session, change.meal_id)
    if meal is None or meal.recipe_id != change.recipe_id:
        return False
    recipe = await session.get(Recipe, change.recipe_id)
    if recipe is None or recipe.archived_at is not None:
        return False
    return await meal_snapshot(session, meal) == snapshot_from_json(change.after)


async def undo_recipe_change(session: AsyncSession, change: RecipeChange) -> None:
    """Rimette la versione di prima, solo se la ricetta e il piatto sono ancora come li ha
    lasciati questa modifica: non sovrascrive mai un lavoro più nuovo (decisione 16)."""
    if change.undone_at is not None:
        raise ChangeRefusal(ChangeRefusalCode.ALREADY_UNDONE, ALREADY_UNDONE_MESSAGE)
    if not await change_is_undoable(session, change):
        raise ChangeRefusal(ChangeRefusalCode.STALE, STALE_MESSAGE)
    meal = await get_meal(session, change.meal_id)
    assert meal is not None
    before = snapshot_from_json(change.before)

    if before.recipe is not None:
        wanted = {line.ingredient_id for line in before.recipe.lines}
        for ingredient_id in wanted:
            if await session.get(Ingredient, ingredient_id) is None:
                raise ChangeRefusal(ChangeRefusalCode.STALE, INGREDIENT_GONE_MESSAGE)

    meal_id = meal.id
    async with session.begin_nested():
        if change.created_recipe:
            await release_recipe(session, meal)
        else:
            assert before.recipe is not None
            recipe = await get_recipe(session, change.recipe_id)
            assert recipe is not None
            lines: list[IngredientLine] = [
                (line.ingredient_id, line.role, line.quantity_text, line.note)
                for line in before.recipe.lines
            ]
            await write_recipe_ingredients(session, recipe, lines)
            if (before.recipe.title, before.recipe.description) != (
                recipe.title, recipe.description
            ):
                recipe.embedding = await embedding_for(
                    before.recipe.title, before.recipe.description
                )
            recipe.title = before.recipe.title
            recipe.description = before.recipe.description
            recipe.instructions = before.recipe.instructions
            recipe.servings = before.recipe.servings
        meal.dish = before.dish
        meal.sides = before.sides
        change.undone_at = datetime.now(UTC)
        await session.flush()
    await get_meal(session, meal_id)
