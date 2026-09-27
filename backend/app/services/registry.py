"""Le correzioni dell'anagrafica, in un posto solo (S9).

Due porte le chiamano: le schede dell'anagrafica (`app/api/ingredients.py`,
`app/api/products.py`) e il comando `app.cli.fix_registry`, che corregge a lotti da un
piano scritto. La logica stava nel comando; è stata spostata qui e non ricopiata,
perché una guardia provata su una copia non protegge l'originale (prima lezione di
CLAUDE.md).

Ogni funzione prende la sessione e argomenti tipizzati, e **non fa commit**: chi chiama
decide. È questo che permette all'anteprima della fusione di essere la fusione stessa,
dentro un SAVEPOINT annullato, e al comando di provare un piano intero senza salvarlo.

Un rifiuto è un `RegistryRefusal`: un codice, un messaggio in italiano da mostrare e,
dove serve, l'oggetto che fa da ostacolo — l'omonimo, il prodotto che ha già il codice,
le ricette che usano l'ingrediente. Lo schermo ne ricava il passo dopo invece di un
errore (spec §7). Un id che non esiste è un `LookupError`, come nei repository.
"""

import uuid
from dataclasses import dataclass
from enum import StrEnum

from sqlalchemy import delete, func, inspect, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.recipe import Recipe, RecipeIngredient
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm
from app.db.models.shopping import ShoppingListItem
from app.domain.rules import IngredientKind, IngredientRole, kind_for_category
from app.repositories.ingredients import (
    canonical_name,
    delete_ingredient_if_unused,
    find_by_name,
    remember_alias,
)
from app.services.recipe_import.manual import DecisionRefused, ManualDecision, decide_by_hand
from app.services.recipe_import.materialize import (
    materialize_ready,
    merge_quantities,
    stronger,
)
from app.services.recipe_import.undo import undo_decision

# La fonte degli alias che nascono da una correzione a mano. Non sono la metà di una
# decisione della coda, quindi l'anagrafica li può spostare e togliere.
MANUAL_ALIAS_SOURCE = "manual"

# Quante ricette porta con sé il rifiuto «non alimentare con ricette»: abbastanza per
# riconoscerle, non tutte — «sale» è in migliaia di ricette, e il conto le dice.
RECIPES_SHOWN = 20


class RefusalCode(StrEnum):
    SAME_INGREDIENT = "same_ingredient"
    EMPTY_NAME = "empty_name"
    NAME_TAKEN = "name_taken"
    UNKNOWN_CATEGORY = "unknown_category"
    NON_FOOD_IN_RECIPES = "non_food_in_recipes"
    KIND_MISMATCH = "kind_mismatch"
    IMPORT_ALIAS = "import_alias"
    DECISION_REFUSED = "decision_refused"
    STILL_USED = "still_used"
    BARCODE_TAKEN = "barcode_taken"
    BAD_CHECKSUM = "bad_checksum"


