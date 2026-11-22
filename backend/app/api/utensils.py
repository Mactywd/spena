"""Gli utensili di cucina (spec 2026-11-12 §4.4, §5.4): l'elenco che Mattia tiene a mano.

Oltre alla schermata, l'elenco lo leggono le bozze e le varianti dell'AI (Task 3) e la
chat dei pasti (piano 3).
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import require_session
from app.repositories.utensils import (
    create_utensil,
    delete_utensil,
    list_utensils,
    update_utensil,
)
from app.schemas.utensil import UtensilIn, UtensilOut, UtensilPatch

router = APIRouter(
    prefix="/api/v1/utensils", tags=["utensils"], dependencies=[Depends(require_session)]
)


@router.get("", response_model=list[UtensilOut])
async def get_utensils(session: AsyncSession = Depends(get_session)) -> list[UtensilOut]:
    return [UtensilOut.model_validate(u) for u in await list_utensils(session)]


@router.post("", response_model=UtensilOut, status_code=201)
async def post_utensil(
    payload: UtensilIn, session: AsyncSession = Depends(get_session)
) -> UtensilOut:
    utensil = await create_utensil(session, name=payload.name, note=payload.note)
    out = UtensilOut.model_validate(utensil)
    await session.commit()
    return out


@router.patch("/{utensil_id}", response_model=UtensilOut)
async def patch_utensil(
    utensil_id: uuid.UUID,
    payload: UtensilPatch,
    session: AsyncSession = Depends(get_session),
) -> UtensilOut:
    # per presenza, non per valore: `{"note": null}` è la cancellazione della nota
    fields = payload.model_dump(include=payload.model_fields_set)
    if not fields:
        raise HTTPException(400, "niente da modificare")
    try:
        utensil = await update_utensil(session, utensil_id, fields)
    except KeyError:
        raise HTTPException(404, "utensile inesistente") from None
    out = UtensilOut.model_validate(utensil)
    await session.commit()
    return out


@router.delete("/{utensil_id}", status_code=204)
async def remove_utensil(
    utensil_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    try:
        await delete_utensil(session, utensil_id)
    except KeyError:
        raise HTTPException(404, "utensile inesistente") from None
    await session.commit()
    return Response(status_code=204)
