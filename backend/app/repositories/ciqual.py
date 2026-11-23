"""La tabella CIQUAL nel database (S4, fetta 1): scriverla, contarla, cercarla.

I candidati di un ingrediente si trovano con `word_similarity` di `pg_trgm` sui nomi
francesi, una parola di ricerca alla volta; a parità di punteggio vince il nome che
comincia con la prima parola del termine, poi la somiglianza di tutto il nome (vedi
`find_candidates`). Niente `unaccent`: vorrebbe una migrazione, e sulla tabella vera non
cambia i posti. Non e5: in produzione la ricerca semantica è spenta
(`INSTALL_EMBEDDINGS=0`, spec §3), e i trigrammi fra italiano e francese non si
incontrano — per questo le parole francesi le scrive l'AI (`services/ciqual_match.py`).
Le tremila righe si leggono intere a ogni domanda: è meno di un millisecondo per riga,
e un indice non varrebbe la migrazione.
"""

import re
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import CiqualFood
from app.domain.ciqual import CIQUAL_VERSION, CiqualRow
from app.domain.suggestions import FOLD_FROM, FOLD_TO, fold_for_match

# Sotto questa somiglianza un alimento non è un candidato: l'AI sceglierebbe fra rumore.
CANDIDATE_MIN_SIMILARITY = 0.3
# Nella ricerca di Anagrafica si vuole di più: lì c'è anche il pezzo di nome esatto.
SEARCH_MIN_SIMILARITY = 0.4
UPSERT_CHUNK = 500


@dataclass(frozen=True)
class Candidate:
    code: str
    name_fr: str
    group_fr: str | None
    score: float


async def upsert_foods(
    session: AsyncSession, foods: Sequence[CiqualRow], version: str = CIQUAL_VERSION
) -> int:
    """Scrive o aggiorna per codice. Non cancella niente: un alimento che il file non ha
    più resta, perché un ingrediente può averlo scelto (`RESTRICT`)."""
    for start in range(0, len(foods), UPSERT_CHUNK):
        chunk = foods[start : start + UPSERT_CHUNK]
        statement = pg_insert(CiqualFood).values(
            [
                {
                    "code": food.code,
                    "name_fr": food.name_fr,
                    "group_fr": food.group_fr,
                    "nutrients": food.nutrients,
                    "version": version,
                }
                for food in chunk
            ]
        )
        await session.execute(
            statement.on_conflict_do_update(
                index_elements=[CiqualFood.code],
                set_={
                    "name_fr": statement.excluded.name_fr,
                    "group_fr": statement.excluded.group_fr,
                    "nutrients": statement.excluded.nutrients,
                    "version": statement.excluded.version,
                },
            )
        )
    return len(foods)


async def count_foods(session: AsyncSession) -> int:
    return (await session.execute(select(func.count()).select_from(CiqualFood))).scalar_one()


async def count_missing_from(session: AsyncSession, codes: set[str]) -> int:
    """Quanti alimenti nel database il file non ha."""
    return (
        await session.execute(
            select(func.count()).select_from(CiqualFood).where(CiqualFood.code.not_in(sorted(codes)))
        )
    ).scalar_one()


