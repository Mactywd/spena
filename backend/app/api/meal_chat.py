"""La chat del piatto: leggerla, scrivere un messaggio (la risposta arriva in SSE) e
annullare una modifica della ricetta (spec 2026-11-12 §5, §9)."""

import asyncio
import json
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import Settings, get_settings
from app.core.db import get_session, get_session_factory
from app.core.security import require_session
from app.db.models.conversation import (
    Conversation,
    ConversationKind,
    ConversationMessage,
    MessageRole,
    MessageStatus,
)
from app.db.models.meal import Meal
from app.db.models.recipe_change import RecipeChange
from app.domain.meal_chat import (
    BUSY_NOTICE,
    FailureKind,
    can_chat,
    failure_notice,
    pending_is_stale,
)
from app.repositories.conversations import (
    dish_conversation,
    messages_of,
    move_turn_products,
)
from app.repositories.meals import get_meal
from app.schemas.meal_chat import ChatMessageIn, ChatMessageOut, DishChatOut
from app.services.chat_turns import TurnBusy, TurnRegistry, get_turn_registry
from app.services.claude.client import ClaudeClient, claude_configured, get_claude_client
from app.services.meal_chat import ChatEvent, Emit, dish_chat_view, run_dish_turn
from app.services.meal_recipes import ChangeRefusal, undo_recipe_change

router = APIRouter(
    prefix="/api/v1/meals/{meal_id}/chat",
    tags=["meal-chat"],
    dependencies=[Depends(require_session)],
)

# Dopo tanto silenzio si manda un commento SSE, così nessun proxy chiude la connessione.
PING_SECONDS = 15.0
NO_CHAT_NOTICE = "Questo pasto non ha una chat: è una bozza, è fuori casa o è un avanzo."


def _refuse(status_code: int, code: str, detail: str) -> JSONResponse:
    return JSONResponse(status_code=status_code, content={"code": code, "detail": detail})


async def _meal_or_404(session: AsyncSession, meal_id: uuid.UUID) -> Meal:
    meal = await get_meal(session, meal_id)
    if meal is None:
        raise HTTPException(404, "pasto inesistente")
    return meal


def _sse(name: str, data: dict) -> str:
    return f"event: {name}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("", response_model=DishChatOut)
async def get_chat(
    meal_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    registry: TurnRegistry = Depends(get_turn_registry),
):
    meal = await _meal_or_404(session, meal_id)
    if not can_chat(meal):
        return _refuse(409, "no_chat_here", NO_CHAT_NOTICE)
    conversation = await dish_conversation(session, meal.id)
    replying = conversation is not None and registry.running(conversation.id)
    return await dish_chat_view(session, meal, replying=replying, now=datetime.now(UTC))


async def _stream(events: AsyncIterator[ChatEvent], start: dict) -> AsyncIterator[str]:
    """Legge dal registro. Se chi legge se ne va, Starlette cancella il generatore e il
    `finally` chiude solo l'iteratore del registro: il giro non si cancella mai."""
    pending: asyncio.Future[ChatEvent] | None = None
    try:
        yield _sse("start", start)
        while True:
            pending = asyncio.ensure_future(anext(events))
            while True:
                done, _ = await asyncio.wait({pending}, timeout=PING_SECONDS)
                if done:
                    break
                yield ": ping\n\n"
            try:
                event = pending.result()
            except StopAsyncIteration:
                return  # il giro è finito senza `done` né `error`: il frontend rilegge
            pending = None
            yield _sse(event.name, event.data)
            if event.name in ("done", "error"):
                return
    finally:
        if pending is not None and not pending.done():
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
        aclose = getattr(events, "aclose", None)
        if aclose is not None:
            await aclose()


TurnRun = Callable[..., Awaitable[None]]


