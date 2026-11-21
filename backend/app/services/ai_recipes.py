"""Stesura di ricette con un LLM.

Il modello fa una cosa sola: trasformare una richiesta in linguaggio naturale in
una ricetta strutturata, con i ruoli degli ingredienti già separati. Non salva
nulla e non produce valori nutrizionali: quelli vengono dai dati, non da un
modello linguistico.

Gli ingredienti proposti vengono agganciati all'anagrafica per somiglianza. Un
aggancio debole viene mostrato ma marcato incerto, perché un ingrediente
sbagliato in silenzio avvelena la disponibilità di tutte le ricette.

Le ricette scritte qui usano solo gli utensili dell'elenco (spec 2026-11-12 §8); con
l'elenco vuoto il prompt è quello di sempre.
"""

import json
import uuid
from dataclasses import dataclass
from typing import Any

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.recipe import Recipe
from app.domain.rules import IngredientKind, IngredientRole, cost_in_scale
from app.services.ingredient_match import match_name
from app.repositories.llm_calls import record_llm_call
from app.services.llm import LlmCallSite, LlmUnavailable, LlmUsage, complete_json
from app.services.recipe_import.decide import CATEGORIES
from app.services.utensils import utensils_prompt_block

DRAFT_MAX_TOKENS = 2000
# La variante rimanda indietro la ricetta intera, e un procedimento importato è lungo:
# col tetto della bozza una risposta troncata sarebbe JSON rotto, cioè un 503.
VARIANT_MAX_TOKENS = 4000

SYSTEM_PROMPT = """Sei un assistente di cucina. Rispondi SOLO con un oggetto JSON valido, senza testo attorno e senza blocchi di codice.

Schema richiesto:
{
  "title": "string",
  "description": "string breve",
  "instructions": "string, passaggi numerati",
  "servings": numero intero,
  "cost": numero intero da 1 a 5,
  "ingredients": [
    {"name": "nome generico dell'ingrediente", "role": "primary" oppure "secondary", "quantity_text": "string libera", "category": "reparto di supermercato"}
  ]
}

Regole:
- "role" è "primary" se l'ingrediente caratterizza il piatto e senza di esso la ricetta non esiste; è "secondary" se serve in piccole dosi e si può ridurre senza snaturare il piatto, come spezie, erbe aromatiche e condimenti.
- "name" deve essere il nome generico dell'ingrediente in italiano minuscolo, senza marche e senza aggettivi di preparazione. Scrivi "basilico", non "basilico fresco tritato finemente".
- "cost" è quanto costano gli ingredienti della ricetta intera, su cinque gradini: 1 molto basso, 2 basso, 3 medio, 4 elevato, 5 molto elevato. Pasta e ceci è 1, un filetto di manzo è 4, un risotto al tartufo è 5.
- Non inserire valori nutrizionali, calorie o macronutrienti.
- "category" è il reparto di supermercato dell'ingrediente, scelto fra: verdura, frutta, carne, pesce, latticini, cereali, legumi, condimenti, spezie, bevande, dolci, altro. Serve nel caso l'ingrediente non sia ancora in anagrafica.
"""

# R8. Le regole della bozza valgono tutte — lo schema, i ruoli, i nomi generici, il
# costo, niente nutrienti, i reparti del cibo — e la variante ne aggiunge di sue: per
# questo il testo estende `SYSTEM_PROMPT` invece di ricopiarlo.
VARIANT_SYSTEM_PROMPT = SYSTEM_PROMPT + """
Questa volta non scrivi una ricetta da zero. Ricevi un oggetto JSON con due chiavi: "ricetta", una ricetta che esiste già, e "richiesta", la modifica che la persona vuole. Rispondi con la ricetta modificata, intera, nello stesso schema.
- Applica la richiesta e ribilancia il resto: se togli, aggiungi o sostituisci un ingrediente, correggi le dosi, i tempi e i passaggi del procedimento che ne dipendono, perché il piatto riesca. Sostituire lo zucchero con un dolcificante, per esempio, cambia la dose e può cambiare i liquidi e la cottura.
- Quel che la richiesta non tocca resta com'è: gli ingredienti con lo stesso "name", la stessa "quantity_text", lo stesso "role" e la stessa "category", e lo stesso numero di porzioni.
- "title" dice in cosa la variante è diversa dall'originale: "Torta di mele con dolcificante", non di nuovo "Torta di mele".
- "cost" è il costo della variante, non quello dell'originale.
- Solo ingredienti alimentari: niente prodotti per la casa o per l'igiene, anche se la richiesta li nomina.
"""

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "instructions": {"type": "string"},
        "servings": {"type": ["integer", "null"]},
        # niente `minimum`/`maximum`: non tutti i fornitori li accettano in modalità
        # rigorosa, e la scala la controlla comunque `cost_in_scale` qui sotto
        "cost": {"type": ["integer", "null"]},
        "ingredients": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "role": {"type": "string", "enum": ["primary", "secondary"]},
                    "quantity_text": {"type": ["string", "null"]},
                    "category": {"type": "string"},
                },
                "required": ["name", "role", "quantity_text", "category"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["title", "description", "instructions", "servings", "cost", "ingredients"],
    "additionalProperties": False,
}


