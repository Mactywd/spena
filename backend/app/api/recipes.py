import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session, is_missing_reference, is_unique_violation
from app.core.security import require_session
from app.db.models.ingredient import Ingredient
from app.db.models.recipe import Recipe
from app.domain.quantities import (
    ANCHOR_AMOUNT_CEILING,
    decimal_text,
    render_quantity,
    scale_quantity,
    with_qb_tail,
)
from app.domain.rules import (
    Availability,
    IngredientRole,
    is_cookable,
    is_satisfied,
    main_department,
    missing_count,
)
from app.repositories.ingredients import create_ingredient
from app.repositories.pantry import availability_map
from app.repositories.imports import adopt_import_page, owned_by_import
from app.repositories.recipes import (
    IngredientLine,
    NonFoodInRecipe,
    VariantCopy,
    create_recipe,
    get_recipe,
    recipe_categories,
    recipe_origin,
    variant_copy,
    write_recipe_ingredients,
)
from app.schemas.ai import DraftIngredientOut, DraftOut, DraftRequest
from app.schemas.recipe import (
    AnchorOut,
    RecipeCreate,
    RecipeIngredientIn,
    RecipeIngredientOut,
    RecipeOriginOut,
    RecipeOut,
    RecipeReplace,
    RecipeSummaryOut,
    RecipeUpdate,
    SearchModeOut,
)
from app.services.ai_recipes import RecipeDraft, draft_recipe, draft_variant
from app.services.embeddings import (
    EmbeddingUnavailable,
    get_embedding_provider,
    log_degradation_once,
    recipe_document,
)
from app.services.ingredient_match import ingredient_for_new_name
from app.services.llm import LlmUnavailable
from app.services.recipe_search import search_recipes, semantic_search_usable
from app.services.rescale import (
    AnchorRefused,
    anchor_unit,
    is_anchorable,
    resolve_anchor,
    unit_forms,
)

router = APIRouter(
    prefix="/api/v1/recipes", tags=["recipes"], dependencies=[Depends(require_session)]
)

RECIPE_ARCHIVED = "Questa ricetta è stata eliminata: ripristinala prima di modificarla."

# R2: le due regole dei parametri del dettaglio. Il frontend non le viola mai, quindi
# non sono frasi a video: dicono il contratto a chi chiama la rotta a mano
ANCHOR_NEEDS_AMOUNT = "La dose di un ingrediente vuole `anchor` e `amount` insieme."
ONE_SCALE_AT_A_TIME = (
    "Un modo alla volta: le porzioni (`servings`) oppure la dose di un ingrediente "
    "(`anchor` con `amount`)."
)


