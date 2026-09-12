import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session, is_missing_reference
from app.core.security import require_session
from app.repositories.ingredients import add_alias, create_ingredient, search_ingredients
from app.schemas.ingredient import AliasCreate, IngredientCreate, IngredientOut

router = APIRouter(
    prefix="/api/v1/ingredients", tags=["ingredients"], dependencies=[Depends(require_session)]
)


@router.get("/search", response_model=list[IngredientOut])
async def search(
    q: str = Query(min_length=1), limit: int = Query(default=10, le=50),
    session: AsyncSession = Depends(get_session),
) -> list[IngredientOut]:
    found = await search_ingredients(session, q, limit)
    return [IngredientOut.model_validate(i) for i in found]


@router.post("", response_model=IngredientOut, status_code=status.HTTP_201_CREATED)
async def create(
    payload: IngredientCreate, session: AsyncSession = Depends(get_session)
) -> IngredientOut:
    try:
        ingredient = await create_ingredient(
            session, payload.name, payload.display_name, payload.category
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "ingrediente già presente") from exc
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
        raise HTTPException(status.HTTP_409_CONFLICT, "alias già presente") from exc
    return {"status": "created"}
