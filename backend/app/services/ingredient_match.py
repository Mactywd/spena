"""Nome grezzo → ingrediente dell'anagrafica, con quanto ci si fida.

Unica implementazione nell'applicazione. La usano la stesura AI, per agganciare gli
ingredienti che Claude propone, e l'import, per decidere da sé i termini che
coincidono con qualcosa che già conosciamo. Due copie di questa regola si
scollerebbero, e la prima a scollarsi sarebbe la definizione di «certo»: da lì
passa la differenza fra un aggancio applicato in silenzio e uno che chiede
conferma.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient, IngredientAlias
from app.repositories.ingredients import search_ingredients


@dataclass(frozen=True)
class NameMatch:
    ingredient_id: uuid.UUID | None
    name: str | None
    certain: bool


async def match_name(session: AsyncSession, raw_name: str) -> NameMatch:
    """La certezza richiede una coincidenza esatta, col nome canonico o con un alias.

    L'uguaglianza non è una proposta, è un fatto, e non ha bisogno di conferma.
    Tutto il resto si propone e si marca incerto, perché un ingrediente sbagliato
    in silenzio avvelena la disponibilità di tutte le ricette che lo usano.
    """
    normalized = raw_name.strip().lower()
    if not normalized:
        return NameMatch(None, None, False)

    # Prima la coincidenza esatta sul nome canonico, in una query sua e non in un
    # OR con gli alias: se l'anagrafica arrivasse mai ad avere un ingrediente il
    # cui nome coincide con l'alias di un altro — il duplicato controlla solo
    # `ingredients.name`, non gli alias esistenti, quindi è raggiungibile — l'OR
    # con `.limit(1)` e senza `ORDER BY` lascerebbe Postgres scegliere a caso fra i
    # due, marcando «certo» un aggancio arbitrario che `sync_terms` applica da
    # solo, senza nessuno che lo rilegga.
    canonical = (
        await session.execute(select(Ingredient).where(Ingredient.name == normalized).limit(1))
    ).scalar_one_or_none()
    if canonical is not None:
        return NameMatch(canonical.id, canonical.name, True)

    # Poi l'alias, solo se il nome canonico non ha già deciso. Stesso principio:
    # niente ambiguità silenziosa, un ordine esplicito anche qui.
    via_alias = (
        await session.execute(
            select(Ingredient)
            .join(IngredientAlias, IngredientAlias.ingredient_id == Ingredient.id)
            .where(IngredientAlias.alias == normalized)
            .order_by(Ingredient.id)
            .limit(1)
        )
    ).scalar_one_or_none()
    if via_alias is not None:
        return NameMatch(via_alias.id, via_alias.name, True)

    candidates = await search_ingredients(session, raw_name, limit=1)
    if not candidates:
        return NameMatch(None, None, False)
    best = candidates[0]
    return NameMatch(best.id, best.name, False)
