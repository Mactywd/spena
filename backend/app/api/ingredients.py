import uuid
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.refusals import refusal_response
from app.core.db import get_session, is_missing_reference, is_unique_violation
from app.core.security import require_session
from app.db.models.ingredient import Ingredient, IngredientAlias
from app.db.models.product import Product
from app.db.models.recipe_import import ImportTerm
from app.domain.rules import IngredientKind
from app.repositories.ingredients import (
    add_alias,
    create_ingredient,
    find_by_name,
    ingredient_usage,
    search_ingredients,
)
from app.schemas.ingredient import (
    AliasCreate,
    AliasMovedOut,
    AliasMoveIn,
    AliasOut,
    IngredientCreate,
    IngredientDetailOut,
    IngredientOut,
    IngredientPatch,
    IngredientUsageOut,
    MergeIn,
    MergeOut,
    ProductBriefOut,
)
from app.services import registry
from app.services.registry import RegistryRefusal

router = APIRouter(
    prefix="/api/v1/ingredients", tags=["ingredients"], dependencies=[Depends(require_session)]
)


@router.get("/search", response_model=list[IngredientOut])
async def search(
    q: str = Query(min_length=1), limit: int = Query(default=10, le=50),
    kind: IngredientKind | None = Query(default=None),
    session: AsyncSession = Depends(get_session),
) -> list[IngredientOut]:
    found = await search_ingredients(session, q, limit, kind=kind)
    return [IngredientOut.model_validate(i) for i in found]


