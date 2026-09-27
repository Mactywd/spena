"""Corregge l'anagrafica degli ingredienti a lotti, da un piano scritto.

Eseguire nel container del backend, dove la cartella `data/` del repository è montata
in `/data`:

    python -m app.cli.fix_registry /data/fixes/<piano>.json             # prova e dice
    python -m app.cli.fix_registry /data/fixes/<piano>.json --conferma  # applica

Senza `--conferma` il piano gira davvero, dentro una transazione che alla fine si
annulla: la prova incontra gli stessi rifiuti dell'applicazione, compresa la
materializzazione delle ricette, e non una loro imitazione. Con `--conferma` la stessa
transazione si salva, e un solo passo rifiutato non salva niente.

Nato il 2026-09-27, dopo l'import completo (R4): la revisione dell'anagrafica ha
trovato alias sbagliati («lampascioni» sotto «lampone disidratato»), doppioni che
davano falsi «manca» (la piadina in dispensa, la piadella nelle ricette) e reparti
sbagliati. Il piano è un file e non un elenco di UPDATE per due ragioni: resta nel
repository come storia di cosa si è deciso, e ogni passo usa gli stessi percorsi già
testati dell'import — l'annullamento di una decisione e la decisione a mano — invece
di una chirurgia su `recipe_ingredients`.

Il piano è una lista di passi JSON, applicati in ordine:

    {"op": "decide", "term": "Fegato di vitello", "create": {"name": "fegato di vitello",
     "category": "carne"}}
    {"op": "decide", "term": "Noce di manzo", "map": "fettina di manzo"}
    {"op": "decide", "term": "Liquore", "map": "liquore", "role": "secondary"}
    {"op": "remap", "term": "Lampascioni", "map": "lampascione"}
    {"op": "merge", "from": "piadella", "into": "piadina"}
    {"op": "recategorize", "ingredient": "eglefino", "category": "pesce"}
    {"op": "rename", "ingredient": "tormini", "name": "tomino", "display_name": "Tomini"}
    {"op": "move_alias", "alias": "piadina", "to": "piadina"}

`decide` vale per un termine in coda, `remap` per uno già deciso: prima lo annulla,
rimettendo in attesa le pagine delle sue ricette, poi lo decide. `merge` sposta tutto
quel che puntava a `from` — termini, dispensa, lista, prodotti, righe di ricetta,
alias — su `into`, e poi cancella `from`; il suo nome resta come alias di `into`,
così chi lo scrive nella lista trova ancora qualcosa. Le pagine rimesse in attesa da
un `merge` tornano ricette dentro il passo stesso, con le loro cotture; quelle di
`remap` e `decide` una volta sola, alla fine.

Da S9 le correzioni dell'anagrafica — `merge`, `recategorize`, `rename`, `move_alias` —
stanno in `app/services/registry.py`, lo stesso servizio che chiamano le schede
dell'anagrafica nell'app. Questo comando traduce il passo in argomenti, chiama il
servizio e trasforma il suo rifiuto (`RegistryRefusal`) in `PlanError`. `decide` e
`remap` restano qui: sono decisioni della coda, non anagrafica.
"""

import argparse
import asyncio
import json
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.ingredient import Ingredient, IngredientAlias
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.domain.rules import IngredientRole
from app.repositories.imports import counts
from app.services import registry
from app.services.recipe_import.manual import DecisionRefused, ManualDecision, decide_by_hand
from app.services.recipe_import.materialize import materialize_ready
from app.services.recipe_import.undo import undo_decision
from app.services.registry import RegistryRefusal

Log = Callable[[str], None]


class PlanError(Exception):
    """Un passo del piano non si può applicare: niente del piano viene salvato."""


@dataclass
class Outcome:
    steps: int = 0
    requeued: int = 0
    rebuilt: int = 0
    skipped: int = 0
    pending_terms: int = 0


async def _ingredient(session: AsyncSession, name: str) -> Ingredient:
    found = (
        await session.execute(select(Ingredient).where(Ingredient.name == name.strip().lower()))
    ).scalars().first()
    if found is None:
        raise PlanError(f"nessun ingrediente di nome «{name}»")
    return found


