"""Il riconoscimento degli ingredienti sconosciuti, con un LLM che decide.

Quattro passi, e l'ordine di esecuzione non è quello in cui si leggono qui:

1. il filtro deterministico sta in `terms.py`, in `sync_terms`: un termine che
   coincide con un nostro nome o alias si decide da sé, senza chiamare nessuno. Solo
   ciò che resta `pending` arriva qui;
2. **fan-out** — `decide_one` per ogni termine, in parallelo, senza scrivere;
3. **collasso** — una chiamata sola sui soli `create`, senza scrivere;
4. **fan-in** — le scritture, in sequenza.

Una chiamata per termine e non un lotto unico: `gemma-4-26b-a4b-it` ha 3,8 miliardi
di parametri attivi per token, e un array JSON di 40 elementi ognuno dei quali deve
riecheggiare identica una delle 40 stringhe ricevute è dove un MoE piccolo si sfalda.
Il degrado sarebbe invisibile — gli elementi non riconosciuti si scartano in silenzio
— e costerebbe un ottavo. Vedi spec §4.2 e §12: il parallelo si paga in soldi e si
guadagna in accuratezza.
"""

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.ingredient import NAME_MAX_LENGTH, Ingredient, IngredientCategory
from app.db.models.recipe_import import ImportTerm, TermDecision
from app.services.llm import LlmUnavailable, build_headers, complete_json, open_client

logger = logging.getLogger(__name__)

TERM_MAX_TOKENS = 300  # una decisione sola: qui sopra c'è solo spazio per divagare

TERM_SYSTEM_PROMPT = """Sei un aiuto per mettere in ordine un'anagrafica di ingredienti. Ricevi UN nome di ingrediente preso da un sito di cucina, e l'anagrafica di un'app di dispensa. Scegli UNA delle tre azioni.

- "map": è lo stesso ingrediente di uno che esiste già in anagrafica, scritto più in dettaglio. "Rigatoni" è pasta, "Latte intero" è latte. Metti in "ingredient" il nome canonico esistente, scritto identico.
- "create": è un ingrediente generico che l'anagrafica non ha. Metti in "name" il nome canonico in italiano minuscolo e singolare, in "display_name" il nome da mostrare, in "category" una delle categorie che ti passo, scritta identica.
- "ignore": non è qualcosa che si tiene in dispensa. L'acqua, il ghiaccio, l'acqua per la cottura.

Regole:
- Preferisci "map" quando l'ingrediente esiste già: un'anagrafica con venti formati di pasta non sa più dire cosa c'è in casa.
- I campi che non servono all'azione scelta valgono null.
- Non inserire valori nutrizionali, calorie o macronutrienti.
"""

TERM_SCHEMA = {
    "type": "object",
    "properties": {
        "action": {"type": "string", "enum": ["map", "create", "ignore"]},
        "ingredient": {"type": ["string", "null"]},
        "name": {"type": ["string", "null"]},
        "display_name": {"type": ["string", "null"]},
        "category": {"type": ["string", "null"]},
    },
    # Vincolo dello strict mode: ogni proprietà in `required`, additionalProperties a
    # false. È il motivo per cui i campi di una sola azione sono nullable e non
    # opzionali — dichiararli opzionali farebbe rifiutare lo schema.
    "required": ["action", "ingredient", "name", "display_name", "category"],
    "additionalProperties": False,
}

CATEGORIES = frozenset(str(value) for value in IngredientCategory)


@dataclass(frozen=True)
class Registry:
    """L'anagrafica in una forma che sta in un prompt e si interroga senza database.

    Si carica una volta per lotto e non una per termine: con N chiamate in parallelo
    sarebbero N letture identiche della stessa tabella.
    """

    by_name: dict[str, uuid.UUID]
    name_by_id: dict[uuid.UUID, str]
    entries: list[tuple[str, str]]  # (nome, categoria), ordinati per nome


async def load_registry(session: AsyncSession) -> Registry:
    rows = list(
        (
            await session.execute(
                select(Ingredient.id, Ingredient.name, Ingredient.category).order_by(
                    Ingredient.name
                )
            )
        ).all()
    )
    return Registry(
        by_name={name: ingredient_id for ingredient_id, name, _ in rows},
        name_by_id={ingredient_id: name for ingredient_id, name, _ in rows},
        entries=[(name, category) for _, name, category in rows],
    )


