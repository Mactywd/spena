"""Le risposte di «Sostituisci» (R5): leggerle, scriverle, controllarle.

Una tabella sola per due ambiti (vedi `app/db/models/substitution.py`): la **voce
generale** di un ingrediente in un contesto, e la **correzione di una ricetta**. Per una
riga di ricetta vale la correzione, se c'è, altrimenti la voce generale del contesto
della ricetta (`effective_row`).

Una risposta «sostituti» che non ha più sostituti visibili — l'unico è stato cancellato,
o è diventato non alimentare — **vale come nessuna risposta** (`is_answered`): a video
«Nessun suggerimento ancora», e il calcolo la richiede. È la regola che rende innocue le
strade che cancellano un ingrediente (un annullamento della coda, l'import che rifà una
ricetta) senza che ognuna debba sapere dei sostituti; vale anche per una risposta scritta
a mano, perché non resta niente da proteggere.

L'AI scrive solo dove non c'è una risposta (`store_ai_answer`), e lo controlla nella
stessa scrittura: una correzione a mano non si riscrive mai (decisione 4 di Mattia).

Nessuna funzione fa commit: chi chiama decide, come in `services/registry.py`.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.ingredient import Ingredient
from app.db.models.recipe import Recipe, RecipeIngredient
from app.db.models.substitution import IngredientSubstitution, SubstitutionOption
from app.domain.rules import IngredientKind
from app.domain.substitutions import (
    SUBSTITUTE_NOTE_MAX,
    SUBSTITUTES_MAX,
    DecidedBy,
    SubstitutionContext,
    SubstitutionVerdict,
    clean_note,
    recipe_context,
)


@dataclass(frozen=True)
class Answer:
    """Una risposta da scrivere: l'esito e, per «sostituti», gli ingredienti con la nota,
    nell'ordine in cui si mostrano (dal migliore)."""

    verdict: SubstitutionVerdict
    substitutes: tuple[tuple[uuid.UUID, str | None], ...] = ()


class SubstitutionRefused(Exception):
    """Una risposta scritta a mano che non si può salvare, col perché da mostrare."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def _loaded(statement):
    # `populate_existing`: una riga già nella sessione si rilegge dal database, sostituti
    # compresi. Senza, dopo una scrittura la sessione restituirebbe la copia in memoria,
    # i cui sostituti appena aggiunti non hanno l'ingrediente caricato — e leggerlo in una
    # sessione async è un MissingGreenlet.
    return statement.options(
        selectinload(IngredientSubstitution.options).joinedload(SubstitutionOption.substitute)
    ).execution_options(populate_existing=True)


def visible_options(row: IngredientSubstitution) -> list[SubstitutionOption]:
    """I sostituti che si possono ancora proporre: solo alimenti (decisione 2)."""
    return [option for option in row.options if option.substitute.kind == IngredientKind.FOOD]


def is_answered(row: IngredientSubstitution) -> bool:
    return row.verdict != SubstitutionVerdict.SUBSTITUTES or bool(visible_options(row))


async def general_row(
    session: AsyncSession, ingredient_id: uuid.UUID, context: SubstitutionContext
) -> IngredientSubstitution | None:
    statement = select(IngredientSubstitution).where(
        IngredientSubstitution.ingredient_id == ingredient_id,
        IngredientSubstitution.context == context.value,
        IngredientSubstitution.recipe_id.is_(None),
    )
    return (await session.execute(_loaded(statement))).scalars().first()


async def recipe_row(
    session: AsyncSession, recipe_id: uuid.UUID, ingredient_id: uuid.UUID
) -> IngredientSubstitution | None:
    statement = select(IngredientSubstitution).where(
        IngredientSubstitution.recipe_id == recipe_id,
        IngredientSubstitution.ingredient_id == ingredient_id,
    )
    return (await session.execute(_loaded(statement))).scalars().first()


async def effective_row(
    session: AsyncSession,
    recipe_id: uuid.UUID,
    ingredient_id: uuid.UUID,
    context: SubstitutionContext,
) -> IngredientSubstitution | None:
    """La risposta che vale per una riga di ricetta, se ce n'è una che risponde."""
    override = await recipe_row(session, recipe_id, ingredient_id)
    if override is not None and is_answered(override):
        return override
    general = await general_row(session, ingredient_id, context)
    if general is not None and is_answered(general):
        return general
    return None


