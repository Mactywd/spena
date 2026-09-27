"""Disfare una decisione: il termine, l'alias, l'ingrediente, le pagine.

Un verbo solo, e non un editor delle decisioni. Dopo l'annullamento il termine è
esattamente dov'era prima che l'AI lo toccasse, e si decide a mano con la scheda che
esiste già ed è già testata: niente secondo percorso di decisione da scrivere e
mantenere.

Le ricette non si correggono, si rifanno. `recipe_imports.payload` è ancora nel
database esattamente per questo (spec madre §6.1), quindi rimettere la pagina a
`pending` e lasciare che `materialize_ready` la ricostruisca è più corretto di
qualunque chirurgia su `recipe_ingredients` — e non può sbagliare a metà.

Nelle ricette cancellate ci sono due cose da preservare, e passano entrambe nel
`payload` prima della cancellazione. Il costo, l'unico campo che l'applicazione lascia
modificare a mano (R9). E le cotture: `cooking_events.recipe_id` è ON DELETE SET NULL,
quindi cancellare la ricetta scollegherebbe lo storico per sempre. Fino a S9 questo
file rifiutava con `CookedRecipesAffected` e chiedeva conferma; ora scrive gli id delle
cotture alla chiave `cooking_event_ids` (`COOKING_EVENTS_KEY`), e `materialize_ready`
li rimette sulla ricetta rifatta. Una pagina che resta in coda tiene gli id finché non
torna ricetta: la cottura è senza ricetta per quel tempo, e la ritrova dopo. Il giorno
in cui una ricetta importata potrà essere modificata in altro (R10), questo file va
ripensato.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.recipe import CookingEvent, Recipe
from app.db.models.recipe_import import ImportState, ImportTerm, RecipeImport, TermDecision
from app.domain.rules import cost_in_scale
from app.repositories.ingredients import delete_ingredient_if_unused, forget_alias
from app.services.recipe_import.materialize import COOKING_EVENTS_KEY


@dataclass(frozen=True)
class Undone:
    recipes_requeued: int
    ingredient_deleted: bool
    alias_forgotten: bool


async def _imported_pages_with(
    session: AsyncSession, term: ImportTerm
) -> list[RecipeImport]:
    """Le pagine già materializzate che contengono questo termine.

    Contenimento JSONB e non una scansione in Python: le pagine importate crescono con
    il ricettario, e caricarle tutte per leggerne una chiave sarebbe la stessa scelta
    che CLAUDE.md segnala su `recipe_search.py` — un limite scritto quando i dati erano
    pochi. Nessun indice nuovo (la feature non aggiunge migrazioni): resta una
    scansione, ma dentro il database e senza materializzare le righe, su
    un'operazione che si fa a mano e di rado.

    `recipe_id IS NOT NULL` distingue una pagina da rifare da una la cui ricetta
    l'utente ha cancellato: quella resta `imported`, perché è lo stato e non la
    presenza della chiave a dire «già importata una volta» (modello `RecipeImport`).
    """
    rows = await session.execute(
        select(RecipeImport).where(
            RecipeImport.source == term.source,
            RecipeImport.state == ImportState.IMPORTED,
            RecipeImport.recipe_id.is_not(None),
            RecipeImport.payload["ingredients"].op("@>")(
                func.jsonb_build_array(func.jsonb_build_object("key", term.term_key))
            ),
        )
    )
    return list(rows.scalars())


async def undo_decision(session: AsyncSession, term: ImportTerm) -> Undone:
    """Rimette il mondo come era prima che quella decisione fosse presa.

    Quattro effetti, in quest'ordine: le pagine e le ricette, l'alias, l'ingrediente, il
    termine. Nessuno rifiuta: le ricette già cucinate si rifanno come le altre, perché
    le loro cotture aspettano nel `payload` (vedi la docstring del modulo).
    """
    pages = await _imported_pages_with(session, term)

    # le ricette si rifanno da payload: cancellarle è il modo corretto, non una
    # scorciatoia
    requeued = 0
    for page in pages:
        recipe = await session.get(Recipe, page.recipe_id)
        if recipe is not None:
            payload = dict(page.payload)
            # Il costo si sceglie anche a mano dal dettaglio (R9): è l'unica modifica
            # che una ricetta importata può ricevere, e rifacendola da `payload` si
            # perderebbe. Scritto nel `payload`, `materialize_ready` lo rilegge da lì.
            if recipe.cost != cost_in_scale(payload.get("cost")):
                payload["cost"] = recipe.cost
            cooked = [
                str(event_id)
                for event_id in (
                    await session.execute(
                        select(CookingEvent.id).where(CookingEvent.recipe_id == recipe.id)
                    )
                ).scalars()
            ]
            if cooked:
                payload[COOKING_EVENTS_KEY] = sorted(
                    {*payload.get(COOKING_EVENTS_KEY, []), *cooked}
                )
            # Riassegnato e non mutato: SQLAlchemy non vede le mutazioni in un JSONB.
            if payload != page.payload:
                page.payload = payload
            await session.delete(recipe)
        page.state = ImportState.PENDING
        page.recipe_id = None
        requeued += 1

    ingredient_id: uuid.UUID | None = term.ingredient_id
    alias_forgotten = False
    ingredient_deleted = False

    # il termine si libera prima di provare a cancellare l'ingrediente: finché lo
    # indica, `delete_ingredient_if_unused` lo conta come un uso e rifiuta sempre
    term.decision = TermDecision.PENDING
    term.ingredient_id = None
    term.role_override = None
    term.decided_by = None
    term.decided_at = None
    await session.flush()

    if ingredient_id is not None:
        alias_forgotten = await forget_alias(session, ingredient_id, term.display_name)
        ingredient_deleted = await delete_ingredient_if_unused(session, ingredient_id)

    await session.flush()
    return Undone(
        recipes_requeued=requeued,
        ingredient_deleted=ingredient_deleted,
        alias_forgotten=alias_forgotten,
    )
