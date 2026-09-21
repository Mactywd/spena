import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models.pantry import PantryItem
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus
from app.domain.rules import PantryStatus
from app.repositories.pantry import add_pantry_item


@dataclass(frozen=True)
class StockEntry:
    shopping_item_id: uuid.UUID
    ingredient_id: uuid.UUID
    product_id: uuid.UUID | None
    expires_on: date | None


async def list_items(
    session: AsyncSession, statuses: Sequence[str] | None = None
) -> list[ShoppingListItem]:
    statement = (
        select(ShoppingListItem)
        .options(joinedload(ShoppingListItem.ingredient))
        .order_by(ShoppingListItem.created_at.asc())
    )
    if statuses:
        statement = statement.where(ShoppingListItem.status.in_(statuses))
    return list((await session.execute(statement)).unique().scalars())


async def add_item(
    session: AsyncSession,
    raw_text: str,
    ingredient_id: uuid.UUID | None = None,
    reason: ShoppingReason = ShoppingReason.MANUAL,
) -> ShoppingListItem:
    item = ShoppingListItem(
        raw_text=raw_text.strip(), ingredient_id=ingredient_id,
        status=ShoppingStatus.PENDING, reason=reason,
    )
    session.add(item)
    await session.flush()
    return item


async def patch_item(
    session: AsyncSession,
    item_id: uuid.UUID,
    *,
    status: ShoppingStatus | None = None,
    ingredient_id: uuid.UUID | None = None,
) -> ShoppingListItem:
    item = await session.get(ShoppingListItem, item_id)
    if item is None:
        raise KeyError(item_id)
    if ingredient_id is not None:
        item.ingredient_id = ingredient_id
    if status is not None:
        item.status = status
        now = datetime.now(UTC)
        if status is ShoppingStatus.CHECKED:
            item.checked_at = now
        elif status is ShoppingStatus.DONE:
            item.done_at = now
    await session.flush()
    await session.refresh(item, ["ingredient"])
    return item


async def stock_items(session: AsyncSession, entries: list[StockEntry]) -> list[PantryItem]:
    """Dalla lista spuntata alla dispensa, tutto dentro una sola transazione.

    Il chiamante non fa commit prima della fine: un riferimento sbagliato a metà
    strada non deve lasciare la dispensa popolata a metà.
    """
    created: list[PantryItem] = []
    now = datetime.now(UTC)
    for entry in entries:
        shopping_item = await session.get(ShoppingListItem, entry.shopping_item_id)
        if shopping_item is None:
            raise KeyError(entry.shopping_item_id)
        item = await add_pantry_item(
            session, ingredient_id=entry.ingredient_id, product_id=entry.product_id,
            status=PantryStatus.AVAILABLE, expires_on=entry.expires_on,
        )
        shopping_item.ingredient_id = entry.ingredient_id
        shopping_item.status = ShoppingStatus.DONE
        shopping_item.done_at = now
        created.append(item)
    await session.flush()
    return created
