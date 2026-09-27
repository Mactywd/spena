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
così chi lo scrive nella lista trova ancora qualcosa. Le pagine rimesse in attesa
tornano ricette una volta sola, alla fine.
"""

import argparse
import asyncio
import json
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.recipe import RecipeIngredient
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.db.models.shopping import ShoppingListItem
from app.domain.rules import IngredientKind, IngredientRole, kind_for_category
from app.repositories.imports import counts
from app.repositories.ingredients import delete_ingredient_if_unused, remember_alias
from app.services.recipe_import.manual import DecisionRefused, ManualDecision, decide_by_hand
from app.services.recipe_import.materialize import (
    materialize_ready,
    merge_quantities,
    stronger,
)
from app.services.recipe_import.undo import undo_decision

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
    if loser.id == winner.id:
        raise PlanError(f"«{loser.name}» non si unisce a sé stesso")
    if loser.kind != winner.kind:
        raise PlanError(
            f"«{loser.name}» ({loser.kind}) e «{winner.name}» ({winner.kind}): un alimento "
            "e una voce non alimentare non si uniscono"
        )
    loser_id: uuid.UUID = loser.id
    # I nomi si fotografano prima: l'annullamento dell'ultimo termine può cancellare
    # l'ingrediente, e i suoi alias con lui.
    names = [loser.name, loser.display_name, *(alias.alias for alias in loser.aliases)]

    terms = list(
        (
            await session.execute(select(ImportTerm).where(ImportTerm.ingredient_id == loser_id))
        ).scalars()
    )
    requeued = 0
    for term in terms:
        role = term.role_override
        requeued += await _undo(session, term)
        await _apply_decision(
            session, term,
            ManualDecision(action="map", ingredient_id=winner.id, role_override=role),
        )
    outcome.requeued += requeued

    moved = 0
    for model in (PantryItem, ShoppingListItem, Product):
        result = await session.execute(
            update(model).where(model.ingredient_id == loser_id).values(ingredient_id=winner.id)
        )
        moved += result.rowcount or 0

    # Le righe rimaste sono di ricette che non vengono dall'import (scritte a mano o
    # con l'AI): quelle non si rifanno da un payload, si spostano. Se la ricetta ha
    # già una riga del vincitore, le due diventano una come nella materializzazione.
    lines = list(
        (
            await session.execute(
                select(RecipeIngredient).where(RecipeIngredient.ingredient_id == loser_id)
            )
        ).scalars()
    )
    for line in lines:
        twin = (
            await session.execute(
                select(RecipeIngredient).where(
                    RecipeIngredient.recipe_id == line.recipe_id,
                    RecipeIngredient.ingredient_id == winner.id,
                )
            )
        ).scalars().first()
        if twin is None:
            line.ingredient_id = winner.id
            continue
        twin.role = stronger(IngredientRole(twin.role), IngredientRole(line.role))
        twin.quantity_text = merge_quantities(twin.quantity_text, line.quantity_text)
        # «500 g + 50 g» non è una dose che il riporziona sappia leggere: la riga
        # smette di scalare, che è onesto, invece di scalare solo metà.
        twin.quantity_value = None
        twin.quantity_unit_id = None
        await session.delete(line)
    await session.flush()

    await session.execute(delete(IngredientAlias).where(IngredientAlias.ingredient_id == loser_id))
    await session.flush()
    survivor = await session.get(Ingredient, loser_id)
    if survivor is not None:
        # la collezione in memoria ricorda ancora gli alias appena cancellati
        await session.refresh(survivor)
        if not await delete_ingredient_if_unused(session, loser_id):
            raise PlanError(f"«{step['from']}» è ancora usato dopo l'unione")
    for name in names:
        if name.strip().lower() != winner.name:
            await remember_alias(session, winner.id, name)
    await session.flush()
    return (
        f"{step['from']} → {winner.name}: {len(terms)} termini, {len(lines)} righe "
        f"fuori dall'import, {moved} fra dispensa, lista e prodotti "
        f"({requeued} ricette da rifare)"
    )


async def recategorize(session: AsyncSession, step: dict, outcome: Outcome) -> str:
    ingredient = await _ingredient(session, step["ingredient"])
    category = step["category"]
    if category not in {c.value for c in IngredientCategory}:
        raise PlanError(f"reparto sconosciuto: «{category}»")
    if kind_for_category(category) == IngredientKind.NON_FOOD:
        used = (
            await session.execute(
                select(RecipeIngredient.id)
                .where(RecipeIngredient.ingredient_id == ingredient.id)
                .limit(1)
            )
        ).first()
        if used is not None:
            raise PlanError(
                f"«{ingredient.name}» è in qualche ricetta: non può diventare non alimentare"
            )
    before = ingredient.category
    ingredient.category = category
    await session.flush()
    return f"{ingredient.name}: {before} → {category}"


async def rename(session: AsyncSession, step: dict, outcome: Outcome) -> str:
    ingredient = await _ingredient(session, step["ingredient"])
    old_name, old_display = ingredient.name, ingredient.display_name
    if "name" in step:
        new_name = step["name"].strip().lower()
        if new_name != ingredient.name:
            taken = (
                await session.execute(select(Ingredient.id).where(Ingredient.name == new_name))
            ).first()
            if taken is not None:
                raise PlanError(f"«{new_name}» è già in anagrafica: usa «merge»")
            # l'alias uguale al nome nuovo diventerebbe un doppione del nome
            await session.execute(
                delete(IngredientAlias).where(
                    IngredientAlias.ingredient_id == ingredient.id,
                    IngredientAlias.alias == new_name,
                )
            )
            ingredient.name = new_name
    if "display_name" in step:
        ingredient.display_name = step["display_name"].strip()
    await session.flush()
    if old_name != ingredient.name:
        await remember_alias(session, ingredient.id, old_name)
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
        await session.delete(row)
    await session.flush()
    if alias != target.name:
        await remember_alias(session, target.id, alias)
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
    outcome.rebuilt = materialized.created
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
