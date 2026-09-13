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
import uuid
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe_import import ImportTerm
from app.services.llm import LlmUnavailable, complete_json, open_client

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

    merged: dict[str, TermDecisionProposal] = {}
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

        for raw in names:
            name = str(raw or "").strip().lower()
            if name == canonical or name not in proposed:
                continue  # un nome che nessuno ha proposto non si accorpa
            losing = proposed[name]
            winner = proposed.get(canonical)
            merged[name] = TermDecisionProposal(
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
        replacement = merged.get(proposal.name) if proposal.action == "create" else None
        out.append(replacement if replacement is not None else proposal)
    return out