async def checked_answer(
    session: AsyncSession,
    ingredient_id: uuid.UUID,
    verdict: SubstitutionVerdict,
    substitutes: Sequence[tuple[uuid.UUID, str | None]],
) -> Answer:
    """Una risposta scritta a mano, controllata: la stessa regola che scarta quelle
    dell'AI (decisione 2), detta con la frase che lo schermo mostra accanto a «Salva»."""
    if verdict != SubstitutionVerdict.SUBSTITUTES:
        if substitutes:
            raise SubstitutionRefused(
                "Chi si omette o è insostituibile non ha sostituti: toglili, poi salva."
            )
        return Answer(verdict)
    if not substitutes:
        raise SubstitutionRefused("Scegli almeno un ingrediente da usare al suo posto.")
    if len(substitutes) > SUBSTITUTES_MAX:
        raise SubstitutionRefused("Al massimo tre sostituti: togline uno, poi salva.")
    ids = {substitute_id for substitute_id, _ in substitutes} | {ingredient_id}
    found = {
        ingredient.id: ingredient
        for ingredient in (
            await session.execute(select(Ingredient).where(Ingredient.id.in_(ids)))
        ).scalars()
    }
    seen: set[uuid.UUID] = set()
    cleaned: list[tuple[uuid.UUID, str | None]] = []
    for substitute_id, raw_note in substitutes:
        substitute = found.get(substitute_id)
        if substitute is None:
            raise SubstitutionRefused(
                "Uno dei sostituti scelti non è più in anagrafica: toglilo e scegline un altro."
            )
        name = substitute.display_name
        if substitute_id == ingredient_id:
            raise SubstitutionRefused(
                f"«{name}» non può sostituire sé stesso: scegli un altro ingrediente."
            )
        if substitute.kind != IngredientKind.FOOD:
            raise SubstitutionRefused(
                f"«{name}» non è un alimento: non può sostituire un ingrediente."
            )
        if substitute_id in seen:
            raise SubstitutionRefused(f"«{name}» è scelto due volte: tienilo una volta sola.")
        seen.add(substitute_id)
        note = clean_note(raw_note)
        if note is not None and len(note) > SUBSTITUTE_NOTE_MAX:
            raise SubstitutionRefused(
                f"La nota per «{name}» è troppo lunga: bastano poche parole, al massimo "
                f"{SUBSTITUTE_NOTE_MAX} caratteri."
            )
        cleaned.append((substitute_id, note))
    return Answer(verdict, tuple(cleaned))


def _options(answer: Answer) -> list[SubstitutionOption]:
    return [
        SubstitutionOption(substitute_id=substitute_id, note=note, position=position)
        for position, (substitute_id, note) in enumerate(answer.substitutes)
    ]


async def write_general(
    session: AsyncSession,
    ingredient_id: uuid.UUID,
    context: SubstitutionContext,
    answer: Answer,
) -> None:
    """La voce generale scritta a mano, in Anagrafica: prende il posto di quel che c'era,
    dell'AI o di una persona. «Va bene così» passa di qui con la risposta com'è."""
    await session.execute(
        delete(IngredientSubstitution).where(
            IngredientSubstitution.ingredient_id == ingredient_id,
            IngredientSubstitution.context == context.value,
            IngredientSubstitution.recipe_id.is_(None),
        )
    )
    session.add(
        IngredientSubstitution(
            ingredient_id=ingredient_id, context=context.value, recipe_id=None,
            verdict=answer.verdict.value, decided_by=DecidedBy.HUMAN.value,
            options=_options(answer),
        )
    )
    await session.flush()


async def write_override(
    session: AsyncSession, recipe_id: uuid.UUID, ingredient_id: uuid.UUID, answer: Answer
) -> None:
    """La correzione di una ricetta («Non va bene qui»): prende il posto di quella di prima."""
    await delete_override(session, recipe_id, ingredient_id)
    session.add(
        IngredientSubstitution(
            ingredient_id=ingredient_id, context=None, recipe_id=recipe_id,
            verdict=answer.verdict.value, decided_by=DecidedBy.HUMAN.value,
            options=_options(answer),
        )
    )
    await session.flush()


async def delete_override(
    session: AsyncSession, recipe_id: uuid.UUID, ingredient_id: uuid.UUID
) -> bool:
    """Toglie la correzione di una ricetta. Vero se c'era."""
    result = await session.execute(
        delete(IngredientSubstitution).where(
            IngredientSubstitution.recipe_id == recipe_id,
            IngredientSubstitution.ingredient_id == ingredient_id,
        )
    )
    await session.flush()
    return (result.rowcount or 0) > 0