async def _to_out(
    session: AsyncSession,
    recipe: Recipe,
    servings: int | None = None,
    anchor: tuple[uuid.UUID, Decimal] | None = None,
) -> RecipeOut:
    ingredient_ids = [ri.ingredient_id for ri in recipe.ingredients]
    availability = await availability_map(session, ingredient_ids)

    # Il fattore sta qui e non nel client: la pluralizzazione e l'aritmetica sono
    # logica di dominio, ed è la riga di CLAUDE.md che tiene in piedi la porta a
    # Capacitor. In TypeScript vorrebbe dire spedire il registro delle unità al
    # client e tenere le stesse regole in due lingue.
    factor: Decimal | None = None
    # R2, secondo modo: una dose fissata su una riga. `resolve_anchor` solleva
    # `AnchorRefused` oltre le 50 volte (la rotta ne fa un 422 con la frase); un'ancora
    # che la ricetta non ha più si ignora, come `servings` su una ricetta senza porzioni
    resolved = resolve_anchor(recipe, *anchor) if anchor is not None else None
    if resolved is not None:
        factor = resolved.factor
    # `is not None` e non la verità: che `servings=0` non arrivi mai qui lo garantisce
    # `Query(ge=1)` in fondo a questo file, e una condizione che dipende da un
    # validatore scritto altrove smette di valere il giorno in cui quello cambia
    elif servings is not None and recipe.servings is not None:
        factor = Decimal(servings) / Decimal(recipe.servings)
    if factor == 1:
        factor = None  # chiedere quel che la ricetta dice già è come non chiedere niente

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
            # la riga dell'ancora dice la dose scritta, non il suo ricalcolo: chi
            # ha scritto 150 deve leggere 150, anche quando 150 / 400 × 400 non torna esatto
            value = (
                resolved.amount
                if resolved is not None and ri is resolved.line
                else scale_quantity(ri.quantity_value, factor)
            )
            # «50 g + q.b.» riscalata è «100 g + q.b.»: il q.b. resta scritto accanto,
            # anche sulla riga dell'ancora
            display = with_qb_tail(render_quantity(value, unit_forms(ri)), ri.quantity_text)
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
                anchorable=is_anchorable(ri),
                anchor_unit=anchor_unit(ri) if is_anchorable(ri) else None,
            )
        )
    # il conteggio e il verdetto arrivano da app/domain/rules.py, non da un `sum`
    # qui: ricalcolarli in linea fa sì che il test a tabella difenda una copia che
    # non gira, ed è la metà aggregata della regola del capitolo 7 della spec
    origin = await recipe_origin(session, recipe)
    return RecipeOut(
        id=recipe.id, title=recipe.title, description=recipe.description,
        instructions=recipe.instructions, servings=recipe.servings, source=recipe.source,
        source_ref=recipe.source_ref, ingredients=lines,
        missing=missing_count(requirements), cookable=is_cookable(requirements),
        missing_names=sorted(missing_names),
        main_department=main_department(
            (IngredientRole(ri.role), ri.ingredient.category) for ri in recipe.ingredients
        ),
        image_url=recipe.image_url, prep_minutes=recipe.prep_minutes,
        cook_minutes=recipe.cook_minutes, category=recipe.category, cost=recipe.cost,
        scaled_to=servings if factor is not None and resolved is None else None,
        unscalable_lines=unscalable, dose_lines=dose_lines,
        anchor=(
            AnchorOut(
                ingredient_id=resolved.line.ingredient_id,
                amount=decimal_text(resolved.amount),
                equivalent_servings=(
                    float(resolved.equivalent_servings)
                    if resolved.equivalent_servings is not None
                    else None
                ),
            )
            if resolved is not None
            else None
        ),
        archived_at=recipe.archived_at,
        owned_by_import=await owned_by_import(session, recipe.id),
        derived_from=(
            RecipeOriginOut(id=origin.id, title=origin.title, archived=origin.archived)
            if origin is not None
            else None
        ),
    )


@router.get("/search", response_model=list[RecipeSummaryOut])
async def search(
    response: Response,
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
    # «Mostra altre» nel ricettario (R4). Una lista resta una lista: un frontend
    # vecchio non manda `offset` e vede la prima pagina, come prima.
    offset: int = Query(default=0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[RecipeSummaryOut]:
    # esplicito batte sinonimo: se arrivano entrambi vince quello che la persona ha scelto
    budget = max_missing if max_missing is not None else (0 if only_cookable else None)
    page = await search_recipes(
        session,
        q,
        # per nome, non per posizione: il terzo argomento posizionale era un `bool` e
        # adesso è un `int | None`, e in Python `True == 1` — un `only_cookable`
        # rimasto posizionale diventerebbe in silenzio «al massimo un mancante»
        max_missing=budget,
        limit=limit,
        category=category,
        ingredient_ids=ingredient_id,
        offset=offset,
    )
    # Quante ricette rispondono a questa domanda, prima del limite (T3 Consegna 4). In
    # un'intestazione e non nel corpo: il corpo resta una lista, e una copia vecchia del
    # frontend servita dal service worker continua a leggerla com'era.
    response.headers["X-Total-Count"] = str(page.total)
    if page.total_is_lower_bound:
        # La piscina dei candidati era piena: il numero qui sopra è quanto si è
        # visto, non quante ricette rispondono davvero (R-A, sesta lezione di
        # CLAUDE.md). Il client la legge per dire «almeno N» invece di «N».
        response.headers["X-Total-Count-Lower-Bound"] = "1"
    return [
        RecipeSummaryOut(
            id=r.recipe.id, title=r.recipe.title, description=r.recipe.description,
            source=r.recipe.source, missing=r.missing, cookable=r.cookable,
            missing_names=r.missing_names,
            main_department=r.main_department,
            image_url=r.recipe.image_url, prep_minutes=r.recipe.prep_minutes,
            cook_minutes=r.recipe.cook_minutes, category=r.recipe.category,
            cost=r.recipe.cost,
            archived_at=r.recipe.archived_at,
        )
        for r in page.results
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
    """Le categorie presenti nel ricettario, per il filtro (vedi `recipe_categories`)."""
    return await recipe_categories(session)


@router.get("/{recipe_id}", response_model=RecipeOut)
async def detail(
    recipe_id: uuid.UUID,
    servings: int | None = Query(default=None, ge=1, le=50),
    # R2, secondo modo: la riga (per ingrediente) e la dose scritta, col punto. Tre
    # decimali come la colonna `quantity_value`
    anchor: uuid.UUID | None = Query(default=None),
    amount: Decimal | None = Query(
        default=None, gt=0, lt=ANCHOR_AMOUNT_CEILING, decimal_places=3
    ),
    session: AsyncSession = Depends(get_session),
) -> RecipeOut:
    if (anchor is None) != (amount is None):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, ANCHOR_NEEDS_AMOUNT)
    if anchor is not None and servings is not None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, ONE_SCALE_AT_A_TIME)
    recipe = await get_recipe(session, recipe_id)
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ricetta inesistente")
    try:
        return await _to_out(
            session,
            recipe,
            servings=servings,
            anchor=(anchor, amount) if anchor is not None and amount is not None else None,
        )
    except AnchorRefused as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, exc.sentence) from exc


