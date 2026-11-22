"""Letture dei pasti. Caricano `recipe`, `leftover_of` e `leftover_of.recipe` (i due legami
sono `lazy="raise"`), e rileggono dal database anche un pasto già in sessione: chi chiama
dopo una scrittura vuole lo stato vero, non quello in memoria."""

import uuid
from datetime import date, timedelta

from sqlalchemy import case, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.meal import Meal
from app.domain.meals import LEFTOVER_WINDOW_DAYS, MealSlot, in_leftover_window

_LOADS = (
    selectinload(Meal.recipe),
    selectinload(Meal.leftover_of).selectinload(Meal.recipe),
)


def _select():
    return select(Meal).options(*_LOADS).execution_options(populate_existing=True)


def _slot_order():
    return case((Meal.slot == MealSlot.LUNCH.value, 0), else_=1)


async def get_meal(session: AsyncSession, meal_id: uuid.UUID) -> Meal | None:
    return (await session.execute(_select().where(Meal.id == meal_id))).scalar_one_or_none()


async def lock_meal(session: AsyncSession, meal_id: uuid.UUID) -> Meal | None:
    """Il pasto, con la sua riga bloccata (`SELECT … FOR UPDATE`) fino alla fine della
    transazione di chi chiama: chi scrive la ricetta di un pasto lo prende per primo, e un
    secondo scrittore aspetta il `commit` del primo e poi rilegge il pasto com'è (idea 52).
    Solo la riga del pasto: la ricetta e l'origine dell'avanzo si leggono senza bloccarle."""
    statement = _select().where(Meal.id == meal_id).with_for_update(of=Meal)
    return (await session.execute(statement)).scalar_one_or_none()


async def meal_at(session: AsyncSession, day: date, slot: MealSlot) -> Meal | None:
    statement = _select().where(Meal.day == day, Meal.slot == MealSlot(slot).value)
    return (await session.execute(statement)).scalar_one_or_none()


async def meals_between(session: AsyncSession, start: date, end: date) -> list[Meal]:
    """Dal giorno `start` al giorno `end`, estremi compresi: per giorno, pranzo prima di cena."""
    statement = (
        _select().where(Meal.day >= start, Meal.day <= end).order_by(Meal.day, _slot_order())
    )
    return list((await session.execute(statement)).scalars().all())


async def meal_of_recipe(session: AsyncSession, recipe_id: uuid.UUID) -> Meal | None:
    return (
        await session.execute(_select().where(Meal.recipe_id == recipe_id))
    ).scalar_one_or_none()


async def leftover_candidates(session: AsyncSession, day: date, slot: MealSlot) -> list[Meal]:
    """I pasti da cui un avanzo in questo posto può venire: gli ultimi giorni della finestra,
    cucinati prima del posto, né avanzi né fuori casa. Dal più recente."""
    statement = _select().where(
        Meal.day >= day - timedelta(days=LEFTOVER_WINDOW_DAYS),
        Meal.day <= day,
        Meal.leftover_of_id.is_(None),
        Meal.away.is_(False),
    )
    found = (await session.execute(statement)).scalars().all()
    before = [m for m in found if in_leftover_window(m.day, MealSlot(m.slot), day, MealSlot(slot))]
    return sorted(before, key=lambda m: (m.day, MealSlot(m.slot) == MealSlot.DINNER), reverse=True)
