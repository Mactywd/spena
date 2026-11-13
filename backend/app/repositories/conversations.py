"""Le letture e la creazione delle conversazioni della chat dei piatti (spec 2026-11-12 §4.3).

L'ordine dei messaggi è `created_at`, poi `id`: chi scrive un messaggio gli dà un
`created_at` suo, perché `now()` di Postgres è l'inizio della transazione e due messaggi
nella stessa avrebbero lo stesso istante.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.conversation import (
    Conversation,
    ConversationKind,
    ConversationMessage,
    MessageRole,
)
from app.db.models.recipe_change import RecipeChange


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
