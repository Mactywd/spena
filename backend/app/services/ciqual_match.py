"""L'AI abbina un ingrediente all'alimento CIQUAL che gli dà i nutrienti (S4, fetta 1).

Due passi, perché in produzione la ricerca semantica è spenta e i trigrammi fra italiano e
francese non si incontrano («pomodoro» / «tomate») — spec §4.9–4.12:

1. **le parole di ricerca**: a lotti di `TERMS_BATCH` nomi italiani, l'AI scrive da una a
   tre parole in francese, come le scriverebbe CIQUAL (sezione `ciqual_terms`);
2. **la scelta**: con quelle parole `pg_trgm` trova i candidati veri nella tabella
   (`find_candidates`); il nome italiano si cerca solo se le parole non trovano niente
   (aggiunto sempre portava rumore: «sale» → «Salers»). L'AI sceglie il codice di uno
   dei **suoi** candidati, o `null` se nessuno è quell'ingrediente (sezione
   `ciqual_match`).

L'AI non può inventare un codice: uno che non è fra i candidati di quell'ingrediente non
si applica. Come in `decide_emoji`, i nomi si numerano e la risposta riporta numero e
nome: in un lotto un modello piccolo può scivolare di una riga, e il nome lo fa vedere.
Lo schema stretto è una forma, non una verifica: la verifica è qui.

Un ingrediente per cui la ricerca non trova nemmeno un candidato è «nessun alimento
adatto», senza chiedere la scelta; lo stesso per `null` dall'AI. Si scrive, e il giro dopo
non lo richiede (deciso da Mattia il 2026-10-13): «Annulla la scelta» in Anagrafica lo
rimette da decidere.

`match_names` lavora sui nomi e non scrive: la usa anche il pilota. `decide_ciqual` è il
giro sugli ingredienti, e scrive con `apply_ai_choice`, solo dove non c'è niente.
"""

import json
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from anthropic import AsyncAnthropic
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.ingredient import Ingredient
from app.db.models.nutrition import IngredientNutrition
from app.domain.rules import IngredientKind
from app.repositories.ciqual import Candidate, find_candidates
from app.services.ai_spend import Spend, complete_recorded
from app.services.ingredient_nutrition import apply_ai_choice
from app.services.llm import LlmCallSite, LlmUnavailable

# 25 nomi per le parole: una risposta è ~25 token a nome, ~600 per lotto. ~36 chiamate
# sui ~900 ingredienti di produzione.
TERMS_BATCH = 25
TERMS_MAX_TOKENS = 3000
# 10 ingredienti per la scelta: ognuno porta fino a 15 candidati (~25 token l'uno), cioè
# ~4.000 token di domanda per lotto e una risposta corta. ~90 chiamate in produzione.
CHOICE_BATCH = 10
CHOICE_MAX_TOKENS = 1500
CANDIDATES = 15
MAX_TERMS = 3
TERM_MAX_LENGTH = 80

TERMS_SYSTEM_PROMPT = (
    "Ricevi un elenco numerato di ingredienti di ricette italiane, ciascuno col suo reparto "
    "del supermercato. Per ognuno scrivi da una a tre parole di ricerca in francese, come le "
    "scriverebbe la tabella di composizione degli alimenti CIQUAL dell'Anses: il nome "
    'dell\'alimento e, se serve, il suo stato (per esempio "tomate crue", "pâtes sèches", '
    '"huile d\'olive").\n\n'
    "Regole:\n"
    '- "n" e "nome" vanno riscritti identici a come te li ho passati.\n'
    "- Pensa all'ingrediente come lo pesa una ricetta: crudo se si cucina, secco se si "
    "compra secco.\n"
    "- Una risposta per ogni ingrediente, nessuna in più."
)

TERMS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "ingredienti": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "nome": {"type": "string"},
                    "termini": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["n", "nome", "termini"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["ingredienti"],
    "additionalProperties": False,
}

CHOICE_SYSTEM_PROMPT = (
    "Ricevi un elenco numerato di ingredienti di ricette italiane. Per ognuno ti do dei "
    "candidati presi dalla tabella CIQUAL dell'Anses (nomi in francese, col loro gruppo). "
    "Scegli il codice del candidato che è proprio quell'ingrediente, nello stato in cui una "
    "ricetta lo pesa: crudo se si cucina, secco se si compra secco (pasta, riso, legumi "
    "secchi), intero se non è detto altro.\n\n"
    "Regole:\n"
    "- Carne e pesce: senza pelle né ossa, se il nome non dice altro (per esempio "
    '"petto di pollo" è "filet sans peau", non "viande et peau").\n'
    '- "n" e "nome" vanno riscritti identici a come te li ho passati.\n'
    '- "codice" è uno dei codici dei candidati di quell\'ingrediente, oppure null se nessun '
    "candidato è quell'ingrediente: meglio nessun valore che uno sbagliato.\n"
    "- Una risposta per ogni ingrediente, nessuna in più."
)

