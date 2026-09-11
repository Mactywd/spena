import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import require_session
from app.schemas.cooking import CookRequest, CookResultOut
from app.services.cooking import Transition, cook

router = APIRouter(
    prefix="/api/v1/recipes", tags=["cooking"], dependencies=[Depends(require_session)]
)


@router.post("/{recipe_id}/cook", response_model=CookResultOut,
             status_code=status.HTTP_201_CREATED)
async def cook_recipe(
    recipe_id: uuid.UUID, payload: CookRequest,
    session: AsyncSession = Depends(get_session),
) -> CookResultOut:
    transitions = [
        Transition(pantry_item_id=t.pantry_item_id, to_status=t.to_status, restock=t.restock)
        for t in payload.transitions
    ]
    try:
        event = await cook(
            session, recipe_id=recipe_id, servings=payload.servings, transitions=transitions
        )
        await session.commit()
    except KeyError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ricetta o voce inesistente") from exc

    return CookResultOut(
        event_id=event.id,
        updated=len(event.snapshot["transitions"]),
        restocked=event.snapshot["restocked"],
    )