@router.patch("/{recipe_id}", response_model=RecipeOut)
async def update(
    recipe_id: uuid.UUID, payload: RecipeUpdate, session: AsyncSession = Depends(get_session)
) -> RecipeOut:
    """Cambia quel che `RecipeUpdate` dichiara, e solo i campi mandati davvero.

    `archived` elimina e ripristina (R10 §5). Eliminare prende in carico la pagina
    d'import, come il primo salvataggio di una modifica; ripristinare no, e la pagina
    resta `adopted`. Il costo di una ricetta eliminata non si cambia, come il resto: il
    409 lo dice prima di toccare qualunque cosa.
    """
    recipe = await get_recipe(session, recipe_id)
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ricetta inesistente")
    archived_after = (
        recipe.archived_at is not None if payload.archived is None else payload.archived
    )
    if "cost" in payload.model_fields_set and archived_after:
        raise HTTPException(status.HTTP_409_CONFLICT, RECIPE_ARCHIVED)
    if payload.archived is True:
        # la prima data resta: eliminare due volte non sposta l'eliminazione
        if recipe.archived_at is None:
            recipe.archived_at = datetime.now(UTC)
        await adopt_import_page(session, recipe.id)
    elif payload.archived is False:
        recipe.archived_at = None
    if "cost" in payload.model_fields_set:
        recipe.cost = payload.cost
    await session.commit()
    return await _to_out(session, recipe)


@router.put("/{recipe_id}", response_model=RecipeOut)
async def replace(
    recipe_id: uuid.UUID, payload: RecipeReplace, session: AsyncSession = Depends(get_session)
) -> RecipeOut:
    """La ricetta intera, righe comprese (R10 §5).

    Le righe passano dalla stessa strada della creazione: stessi nomi risolti
    (`_resolve_lines`), stesso imbuto e stesse quantità (`write_recipe_ingredients`),
    stessi errori (`_writing_recipe`). Se la ricetta viene dall'import e la sua pagina è
    ancora `imported`, passa ad `adopted` in questa transazione: da qui l'import non la
    rifà più.
    """
    recipe = await get_recipe(session, recipe_id)
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ricetta inesistente")
    if recipe.archived_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, RECIPE_ARCHIVED)
    await _check_category(session, payload.category, current=recipe.category)
    # il vettore nasce da titolo e descrizione: solo se cambiano va rifatto, e senza
    # modello va a NULL — un vettore del testo vecchio mentirebbe sulla ricetta nuova
    new_text = (payload.title, payload.description) != (recipe.title, recipe.description)
    embedding = await _embedding_for(payload.title, payload.description) if new_text else None
    async with _writing_recipe(session):
        await write_recipe_ingredients(
            session, recipe, await _resolve_lines(session, payload.ingredients)
        )
        recipe.title = payload.title
        recipe.description = payload.description
        recipe.category = payload.category
        recipe.instructions = payload.instructions
        recipe.servings = payload.servings
        recipe.cost = payload.cost
        if new_text:
            recipe.embedding = embedding
        await adopt_import_page(session, recipe.id)
        await session.commit()
    # Le righe appena scritte non hanno l'ingrediente caricato: si rilegge la ricetta
    # intera invece di scoprirlo con un caricamento pigro, che in una sessione async è un
    # MissingGreenlet.
    session.expire(recipe)
    stored = await get_recipe(session, recipe_id)
    return await _to_out(session, stored)