@dataclass(frozen=True)
class TermDecisionProposal:
    term_id: uuid.UUID
    action: str
    ingredient_id: uuid.UUID | None = None
    name: str | None = None
    display_name: str | None = None
    category: str | None = None


def _question(term: ImportTerm, registry: Registry) -> str:
    return json.dumps(
        {
            "termine": term.display_name,
            "anagrafica": [{"nome": name, "categoria": category} for name, category in registry.entries],
            "categorie": sorted(CATEGORIES),
        },
        ensure_ascii=False,
    )


async def decide_one(
    session: AsyncSession,
    term: ImportTerm,
    registry: Registry,
    client: object | None = None,
) -> TermDecisionProposal | None:
    """Una decisione verificata per questo termine, o `None` se non è verificabile.

    `None` non è un guasto: è «il modello ha risposto qualcosa che non posso
    applicare», e il termine resta in coda. `LlmUnavailable` invece risale: chi
    orchestra deve poter distinguere «il modello è giù» da «il modello ha detto una
    cosa inutilizzabile», perché la prima si ritenta e la seconda no.

    `session` non serve oggi alla verifica — il registro basta — ed è nella firma
    perché il chiamante ce l'ha già e perché il collasso e l'applicazione la vogliono:
    una firma diversa per ognuno dei tre passi renderebbe il fan-out più difficile da
    leggere di quanto valga.
    """
    payload = await complete_json(
        system=TERM_SYSTEM_PROMPT,
        user=_question(term, registry),
        schema=TERM_SCHEMA,
        schema_name="decisione_termine",
        max_tokens=TERM_MAX_TOKENS,
        client=client,
    )

    action = payload.get("action")

    if action == "ignore":
        return TermDecisionProposal(term_id=term.id, action="ignore")

    if action == "map":
        name = str(payload.get("ingredient") or "").strip().lower()
        ingredient_id = registry.by_name.get(name)
        if ingredient_id is None:
            return None  # un ingrediente che non esiste non è una proposta
        return TermDecisionProposal(
            term_id=term.id, action="map", ingredient_id=ingredient_id,
            name=registry.name_by_id.get(ingredient_id),
        )

    if action == "create":
        name = str(payload.get("name") or "").strip().lower()
        category = str(payload.get("category") or "").strip().lower()
        if not name or category not in CATEGORIES:
            return None
        existing = registry.by_name.get(name)
        if existing is not None:
            # Un `create` di un nome che l'anagrafica ha già: il 409 lo rifiuterebbe a
            # ogni tentativo. Ma la carta verificata non è il `create` sbagliato, è il
            # `map` che il modello avrebbe dovuto scegliere — e id e nome canonico li
            # abbiamo già, dalla stessa ricerca che verifica un `map` vero.
            return TermDecisionProposal(
                term_id=term.id, action="map", ingredient_id=existing,
                name=registry.name_by_id.get(existing),
            )
        return TermDecisionProposal(
            term_id=term.id, action="create", name=name,
            display_name=str(payload.get("display_name") or name).strip(),
            category=category,
        )

    return None  # un'azione che non conosco


COLLAPSE_MAX_TOKENS = 800

COLLAPSE_SYSTEM_PROMPT = """Sei un aiuto per mettere in ordine un'anagrafica di ingredienti di un'app di dispensa, che serve a rispondere «ce l'ho in casa?».

Ricevi una lista di nomi di ingredienti che stanno per essere aggiunti, e per ognuno i nomi già presenti in anagrafica che gli assomigliano. Raggruppa i nomi che sono lo stesso ingrediente.

Per ogni gruppo:
- "canonical": il nome che sopravvive. Deve essere uno dei nomi che ti passo — fra quelli nuovi o fra quelli già in anagrafica. Non inventarne uno terzo.
- "merge": i nomi nuovi che diventano varianti di quel canonico. Solo nomi presenti nella lista che ti ho dato.

Regole:
- Raggruppa solo ciò che in cucina è la stessa cosa. "Salmone" e "Salmone selvaggio" sì. "Cipolla" e "Cipollotto" NO: sono ingredienti diversi.
- Nel dubbio non raggruppare: due ingredienti in più si correggono, una distinzione perduta no.
- Se non c'è niente da raggruppare, torna una lista vuota.
- Non inserire valori nutrizionali.
"""

