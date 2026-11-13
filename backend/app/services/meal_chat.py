"""Il giro della chat del piatto: un messaggio di Mattia → una risposta di Claude (spec
2026-11-12 §5.3, §6, §9), e la vista della chat che la `GET` restituisce.

**La cronologia si ricostruisce dai messaggi salvati in spena, non dalle sessioni
dell'SDK** (decisione 9). Ogni giro è una `query()` nuova: in testa al prompt ci sono il
contesto (oggi, il pasto, la ricetta com'è adesso) e gli ultimi `HISTORY_MESSAGES`
messaggi inviati, con le righe delle loro modifiche e il loro «annullata». Così un
`up -d --build` del container non fa dimenticare niente, e non serve un volume per le
sessioni dell'SDK.

**Il giro non dipende dalla richiesta** (decisione 11). Gira in un task del registro
(`app.services.chat_turns`), con le sue sessioni aperte da `session_factory`, e manda
quello che succede a `emit`. Se il telefono si blocca a metà risposta, chi legge se ne
va e il giro finisce lo stesso: la risposta si trova riaprendo il piatto. Per questo un
giro non lascia mai il messaggio `pending`: o `sent` con la risposta, o `failed` con
l'avviso.

Le modifiche che `write_recipe` scrive sono committate una per una dallo strumento (§9: le
scritture sono atomiche): restano anche se poi il giro fallisce, e hanno il loro «Annulla».
"""

import asyncio
import logging
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db.models.conversation import (
    Conversation,
    ConversationMessage,
    MessageRole,
    MessageStatus,
)
from app.db.models.meal import Meal
from app.db.models.recipe_change import RecipeChange
from app.domain.meal_chat import (
    DISH_EFFORT,
    DISH_MAX_TURNS,
    HISTORY_MESSAGES,
    FailureKind,
    can_chat,
    failure_notice,
    pending_is_stale,
)
from app.domain.meals import MealSlot
from app.domain.rules import today_in_pantry
from app.repositories.conversations import (
    changes_of,
    dish_conversation,
    latest_turn,
    messages_of,
)
from app.repositories.llm_calls import record_llm_call
from app.repositories.meals import get_meal
from app.repositories.recipes import get_recipe
from app.schemas.meal_chat import ChatMessageOut, DishChatOut, HighlightOut, RecipeChangeOut
from app.services.claude.client import (
    ClaudeClient,
    ClaudeFailure,
    TextDelta,
    TurnFailed,
    TurnFinished,
    claude_configured,
)
from app.services.claude.prompts import (
    DishContext,
    HistoryItem,
    dish_system_prompt,
    render_turn_prompt,
)
from app.services.claude.tools import TurnContext, dish_tools
from app.services.llm import LlmCallSite, LlmUsage
from app.services.meal_recipes import change_is_undoable
from app.services.utensils import utensils_prompt_block

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatEvent:
    """Un evento del giro, come lo scrive lo stream SSE: `data` è già JSON."""

    name: Literal["delta", "change", "done", "error"]
    data: dict[str, Any]


Emit = Callable[[ChatEvent], Awaitable[None]]


# --- la vista ----------------------------------------------------------------------------


def change_line(change: RecipeChange) -> str:
    """La riga di una modifica, come la legge Claude nella cronologia (decisione 15)."""
    verb = "scritta" if change.created_recipe else "aggiornata"
    line = f"Ricetta {verb}: {change.summary}"
    if change.undone_at is not None:
        line += " — annullata"
    return line


def _changes_by_message(
    messages: list[ConversationMessage], changes: list[RecipeChange]
) -> dict[uuid.UUID, list[RecipeChange]]:
    """Le modifiche di un giro stanno sotto la risposta di Claude, o sotto il messaggio di
    Mattia se la risposta non c'è. Una modifica senza giro (il giro tolto da «Riprova») non
    ha dove stare."""
    reply_of = {
        m.reply_to_id: m.id
        for m in messages
        if m.role == MessageRole.ASSISTANT.value and m.reply_to_id is not None
    }
    groups: dict[uuid.UUID, list[RecipeChange]] = defaultdict(list)
    for change in changes:
        if change.turn_message_id is None:
            continue
        groups[reply_of.get(change.turn_message_id, change.turn_message_id)].append(change)
    return groups


