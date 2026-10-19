"""Ripulisce le dosi scritte dall'import, le rilegge, e toglie le unità rimaste senza righe.

    python -m app.cli.clean_doses --dry-run
    python -m app.cli.clean_doses

Il primo fa tutto il lavoro e alla fine annulla la transazione: i numeri che stampa sono
quelli della scrittura vera, e un errore della scrittura vera esce già lì. Il secondo
salva, in una transazione sola. Rilanciato, non cambia niente: una dose pulita non ha più
la forma dell'import (spec `docs/superpowers/specs/2026-10-13-pulizia-dosi-design.md`).

Legge tutte le righe di `recipe_ingredients` — ricette importate, adottate, scritte a mano,
archiviate —, ma `clean_dose` cambia solo quelle che hanno ancora gli a capo e le
tabulazioni di GialloZafferano (decisione 3 di Mattia, 2026-10-13). La rilettura è quella
di `reparse_quantities` (`parse_quantity` più `ensure_unit`) in una passata sola e a tuple
invece che a oggetti: in produzione sono più di 83.000 righe.
"""

import argparse
import asyncio
import uuid
from collections import Counter
from dataclasses import dataclass, field

from sqlalchemy import bindparam, delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.recipe import RecipeIngredient
from app.db.models.unit import Unit
from app.domain.quantities import DoseShape, clean_dose, merge_notes, parse_quantity
from app.repositories.units import ensure_unit

SAMPLE_PER_SHAPE = 5

SHAPE_LABELS = {
    DoseShape.SPACES: "solo a capo e tabulazioni",
    DoseShape.WORDS_BEFORE: "parole davanti alla dose, ora nella nota",
    DoseShape.NUMBER_IN_NAME: "numero nel nome, ora nella nota",
    DoseShape.NOTE_QB: "nota e q.b.",
}

_LINES = RecipeIngredient.__table__
_UNITS = Unit.__table__

# Core e non ORM: un `update(RecipeIngredient)` con una lista diventerebbe l'«ORM bulk
# update», che controlla quante righe ha toccato, e una riga cancellata nel frattempo da
# chi usa l'app farebbe fallire tutto. I nomi dei parametri sono diversi da quelli delle
# colonne, come Core chiede.
_WRITE_LINE = (
    update(_LINES)
    .where(_LINES.c.id == bindparam("row_id"))
    .values(
        quantity_text=bindparam("new_text"),
        note=bindparam("new_note"),
        quantity_value=bindparam("new_value"),
        quantity_unit_id=bindparam("new_unit"),
    )
)


@dataclass(frozen=True)
class Sample:
    shape: DoseShape
    before: str | None
    after: str | None
    note: str | None


@dataclass
class Cleaned:
    rows: int = 0
    shapes: Counter[DoseShape] = field(default_factory=Counter)
    parsed_before: int = 0
    parsed_after: int = 0
    # lette sia prima sia dopo, ma con un valore o un'unità diversi: «36 mesi» → 50 g
    changed_values: int = 0
    new_units: list[str] = field(default_factory=list)
    removed_units: list[str] = field(default_factory=list)
    # senza righe dopo la pulizia, ma canoniche di un'unità che resta (FK RESTRICT)
    kept_units: list[str] = field(default_factory=list)
    # già senza righe prima: non è la pulizia ad averle lasciate sole, e non si toccano
    idle_units: list[str] = field(default_factory=list)
    sample: list[Sample] = field(default_factory=list)

    @property
    def cleaned(self) -> int:
        return sum(self.shapes.values())


async def clean_doses(session: AsyncSession) -> Cleaned:
    """Pulisce, rilegge e toglie le unità orfane. Non fa commit: decide chi chiama."""
    outcome = Cleaned()
    rows = (
        await session.execute(
            select(
                _LINES.c.id,
                _LINES.c.quantity_text,
                _LINES.c.note,
                _LINES.c.quantity_value,
                _LINES.c.quantity_unit_id,
            ).order_by(_LINES.c.id)
        )
    ).all()
    outcome.rows = len(rows)
    units = dict((await session.execute(select(_UNITS.c.key, _UNITS.c.id))).all())
    used_before = {row.quantity_unit_id for row in rows if row.quantity_unit_id is not None}

    writes = []
    for row in rows:
        cleaned = clean_dose(row.quantity_text)
        if cleaned.shape is DoseShape.UNCHANGED:
            text, note = row.quantity_text, row.note
        else:
            # la nota già scritta resta davanti: c'era prima della pulizia
            text, note = cleaned.quantity_text, merge_notes(row.note, cleaned.note)
            outcome.shapes[cleaned.shape] += 1
            if sum(1 for s in outcome.sample if s.shape is cleaned.shape) < SAMPLE_PER_SHAPE:
                outcome.sample.append(Sample(cleaned.shape, row.quantity_text, text, note))

        value, key = parse_quantity(text)
        unit_id = None
        if key is not None:
            if key not in units:
                units[key] = (await ensure_unit(session, key)).id
                outcome.new_units.append(key)
            unit_id = units[key]

        if row.quantity_value is not None:
            outcome.parsed_before += 1
        if value is not None:
            outcome.parsed_after += 1
            if row.quantity_value is not None and (value, unit_id) != (
                row.quantity_value,
                row.quantity_unit_id,
            ):
                outcome.changed_values += 1
        if (text, note, value, unit_id) != (
            row.quantity_text,
            row.note,
            row.quantity_value,
            row.quantity_unit_id,
        ):
            writes.append({
                "row_id": row.id,
                "new_text": text,
                "new_note": note,
                "new_value": value,
                "new_unit": unit_id,
            })

    if writes:
        await session.execute(_WRITE_LINE, writes)
    await _drop_orphaned_units(session, used_before, outcome)
    return outcome


