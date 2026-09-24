"""Da pagina in attesa a ricetta vera.

Una pagina diventa ricetta solo quando **tutti** i suoi termini hanno una decisione.
L'alternativa — far entrare la ricetta con la riga non agganciata — richiederebbe di
dire alla cucinabilità cosa risponde su un ingrediente ignoto: «sì» è una bugia che
si scopre a metà cottura, «no» nasconde ricette fattibili. Aspettare è la sola
risposta onesta, ed è sopportabile perché la coda è ordinata per quante ricette
sblocca.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient
from app.db.models.recipe import RecipeSource
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportState, TermDecision
from app.domain.rules import IngredientRole, cost_in_scale, default_role
from app.repositories.imports import pending_pages, terms_by_key
from app.repositories.recipes import NonFoodInRecipe, create_recipe
from app.services.embeddings import (
    EmbeddingUnavailable,
    get_embedding_provider,
    log_degradation_once,
    recipe_document,
)

MAX_QUANTITY_CHARS = 100  # il limite di recipe_ingredients.quantity_text
EMPTY_REASON = (
    "ogni ingrediente è stato ignorato: la ricetta resterebbe senza righe, "
    "e una ricetta senza ingredienti risulterebbe sempre cucinabile"
)


@dataclass(frozen=True)
class Materialized:
    created: int
    skipped: int


def merge_quantities(first: str | None, second: str | None) -> str | None:
    """Due dosi sullo stesso ingrediente diventano una stringa sola.

    Il gruppo di appartenenza («per la frolla», «per la crema») non entra nel nostro
    modello, quindi unire è il massimo di verità che si può conservare: si legge
    «500 g + 50 g», che è meno informativo dei due gruppi separati ma non è falso.
    """
    parts = [part for part in (first, second) if part]
    if not parts:
        return None
    return " + ".join(parts)[:MAX_QUANTITY_CHARS]


def stronger(first: IngredientRole, second: IngredientRole) -> IngredientRole:
    """`primary` vince: la farina della frolla serve anche se la spolverata è «q.b.»."""
    if IngredientRole.PRIMARY in (first, second):
        return IngredientRole.PRIMARY
    return IngredientRole.SECONDARY


async def materialize_ready(
    session: AsyncSession, source: str = GIALLOZAFFERANO
) -> Materialized:
    """Tutte le pagine in attesa i cui termini sono decisi diventano ricette."""
    terms = await terms_by_key(session, source)
    categories = dict(
        (await session.execute(select(Ingredient.id, Ingredient.category))).all()
    )
    provider = get_embedding_provider()

    created = 0
    skipped = 0
    for page in await pending_pages(session, source):
        lines = page.payload.get("ingredients") or []
        decisions = [terms.get(line.get("key")) for line in lines]
        if any(
            term is None or term.decision == TermDecision.PENDING for term in decisions
        ):
            continue  # aspetta: è la decisione presa nello spec §2

        # collasso per ingrediente, nell'ordine di prima comparsa
        collapsed: dict[uuid.UUID, tuple[IngredientRole, str | None]] = {}
        for line, term in zip(lines, decisions, strict=True):
            if term.decision == TermDecision.IGNORED:
                continue
            quantity = line.get("quantity_text")
            role = IngredientRole(
                term.role_override
                or default_role(categories.get(term.ingredient_id, "altro"), quantity)
            )
            key = term.ingredient_id
            if key in collapsed:
                previous_role, previous_quantity = collapsed[key]
                collapsed[key] = (
                    stronger(previous_role, role),
                    merge_quantities(previous_quantity, quantity),
                )
            else:
                collapsed[key] = (role, quantity[:MAX_QUANTITY_CHARS] if quantity else None)

        if not collapsed:
            page.state = ImportState.SKIPPED
            page.skipped_reason = EMPTY_REASON[:200]
            skipped += 1
            continue

        text = recipe_document(page.payload.get("title", ""), page.payload.get("description"))
        try:
            embedding = (await provider.embed_passages([text]))[0]
        except EmbeddingUnavailable as exc:
            # il vettore è un ornamento: la ricetta vale anche senza. `app.cli.reindex`
            # li calcola dopo, quando il modello c'è.
            embedding = None
            log_degradation_once(exc)

        try:
            recipe = await create_recipe(
                session,
                title=str(page.payload.get("title") or "Senza titolo")[:200],
                description=page.payload.get("description"),
                instructions=str(page.payload.get("instructions") or ""),
                servings=page.payload.get("servings"),
                source=RecipeSource.DATASET,
                source_ref=page.url,
                ingredients=[
                    (ingredient_id, role, quantity, None)
                    for ingredient_id, (role, quantity) in collapsed.items()
                ],
                embedding=embedding,
            )
        except NonFoodInRecipe as exc:
            # Per pagina, non per lotto: `create_recipe` è l'ultima linea di difesa e
            # solleva forte apposta (vedi la sua docstring). Senza questo `except`,
            # una sola riga non alimentare — arrivata qui solo perché una guardia più
            # a monte ha un buco — farebbe fallire con un errore non gestito la
            # materializzazione di tutte le pagine pronte di questa chiamata, buone
            # comprese, e senza che nessuna delle loro scritture venisse salvata. La
            # pagina resta visibile e recuperabile: SKIPPED col nome della voce
            # incriminata, non un buco silenzioso.
            page.state = ImportState.SKIPPED
            page.skipped_reason = f"riga non alimentare: «{exc.display_name}»"[:200]
            skipped += 1
            continue
        recipe.category = (page.payload.get("category") or None) and str(page.payload["category"])[:60]
        recipe.image_url = (page.payload.get("image_url") or None) and str(page.payload["image_url"])[:500]
        recipe.prep_minutes = page.payload.get("prep_minutes")
        recipe.cook_minutes = page.payload.get("cook_minutes")
        # Assente sulle pagine scaricate prima di R9, e un valore fuori scala non
        # deve arrivare al CHECK di `recipes.cost`: lì farebbe fallire il flush di
        # tutte le pagine pronte di questa chiamata, non solo di questa.
        recipe.cost = cost_in_scale(page.payload.get("cost"))
        page.state = ImportState.IMPORTED
        page.recipe_id = recipe.id
        created += 1

    await session.flush()
    return Materialized(created=created, skipped=skipped)