def _change_out(change: RecipeChange, undoable: bool) -> RecipeChangeOut:
    return RecipeChangeOut(
        id=change.id,
        summary=change.summary,
        created_recipe=change.created_recipe,
        undone=change.undone_at is not None,
        undoable=undoable,
    )


async def change_out(session: AsyncSession, change: RecipeChange) -> RecipeChangeOut:
    return _change_out(change, await change_is_undoable(session, change))


def _repair_orphans(messages: list[ConversationMessage], now: datetime) -> bool:
    """Un messaggio rimasto in attesa oltre il tempo massimo, senza un giro vivo, conta come
    interrotto (decisione 12): il container è ripartito a metà risposta."""
    timeout = get_settings().claude_reply_timeout_seconds
    repaired = False
    for message in messages:
        if message.status == MessageStatus.PENDING.value and pending_is_stale(
            message.created_at, now, timeout
        ):
            message.status = MessageStatus.FAILED.value
            message.failure = FailureKind.INTERRUPTED.value
            message.notice = failure_notice(FailureKind.INTERRUPTED, None, now)
            repaired = True
    return repaired


async def dish_chat_view(
    session: AsyncSession, meal: Meal, *, replying: bool, now: datetime
) -> DishChatOut:
    """La chat di un pasto com'è adesso. `replying` dice se il registro ha un giro vivo:
    senza, un'attesa troppo lunga si mostra (e si scrive, con un `commit`) interrotta."""
    ready = claude_configured()
    notice = None if ready else failure_notice(FailureKind.NOT_CONFIGURED, None, now)
    conversation = await dish_conversation(session, meal.id)
    if conversation is None:
        return DishChatOut(
            meal_id=meal.id, conversation_id=None, messages=[], replying=replying,
            highlight=None, claude_ready=ready, claude_notice=notice,
        )
    messages = await messages_of(session, conversation.id)
    if not replying and _repair_orphans(messages, now):
        await session.commit()
    changes = await changes_of(session, conversation.id)
    undoable = {c.id: await change_is_undoable(session, c) for c in changes}
    groups = _changes_by_message(messages, changes)
    out = [
        ChatMessageOut(
            id=m.id,
            role=m.role,  # type: ignore[arg-type]
            text=m.text,
            status=m.status,  # type: ignore[arg-type]
            notice=m.notice,
            created_at=m.created_at,
            changes=[_change_out(c, undoable[c.id]) for c in groups.get(m.id, [])],
        )
        for m in messages
    ]

    highlight = None
    turn = await latest_turn(session, conversation.id)
    if turn is not None:
        mine = [c for c in changes if c.turn_message_id == turn.id]
        live = next((c for c in reversed(mine) if undoable[c.id]), None)
        if live is not None:
            highlight = HighlightOut(
                ingredient_ids=[uuid.UUID(i) for i in live.changed["ingredient_ids"]],
                title=live.changed["title"],
                servings=live.changed["servings"],
                instructions=live.changed["instructions"],
                description=live.changed["description"],
            )
    return DishChatOut(
        meal_id=meal.id, conversation_id=conversation.id, messages=out, replying=replying,
        highlight=highlight, claude_ready=ready, claude_notice=notice,
    )


async def _chat_data(session: AsyncSession, meal_id: uuid.UUID | None) -> dict[str, Any] | None:
    meal = await get_meal(session, meal_id) if meal_id is not None else None
    if meal is None:
        return None
    view = await dish_chat_view(session, meal, replying=False, now=datetime.now(UTC))
    return view.model_dump(mode="json")


# --- il giro -----------------------------------------------------------------------------


async def _history(
    session: AsyncSession, conversation_id: uuid.UUID, exclude: uuid.UUID
) -> list[HistoryItem]:
    """Gli ultimi `HISTORY_MESSAGES` messaggi inviati, con le righe delle loro modifiche:
    il filtro prima del limite, così un giro fallito non ruba un posto."""
    messages = await messages_of(session, conversation_id)
    groups = _changes_by_message(messages, await changes_of(session, conversation_id))
    sent = [m for m in messages if m.status == MessageStatus.SENT.value and m.id != exclude]
    return [
        HistoryItem(m.role, m.text, tuple(change_line(c) for c in groups.get(m.id, [])))
        for m in sent[-HISTORY_MESSAGES:]
    ]