CHOICE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "scelte": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "n": {"type": "integer"},
                    "nome": {"type": "string"},
                    "codice": {"anyOf": [{"type": "string"}, {"type": "null"}]},
                },
                "required": ["n", "nome", "codice"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["scelte"],
    "additionalProperties": False,
}


@dataclass(frozen=True)
class NameToMatch:
    name: str
    category: str


@dataclass(frozen=True)
class Matched:
    # None = «nessun alimento adatto»
    code: str | None
    # quanti candidati ha visto l'AI: 0 se la ricerca non ne ha trovati
    candidates: int


@dataclass(frozen=True)
class Searched:
    """Cosa si è cercato per un nome: le parole dell'AI, quanti candidati ha visto la
    scelta, e se venivano dal nome italiano (il ripiego quando le parole non trovano
    niente)."""

    terms: tuple[str, ...]
    candidates: int
    by_italian_name: bool = False


@dataclass(frozen=True)
class MatchBatch:
    # per nome, solo quelli decisi: un nome che manca è da decidere
    decided: dict[str, Matched]
    refused: int = 0
    unavailable: str | None = None
    # per nome, ogni nome le cui parole si sono verificate, anche se poi la scelta è stata
    # rifiutata o l'AI si è fermata prima di sceglierlo: è il perché di un caso mancato
    searched: dict[str, Searched] = field(default_factory=dict)


def _numbered(answer: object, asked: dict[int, Any], answered: set[int]) -> int | None:
    """Il numero di una risposta, se è uno di quelli chiesti e non già risposto."""
    if not isinstance(answer, dict):
        return None
    n = answer.get("n")
    if type(n) is not int or n not in asked or n in answered:
        return None
    return n


def _same_name(answer: dict, name: str) -> bool:
    return str(answer.get("nome") or "").strip().casefold() == name.casefold()


async def _ask_terms(
    session: AsyncSession,
    chunk: Sequence[NameToMatch],
    client: AsyncAnthropic | None,
    spend: Spend | None,
) -> tuple[dict[str, list[str]], int]:
    asked = dict(enumerate(chunk, start=1))
    question = {
        "ingredienti": [
            {"n": n, "nome": item.name, "reparto": item.category} for n, item in asked.items()
        ]
    }
    data = await complete_recorded(
        session,
        call_site=LlmCallSite.CIQUAL_TERMS,
        system=TERMS_SYSTEM_PROMPT,
        user=json.dumps(question, ensure_ascii=False),
        schema=TERMS_SCHEMA,
        max_tokens=TERMS_MAX_TOKENS,
        client=client,
        spend=spend,
    )
    terms: dict[str, list[str]] = {}
    refused = 0
    answered: set[int] = set()
    for answer in data.get("ingredienti") or []:
        n = _numbered(answer, asked, answered)
        if n is None or not _same_name(answer, asked[n].name):
            refused += 1
            continue
        answered.add(n)
        words = [
            word.strip()
            for word in answer.get("termini") or []
            if isinstance(word, str) and word.strip() and len(word.strip()) <= TERM_MAX_LENGTH
        ][:MAX_TERMS]
        if not words:
            refused += 1
            continue
        terms[asked[n].name] = words
    return terms, refused


async def _ask_choices(
    session: AsyncSession,
    group: Sequence[tuple[NameToMatch, list[Candidate]]],
    client: AsyncAnthropic | None,
    spend: Spend | None,
) -> tuple[dict[str, Matched], int]:
    asked = dict(enumerate(group, start=1))
    question = {
        "ingredienti": [
            {
                "n": n,
                "nome": item.name,
                "candidati": [
                    {"codice": c.code, "nome": c.name_fr, "gruppo": c.group_fr} for c in candidates
                ],
            }
            for n, (item, candidates) in asked.items()
        ]
    }
    data = await complete_recorded(
        session,
        call_site=LlmCallSite.CIQUAL_MATCH,
        system=CHOICE_SYSTEM_PROMPT,
        user=json.dumps(question, ensure_ascii=False),
        schema=CHOICE_SCHEMA,
        max_tokens=CHOICE_MAX_TOKENS,
        client=client,
        spend=spend,
    )
    chosen: dict[str, Matched] = {}
    refused = 0
    answered: set[int] = set()
    for answer in data.get("scelte") or []:
        n = _numbered(answer, asked, answered)
        if n is None or not _same_name(answer, asked[n][0].name):
            refused += 1
            continue
        answered.add(n)
        item, candidates = asked[n]
        code = answer.get("codice")
        if code is not None:
            code = code.strip() if isinstance(code, str) else None
            if code not in {candidate.code for candidate in candidates}:
                refused += 1
                continue
        chosen[item.name] = Matched(code=code, candidates=len(candidates))
    return chosen, refused


