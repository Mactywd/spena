import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session, is_missing_reference, is_unique_violation
from app.core.security import require_session
from app.db.models.recipe import Recipe
from app.domain.quantities import UnitForms, render_quantity, scale_quantity
from app.domain.rules import (
    Availability,
    IngredientRole,
    is_cookable,
    is_satisfied,
    missing_count,
)
from app.repositories.ingredients import create_ingredient
from app.repositories.pantry import availability_map
from app.repositories.recipes import NonFoodInRecipe, create_recipe, get_recipe
from app.schemas.ai import DraftIngredientOut, DraftOut, DraftRequest
from app.schemas.recipe import (
    RecipeCreate,
    RecipeIngredientOut,
    RecipeOut,
    RecipeSummaryOut,
    RecipeUpdate,
    SearchModeOut,
)
from app.services.ai_recipes import draft_recipe
from app.services.embeddings import (
    EmbeddingUnavailable,
    get_embedding_provider,
    log_degradation_once,
    recipe_document,
)
from app.services.ingredient_match import match_name
from app.services.llm import LlmUnavailable
from app.services.recipe_search import search_recipes, semantic_search_usable

router = APIRouter(
    prefix="/api/v1/recipes", tags=["recipes"], dependencies=[Depends(require_session)]
)


async def _to_out(
    session: AsyncSession, recipe: Recipe, servings: int | None = None
) -> RecipeOut:
    ingredient_ids = [ri.ingredient_id for ri in recipe.ingredients]
    availability = await availability_map(session, ingredient_ids)

    # Il fattore sta qui e non nel client: la pluralizzazione e l'aritmetica sono
    # logica di dominio, ed è la riga di CLAUDE.md che tiene in piedi la porta a
    # Capacitor. In TypeScript vorrebbe dire spedire il registro delle unità al
    # client e tenere le stesse regole in due lingue.
    factor: Decimal | None = None
    # `is not None` e non la verità: che `servings=0` non arrivi mai qui lo garantisce
    # `Query(ge=1)` in fondo a questo file, e una condizione che dipende da un
    # validatore scritto altrove smette di valere il giorno in cui quello cambia
    if servings is not None and recipe.servings is not None:
        factor = Decimal(servings) / Decimal(recipe.servings)
        if factor == 1:
            factor = None  # chiedere le porzioni che ha già è come non chiedere niente

    lines: list[RecipeIngredientOut] = []
    requirements: list[tuple[IngredientRole, Availability]] = []
    missing_names: list[str] = []
    # Il conto della copertura si fa sulle righe che una dose ce l'hanno. «aglio» e
    # «basilico» senza `quantity_text` non sono dosi che non si riscalano: sono righe
    # senza dose, e contarle farebbe leggere «4 dosi su 12 non si riscalano» a chi di
    # dosi non riuscite ne ha due. La spec §5.4 promette la stessa onestà dei
    # nutrienti mancanti, e gonfiare il numero è il modo opposto di mancarla.
    # Il denominatore lo manda il server: qui si sa quali righe hanno una dose, nel
    # client si sa solo quante righe ci sono.
    dose_lines = 0
    unscalable = 0
    for ri in recipe.ingredients:
        have = availability.get(ri.ingredient_id, Availability.MISSING)
        role = IngredientRole(ri.role)
        requirements.append((role, have))
        if not is_satisfied(role, have):
            missing_names.append(ri.ingredient.display_name)
        if ri.quantity_text is not None:
            dose_lines += 1
        if factor is not None and ri.quantity_value is not None:
            forms = (
                UnitForms(ri.unit.key, ri.unit.singular, ri.unit.plural)
                if ri.unit
                else None
            )
            display = render_quantity(scale_quantity(ri.quantity_value, factor), forms)
            scaled = True
        else:
            display = ri.quantity_text
            scaled = False
            if factor is not None and ri.quantity_text is not None:
                unscalable += 1
        lines.append(
            RecipeIngredientOut(
                ingredient_id=ri.ingredient_id,
                ingredient_name=ri.ingredient.name,
                role=role,
                quantity_text=ri.quantity_text,
                note=ri.note,
                availability=have,
                satisfied=is_satisfied(role, have),
                quantity_display=display,
                quantity_scaled=scaled,
            )
        )
    # il conteggio e il verdetto arrivano da app/domain/rules.py, non da un `sum`
    # qui: ricalcolarli in linea fa sì che il test a tabella difenda una copia che
    # non gira, ed è la metà aggregata della regola del capitolo 7 della spec
    return RecipeOut(
        id=recipe.id, title=recipe.title, description=recipe.description,
        instructions=recipe.instructions, servings=recipe.servings, source=recipe.source,
        source_ref=recipe.source_ref, ingredients=lines,
        missing=missing_count(requirements), cookable=is_cookable(requirements),
        missing_names=sorted(missing_names),
        image_url=recipe.image_url, prep_minutes=recipe.prep_minutes,
        cook_minutes=recipe.cook_minutes, category=recipe.category, cost=recipe.cost,
        scaled_to=servings if factor is not None else None,
        unscalable_lines=unscalable, dose_lines=dose_lines,
    )


