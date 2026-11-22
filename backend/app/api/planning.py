"""La chat di pianificazione (spec 2026-11-12 §5.2; piano 6c, Task 9): la conversazione da
riaprire o nuova, il posto di partenza, i messaggi in streaming (lo stesso
`start_turn_stream` della chat del piatto) e «Metti nella settimana» con il seguito."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.meal_chat import start_turn_stream
from app.api.meals import meals_out
from app.api.refusals import meal_refusal_response
from app.core.config import get_settings
from app.core.db import get_session, get_session_factory
from app.core.security import require_session
from app.db.models.conversation import Conversation, ConversationKind
from app.db.models.planning import MealProposal, ProposalKind
from app.domain.meal_chat import FailureKind, failure_notice
from app.domain.rules import today_in_pantry
from app.repositories.conversations import create_planning, set_focus
from app.schemas.meal_chat import ChatMessageIn
from app.schemas.planning import (
    PlaceIn,
    PlaceOut,
    PlanningChatOut,
    PlanningCreateIn,
    PlanningFocusIn,
)
from app.services.chat_turns import TurnRegistry, get_turn_registry
from app.services.claude.client import ClaudeClient, claude_configured, get_claude_client
from app.services.meals import MealRefusal
from app.services.planning import (
    PlanningRefusal,
    PlanningRefusalCode,
    place_proposal,
    planning_to_reopen,
)
from app.services.planning_chat import planning_view, run_planning_turn
from app.services.recipe_jobs import RecipeJobs, get_recipe_jobs, recipe_run, wants_recipe

router = APIRouter(
    prefix="/api/v1/planning", tags=["planning"], dependencies=[Depends(require_session)]
)

NO_CONVERSATION = "conversazione inesistente"
NO_PROPOSAL = "proposta inesistente"


async def _conversation_or_404(session: AsyncSession, conversation_id: uuid.UUID) -> Conversation:
    """Una conversazione di pianificazione: quella di un piatto qui non esiste."""
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or conversation.kind != ConversationKind.PLANNING.value:
        raise HTTPException(404, NO_CONVERSATION)
    return conversation


async def _view(
    session: AsyncSession, registry: TurnRegistry, conversation: Conversation | None
) -> PlanningChatOut:
    replying = conversation is not None and registry.running(conversation.id)
    return await planning_view(session, conversation, replying=replying, now=datetime.now(UTC))


@router.get("/current", response_model=PlanningChatOut)
async def get_current(
    session: AsyncSession = Depends(get_session),
    registry: TurnRegistry = Depends(get_turn_registry),
):
    """«Pianifica con Claude»: l'ultima conversazione non conclusa (`planning_to_reopen`,
    decisione 26), altrimenti la vista vuota, da cui il primo messaggio ne apre una nuova."""
    conversation = await planning_to_reopen(session, today_in_pantry(datetime.now(UTC)))
    return await _view(session, registry, conversation)


@router.post("/conversations", response_model=PlanningChatOut, status_code=201)
async def post_conversation(
    body: PlanningCreateIn,
    session: AsyncSession = Depends(get_session),
    registry: TurnRegistry = Depends(get_turn_registry),
):
    """«Nuova», anche con il posto di partenza (decisione 25)."""
    focus = (body.focus.day, body.focus.slot) if body.focus is not None else None
    conversation = await create_planning(session, focus=focus)
    await session.commit()
    return await _view(session, registry, conversation)


@router.get("/conversations/{conversation_id}", response_model=PlanningChatOut)
async def get_conversation(
    conversation_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    registry: TurnRegistry = Depends(get_turn_registry),
):
    conversation = await _conversation_or_404(session, conversation_id)
    return await _view(session, registry, conversation)


@router.patch("/conversations/{conversation_id}", response_model=PlanningChatOut)
async def patch_conversation(
    conversation_id: uuid.UUID,
    body: PlanningFocusIn,
    session: AsyncSession = Depends(get_session),
    registry: TurnRegistry = Depends(get_turn_registry),
):
    """Il posto di partenza, cambiato o tolto (`{"focus": null}`)."""
    conversation = await _conversation_or_404(session, conversation_id)
    focus = (body.focus.day, body.focus.slot) if body.focus is not None else None
    await set_focus(session, conversation, focus)
    await session.commit()
    return await _view(session, registry, conversation)


@router.post("/conversations/{conversation_id}/messages")
async def post_message(
    conversation_id: uuid.UUID,
    body: ChatMessageIn,
    session: AsyncSession = Depends(get_session),
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    client: ClaudeClient = Depends(get_claude_client),
    registry: TurnRegistry = Depends(get_turn_registry),
):
    """Un messaggio a Claude: la risposta arriva in SSE, come nella chat del piatto."""
    conversation = await _conversation_or_404(session, conversation_id)
    return await start_turn_stream(
        session, registry, client, factory, conversation=conversation, body=body,
        run=run_planning_turn, settings=get_settings(),
    )


@router.post("/proposals/{proposal_id}/place", response_model=PlaceOut)
async def place(
    proposal_id: uuid.UUID,
    body: PlaceIn | None = None,
    session: AsyncSession = Depends(get_session),
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    client: ClaudeClient = Depends(get_claude_client),
    registry: TurnRegistry = Depends(get_turn_registry),
    jobs: RecipeJobs = Depends(get_recipe_jobs),
):
    """«Metti nella settimana» (decisioni 12–14). Un rifiuto è un 409 con la chat com'è, e
    per i posti occupati con gli occupanti, da confermare con `replace`. Dopo il `commit`
    le ricette dei pasti ufficiali entrano nella coda (decisione 15); senza Claude i pasti
    entrano lo stesso, con l'avviso e senza «in preparazione». La risposta porta
    `follow_up`, il messaggio che il telefono manda a Claude per la scheda dei cambi."""
    replace = body.replace if body is not None else False
    found = await session.get(MealProposal, proposal_id)
    if found is None:
        raise HTTPException(404, NO_PROPOSAL)
    conversation_id = found.conversation_id
    now = datetime.now(UTC)
    try:
        placement = await place_proposal(
            session, proposal_id, replace=replace, now=now, today=today_in_pantry(now)
        )
    except PlanningRefusal as refusal:
        # gli occupanti si serializzano prima del rollback, che li scade
        occupants = (
            await meals_out(
                session, refusal.occupants, today_in_pantry(now), jobs.live_ids()
            )
            if refusal.code == PlanningRefusalCode.SLOTS_TAKEN
            else None
        )
        await session.rollback()
        chat = await _view(session, registry, await session.get(Conversation, conversation_id))
        content: dict[str, object] = {
            "code": refusal.code.value,
            "detail": refusal.message,
            "chat": chat.model_dump(mode="json"),
        }
        if occupants is not None:
            content["occupants"] = [o.model_dump(mode="json") for o in occupants]
        return JSONResponse(status_code=409, content=content)
    except MealRefusal as exc:
        # una corsa: un posto preso fra il controllo e la scrittura, con le prime righe già
        # scritte. Il rollback le toglie tutte.
        response = meal_refusal_response(exc)
        await session.rollback()
        return response
    except KeyError:
        await session.rollback()
        raise HTTPException(404, NO_PROPOSAL) from None
    except Exception:
        await session.rollback()
        raise

    configured = claude_configured()
    queued: list[uuid.UUID] = []
    if placement.proposal.kind == ProposalKind.OFFICIAL.value:
        for meal in placement.meals:
            if not wants_recipe(meal):
                meal.recipe_requested_at = None
            elif configured:
                queued.append(meal.id)
            else:
                # decisione 15: senza Claude niente «in preparazione», l'avviso subito
                meal.recipe_requested_at = None
                meal.recipe_notice = failure_notice(FailureKind.NOT_CONFIGURED, None, now)
        await session.flush()
    meals = await meals_out(
        session, placement.meals, today_in_pantry(now), jobs.live_ids() | frozenset(queued)
    )
    chat = await _view(session, registry, await session.get(Conversation, conversation_id))
    await session.commit()
    # Dopo il commit nessuna lettura: la coda parte al primo `await` e usa le sue sessioni.
    if queued:
        jobs.enqueue(
            queued,
            conversation_id,
            recipe_run(
                factory, client, timeout_seconds=get_settings().claude_reply_timeout_seconds
            ),
        )
    return PlaceOut(chat=chat, meals=meals, follow_up=placement.follow_up)