async def _term(session: AsyncSession, step: dict) -> ImportTerm:
    """Il termine per `term_key`, oppure per nome visibile se quel nome è di uno solo."""
    if "term_key" in step:
        found = list(
            (
                await session.execute(
                    select(ImportTerm).where(
                        ImportTerm.source == GIALLOZAFFERANO,
                        ImportTerm.term_key == step["term_key"],
                    )
                )
            ).scalars()
        )
    else:
        wanted = str(step["term"]).strip().lower()
        found = list(
            (
                await session.execute(
                    select(ImportTerm).where(
                        ImportTerm.source == GIALLOZAFFERANO,
                        func.lower(func.trim(ImportTerm.display_name)) == wanted,
                    )
                )
            ).scalars()
        )
    if len(found) != 1:
        label = step.get("term_key") or step.get("term")
        keys = ", ".join(term.term_key for term in found) or "nessuno"
        raise PlanError(f"«{label}»: serve un termine solo, trovati {len(found)} ({keys})")
    return found[0]


async def _decision(session: AsyncSession, step: dict) -> ManualDecision:
    role = step.get("role")
    if role is not None and role not in {r.value for r in IngredientRole}:
        raise PlanError(f"ruolo sconosciuto: «{role}»")
    if step.get("ignore"):
        return ManualDecision(action="ignore", role_override=role)
    if "map" in step:
        target = await _ingredient(session, step["map"])
        return ManualDecision(action="map", ingredient_id=target.id, role_override=role)
    if "create" in step:
        spec = step["create"]
        return ManualDecision(
            action="create",
            name=spec.get("name"),
            display_name=spec.get("display_name"),
            category=spec.get("category"),
            role_override=role,
        )
    raise PlanError("una decisione vuole «map», «create» oppure «ignore»")


async def _apply_decision(
    session: AsyncSession, term: ImportTerm, decision: ManualDecision
) -> Ingredient | None:
    try:
        return await decide_by_hand(session, term, decision)
    except DecisionRefused as exc:
        raise PlanError(f"«{term.display_name}»: {exc.message}") from exc


async def _undo(session: AsyncSession, term: ImportTerm) -> int:
    return (await undo_decision(session, term)).recipes_requeued


async def decide(session: AsyncSession, step: dict, outcome: Outcome) -> str:
    term = await _term(session, step)
    if term.decision != TermDecision.PENDING:
        raise PlanError(f"«{term.display_name}» è già deciso: per cambiarlo usa «remap»")
    ingredient = await _apply_decision(session, term, await _decision(session, step))
    return f"«{term.display_name}» → {ingredient.name if ingredient else 'ignorato'}"


async def remap(session: AsyncSession, step: dict, outcome: Outcome) -> str:
    term = await _term(session, step)
    if term.decision == TermDecision.PENDING:
        raise PlanError(f"«{term.display_name}» è in coda: per deciderlo usa «decide»")
    before = await session.get(Ingredient, term.ingredient_id) if term.ingredient_id else None
    decision = await _decision(session, step)
    requeued = await _undo(session, term)
    outcome.requeued += requeued
    ingredient = await _apply_decision(session, term, decision)
    return (
        f"«{term.display_name}»: {before.name if before else 'ignorato'} → "
        f"{ingredient.name if ingredient else 'ignorato'} ({requeued} ricette da rifare)"
    )


async def merge(session: AsyncSession, step: dict, outcome: Outcome) -> str:
    loser = await _ingredient(session, step["from"])
    winner = await _ingredient(session, step["into"])
    try:
        merged = await registry.merge_ingredients(session, loser.id, winner.id)
    except RegistryRefusal as exc:
        raise PlanError(exc.message) from exc
    # `merge_ingredients` rimaterializza le pagine che l'unione ha reso pronte dentro
    # se stessa (annulla e ridecide ogni termine del perdente, poi ricostruisce): non
    # resta niente in attesa da contare qui, quindi `outcome.requeued` non si tocca —
    # a differenza di `remap`, dove la rimaterializzazione finale di `apply_plan` è
    # quella che rifà le ricette rimesse in attesa.
    outcome.rebuilt += merged.recipes_rebuilt
    return (
        f"{step['from']} → {merged.winner_name}: {merged.recipes_rebuilt} ricette rifatte, "
        f"{merged.recipe_lines_moved} righe fuori dall'import, "
        f"{merged.pantry_items + merged.shopping_items + merged.products} fra dispensa, "
        f"lista e prodotti, {merged.cooking_events_relinked} cotture ri-legate"
    )


