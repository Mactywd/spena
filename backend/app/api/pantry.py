import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import require_session
from app.db.models.pantry import PantryItem
from app.domain.rules import Availability
from app.repositories.pantry import (
    add_pantry_item,
    archive_item,
    availability_map,
    list_pantry,
    set_status,
)
from app.schemas.pantry import PantryItemCreate, PantryItemOut, PantryItemPatch

router = APIRouter(
    prefix="/api/v1/pantry", tags=["pantry"], dependencies=[Depends(require_session)]
)


def _to_out(item: PantryItem) -> PantryItemOut:
    return PantryItemOut(
        id=item.id,
        ingredient_id=item.ingredient_id,
        product_id=item.product_id,
        ingredient_name=item.ingredient.name,
        ingredient_category=item.ingredient.category,
        product_name=item.product.name if item.product else None,
        product_brand=item.product.brand if item.product else None,
        status=item.status,
        note=item.note,
        added_at=item.added_at,
    )


@router.get("", response_model=list[PantryItemOut])
async def read_pantry(session: AsyncSession = Depends(get_session)) -> list[PantryItemOut]:
    return [_to_out(item) for item in await list_pantry(session)]


@router.get("/availability", response_model=dict[uuid.UUID, Availability])
async def read_availability(
    session: AsyncSession = Depends(get_session),
) -> dict[uuid.UUID, Availability]:
    return await availability_map(session)


@router.post("", response_model=PantryItemOut, status_code=status.HTTP_201_CREATED)
async def create(
    payload: PantryItemCreate, session: AsyncSession = Depends(get_session)
) -> PantryItemOut:
    item = await add_pantry_item(
        session, ingredient_id=payload.ingredient_id, product_id=payload.product_id,
        status=payload.status, note=payload.note,
    )
    await session.commit()
    await session.refresh(item, ["ingredient", "product"])
    return _to_out(item)


@router.patch("/{item_id}", response_model=PantryItemOut)
async def patch(
    item_id: uuid.UUID, payload: PantryItemPatch,
    session: AsyncSession = Depends(get_session),
) -> PantryItemOut:
    try:
        if payload.archived:
            item = await archive_item(session, item_id)
        elif payload.status is not None:
            item = await set_status(session, item_id, payload.status)
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "niente da modificare")
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "voce inesistente") from exc
    await session.commit()
    await session.refresh(item, ["ingredient", "product"])
    return _to_out(item)
