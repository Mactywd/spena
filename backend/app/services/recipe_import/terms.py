"""Il dizionario dal catalogo della fonte al nostro.

Il catalogo di un sito di cucina è più fine di un'anagrafica fatta per rispondere
«ce l'ho in casa?»: dove noi abbiamo `pasta`, loro hanno `Rigatoni`. Colmare quella
distanza è l'unica parte dell'import che non si automatizza, perché colmarla male
avvelena la disponibilità di tutte le ricette che usano quell'ingrediente.

Quel che si automatizza è l'uguaglianza: un termine che coincide con un nostro nome
canonico o con un alias già scritto si decide da sé. Non è una proposta, è un fatto.
"""

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.imports import pending_pages, terms_by_key
from app.services.ai_recipes import AiUnavailable, _build_client
from app.services.ingredient_match import match_name


@dataclass(frozen=True)
class TermsSynced:
    created: int
    auto_decided: int
    pending: int


async def sync_terms(session: AsyncSession, source: str = GIALLOZAFFERANO) -> TermsSynced:
    """Allinea il dizionario alle pagine in attesa.

    `occurrences` conta le **ricette** in attesa che usano il termine, non le righe:
    la frolla e la crema vogliono entrambe lo zucchero a velo, ma la ricetta
    bloccata è una. Si ricalcola a ogni passaggio e non si incrementa mai: un
    contatore incrementato divergerebbe al primo ri-scarico, e un ordinamento della
    coda basato su un numero sbagliato è un difetto che nessuno nota.
    """
    occurrences: dict[str, int] = {}
    display_names: dict[str, str] = {}
    for page in await pending_pages(session, source):
        keys_here = set()
        for line in page.payload.get("ingredients") or []:
            key = line.get("key")
            if not key:
                continue
            keys_here.add(key)
            display_names.setdefault(key, str(line.get("name") or key)[:200])
        for key in keys_here:
            occurrences[key] = occurrences.get(key, 0) + 1

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
            if match.certain:
                term.decision = TermDecision.MAPPED
                term.ingredient_id = match.ingredient_id
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


PROPOSAL_MODEL = "claude-sonnet-5"
PROPOSAL_MAX_TOKENS = 3000
# il prompt porta l'anagrafica intera: un lotto senza tetto la farebbe crescere fino
# a una chiamata che costa e che il modello tronca a metà
MAX_TERMS_PER_CALL = 40

PROPOSAL_SYSTEM_PROMPT = """Sei un aiuto per mettere in ordine un'anagrafica di ingredienti. Rispondi SOLO con un oggetto JSON valido, senza testo attorno e senza blocchi di codice.

Ricevi una lista di nomi di ingredienti presi da un sito di cucina, e l'anagrafica di un'app di dispensa. Per ognuno dei nomi scegli UNA delle tre azioni:

- "map": è lo stesso ingrediente di uno che esiste già in anagrafica, scritto più in dettaglio. "Rigatoni" è pasta, "Latte intero" è latte.
- "create": è un ingrediente generico che l'anagrafica non ha. Dai il nome canonico in italiano minuscolo e singolare, il nome da mostrare, e la categoria.
- "ignore": non è qualcosa che si tiene in dispensa. L'acqua, il ghiaccio, l'acqua per la cottura.

Schema richiesto:
{
  "proposals": [
    {"term": "il nome ricevuto, identico", "action": "map", "ingredient": "nome canonico esistente"},
    {"term": "...", "action": "create", "name": "...", "display_name": "...", "category": "..."},
    {"term": "...", "action": "ignore"}
  ]
}

Regole:
- "ingredient" deve essere uno dei nomi canonici che ti passo, scritto identico.
- "category" deve essere una delle categorie che ti passo, scritta identica.
- Preferisci "map" quando l'ingrediente esiste già: un'anagrafica con venti formati di pasta non sa più dire cosa c'è in casa.
- Non inserire valori nutrizionali.
"""


@dataclass(frozen=True)
class TermProposal:
    term_id: uuid.UUID
    action: str
    ingredient_id: uuid.UUID | None = None
    name: str | None = None
    display_name: str | None = None
    category: str | None = None