async def recategorize(session: AsyncSession, step: dict, outcome: Outcome) -> str:
    ingredient = await _ingredient(session, step["ingredient"])
    before = ingredient.category
    try:
        await registry.recategorize_ingredient(session, ingredient.id, step["category"])
    except RegistryRefusal as exc:
        raise PlanError(exc.message) from exc
    return f"{ingredient.name}: {before} → {ingredient.category}"


async def rename(session: AsyncSession, step: dict, outcome: Outcome) -> str:
    ingredient = await _ingredient(session, step["ingredient"])
    old_name, old_display = ingredient.name, ingredient.display_name
    try:
        await registry.rename_ingredient(
            session, ingredient.id,
            name=step.get("name"), display_name=step.get("display_name"),
        )
    except RegistryRefusal as exc:
        raise PlanError(exc.message) from exc
    return f"{old_name} ({old_display}) → {ingredient.name} ({ingredient.display_name})"


async def move_alias(session: AsyncSession, step: dict, outcome: Outcome) -> str:
    alias = step["alias"].strip().lower()
    target = await _ingredient(session, step["to"])
    query = select(IngredientAlias).where(IngredientAlias.alias == alias)
    if "from" in step:
        query = query.where(
            IngredientAlias.ingredient_id == (await _ingredient(session, step["from"])).id
        )
    rows = list((await session.execute(query)).scalars())
    if not rows:
        raise PlanError(f"nessun alias «{alias}» da spostare")
    for row in rows:
        try:
            await registry.move_alias(session, row.id, target.id)
        except RegistryRefusal as exc:
            raise PlanError(exc.message) from exc
    return f"alias «{alias}» → {target.name}"


OPERATIONS = {
    "decide": decide,
    "remap": remap,
    "merge": merge,
    "recategorize": recategorize,
    "rename": rename,
    "move_alias": move_alias,
}


async def apply_plan(
    session: AsyncSession, plan: list[dict], *, log: Log = print
) -> Outcome:
    """Applica il piano nella sessione, senza commit: lo decide chi chiama."""
    outcome = Outcome()
    for index, step in enumerate(plan, start=1):
        operation = OPERATIONS.get(step.get("op", ""))
        if operation is None:
            raise PlanError(f"passo {index}: operazione sconosciuta «{step.get('op')}»")
        try:
            message = await operation(session, step, outcome)
        except PlanError as exc:
            raise PlanError(f"passo {index} ({step['op']}): {exc}") from exc
        except KeyError as exc:
            raise PlanError(f"passo {index} ({step['op']}): manca il campo {exc}") from exc
        outcome.steps += 1
        log(f"{index:>3}. {step['op']:<12} {message}")

    materialized = await materialize_ready(session, GIALLOZAFFERANO)
    outcome.rebuilt += materialized.created
    outcome.skipped = materialized.skipped
    outcome.pending_terms = (await counts(session, GIALLOZAFFERANO)).pending_terms
    log(
        f"{outcome.steps} passi; {outcome.requeued} ricette rimesse in attesa, "
        f"{outcome.rebuilt} rifatte, {outcome.skipped} scartate; "
        f"{outcome.pending_terms} termini ancora in coda."
    )
    return outcome


async def main() -> int:
    parser = argparse.ArgumentParser(description="Corregge l'anagrafica da un piano.")
    parser.add_argument("piano", type=Path, help="il file JSON con i passi")
    parser.add_argument("--conferma", action="store_true", help="salva davvero")
    arguments = parser.parse_args()
    plan = json.loads(arguments.piano.read_text(encoding="utf-8"))

    async with SessionLocal() as session:
        try:
            await apply_plan(session, plan)
        except PlanError as exc:
            await session.rollback()
            print(f"Rifiutato, niente salvato. {exc}")
            return 1
        if not arguments.conferma:
            await session.rollback()
            print("Era una prova, niente salvato: rilancia con --conferma per applicare.")
            return 0
        await session.commit()
        print("Salvato.")
        return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
