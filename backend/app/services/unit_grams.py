"""I grammi per ingrediente × unità canonica (S4, fetta 2): quali coppie servono, chi le
scrive, come si mostrano.

Le coppie da pesare sono quelle che le ricette usano davvero — tutte, eliminate comprese,
perché una ricetta eliminata si ripristina — di un alimento, con una dose letta, su
un'unità che non è di massa né di volume (`classify_unit`). Sempre sull'unità canonica, e
«pezzo»/«pezzi» come la dose senza unità (spec §4.21–4.23).

L'unico posto che scrive `ingredient_unit_grams`: il peso a mano (Anagrafica, rotte di
`app/api/nutrition.py`) vince sempre e si scrive anche sopra quello dell'AI; l'AI scrive
solo dove non c'è niente, e lo controlla nella stessa INSERT. «Annulla il peso» toglie la
riga: la coppia torna da decidere. Il rifiuto ha la forma di quelli della fetta 1
(`NutritionRefusal`).

L'AI pesa le coppie da decidere a lotti di `GRAMS_BATCH` (`decide_grams`, sezione
`unit_grams`): i grammi netti della parte che si mangia di una unità, o `null` se
un'unità di quell'ingrediente non ha un peso sensato — che si scrive, e non si richiede.
"""

import json
import uuid
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Literal

from anthropic import AsyncAnthropic
from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.db.models.ingredient import Ingredient
from app.db.models.nutrition import IngredientUnitGrams, NutritionDecider
from app.db.models.recipe import RecipeIngredient
from app.db.models.unit import Unit
from app.domain.recipe_nutrition import (
    GRAMS_MAX,
    PIECE_LABEL,
    UnitKind,
    classify_unit,
    unit_label,
)
from app.domain.rules import IngredientKind
from app.services.ai_spend import Spend, complete_recorded
from app.services.ingredient_nutrition import NON_FOOD_CODE, NutritionRefusal
from app.services.llm import LlmCallSite, LlmFailureKind, LlmUnavailable

MEASURED_UNIT_CODE = "measured_unit"
BAD_GRAMS_CODE = "bad_grams"


@dataclass(frozen=True)
class Pair:
    ingredient_id: uuid.UUID
    ingredient_name: str
    # l'unità canonica, o None per il pezzo
    unit_id: uuid.UUID | None
    unit_label: str
    # una dose com'è scritta in una ricetta: all'AI dice di che si parla
    example: str | None


@dataclass(frozen=True)
class Weight:
    # l'id dell'unità canonica, o «pezzo»: è anche il pezzo di indirizzo delle rotte
    unit: str
    unit_label: str
    grams: Decimal | None
    state: Literal["undecided", "decided", "none"]
    decided_by: str | None


def unit_param(unit_id: uuid.UUID | None) -> str:
    return PIECE_LABEL if unit_id is None else str(unit_id)


def _same_unit(unit_id: uuid.UUID | None):
    if unit_id is None:
        return IngredientUnitGrams.unit_id.is_(None)
    return IngredientUnitGrams.unit_id == unit_id


async def used_pairs(session: AsyncSession, ingredient_id: uuid.UUID | None = None) -> list[Pair]:
    seen = aliased(Unit)
    canonical = aliased(Unit)
    statement = (
        select(
            RecipeIngredient.ingredient_id,
            Ingredient.name,
            canonical.id,
            canonical.key,
            canonical.singular,
            func.min(RecipeIngredient.quantity_text),
        )
        .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
        .outerjoin(seen, seen.id == RecipeIngredient.quantity_unit_id)
        .outerjoin(canonical, canonical.id == func.coalesce(seen.canonical_id, seen.id))
        .where(
            RecipeIngredient.quantity_value.is_not(None),
            Ingredient.kind == IngredientKind.FOOD,
        )
        .group_by(
            RecipeIngredient.ingredient_id, Ingredient.name, canonical.id, canonical.key, canonical.singular
        )
    )
    if ingredient_id is not None:
        statement = statement.where(RecipeIngredient.ingredient_id == ingredient_id)
    pairs: dict[tuple[uuid.UUID, uuid.UUID | None], Pair] = {}
    for ingredient, name, unit_id, key, singular, example in (await session.execute(statement)).all():
        kind = classify_unit(key, singular)
        if kind.measure != "pair":
            continue
        pair_unit = None if kind.piece else unit_id
        current = pairs.get((ingredient, pair_unit))
        if current is None or (example or "") < (current.example or ""):
            pairs[(ingredient, pair_unit)] = Pair(ingredient, name, pair_unit, unit_label(key, singular), example)
    return sorted(pairs.values(), key=lambda pair: (pair.ingredient_name, pair.unit_label))


