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
`payload` prima della cancellazione. Il costo, l'unico campo che si cambia senza
prendere in carico la ricetta (R9, R10). E le cotture: `cooking_events.recipe_id` è
ON DELETE SET NULL, quindi cancellare la ricetta scollegherebbe lo storico per sempre.
Fino a S9 questo file rifiutava con `CookedRecipesAffected` e chiedeva conferma; ora
scrive gli id delle cotture alla chiave `cooking_event_ids` (`COOKING_EVENTS_KEY`), e
`materialize_ready` li rimette sulla ricetta rifatta. Una pagina che resta in coda
tiene gli id finché non torna ricetta: la cottura è senza ricetta per quel tempo, e la
ritrova dopo.

Ripensato con R10, quando le ricette importate sono diventate modificabili. Una ricetta
che l'utente modifica o elimina non è più dell'import: la sua pagina passa ad `adopted`
nella stessa transazione, e qui si selezionano solo le pagine `imported`. Una pagina
`adopted` non si cancella e non torna in coda: rifarla dal `payload` cancellerebbe il
lavoro di chi l'ha corretta, ed è per questo che la presa in carico esiste. Le si conta
soltanto (`adopted_untouched`), perché la coda dica che l'annullamento non le ha
toccate; e se l'ingrediente che l'annullamento avrebbe cancellato (`created_ingredient`)
resta perché una ricetta presa in carico lo usa ancora — `delete_ingredient_if_unused` lo
lascia — lo si dice (`ingredient_kept_for_adopted`).
Le loro righe restano sull'ingrediente di prima: spostarle è una modifica della ricetta,
o una fusione in anagrafica, che le sposta in loco.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.recipe import CookingEvent, Recipe, RecipeIngredient
from app.db.models.recipe_import import ImportState, ImportTerm, RecipeImport, TermDecision
from app.domain.rules import cost_in_scale
from app.repositories.imports import pending_pages
from app.repositories.ingredients import delete_ingredient_if_unused, forget_alias
from app.services.recipe_import.materialize import COOKING_EVENTS_KEY
from app.services.recipe_import.terms import count_pending_keys


@dataclass(frozen=True)
class Undone:
    recipes_requeued: int
    ingredient_deleted: bool
    alias_forgotten: bool
    # le ricette prese in carico che contengono il termine: l'annullamento non le tocca,
    # e la coda lo dice (R10 §4)
    adopted_untouched: int
    # l'ingrediente del termine non è stato cancellato e una ricetta presa in carico lo
    # usa: resta per lei. Vero solo se l'annullamento l'avrebbe cancellato
    # (`created_ingredient`), non l'ha cancellato, e una ricetta presa in carico — una
    # qualunque, non solo fra quelle che contano in `adopted_untouched` — lo usa ancora.
    ingredient_kept_for_adopted: bool


async def _pages_with(
    session: AsyncSession, term: ImportTerm, state: ImportState
) -> list[RecipeImport]:
    """Le pagine in quello stato, con una ricetta, che contengono questo termine.

    Contenimento JSONB e non una scansione in Python: le pagine importate crescono con
    il ricettario, e caricarle tutte per leggerne una chiave sarebbe la stessa scelta
    che CLAUDE.md segnala su `recipe_search.py` — un limite scritto quando i dati erano
    pochi. Nessun indice nuovo (la feature non aggiunge migrazioni): resta una
    scansione, ma dentro il database e senza materializzare le righe, su
    un'operazione che si fa a mano e di rado.

    `recipe_id IS NOT NULL` distingue una pagina da rifare da una la cui ricetta
    l'utente ha cancellato: quella resta `imported`, perché è lo stato e non la
    presenza della chiave a dire «già importata una volta» (modello `RecipeImport`).

    `imported` sono quelle da rifare; `adopted` quelle prese in carico (R10), che non si
    toccano e si contano soltanto.
    """
    rows = await session.execute(
        select(RecipeImport).where(
            RecipeImport.source == term.source,
            RecipeImport.state == state,
            RecipeImport.recipe_id.is_not(None),
            RecipeImport.payload["ingredients"].op("@>")(
                func.jsonb_build_array(func.jsonb_build_object("key", term.term_key))
            ),
        )
    )
    return list(rows.scalars())


async def _hand_over_creation(session: AsyncSession, ingredient_id: uuid.UUID) -> None:
    """Il termine che possedeva la cancellazione è stato annullato e l'ingrediente è
    rimasto, perché qualcosa lo usa ancora. Se fra quelle cose c'è un altro termine
    deciso su di lui, il primo deciso riceve `created_ingredient = True`: da qui in poi è
    annullando lui che l'ingrediente si cancella, se niente altro lo usa. Senza, annullati
    anche quelli (tutti `False`) l'ingrediente resterebbe orfano in anagrafica.

    Il passaggio avviene quando un termine lo indica, qualunque altra cosa lo usi insieme
    (dispensa, lista, una ricetta): quelle lo tengono in vita al prossimo annullamento
    come a questo. Se nessun termine lo indica, nessuno lo riceve e l'ingrediente resta
    come uno scritto a mano. L'erede non l'ha creato: il `True` passato vuol dire «tocca a
    te toglierlo», e i testi della coda sono scritti per essere veri in tutti e due i casi
    («creato dall'import»).
    """
    heir = (
        await session.execute(
            select(ImportTerm)
            .where(
                ImportTerm.ingredient_id == ingredient_id,
                ImportTerm.decision == TermDecision.MAPPED,
            )
            .order_by(ImportTerm.decided_at.asc().nullslast(), ImportTerm.id)
            .limit(1)
        )
    ).scalars().first()
    if heir is not None:
        heir.created_ingredient = True