class _RepeatedIngredient(Exception):
    """Due righe del modulo che, risolte, puntano allo stesso ingrediente."""

    def __init__(self, display_name: str) -> None:
        super().__init__(display_name)
        self.display_name = display_name


async def _resolve_lines(
    session: AsyncSession, lines: list[RecipeIngredientIn]
) -> list[IngredientLine]:
    """Da righe del modulo a righe da scrivere: la stessa strada per creare e modificare.

    Le righe che nominano un ingrediente non ancora in anagrafica lo creano qui,
    dentro la stessa transazione della ricetta: se il salvataggio fallisce non resta
    nessun ingrediente orfano. In sequenza e non in parallelo, per lo stesso motivo del
    fan-in dell'import: due righe con lo stesso nome nuovo devono diventare un
    ingrediente, non un doppione.

    Due righe che puntano allo stesso ingrediente — lo stesso id due volte, un nome nuovo
    uguale a una riga agganciata, due nomi che `match_name` porta allo stesso — si
    rifiutano qui, nominandolo (`_RepeatedIngredient`, 409 in `_writing_recipe`): il
    vincolo d'unicità della tabella delle righe le rifiuterebbe comunque, ma non sa dire
    quale ingrediente.
    """
    resolved: list[IngredientLine] = []
    seen: set[uuid.UUID] = set()
    for line in lines:
        ingredient_id = line.ingredient_id
        if ingredient_id is None:
            # `match_name` (dentro `ingredient_for_new_name`) e non una ricerca sul solo
            # nome canonico: se la bozza dice «pomodori» e l'anagrafica ha «pomodoro» con
            # quell'alias, collegarsi è giusto e creare sarebbe un duplicato travestito. La
            # stessa funzione la chiede in anticipo il passo del nome del modulo
            # (`GET /ingredients/match`): l'avviso sul non alimentare dice quel che qui succede
            linked = await ingredient_for_new_name(session, line.name or "")
            if linked is not None:
                ingredient_id = linked.id
            else:
                created = await create_ingredient(
                    session, name=line.name or "",
                    display_name=(line.name or "").capitalize(),
                    category=line.category or "altro",
                )
                ingredient_id = created.id
        if ingredient_id in seen:
            ingredient = await session.get(Ingredient, ingredient_id)
            # un id che non esiste due volte non è un doppione da nominare: lo
            # scopre la scrittura, col suo 404 «inesistente», come prima
            if ingredient is not None:
                raise _RepeatedIngredient(ingredient.display_name)
        seen.add(ingredient_id)
        resolved.append((ingredient_id, line.role, line.quantity_text, line.note))
    return resolved


async def _check_category(
    session: AsyncSession, category: str | None, *, current: str | None = None
) -> None:
    """Una categoria che il ricettario ha già, o nessuna (R10, deviazione 3).

    `current` è quella che la ricetta ha già: tenerla non si rifiuta mai.
    """
    if category is None or category == current:
        return
    if category not in await recipe_categories(session):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"«{category}» non è una categoria del ricettario: scegline una dall'elenco, "
            "o nessuna.",
        )


async def _embedding_for(title: str, description: str | None) -> list[float] | None:
    """L'embedding è un ornamento: se il modello non c'è, la ricetta si salva comunque,
    con il vettore a `NULL`, e `app.cli.reindex` lo ritrova (riempie solo i `NULL`)."""
    try:
        return (await get_embedding_provider().embed_passages([recipe_document(title, description)]))[0]
    except EmbeddingUnavailable as exc:
        log_degradation_once(exc)
        return None


