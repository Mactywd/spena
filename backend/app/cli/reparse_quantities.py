"""Riempie `quantity_value` e `quantity_unit_id` rileggendo `quantity_text`.

Eseguire con `python -m app.cli.reparse_quantities` dentro il container del backend,
una volta dopo la migrazione `0008` e ogni volta che il parser migliora.

Non è un passo dati dentro la migrazione proprio per questo: il primo catalogo vero
porterà forme di dose che 26 ricette non hanno, e migliorare il parser non deve voler
dire scriverne un'altra. È la stessa ragione per cui esiste `app.cli.reindex`.
"""

import asyncio
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.recipe import RecipeIngredient
from app.db.models.unit import Unit
from app.domain.quantities import parse_quantity
from app.repositories.units import ensure_unit

# Nessun `.limit()` qui, di proposito: si legge tutta la tabella in un colpo solo
# perché è piccola per contratto (un centinaio di ricette finché i volumi non
# cambiano). Se un giorno smettesse di esserlo, `app.cli.reindex` tiene già la
# forma a lotti da copiare.


@dataclass(frozen=True)
class Reparsed:
    parsed: int
    unparsed: int
    new_units: int


async def reparse(session: AsyncSession) -> Reparsed:
    before = len((await session.execute(select(Unit.id))).scalars().all())
    parsed = unparsed = 0
    rows = (await session.execute(select(RecipeIngredient))).scalars().all()
    for row in rows:
        value, key = parse_quantity(row.quantity_text)
        unit = await ensure_unit(session, key) if key else None
        row.quantity_value = value
        row.quantity_unit_id = unit.id if unit else None
        if value is None:
            unparsed += 1
        else:
            parsed += 1
    await session.flush()
    after = len((await session.execute(select(Unit.id))).scalars().all())
    return Reparsed(parsed=parsed, unparsed=unparsed, new_units=after - before)


async def main() -> None:
    async with SessionLocal() as session:
        esito = await reparse(session)
        await session.commit()
    print(
        f"{esito.parsed} dosi parsate, {esito.unparsed} no, "
        f"{esito.new_units} unità nuove depositate"
    )
    if esito.new_units:
        print("decidile con: python -m app.cli.decide_units")


if __name__ == "__main__":
    asyncio.run(main())