@dataclass
class DraftIngredient:
    raw_name: str
    role: IngredientRole
    quantity_text: str | None
    ingredient_id: uuid.UUID | None
    matched_name: str | None
    confident: bool
    proposed_category: str | None = None
    # Vero quando la riga nomina con certezza (nome o alias esatto) un ingrediente non
    # alimentare: l'aggancio si stacca (una ricetta non lo può avere), e il modulo dice
    # «non è un alimento» invece di «non in anagrafica», che lì sarebbe falso.
    non_food: bool = False


@dataclass
class RecipeDraft:
    title: str
    description: str | None
    instructions: str
    servings: int | None
    ingredients: list[DraftIngredient]
    cost: int | None = None


def system_with_utensils(base: str, block: str | None) -> str:
    """Il prompt di sistema con il blocco degli utensili; senza blocco, `base` com'è."""
    return base if block is None else f"{base}\n{block}\n"


async def draft_recipe(
    session: AsyncSession, prompt: str, client: AsyncAnthropic | None = None
) -> RecipeDraft:
    block = await utensils_prompt_block(session)
    payload = await _ask(
        session, call_site=LlmCallSite.RECIPE_DRAFT,
        system=system_with_utensils(SYSTEM_PROMPT, block), user=prompt,
        max_tokens=DRAFT_MAX_TOKENS, client=client,
    )
    return await _draft_from(session, payload)


def variant_question(recipe: Recipe, prompt: str) -> str:
    """La domanda della variante: la ricetta com'è salvata, e la richiesta (R8).

    Le righe col nome canonico dell'anagrafica e non col nome a video: è quello che
    `match_name` riconosce con certezza, quindi le righe che la variante tiene tornano
    agganciate senza niente da confermare. Il reparto c'è perché lo schema lo chiede a
    ogni riga, e il modello lo ripete invece di indovinarlo.
    """
    return json.dumps(
        {
            "ricetta": {
                "title": recipe.title,
                "description": recipe.description,
                "instructions": recipe.instructions,
                "servings": recipe.servings,
                "cost": recipe.cost,
                "ingredients": [
                    {
                        "name": line.ingredient.name,
                        "role": line.role,
                        "quantity_text": line.quantity_text,
                        "category": line.ingredient.category,
                    }
                    for line in recipe.ingredients
                ],
            },
            "richiesta": prompt,
        },
        ensure_ascii=False,
    )


async def draft_variant(
    session: AsyncSession, recipe: Recipe, prompt: str, client: AsyncAnthropic | None = None
) -> RecipeDraft:
    """Una variante di `recipe` secondo `prompt` (R8): la ricetta modificata, intera, da
    correggere nel modulo. Propone e non salva, e l'originale non si tocca: si salva con
    `POST /recipes` e `derived_from_id`, come ogni ricetta nuova.

    La domanda si costruisce prima della chiamata: dopo, la registrazione della spesa fa
    `commit` sulla sessione.
    """
    question = variant_question(recipe, prompt)
    block = await utensils_prompt_block(session)
    payload = await _ask(
        session, call_site=LlmCallSite.RECIPE_VARIANT,
        system=system_with_utensils(VARIANT_SYSTEM_PROMPT, block),
        user=question, max_tokens=VARIANT_MAX_TOKENS, client=client,
    )
    return await _draft_from(session, payload)


