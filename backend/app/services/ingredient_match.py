"""Nome grezzo → ingrediente dell'anagrafica, con quanto ci si fida.

Unica implementazione nell'applicazione. La usano la stesura AI, per agganciare gli
ingredienti che Claude propone, e l'import, per decidere da sé i termini che
coincidono con qualcosa che già conosciamo; la lista della spesa ne usa la sola
metà esatta, `exact_ingredient`. Due copie di questa regola si
scollerebbero, e la prima a scollarsi sarebbe la definizione di «certo»: da lì
passa la differenza fra un aggancio applicato in silenzio e uno che chiede
conferma.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient, IngredientAlias
from app.domain.rules import IngredientKind
from app.repositories.ingredients import search_ingredients


@dataclass(frozen=True)
class NameMatch:
    ingredient_id: uuid.UUID | None
    name: str | None
    certain: bool
    kind: IngredientKind | None = None


def _normalize(raw_name: str) -> str:
    """La stessa forma in cui `create_ingredient` e `add_alias` scrivono nomi e alias."""
    return raw_name.strip().lower()


async def _by_canonical_name(session: AsyncSession, normalized: str) -> Ingredient | None:
    # `ingredients.name` è unico: al più una riga, e nessun ordine da decidere
    return (
        await session.execute(select(Ingredient).where(Ingredient.name == normalized))
    ).scalar_one_or_none()


async def exact_ingredient(session: AsyncSession, raw_name: str) -> Ingredient | None:
    """Solo la coincidenza esatta, e solo se indica un ingrediente e uno soltanto.

    È la metà certa di `match_name`, per chi aggancia senza chiedere e non vuole
    mai una proposta: la lista della spesa (S18). Stessa precedenza — il nome
    canonico decide per primo — con una differenza voluta sugli alias: l'unicità
    lì è per coppia (ingrediente, alias), quindi lo stesso alias può stare su due
    ingredienti, e dove `match_name` ne prende uno in un ordine fisso questa
    funzione non sceglie. Una voce di lista lasciata libera si abbina dopo con un
    tocco; una agganciata all'ingrediente sbagliato non lo dice a nessuno.
    """
    normalized = _normalize(raw_name)
    if not normalized:
        return None
    canonical = await _by_canonical_name(session, normalized)
    if canonical is not None:
        return canonical
    via_alias = list(
        (
            await session.execute(
                select(Ingredient)
                .join(IngredientAlias, IngredientAlias.ingredient_id == Ingredient.id)
                .where(IngredientAlias.alias == normalized)
                # due bastano a sapere che non è uno solo; e due righe sono due
                # ingredienti, perché la coppia (ingrediente, alias) è unica
                .limit(2)
            )
        ).scalars()
    )
    return via_alias[0] if len(via_alias) == 1 else None


async def match_name(session: AsyncSession, raw_name: str) -> NameMatch:
    """La certezza richiede una coincidenza esatta, col nome canonico o con un alias.

    L'uguaglianza non è una proposta, è un fatto, e non ha bisogno di conferma.
    Tutto il resto si propone e si marca incerto, perché un ingrediente sbagliato
    in silenzio avvelena la disponibilità di tutte le ricette che lo usano.
    """
    normalized = _normalize(raw_name)
    if not normalized:
        return NameMatch(None, None, False)

    # Prima la coincidenza esatta sul nome canonico, in una query sua e non in un
    # OR con gli alias: se l'anagrafica arrivasse mai ad avere un ingrediente il
    # cui nome coincide con l'alias di un altro — il duplicato controlla solo
    # `ingredients.name`, non gli alias esistenti, quindi è raggiungibile — l'OR
    # con `.limit(1)` e senza `ORDER BY` lascerebbe Postgres scegliere a caso fra i
    # due, marcando «certo» un aggancio arbitrario che `sync_terms` applica da
    # solo, senza nessuno che lo rilegga.
    canonical = await _by_canonical_name(session, normalized)
    if canonical is not None:
        return NameMatch(canonical.id, canonical.name, True, IngredientKind(canonical.kind))

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
        return NameMatch(via_alias.id, via_alias.name, True, IngredientKind(via_alias.kind))

    candidates = await search_ingredients(session, raw_name, limit=1)
    if not candidates:
        return NameMatch(None, None, False)
    best = candidates[0]
    # `Ingredient.kind` è una `String(10)`, non un tipo enum: appena la riga arriva
    # da una sessione che la sta leggendo per la prima volta — il caso normale in
    # produzione — l'attributo è la stringa grezza di Postgres, non il membro che
    # `_deduce_kind` assegna in memoria alla costruzione. Convertire qui rende vera
    # l'annotazione di `NameMatch.kind` a prescindere da come l'oggetto è arrivato,
    # invece di lasciarla vera per caso quando l'ingrediente è ancora nella identity
    # map di chi lo ha creato.
    return NameMatch(best.id, best.name, False, IngredientKind(best.kind))
