"""Scrivere i pasti (spec 2026-11-12 §4). Scrivono e fanno `flush`, mai `commit`: il commit
è della rotta. Ogni rifiuto è un `MealRefusal` con un codice e una frase che dice che cosa
fare, e arriva prima di ogni scrittura: un rifiuto lascia tutto com'era."""

import uuid
from collections.abc import Mapping
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.meal import Meal
from app.db.models.recipe import Recipe
from app.domain.meals import MealSlot, MealStatus, is_before
from app.repositories.meals import get_meal, meal_at
from app.repositories.recipes import copy_recipe
from app.services.change_cards import InverseReason, propose_inverse_card

_ALLOWED = {"dish", "sides", "away", "day", "slot", "status"}


class MealRefusalCode(StrEnum):
    SLOT_TAKEN = "slot_taken"
    HAS_RECIPE = "has_recipe"
    NO_RECIPE_HERE = "no_recipe_here"
    BAD_LEFTOVER = "bad_leftover"
    STAYS_OFFICIAL = "stays_official"
    RECIPE_ARCHIVED = "recipe_archived"


class MealRefusal(Exception):
    def __init__(
        self, code: MealRefusalCode, message: str, occupant: Meal | None = None
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.occupant = occupant


def _bad_leftover() -> MealRefusal:
    return MealRefusal(
        MealRefusalCode.BAD_LEFTOVER,
        "Un avanzo viene da un pasto cucinato prima, che non sia a sua volta un avanzo.",
    )


async def _check_leftover(
    session: AsyncSession, leftover_of_id: uuid.UUID, day: date, slot: MealSlot
) -> None:
    origin = await session.get(Meal, leftover_of_id)
    if (
        origin is None
        or origin.away
        or origin.leftover_of_id is not None
        or not is_before(origin.day, MealSlot(origin.slot), day, slot)
    ):
        raise _bad_leftover()


async def _unlink_leftovers_of(session: AsyncSession, meal: Meal) -> None:
    """Gli avanzi che puntano a `meal` restano pasti a mano, con il loro piatto (decisione 15).
    Per l'ORM e non per `ON DELETE SET NULL`: gli oggetti già in sessione devono saperlo."""
    rows = (
        await session.execute(select(Meal).where(Meal.leftover_of_id == meal.id))
    ).scalars().all()
    for row in rows:
        row.leftover_of_id = None
    if rows:
        await session.flush()


async def release_recipe(session: AsyncSession, meal: Meal) -> None:
    """Stacca la ricetta dal pasto. Fuori dal ricettario la si archivia (nessun altro pasto
    la ha, e l'invariante è che una ricetta viva fuori dal ricettario ha un pasto); nel
    ricettario resta com'è."""
    if meal.recipe_id is None:
        return
    recipe = await session.get(Recipe, meal.recipe_id)
    meal.recipe_id = None
    if recipe is not None and not recipe.in_book and recipe.archived_at is None:
        recipe.archived_at = datetime.now(UTC)
    await session.flush()


async def delete_meal(
    session: AsyncSession, meal: Meal, *, _reason: InverseReason = InverseReason.DELETED
) -> None:
    # prima di toglierlo: la scheda inversa legge il pasto com'è (decisione 22).
    # `_reason` è delle sostituzioni di questo modulo, che tolgono l'occupante
    await propose_inverse_card(session, meal, _reason)
    await release_recipe(session, meal)
    await _unlink_leftovers_of(session, meal)
    await session.delete(meal)
    await session.flush()


def _slot_taken(occupant: Meal) -> MealRefusal:
    return MealRefusal(
        MealRefusalCode.SLOT_TAKEN, f"C'è già «{occupant.dish}» in questo posto.", occupant
    )


async def create_meal(
    session: AsyncSession,
    *,
    day: date,
    slot: MealSlot,
    dish: str,
    sides: str | None = None,
    away: bool = False,
    status: MealStatus = MealStatus.OFFICIAL,
    leftover_of_id: uuid.UUID | None = None,
    replace: bool = False,
) -> Meal:
    slot = MealSlot(slot)
    if away:
        leftover_of_id = None
    if leftover_of_id is not None:
        await _check_leftover(session, leftover_of_id, day, slot)
    occupant = await meal_at(session, day, slot)
    if occupant is not None:
        if not replace:
            raise _slot_taken(occupant)
        await delete_meal(session, occupant, _reason=InverseReason.REPLACED)
    meal = Meal(
        day=day, slot=slot.value, dish=dish, sides=sides, away=away,
        status=MealStatus(status).value, leftover_of_id=leftover_of_id,
    )
    session.add(meal)
    await session.flush()
    created = await get_meal(session, meal.id)
    assert created is not None
    return created


async def update_meal(
    session: AsyncSession, meal: Meal, changes: Mapping[str, object], *, replace: bool = False
) -> Meal:
    unknown = set(changes) - _ALLOWED
    if unknown:
        raise ValueError(f"Campi non modificabili: {sorted(unknown)}")

    day = changes.get("day", meal.day)
    slot = MealSlot(changes.get("slot", meal.slot))  # type: ignore[arg-type]
    away = bool(changes.get("away", meal.away))
    status = MealStatus(changes.get("status", meal.status))  # type: ignore[arg-type]
    assert isinstance(day, date)

    # tutti i rifiuti prima di scrivere
    if meal.status == MealStatus.OFFICIAL and status == MealStatus.DRAFT:
        raise MealRefusal(MealRefusalCode.STAYS_OFFICIAL, "Un pasto ufficiale non torna bozza.")
    moved = (day, slot.value) != (meal.day, meal.slot)
    if moved and not away and meal.leftover_of_id is not None:
        await _check_leftover(session, meal.leftover_of_id, day, slot)
    occupant = None
    if moved:
        occupant = await meal_at(session, day, slot)
        if occupant is not None and occupant.id != meal.id and not replace:
            raise _slot_taken(occupant)

    if occupant is not None and occupant.id != meal.id:
        await delete_meal(session, occupant, _reason=InverseReason.REPLACED)

    if away and not meal.away:
        await propose_inverse_card(session, meal, InverseReason.AWAY)
        # un pasto fuori casa non ha legame d'avanzo (decisione 14), e gli avanzi che venivano
        # da lui restano soli, come se fosse eliminato (decisione 15). La ricetta invece resta,
        # nascosta (decisione di Mattia del 2026-11-18): tolta la spunta, torna
        meal.leftover_of_id = None
        await _unlink_leftovers_of(session, meal)
    for key in ("dish", "sides"):
        if key in changes:
            setattr(meal, key, changes[key])
    meal.away = away
    meal.day = day
    meal.slot = slot.value
    meal.status = status.value
    await session.flush()
    updated = await get_meal(session, meal.id)
    assert updated is not None
    return updated


def refuse_if_no_recipe_here(meal: Meal) -> None:
    """Un avanzo, un pasto fuori casa e una bozza non hanno una ricetta propria."""
    if meal.leftover_of_id is not None:
        message = "Un avanzo usa la ricetta del pasto da cui viene."
    elif meal.away:
        message = "Un pasto fuori casa non ha una ricetta."
    elif meal.status == MealStatus.DRAFT:
        message = "È una bozza: la ricetta arriva quando diventa ufficiale."
    else:
        return
    raise MealRefusal(MealRefusalCode.NO_RECIPE_HERE, message)


def check_can_take_recipe(meal: Meal) -> None:
    if meal.recipe_id is not None:
        raise MealRefusal(MealRefusalCode.HAS_RECIPE, "Il pasto ha già una ricetta.")
    refuse_if_no_recipe_here(meal)


async def link_recipe(session: AsyncSession, meal: Meal, recipe: Recipe) -> None:
    check_can_take_recipe(meal)
    meal.recipe_id = recipe.id
    await session.flush()
    await get_meal(session, meal.id)  # ricarica `recipe` sul pasto che chi chiama ha in mano


async def copy_recipe_to_meal(session: AsyncSession, meal: Meal, source: Recipe) -> Recipe:
    check_can_take_recipe(meal)
    if source.archived_at is not None:
        raise MealRefusal(
            MealRefusalCode.RECIPE_ARCHIVED,
            "Questa ricetta è stata eliminata: ripristinala prima di copiarla.",
        )
    copy = await copy_recipe(session, source)
    await link_recipe(session, meal, copy)
    return copy
