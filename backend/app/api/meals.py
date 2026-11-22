"""I pasti e la settimana (spec 2026-11-12 §5). Le rotte dal nome fisso stanno sopra
`/{meal_id}`, o «week» sarebbe letto come un id."""

import uuid
from datetime import UTC, date, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.api.refusals import meal_refusal_response
from app.core.config import get_settings
from app.core.db import get_session, get_session_factory
from app.core.security import require_session
from app.db.models.meal import Meal
from app.db.models.recipe import Recipe
from app.domain.meal_chat import FailureKind, can_chat, failure_notice
from app.domain.meals import MealSlot, MealStatus, is_unrecorded, week_bounds
from app.domain.rules import today_in_pantry
from app.repositories.meals import get_meal, leftover_candidates, meals_between
from app.schemas.meal import (
    MealCreate,
    MealOut,
    MealRecipeOut,
    MealRefOut,
    MealUpdate,
    RecipeCopyIn,
    WeekOut,
)
from app.services.change_cards import (
    create_empty_card,
    open_card_for_meal,
    open_cards_for_meals,
)
from app.services.claude.client import ClaudeClient, claude_configured, get_claude_client
from app.services.meals import (
    MealRefusal,
    check_can_take_recipe,
    copy_recipe_to_meal,
    create_meal,
    delete_meal,
    update_meal,
)
from app.services.planning import conversation_for_meal
from app.services.recipe_jobs import (
    RecipeJobs,
    get_recipe_jobs,
    recipe_run,
    settle_orphans,
    wants_recipe,
)

router = APIRouter(
    prefix="/api/v1/meals", tags=["meals"], dependencies=[Depends(require_session)]
)

RECIPE_PREPARING_NOTICE = "La ricetta è già in preparazione."


def meal_out(
    meal: Meal,
    today: date,
    *,
    preparing: frozenset[uuid.UUID] = frozenset(),
    open_card_id: uuid.UUID | None = None,
) -> MealOut:
    """Serializza un pasto con `recipe` e `leftover_of` già caricati (sono `lazy="raise"`).
    `preparing` sono i pasti che la coda delle ricette ha adesso (`RecipeJobs.live_ids`)."""
    origin = meal.leftover_of
    recipe = meal.recipe
    if meal.id in preparing:
        recipe_state = "preparing"
    elif wants_recipe(meal) and meal.recipe_notice is not None:
        recipe_state = "failed"
    else:
        recipe_state = "none"
    return MealOut(
        id=meal.id,
        day=meal.day,
        slot=MealSlot(meal.slot),
        week=week_bounds(meal.day)[0],
        dish=meal.dish,
        sides=meal.sides,
        away=meal.away,
        status=MealStatus(meal.status),
        unrecorded=is_unrecorded(MealStatus(meal.status), meal.day, today),
        recipe=(
            None
            if recipe is None
            else MealRecipeOut(id=recipe.id, title=recipe.title, in_book=recipe.in_book)
        ),
        leftover_of=(
            None
            if origin is None
            else MealRefOut(
                id=origin.id, day=origin.day, slot=MealSlot(origin.slot),
                dish=origin.dish, recipe_id=origin.recipe_id,
            )
        ),
        can_chat=can_chat(meal),
        open_card_id=open_card_id,
        recipe_state=recipe_state,
        recipe_notice=meal.recipe_notice if recipe_state == "failed" else None,
        can_ask_recipe=wants_recipe(meal) and recipe_state != "preparing",
    )


async def _refuse(session: AsyncSession, exc: MealRefusal):
    response = meal_refusal_response(exc)  # prima del rollback: legge l'occupante
    await session.rollback()
    return response


async def meals_out(
    session: AsyncSession,
    meals: list[Meal],
    today: date,
    preparing: frozenset[uuid.UUID] = frozenset(),
) -> list[MealOut]:
    """Una lista di pasti, con la scheda aperta di ciascuno letta con una query sola e la
    ricetta in preparazione letta dalla coda, in memoria."""
    open_cards = await open_cards_for_meals(session, [m.id for m in meals])
    return [
        meal_out(m, today, preparing=preparing, open_card_id=open_cards.get(m.id))
        for m in meals
    ]


async def _one_meal_out(
    session: AsyncSession,
    meal: Meal,
    today: date,
    preparing: frozenset[uuid.UUID] = frozenset(),
) -> MealOut:
    card = await open_card_for_meal(session, meal.id)
    return meal_out(meal, today, preparing=preparing, open_card_id=card.id if card else None)


async def _meal_or_404(session: AsyncSession, meal_id: uuid.UUID) -> Meal:
    meal = await get_meal(session, meal_id)
    if meal is None:
        raise HTTPException(404, "pasto inesistente")
    return meal


@router.get("/week", response_model=WeekOut)
async def get_week(
    of: date | None = None,
    session: AsyncSession = Depends(get_session),
    jobs: RecipeJobs = Depends(get_recipe_jobs),
) -> WeekOut:
    today = today_in_pantry()
    monday, sunday = week_bounds(of or today)
    live = jobs.live_ids()  # prima dei pasti: un pasto uscito dalla coda è già committato
    meals = await meals_between(session, monday, sunday)
    if await settle_orphans(session, meals, live):
        await session.commit()
    return WeekOut(
        monday=monday,
        sunday=sunday,
        today=today,
        previous=monday - timedelta(days=7),
        next=monday + timedelta(days=7),
        days=[monday + timedelta(days=i) for i in range(7)],
        meals=await meals_out(session, list(meals), today, live),
        preparing=any(m.id in live for m in meals),
    )