async def decided_grams(
    session: AsyncSession, ingredient_ids: Sequence[uuid.UUID] | None = None
) -> dict[tuple[uuid.UUID, uuid.UUID | None], tuple[Decimal | None, str]]:
    """Le coppie decise: (ingrediente, unità) → (grammi o None, chi ha deciso)."""
    statement = select(
        IngredientUnitGrams.ingredient_id,
        IngredientUnitGrams.unit_id,
        IngredientUnitGrams.grams,
        IngredientUnitGrams.decided_by,
    )
    if ingredient_ids is not None:
        statement = statement.where(IngredientUnitGrams.ingredient_id.in_(list(ingredient_ids)))
    return {
        (row.ingredient_id, row.unit_id): (row.grams, row.decided_by)
        for row in (await session.execute(statement)).all()
    }


async def pending_pairs(session: AsyncSession, limit: int | None = None) -> list[Pair]:
    decided = await decided_grams(session)
    pending = [pair for pair in await used_pairs(session) if (pair.ingredient_id, pair.unit_id) not in decided]
    return pending if limit is None else pending[:limit]


async def count_pending_pairs(session: AsyncSession) -> int:
    return len(await pending_pairs(session))


async def weights_of(session: AsyncSession, ingredient_id: uuid.UUID) -> list[Weight]:
    """Le coppie di un ingrediente: quelle che le ricette usano, e quelle decise anche se
    nessuna ricetta le usa più (un peso scritto non sparisce di nascosto)."""
    decided = await decided_grams(session, [ingredient_id])
    labels: dict[uuid.UUID | None, str] = {
        pair.unit_id: pair.unit_label for pair in await used_pairs(session, ingredient_id)
    }
    extra = [unit_id for (_, unit_id) in decided if unit_id is not None and unit_id not in labels]
    if extra:
        for unit_id, key, singular in (
            await session.execute(select(Unit.id, Unit.key, Unit.singular).where(Unit.id.in_(extra)))
        ).all():
            labels[unit_id] = unit_label(key, singular)
    if (ingredient_id, None) in decided:
        labels.setdefault(None, PIECE_LABEL)
    weights = []
    for unit_id, label in labels.items():
        if (ingredient_id, unit_id) not in decided:
            weights.append(Weight(unit_param(unit_id), label, None, "undecided", None))
            continue
        grams, decided_by = decided[(ingredient_id, unit_id)]
        state = "none" if grams is None else "decided"
        weights.append(Weight(unit_param(unit_id), label, grams, state, decided_by))
    return sorted(weights, key=lambda weight: weight.unit_label)


async def resolve_pair_unit(
    session: AsyncSession, unit_id: uuid.UUID | None
) -> tuple[uuid.UUID | None, str, UnitKind]:
    """L'unità della coppia (canonica, o None per il pezzo), il suo nome e il suo tipo."""
    if unit_id is None:
        return None, PIECE_LABEL, classify_unit(None, None)
    unit = await session.get(Unit, unit_id)
    if unit is None:
        raise LookupError(f"nessuna unità {unit_id}")
    canonical = unit if unit.canonical_id is None else await session.get(Unit, unit.canonical_id)
    kind = classify_unit(canonical.key, canonical.singular)
    return (None if kind.piece else canonical.id), unit_label(canonical.key, canonical.singular), kind


async def _food(session: AsyncSession, ingredient_id: uuid.UUID) -> Ingredient:
    ingredient = await session.get(Ingredient, ingredient_id)
    if ingredient is None:
        raise LookupError(f"nessun ingrediente {ingredient_id}")
    if ingredient.kind != IngredientKind.FOOD:
        raise NutritionRefusal(
            NON_FOOD_CODE,
            f"«{ingredient.display_name}» non è un alimento: non ha valori nutrizionali.",
        )
    return ingredient


