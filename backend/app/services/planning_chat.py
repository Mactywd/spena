"""Il giro della chat di pianificazione (spec 2026-11-12 §5.2, §7; piano 6c, Task 7) e la sua
vista.

Il giro è quello della chat del piatto (`run_chat_turn` di `app.services.meal_chat`) con
un'altra specie: `PLANNING_TURN`. Cambiano la sezione delle spese (`meal_planning`), lo
sforzo (`high`) e i turni, il prompt (la pianificazione, con il posto di partenza e la
proposta sul tavolo) e gli strumenti (`propose_meals` e `propose_changes`, niente
`write_recipe`: le ricette si scrivono dopo l'ufficializzazione, decisione 4).
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models.conversation import Conversation, ConversationKind, ConversationMessage
from app.db.models.planning import MealProposal, ProposalStatus
from app.domain.meal_chat import (
    PLANNING_EFFORT,
    PLANNING_MAX_TURNS,
    FailureKind,
    failure_notice,
)
from app.domain.meals import MealSlot
from app.domain.rules import today_in_pantry
from app.repositories.conversations import proposals_of
from app.schemas.planning import FocusOut, PlanningChatOut
from app.services.claude.client import ClaudeClient, SdkMcpTool, claude_configured
from app.services.claude.prompts import (
    PlanningContext,
    planning_system_prompt,
    render_planning_prompt,
)
from app.services.claude.tools import TurnContext, planning_tools
from app.services.llm import LlmCallSite
from app.services.meal_chat import (
    Emit,
    TurnSpec,
    chat_history,
    chat_messages_out,
    repair_orphans,
    run_chat_turn,
)
from app.services.planning import planning_concluded
from app.services.utensils import utensils_prompt_block


async def open_proposal(session: AsyncSession, conversation_id: uuid.UUID) -> MealProposal | None:
    """L'ultima proposta aperta della conversazione: quella sul tavolo."""
    open_ones = [
        p for p in await proposals_of(session, conversation_id)
        if p.status == ProposalStatus.OPEN.value
    ]
    return open_ones[-1] if open_ones else None


def _focus(conversation: Conversation) -> FocusOut | None:
    if conversation.focus_day is None or conversation.focus_slot is None:
        return None
    return FocusOut(day=conversation.focus_day, slot=MealSlot(conversation.focus_slot))


async def planning_view(
    session: AsyncSession,
    conversation: Conversation | None,
    *,
    replying: bool,
    now: datetime,
) -> PlanningChatOut:
    """La chat di pianificazione com'è adesso; senza conversazione, la vista vuota. Come la
    chat del piatto, senza un giro vivo un'attesa troppo lunga si scrive interrotta."""
    ready = claude_configured()
    notice = None if ready else failure_notice(FailureKind.NOT_CONFIGURED, None, now)
    if conversation is None:
        return PlanningChatOut(
            conversation_id=None, focus=None, messages=[], replying=replying,
            concluded=False, claude_ready=ready, claude_notice=notice,
        )
    focus = _focus(conversation)
    await repair_orphans(session, conversation.id, replying=replying, now=now)
    return PlanningChatOut(
        conversation_id=conversation.id,
        focus=focus,
        messages=await chat_messages_out(session, conversation, now=now),
        replying=replying,
        concluded=await planning_concluded(session, conversation, today_in_pantry(now)),
        claude_ready=ready,
        claude_notice=notice,
    )


async def _planning_allowed(session: AsyncSession, conversation: Conversation) -> bool:
    # una pianificazione può sempre avere un giro: non dipende da un pasto
    return conversation.kind == ConversationKind.PLANNING.value


async def _planning_prepare(
    session: AsyncSession,
    conversation: Conversation,
    message: ConversationMessage,
    ctx: TurnContext,
) -> tuple[str, str, list[SdkMcpTool]]:
    system_prompt = planning_system_prompt(await utensils_prompt_block(session))
    focus = _focus(conversation)
    context = PlanningContext(
        now=datetime.now(UTC),
        focus=(focus.day, focus.slot) if focus is not None else None,
        open_proposal=await open_proposal(session, conversation.id),
    )
    history = await chat_history(session, conversation.id, exclude=message.id)
    prompt = render_planning_prompt(context, history, message.text)
    return system_prompt, prompt, planning_tools(ctx)


async def _planning_view(
    session: AsyncSession, conversation: Conversation, replying: bool, now: datetime
) -> PlanningChatOut:
    return await planning_view(session, conversation, replying=replying, now=now)


PLANNING_TURN = TurnSpec(
    call_site=LlmCallSite.MEAL_PLANNING,
    effort=PLANNING_EFFORT,
    max_turns=PLANNING_MAX_TURNS,
    allowed=_planning_allowed,
    prepare=_planning_prepare,
    view=_planning_view,
)


async def run_planning_turn(
    session_factory: async_sessionmaker[AsyncSession],
    client: ClaudeClient,
    *,
    conversation_id: uuid.UUID,
    user_message_id: uuid.UUID,
    emit: Emit,
    timeout_seconds: float,
) -> None:
    """Il giro della pianificazione: `run_chat_turn` con `PLANNING_TURN`."""
    await run_chat_turn(
        session_factory, client, conversation_id=conversation_id,
        user_message_id=user_message_id, emit=emit, timeout_seconds=timeout_seconds,
        spec=PLANNING_TURN,
    )
