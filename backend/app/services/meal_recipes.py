"""La ricetta di un pasto scritta da Claude, e «Annulla» (spec 2026-11-12 §4.3, §5.3, §6.3).

Fanno `flush`, mai `commit`: il commit è del chiamante.
"""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.meal import Meal
from app.db.models.recipe import Recipe, RecipeSource
from app.db.models.recipe_change import RecipeChange
from app.domain.recipe_changes import (
    LineSnapshot,
    MealSnapshot,
    RecipeSnapshot,
    changed_parts,
    changed_to_json,
    snapshot_from_json,
    snapshot_to_json,
)
from app.domain.rules import IngredientKind, IngredientRole
from app.repositories.ingredients import delete_ingredient_if_unused
from app.repositories.meals import get_meal, lock_meal
from app.repositories.recipes import (
    IngredientLine,
    NonFoodInRecipe,
    create_recipe,
    get_recipe,
    write_recipe_ingredients,
)
from app.schemas.recipe import RecipeFields, RecipeIngredientIn
from app.services.ingredient_match import ingredient_for_new_name
from app.services.meals import (
    link_recipe,
    refuse_if_no_recipe_here,
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
STALE_WRITE_MESSAGE = (
    "La ricetta di questo pasto è cambiata mentre rispondevi (l'ha corretta Mattia, o ha "
    "annullato una modifica): rileggila con read_meals e riscrivila partendo da com'è "
    "adesso. Non ho scritto niente."
)
INGREDIENT_GONE_MESSAGE = (
    "Un ingrediente della versione di prima non c'è più: correggi la ricetta dal modulo."
)
CREATE_ONLY_MESSAGE = "Il pasto ha già una ricetta: non riscriverla."
MEAL_GONE_MESSAGE = "Il pasto non esiste più."
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


def _invalid(exc: ValidationError, what: str) -> RecipeWriteRefused:
    first = exc.errors()[0]
    field = ".".join(str(part) for part in first["loc"]) or what
    return RecipeWriteRefused(f"{what}: il campo {field} non è valido ({first['msg']}).")


def _check_fields(draft: "MealRecipeDraft") -> None:
    """Le regole dei campi della ricetta, quelle del modulo (`RecipeFields`)."""
    try:
        RecipeFields.model_validate(
            {
                "title": draft.title.strip(),
                "description": draft.description,
                "instructions": draft.instructions,
                "servings": draft.servings,
            }
        )
    except ValidationError as exc:
        raise _invalid(exc, "La ricetta") from exc


async def _to_form_lines(
    session: AsyncSession, lines: tuple[DraftLine, ...]
) -> list[RecipeIngredientIn]:
    """Le righe passano dallo schema del modulo, con le sue regole: note ripulite, lunghezze,
    un nome nuovo solo con il reparto. Un nome senza reparto che l'anagrafica conosce si
    aggancia (`ingredient_for_new_name`, come il modulo); uno che non conosce si rifiuta,
    e non nasce in «altro»."""
    out: list[RecipeIngredientIn] = []
    for number, line in enumerate(lines, start=1):
        ingredient_id, name, category = line.ingredient_id, line.name, line.category
        if ingredient_id is not None:
            name = category = None
        elif name and name.strip() and category is None:
            linked = await ingredient_for_new_name(session, name)
            if linked is None:
                raise RecipeWriteRefused(
                    f"{name} non è in anagrafica: per crearlo serve anche il reparto."
                )
            ingredient_id, name = linked.id, None
        try:
            out.append(
                RecipeIngredientIn.model_validate(
                    {
                        "ingredient_id": ingredient_id,
                        "name": name,
                        "category": category,
                        "role": line.role,
                        "quantity_text": line.quantity_text,
                        "note": line.note,
                    }
                )
            )
        except ValidationError as exc:
            raise _invalid(exc, f"Riga {number}") from exc
    return out


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
    expected: MealSnapshot | None = None,
    allowed_recipe_ids: frozenset[uuid.UUID | None] | None = None,
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

    Con `expected` (l'istantanea che Claude ha visto) scrive solo se il pasto è ancora
    quello: se Mattia l'ha corretto nel frattempo rifiuta, prima di ogni scrittura.

    Con `allowed_recipe_ids` (i giri della coda: `{None}` più le ricette che il giro ha già
    scritto) scrive solo se la ricetta del pasto è fra quelle: una ricetta che c'è già, scritta
    a mano o scelta dal ricettario nel frattempo, non si riscrive.
    """
    title = draft.title.strip()
    description = draft.description
    # Il vettore prima del lucchetto (decisione 7 del quarto giro): `embedding_for` può andare
    # in rete, e col pasto bloccato fermerebbe la coda, la chat e «Annulla». Si decide su una
    # lettura senza lucchetto se serve (il vettore nasce da titolo e descrizione: si rifà solo
    # se cambiano, come in `replace`), e la decisione si rifà sotto il lucchetto, qui sotto.
    seen: Recipe | None = None
    if meal.recipe_id is not None:
        seen = await get_recipe(session, meal.recipe_id)
    new_text_seen = seen is None or (title, description) != (seen.title, seen.description)
    embedding: list[float] | None = None
    if new_text_seen:
        embedding = await embedding_for(title, description)

    # Il lucchetto, prima di ogni controllo (idea 52): due ricette nello stesso istante,
    # l'ultima vince e l'altra resta orfana. Chi arriva secondo aspetta il commit del primo e
    # rilegge il pasto com'è, poi i controlli qui sotto lo trovano con la ricetta già legata.
    locked = await lock_meal(session, meal.id)
    if locked is None:
        raise RecipeWriteRefused(MEAL_GONE_MESSAGE)
    meal = locked  # con `populate_existing` è lo stesso oggetto di chi chiama, riletto
    if allowed_recipe_ids is not None and meal.recipe_id not in allowed_recipe_ids:
        raise RecipeWriteRefused(CREATE_ONLY_MESSAGE)
    refuse_if_no_recipe_here(meal)
    _check_fields(draft)
    meal_id = meal.id
    before = await meal_snapshot(session, meal)
    if expected is not None and before != expected:
        raise RecipeWriteRefused(STALE_WRITE_MESSAGE)
    recipe: Recipe | None = None
    if meal.recipe_id is not None:
        recipe = await get_recipe(session, meal.recipe_id)
        assert recipe is not None
        if recipe.archived_at is not None:
            raise RecipeWriteRefused(RECIPE_DELETED_MESSAGE)
    created = recipe is None
    new_ingredients: list[uuid.UUID] = []
    new_text = recipe is None or (title, description) != (recipe.title, recipe.description)
    if new_text and not new_text_seen:
        # La corsa rara: fra la lettura e il lucchetto qualcuno ha cambiato titolo o
        # descrizione della ricetta. Solo qui il vettore si calcola col pasto bloccato. Nel
        # caso opposto il vettore già calcolato non serve e la ricetta tiene il suo; quando
        # le due decisioni lo chiedono, vale lo stesso, perché nasce solo dalla bozza.
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
            lines = await resolve_lines(
                session, await _to_form_lines(session, draft.lines), created=new_ingredients
            )
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
    except Exception as exc:
        # il rollback del SAVEPOINT scade gli oggetti: il pasto che chi chiama ha in mano
        # si ricarica, o la prima lettura dopo il rifiuto sarebbe un MissingGreenlet. Vale
        # per ogni eccezione, non solo per i rifiuti: un errore del database, a metà
        # scrittura, scade il pasto allo stesso modo.
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
        created_ingredient_ids=[str(i) for i in new_ingredients],
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


async def undoable_change_ids(
    session: AsyncSession, changes: list[RecipeChange]
) -> set[uuid.UUID]:
    """Quali modifiche si possono annullare: non annullate, e ricetta e piatto sono ancora
    esattamente come le ha lasciate. Il pasto si legge una volta sola per pasto, non una per
    modifica: la vista della chat costa lo stesso con una modifica o con otto."""
    open_changes = [c for c in changes if c.undone_at is None]
    by_meal: dict[uuid.UUID, list[RecipeChange]] = {}
    for change in open_changes:
        by_meal.setdefault(change.meal_id, []).append(change)

    undoable: set[uuid.UUID] = set()
    for meal_id, group in by_meal.items():
        meal = await get_meal(session, meal_id)
        if meal is None or meal.recipe_id is None:
            continue
        recipe = await session.get(Recipe, meal.recipe_id)
        if recipe is None or recipe.archived_at is not None:
            continue
        current = await meal_snapshot(session, meal)
        for change in group:
            if meal.recipe_id == change.recipe_id and current == snapshot_from_json(change.after):
                undoable.add(change.id)
    return undoable


async def change_is_undoable(session: AsyncSession, change: RecipeChange) -> bool:
    """Non annullata, e ricetta e piatto sono ancora esattamente come li ha lasciati."""
    return change.id in await undoable_change_ids(session, [change])


async def undo_recipe_change(session: AsyncSession, change: RecipeChange) -> None:
    """Rimette la versione di prima, solo se la ricetta e il piatto sono ancora come li ha
    lasciati questa modifica: non sovrascrive mai un lavoro più nuovo (decisione 16)."""
    # Il vettore prima del lucchetto (decisione 7 del quarto giro): se serve lo dice la
    # modifica stessa, perché una modifica annullabile ha la ricetta com'era dopo di lei, e
    # titolo e descrizione si rimettono a quelli di prima. Così `embedding_for`, che può andare
    # in rete, non gira col pasto bloccato.
    before = snapshot_from_json(change.before)
    recompute = not change.created_recipe and bool(
        change.changed["title"] or change.changed["description"]
    )
    restored_embedding: list[float] | None = None
    if recompute:
        assert before.recipe is not None
        restored_embedding = await embedding_for(before.recipe.title, before.recipe.description)

    # Il lucchetto, prima di ogni controllo (idea 52): un «Annulla» nello stesso istante di una
    # scrittura (o di un altro «Annulla») riscriverebbe sopra l'altra. Preso il pasto, la
    # modifica si rilegge: chi l'ha annullata o superata intanto ha già committato.
    if await lock_meal(session, change.meal_id) is None:
        raise ChangeRefusal(ChangeRefusalCode.STALE, MEAL_GONE_MESSAGE)
    await session.refresh(change)
    if change.undone_at is not None:
        raise ChangeRefusal(ChangeRefusalCode.ALREADY_UNDONE, ALREADY_UNDONE_MESSAGE)
    if not await change_is_undoable(session, change):
        raise ChangeRefusal(ChangeRefusalCode.STALE, STALE_MESSAGE)
    meal = await get_meal(session, change.meal_id)
    assert meal is not None

    if before.recipe is not None:
        wanted = {line.ingredient_id for line in before.recipe.lines}
        for ingredient_id in wanted:
            found = await session.get(Ingredient, ingredient_id)
            # sparito, o diventato non alimentare: l'imbuto lo rifiuterebbe
            if found is None or found.kind == IngredientKind.NON_FOOD:
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
            if recompute:
                recipe.embedding = restored_embedding
            recipe.title = before.recipe.title
            recipe.description = before.recipe.description
            recipe.instructions = before.recipe.instructions
            recipe.servings = before.recipe.servings
        meal.dish = before.dish
        meal.sides = before.sides
        change.undone_at = datetime.now(UTC)
        await session.flush()
        # dopo la versione di prima: una ricetta archiviata usa ancora i suoi ingredienti,
        # che restano; se nient'altro li usa, quelli che questa modifica aveva creato vanno
        for ingredient_id in change.created_ingredient_ids:
            await delete_ingredient_if_unused(session, uuid.UUID(ingredient_id))
    await get_meal(session, meal_id)
