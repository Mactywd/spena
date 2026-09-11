import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models.pantry import PantryItem
from app.domain.rules import Availability, PantryStatus, availability_of


def _active(statement):
    """Le voci finite o archiviate non esistono, ai fini della disponibilità."""
    return statement.where(
        PantryItem.archived_at.is_(None), PantryItem.status != PantryStatus.FINISHED
    )


async def availability_map(
    session: AsyncSession, ingredient_ids: Sequence[uuid.UUID] | None = None
) -> dict[uuid.UUID, Availability]:
    """Ponte fra il database e le regole pure: stati concreti verso disponibilità.

    Gli ingredienti assenti dalla mappa sono mancanti. I chiamanti usano
    `result.get(id, Availability.MISSING)`.
    """
    statement = _active(select(PantryItem.ingredient_id, PantryItem.status))
    if ingredient_ids is not None:
        if not ingredient_ids:
            return {}
        statement = statement.where(PantryItem.ingredient_id.in_(ingredient_ids))

    grouped: dict[uuid.UUID, list[PantryStatus]] = defaultdict(list)
    for ingredient_id, status in (await session.execute(statement)).all():
        grouped[ingredient_id].append(PantryStatus(status))

    return {
        ingredient_id: availability_of(statuses) for ingredient_id, statuses in grouped.items()
    }


async def list_pantry(session: AsyncSession) -> list[PantryItem]:
    statement = (
        select(PantryItem)
        .options(joinedload(PantryItem.ingredient), joinedload(PantryItem.product))
        .where(PantryItem.archived_at.is_(None))
        .order_by(PantryItem.added_at.desc())
    )
    return list((await session.execute(statement)).unique().scalars())


async def add_pantry_item(
    session: AsyncSession,
    *,
    ingredient_id: uuid.UUID,
    product_id: uuid.UUID | None = None,
    status: PantryStatus = PantryStatus.AVAILABLE,
    note: str | None = None,
) -> PantryItem:
    item = PantryItem(ingredient_id=ingredient_id, product_id=product_id, status=status, note=note)
    session.add(item)
    await session.flush()
    return item


async def set_status(session: AsyncSession, item_id: uuid.UUID, status: PantryStatus) -> PantryItem:
    item = await session.get(PantryItem, item_id)
    if item is None:
        raise KeyError(item_id)
    item.status = status
    item.status_changed_at = datetime.now(UTC)
    await session.flush()
    return item


async def archive_item(session: AsyncSession, item_id: uuid.UUID) -> PantryItem:
    item = await session.get(PantryItem, item_id)
    if item is None:
        raise KeyError(item_id)
    item.archived_at = datetime.now(UTC)
    await session.flush()
    return item
