"""Il dizionario dal catalogo della fonte al nostro.

Il catalogo di un sito di cucina è più fine di un'anagrafica fatta per rispondere
«ce l'ho in casa?»: dove noi abbiamo `pasta`, loro hanno `Rigatoni`. Colmare quella
distanza è l'unica parte dell'import che non si automatizza, perché colmarla male
avvelena la disponibilità di tutte le ricette che usano quell'ingrediente.

Quel che si automatizza è l'uguaglianza: un termine che coincide con un nostro nome
canonico o con un alias già scritto si decide da sé. Non è una proposta, è un fatto —
tranne quando quel fatto punterebbe a una voce non alimentare, che `create_recipe`
rifiuterebbe più tardi: lì resta comunque `PENDING`, per la coda umana.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, RecipeImport, TermDecision
from app.domain.rules import IngredientKind
from app.repositories.imports import pending_pages, terms_by_key
from app.services.ingredient_match import match_name


@dataclass(frozen=True)
class TermsSynced:
    created: int
    auto_decided: int
    pending: int


@dataclass(frozen=True)
class PendingKeys:
    """Quel che le pagine in attesa dicono dei loro termini."""

    # le ricette in attesa per chiave: una ricetta conta una volta, anche se nomina il
    # termine in due righe
    occurrences: dict[str, int]
    # il primo nome letto per ogni chiave, già tagliato alla colonna
    display_names: dict[str, str]


def count_pending_keys(pages: Iterable[RecipeImport]) -> PendingKeys:
    """`occurrences` conta le **ricette** in attesa che usano il termine, non le righe:
    la frolla e la crema vogliono entrambe lo zucchero a velo, ma la ricetta bloccata è
    una. Una funzione sola per `sync_terms` e per `undo_decision`: due conteggi scritti
    due volte divergono, e la coda direbbe numeri diversi a seconda di chi l'ha
    toccata per ultimo.
    """
    occurrences: dict[str, int] = {}
    display_names: dict[str, str] = {}
    for page in pages:
        keys_here = set()
        for line in page.payload.get("ingredients") or []:
            key = line.get("key")
            if not key:
                continue
            keys_here.add(key)
            display_names.setdefault(key, str(line.get("name") or key)[:200])
        for key in keys_here:
            occurrences[key] = occurrences.get(key, 0) + 1
    return PendingKeys(occurrences=occurrences, display_names=display_names)


async def sync_terms(session: AsyncSession, source: str = GIALLOZAFFERANO) -> TermsSynced:
    """Allinea il dizionario alle pagine in attesa.

    `occurrences` (vedi `count_pending_keys`) si ricalcola a ogni passaggio e non si
    incrementa mai: un contatore incrementato divergerebbe al primo ri-scarico, e un
    ordinamento della coda basato su un numero sbagliato è un difetto che nessuno nota.
    L'altro posto che lo ricalcola è `undo_decision`, per il termine annullato.
    """
    counted = count_pending_keys(await pending_pages(session, source))
    occurrences = counted.occurrences
    display_names = counted.display_names

    existing = await terms_by_key(session, source)

    created = 0
    auto_decided = 0
    for key, count in occurrences.items():
        term = existing.get(key)
        if term is None:
            term = ImportTerm(
                source=source, term_key=key, display_name=display_names[key],
                occurrences=count, decision=TermDecision.PENDING,
            )
            session.add(term)
            existing[key] = term
            created += 1
            match = await match_name(session, term.display_name)
            # Certo non basta: una coincidenza esatta su una voce non alimentare
            # (`carta da forno` è alias di `casa` nel seme) non deve decidersi da
            # sé, perché `create_recipe` la rifiuterebbe più tardi — a
            # materializzazione già avviata, con la ricetta intera persa e nessuna
            # coda a raccoglierla, dato che «auto» decide solo alla creazione del
            # termine e non torna mai più a rivederlo. Resta `PENDING`: la coda
            # umana ha già le sue guardie a 422 e l'uscita «ignora il termine».
            if match.certain and match.kind != IngredientKind.NON_FOOD:
                term.decision = TermDecision.MAPPED
                term.ingredient_id = match.ingredient_id
                term.created_ingredient = False
                term.decided_by = "auto"
                term.decided_at = datetime.now(UTC)
                auto_decided += 1
        else:
            term.occurrences = count

    # un termine che non compare più in nessuna pagina in attesa non ha più ricette
    # da sbloccare: il suo conteggio va a zero, non resta al valore di ieri
    for key, term in existing.items():
        if key not in occurrences:
            term.occurrences = 0

    await session.flush()
    pending = sum(
        1 for term in existing.values() if term.decision == TermDecision.PENDING
    )
    return TermsSynced(created=created, auto_decided=auto_decided, pending=pending)