async def _close(stream: AsyncIterator[Any]) -> None:
    aclose = getattr(stream, "aclose", None)
    if aclose is None:
        return
    try:
        await aclose()
    except Exception:
        logger.exception("La chiusura dello stream di Claude è fallita")


async def _fail(
    session: AsyncSession,
    lock: asyncio.Lock,
    *,
    message_id: uuid.UUID,
    meal_id: uuid.UUID | None,
    failure: ClaudeFailure,
    record: bool,
    emit: Emit,
) -> None:
    """Il messaggio di Mattia passa a `failed` con l'avviso; Claude è stato chiamato, salvo
    `record` falso, e la chiamata va nelle spese, senza token e senza costo."""
    now = datetime.now(UTC)
    notice = failure_notice(failure.kind, failure.resets_at, now)
    async with lock:
        # una scrittura interrotta a metà lascerebbe la sessione sporca: quello che uno
        # strumento ha già committato resta
        await session.rollback()
        message = await session.get(ConversationMessage, message_id)
        if message is not None:
            message.status = MessageStatus.FAILED.value
            message.failure = failure.kind.value
            message.notice = notice
        if record:
            await record_llm_call(
                session, call_site=LlmCallSite.MEAL_CHAT, usage=LlmUsage(), ok=False
            )
        await session.commit()
        chat = await _chat_data(session, meal_id)
    await emit(ChatEvent("error", {"code": failure.kind.value, "notice": notice, "chat": chat}))


async def _turn(
    session: AsyncSession,
    client: ClaudeClient,
    *,
    conversation_id: uuid.UUID,
    user_message_id: uuid.UUID,
    emit: Emit,
    timeout_seconds: float,
) -> None:
    lock = asyncio.Lock()
    now = datetime.now(UTC)
    message = await session.get(ConversationMessage, user_message_id)
    if (
        message is None
        or message.conversation_id != conversation_id
        or message.status != MessageStatus.PENDING.value
    ):
        logger.warning("Il giro %s non ha un messaggio in attesa: niente da fare", user_message_id)
        return
    conversation = await session.get(Conversation, conversation_id)
    meal_id = conversation.meal_id if conversation is not None else None
    meal = await get_meal(session, meal_id) if meal_id is not None else None
    if meal is None or not can_chat(meal):
        await _fail(
            session, lock, message_id=message.id, meal_id=meal_id,
            failure=ClaudeFailure(FailureKind.INTERRUPTED, None, "il pasto non ha la chat"),
            record=False, emit=emit,
        )
        return

    today = today_in_pantry(now)
    system_prompt = dish_system_prompt(await utensils_prompt_block(session))
    recipe = await get_recipe(session, meal.recipe_id) if meal.recipe_id is not None else None
    context = DishContext(
        today=today, day=meal.day, slot=MealSlot(meal.slot), dish=meal.dish,
        sides=meal.sides, recipe=recipe,
    )
    history = await _history(session, conversation_id, exclude=message.id)
    prompt = render_turn_prompt(context, history, message.text)

    async def on_change(change: RecipeChange) -> None:
        # chiamata da `write_recipe` dopo il suo commit, con `ctx.lock` già preso
        out = await change_out(session, change)
        await emit(ChatEvent("change", {"change": out.model_dump(mode="json")}))

    ctx = TurnContext(
        session=session, lock=lock, today=today, meal_id=meal.id,
        conversation_id=conversation_id, turn_message_id=message.id, on_change=on_change,
    )

    deltas: list[str] = []
    outcome: TurnFinished | ClaudeFailure | None = None
    stream = client.run(
        system_prompt=system_prompt,
        prompt=prompt,
        tools=dish_tools(ctx),
        effort=DISH_EFFORT,
        max_turns=DISH_MAX_TURNS,
    )
    timer = asyncio.timeout(timeout_seconds)
    try:
        async with timer:
            async for event in stream:
                if isinstance(event, TextDelta):
                    deltas.append(event.text)
                    await emit(ChatEvent("delta", {"text": event.text}))
                elif isinstance(event, TurnFinished):
                    outcome = event
                    break
                elif isinstance(event, TurnFailed):
                    outcome = event.failure
                    break
    except TimeoutError:
        if timer.expired():
            outcome = ClaudeFailure(FailureKind.TIMEOUT, None, "tempo massimo")
        else:
            logger.exception("Il giro della chat %s è caduto", conversation_id)
            outcome = ClaudeFailure(FailureKind.UNAVAILABLE, None, "eccezione")
    except Exception:
        # `SdkClaudeClient` traduce solo gli errori dell'SDK: il resto arriva qui
        logger.exception("Il giro della chat %s è caduto", conversation_id)
        outcome = ClaudeFailure(FailureKind.UNAVAILABLE, None, "eccezione")
    finally:
        await _close(stream)
    if outcome is None:
        outcome = ClaudeFailure(FailureKind.INTERRUPTED, None, "il flusso è finito senza risultato")

    if isinstance(outcome, ClaudeFailure):
        await _fail(
            session, lock, message_id=message.id, meal_id=meal.id, failure=outcome,
            record=outcome.kind != FailureKind.NOT_CONFIGURED, emit=emit,
        )
        return

    usage = outcome.usage
    async with lock:
        message = await session.get(ConversationMessage, user_message_id)
        assert message is not None
        message.status = MessageStatus.SENT.value
        message.failure = None
        message.notice = None
        session.add(
            ConversationMessage(
                conversation_id=conversation_id,
                role=MessageRole.ASSISTANT.value,
                text=outcome.text or "".join(deltas),
                status=MessageStatus.SENT.value,
                reply_to_id=message.id,
                created_at=datetime.now(UTC),
            )
        )
        await record_llm_call(
            session,
            call_site=LlmCallSite.MEAL_CHAT,
            usage=LlmUsage(
                generation_id=usage.session_id,
                model=usage.model,
                prompt_tokens=usage.input_tokens,
                completion_tokens=usage.output_tokens,
                cost_usd=None,
            ),
            ok=True,
        )
        await session.commit()
        chat = await _chat_data(session, meal.id)
    await emit(ChatEvent("done", {"chat": chat}))


