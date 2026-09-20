"""Il registro delle unità: depositarle e rileggerle.

Sta in un repository e non nel dominio perché tocca il database; la regola di cosa
sia un'unità resta in `app/domain/quantities.py`, che non sa niente di sessioni.
"""

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