async def set_grams(
    session: AsyncSession, ingredient_id: uuid.UUID, unit_id: uuid.UUID | None, grams: Decimal
) -> list[Weight]:
    """Il peso a mano. Vince sempre, anche su quello dell'AI."""
    await _food(session, ingredient_id)
    pair_unit, label, kind = await resolve_pair_unit(session, unit_id)
    if kind.measure != "pair":
        raise NutritionRefusal(
            MEASURED_UNIT_CODE,
            f"«{label}» è un'unità di peso o di volume: i grammi si contano da sé.",
        )
    refusal = NutritionRefusal(
        BAD_GRAMS_CODE, "Un peso va da più di 0 a 5000 g: controlla il numero."
    )
    if not grams.is_finite():
        raise refusal
    # la colonna è Numeric(8, 2): si controlla il valore che finirebbe scritto, non quello
    # grezzo (0,001 diventa 0,00 e romperebbe il CHECK invece di essere rifiutato)
    try:
        grams = grams.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:  # troppo grande per la precisione del contesto
        raise refusal from None
    if not Decimal("0") < grams <= GRAMS_MAX:
        raise refusal
    statement = pg_insert(IngredientUnitGrams).values(
        id=uuid.uuid4(),
        ingredient_id=ingredient_id,
        unit_id=pair_unit,
        grams=grams,
        decided_by=NutritionDecider.HUMAN,
        decided_at=func.now(),
    )
    await session.execute(
        statement.on_conflict_do_update(
            constraint="uq_ingredient_unit_grams",
            set_={
                "grams": statement.excluded.grams,
                "decided_by": statement.excluded.decided_by,
                "decided_at": statement.excluded.decided_at,
            },
        )
    )
    return await weights_of(session, ingredient_id)


async def clear_grams(
    session: AsyncSession, ingredient_id: uuid.UUID, unit_id: uuid.UUID | None
) -> list[Weight]:
    """L'annullamento: la coppia torna da decidere, e l'AI la riprenderà."""
    await _food(session, ingredient_id)
    pair_unit, _, _ = await resolve_pair_unit(session, unit_id)
    await session.execute(
        delete(IngredientUnitGrams).where(
            IngredientUnitGrams.ingredient_id == ingredient_id, _same_unit(pair_unit)
        )
    )
    return await weights_of(session, ingredient_id)


async def apply_ai_grams(
    session: AsyncSession, ingredient_id: uuid.UUID, unit_id: uuid.UUID | None, grams: Decimal | None
) -> bool:
    """Il peso dell'AI (o «nessun peso», `None`), solo dove non c'è niente. `True` se l'ha
    scritto. `unit_id` è già quella della coppia (canonica, o None)."""
    result = await session.execute(
        pg_insert(IngredientUnitGrams)
        .values(
            id=uuid.uuid4(),
            ingredient_id=ingredient_id,
            unit_id=unit_id,
            grams=grams,
            decided_by=NutritionDecider.AI,
        )
        .on_conflict_do_nothing()
    )
    return result.rowcount == 1


# Quaranta coppie per chiamata: una risposta è ~30 token a coppia, ~1.200 per lotto, ben
# sotto il tetto. Le 800–1.500 coppie stimate per la produzione (spec §3) sono 20–40
# chiamate, meno di 0,05 $. Un lotto a cui l'AI risponde in modo illeggibile si divide a
# metà fino alla coppia sola (`decide_grams`): le misure non cambiano, cambia solo quante
# coppie porta la domanda che segue un guasto della risposta.
GRAMS_BATCH = 40
GRAMS_MAX_TOKENS = 3000
GRAMS_ALL_BROKEN = "nessuna coppia del lotto ha avuto una risposta leggibile, nemmeno da sola"

GRAMS_SYSTEM_PROMPT = (
    "Ricevi un elenco numerato di coppie ingrediente e unità di misura, prese da ricette "
    "italiane, ciascuna con un esempio di dose. Per ognuna scrivi quanti grammi pesa UNA "
    "unità di quell'ingrediente: il peso netto della parte che si mangia (senza buccia, "
    "guscio, osso o torsolo), per un pezzo di misura media. «pezzo» vuol dire un pezzo "
    "intero: un uovo, una cipolla, un limone.\n\n"
    "Regole:\n"
    '- "n", "ingrediente" e "unita" vanno riscritti identici a come te li ho passati.\n'
    '- "grammi" è un numero maggiore di zero; null se quell\'unità, per quell\'ingrediente, '
    "non ha un peso sensato.\n"
    "- Una risposta per ogni coppia, nessuna in più."
)

