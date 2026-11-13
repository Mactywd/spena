"""Gli utensili di cucina: leggere, aggiungere, correggere, togliere.

Le funzioni fanno `flush` e mai `commit`: la `commit` la fa la rotta.
"""

import uuid
from collections.abc import Mapping

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.utensil import Utensil


async def list_utensils(session: AsyncSession) -> list[Utensil]:
    result = await session.execute(
        select(Utensil).order_by(func.lower(Utensil.name), Utensil.created_at, Utensil.id)
    )
    return list(result.scalars())


async def create_utensil(session: AsyncSession, *, name: str, note: str | None) -> Utensil:
    utensil = Utensil(name=name, note=note)
    session.add(utensil)
    await session.flush()
    return utensil


async def update_utensil(
    session: AsyncSession, utensil_id: uuid.UUID, fields: Mapping[str, str | None]
) -> Utensil:
    utensil = await session.get(Utensil, utensil_id)
    if utensil is None:
        raise KeyError(utensil_id)
    if "name" in fields:
        utensil.name = fields["name"]  # type: ignore[assignment]
    if "note" in fields:
        utensil.note = fields["note"]
    await session.flush()
    await session.refresh(utensil)
    return utensil


async def delete_utensil(session: AsyncSession, utensil_id: uuid.UUID) -> None:
    utensil = await session.get(Utensil, utensil_id)
    if utensil is None:
        raise KeyError(utensil_id)
    await session.delete(utensil)
    await session.flush()
