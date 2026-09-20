"""Il registro delle unità: depositarle e rileggerle.

Sta in un repository e non nel dominio perché tocca il database; la regola di cosa
sia un'unità resta in `app/domain/quantities.py`, che non sa niente di sessioni.
"""

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.unit import Unit


async def ensure_unit(session: AsyncSession, key: str) -> Unit:
    """La riga di `key`, creandola non decisa se non c'è.

    Non chiama nessuno e non decide niente: depositare un'unità sconosciuta deve
    poter succedere dentro la transazione che scrive una ricetta, e una chiamata di
    rete lì dentro legherebbe una scrittura a un servizio esterno.
    """
    found = (
        await session.execute(select(Unit).where(Unit.key == key))
    ).scalars().first()
    if found is not None:
        return found
    unit = Unit(key=key)
    session.add(unit)
    await session.flush()
    return unit


async def undecided_units(session: AsyncSession) -> list[Unit]:
    return list(
        (
            await session.execute(select(Unit).where(Unit.decided_by.is_(None)))
        ).scalars().all()
    )


async def apply_forms(
    session: AsyncSession, unit: Unit, singular: str, plural: str
) -> None:
    unit.singular = singular
    unit.plural = plural
    unit.decided_by = "ai"
    unit.decided_at = datetime.now(UTC)
    # «cucchiai» il cui singolare è «cucchiaio», che esiste già: ci punta, così S4
    # riempirà il peso di quell'unità una volta sola. Le forme restano scritte anche
    # sulla riga: il dettaglio della ricetta le legge dirette, senza seguire il
    # puntatore a ogni lettura.
    if singular != unit.key:
        canonical = (
            await session.execute(select(Unit).where(Unit.key == singular))
        ).scalars().first()
        if canonical is not None and canonical.id != unit.id:
            unit.canonical_id = canonical.id
