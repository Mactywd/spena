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
from app.domain.meals import MealSlot, MealStatus, in_leftover_window, place_words
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
    LEFTOVER_AFTER = "leftover_after"
    ORIGIN_OUT_OF_REACH = "origin_out_of_reach"


class MealRefusal(Exception):
    def __init__(
        self,
        code: MealRefusalCode,
        message: str,
        occupant: Meal | None = None,
        leftovers: int = 0,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.occupant = occupant
        self.leftovers = leftovers


def _bad_leftover() -> MealRefusal:
    return MealRefusal(
        MealRefusalCode.BAD_LEFTOVER,
        "Un avanzo viene da un pasto cucinato nei 3 giorni prima, che non sia a sua volta "
        "un avanzo.",
    )


async def _leftover_origin(session: AsyncSession, leftover_of_id: uuid.UUID) -> Meal:
    """Il pasto d'origine di un avanzo, se può esserlo dovunque stia l'avanzo: c'è, non è fuori
    casa e non è a sua volta un avanzo."""
    origin = await session.get(Meal, leftover_of_id)
    if origin is None or origin.away or origin.leftover_of_id is not None:
        raise _bad_leftover()
    return origin


async def _check_leftover(
    session: AsyncSession, leftover_of_id: uuid.UUID, day: date, slot: MealSlot
) -> None:
    origin = await _leftover_origin(session, leftover_of_id)
    if not in_leftover_window(origin.day, MealSlot(origin.slot), day, slot):
        raise _bad_leftover()


def _origin_out_of_reach(origin: Meal) -> MealRefusal:
    return MealRefusal(
        MealRefusalCode.ORIGIN_OUT_OF_REACH,
        f"Qui non può essere l'avanzo di «{origin.dish}» "
        f"({place_words(origin.day, MealSlot(origin.slot))}): un avanzo viene dopo il suo "
        "pasto, entro 3 giorni.",
    )


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


def _leftovers_sentence(places: list[str]) -> str:
    text = places[0] if len(places) == 1 else ", ".join(places[:-1]) + " e " + places[-1]
    text = text[0].upper() + text[1:]
    return f"{text} è un suo avanzo." if len(places) == 1 else f"{text} sono suoi avanzi."


async def _leftovers_left_behind(
    session: AsyncSession, meal: Meal, day: date, slot: MealSlot, skip: uuid.UUID | None
) -> list[Meal]:
    """Gli avanzi di `meal` che dal posto nuovo uscirebbero dalla finestra (prima di lui, o più
    di 3 giorni dopo), in ordine di posto. `skip` è l'occupante che la sostituzione elimina: se
    è un avanzo di `meal` non si considera (ruling B-R2), non si scrive su una riga che
    sparisce."""
    rows = (
        await session.execute(select(Meal).where(Meal.leftover_of_id == meal.id))
    ).scalars().all()
    behind = [
        r
        for r in rows
        if r.id != skip and not in_leftover_window(day, slot, r.day, MealSlot(r.slot))
    ]
    return sorted(behind, key=lambda r: (r.day, MealSlot(r.slot) == MealSlot.DINNER))


async def release_recipe(session: AsyncSession, meal: Meal) -> None:
    """Stacca la ricetta dal pasto. Fuori dal ricettario la si archivia (nessun altro pasto
    la ha, e l'invariante è che una ricetta viva fuori dal ricettario ha un pasto); nel
    ricettario resta com'è."""
    if meal.recipe_id is None:
        return
    recipe = await session.get(Recipe, meal.recipe_id)
    meal.recipe_id = None
    meal.recipe_notice = None  # un avviso vecchio della coda non deve ricomparire
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
    session: AsyncSession,
    meal: Meal,
    changes: Mapping[str, object],
    *,
    replace: bool = False,
    detach_leftovers: bool = False,
    detach_origin: bool = False,
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
    occupant = None
    if moved:
        occupant = await meal_at(session, day, slot)
        if occupant is not None and occupant.id != meal.id and not replace:
            raise _slot_taken(occupant)
    # un avanzo spostato fuori dalla finestra del suo pasto (decisione 5): dopo la domanda del
    # posto. Non chiede un avanzo che va fuori casa, né uno che sostituisce proprio il suo pasto
    # d'origine (ruling F-R1, come B-R2): in tutti e due il legame si toglie già
    replaces_origin = occupant is not None and occupant.id == meal.leftover_of_id
    detach_from_origin = False
    if moved and not away and meal.leftover_of_id is not None and not replaces_origin:
        origin = await _leftover_origin(session, meal.leftover_of_id)
        if not in_leftover_window(origin.day, MealSlot(origin.slot), day, slot):
            if not detach_origin:
                raise _origin_out_of_reach(origin)
            detach_from_origin = True
    # i suoi avanzi non possono stare prima di lui né più di 3 giorni dopo (decisioni 1 e 5): un
    # pasto che va fuori casa non chiede, i suoi avanzi si staccano già
    behind: list[Meal] = []
    if moved and not away:
        skip = occupant.id if occupant is not None and occupant.id != meal.id else None
        behind = await _leftovers_left_behind(session, meal, day, slot, skip)
        if behind and not detach_leftovers:
            raise MealRefusal(
                MealRefusalCode.LEFTOVER_AFTER,
                _leftovers_sentence([place_words(r.day, MealSlot(r.slot)) for r in behind]),
                leftovers=len(behind),
            )

    if detach_from_origin:
        meal.leftover_of_id = None  # prima di scrivere il posto: diventa un pasto a mano
    if occupant is not None and occupant.id != meal.id:
        await delete_meal(session, occupant, _reason=InverseReason.REPLACED)
    for row in behind:
        row.leftover_of_id = None

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
    meal.recipe_notice = None
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
