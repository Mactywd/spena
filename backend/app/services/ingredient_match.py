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

    # prima la coincidenza esatta, che non dipende dalla somiglianza trigram e non
    # può essere scavalcata da un candidato più "frequente"
    exact = (
        await session.execute(
            select(Ingredient)
            .outerjoin(IngredientAlias, IngredientAlias.ingredient_id == Ingredient.id)
            .where((Ingredient.name == normalized) | (IngredientAlias.alias == normalized))
            .limit(1)
        )
    ).unique().scalar_one_or_none()
    if exact is not None:
        return NameMatch(exact.id, exact.name, True)

    candidates = await search_ingredients(session, raw_name, limit=1)
    if not candidates:
        return NameMatch(None, None, False)
    best = candidates[0]
    return NameMatch(best.id, best.name, False)
