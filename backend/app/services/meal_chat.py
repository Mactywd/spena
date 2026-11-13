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
Lo stesso vale per le proposte di pasti e le schede dei cambi (piano 6c, decisione 11).

**Un giro solo, due specie** (piano 6c, Task 7). `run_chat_turn` è il giro; un `TurnSpec`
dice che cosa cambia fra la chat del piatto (`DISH_TURN`, qui) e la pianificazione
(`PLANNING_TURN`, in `app.services.planning_chat`): la sezione delle spese, lo sforzo, i
turni, chi può avere un giro, il prompt e gli strumenti, la vista. Il resto — il messaggio
in attesa, la transazione chiusa prima di Claude, il tempo massimo, i fallimenti, la
risposta, gli eventi — è una copia sola (la prima lezione di `CLAUDE.md`).
"""

import asyncio
import logging
import uuid
from collections import defaultdict
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.config import get_settings
from app.db.models.conversation import (
    Conversation,
    ConversationMessage,
    MessageRole,
    MessageStatus,
)
from app.db.models.change_card import CardStatus, ChangeCard
from app.db.models.meal import Meal
from app.db.models.planning import MealProposal, ProposalStatus
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
    cards_of,
    changes_of,
    dish_conversation,
    latest_turn,
    messages_of,
    proposals_of,
)
from app.repositories.llm_calls import record_llm_call
from app.repositories.meals import get_meal
from app.repositories.recipes import get_recipe
from app.schemas.change_card import card_out
from app.schemas.meal_chat import ChatMessageOut, DishChatOut, HighlightOut, RecipeChangeOut
from app.services.claude.client import (
    ClaudeClient,
    ClaudeFailure,
    Effort,
    SdkMcpTool,
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
from app.services.planning import proposal_out
from app.services.utensils import utensils_prompt_block

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ChatEvent:
    """Un evento del giro, come lo scrive lo stream SSE: `data` è già JSON."""

    name: Literal["delta", "change", "proposal", "card", "done", "error"]
    data: dict[str, Any]


Emit = Callable[[ChatEvent], Awaitable[None]]


@dataclass(frozen=True)
class TurnSpec:
    """La specie di un giro: quello che cambia fra la chat del piatto e la pianificazione.

    `allowed` dice se la conversazione può avere un giro adesso (il piatto: il pasto c'è e
    ha la chat); senza, il messaggio fallisce come interrotto e Claude non si chiama.
    `prepare` legge quello che serve e restituisce il prompt di sistema, il prompt del giro
    e gli strumenti costruiti sul `TurnContext`. `view` è la vista della conversazione che
    va negli eventi `done` ed `error` (`None` se non c'è più niente da mostrare).
    """

    call_site: LlmCallSite
    effort: Effort
    max_turns: int
    allowed: Callable[[AsyncSession, Conversation], Awaitable[bool]]
    prepare: Callable[
        [AsyncSession, Conversation, ConversationMessage, TurnContext],
        Awaitable[tuple[str, str, list[SdkMcpTool]]],
    ]
    view: Callable[[AsyncSession, Conversation, bool, datetime], Awaitable[BaseModel | None]]


# --- la vista ----------------------------------------------------------------------------


def change_line(change: RecipeChange) -> str:
    """La riga di una modifica, come la legge Claude nella cronologia (decisione 15)."""
    verb = "scritta" if change.created_recipe else "aggiornata"
    line = f"Ricetta {verb}: {change.summary}"
    if change.undone_at is not None:
        line += " — annullata"
    return line


_PROPOSAL_STATES = {
    ProposalStatus.OPEN.value: "aperta",
    ProposalStatus.PLACED.value: "messa nella settimana",
    ProposalStatus.SUPERSEDED.value: "sostituita",
}
_CARD_STATES = {
    CardStatus.PROPOSED.value: "da applicare",
    CardStatus.APPLIED.value: "applicata",
    CardStatus.DISCARDED.value: "scartata",
}


def proposal_line(proposal: MealProposal) -> str:
    """«Proposta: Frittata; Orata al forno — aperta», nella cronologia di Claude."""
    dishes = "; ".join(row["dish"] for row in proposal.rows)
    return f"Proposta: {dishes} — {_PROPOSAL_STATES[proposal.status]}"


def card_line(card: ChangeCard) -> str:
    """«Scheda dei cambi: ‹titolo› — da applicare», nella cronologia di Claude."""
    return f"Scheda dei cambi: {card.title} — {_CARD_STATES[card.status]}"


TurnProduct = RecipeChange | MealProposal | ChangeCard


def _product_line(product: TurnProduct) -> str:
    if isinstance(product, RecipeChange):
        return change_line(product)
    if isinstance(product, MealProposal):
        return proposal_line(product)
    return card_line(product)


def _by_message[T: TurnProduct](
    messages: list[ConversationMessage], products: list[T]
) -> dict[uuid.UUID, list[T]]:
    """Quello che un giro ha prodotto (modifiche, proposte, schede) sta sotto la risposta di
    Claude, o sotto il messaggio di Mattia se la risposta non c'è. Senza giro (il giro tolto
    da «Riprova» prima della decisione 28) non ha dove stare."""
    reply_of = {
        m.reply_to_id: m.id
        for m in messages
        if m.role == MessageRole.ASSISTANT.value and m.reply_to_id is not None
    }
    groups: dict[uuid.UUID, list[T]] = defaultdict(list)
    for product in products:
        if product.turn_message_id is None:
            continue
        groups[reply_of.get(product.turn_message_id, product.turn_message_id)].append(product)
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


async def repair_orphans(
    session: AsyncSession, conversation_id: uuid.UUID, *, replying: bool, now: datetime
) -> None:
    """Per le viste: senza un giro vivo, un'attesa troppo lunga si scrive interrotta, con
    un `commit`. Con il giro vivo non si tocca niente."""
    if replying:
        return
    if _repair_orphans(await messages_of(session, conversation_id), now):
        await session.commit()


async def chat_messages_out(
    session: AsyncSession, conversation: Conversation, *, now: datetime
) -> list[ChatMessageOut]:
    """I messaggi della conversazione, ognuno con le modifiche, le proposte e le schede del
    suo giro. Una lettura sola: le attese orfane le sistema prima la vista
    (`repair_orphans`), perché solo lei sa se il giro è vivo. `now` è lo stesso istante
    della vista."""
    del now  # la stessa firma delle viste; qui non serve
    messages = await messages_of(session, conversation.id)
    changes = await changes_of(session, conversation.id)
    proposals = await proposals_of(session, conversation.id)
    cards = await cards_of(session, conversation.id)
    change_groups = _by_message(messages, changes)
    proposal_groups = _by_message(messages, proposals)
    card_groups = _by_message(messages, cards)

    out: list[ChatMessageOut] = []
    for m in messages:
        out.append(
            ChatMessageOut(
                id=m.id,
                role=m.role,  # type: ignore[arg-type]
                text=m.text,
                status=m.status,  # type: ignore[arg-type]
                notice=m.notice,
                created_at=m.created_at,
                changes=[await change_out(session, c) for c in change_groups.get(m.id, [])],
                proposals=[
                    await proposal_out(session, p) for p in proposal_groups.get(m.id, [])
                ],
                cards=[await card_out(session, c) for c in card_groups.get(m.id, [])],
            )
        )
    return out


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
    await repair_orphans(session, conversation.id, replying=replying, now=now)
    out = await chat_messages_out(session, conversation, now=now)

    highlight = None
    turn = await latest_turn(session, conversation.id)
    if turn is not None:
        changes = await changes_of(session, conversation.id)
        mine = [c for c in changes if c.turn_message_id == turn.id]
        live = None
        for change in reversed(mine):
            if await change_is_undoable(session, change):
                live = change
                break
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


# --- la cronologia -----------------------------------------------------------------------


async def chat_history(
    session: AsyncSession, conversation_id: uuid.UUID, *, exclude: uuid.UUID | None = None
) -> list[HistoryItem]:
    """Gli ultimi `HISTORY_MESSAGES` messaggi inviati, ognuno con le righe di quello che il
    suo giro ha prodotto (modifiche, proposte, schede, in ordine di tempo): il filtro prima
    del limite, così un giro fallito non ruba un posto. `exclude` è il messaggio del giro;
    il giro della ricetta non ne ha uno (decisione 17)."""
    messages = await messages_of(session, conversation_id)
    products: list[TurnProduct] = [
        *await changes_of(session, conversation_id),
        *await proposals_of(session, conversation_id),
        *await cards_of(session, conversation_id),
    ]
    groups = _by_message(messages, products)
    sent = [m for m in messages if m.status == MessageStatus.SENT.value and m.id != exclude]
    return [
        HistoryItem(
            m.role,
            m.text,
            tuple(
                _product_line(p)
                for p in sorted(groups.get(m.id, []), key=lambda p: p.created_at)
            ),
        )
        for m in sent[-HISTORY_MESSAGES:]
    ]


# --- il giro -----------------------------------------------------------------------------


async def _chat_data(
    session: AsyncSession, spec: TurnSpec, conversation_id: uuid.UUID
) -> dict[str, Any] | None:
    # riletta qui: dopo il flusso gli oggetti caricati prima possono essere scaduti
    conversation = await session.get(Conversation, conversation_id, populate_existing=True)
    if conversation is None:
        return None
    view = await spec.view(session, conversation, False, datetime.now(UTC))
    return None if view is None else view.model_dump(mode="json")


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
    spec: TurnSpec,
    *,
    message_id: uuid.UUID,
    conversation_id: uuid.UUID,
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
            await record_llm_call(session, call_site=spec.call_site, usage=LlmUsage(), ok=False)
        await session.commit()
        chat = await _chat_data(session, spec, conversation_id)
    await emit(ChatEvent("error", {"code": failure.kind.value, "notice": notice, "chat": chat}))


async def _turn(
    session: AsyncSession,
    client: ClaudeClient,
    spec: TurnSpec,
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
    # Da qui si usano solo questi id: un SAVEPOINT annullato dentro `write_recipe` (un
    # tempo massimo a metà scrittura, un errore del database) scade gli oggetti caricati,
    # e rileggerne uno dopo il flusso sarebbe un MissingGreenlet.
    message_id = message.id
    conversation = await session.get(Conversation, conversation_id)
    if conversation is None or not await spec.allowed(session, conversation):
        await _fail(
            session, lock, spec, message_id=message_id, conversation_id=conversation_id,
            failure=ClaudeFailure(
                FailureKind.INTERRUPTED, None, "la conversazione non può avere un giro"
            ),
            record=False, emit=emit,
        )
        return

    async def on_change(change: RecipeChange) -> None:
        # chiamata da `write_recipe` dopo il suo commit, con `ctx.lock` già preso
        out = await change_out(session, change)
        await emit(ChatEvent("change", {"change": out.model_dump(mode="json")}))

    async def on_proposal(proposal: MealProposal) -> None:
        # chiamata da `propose_meals` dopo il suo commit, con `ctx.lock` già preso
        out = await proposal_out(session, proposal)
        await emit(ChatEvent("proposal", {"proposal": out.model_dump(mode="json")}))

    async def on_card(card: ChangeCard) -> None:
        # chiamata da `propose_changes` dopo il suo commit, con `ctx.lock` già preso
        out = await card_out(session, card)
        await emit(ChatEvent("card", {"card": out.model_dump(mode="json")}))

    ctx = TurnContext(
        session=session, lock=lock, today=today_in_pantry(now), meal_id=conversation.meal_id,
        conversation_id=conversation_id, turn_message_id=message_id, on_change=on_change,
        on_proposal=on_proposal, on_card=on_card,
    )
    system_prompt, prompt, tools = await spec.prepare(session, conversation, message, ctx)
    # Le letture sono finite: si chiude la transazione, o la sessione resterebbe «idle in
    # transaction» (con i lock di lettura sulle tabelle) per tutto il tempo di Claude.
    # Non c'è niente in sospeso, e `expire_on_commit=False` tiene gli oggetti caricati.
    await session.commit()

    deltas: list[str] = []
    outcome: TurnFinished | ClaudeFailure | None = None
    stream = client.run(
        system_prompt=system_prompt,
        prompt=prompt,
        tools=tools,
        effort=spec.effort,
        max_turns=spec.max_turns,
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
            session, lock, spec, message_id=message_id, conversation_id=conversation_id,
            failure=outcome, record=outcome.kind != FailureKind.NOT_CONFIGURED, emit=emit,
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
                reply_to_id=message_id,
                created_at=datetime.now(UTC),
            )
        )
        await record_llm_call(
            session,
            call_site=spec.call_site,
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
        chat = await _chat_data(session, spec, conversation_id)
    await emit(ChatEvent("done", {"chat": chat}))


async def _fail_after_crash(
    session_factory: async_sessionmaker[AsyncSession],
    spec: TurnSpec,
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
                conversation_id = message.conversation_id
                await session.commit()
                failed = True
                chat = await _chat_data(session, spec, conversation_id)
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


async def run_chat_turn(
    session_factory: async_sessionmaker[AsyncSession],
    client: ClaudeClient,
    *,
    conversation_id: uuid.UUID,
    user_message_id: uuid.UUID,
    emit: Emit,
    timeout_seconds: float,
    spec: TurnSpec,
) -> None:
    """Un giro: rilegge il messaggio in attesa, chiama Claude con il prompt e gli strumenti
    della sua specie, e lascia il messaggio `sent` con la risposta (evento `done`) o
    `failed` con l'avviso (evento `error`). I pezzi di testo escono come `delta`; le
    modifiche della ricetta come `change`, le proposte come `proposal` e le schede come
    `card`, appena committate."""
    try:
        async with session_factory() as session:
            await _turn(
                session, client, spec, conversation_id=conversation_id,
                user_message_id=user_message_id, emit=emit, timeout_seconds=timeout_seconds,
            )
    except Exception:
        logger.exception("Il giro della chat %s è caduto", conversation_id)
        await _fail_after_crash(session_factory, spec, user_message_id, emit)


# --- la chat del piatto --------------------------------------------------------------------


async def _dish_meal(session: AsyncSession, conversation: Conversation) -> Meal | None:
    return await get_meal(session, conversation.meal_id) if conversation.meal_id else None


async def _dish_allowed(session: AsyncSession, conversation: Conversation) -> bool:
    meal = await _dish_meal(session, conversation)
    return meal is not None and can_chat(meal)


async def _dish_prepare(
    session: AsyncSession,
    conversation: Conversation,
    message: ConversationMessage,
    ctx: TurnContext,
) -> tuple[str, str, list[SdkMcpTool]]:
    meal = await _dish_meal(session, conversation)
    assert meal is not None  # `_dish_allowed` l'ha appena trovato
    system_prompt = dish_system_prompt(await utensils_prompt_block(session))
    recipe = await get_recipe(session, meal.recipe_id) if meal.recipe_id is not None else None
    context = DishContext(
        today=ctx.today, day=meal.day, slot=MealSlot(meal.slot), dish=meal.dish,
        sides=meal.sides, recipe=recipe,
    )
    history = await chat_history(session, conversation.id, exclude=message.id)
    return system_prompt, render_turn_prompt(context, history, message.text), dish_tools(ctx)


async def _dish_view(
    session: AsyncSession, conversation: Conversation, replying: bool, now: datetime
) -> DishChatOut | None:
    meal = await _dish_meal(session, conversation)
    if meal is None:
        return None
    return await dish_chat_view(session, meal, replying=replying, now=now)


DISH_TURN = TurnSpec(
    call_site=LlmCallSite.MEAL_CHAT,
    effort=DISH_EFFORT,
    max_turns=DISH_MAX_TURNS,
    allowed=_dish_allowed,
    prepare=_dish_prepare,
    view=_dish_view,
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
    """Il giro della chat del piatto: `run_chat_turn` con `DISH_TURN`."""
    await run_chat_turn(
        session_factory, client, conversation_id=conversation_id,
        user_message_id=user_message_id, emit=emit, timeout_seconds=timeout_seconds,
        spec=DISH_TURN,
    )