async def start_turn_stream(
    session: AsyncSession,
    registry: TurnRegistry,
    client: ClaudeClient,
    session_factory: async_sessionmaker[AsyncSession],
    *,
    conversation: Conversation,
    body: ChatMessageIn,
    run: TurnRun,
    settings: Settings,
) -> Response:
    """Il corpo comune della `POST` dei messaggi, per la chat del piatto e per quella di
    pianificazione: i controlli, il messaggio in attesa, l'avvio del giro e lo stream.

    I controlli arrivano prima di salvare, in quest'ordine (quelli del pasto, 404 e
    `no_chat_here`, li fa prima la rotta): 503 senza Claude, 409 `claude_busy` con un giro
    vivo o un'attesa non ancora orfana. `conversation` può essere ancora da salvare (la
    chat del piatto nasce col primo messaggio): si salva qui, insieme al messaggio, così un
    rifiuto non lascia niente.

    Con `retry_of` (decisione 28) quello che il giro fallito aveva prodotto — proposte,
    schede, modifiche della ricetta — passa al messaggio nuovo **prima** che il fallito si
    cancelli: altrimenti `ON DELETE SET NULL` lo staccherebbe dalla chat.

    `run` è il giro (`run_dish_turn` o `run_planning_turn`): stessa firma, chiamato con
    `session_factory`, `client`, gli id della conversazione e del messaggio, `emit` e il
    tempo massimo delle impostazioni."""
    now = datetime.now(UTC)
    if not claude_configured():
        return _refuse(
            503, "claude_not_configured", failure_notice(FailureKind.NOT_CONFIGURED, None, now)
        )
    timeout = settings.claude_reply_timeout_seconds
    # una conversazione ancora da salvare non ha né giri né messaggi
    saved = conversation.id is not None
    busy = saved and (
        registry.running(conversation.id)
        or any(
            m.status == MessageStatus.PENDING.value
            and not pending_is_stale(m.created_at, now, timeout)
            for m in await messages_of(session, conversation.id)
        )
    )
    if busy:
        return _refuse(409, "claude_busy", BUSY_NOTICE)

    if not saved:
        session.add(conversation)
        await session.flush()
    failed: ConversationMessage | None = None
    if body.retry_of is not None:
        failed = await session.get(ConversationMessage, body.retry_of)
        if (
            failed is None
            or failed.conversation_id != conversation.id
            or failed.role != MessageRole.USER.value
            or failed.status != MessageStatus.FAILED.value
        ):
            await session.rollback()
            raise HTTPException(404, "messaggio inesistente")
    message = ConversationMessage(
        conversation_id=conversation.id,
        role=MessageRole.USER.value,
        text=body.text,
        status=MessageStatus.PENDING.value,
        created_at=datetime.now(UTC),
    )
    session.add(message)
    await session.flush()
    if failed is not None:
        await move_turn_products(session, from_message_id=failed.id, to_message_id=message.id)
        await session.delete(failed)
    await session.commit()

    conversation_id, message_id = conversation.id, message.id
    start = {
        "message": ChatMessageOut(
            id=message.id, role="user", text=message.text, status="pending",
            notice=None, created_at=message.created_at, changes=[],
        ).model_dump(mode="json")
    }

    async def turn(emit: Emit) -> None:
        await run(
            session_factory, client, conversation_id=conversation_id,
            user_message_id=message_id, emit=emit, timeout_seconds=timeout,
        )

    try:
        events = registry.start(conversation_id, turn)
    except TurnBusy:
        # una corsa: un altro giro è partito fra il controllo e qui. Il messaggio salvato
        # non avrebbe un giro: si toglie.
        await session.delete(message)
        await session.commit()
        return _refuse(409, "claude_busy", BUSY_NOTICE)

    return StreamingResponse(
        _stream(events, start),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@router.post("/messages")
async def post_message(
    meal_id: uuid.UUID,
    body: ChatMessageIn,
    session: AsyncSession = Depends(get_session),
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    client: ClaudeClient = Depends(get_claude_client),
    registry: TurnRegistry = Depends(get_turn_registry),
):
    meal = await _meal_or_404(session, meal_id)
    if not can_chat(meal):
        return _refuse(409, "no_chat_here", NO_CHAT_NOTICE)
    # la conversazione nasce col primo messaggio: la salva `start_turn_stream`, dopo i controlli
    conversation = await dish_conversation(session, meal.id) or Conversation(
        kind=ConversationKind.DISH.value, meal_id=meal.id
    )
    return await start_turn_stream(
        session, registry, client, factory, conversation=conversation, body=body,
        run=run_dish_turn, settings=get_settings(),
    )


@router.post("/changes/{change_id}/undo", response_model=DishChatOut)
async def undo_change(
    meal_id: uuid.UUID,
    change_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    registry: TurnRegistry = Depends(get_turn_registry),
):
    meal = await _meal_or_404(session, meal_id)
    change = await session.get(RecipeChange, change_id)
    if change is None or change.meal_id != meal.id:
        raise HTTPException(404, "modifica inesistente")
    # Con un giro vivo, `write_recipe` può scrivere le stesse righe proprio ora: l'interfaccia
    # spegne «Annulla», ma un'altra scheda no. Si rifiuta come un secondo messaggio.
    conversation = await dish_conversation(session, meal.id)
    conversation_id = conversation.id if conversation is not None else None
    if conversation_id is not None and registry.running(conversation_id):
        return _refuse(409, "claude_busy", BUSY_NOTICE)
    try:
        await undo_recipe_change(session, change)
    except ChangeRefusal as refusal:
        await session.rollback()
        return _refuse(409, str(refusal.code), refusal.message)
    await session.commit()
    replying = conversation_id is not None and registry.running(conversation_id)
    return await dish_chat_view(session, meal, replying=replying, now=datetime.now(UTC))
