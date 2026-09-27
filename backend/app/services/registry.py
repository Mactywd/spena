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

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.recipe import Recipe, RecipeIngredient
from app.db.models.recipe_import import ImportTerm
from app.domain.rules import IngredientKind, kind_for_category
from app.repositories.ingredients import canonical_name, find_by_name, remember_alias

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