async def store_ai_answer(
    session: AsyncSession,
    ingredient_id: uuid.UUID,
    context: SubstitutionContext,
    answer: Answer,
) -> bool:
    """La voce generale decisa dall'AI, solo dove non c'è una risposta. Vero se scritta.

    Una risposta rimasta vuota (`is_answered` falso) si toglie prima: non dice più niente.
    Poi l'`INSERT` stesso controlla, con `ON CONFLICT DO NOTHING` sull'indice parziale:
    se fra la lettura e la scrittura una persona ha scritto la voce, vince la persona —
    il comando gira minuti, e la correzione fatta nel frattempo non si riscrive.
    """
    existing = await general_row(session, ingredient_id, context)
    if existing is not None:
        if is_answered(existing):
            return False
        await session.execute(
            delete(IngredientSubstitution).where(IngredientSubstitution.id == existing.id)
        )
    inserted = (
        await session.execute(
            pg_insert(IngredientSubstitution)
            .values(
                id=uuid.uuid4(), ingredient_id=ingredient_id, context=context.value,
                recipe_id=None, verdict=answer.verdict.value, decided_by=DecidedBy.AI.value,
            )
            .on_conflict_do_nothing(
                index_elements=["ingredient_id", "context"],
                index_where=IngredientSubstitution.recipe_id.is_(None),
            )
            .returning(IngredientSubstitution.id)
        )
    ).scalar_one_or_none()
    if inserted is None:
        return False
    session.add_all(
        SubstitutionOption(
            substitution_id=inserted, substitute_id=substitute_id, note=note, position=position
        )
        for position, (substitute_id, note) in enumerate(answer.substitutes)
    )
    await session.flush()
    return True


@dataclass(frozen=True)
class Voice:
    """Un ingrediente in un contesto: la granularità delle risposte generali."""

    ingredient_id: uuid.UUID
    name: str
    context: SubstitutionContext
    # le ricette non eliminate di quel contesto che lo usano: l'ordine del comando
    recipes: int


async def _usage(
    session: AsyncSession, ingredient_id: uuid.UUID | None = None
) -> dict[tuple[uuid.UUID, SubstitutionContext], Voice]:
    """Le voci del ricettario: un ingrediente per ogni contesto in cui compare.

    Si raggruppa per categoria in SQL e si piega in contesti qui, con `recipe_context`:
    la regola del contesto resta una sola, nel dominio, invece di una seconda copia in
    SQL che si scollerebbe (prima lezione di CLAUDE.md). Le categorie sono una ventina.
    """
    statement = (
        select(RecipeIngredient.ingredient_id, Ingredient.name, Recipe.category, func.count())
        .join(Recipe, Recipe.id == RecipeIngredient.recipe_id)
        .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
        .where(Recipe.archived_at.is_(None), Ingredient.kind == IngredientKind.FOOD)
        .group_by(RecipeIngredient.ingredient_id, Ingredient.name, Recipe.category)
    )
    if ingredient_id is not None:
        statement = statement.where(RecipeIngredient.ingredient_id == ingredient_id)
    voices: dict[tuple[uuid.UUID, SubstitutionContext], Voice] = {}
    for found_id, name, category, count in (await session.execute(statement)).all():
        context = recipe_context(category)
        before = voices.get((found_id, context))
        voices[(found_id, context)] = Voice(
            found_id, name, context, count + (before.recipes if before else 0)
        )
    return voices


async def pending_voices(session: AsyncSession) -> list[Voice]:
    """Le voci senza una risposta generale che risponda, dalla più usata.

    Le più usate prima: `--limit 20` mostra le risposte che contano di più, e un lancio
    interrotto ha già coperto le ricette più frequenti.
    """
    usage = await _usage(session)
    rows = (
        await session.execute(
            _loaded(select(IngredientSubstitution).where(IngredientSubstitution.recipe_id.is_(None)))
        )
    ).scalars().all()
    answered = {
        (row.ingredient_id, SubstitutionContext(row.context)) for row in rows if is_answered(row)
    }
    pending = [voice for key, voice in usage.items() if key not in answered]
    pending.sort(key=lambda voice: (-voice.recipes, voice.name, voice.context.value))
    return pending


@dataclass(frozen=True)
class ContextView:
    context: SubstitutionContext
    recipes: int
    # la voce generale, solo se risponde (`is_answered`)
    row: IngredientSubstitution | None


@dataclass(frozen=True)
class IngredientView:
    contexts: tuple[ContextView, ...]
    # le correzioni di ricetta che rispondono: «Corretto a mano in N ricette»
    recipe_overrides: int