async def get_food(session: AsyncSession, code: str) -> CiqualFood | None:
    # `populate_existing`: dopo un caricamento (una INSERT … ON CONFLICT, che l'identity
    # map non vede) l'oggetto in memoria potrebbe essere quello vecchio
    return (
        await session.execute(
            select(CiqualFood)
            .where(CiqualFood.code == code)
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()


async def find_candidates(
    session: AsyncSession,
    terms: Sequence[str],
    limit: int,
    min_similarity: float = CANDIDATE_MIN_SIMILARITY,
) -> list[Candidate]:
    """I migliori `limit` alimenti per almeno una delle parole, ciascuno col suo
    punteggio migliore.

    `word_similarity` vale 1 per ogni nome che contiene la parola: sulla tabella vera
    «riz» ne lega 43, e a parità l'ordine alfabetico metteva «Amidon de riz» e «Boisson
    au riz» prima di «Riz blanc, cru», lasciando fuori l'alimento semplice. Per questo, a
    parità, prima il nome che comincia con la prima parola del termine, poi la
    `similarity` di tutto il nome, poi il nome. Lo stesso ordine vale nella query di
    ogni parola e nell'unione, dove ogni alimento tiene il massimo di ciascuna delle tre
    misure fra le parole che lo hanno trovato. `Candidate.score` resta la
    `word_similarity` migliore.
    """
    # codice → (candidato, comincia con la parola, somiglianza di tutto il nome)
    best: dict[str, tuple[Candidate, bool, float]] = {}
    for term in terms:
        score = func.word_similarity(term, CiqualFood.name_fr)
        starts = func.lower(CiqualFood.name_fr).startswith(_first_word(term), autoescape=True)
        closeness = func.similarity(term, CiqualFood.name_fr)
        rows = (
            await session.execute(
                select(
                    CiqualFood.code,
                    CiqualFood.name_fr,
                    CiqualFood.group_fr,
                    score.label("score"),
                    starts.label("starts"),
                    closeness.label("closeness"),
                )
                .where(score >= min_similarity)
                .order_by(score.desc(), starts.desc(), closeness.desc(), CiqualFood.name_fr)
                .limit(limit)
            )
        ).all()
        for row in rows:
            known = best.get(row.code)
            if known is None:
                best[row.code] = (
                    Candidate(row.code, row.name_fr, row.group_fr, float(row.score)),
                    bool(row.starts),
                    float(row.closeness),
                )
                continue
            candidate, known_starts, known_closeness = known
            best[row.code] = (
                Candidate(
                    candidate.code, candidate.name_fr, candidate.group_fr,
                    max(candidate.score, float(row.score)),
                ),
                known_starts or bool(row.starts),
                max(known_closeness, float(row.closeness)),
            )
    ranked = sorted(
        best.values(),
        key=lambda found: (-found[0].score, not found[1], -found[2], found[0].name_fr),
    )
    return [candidate for candidate, _, _ in ranked[:limit]]


def _first_word(term: str) -> str:
    """La prima parola del termine, in minuscolo: lettere, cifre, apostrofi e trattini
    («Riz, cru» → «riz», «huile d'olive» → «huile», «(riz)» → «riz»)."""
    match = re.search(r"[\w'’-]+", term.lower())
    return match.group() if match else ""


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def _folded_name():
    """Il nome francese come lo confronta la ricerca: minuscolo, senza accenti, apostrofi
    e trattini in spazi, spazi (a capo compresi) ridotti a uno."""
    return func.regexp_replace(
        func.translate(func.lower(CiqualFood.name_fr), FOLD_FROM, FOLD_TO), r"\s+", " ", "g"
    )


async def search_foods(session: AsyncSession, query: str, limit: int) -> list[CiqualFood]:
    """La ricerca della correzione in Anagrafica: il codice esatto prima, poi il pezzo di
    nome e la somiglianza. `%` e `_` sono lettere, non jolly.

    Il nome e il testo cercato si piegano come nei suggerimenti (`FOLD_FROM`/`FOLD_TO`):
    «pates» trova «Pâtes». È la `translate()` e non `unaccent`, che vorrebbe una
    migrazione per l'estensione; copre ogni lettera dei nomi del file. Il codice esatto
    si confronta col testo com'è. A parità di `word_similarity` (1 per ogni nome che
    contiene la parola) vale lo spareggio di `find_candidates`: prima il nome che comincia
    con la prima parola, poi la `similarity` di tutto il nome, poi il nome.
    """
    code = query.strip()
    text = fold_for_match(code.lower())
    if not text:
        return []
    name = _folded_name()
    score = func.word_similarity(text, name)
    exact = CiqualFood.code == code
    starts = name.startswith(_first_word(text), autoescape=True)
    return list(
        (
            await session.execute(
                select(CiqualFood)
                .where(
                    or_(
                        exact,
                        name.ilike(f"%{_escape_like(text)}%", escape="\\"),
                        score >= SEARCH_MIN_SIMILARITY,
                    )
                )
                .order_by(
                    exact.desc(),
                    score.desc(),
                    starts.desc(),
                    func.similarity(text, name).desc(),
                    CiqualFood.name_fr,
                )
                .limit(limit)
            )
        ).scalars()
    )