@router.get("/search", response_model=list[RecipeSummaryOut])
async def search(
    q: str | None = None,
    # quante cose si è disposti a comprare; assente vuol dire «tutto il ricettario»
    max_missing: int | None = Query(default=None, ge=0),
    # Sinonimo di `max_missing=0`, e non un residuo da togliere alla prossima
    # occasione. Il service worker della PWA può servire per giorni una copia vecchia
    # dello schermo, che manda ancora questo parametro: ignorarlo significherebbe
    # mostrarle il ricettario intero sotto l'etichetta di un filtro che sembra acceso
    # — lo stesso guasto silenzioso che il commento su `ingredient_id` qui sotto
    # esiste per evitare.
    only_cookable: bool = False,
    category: str | None = None,
    # ripetibile: `?ingredient_id=a&ingredient_id=b` vuol dire «che li contenga
    # tutti e due». Il nome resta al singolare — è il nome di ogni ripetizione, non
    # dell'insieme — e questo ha un secondo effetto utile: una copia vecchia del
    # frontend, servita dal service worker dalla sua cache, manda ancora un solo
    # `ingredient_id` e continua a filtrare bene, invece di vedersi ignorare il
    # parametro e mostrare il ricettario intero sotto l'etichetta di un filtro acceso.
    ingredient_id: list[uuid.UUID] = Query(default=[]),
    limit: int = Query(default=30, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[RecipeSummaryOut]:
    # esplicito batte sinonimo: se arrivano entrambi vince quello che la persona ha scelto
    budget = max_missing if max_missing is not None else (0 if only_cookable else None)
    results = await search_recipes(
        session,
        q,
        # per nome, non per posizione: il terzo argomento posizionale era un `bool` e
        # adesso è un `int | None`, e in Python `True == 1` — un `only_cookable`
        # rimasto posizionale diventerebbe in silenzio «al massimo un mancante»
        max_missing=budget,
        limit=limit,
        category=category,
        ingredient_ids=ingredient_id,
    )
    return [
        RecipeSummaryOut(
            id=r.recipe.id, title=r.recipe.title, description=r.recipe.description,
            source=r.recipe.source, missing=r.missing, cookable=r.cookable,
            missing_names=r.missing_names,
            image_url=r.recipe.image_url, prep_minutes=r.recipe.prep_minutes,
            cook_minutes=r.recipe.cook_minutes, category=r.recipe.category,
            cost=r.recipe.cost,
        )
        for r in results
    ]


@router.get("/search-mode", response_model=SearchModeOut)
async def search_mode(session: AsyncSession = Depends(get_session)) -> SearchModeOut:
    """Dichiarata prima di `/{recipe_id}`, altrimenti la rotta col parametro la mangia.

    La sessione serve dalla terza condizione di `semantic_search_usable`: la risposta
    parla anche del ricettario, non solo del fornitore di vettori.
    """
    return SearchModeOut(semantic=await semantic_search_usable(session))


@router.get("/categories", response_model=list[str])
async def categories(session: AsyncSession = Depends(get_session)) -> list[str]:
    """Le categorie presenti nel ricettario, per il filtro.

    Solo quelle che esistono davvero: un filtro che offre voci vuote è un filtro che
    porta a una schermata vuota.
    """
    rows = await session.execute(
        select(Recipe.category)
        .where(Recipe.category.is_not(None))
        .distinct()
        .order_by(Recipe.category)
    )
    return list(rows.scalars())


@router.get("/{recipe_id}", response_model=RecipeOut)
async def detail(
    recipe_id: uuid.UUID,
    servings: int | None = Query(default=None, ge=1, le=50),
    session: AsyncSession = Depends(get_session),
) -> RecipeOut:
    recipe = await get_recipe(session, recipe_id)
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ricetta inesistente")
    return await _to_out(session, recipe, servings=servings)


@router.patch("/{recipe_id}", response_model=RecipeOut)
async def update(
    recipe_id: uuid.UUID, payload: RecipeUpdate, session: AsyncSession = Depends(get_session)
) -> RecipeOut:
    """Cambia quel che `RecipeUpdate` dichiara, e solo i campi mandati davvero."""
    recipe = await get_recipe(session, recipe_id)
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ricetta inesistente")
    if "cost" in payload.model_fields_set:
        recipe.cost = payload.cost
    await session.commit()
    return await _to_out(session, recipe)


@router.post("", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
async def create(
    payload: RecipeCreate, session: AsyncSession = Depends(get_session)
) -> RecipeOut:
    """L'embedding è un ornamento: se il modello non c'è, la ricetta si salva comunque."""
    text = recipe_document(payload.title, payload.description)
    try:
        embedding = (await get_embedding_provider().embed_passages([text]))[0]
    except EmbeddingUnavailable as exc:
        embedding = None
        log_degradation_once(exc)

    try:
        # Le righe che nominano un ingrediente non ancora in anagrafica lo creano qui,
        # dentro la stessa transazione della ricetta: se il salvataggio fallisce non
        # resta nessun ingrediente orfano. In sequenza e non in parallelo, per lo
        # stesso motivo del fan-in dell'import: due righe con lo stesso nome nuovo
        # devono diventare un ingrediente, non un doppione.
        resolved: list[tuple[uuid.UUID, str, str | None, str | None]] = []
        for line in payload.ingredients:
            ingredient_id = line.ingredient_id
            if ingredient_id is None:
                # `match_name` e non una ricerca sul solo nome canonico: se la bozza
                # dice «pomodori» e l'anagrafica ha «pomodoro» con quell'alias,
                # collegarsi è giusto e creare sarebbe un duplicato travestito
                match = await match_name(session, line.name or "")
                if match.certain and match.ingredient_id is not None:
                    ingredient_id = match.ingredient_id
                else:
                    created = await create_ingredient(
                        session, name=line.name or "",
                        display_name=(line.name or "").capitalize(),
                        category=line.category or "altro",
                    )
                    ingredient_id = created.id
            resolved.append((ingredient_id, line.role, line.quantity_text, line.note))

        recipe = await create_recipe(
            session, title=payload.title, description=payload.description,
            instructions=payload.instructions, servings=payload.servings,
            source=payload.source, source_ref=payload.source_ref,
            ingredients=resolved,
            embedding=embedding,
            cost=payload.cost,
        )
        await session.commit()
    except NonFoodInRecipe as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"«{exc.display_name}» non è un alimento: una ricetta non può averlo fra "
            "gli ingredienti. Toglilo dalla riga, poi salva.",
        ) from exc
    except IntegrityError as exc:
        await session.rollback()
        if is_missing_reference(exc):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente") from exc
        # solo un duplicato è un "ripetuto": qualunque altra violazione è un difetto
        # nostro e deve restare visibile come 500, come in shopping.py e pantry.py
        if not is_unique_violation(exc):
            raise
        raise HTTPException(
            status.HTTP_409_CONFLICT, "ingrediente ripetuto nella ricetta"
        ) from exc
    stored = await get_recipe(session, recipe.id)
    return await _to_out(session, stored)


@router.post("/ai-draft", response_model=DraftOut)
async def ai_draft(
    payload: DraftRequest, session: AsyncSession = Depends(get_session)
) -> DraftOut:
    """Propone, non salva. Il salvataggio passa da POST /recipes come le altre."""
    try:
        draft = await draft_recipe(session, payload.prompt)
    except LlmUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"stesura AI non disponibile: {exc}"
        ) from exc
    return DraftOut(
        title=draft.title, description=draft.description, instructions=draft.instructions,
        servings=draft.servings,
        ingredients=[DraftIngredientOut(**vars(i)) for i in draft.ingredients],
        cost=draft.cost,
    )