async def match_names(
    session: AsyncSession,
    names: Sequence[NameToMatch],
    client: AsyncAnthropic | None = None,
    spend: Spend | None = None,
) -> MatchBatch:
    """Abbina i nomi, a lotti, senza scrivere niente. Al primo guasto dell'AI si ferma e
    torna quel che ha già deciso: chiedere oltre sarebbe pagare per sapere che è giù."""
    decided: dict[str, Matched] = {}
    searched: dict[str, Searched] = {}
    refused = 0
    for start in range(0, len(names), TERMS_BATCH):
        chunk = names[start : start + TERMS_BATCH]
        try:
            terms, bad = await _ask_terms(session, chunk, client, spend)
        except LlmUnavailable as exc:
            return MatchBatch(decided, refused, str(exc), searched)
        refused += bad
        with_candidates: list[tuple[NameToMatch, list[Candidate]]] = []
        for item in chunk:
            if item.name not in terms:
                continue
            candidates = await find_candidates(session, terms[item.name], limit=CANDIDATES)
            # Il nome italiano solo come ripiego (decisione 6 del piano s4-candidati):
            # aggiunto sempre porta rumore fra candidati già giusti; da solo, quando le
            # parole non trovano niente, recupera i nomi che CIQUAL scrive in italiano.
            by_italian = False
            if not candidates:
                candidates = await find_candidates(session, [item.name], limit=CANDIDATES)
                by_italian = bool(candidates)
            searched[item.name] = Searched(tuple(terms[item.name]), len(candidates), by_italian)
            if not candidates:
                decided[item.name] = Matched(code=None, candidates=0)
                continue
            with_candidates.append((item, candidates))
        for group_start in range(0, len(with_candidates), CHOICE_BATCH):
            group = with_candidates[group_start : group_start + CHOICE_BATCH]
            try:
                chosen, bad = await _ask_choices(session, group, client, spend)
            except LlmUnavailable as exc:
                return MatchBatch(decided, refused, str(exc), searched)
            refused += bad
            decided.update(chosen)
    return MatchBatch(decided, refused, None, searched)


@dataclass(frozen=True)
class CiqualRun:
    """Quel che un lancio ha fatto, e quel che resta."""

    matched: int = 0
    none: int = 0
    # dentro `none`: quelli per cui la ricerca non ha trovato nemmeno un candidato,
    # nemmeno col nome italiano (la ricerca ha mancato, non l'AI ha detto no)
    no_candidates: int = 0
    refused: int = 0
    # gli ingredienti alimentari ancora da decidere alla fine, non solo quelli del
    # `--limit`: è la riga che dice a Mattia se rilanciare
    pending: int = 0
    unavailable: str | None = None
    asked: int = 0


def _pending_ingredients():
    return (
        select(Ingredient.id, Ingredient.name, Ingredient.category)
        .outerjoin(IngredientNutrition, IngredientNutrition.ingredient_id == Ingredient.id)
        .where(IngredientNutrition.ingredient_id.is_(None), Ingredient.kind == IngredientKind.FOOD)
    )


async def count_pending(session: AsyncSession) -> int:
    return (
        await session.execute(select(func.count()).select_from(_pending_ingredients().subquery()))
    ).scalar_one()


async def decide_ciqual(
    session: AsyncSession,
    client: AsyncAnthropic | None = None,
    limit: int | None = None,
    after_batch: Callable[[], Awaitable[None]] | None = None,
    batch_size: int = TERMS_BATCH,
) -> CiqualRun:
    """Abbina gli ingredienti alimentari da decidere, i primi `limit` per nome.

    Non fa commit: lo fa `after_batch`, se c'è, dopo ogni lotto (il comando passa
    `session.commit`). Al primo guasto dell'AI si ferma, dopo aver scritto quel che il
    lotto aveva già deciso.
    """
    statement = _pending_ingredients().order_by(Ingredient.name)
    if limit is not None:
        statement = statement.limit(limit)
    rows = (await session.execute(statement)).all()
    matched = none = no_candidates = refused = 0
    unavailable: str | None = None
    for start in range(0, len(rows), batch_size):
        chunk = rows[start : start + batch_size]
        by_name = {row.name: row.id for row in chunk}
        result = await match_names(
            session, [NameToMatch(row.name, row.category) for row in chunk], client=client
        )
        refused += result.refused
        for name, decision in result.decided.items():
            if await apply_ai_choice(session, by_name[name], decision.code):
                if decision.code is None:
                    none += 1
                    if decision.candidates == 0:
                        no_candidates += 1
                else:
                    matched += 1
        await session.flush()
        if after_batch is not None:
            await after_batch()
        if result.unavailable is not None:
            unavailable = result.unavailable
            break
    return CiqualRun(
        matched=matched,
        none=none,
        no_candidates=no_candidates,
        refused=refused,
        pending=await count_pending(session),
        unavailable=unavailable,
        asked=len(rows),
    )
