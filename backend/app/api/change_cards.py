"""Le schede dei cambi (spec 2026-11-12 §6.2): leggere, aggiungere una riga a mano,
applicare, scartare. Un rifiuto è un 409 con la scheda com'è adesso accanto."""

import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import require_session
from app.db.models.change_card import CardStatus
from app.schemas.change_card import (
    CardApplyIn,
    CardRowIn,
    ChangeCardOut,
    card_out,
)
from app.services.change_cards import (
    SUPERSEDED_SENTENCE,
    CardRefusal,
    CardRefusalCode,
    RowOverride,
    add_row,
    apply_card,
    cards_with_status,
    discard_card,
    get_card,
)

router = APIRouter(
    prefix="/api/v1/change-cards",
    tags=["change-cards"],
    dependencies=[Depends(require_session)],
)

SENTENCES = {
    CardRefusalCode.ALREADY_APPLIED: "La scheda era già applicata.",
    CardRefusalCode.DISCARDED: "La scheda è stata scartata.",
    CardRefusalCode.SUPERSEDED: SUPERSEDED_SENTENCE,
    CardRefusalCode.LIST_ONLY: "Per una bozza la scheda ha solo le righe della lista.",
    CardRefusalCode.ROW_EXISTS: "Questa voce è già nella scheda.",
    CardRefusalCode.NOT_IN_PANTRY: "La voce non è più in dispensa.",
    CardRefusalCode.NOT_FOOD: "Le voci non alimentari non vanno nella scheda.",
}


async def _refuse(
    session: AsyncSession, card_id: uuid.UUID, exc: CardRefusal
) -> JSONResponse:
    await session.rollback()
    card = await get_card(session, card_id)
    body: dict[str, object] = {
        "code": exc.code.value,
        "detail": SENTENCES.get(exc.code, exc.message),
        "card": None,
    }
    if card is not None:
        body["card"] = (await card_out(session, card)).model_dump(mode="json")
    return JSONResponse(status_code=409, content=body)


async def _card_or_404(session: AsyncSession, card_id: uuid.UUID):
    card = await get_card(session, card_id)
    if card is None:
        raise HTTPException(404, "scheda inesistente")
    return card


@router.get("", response_model=list[ChangeCardOut])
async def list_cards(
    status: Literal["proposed", "applied", "discarded"] = "proposed",
    session: AsyncSession = Depends(get_session),
) -> list[ChangeCardOut]:
    cards = await cards_with_status(session, CardStatus(status))
    return [await card_out(session, c) for c in cards]


@router.get("/{card_id}", response_model=ChangeCardOut)
async def get_one_card(
    card_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ChangeCardOut:
    return await card_out(session, await _card_or_404(session, card_id))


@router.post("/{card_id}/rows", response_model=ChangeCardOut)
async def post_row(
    card_id: uuid.UUID, payload: CardRowIn, session: AsyncSession = Depends(get_session)
):
    card = await _card_or_404(session, card_id)
    try:
        card = await add_row(
            session, card, pantry_item_id=payload.pantry_item_id, raw_text=payload.raw_text
        )
    except CardRefusal as exc:
        return await _refuse(session, card_id, exc)
    out = await card_out(session, card)
    await session.commit()
    return out


@router.post("/{card_id}/apply", response_model=ChangeCardOut)
async def post_apply(
    card_id: uuid.UUID, payload: CardApplyIn, session: AsyncSession = Depends(get_session)
):
    await _card_or_404(session, card_id)
    overrides = [RowOverride(r.id, r.checked, r.to_status) for r in payload.rows]
    try:
        card = await apply_card(session, card_id, overrides)
    except CardRefusal as exc:
        return await _refuse(session, card_id, exc)
    out = await card_out(session, card)
    await session.commit()
    return out


@router.post("/{card_id}/discard", response_model=ChangeCardOut)
async def post_discard(card_id: uuid.UUID, session: AsyncSession = Depends(get_session)):
    await _card_or_404(session, card_id)
    try:
        card = await discard_card(session, card_id)
    except CardRefusal as exc:
        return await _refuse(session, card_id, exc)
    out = await card_out(session, card)
    await session.commit()
    return out