COLLAPSE_SCHEMA = {
    "type": "object",
    "properties": {
        "groups": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "canonical": {"type": "string"},
                    "merge": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["canonical", "merge"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["groups"],
    "additionalProperties": False,
}

NEIGHBOURS_PER_NAME = 3


async def collapse_creates(
    session: AsyncSession,
    proposals: list[TermDecisionProposal],
    registry: Registry,
    client: object | None = None,
) -> list[TermDecisionProposal]:
    """Unisce i `create` che sono lo stesso ingrediente. Non scrive niente.

    Copre due rischi in una chiamata: nuovo contro nuovo (che nessuna delle chiamate
    parallele poteva vedere) e nuovo contro esistente (che `decide_one` avrebbe dovuto
    prendere, e che un modello con 3,8 miliardi di parametri attivi a volte non
    prende).

    I vicini si trovano con `search_ingredients`, la ricerca per trigrammi che è già
    la primitiva di somiglianza del progetto: al modello arriva un input minuscolo e
    non l'anagrafica intera.

    Zero chiamate quando non c'è niente da chiedere: nessun `create`, oppure un solo
    `create` la cui ricerca per trigrammi non trova nessun vicino — né fra i nuovi (non
    ce ne sono altri) né in anagrafica (nessuna riga simile). Un solo `create` con un
    vicino in anagrafica invece chiama comunque: è esattamente il caso «nuovo contro
    esistente» che `decide_one` avrebbe dovuto prendere e a volte non prende.

    Un guasto del modello non perde il lotto: si tornano le proposte come sono
    arrivate. Il collasso è una rifinitura, e far cadere N decisioni buone per una
    chiamata andata male sarebbe il contrario di quel che serve.
    """
    from app.repositories.ingredients import search_ingredients

    creates = [p for p in proposals if p.action == "create" and p.name]
    if not creates:
        return list(proposals)

    proposed = {p.name: p for p in creates if p.name}
    neighbours: dict[str, list[str]] = {}
    for name in proposed:
        found = await search_ingredients(session, name, limit=NEIGHBOURS_PER_NAME)
        neighbours[name] = [ingredient.name for ingredient in found]

    if len(proposed) < 2 and not any(neighbours.values()):
        return list(proposals)  # niente con cui collassare, né fra i nuovi né in anagrafica

    question = json.dumps(
        {
            "nuovi": [
                {"nome": name, "simili_in_anagrafica": neighbours[name]} for name in proposed
            ]
        },
        ensure_ascii=False,
    )

    try:
        payload = await complete_json(
            system=COLLAPSE_SYSTEM_PROMPT,
            user=question,
            schema=COLLAPSE_SCHEMA,
            schema_name="collasso_ingredienti",
            max_tokens=COLLAPSE_MAX_TOKENS,
            client=client,
        )
    except LlmUnavailable:
        return list(proposals)

    groups = payload.get("groups")
    if not isinstance(groups, list):
        return list(proposals)

    # Chiave per `term_id`, non per nome: due termini distinti possono proporre lo
    # stesso `create` («Salmone selvaggio» e «Filetto di salmone selvaggio» riducono
    # entrambi a `name="salmone selvaggio"`). Con una chiave per nome, se quel nome
    # perde in un gruppo, entrambe le proposte verrebbero sostituite dallo stesso
    # oggetto: uno dei due `term_id` sparirebbe dal risultato e l'altro comparirebbe
    # due volte, facendo applicare — e contare — la stessa decisione due volte al
    # passo che scrive.
    merged: dict[uuid.UUID, TermDecisionProposal] = {}
    for group in groups:
        if not isinstance(group, dict):
            continue
        canonical = str(group.get("canonical") or "").strip().lower()
        names = group.get("merge")
        if not canonical or not isinstance(names, list):
            continue

        # il canonico deve essere qualcosa che esiste o che stiamo creando: un terzo
        # nome inventato fa scartare il gruppo, e i nomi restano separati
        existing_id = registry.by_name.get(canonical)
        if canonical not in proposed and existing_id is None:
            continue

        winner = proposed.get(canonical)
        for raw in names:
            name = str(raw or "").strip().lower()
            if name == canonical or name not in proposed:
                continue  # un nome che nessuno ha proposto non si accorpa
            # Il gruppo del modello parla di nomi, non di `term_id`: `proposed[name]`
            # ne indicherebbe uno solo, ma più termini possono aver proposto lo stesso
            # `create` (sopra). Il merge va scritto per ciascuno di essi, non per uno
            # a caso — altrimenti il secondo resterebbe un `create` con un nome che il
            # collasso ha appena deciso di non tenere.
            for losing in (p for p in creates if p.name == name):
                merged[losing.term_id] = TermDecisionProposal(
                    term_id=losing.term_id,
                    action="merge",
                    ingredient_id=existing_id,  # None quando il canonico è un `create` del lotto
                    name=canonical,
                    # Nome visibile e categoria sono quelli del **vincitore**, non del nome
                    # che perde. Quando il canonico è un `create` dello stesso lotto, il
                    # fan-in può trovarsi a creare l'ingrediente partendo da questa
                    # proposta — dipende da quale delle due incontra prima — e con
                    # l'etichetta del perdente nascerebbe «salmone» con nome visibile
                    # «Salmone selvaggio». Prenderli dal vincitore rende il risultato
                    # indipendente dall'ordine, che è la sola forma in cui è corretto.
                    display_name=(
                        winner.display_name if winner is not None else canonical.capitalize()
                    ),
                    category=winner.category if winner is not None else losing.category,
                )

    out: list[TermDecisionProposal] = []
    for proposal in proposals:
        replacement = merged.get(proposal.term_id) if proposal.action == "create" else None
        out.append(replacement if replacement is not None else proposal)
    return out


# `ingredients.name` e `ingredients.display_name` sono `String(NAME_MAX_LENGTH)`. Non è
# una preferenza di stile: oltre quel limite l'insert è un errore del database in mezzo
# alla passata che scrive, e niente a monte lo rifiuta — `decide_one` controlla che il
# nome non sia vuoto e che la categoria sia una delle dodici, e si ferma. Il limite si
# legge dal modello, dove la colonna è dichiarata: due 120 scritti a mano si
# scollerebbero al primo allargamento.
def _fits(text: str | None) -> bool:
    return bool(text) and len(text.strip()) <= NAME_MAX_LENGTH


@dataclass(frozen=True)
class Decided:
    applied: int
    created: int
    ignored: int
    still_pending: int


async def decide_terms(
    session: AsyncSession, terms: list[ImportTerm], client: object | None = None
) -> Decided:
    """Decide i termini in attesa e applica: fan-out, collasso, fan-in.

    Le domande partono insieme sotto un semaforo (`LLM_MAX_CONCURRENCY`); le
    **scritture** si applicano dopo, in sequenza e in ordine, rifacendo `match_name`
    prima di ogni `create`. Il parallelo è sulla rete, non sul database: due `create`
    dello stesso nome scritti insieme sarebbero un doppione o una violazione del
    vincolo, e in sequenza il secondo trova quello che il primo ha appena creato.

    Un guasto su un termine lascia in coda solo quel termine. `LlmUnavailable`
    risale solo quando **nessuna** chiamata è partita — manca la chiave — perché
    quello non è un intoppo: è una configurazione assente, e chi chiama la traduce in
    «decidi a mano».
    """
    from app.repositories.ingredients import create_ingredient, remember_alias
    from app.services.ingredient_match import match_name

    if not terms:
        return Decided(applied=0, created=0, ignored=0, still_pending=0)

    # senza chiave si esce prima di aprire qualunque cosa: è la configurazione, non
    # un intoppo, e N fallimenti identici non sono più informativi di uno
    build_headers()

    registry = await load_registry(session)
    # `max(1, ...)`: `LLM_MAX_CONCURRENCY` si scrive in `.env`, e a 0 (o negativo) il
    # semaforo non si aprirebbe mai — l'import resterebbe appeso per sempre, senza
    # timeout e senza errore, che è il guasto peggiore perché non si presenta. Un valore
    # assurdo degrada a una domanda per volta: lento, ma finisce e si vede.
    semaphore = asyncio.Semaphore(max(1, get_settings().llm_max_concurrency))

    async def ask(term: ImportTerm, api: object) -> TermDecisionProposal | None:
        async with semaphore:
            try:
                return await decide_one(session, term, registry, client=api)
            except LlmUnavailable as exc:
                # questo termine resta in coda; gli altri non ne sanno niente. Il
                # livello resta warning e non error: un modello giù è un evento
                # atteso (timeout, 429), non un difetto nostro — ma deve pur
                # comparire da qualche parte, perché un lotto intero che fallisce
                # così riporta `applied=0` senza dire perché.
                logger.warning(
                    "termine %r (%s) non deciso, resta in coda: %s",
                    term.display_name, term.id, exc,
                )
                return None

    owned = client is None
    api = client if client is not None else open_client()
    try:
        # `return_exceptions=True`: `ask` assorbe `LlmUnavailable`, ma il resto del
        # corpo di `decide_one` (e la lettura del termine per costruire la domanda) non
        # è coperto da niente, e un errore qualsiasi che risalisse dal gather
        # butterebbe le decisioni buone di tutto il lotto e chiuderebbe il client
        # condiviso nel `finally` con le altre chiamate ancora in volo — l'opposto
        # dell'isolamento del guasto per cui il fan-out esiste. Ciò che non è una
        # proposta vale «nessuna decisione»: quel termine resta in coda.
        raw = await asyncio.gather(
            *(ask(term, api) for term in terms), return_exceptions=True
        )
        # Un'eccezione qui non è un guasto del modello, è un difetto nostro — il
        # solo assorbimento sopra non la copre — e senza questo log un `decide_one`
        # rotto produce lo stesso `applied=0, still_pending=N` di un modello giù,
        # indistinguibile nei log perché finora non ce n'erano.
        for term, esito in zip(terms, raw):
            if isinstance(esito, BaseException):
                logger.error(
                    "errore inatteso decidendo il termine %r (%s)",
                    term.display_name, term.id, exc_info=esito,
                )
        proposals = [p for p in raw if isinstance(p, TermDecisionProposal)]
        proposals = await collapse_creates(session, proposals, registry, client=api)
    finally:
        if owned:
            await api.aclose()

    by_id = {term.id: term for term in terms}
    applied = created = ignored = 0

    for proposal in proposals:
        term = by_id.get(proposal.term_id)
        if term is None:
            continue

        if proposal.action == "ignore":
            term.decision = TermDecision.IGNORED
            term.ingredient_id = None
            # nessun alias: punterebbe a niente, e resterebbe
            ignored += 1
        else:
            # `merge` e `map` chiedono entrambi un ingrediente esistente; `create` lo
            # fa nascere. `match_name` si rifà qui, per ogni `create`, e il suo esito
            # vince sul registro caricato in cima: quel registro è stato letto prima
            # che partissero N chiamate parallele, quindi qui è già vecchio — e
            # `decide_one` confronta un nome nuovo solo con `ingredients.name`, mai
            # con gli alias, mentre `match_name` guarda entrambi. È così che un
            # `create: rigatoni` su un'anagrafica che ha «rigatoni» come alias di
            # «pasta» torna a essere il `map` che doveva essere, e così che il secondo
            # dei due `create` dello stesso nome trova quello che il primo ha appena
            # scritto.
            ingredient_id = proposal.ingredient_id
            if ingredient_id is None and proposal.name:
                match = await match_name(session, proposal.name)
                if match.certain:
                    ingredient_id = match.ingredient_id
            if ingredient_id is None:
                if proposal.action not in ("create", "merge") or not proposal.name:
                    continue
                if not _fits(proposal.name) or not _fits(
                    proposal.display_name or proposal.name
                ):
                    # si rifiuta come ogni altra risposta non verificabile: il termine
                    # resta `pending` e lo raccoglie la coda umana
                    continue
                ingredient = await create_ingredient(
                    session,
                    name=proposal.name,
                    display_name=proposal.display_name or proposal.name,
                    category=proposal.category or "altro",
                )
                ingredient_id = ingredient.id
                created += 1

            term.decision = TermDecision.MAPPED
            term.ingredient_id = ingredient_id
            # `import_terms.display_name` è `String(200)` e `alias` è `String(120)`: un
            # termine lunghissimo si decide comunque e l'alias si salta, perché la
            # decisione vive su `import_terms` e perderla sarebbe sproporzionato —
            # l'aggancio è buono, è l'etichetta permanente che non entra nella colonna.
            # Il rifiuto lo fa `remember_alias`, che torna `False`: farlo qui lascerebbe
            # scoperta la decisione umana, che chiama la stessa funzione.
            await remember_alias(session, ingredient_id, term.display_name)

        # `role_override` sta nell'elenco della spec §4.3 dei campi che ogni decisione
        # applicata scrive, e il Task 10 lo riporta a `NULL` annullando: l'AI non
        # propone ruoli, quindi il valore è `None` — scritto e non solo lasciato stare,
        # perché chi confronta i due elenchi non deve trovarci una differenza da
        # spiegare.
        term.role_override = None
        term.decided_by = "ai"
        term.decided_at = datetime.now(UTC)
        applied += 1

    await session.flush()
    still_pending = sum(1 for term in terms if term.decision == TermDecision.PENDING)
    return Decided(
        applied=applied, created=created, ignored=ignored, still_pending=still_pending
    )