GRAMS_SCHEMA = {
    "type": "object",
    "properties": {
        "pesi": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "ingrediente": {"type": "string"},
                    "unita": {"type": "string"},
                    "grammi": {"anyOf": [{"type": "number"}, {"type": "null"}]},
                },
                "required": ["n", "ingrediente", "unita", "grammi"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["pesi"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class PairQuestion:
    ingredient: str
    unit_label: str
    example: str | None


def _read_grams(value: object) -> tuple[bool, Decimal | None]:
    """(si può applicare, grammi): `None` è «nessun peso»; un numero fuori misura, una
    stringa o un booleano non si applicano. Un numero enorme (1e30, un intero di 400 cifre)
    si rifiuta come gli altri: non deve fermare il giro."""
    if value is None:
        return True, None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False, None
    try:
        raw = Decimal(str(value))
        # prima la misura sul valore grezzo, poi l'arrotondamento: un 1e30 non arriva al quantize
        if not raw.is_finite() or not Decimal("0") < raw <= GRAMS_MAX + Decimal("0.005"):
            return False, None
        grams = raw.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except (InvalidOperation, OverflowError, ValueError):
        return False, None
    if not Decimal("0") < grams <= GRAMS_MAX:
        return False, None
    return True, grams


def _same_text(answer: dict, field: str, expected: str) -> bool:
    return str(answer.get(field) or "").strip().casefold() == expected.casefold()


async def ask_grams(
    session: AsyncSession,
    questions: Sequence[PairQuestion],
    client: AsyncAnthropic | None = None,
    spend: Spend | None = None,
) -> tuple[dict[int, Decimal | None], int]:
    """I pesi delle coppie chieste, per indice (da 0), e quante risposte si sono rifiutate.
    Una coppia che manca dal dizionario non ha avuto una risposta verificabile."""
    asked = dict(enumerate(questions, start=1))
    question = {
        "coppie": [
            {"n": n, "ingrediente": item.ingredient, "unita": item.unit_label, "esempio": item.example}
            for n, item in asked.items()
        ]
    }
    data = await complete_recorded(
        session,
        call_site=LlmCallSite.UNIT_GRAMS,
        system=GRAMS_SYSTEM_PROMPT,
        user=json.dumps(question, ensure_ascii=False),
        schema=GRAMS_SCHEMA,
        max_tokens=GRAMS_MAX_TOKENS,
        client=client,
        spend=spend,
    )
    weights: dict[int, Decimal | None] = {}
    refused = 0
    answered: set[int] = set()
    for answer in data.get("pesi") or []:
        if not isinstance(answer, dict):
            refused += 1
            continue
        n = answer.get("n")
        if type(n) is not int or n not in asked or n in answered:
            refused += 1
            continue
        item = asked[n]
        if not _same_text(answer, "ingrediente", item.ingredient) or not _same_text(
            answer, "unita", item.unit_label
        ):
            refused += 1
            continue
        answered.add(n)
        ok, grams = _read_grams(answer.get("grammi"))
        if not ok:
            refused += 1
            continue
        weights[n - 1] = grams
    return weights, refused


@dataclass(frozen=True)
class GramsRun:
    """Quel che un lancio ha fatto, e quel che resta."""

    weighed: int = 0
    none: int = 0
    refused: int = 0
    # le coppie ancora da pesare alla fine, non solo quelle del `--limit`
    pending: int = 0
    unavailable: str | None = None
    asked: int = 0
    # le coppie a cui l'AI non ha dato una risposta leggibile nemmeno da sole, in questo
    # giro: «‹ingrediente› × ‹unità›». Restano da pesare, e sono contate in `pending`
    skipped: tuple[str, ...] = ()
    # l'errore dell'ultima coppia saltata
    last_error: str | None = None


# I tipi di una risposta arrivata ma inutilizzabile: `TRUNCATED` (tagliata al tetto dei
# token) e `INVALID` (non JSON, non un oggetto, senza testo; `complete_json` dà lo stesso
# tipo anche a un 200 che non è un messaggio). Dicono qualcosa del lotto — una coppia può
# rompere la risposta di tutte — e per questo dividerlo serve. I guasti di passaggio
# (`TRANSIENT`: rete, tempo, 5xx) e i terminali (`TERMINAL_LLM_FAILURES`: chiave, credito,
# frequenza, richiesta rifiutata) no: non dicono niente del lotto, e dividere in
# un'interruzione di rete moltiplicherebbe le chiamate per niente (decisione 10 del piano
# 2026-11-21-s4-candidati); fermano il giro come prima. Il rifiuto del modello (`REFUSAL`)
# resta fuori anche lui: non è una risposta rotta, e ferma il giro come prima. Se un
# `INVALID` non dipende dal lotto, il freno di `decide_grams` tiene il costo limitato.
_UNUSABLE_ANSWERS = frozenset({LlmFailureKind.TRUNCATED, LlmFailureKind.INVALID})


def _answer_unusable(exc: LlmUnavailable) -> bool:
    return exc.kind in _UNUSABLE_ANSWERS


@dataclass
class _Tally:
    weighed: int = 0
    none: int = 0
    refused: int = 0
    skipped: list[str] = field(default_factory=list)
    last_error: str | None = None


async def _weigh(
    session: AsyncSession, pairs: Sequence[Pair], client: AsyncAnthropic | None, tally: _Tally
) -> None:
    """Chiede i pesi di `pairs` e li applica. Una risposta illeggibile divide le coppie a
    metà e richiede le due metà; una coppia sola che non si legge si salta. Ogni altro
    guasto risale, con quel che le metà prima hanno già scritto."""
    try:
        answers, bad = await ask_grams(
            session,
            [PairQuestion(pair.ingredient_name, pair.unit_label, pair.example) for pair in pairs],
            client=client,
        )
    except LlmUnavailable as exc:
        if not _answer_unusable(exc):
            raise
        if len(pairs) == 1:
            pair = pairs[0]
            tally.skipped.append(f"{pair.ingredient_name} × {pair.unit_label}")
            tally.last_error = str(exc)
            return
        mid = len(pairs) // 2
        await _weigh(session, pairs[:mid], client, tally)
        await _weigh(session, pairs[mid:], client, tally)
        return
    tally.refused += bad
    for index, grams in answers.items():
        pair = pairs[index]
        if await apply_ai_grams(session, pair.ingredient_id, pair.unit_id, grams):
            if grams is None:
                tally.none += 1
            else:
                tally.weighed += 1


async def decide_grams(
    session: AsyncSession,
    client: AsyncAnthropic | None = None,
    limit: int | None = None,
    after_batch: Callable[[], Awaitable[None]] | None = None,
    batch_size: int = GRAMS_BATCH,
) -> GramsRun:
    """Pesa le coppie da decidere, le prime `limit` per ingrediente e unità. Non fa
    commit: lo fa `after_batch` dopo ogni lotto.

    Un lotto a cui l'AI risponde in modo illeggibile (troncato, non JSON, fuori schema) si
    divide a metà e si richiedono le due metà, fino alla coppia sola; una coppia che non si
    legge nemmeno da sola si salta per questo giro — resta da pesare, finisce in `skipped`
    e un giro dopo si richiede — e il giro va avanti. Il freno: se di un lotto tutte le
    coppie sono state saltate, il guasto non è nel lotto, e il giro si ferma con
    `GRAMS_ALL_BROKEN`. Ogni altro guasto dell'AI ferma subito il giro, anche a metà di una
    divisione, e quel che è già scritto resta."""
    pairs = await pending_pairs(session, limit)
    tally = _Tally()
    unavailable: str | None = None
    for start in range(0, len(pairs), batch_size):
        chunk = pairs[start : start + batch_size]
        skipped_before = len(tally.skipped)
        try:
            await _weigh(session, chunk, client, tally)
        except LlmUnavailable as exc:
            unavailable = str(exc)
            break
        await session.flush()
        if after_batch is not None:
            await after_batch()
        if len(tally.skipped) - skipped_before == len(chunk):
            unavailable = f"{GRAMS_ALL_BROKEN}: {tally.last_error}"
            break
    return GramsRun(
        weighed=tally.weighed,
        none=tally.none,
        refused=tally.refused,
        pending=await count_pending_pairs(session),
        unavailable=unavailable,
        asked=len(pairs),
        skipped=tuple(tally.skipped),
        last_error=tally.last_error,
    )
