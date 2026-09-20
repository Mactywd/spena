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


async def _write_forms(
    session: AsyncSession, unit: Unit, singular: str, plural: str, decided_by: str
) -> None:
    """Scrive le forme e chi le ha decise. Un posto solo per le due strade che ci
    arrivano — l'AI e la correzione a mano — perché quel che va scritto è lo stesso
    fatto, e due copie sono il modo di farle divergere."""
    unit.singular = singular
    unit.plural = plural
    unit.decided_by = decided_by
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


async def apply_forms(
    session: AsyncSession, unit: Unit, singular: str, plural: str
) -> None:
    await _write_forms(session, unit, singular, plural, decided_by="ai")


async def set_unit_forms(
    session: AsyncSession, key: str, singular: str, plural: str
) -> bool:
    """Le forme scritte a mano. Torna `False` se quella chiave non c'è.

    Esiste perché l'`--azzera` da solo non basta: misurato in produzione il
    2026-09-20, azzerare «cucchiai» e rilanciare ha riprodotto lo stesso errore del
    modello. Un annulla senza un «invece è così» lascia come unica via una UPDATE a
    mano, cioè fuori da ogni strada progettata.

    `decided_by` diventa «human», e questo la toglie dalla coda di `undecided_units`:
    una decisione umana è definitiva finché non la si azzera, altrimenti il modello
    rifarebbe al giro dopo l'errore appena corretto. La lunghezza delle forme la
    controlla chi chiama — le colonne sono `String(UNIT_MAX_LENGTH)` — perché è
    validazione di un argomento, non una regola del registro.
    """
    unit = (
        await session.execute(select(Unit).where(Unit.key == key))
    ).scalars().first()
    if unit is None:
        return False
    await _write_forms(session, unit, singular, plural, decided_by="human")
    await session.flush()
    return True


async def reset_unit(session: AsyncSession, key: str) -> bool:
    """Riporta un'unità a non decisa. Torna `False` se quella chiave non c'è."""
    unit = (
        await session.execute(select(Unit).where(Unit.key == key))
    ).scalars().first()
    if unit is None:
        return False
    unit.singular = None
    unit.plural = None
    unit.decided_by = None
    unit.decided_at = None
    unit.canonical_id = None
    await session.flush()
    return True