async def _drop_orphaned_units(
    session: AsyncSession, used_before: set[uuid.UUID], outcome: Cleaned
) -> None:
    """Toglie le unità che la pulizia ha lasciato senza righe: le parole che stavano
    davanti alla dose («mesi», «da», «per»), finite nel registro come unità."""
    used_after = set(
        (
            await session.execute(
                select(_LINES.c.quantity_unit_id)
                .where(_LINES.c.quantity_unit_id.is_not(None))
                .distinct()
            )
        ).scalars()
    )
    registry = (
        await session.execute(select(_UNITS.c.id, _UNITS.c.key, _UNITS.c.canonical_id))
    ).all()
    keys = {unit.id: unit.key for unit in registry}
    orphaned = used_before - used_after
    deletable = set(orphaned)
    # Un'unità che resta e punta a una di queste la tiene in vita: la FK è RESTRICT. E
    # tenerla può tenerne un'altra, se a sua volta ci punta: si ripete finché niente cambia.
    while True:
        needed = {
            unit.canonical_id
            for unit in registry
            if unit.id not in deletable and unit.canonical_id in deletable
        }
        if not needed:
            break
        deletable -= needed
    if deletable:
        # fra quelle che se ne vanno, i puntatori prima: una che punta a un'altra della
        # stessa lista bloccherebbe la DELETE
        await session.execute(
            update(_UNITS).where(_UNITS.c.id.in_(deletable)).values(canonical_id=None)
        )
        await session.execute(delete(_UNITS).where(_UNITS.c.id.in_(deletable)))
    outcome.removed_units = sorted(keys[unit_id] for unit_id in deletable)
    outcome.kept_units = sorted(keys[unit_id] for unit_id in orphaned - deletable)
    outcome.idle_units = sorted(
        unit.key
        for unit in registry
        if unit.id not in used_before and unit.id not in used_after
    )


def _visible(text: str | None) -> str:
    """Una dose dell'import su una riga sola: l'a capo come ⏎, le tabulazioni via."""
    if text is None:
        return "(vuota)"
    return text.replace("\t", "").replace("\r", "").replace("\n", "⏎")


def _names(keys: list[str]) -> str:
    return ", ".join(keys) if keys else "nessuna"


def report(outcome: Cleaned) -> str:
    lines = [f"Righe lette: {outcome.rows}. Ripulite: {outcome.cleaned}."]
    for shape, label in SHAPE_LABELS.items():
        lines.append(f"  {label}: {outcome.shapes[shape]}")
    lines.append(
        f"Dosi lette: {outcome.parsed_before} prima, {outcome.parsed_after} dopo; "
        f"{outcome.changed_values} lette diverse da prima."
    )
    lines.append(f"Unità nuove: {_names(outcome.new_units)}.")
    lines.append(f"Unità tolte, nessuna riga le usa più: {_names(outcome.removed_units)}.")
    lines.append(
        f"Unità senza righe tenute, perché canoniche di un'altra: {_names(outcome.kept_units)}."
    )
    lines.append(f"Unità già senza righe prima, lasciate: {_names(outcome.idle_units)}.")
    if outcome.sample:
        lines.append("Campione:")
        for sample in outcome.sample:
            note = f", nota «{sample.note}»" if sample.note else ""
            lines.append(
                f"  [{SHAPE_LABELS[sample.shape]}] «{_visible(sample.before)}» → "
                f"«{_visible(sample.after)}»{note}"
            )
    return "\n".join(lines)


async def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Ripulisce le dosi scritte dall'import, le rilegge, toglie le unità orfane."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="fa tutto, stampa i numeri e non salva niente"
    )
    arguments = parser.parse_args(argv)
    async with SessionLocal() as session:
        outcome = await clean_doses(session)
        print(report(outcome))
        if arguments.dry_run:
            await session.rollback()
            print("Era una prova, niente salvato: rilancia senza --dry-run per applicare.")
            return 0
        await session.commit()
    print("Salvato.")
    if outcome.new_units:
        print("Le unità nuove si decidono con: python -m app.cli.decide_units")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