@router.post(
    "", response_model=IngredientOut, status_code=status.HTTP_201_CREATED,
    responses={status.HTTP_409_CONFLICT: {
        "description": "nome già presente: `existing` è l'ingrediente che lo porta",
    }},
)
async def create(
    payload: IngredientCreate, session: AsyncSession = Depends(get_session)
) -> IngredientOut | JSONResponse:
    try:
        ingredient = await create_ingredient(
            session, payload.name, payload.display_name, payload.category
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        # solo un duplicato è un "già presente": qualunque altra violazione è un
        # difetto nostro e deve restare visibile come 500
        if not is_unique_violation(exc):
            raise
        # Il doppione porta con sé l'ingrediente che ha già quel nome (S19): chi
        # crea da «Sistema la spesa» lo aggancia, invece di sentirsi dire «forse
        # esiste con un altro nome» quando esisteva con lo stesso. `detail` resta
        # la stringa di sempre; `existing` è in più, e manca solo se l'omonimo è
        # sparito fra il rifiuto e la lettura.
        existing = await find_by_name(session, payload.name)
        content: dict[str, object] = {"detail": "ingrediente già presente"}
        if existing is not None:
            content["existing"] = IngredientOut.model_validate(existing).model_dump(mode="json")
        return JSONResponse(content, status_code=status.HTTP_409_CONFLICT)
    return IngredientOut.model_validate(ingredient)


@router.post("/{ingredient_id}/aliases", status_code=status.HTTP_201_CREATED)
async def create_alias(
    ingredient_id: uuid.UUID, payload: AliasCreate,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    try:
        await add_alias(session, ingredient_id, payload.alias, payload.source)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        # un ingrediente che non esiste non è un alias duplicato: dirlo male manda
        # l'utente a cercare un doppione che non c'è
        if is_missing_reference(exc):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente") from exc
        if not is_unique_violation(exc):
            raise
        raise HTTPException(status.HTTP_409_CONFLICT, "alias già presente") from exc
    return {"status": "created"}


_CONFLICT = {status.HTTP_409_CONFLICT: {
    "description": "rifiuto dell'anagrafica: `code`, `detail` e l'ostacolo accanto",
}}


def _alias_out(alias: IngredientAlias, terms_by_alias: dict[str, ImportTerm]) -> AliasOut:
    """Un solo posto che traduce un alias in `AliasOut`, usato dalla scheda (GET) e
    dallo spostamento (PATCH alias): la domanda «è la metà di una decisione della
    coda?» la risponde solo `registry.queue_decision_for` (F5), mai una riscrittura
    della regola qui."""
    term = registry.queue_decision_for(alias, terms_by_alias)
    return AliasOut(
        id=alias.id, alias=alias.alias, source=alias.source,
        decided_in_queue=term is not None, term_id=term.id if term is not None else None,
    )


async def _aliases_out(session: AsyncSession, ingredient_id: uuid.UUID) -> list[AliasOut]:
    rows = list(
        (
            await session.execute(
                select(IngredientAlias)
                .where(IngredientAlias.ingredient_id == ingredient_id)
                .order_by(IngredientAlias.alias)
            )
        ).scalars()
    )
    terms_by_alias = await registry.queue_terms_by_alias(session, ingredient_id)
    return [_alias_out(alias, terms_by_alias) for alias in rows]


async def _detail(session: AsyncSession, ingredient_id: uuid.UUID) -> IngredientDetailOut:
    ingredient = await session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente")
    products = list(
        (
            await session.execute(
                select(Product)
                .where(Product.ingredient_id == ingredient_id)
                .order_by(Product.name, Product.id)
            )
        ).scalars()
    )
    usage = await ingredient_usage(session, ingredient_id)
    return IngredientDetailOut(
        **IngredientOut.model_validate(ingredient).model_dump(),
        aliases=await _aliases_out(session, ingredient_id),
        products=[ProductBriefOut.model_validate(product) for product in products],
        usage=IngredientUsageOut(**asdict(usage)),
    )


@router.get("/{ingredient_id}", response_model=IngredientDetailOut)
async def read_one(
    ingredient_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> IngredientDetailOut:
    return await _detail(session, ingredient_id)


@router.patch("/{ingredient_id}", response_model=IngredientDetailOut, responses=_CONFLICT)
async def update(
    ingredient_id: uuid.UUID, payload: IngredientPatch,
    session: AsyncSession = Depends(get_session),
) -> IngredientDetailOut | JSONResponse:
    if payload.name is None and payload.category is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "niente da cambiare")
    try:
        if payload.name is not None:
            await registry.rename_ingredient(
                session, ingredient_id, name=payload.name, display_name=payload.name
            )
        if payload.category is not None:
            await registry.recategorize_ingredient(session, ingredient_id, payload.category)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente") from exc
    except RegistryRefusal as exc:
        response = refusal_response(exc)
        await session.rollback()
        return response
    await session.commit()
    return await _detail(session, ingredient_id)


@router.post("/{ingredient_id}/merge", response_model=MergeOut, responses=_CONFLICT)
async def merge(
    ingredient_id: uuid.UUID, payload: MergeIn,
    session: AsyncSession = Depends(get_session),
) -> MergeOut | JSONResponse:
    """`dry_run` esegue la stessa fusione dentro un SAVEPOINT annullato (§5.1): i numeri
    dell'anteprima sono quelli dell'operazione, per costruzione."""
    try:
        if payload.dry_run:
            merged = await registry.preview_merge(session, ingredient_id, payload.into)
        else:
            merged = await registry.merge_ingredients(session, ingredient_id, payload.into)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente") from exc
    except RegistryRefusal as exc:
        response = refusal_response(exc)
        await session.rollback()
        return response
    if payload.dry_run:
        await session.rollback()
    else:
        await session.commit()
    return MergeOut(dry_run=payload.dry_run, winner_id=payload.into, **asdict(merged))


async def _own_alias(
    session: AsyncSession, ingredient_id: uuid.UUID, alias_id: uuid.UUID
) -> IngredientAlias:
    alias = await session.get(IngredientAlias, alias_id)
    if alias is None or alias.ingredient_id != ingredient_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alias inesistente")
    return alias


@router.patch(
    "/{ingredient_id}/aliases/{alias_id}", response_model=AliasMovedOut, responses=_CONFLICT
)
async def move_one_alias(
    ingredient_id: uuid.UUID, alias_id: uuid.UUID, payload: AliasMoveIn,
    session: AsyncSession = Depends(get_session),
) -> AliasMovedOut | JSONResponse:
    await _own_alias(session, ingredient_id, alias_id)
    try:
        moved = await registry.move_alias(session, alias_id, payload.ingredient_id)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente") from exc
    except RegistryRefusal as exc:
        response = refusal_response(exc)
        await session.rollback()
        return response
    target = await session.get(Ingredient, payload.ingredient_id)
    terms_by_alias = await registry.queue_terms_by_alias(session, payload.ingredient_id)
    out = AliasMovedOut(
        alias=_alias_out(moved, terms_by_alias) if moved is not None else None,
        ingredient=IngredientOut.model_validate(target),
    )
    await session.commit()
    return out


@router.delete(
    "/{ingredient_id}/aliases/{alias_id}", status_code=status.HTTP_204_NO_CONTENT,
    response_model=None, responses=_CONFLICT,
)
async def remove_alias(
    ingredient_id: uuid.UUID, alias_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> Response:
    await _own_alias(session, ingredient_id, alias_id)
    try:
        await registry.delete_alias(session, alias_id)
    except RegistryRefusal as exc:
        response = refusal_response(exc)
        await session.rollback()
        return response
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