async def undo_decision(session: AsyncSession, term: ImportTerm) -> Undone:
    """Rimette il mondo come era prima che quella decisione fosse presa.

    Quattro effetti, in quest'ordine: le pagine e le ricette, il termine (col suo
    `occurrences` ricontato), l'alias, l'ingrediente (solo se il termine ne possiede la
    cancellazione, `created_ingredient`). Nessuno rifiuta: le ricette già cucinate si
    rifanno come le altre, perché le loro cotture aspettano nel `payload` (vedi la
    docstring del modulo).
    """
    pages = await _pages_with(session, term, ImportState.IMPORTED)
    adopted = await _pages_with(session, term, ImportState.ADOPTED)

    # le ricette si rifanno da payload: cancellarle è il modo corretto, non una
    # scorciatoia
    requeued = 0
    for page in pages:
        recipe = await session.get(Recipe, page.recipe_id)
        if recipe is not None:
            payload = dict(page.payload)
            # Il costo si sceglie anche dal dettaglio (R9), ed è l'unica modifica che non
            # prende in carico la ricetta (R10): rifacendola da `payload` si perderebbe.
            # Scritto nel `payload`, `materialize_ready` lo rilegge da lì.
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
    created_ingredient = term.created_ingredient
    alias_forgotten = False
    ingredient_deleted = False

    # il termine si libera prima di provare a cancellare l'ingrediente: finché lo
    # indica, `delete_ingredient_if_unused` lo conta come un uso e rifiuta sempre
    term.decision = TermDecision.PENDING
    term.ingredient_id = None
    term.role_override = None
    term.decided_by = None
    term.decided_at = None
    term.created_ingredient = None
    await session.flush()

    # `occurrences` si ricalcolava solo a ogni scarico (`sync_terms`): le pagine appena
    # rimesse in coda restavano fuori dal conto, e la coda diceva «1 ricetta in attesa»
    # sopra due titoli (T3, esito del giro). Si riconta il termine annullato, e solo
    # lui, con la funzione di `sync_terms`, dopo il `flush` che ha scritto le pagine
    # tornate `pending`. Gli altri termini di quelle pagine si riallineano al prossimo
    # scarico, come prima.
    counted = count_pending_keys(await pending_pages(session, term.source))
    term.occurrences = counted.occurrences.get(term.term_key, 0)

    if ingredient_id is not None:
        alias_forgotten = await forget_alias(session, ingredient_id, term.display_name)
        # Solo un ingrediente di cui questo termine possiede la cancellazione (l'ha
        # creato, o l'ha ereditato dal creatore annullato), e che niente altro usa. Uno
        # agganciato («Rigatoni» → «pasta», che c'era da prima) resta; e resta anche su
        # NULL, le decisioni prese prima che il fatto si scrivesse: `mapped` da solo non
        # distingue le due storie, e nel dubbio non si cancella.
        if created_ingredient is True:
            ingredient_deleted = await delete_ingredient_if_unused(session, ingredient_id)
            if not ingredient_deleted:
                await _hand_over_creation(session, ingredient_id)

    # Spec §4: l'annullamento avrebbe cancellato l'ingrediente, non l'ha fatto, e lo tiene
    # una ricetta tua. `created_ingredient` è la variabile letta sopra, prima che il termine
    # si azzerasse. «Tua» è la ricetta di una pagina `adopted` qualunque, non solo di quelle
    # che contengono questo termine (che `adopted_untouched` conta): dopo un passaggio
    # (`_hand_over_creation`) l'erede può non comparire in nessuna pagina tua, mentre la
    # ricetta tua che tiene l'ingrediente contiene il termine del creatore. Una ricetta
    # scritta a mano che lo usa lo tiene in vita anche lei, ma quello non è R10 e la coda
    # non lo dice.
    kept_for_adopted = False
    if created_ingredient is True and ingredient_id is not None and not ingredient_deleted:
        kept_for_adopted = (
            await session.scalar(
                select(RecipeIngredient.id)
                .join(RecipeImport, RecipeImport.recipe_id == RecipeIngredient.recipe_id)
                .where(
                    RecipeIngredient.ingredient_id == ingredient_id,
                    RecipeImport.state == ImportState.ADOPTED,
                )
                .limit(1)
            )
        ) is not None

    await session.flush()
    return Undone(
        recipes_requeued=requeued,
        ingredient_deleted=ingredient_deleted,
        alias_forgotten=alias_forgotten,
        adopted_untouched=len(adopted),
        ingredient_kept_for_adopted=kept_for_adopted,
    )
