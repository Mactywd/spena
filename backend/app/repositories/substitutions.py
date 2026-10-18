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

from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.ingredient import Ingredient
from app.db.models.substitution import IngredientSubstitution, SubstitutionOption
from app.domain.rules import IngredientKind
from app.domain.substitutions import (
    SUBSTITUTE_NOTE_MAX,
    SUBSTITUTES_MAX,
    DecidedBy,
    SubstitutionContext,
    SubstitutionVerdict,
    clean_note,
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
