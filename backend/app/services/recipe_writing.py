"""Scrivere le righe e il vettore di una ricetta: la strada del modulo, condivisa.

Stava in `app/api/recipes.py`; è qui perché Claude, scrivendo la ricetta di un pasto
(`app.services.meal_recipes`), usi **la stessa strada** del modulo e non una seconda copia
(spec 2026-11-12 §6.3). Spostato senza cambiare comportamento.
"""

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import IngredientLine
from app.schemas.recipe import RecipeIngredientIn
from app.services.embeddings import (
    EmbeddingUnavailable,
    get_embedding_provider,
    log_degradation_once,
    recipe_document,
)
from app.services.ingredient_match import ingredient_for_new_name


class RepeatedIngredient(Exception):
    """Due righe del modulo che, risolte, puntano allo stesso ingrediente."""

    def __init__(self, display_name: str) -> None:
        super().__init__(display_name)
        self.display_name = display_name


async def resolve_lines(
    session: AsyncSession, lines: list[RecipeIngredientIn]
) -> list[IngredientLine]:
    """Da righe del modulo a righe da scrivere: la stessa strada per creare e modificare.

    Le righe che nominano un ingrediente non ancora in anagrafica lo creano qui,
    dentro la stessa transazione della ricetta: se il salvataggio fallisce non resta
    nessun ingrediente orfano. In sequenza e non in parallelo, per lo stesso motivo del
    fan-in dell'import: due righe con lo stesso nome nuovo devono diventare un
    ingrediente, non un doppione.

    Due righe che puntano allo stesso ingrediente — lo stesso id due volte, un nome nuovo
    uguale a una riga agganciata, due nomi che `match_name` porta allo stesso — si
    rifiutano qui, nominandolo (`RepeatedIngredient`, 409 in `_writing_recipe`): il
    vincolo d'unicità della tabella delle righe le rifiuterebbe comunque, ma non sa dire
    quale ingrediente.
    """
    resolved: list[IngredientLine] = []
    seen: set[uuid.UUID] = set()
    for line in lines:
        ingredient_id = line.ingredient_id
        if ingredient_id is None:
            # `match_name` (dentro `ingredient_for_new_name`) e non una ricerca sul solo
            # nome canonico: se la bozza dice «pomodori» e l'anagrafica ha «pomodoro» con
            # quell'alias, collegarsi è giusto e creare sarebbe un duplicato travestito. La
            # stessa funzione la chiede in anticipo il passo del nome del modulo
            # (`GET /ingredients/match`): l'avviso sul non alimentare dice quel che qui succede
            linked = await ingredient_for_new_name(session, line.name or "")
            if linked is not None:
                ingredient_id = linked.id
            else:
                created = await create_ingredient(
                    session, name=line.name or "",
                    display_name=(line.name or "").capitalize(),
                    category=line.category or "altro",
                )
                ingredient_id = created.id
        if ingredient_id in seen:
            ingredient = await session.get(Ingredient, ingredient_id)
            # un id che non esiste due volte non è un doppione da nominare: lo
            # scopre la scrittura, col suo 404 «inesistente», come prima
            if ingredient is not None:
                raise RepeatedIngredient(ingredient.display_name)
        seen.add(ingredient_id)
        resolved.append((ingredient_id, line.role, line.quantity_text, line.note))
    return resolved


async def embedding_for(
    title: str, description: str | None, *, provider=None
) -> list[float] | None:
    """L'embedding è un ornamento: se il modello non c'è, la ricetta si salva comunque,
    con il vettore a `NULL`, e `app.cli.reindex` lo ritrova (riempie solo i `NULL`).

    `provider` lo passa la rotta delle ricette, che lo prende dal proprio modulo (i test
    lo sostituiscono lì); senza, lo si chiede qui."""
    try:
        chosen = provider if provider is not None else get_embedding_provider()
        return (await chosen.embed_passages([recipe_document(title, description)]))[0]
    except EmbeddingUnavailable as exc:
        log_degradation_once(exc)
        return None