class RegistryRefusal(Exception):
    """Una correzione che non si può applicare così com'è, detta con il suo perché."""

    def __init__(
        self, code: RefusalCode, message: str, obstacle: object | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.obstacle = obstacle


@dataclass(frozen=True)
class RecipeRef:
    id: uuid.UUID
    title: str


@dataclass(frozen=True)
class RecipesInUse:
    count: int
    recipes: tuple[RecipeRef, ...]


@dataclass(frozen=True)
class MergeCounts:
    """Quel che una fusione ha mosso (spec §5.1). Gli stessi numeri escono
    dall'anteprima, perché l'anteprima è questa stessa fusione annullata."""

    loser_name: str
    winner_name: str
    recipes_rebuilt: int  # ricette dell'import rifatte dal loro `payload`
    recipe_lines_moved: int  # righe di ricette non importate, spostate sul vincitore
    pantry_items: int
    shopping_items: int
    products: int
    aliases: int  # alias che il vincitore guadagna, nome del perdente compreso
    cooking_events_relinked: int


async def _ingredient(session: AsyncSession, ingredient_id: uuid.UUID) -> Ingredient:
    ingredient = await session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise LookupError(f"nessun ingrediente {ingredient_id}")
    return ingredient


async def recipes_using(session: AsyncSession, ingredient_id: uuid.UUID) -> RecipesInUse:
    """Quante ricette usano l'ingrediente, e le prime `RECIPES_SHOWN` per titolo.

    Il conto è una query sua e non la lunghezza dell'elenco: l'elenco è tagliato, il
    conto no (sesta lezione di CLAUDE.md, un limite davanti a quel che si conta).
    """
    count = (
        await session.execute(
            select(func.count())
            .select_from(RecipeIngredient)
            .where(RecipeIngredient.ingredient_id == ingredient_id)
        )
    ).scalar_one()
    rows = await session.execute(
        select(Recipe.id, Recipe.title)
        .join(RecipeIngredient, RecipeIngredient.recipe_id == Recipe.id)
        .where(RecipeIngredient.ingredient_id == ingredient_id)
        .order_by(Recipe.title, Recipe.id)
        .limit(RECIPES_SHOWN)
    )
    return RecipesInUse(
        count=count, recipes=tuple(RecipeRef(id=row.id, title=row.title) for row in rows)
    )


async def rename_ingredient(
    session: AsyncSession,
    ingredient_id: uuid.UUID,
    *,
    name: str | None = None,
    display_name: str | None = None,
) -> Ingredient:
    """Il nome canonico e il nome a video. Il vecchio nome resta come alias, così chi
    lo scrive in lista trova ancora l'ingrediente.

    Tutti i controlli vengono prima di ogni scrittura: un rifiuto a metà lascerebbe
    un ingrediente col nome nuovo e il nome a video vecchio.
    """
    ingredient = await _ingredient(session, ingredient_id)
    new_name = canonical_name(name) if name is not None else None
    new_display = display_name.strip() if display_name is not None else None
    if new_name == "" or new_display == "":
        raise RegistryRefusal(RefusalCode.EMPTY_NAME, "Il nome non può essere vuoto.")
    if new_name is not None and new_name != ingredient.name:
        taken = await find_by_name(session, new_name)
        if taken is not None:
            raise RegistryRefusal(
                RefusalCode.NAME_TAKEN,
                f"«{new_name}» è già in anagrafica: uniscili invece di rinominare.",
                taken,
            )

    old_name = ingredient.name
    if new_name is not None and new_name != ingredient.name:
        # l'alias uguale al nome nuovo diventerebbe un doppione del nome
        await session.execute(
            delete(IngredientAlias).where(
                IngredientAlias.ingredient_id == ingredient.id,
                IngredientAlias.alias == new_name,
            )
        )
        ingredient.name = new_name
    if new_display is not None:
        ingredient.display_name = new_display
    await session.flush()
    if old_name != ingredient.name:
        await remember_alias(session, ingredient.id, old_name, source=MANUAL_ALIAS_SOURCE)
    return ingredient


async def recategorize_ingredient(
    session: AsyncSession, ingredient_id: uuid.UUID, category: str
) -> Ingredient:
    """Il reparto, e con lui `kind`, che il `@validates` del modello deriva.

    Un ingrediente che una ricetta usa non diventa non alimentare: le ricette puntano
    solo al cibo (decisione fondante 2), e il rifiuto porta le ricette perché lo
    schermo le elenchi, ciascuna col suo link.
    """
    ingredient = await _ingredient(session, ingredient_id)
    if category not in {c.value for c in IngredientCategory}:
        raise RegistryRefusal(RefusalCode.UNKNOWN_CATEGORY, f"reparto sconosciuto: «{category}»")
    if kind_for_category(category) == IngredientKind.NON_FOOD:
        in_use = await recipes_using(session, ingredient.id)
        if in_use.count:
            recipes = "1 ricetta" if in_use.count == 1 else f"{in_use.count} ricette"
            raise RegistryRefusal(
                RefusalCode.NON_FOOD_IN_RECIPES,
                f"«{ingredient.display_name}» è in {recipes}: non può diventare non "
                "alimentare finché una ricetta lo usa.",
                in_use,
            )
    ingredient.category = str(category)
    await session.flush()
    return ingredient


async def queue_terms_by_alias(
    session: AsyncSession, ingredient_id: uuid.UUID
) -> dict[str, ImportTerm]:
    """I termini della coda decisi su questo ingrediente, per l'alias che hanno scritto.

    La chiave è normalizzata come in `remember_alias` (strip e minuscole), in Python e
    non in SQL: è la stessa operazione che ha scritto l'alias, quindi le due non
    possono dare risposte diverse sullo stesso nome.
    """
    rows = await session.execute(
        select(ImportTerm).where(ImportTerm.ingredient_id == ingredient_id)
    )
    return {term.display_name.strip().lower(): term for term in rows.scalars()}


def queue_decision_for(
    alias: IngredientAlias, terms_by_alias: dict[str, ImportTerm]
) -> ImportTerm | None:
    """Il termine della coda che ha scritto `alias`, se ce n'è uno.

    Un alias è la metà di una decisione dell'import quando `source == "import"` **e**
    un termine in coda porta ancora il suo nome (normalizzato come `queue_terms_by_alias`).
    Regola scritta una volta sola: la usano sia la guardia qui sotto, che rifiuta di
    toccare l'alias da qui, sia le rotte dell'anagrafica (Task 9), che decidono se
    mostrare «Sposta» accanto a un alias.
    """
    if alias.source != "import":
        return None
    return terms_by_alias.get(alias.alias)


async def _alias(session: AsyncSession, alias_id: uuid.UUID) -> IngredientAlias:
    alias = await session.get(IngredientAlias, alias_id)
    if alias is None:
        raise LookupError(f"nessun alias {alias_id}")
    return alias


async def _refuse_import_alias(session: AsyncSession, alias: IngredientAlias) -> None:
    """Un alias `import` che ha il suo termine nella coda è la metà di una decisione.

    Spostarlo da qui lascerebbe la coda a dire una cosa e l'anagrafica un'altra: si
    corregge dalla coda, dove R11 mostra anche le decisioni prese a mano. Un alias
    `import` *senza* termine — il vecchio nome scritto da un `merge` o da un `rename`
    della CLI prima di S9 — non è la metà di niente, e si corregge da qui: rifiutarlo
    sarebbe un vicolo cieco, perché nella coda non c'è niente da correggere.
    """
    terms_by_alias = await queue_terms_by_alias(session, alias.ingredient_id)
    term = queue_decision_for(alias, terms_by_alias)
    if term is not None:
        raise RegistryRefusal(
            RefusalCode.IMPORT_ALIAS,
            f"«{alias.alias}» viene dalla decisione su «{term.display_name.strip()}» nella "
            "coda: si corregge da lì, così la coda e l'anagrafica dicono la stessa cosa.",
            term,
        )


async def move_alias(
    session: AsyncSession, alias_id: uuid.UUID, target_id: uuid.UUID
) -> IngredientAlias | None:
    """L'alias passa a `target_id`. Torna la riga che ora lo porta su quell'ingrediente,
    oppure `None`: se l'alias era il nome stesso dell'ingrediente d'arrivo (un alias
    uguale al nome è un doppione, e sparisce) o se un terzo ingrediente lo porta già.

    `remember_alias` e non un inserimento diretto: è la regola che impedisce lo stesso
    alias su due ingredienti, cioè un autocomplete con due risposte.
    """
    alias = await _alias(session, alias_id)
    target = await _ingredient(session, target_id)
    await _refuse_import_alias(session, alias)
    text = alias.alias
    await session.delete(alias)
    await session.flush()
    if text != target.name:
        await remember_alias(session, target.id, text, source=MANUAL_ALIAS_SOURCE)
    return (
        await session.execute(
            select(IngredientAlias).where(
                IngredientAlias.ingredient_id == target.id, IngredientAlias.alias == text
            )
        )
    ).scalars().first()


async def delete_alias(session: AsyncSession, alias_id: uuid.UUID) -> None:
    """Toglie un alias che non è la metà di una decisione della coda."""
    alias = await _alias(session, alias_id)
    await _refuse_import_alias(session, alias)
    await session.delete(alias)
    await session.flush()


async def _repoint(
    session: AsyncSession, model: type, loser_id: uuid.UUID, winner_id: uuid.UUID
) -> int:
    result = await session.execute(
        update(model).where(model.ingredient_id == loser_id).values(ingredient_id=winner_id)
    )
    return result.rowcount or 0


async def _alias_count(session: AsyncSession, ingredient_id: uuid.UUID) -> int:
    return (
        await session.execute(
            select(func.count())
            .select_from(IngredientAlias)
            .where(IngredientAlias.ingredient_id == ingredient_id)
        )
    ).scalar_one()


async def merge_ingredients(
    session: AsyncSession, loser_id: uuid.UUID, winner_id: uuid.UUID
) -> MergeCounts:
    """Tutto quel che punta al perdente passa al vincitore, e il perdente sparisce.

    Termini dell'import, dispensa, lista, prodotti, righe di ricetta, alias: i termini
    si annullano e si ridecidono sul vincitore, così le loro ricette si rifanno dal
    `payload` invece di una chirurgia su `recipe_ingredients`; le righe delle ricette
    scritte a mano o dall'AI si spostano. Il nome del perdente resta come alias del
    vincitore: chi lo scrive nella lista trova ancora qualcosa. Le pagine rimesse in
    attesa tornano ricette qui dentro, e le loro cotture con loro (§5.2).

    È l'unica correzione che non si annulla: per questo `preview_merge` la esegue
    tutta dentro un SAVEPOINT prima di chiedere conferma.

    Un `RegistryRefusal` sollevato a metà lascia la sessione parzialmente cambiata
    (termini annullati, righe spostate): chi chiama deve fare rollback, non salvare.
    """
    loser = await _ingredient(session, loser_id)
    winner = await _ingredient(session, winner_id)
    if loser.id == winner.id:
        raise RegistryRefusal(
            RefusalCode.SAME_INGREDIENT,
            f"«{loser.display_name}» non si unisce a sé stesso: scegli un altro ingrediente.",
        )
    if loser.kind != winner.kind:
        raise RegistryRefusal(
            RefusalCode.KIND_MISMATCH,
            f"«{loser.display_name}» e «{winner.display_name}» stanno in due metà diverse "
            "dell'anagrafica: un alimento e una voce non alimentare non si uniscono. "
            f"Prima porta «{loser.display_name}» nello stesso reparto di "
            f"«{winner.display_name}», poi uniscili.",
            winner,
        )
    loser_name, winner_name = loser.name, winner.name
    # I nomi si fotografano prima: l'annullamento dell'ultimo termine può cancellare
    # l'ingrediente, e i suoi alias con lui. Gli alias con una query e non con
    # `loser.aliases`: `session.get` restituisce l'oggetto che la sessione ha già, e se
    # quella collezione non è mai stata caricata leggerla è un caricamento pigro — in
    # una sessione async, un MissingGreenlet. La CLI non lo vedeva perché trovava
    # l'ingrediente con una `select`, che la carica.
    alias_names = list(
        (
            await session.execute(
                select(IngredientAlias.alias).where(IngredientAlias.ingredient_id == loser.id)
            )
        ).scalars()
    )
    names = [loser.name, loser.display_name, *alias_names]
    aliases_before = await _alias_count(session, winner.id)

    terms = list(
        (await session.execute(select(ImportTerm).where(ImportTerm.ingredient_id == loser_id))).scalars()
    )
    for term in terms:
        role = term.role_override
        await undo_decision(session, term)
        try:
            await decide_by_hand(
                session, term,
                ManualDecision(action="map", ingredient_id=winner.id, role_override=role),
            )
        except DecisionRefused as exc:
            # `exc.message` qui è sempre quello di `decide_by_hand` sul non
            # alimentare («Scegline un'altra, oppure ignora il termine»): un vicolo
            # cieco dentro una fusione, dove non si sceglie un altro ingrediente per
            # il termine. Il passo vero è nella coda, dove il termine si annulla o si
            # ignora; `obstacle=term` lascia lo schermo linkarcela.
            raise RegistryRefusal(
                RefusalCode.DECISION_REFUSED,
                f"Il termine «{term.display_name}» dell'import non può finire su "
                f"«{winner.display_name}», che non è un alimento: annullalo o ignoralo "
                "in «Ingredienti da abbinare», poi riprova.",
                term,
            ) from exc

    pantry_items = await _repoint(session, PantryItem, loser_id, winner.id)
    shopping_items = await _repoint(session, ShoppingListItem, loser_id, winner.id)
    products = await _repoint(session, Product, loser_id, winner.id)

    # Le righe rimaste sono di ricette che non vengono dall'import (scritte a mano o
    # con l'AI): quelle non si rifanno da un payload, si spostano. Se la ricetta ha
    # già una riga del vincitore, le due diventano una come nella materializzazione.
    lines = list(
        (
            await session.execute(
                select(RecipeIngredient).where(RecipeIngredient.ingredient_id == loser_id)
            )
        ).scalars()
    )
    for line in lines:
        twin = (
            await session.execute(
                select(RecipeIngredient).where(
                    RecipeIngredient.recipe_id == line.recipe_id,
                    RecipeIngredient.ingredient_id == winner.id,
                )
            )
        ).scalars().first()
        if twin is None:
            line.ingredient_id = winner.id
            continue
        twin.role = stronger(IngredientRole(twin.role), IngredientRole(line.role))
        twin.quantity_text = merge_quantities(twin.quantity_text, line.quantity_text)
        # «500 g + 50 g» non è una dose che il riporziona sappia leggere: la riga
        # smette di scalare, che è onesto, invece di scalare solo metà.
        twin.quantity_value = None
        twin.quantity_unit_id = None
        await session.delete(line)
    await session.flush()

    await session.execute(delete(IngredientAlias).where(IngredientAlias.ingredient_id == loser_id))
    await session.flush()
    survivor = await session.get(Ingredient, loser_id)
    if survivor is not None:
        # la collezione in memoria ricorda ancora gli alias appena cancellati
        await session.refresh(survivor)
        if not await delete_ingredient_if_unused(session, loser_id):
            raise RegistryRefusal(
                RefusalCode.STILL_USED,
                f"«{loser_name}» è ancora usato dopo l'unione: niente è stato salvato.",
            )
    for name in names:
        if canonical_name(name) != winner_name:
            await remember_alias(session, winner.id, name, source=MANUAL_ALIAS_SOURCE)
    await session.flush()

    materialized = await materialize_ready(session, GIALLOZAFFERANO)
    return MergeCounts(
        loser_name=loser_name,
        winner_name=winner_name,
        recipes_rebuilt=materialized.created,
        recipe_lines_moved=len(lines),
        pantry_items=pantry_items,
        shopping_items=shopping_items,
        products=products,
        aliases=await _alias_count(session, winner.id) - aliases_before,
        cooking_events_relinked=materialized.relinked,
    )


async def preview_merge(
    session: AsyncSession, loser_id: uuid.UUID, winner_id: uuid.UUID
) -> MergeCounts:
    """L'anteprima della fusione è la fusione stessa, dentro un SAVEPOINT annullato.

    Nessuna seconda funzione che stima: i numeri sono quelli dell'operazione, per
    costruzione (spec §5.1). Una stima scritta a parte sarebbe giusta finché i dati sono
    pochi — la lezione di `recipe_search.py` al contrario. Le ricette si rimaterializzano
    anche qui, embedding compresi: sono poche per fusione, ed è il prezzo della garanzia.

    Dopo il rollback del SAVEPOINT gli oggetti che la fusione ha toccato sono scaduti.
    Chi chiama non li rilegge di sfuggita (in una sessione async un attributo scaduto
    letto senza `await` è un MissingGreenlet): le rotte rispondono coi conteggi, che sono
    valori, e i test rileggono per id.

    Un `RegistryRefusal` con un `obstacle` (F12) fa eccezione a questa regola: il
    chiamante lo legge subito dopo — la rotta di Task 9 serializza `refusal.obstacle`
    nella risposta — e a quel punto il SAVEPOINT è già annullato. Se l'ostacolo è
    l'oggetto che la fusione ha modificato prima di rifiutare (il termine di
    DECISION_REFUSED, già passato per `undo_decision`), è fra quelli scaduti dal
    rollback. Per questo, prima di rilanciare, lo ricarichiamo con `session.refresh`:
    l'ostacolo torna leggibile con il suo valore precedente alla fusione, senza che chi
    chiama debba sapere di doverlo rileggere lui stesso. L'ostacolo non è sempre un
    oggetto mappato dall'ORM (`RecipesInUse` di `recategorize_ingredient` non lo è, per
    esempio, anche se qui dentro non compare mai): `inspect(obstacle, raiseerr=False)`
    distingue i due casi, così un ostacolo non-ORM non fa mai sollevare
    `UnmappedInstanceError` da `session.refresh` al posto del rifiuto vero.
    """
    savepoint = await session.begin_nested()
    try:
        counts = await merge_ingredients(session, loser_id, winner_id)
    except RegistryRefusal as refusal:
        await savepoint.rollback()
        if refusal.obstacle is not None and inspect(refusal.obstacle, raiseerr=False) is not None:
            await session.refresh(refusal.obstacle)
        raise
    except BaseException:
        await savepoint.rollback()
        raise
    await savepoint.rollback()
    return counts
