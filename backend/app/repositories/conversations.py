"""Le letture e la creazione delle conversazioni: la chat dei piatti e la pianificazione
(spec 2026-11-12 §4.3, §5.2).

L'ordine dei messaggi è `created_at`, poi `id`: chi scrive un messaggio gli dà un
`created_at` suo, perché `now()` di Postgres è l'inizio della transazione e due messaggi
nella stessa avrebbero lo stesso istante.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.change_card import ChangeCard
from app.db.models.conversation import (
    Conversation,
    ConversationKind,
    ConversationMessage,
    MessageRole,
)
from app.db.models.planning import MealProposal
from app.db.models.recipe_change import RecipeChange
from app.domain.meals import MealSlot


async def dish_conversation(session: AsyncSession, meal_id: uuid.UUID) -> Conversation | None:
    statement = select(Conversation).where(
        Conversation.kind == ConversationKind.DISH.value, Conversation.meal_id == meal_id
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def get_or_create_dish_conversation(
    session: AsyncSession, meal_id: uuid.UUID
) -> Conversation:
    found = await dish_conversation(session, meal_id)
    if found is not None:
        return found
    conversation = Conversation(kind=ConversationKind.DISH.value, meal_id=meal_id)
    session.add(conversation)
    await session.flush()
    return conversation


async def messages_of(
    session: AsyncSession, conversation_id: uuid.UUID
) -> list[ConversationMessage]:
    statement = (
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at, ConversationMessage.id)
        .execution_options(populate_existing=True)
    )
    return list((await session.execute(statement)).scalars().all())


async def changes_of(session: AsyncSession, conversation_id: uuid.UUID) -> list[RecipeChange]:
    statement = (
        select(RecipeChange)
        .where(RecipeChange.conversation_id == conversation_id)
        .order_by(RecipeChange.created_at, RecipeChange.id)
        .execution_options(populate_existing=True)
    )
    return list((await session.execute(statement)).scalars().all())


async def latest_turn(
    session: AsyncSession, conversation_id: uuid.UUID
) -> ConversationMessage | None:
    """L'ultimo messaggio di Mattia: apre il giro più recente."""
    statement = (
        select(ConversationMessage)
        .where(
            ConversationMessage.conversation_id == conversation_id,
            ConversationMessage.role == MessageRole.USER.value,
        )
        .order_by(ConversationMessage.created_at.desc(), ConversationMessage.id.desc())
        .limit(1)
    )
    return (await session.execute(statement)).scalar_one_or_none()


# --- la pianificazione ---------------------------------------------------------------


async def latest_planning(session: AsyncSession) -> Conversation | None:
    statement = (
        select(Conversation)
        .where(Conversation.kind == ConversationKind.PLANNING.value)
        .order_by(Conversation.created_at.desc(), Conversation.id.desc())
        .limit(1)
    )
    return (await session.execute(statement)).scalar_one_or_none()


def _write_focus(conversation: Conversation, focus: tuple[date, MealSlot] | None) -> None:
    if focus is None:
        conversation.focus_day, conversation.focus_slot = None, None
    else:
        conversation.focus_day, conversation.focus_slot = focus[0], MealSlot(focus[1]).value


async def create_planning(
    session: AsyncSession, *, focus: tuple[date, MealSlot] | None = None
) -> Conversation:
    # `created_at` scritto qui: «la più recente» non può dipendere da `now()`, che è lo
    # stesso istante per tutta la transazione
    now = datetime.now(UTC)
    conversation = Conversation(
        kind=ConversationKind.PLANNING.value, created_at=now, updated_at=now
    )
    _write_focus(conversation, focus)
    session.add(conversation)
    await session.flush()
    return conversation


async def set_focus(
    session: AsyncSession, conversation: Conversation, focus: tuple[date, MealSlot] | None
) -> None:
    _write_focus(conversation, focus)
    await session.flush()


async def proposals_of(session: AsyncSession, conversation_id: uuid.UUID) -> list[MealProposal]:
    statement = (
        select(MealProposal)
        .where(MealProposal.conversation_id == conversation_id)
        .order_by(MealProposal.created_at, MealProposal.id)
        .execution_options(populate_existing=True)
    )
    return list((await session.execute(statement)).scalars().all())


async def cards_of(session: AsyncSession, conversation_id: uuid.UUID) -> list[ChangeCard]:
    statement = (
        select(ChangeCard)
        .options(selectinload(ChangeCard.rows))
        .where(ChangeCard.conversation_id == conversation_id)
        .order_by(ChangeCard.created_at, ChangeCard.id)
        .execution_options(populate_existing=True)
    )
    return list((await session.execute(statement)).scalars().all())


async def move_turn_products(
    session: AsyncSession, *, from_message_id: uuid.UUID, to_message_id: uuid.UUID
) -> None:
    """«Riprova» si porta dietro quello che il giro fallito aveva prodotto (decisione 28):
    proposte, schede e modifiche della ricetta passano al messaggio nuovo prima che il
    vecchio si cancelli; altrimenti `ON DELETE SET NULL` le staccherebbe dalla chat."""
    for model in (MealProposal, ChangeCard, RecipeChange):
        await session.execute(
            update(model)
            .where(model.turn_message_id == from_message_id)
            .values(turn_message_id=to_message_id)
            .execution_options(synchronize_session="fetch")
        )
    await session.flush()