async def _fail_after_crash(
    session_factory: async_sessionmaker[AsyncSession],
    user_message_id: uuid.UUID,
    emit: Emit,
) -> None:
    """Un'eccezione che il giro non ha saputo gestire: il messaggio non resta `pending`.
    Con una sessione nuova, perché quella del giro può essere rotta."""
    now = datetime.now(UTC)
    notice = failure_notice(FailureKind.UNAVAILABLE, None, now)
    failed = False
    chat = None
    try:
        async with session_factory() as session:
            message = await session.get(ConversationMessage, user_message_id)
            if message is not None and message.status == MessageStatus.PENDING.value:
                message.status = MessageStatus.FAILED.value
                message.failure = FailureKind.UNAVAILABLE.value
                message.notice = notice
                await session.commit()
                failed = True
                conversation = await session.get(Conversation, message.conversation_id)
                chat = await _chat_data(session, conversation.meal_id if conversation else None)
    except Exception:
        logger.exception("Il messaggio %s non è passato a failed", user_message_id)
        failed = True
    if failed:
        await emit(
            ChatEvent(
                "error",
                {"code": FailureKind.UNAVAILABLE.value, "notice": notice, "chat": chat},
            )
        )


async def run_dish_turn(
    session_factory: async_sessionmaker[AsyncSession],
    client: ClaudeClient,
    *,
    conversation_id: uuid.UUID,
    user_message_id: uuid.UUID,
    emit: Emit,
    timeout_seconds: float,
) -> None:
    """Un giro: rilegge il messaggio in attesa, chiama Claude con gli strumenti di spena,
    e lascia il messaggio `sent` con la risposta (evento `done`) o `failed` con l'avviso
    (evento `error`). I pezzi di testo escono come `delta`, le modifiche della ricetta come
    `change` appena committate."""
    try:
        async with session_factory() as session:
            await _turn(
                session, client, conversation_id=conversation_id,
                user_message_id=user_message_id, emit=emit, timeout_seconds=timeout_seconds,
            )
    except Exception:
        logger.exception("Il giro della chat %s è caduto", conversation_id)
        await _fail_after_crash(session_factory, user_message_id, emit)
