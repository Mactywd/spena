"""Stesura di ricette con un LLM.

Il modello fa una cosa sola: trasformare una richiesta in linguaggio naturale in
una ricetta strutturata, con i ruoli degli ingredienti già separati. Non salva
nulla e non produce valori nutrizionali: quelli vengono dai dati, non da un
modello linguistico.

Gli ingredienti proposti vengono agganciati all'anagrafica per somiglianza. Un
aggancio debole viene mostrato ma marcato incerto, perché un ingrediente
sbagliato in silenzio avvelena la disponibilità di tutte le ricette.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.rules import IngredientRole
from app.services.ingredient_match import match_name
from app.services.llm import LlmUnavailable, complete_json
from app.services.recipe_import.decide import CATEGORIES

DRAFT_MAX_TOKENS = 2000

SYSTEM_PROMPT = """Sei un assistente di cucina. Rispondi SOLO con un oggetto JSON valido, senza testo attorno e senza blocchi di codice.

Schema richiesto:
{
  "title": "string",
  "description": "string breve",
  "instructions": "string, passaggi numerati",
  "servings": numero intero,
  "ingredients": [
    {"name": "nome generico dell'ingrediente", "role": "primary" oppure "secondary", "quantity_text": "string libera", "category": "reparto di supermercato"}
  ]
}

Regole:
- "role" è "primary" se l'ingrediente caratterizza il piatto e senza di esso la ricetta non esiste; è "secondary" se serve in piccole dosi e si può ridurre senza snaturare il piatto, come spezie, erbe aromatiche e condimenti.
- "name" deve essere il nome generico dell'ingrediente in italiano minuscolo, senza marche e senza aggettivi di preparazione. Scrivi "basilico", non "basilico fresco tritato finemente".
- Non inserire valori nutrizionali, calorie o macronutrienti.
- "category" è il reparto di supermercato dell'ingrediente, scelto fra: verdura, frutta, carne, pesce, latticini, cereali, legumi, condimenti, spezie, bevande, dolci, altro. Serve nel caso l'ingrediente non sia ancora in anagrafica.
"""

DRAFT_SCHEMA = {
    "type": "object",
    "properties": {
        "title": {"type": "string"},
        "description": {"type": ["string", "null"]},
        "instructions": {"type": "string"},
        "servings": {"type": ["integer", "null"]},
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
    "required": ["title", "description", "instructions", "servings", "ingredients"],
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


@dataclass
class RecipeDraft:
    title: str
    description: str | None
    instructions: str
    servings: int | None
    ingredients: list[DraftIngredient]


async def draft_recipe(
    session: AsyncSession, prompt: str, client: object | None = None
) -> RecipeDraft:
    payload = await complete_json(
        system=SYSTEM_PROMPT,
        user=prompt,
        schema=DRAFT_SCHEMA,
        schema_name="bozza_ricetta",
        max_tokens=DRAFT_MAX_TOKENS,
        client=client,
    )
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
        category = str(entry.get("category") or "").strip().lower()
        ingredients.append(
            DraftIngredient(
                raw_name=raw_name, role=role,
                quantity_text=entry.get("quantity_text") or None,
                ingredient_id=match.ingredient_id, matched_name=match.name,
                confident=match.certain,
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
            )
        )

    return RecipeDraft(
        title=str(payload.get("title", "Senza titolo")),
        description=payload.get("description") or None,
        instructions=str(payload.get("instructions", "")),
        servings=payload.get("servings"),
        ingredients=ingredients,
    )