async def _ask(
    session: AsyncSession,
    *,
    call_site: LlmCallSite,
    system: str,
    user: str,
    max_tokens: int,
    client: AsyncAnthropic | None,
) -> dict[str, Any]:
    """Una chiamata con lo schema della bozza, con la spesa registrata comunque vada."""
    try:
        esito = await complete_json(
            call_site=call_site,
            system=system,
            user=user,
            schema=DRAFT_SCHEMA,
            max_tokens=max_tokens,
            client=client,
        )
    except LlmUnavailable:
        await _record_spend(session, call_site, LlmUsage(), ok=False)
        raise

    await _record_spend(session, call_site, esito.usage, ok=True)
    return esito.data


async def _draft_from(session: AsyncSession, payload: dict[str, Any]) -> RecipeDraft:
    """La risposta del modello diventa una bozza: la stessa lavorazione per la stesura da
    zero e per la variante (R8), così le guardie sulle righe sono una sola."""
    raw_ingredients = payload.get("ingredients") or []
    if not isinstance(raw_ingredients, list):
        raise LlmUnavailable("la lista degli ingredienti ha una forma inutilizzabile")

    ingredients: list[DraftIngredient] = []
    for entry in raw_ingredients:
        if not isinstance(entry, dict):
            continue
        raw_name = str(entry.get("name", "")).strip()
        if not raw_name:
            continue
        role = (
            IngredientRole.SECONDARY
            if entry.get("role") == IngredientRole.SECONDARY
            else IngredientRole.PRIMARY
        )
        match = await match_name(session, raw_name)
        # Stessa idea di `proposed_category` due righe sotto: una riga non agganciata
        # che l'utente risolve col selettore è meglio di una già agganciata che
        # `POST /recipes` rifiuterebbe con un 422 (finding 3 della revisione
        # finale). Il selettore, dal Task 9, offre solo cibo.
        non_food = match.kind == IngredientKind.NON_FOOD
        category = str(entry.get("category") or "").strip().lower()
        ingredients.append(
            DraftIngredient(
                raw_name=raw_name, role=role,
                quantity_text=entry.get("quantity_text") or None,
                ingredient_id=None if non_food else match.ingredient_id,
                matched_name=None if non_food else match.name,
                confident=False if non_food else match.certain,
                # Solo se l'anagrafica non ce l'ha: proporre una categoria per un
                # ingrediente che esiste già inviterebbe a cambiargliela da una
                # schermata che non è il registro. E solo se è una delle dodici: un
                # campo vuoto da riempire è meglio di un valore che il salvataggio
                # rifiuterebbe.
                proposed_category=(
                    category
                    if match.ingredient_id is None and category in CATEGORIES
                    else None
                ),
                # solo la coincidenza certa: una somiglianza con un non alimentare non
                # dice che la riga lo sia, e lì resta «non in anagrafica»
                non_food=non_food and match.certain,
            )
        )

    return RecipeDraft(
        title=str(payload.get("title", "Senza titolo")),
        description=payload.get("description") or None,
        instructions=str(payload.get("instructions", "")),
        servings=payload.get("servings"),
        ingredients=ingredients,
        # fuori scala, non intero o assente è nessun costo: il modulo lo mostra vuoto,
        # e un campo vuoto è meglio di un gradino inventato o arrotondato
        cost=cost_in_scale(payload.get("cost")),
    )


async def _record_spend(
    session: AsyncSession, call_site: LlmCallSite, usage: LlmUsage, *, ok: bool
) -> None:
    """La spesa si committa anche se la bozza non si salva.

    Queste rotte propongono e non scrivono: la loro sessione non viene committata da
    nessuno. Ma la chiamata è avvenuta ed è stata pagata che l'utente salvi la ricetta
    o la butti, e legarne la registrazione al salvataggio renderebbe invisibile
    proprio il consumo più facile da fare per sbaglio — dieci bozze chieste e nessuna
    tenuta. La commit è sicura perché su questo percorso non c'è nient'altro in sospeso
    nella sessione.
    """
    await record_llm_call(session, call_site=call_site, usage=usage, ok=ok)
    await session.commit()
