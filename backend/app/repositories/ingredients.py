import uuid

from sqlalchemy import case, func, select
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
