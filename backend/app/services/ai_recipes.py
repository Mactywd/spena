"""Stesura di ricette con Claude.

Il modello fa una cosa sola: trasformare una richiesta in linguaggio naturale in
una ricetta strutturata, con i ruoli degli ingredienti già separati. Non salva
nulla e non produce valori nutrizionali: quelli vengono dai dati, non da un
modello linguistico.

Gli ingredienti proposti vengono agganciati all'anagrafica per somiglianza. Un
aggancio debole viene mostrato ma marcato incerto, perché un ingrediente
sbagliato in silenzio avvelena la disponibilità di tutte le ricette.
"""

import json
import uuid
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.domain.rules import IngredientRole
from app.repositories.ingredients import search_ingredients

MODEL = "claude-sonnet-5"
MAX_TOKENS = 2000

SYSTEM_PROMPT = """Sei un assistente di cucina. Rispondi SOLO con un oggetto JSON valido, senza testo attorno e senza blocchi di codice.

Schema richiesto:
{
  "title": "string",
  "description": "string breve",
  "instructions": "string, passaggi numerati",
  "servings": numero intero,
  "ingredients": [
    {"name": "nome generico dell'ingrediente", "role": "primary" oppure "secondary", "quantity_text": "string libera"}
  ]
}

Regole:
- "role" è "primary" se l'ingrediente caratterizza il piatto e senza di esso la ricetta non esiste; è "secondary" se serve in piccole dosi e si può ridurre senza snaturare il piatto, come spezie, erbe aromatiche e condimenti.
- "name" deve essere il nome generico dell'ingrediente in italiano minuscolo, senza marche e senza aggettivi di preparazione. Scrivi "basilico", non "basilico fresco tritato finemente".
- Non inserire valori nutrizionali, calorie o macronutrienti.
"""


class AiUnavailable(Exception):
    """Claude non raggiungibile o risposta inutilizzabile. La sezione lo dichiara."""


@dataclass
class DraftIngredient:
    raw_name: str
    role: IngredientRole
    quantity_text: str | None
    ingredient_id: uuid.UUID | None
    matched_name: str | None
    confident: bool


@dataclass
class RecipeDraft:
    title: str
    description: str | None
    instructions: str
    servings: int | None
    ingredients: list[DraftIngredient]


def _build_client():
    key = get_settings().anthropic_api_key
    if not key:
        raise AiUnavailable("ANTHROPIC_API_KEY non configurata")
    try:
        from anthropic import AsyncAnthropic
    except ImportError as exc:
        raise AiUnavailable("pacchetto anthropic non installato") from exc
    return AsyncAnthropic(api_key=key)


async def _match(
    session: AsyncSession, raw_name: str
) -> tuple[uuid.UUID | None, str | None, bool]:
    """Aggancia un nome proposto all'anagrafica, dichiarando quanto si fida.

    La certezza richiede corrispondenza esatta con il nome canonico: tutto il
    resto si propone ma si marca incerto.
    """
    candidates = await search_ingredients(session, raw_name, limit=1)
    if not candidates:
        return None, None, False

    best = candidates[0]
    normalized = raw_name.strip().lower()
    confident = normalized == best.name
    return best.id, best.name, confident


async def draft_recipe(
    session: AsyncSession, prompt: str, client: object | None = None
) -> RecipeDraft:
    api = client if client is not None else _build_client()

    try:
        response = await api.messages.create(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": prompt}],
        )
        payload = json.loads(response.content[0].text)
    except AiUnavailable:
        raise
    except Exception as exc:  # errore di rete, quota, JSON malformato
        raise AiUnavailable(str(exc)) from exc

    ingredients: list[DraftIngredient] = []
    for entry in payload.get("ingredients", []):
        raw_name = str(entry.get("name", "")).strip()
        if not raw_name:
            continue
        role = (
            IngredientRole.SECONDARY
            if entry.get("role") == IngredientRole.SECONDARY
            else IngredientRole.PRIMARY
        )
        ingredient_id, matched_name, confident = await _match(session, raw_name)
        ingredients.append(
            DraftIngredient(
                raw_name=raw_name, role=role,
                quantity_text=entry.get("quantity_text") or None,
                ingredient_id=ingredient_id, matched_name=matched_name, confident=confident,
            )
        )

    return RecipeDraft(
        title=str(payload.get("title", "Senza titolo")),
        description=payload.get("description") or None,
        instructions=str(payload.get("instructions", "")),
        servings=payload.get("servings"),
        ingredients=ingredients,
    )
