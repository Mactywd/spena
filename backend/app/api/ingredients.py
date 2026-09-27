import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session, is_missing_reference, is_unique_violation
from app.core.security import require_session
from app.domain.rules import IngredientKind
from app.repositories.ingredients import (
    add_alias,
    create_ingredient,
    find_by_name,
    search_ingredients,
)
from app.schemas.ingredient import AliasCreate, IngredientCreate, IngredientOut

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