@router.get("/leftover-candidates", response_model=list[MealOut])
async def get_leftover_candidates(
    day: date,
    slot: MealSlot,
    session: AsyncSession = Depends(get_session),
    jobs: RecipeJobs = Depends(get_recipe_jobs),
) -> list[MealOut]:
    today = today_in_pantry()
    return await meals_out(
        session, list(await leftover_candidates(session, day, slot)), today, jobs.live_ids()
    )


@router.get("/{meal_id}", response_model=MealOut)
async def get_one_meal(
    meal_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    jobs: RecipeJobs = Depends(get_recipe_jobs),
) -> MealOut:
    live = jobs.live_ids()  # prima del pasto, come la settimana
    meal = await _meal_or_404(session, meal_id)
    if await settle_orphans(session, [meal], live):
        await session.commit()
    return await _one_meal_out(session, meal, today_in_pantry(), live)


@router.post("", response_model=MealOut, status_code=201)
async def post_meal(
    payload: MealCreate,
    session: AsyncSession = Depends(get_session),
    jobs: RecipeJobs = Depends(get_recipe_jobs),
):
    try:
        meal = await create_meal(
            session,
            day=payload.day, slot=payload.slot, dish=payload.dish, sides=payload.sides,
            away=payload.away, status=payload.status,
            leftover_of_id=payload.leftover_of_id, replace=payload.replace,
        )
    except MealRefusal as exc:
        return await _refuse(session, exc)
    out = await _one_meal_out(session, meal, today_in_pantry(), jobs.live_ids())
    await session.commit()
    return out


@router.patch("/{meal_id}", response_model=MealOut)
async def patch_meal(
    meal_id: uuid.UUID,
    payload: MealUpdate,
    session: AsyncSession = Depends(get_session),
    jobs: RecipeJobs = Depends(get_recipe_jobs),
):
    meal = await _meal_or_404(session, meal_id)
    changes = payload.model_dump(
        include=payload.model_fields_set - {"replace", "detach_leftovers", "detach_origin"}
    )
    was_draft = meal.status == MealStatus.DRAFT.value
    try:
        updated = await update_meal(
            session,
            meal,
            changes,
            replace=payload.replace,
            detach_leftovers=payload.detach_leftovers,
            detach_origin=payload.detach_origin,
        )
        if was_draft and updated.status == MealStatus.OFFICIAL.value:
            # «Rendi ufficiale»: la scheda vuota, da compilare a mano
            await create_empty_card(session, updated)
    except MealRefusal as exc:
        return await _refuse(session, exc)
    out = await _one_meal_out(session, updated, today_in_pantry(), jobs.live_ids())
    await session.commit()
    return out


@router.delete("/{meal_id}", status_code=204)
async def remove_meal(
    meal_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> Response:
    meal = await _meal_or_404(session, meal_id)
    await delete_meal(session, meal, today=today_in_pantry())
    await session.commit()
    return Response(status_code=204)


@router.post("/{meal_id}/recipe/copy", response_model=MealOut, status_code=201)
async def copy_recipe_into_meal(
    meal_id: uuid.UUID,
    payload: RecipeCopyIn,
    session: AsyncSession = Depends(get_session),
    jobs: RecipeJobs = Depends(get_recipe_jobs),
):
    meal = await _meal_or_404(session, meal_id)
    source = await session.get(Recipe, payload.recipe_id)
    if source is None:
        raise HTTPException(404, "ricetta inesistente")
    try:
        await copy_recipe_to_meal(session, meal, source)
    except MealRefusal as exc:
        return await _refuse(session, exc)
    out = await _one_meal_out(
        session, await _meal_or_404(session, meal_id), today_in_pantry(), jobs.live_ids()
    )
    await session.commit()
    return out


@router.post("/{meal_id}/recipe/ask", response_model=MealOut, status_code=202)
async def ask_recipe(
    meal_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
    factory: async_sessionmaker[AsyncSession] = Depends(get_session_factory),
    client: ClaudeClient = Depends(get_claude_client),
    jobs: RecipeJobs = Depends(get_recipe_jobs),
):
    """«Chiedi la ricetta a Claude»: il pasto entra nella coda delle ricette (decisione 15)
    e la risposta lo dice già `preparing`. Ogni rifiuto arriva prima di scrivere."""
    meal = await _meal_or_404(session, meal_id)
    now = datetime.now(UTC)
    if not claude_configured():
        return JSONResponse(
            status_code=503,
            content={
                "code": "claude_not_configured",
                "detail": failure_notice(FailureKind.NOT_CONFIGURED, None, now),
            },
        )
    if meal.id in jobs.live_ids():
        return JSONResponse(
            status_code=409,
            content={"code": "recipe_preparing", "detail": RECIPE_PREPARING_NOTICE},
        )
    try:
        check_can_take_recipe(meal)
    except MealRefusal as exc:
        return await _refuse(session, exc)
    meal.recipe_requested_at = now
    meal.recipe_notice = None
    conversation_id = await conversation_for_meal(session, meal.id)
    out = await _one_meal_out(
        session, meal, today_in_pantry(), jobs.live_ids() | {meal.id}
    )
    await session.commit()
    # Dopo il commit nessuna lettura: la coda parte al primo `await` e usa le sue sessioni.
    jobs.enqueue(
        [meal.id],
        conversation_id,
        recipe_run(
            factory, client, timeout_seconds=get_settings().claude_reply_timeout_seconds
        ),
    )
    return out