@asynccontextmanager
async def _writing_recipe(session: AsyncSession):
    """Gli errori di una scrittura di ricetta, uguali per la creazione e la modifica."""
    try:
        yield
    except NonFoodInRecipe as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"«{exc.display_name}» non è un alimento: una ricetta non può averlo fra "
            "gli ingredienti. Toglilo dalla riga, poi salva.",
        ) from exc
    except _RepeatedIngredient as exc:
        # un ingrediente creato da una riga precedente se ne va con la ricetta
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"Due righe puntano allo stesso ingrediente, «{exc.display_name}»: "
            "togline una, poi salva.",
        ) from exc
    except IntegrityError as exc:
        await session.rollback()
        # Le due frasi si mostrano così come sono: il modulo fa vedere il `detail` di un
        # rifiuto 4xx (Task 9), quindi dicono il passo dopo invece del solo guasto.
        if is_missing_reference(exc):
            raise HTTPException(
                status.HTTP_404_NOT_FOUND,
                "Un ingrediente agganciato è inesistente, forse unito a un altro: togli "
                "quella riga e aggiungilo di nuovo, poi salva.",
            ) from exc
        # solo un duplicato è un "ripetuto": qualunque altra violazione è un difetto
        # nostro e deve restare visibile come 500, come in shopping.py e pantry.py
        if not is_unique_violation(exc):
            raise
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "Due righe puntano allo stesso ingrediente: togline una, poi salva.",
        ) from exc


@router.post("", response_model=RecipeOut, status_code=status.HTTP_201_CREATED)
async def create(
    payload: RecipeCreate, session: AsyncSession = Depends(get_session)
) -> RecipeOut:
    await _check_category(session, payload.category)
    embedding = await _embedding_for(payload.title, payload.description)
    # R8: un'originale che nel frattempo non c'è più (l'import l'ha rifatta mentre si
    # correggeva la variante) non ferma il salvataggio: la variante nasce senza legame.
    # Rifiutarla butterebbe il lavoro, e dal modulo il legame non si toglie — sarebbe un
    # vicolo cieco. Un'originale eliminata c'è ancora, e tiene il legame.
    # E la variante parte con la foto e i tempi dell'originale (deciso da Mattia il
    # 2026-10-13: «Sì, copiali»): li copia qui il server, perché il modulo non li ha.
    derived_from_id, copied = None, VariantCopy()
    if payload.derived_from_id is not None:
        found = await variant_copy(session, payload.derived_from_id)
        if found is not None:
            derived_from_id, copied = payload.derived_from_id, found
    async with _writing_recipe(session):
        recipe = await create_recipe(
            session, title=payload.title, description=payload.description,
            instructions=payload.instructions, servings=payload.servings,
            source=payload.source, source_ref=payload.source_ref,
            ingredients=await _resolve_lines(session, payload.ingredients),
            embedding=embedding,
            cost=payload.cost,
            category=payload.category,
            derived_from_id=derived_from_id,
            image_url=copied.image_url,
            prep_minutes=copied.prep_minutes,
            cook_minutes=copied.cook_minutes,
        )
        await session.commit()
    stored = await get_recipe(session, recipe.id)
    return await _to_out(session, stored)


def _draft_out(draft: RecipeDraft) -> DraftOut:
    """La bozza come la legge il modulo: la stessa forma per la stesura e per la variante."""
    return DraftOut(
        title=draft.title, description=draft.description, instructions=draft.instructions,
        servings=draft.servings,
        ingredients=[DraftIngredientOut(**vars(i)) for i in draft.ingredients],
        cost=draft.cost,
    )


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
    return _draft_out(draft)


@router.post("/{recipe_id}/ai-variant", response_model=DraftOut)
async def ai_variant(
    recipe_id: uuid.UUID, payload: DraftRequest, session: AsyncSession = Depends(get_session)
) -> DraftOut:
    """Propone una variante della ricetta, e non salva niente (R8).

    La variante si salva con `POST /recipes` e `derived_from_id`: una ricetta nuova,
    mentre questa resta com'è. Un'eliminata risponde come alla modifica (R10): prima
    si ripristina.
    """
    recipe = await get_recipe(session, recipe_id)
    if recipe is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ricetta inesistente")
    if recipe.archived_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, RECIPE_ARCHIVED)
    try:
        draft = await draft_variant(session, recipe, payload.prompt)
    except LlmUnavailable as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, f"variante AI non disponibile: {exc}"
        ) from exc
    return _draft_out(draft)
