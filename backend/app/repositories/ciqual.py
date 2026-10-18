"""La tabella CIQUAL nel database (S4, fetta 1): scriverla, contarla, cercarla.

I candidati di un ingrediente si trovano con `word_similarity` di `pg_trgm` sui nomi
francesi, una parola di ricerca alla volta. Non e5: in produzione la ricerca semantica è
spenta (`INSTALL_EMBEDDINGS=0`, spec §3), e i trigrammi fra italiano e francese non si
incontrano — per questo le parole francesi le scrive l'AI (`services/ciqual_match.py`).
Le tremila righe si leggono intere a ogni domanda: è meno di un millisecondo per riga,
e un indice non varrebbe la migrazione.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func, or_, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.nutrition import CiqualFood
from app.domain.ciqual import CIQUAL_VERSION, CiqualRow

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
    punteggio migliore; a parità, per nome."""
    best: dict[str, Candidate] = {}
    for term in terms:
        score = func.word_similarity(term, CiqualFood.name_fr)
        rows = (
            await session.execute(
                select(CiqualFood.code, CiqualFood.name_fr, CiqualFood.group_fr, score.label("score"))
                .where(score >= min_similarity)
                .order_by(score.desc(), CiqualFood.name_fr)
                .limit(limit)
            )
        ).all()
        for row in rows:
            known = best.get(row.code)
            if known is None or row.score > known.score:
                best[row.code] = Candidate(row.code, row.name_fr, row.group_fr, float(row.score))
    ranked = sorted(best.values(), key=lambda candidate: (-candidate.score, candidate.name_fr))
    return ranked[:limit]


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


async def search_foods(session: AsyncSession, query: str, limit: int) -> list[CiqualFood]:
    """La ricerca della correzione in Anagrafica: il codice esatto prima, poi il pezzo di
    nome e la somiglianza. `%` e `_` sono lettere, non jolly."""
    text = query.strip()
    if not text:
        return []
    score = func.word_similarity(text, CiqualFood.name_fr)
    exact = CiqualFood.code == text
    return list(
        (
            await session.execute(
                select(CiqualFood)
                .where(
                    or_(
                        exact,
                        CiqualFood.name_fr.ilike(f"%{_escape_like(text)}%", escape="\\"),
                        score >= SEARCH_MIN_SIMILARITY,
                    )
                )
                .order_by(exact.desc(), score.desc(), CiqualFood.name_fr)
                .limit(limit)
            )
        ).scalars()
    )