async def ingredient_view(session: AsyncSession, ingredient_id: uuid.UUID) -> IngredientView:
    """Cosa sa di sostituti la scheda di un ingrediente in Anagrafica (R5).

    I contesti in cui compare in una ricetta, più quelli in cui ha una risposta anche
    senza ricette (scritta a mano, o rimasta dopo che l'ultima ricetta è stata eliminata),
    nell'ordine di `SubstitutionContext`: salato, poi dolce.
    """
    usage = await _usage(session, ingredient_id)
    rows = (
        await session.execute(
            _loaded(
                select(IngredientSubstitution).where(
                    IngredientSubstitution.ingredient_id == ingredient_id
                )
            )
        )
    ).scalars().all()
    general = {
        SubstitutionContext(row.context): row
        for row in rows
        if row.recipe_id is None and is_answered(row)
    }
    contexts = []
    for context in SubstitutionContext:
        voice = usage.get((ingredient_id, context))
        row = general.get(context)
        if voice is None and row is None:
            continue
        contexts.append(ContextView(context, voice.recipes if voice else 0, row))
    overrides = sum(1 for row in rows if row.recipe_id is not None and is_answered(row))
    return IngredientView(tuple(contexts), overrides)


async def _rows_of(session: AsyncSession, ingredient_id: uuid.UUID) -> list[IngredientSubstitution]:
    statement = select(IngredientSubstitution).where(
        IngredientSubstitution.ingredient_id == ingredient_id
    )
    return list((await session.execute(_loaded(statement))).scalars())


def _rank(row: IngredientSubstitution) -> tuple[bool, bool]:
    # prima chi risponde, poi chi è scritto a mano; a parità resta il vincitore
    return (is_answered(row), row.decided_by == DecidedBy.HUMAN)


async def move_substitutions(
    session: AsyncSession, loser_id: uuid.UUID, winner_id: uuid.UUID
) -> None:
    """La metà di `merge_ingredients` che riguarda i sostituti (R5).

    Va chiamata prima che il perdente sparisca: le chiavi esterne sono in CASCADE, e
    cancellato lui le sue risposte se ne andrebbero con lui. Quattro passi:

    1. dove il perdente è un sostituto, va il vincitore — tolto prima dove il vincitore
       c'è già, o dove la risposta è proprio del vincitore (sarebbe sostituto di sé);
    2. le risposte del perdente non possono proporre il vincitore: dopo la fusione
       sarebbe un sostituto di sé stesso;
    3. le risposte del perdente passano al vincitore: una voce generale vince su quella
       del vincitore solo se risponde dove l'altra no, o è scritta a mano dove l'altra è
       dell'AI (`_rank`); una correzione di ricetta passa se la ricetta non ne ha già una
       per il vincitore;
    4. una risposta «sostituti» rimasta senza sostituti non dice più niente, e si toglie.
    """
    rows_of_winner = select(IngredientSubstitution.id).where(
        IngredientSubstitution.ingredient_id == winner_id
    )
    rows_of_loser = select(IngredientSubstitution.id).where(
        IngredientSubstitution.ingredient_id == loser_id
    )
    listing_winner = select(SubstitutionOption.substitution_id).where(
        SubstitutionOption.substitute_id == winner_id
    )
    await session.execute(
        delete(SubstitutionOption).where(
            SubstitutionOption.substitute_id == loser_id,
            or_(
                SubstitutionOption.substitution_id.in_(rows_of_winner),
                SubstitutionOption.substitution_id.in_(listing_winner),
            ),
        )
    )
    await session.execute(
        update(SubstitutionOption)
        .where(SubstitutionOption.substitute_id == loser_id)
        .values(substitute_id=winner_id)
    )
    await session.execute(
        delete(SubstitutionOption).where(
            SubstitutionOption.substitute_id == winner_id,
            SubstitutionOption.substitution_id.in_(rows_of_loser),
        )
    )

    winner_rows = await _rows_of(session, winner_id)
    general = {row.context: row for row in winner_rows if row.recipe_id is None}
    overridden = {row.recipe_id for row in winner_rows if row.recipe_id is not None}
    for row in await _rows_of(session, loser_id):
        if row.recipe_id is None:
            rival = general.get(row.context)
            if rival is not None:
                if _rank(rival) >= _rank(row):
                    await session.execute(
                        delete(IngredientSubstitution).where(IngredientSubstitution.id == row.id)
                    )
                    continue
                await session.execute(
                    delete(IngredientSubstitution).where(IngredientSubstitution.id == rival.id)
                )
        elif row.recipe_id in overridden:
            await session.execute(
                delete(IngredientSubstitution).where(IngredientSubstitution.id == row.id)
            )
            continue
        await session.execute(
            update(IngredientSubstitution)
            .where(IngredientSubstitution.id == row.id)
            .values(ingredient_id=winner_id)
        )

    await session.execute(
        delete(IngredientSubstitution).where(
            IngredientSubstitution.verdict == SubstitutionVerdict.SUBSTITUTES.value,
            ~select(SubstitutionOption.id)
            .where(SubstitutionOption.substitution_id == IngredientSubstitution.id)
            .exists(),
        )
    )
    await session.flush()
