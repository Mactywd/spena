import uuid

from sqlalchemy import case, delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient, IngredientAlias
from app.db.models.shopping import ShoppingListItem

SIMILARITY_FLOOR = 0.15  # sotto questa soglia i suggerimenti diventano rumore


async def search_ingredients(
    session: AsyncSession, query: str, limit: int = 10
) -> list[Ingredient]:
    """Autocomplete su nome e alias, tollerante agli errori di battitura.

    Il punteggio combina la somiglianza trigram con quanto spesso l'ingrediente
    è finito in lista: a pari somiglianza vince ciò che compri davvero.
    Il prefisso esatto ha la precedenza, perché chi sta digitando si aspetta
    quello.

    Su query di una o due lettere la trigram similarity non porta informazione
    (`similarity('prezzemolo', 'p')` e `similarity('pomodoro', 'p')` sono
    entrambe sotto SIMILARITY_FLOOR e comunque troppo vicine per distinguere),
    quindi un match di prefisso scavalca la soglia di somiglianza invece di
    esserne escluso.
    """
    cleaned = query.strip().lower()
    if not cleaned:
        return []

    purchases = (
        select(ShoppingListItem.ingredient_id, func.count().label("uses"))
        .where(ShoppingListItem.ingredient_id.is_not(None))
        .group_by(ShoppingListItem.ingredient_id)
        .subquery()
    )

    name_similarity = func.similarity(Ingredient.name, cleaned)
    alias_similarity = func.coalesce(func.max(func.similarity(IngredientAlias.alias, cleaned)), 0.0)
    best_similarity = func.greatest(name_similarity, alias_similarity)

    name_is_prefix = Ingredient.name.like(f"{cleaned}%")
    alias_is_prefix = func.bool_or(IngredientAlias.alias.like(f"{cleaned}%"))
    is_prefix_match = name_is_prefix | func.coalesce(alias_is_prefix, False)

    purchase_count = func.coalesce(func.max(purchases.c.uses), 0)

    statement = (
        select(Ingredient)
        .outerjoin(IngredientAlias, IngredientAlias.ingredient_id == Ingredient.id)
        .outerjoin(purchases, purchases.c.ingredient_id == Ingredient.id)
        .group_by(Ingredient.id)
        # Il prefisso esatto scavalca la soglia di somiglianza: su query di una o
        # due lettere la trigram similarity non è uno strumento utile (vedi
        # docstring), quindi non deve poter escludere un prefisso valido.
        .having((best_similarity >= SIMILARITY_FLOOR) | is_prefix_match)
        .order_by(
            # 1) i match di prefisso vengono sempre prima dei match sfumati.
            is_prefix_match.desc(),
            # 2) tra i prefissi, conta solo quanto lo compri: su una lettera la
            #    somiglianza non distingue nulla (vedi docstring), la frequenza sì.
            case((is_prefix_match, purchase_count), else_=0).desc(),
            # 3) tra i match sfumati, vince la somiglianza; la frequenza fa solo
            #    da spareggio, non deve mai scavalcare un match migliore.
            best_similarity.desc(),
            purchase_count.desc(),
            # 4) spareggio finale, deterministico.
            Ingredient.name.asc(),
        )
        .limit(limit)
    )
    result = await session.execute(statement)
    return list(result.scalars().unique())


async def create_ingredient(
    session: AsyncSession, name: str, display_name: str, category: str
) -> Ingredient:
    ingredient = Ingredient(name=name.strip().lower(), display_name=display_name.strip(),
                            category=category)
    session.add(ingredient)
    await session.flush()
    return ingredient


async def add_alias(
    session: AsyncSession, ingredient_id: uuid.UUID, alias: str, source: str
) -> IngredientAlias:
    entry = IngredientAlias(ingredient_id=ingredient_id, alias=alias.strip().lower(), source=source)
    session.add(entry)
    await session.flush()
    return entry


