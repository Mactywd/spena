"""Interrogazioni sulle due tabelle dell'import.

Le pagine in attesa si leggono più volte per giro (sincronizzazione dei termini,
materializzazione, titoli in attesa): stanno tutte qui perché la stessa query
scritta tre volte si scolla tre volte.
"""

import uuid
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.recipe_import import ImportState, ImportTerm, RecipeImport, TermDecision


@dataclass(frozen=True)
class ImportCounts:
    fetched: int
    pending_recipes: int
    imported: int
    skipped: int
    pending_terms: int


async def known_urls(session: AsyncSession, source: str) -> set[str]:
    """Gli indirizzi già presi. Non si riscarica mai una pagina due volte."""
    rows = await session.execute(
        select(RecipeImport.url).where(RecipeImport.source == source)
    )
    return set(rows.scalars())


async def store_page(
    session: AsyncSession, *, source: str, url: str, payload: dict
) -> RecipeImport:
    page = RecipeImport(
        source=source, url=url, payload=payload, state=ImportState.PENDING
    )
    session.add(page)
    await session.flush()
    return page


async def store_unparsable(
    session: AsyncSession, *, source: str, url: str, reason: str
) -> RecipeImport:
    """Una pagina illeggibile si conserva col suo motivo.

    Un import che perde in silenzio il tre per cento delle pagine è un import di cui
    non si può dire niente.
    """
    page = RecipeImport(
        source=source, url=url, payload={}, state=ImportState.SKIPPED,
        skipped_reason=reason[:200],
    )
    session.add(page)
    await session.flush()
    return page


async def pending_pages(session: AsyncSession, source: str) -> list[RecipeImport]:
    rows = await session.execute(
        select(RecipeImport)
        .where(RecipeImport.source == source, RecipeImport.state == ImportState.PENDING)
        .order_by(RecipeImport.fetched_at)
    )
    return list(rows.scalars())


async def counts(session: AsyncSession, source: str) -> ImportCounts:
    by_state = dict(
        (
            await session.execute(
                select(RecipeImport.state, func.count())
                .where(RecipeImport.source == source)
                .group_by(RecipeImport.state)
            )
        ).all()
    )
    waiting = (
        await session.execute(
            select(func.count())
            .select_from(ImportTerm)
            .where(ImportTerm.source == source, ImportTerm.decision == TermDecision.PENDING)
        )
    ).scalar_one()
    return ImportCounts(
        fetched=sum(by_state.values()),
        pending_recipes=by_state.get(ImportState.PENDING, 0),
        imported=by_state.get(ImportState.IMPORTED, 0),
        skipped=by_state.get(ImportState.SKIPPED, 0),
        pending_terms=waiting,
    )


async def pending_terms(
    session: AsyncSession, source: str, limit: int = 20
) -> list[ImportTerm]:
    """I termini da decidere, da quello che sblocca più ricette.

    È l'unico ordine in cui vale la pena revisionare: più della metà dei termini
    compare in una ricetta sola, e decidere prima i frequenti è ciò che fa vedere il
    ricettario crescere.
    """
    rows = await session.execute(
        select(ImportTerm)
        .where(ImportTerm.source == source, ImportTerm.decision == TermDecision.PENDING)
        .order_by(ImportTerm.occurrences.desc(), ImportTerm.display_name)
        .limit(limit)
    )
    return list(rows.scalars())


async def terms_by_key(session: AsyncSession, source: str) -> dict[str, ImportTerm]:
    rows = await session.execute(select(ImportTerm).where(ImportTerm.source == source))
    return {term.term_key: term for term in rows.scalars()}


async def get_term(session: AsyncSession, term_id: uuid.UUID) -> ImportTerm | None:
    return await session.get(ImportTerm, term_id)


async def waiting_titles(
    session: AsyncSession, source: str, keys: list[str], per_term: int = 3
) -> dict[str, list[str]]:
    """Qualche titolo in attesa per ogni termine chiesto.

    Serve a decidere: «Scorza di limone» si giudica diversamente in una torta e in
    un arrosto. Si scorre in Python sulle pagine in attesa, che sono le sole che
    contano e che calano a ogni decisione.
    """
    wanted = set(keys)
    titles: dict[str, list[str]] = {key: [] for key in keys}
    for page in await pending_pages(session, source):
        title = str(page.payload.get("title") or "")
        for line in page.payload.get("ingredients") or []:
            key = line.get("key")
            if key in wanted and len(titles[key]) < per_term and title not in titles[key]:
                titles[key].append(title)
    return titles