async def propose_decisions(
    session: AsyncSession, terms: list[ImportTerm], client: object | None = None
) -> list[TermProposal]:
    """Una proposta per ogni termine che il modello riesce a giudicare.

    Claude propone e non decide: il risultato va mostrato e confermato. Una proposta
    che non si può verificare — un ingrediente che non esiste, una categoria
    inventata, un termine che non avevo chiesto — si scarta invece di essere
    mostrata: rumore travestito da dato è peggio di nessuna proposta.

    `AiUnavailable` non è un errore da nascondere né da far fallire la coda: chi
    chiama lo traduce in «decidi a mano», che è sempre possibile.
    """
    batch = terms[:MAX_TERMS_PER_CALL]
    if not batch:
        return []

    api = client if client is not None else _build_client()
    registry = list(
        (
            await session.execute(
                select(Ingredient.id, Ingredient.name, Ingredient.category).order_by(
                    Ingredient.name
                )
            )
        ).all()
    )
    by_name = {name: ingredient_id for ingredient_id, name, _ in registry}
    name_by_id = {ingredient_id: name for ingredient_id, name, _ in registry}
    categories = {str(value) for value in IngredientCategory}

    question = json.dumps(
        {
            "termini": [term.display_name for term in batch],
            "anagrafica": [
                {"nome": name, "categoria": category} for _, name, category in registry
            ],
            "categorie": sorted(categories),
        },
        ensure_ascii=False,
    )

    try:
        response = await api.messages.create(
            model=PROPOSAL_MODEL,
            max_tokens=PROPOSAL_MAX_TOKENS,
            system=PROPOSAL_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": question}],
        )
        payload = json.loads(response.content[0].text)
        raw = payload.get("proposals") if isinstance(payload, dict) else None
        if not isinstance(raw, list):
            raise AiUnavailable("la risposta non contiene una lista di proposte")
    except AiUnavailable:
        raise
    except Exception as exc:  # rete, quota, JSON malformato
        raise AiUnavailable(str(exc)) from exc

    by_display = {term.display_name: term for term in batch}
    proposals: list[TermProposal] = []
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        term = by_display.get(str(entry.get("term", "")))
        if term is None:
            continue  # un termine che non avevo chiesto
        action = entry.get("action")
        if action == "ignore":
            proposals.append(TermProposal(term_id=term.id, action="ignore"))
        elif action == "map":
            ingredient_id = by_name.get(str(entry.get("ingredient", "")).strip().lower())
            if ingredient_id is None:
                continue  # un ingrediente che non esiste non è una proposta
            proposals.append(
                TermProposal(
                    term_id=term.id, action="map", ingredient_id=ingredient_id,
                    # il nome canonico: lo abbiamo già risolto per verificare che
                    # l'ingrediente esista, ed è la sola fonte di un nome leggibile
                    # che la scheda può mostrare senza fidarsi di un id cieco
                    name=name_by_id.get(ingredient_id),
                )
            )
        elif action == "create":
            category = str(entry.get("category", "")).strip().lower()
            name = str(entry.get("name", "")).strip().lower()
            if category not in categories or not name:
                continue
            existing_id = by_name.get(name)
            if existing_id is not None:
                # Claude ha proposto "create" per un nome che l'anagrafica ha già
                # (lo stesso caso di "Rigatoni" -> "pasta" che per "map" scartiamo
                # se l'ingrediente non esiste): qui l'ingrediente esiste, quindi la
                # carta verificata non è il "create" che il 409 rifiuterebbe a ogni
                # tocco, ma il "map" che Claude avrebbe dovuto scegliere. Lo
                # convertiamo invece di scartarlo: l'id e il nome canonico li
                # abbiamo già, dalla stessa ricerca che verifica un "map" vero, senza
                # bisogno di indovinare niente.
                proposals.append(
                    TermProposal(
                        term_id=term.id, action="map", ingredient_id=existing_id,
                        name=name_by_id.get(existing_id),
                    )
                )
                continue
            proposals.append(
                TermProposal(
                    term_id=term.id, action="create", name=name,
                    display_name=str(entry.get("display_name") or name).strip(),
                    category=category,
                )
            )
    return proposals