async def remember_alias(
    session: AsyncSession, ingredient_id: uuid.UUID, display_name: str
) -> bool:
    """L'alias è ciò che fa valere una decisione per sempre, e anche fuori dall'import.

    Si scrive solo se quell'alias non esiste già per nessun ingrediente: il vincolo del
    database è su `(ingredient_id, alias)` e lascerebbe passare lo stesso alias su due
    ingredienti diversi, cioè un autocomplete che dà due risposte a una domanda sola.
    Il legame fra termine e ingrediente vive su `import_terms`, quindi saltarlo non
    perde la decisione.

    Torna `True` se l'ha scritto. Unica implementazione: la usano la decisione umana
    (api/imports.py), quella dell'AI (services/recipe_import/decide.py) e il collasso.
    Due copie di questa regola si scollerebbero, e la prima cosa a scollarsi sarebbe
    il vincolo su cui poggia l'autocomplete.
    """
    cleaned = display_name.strip().lower()
    if not cleaned:
        return False
    already = (
        await session.execute(select(IngredientAlias).where(IngredientAlias.alias == cleaned))
    ).scalars().first()
    if already is not None:
        return False
    await add_alias(session, ingredient_id, cleaned, source="import")
    return True


async def forget_alias(
    session: AsyncSession, ingredient_id: uuid.UUID, display_name: str
) -> bool:
    """L'inversa di `remember_alias`, e prudente per la stessa ragione.

    Cancella solo un alias scritto dall'import (`source="import"`) e solo su quel
    preciso ingrediente: annullare una decisione dell'AI non deve poter smontare
    l'anagrafica del seme, dove gli alias arrivano da `source="seed"` e valgono a
    prescindere da qualunque import.
    """
    cleaned = display_name.strip().lower()
    if not cleaned:
        return False
    entry = (
        await session.execute(
            select(IngredientAlias).where(
                IngredientAlias.ingredient_id == ingredient_id,
                IngredientAlias.alias == cleaned,
                IngredientAlias.source == "import",
            )
        )
    ).scalars().first()
    if entry is None:
        return False
    await session.delete(entry)
    await session.flush()
    return True


async def delete_ingredient_if_unused(
    session: AsyncSession, ingredient_id: uuid.UUID
) -> bool:
    """Cancella un ingrediente solo se nessuno lo usa più. Torna `True` se l'ha fatto.

    «Usarlo» significa: una riga di ricetta, un articolo in dispensa, una voce di
    lista, un termine dell'import che lo indica, o un prodotto che lo porta come
    referenza — un barattolo può restare sullo scaffale della dispensa (mai
    cancellato, solo archiviato) molto dopo che l'ultimo articolo che lo citava è
    sparito, e a quel punto è il prodotto solo a tenere in piedi il vincolo. I suoi
    **alias** non contano: sono parte della decisione che lo ha creato, non un uso
    indipendente, e se contassero nessun ingrediente creato dall'AI sarebbe mai
    cancellabile — ogni decisione ne scrive uno.

    È questo controllo che rende gratuito l'annullamento di un collasso: se «salmone
    selvaggio» era stato accorpato in «salmone», annullare «Salmone» trova l'altro
    termine e non cancella niente.
    """
    from app.db.models.pantry import PantryItem
    from app.db.models.product import Product
    from app.db.models.recipe import RecipeIngredient
    from app.db.models.recipe_import import ImportTerm

    for model, column in (
        (RecipeIngredient, RecipeIngredient.ingredient_id),
        (PantryItem, PantryItem.ingredient_id),
        (ShoppingListItem, ShoppingListItem.ingredient_id),
        (ImportTerm, ImportTerm.ingredient_id),
        (Product, Product.ingredient_id),
    ):
        used = (
            await session.execute(select(model.id).where(column == ingredient_id).limit(1))
        ).scalars().first()
        if used is not None:
            return False

    ingredient = await session.get(Ingredient, ingredient_id)
    if ingredient is None:
        return False
    await session.execute(
        delete(IngredientAlias).where(IngredientAlias.ingredient_id == ingredient_id)
    )
    await session.delete(ingredient)
    await session.flush()
    return True
