"""Calcola i vettori delle ricette che non ne hanno.

Eseguire con `python -m app.cli.reindex` dentro il container del backend, dopo un
import, se si tiene accesa la ricerca semantica (`INSTALL_EMBEDDINGS=1`).

Esiste perché una ricetta salvata senza vettore non lo riceveva mai più: il seme è
idempotente e non torna sulle ricette già presenti, e l'import eredita la stessa
proprietà. Con 26 ricette era un fastidio, con 500 è la ricerca semantica spenta per
sempre.
"""

import asyncio

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.recipe import Recipe
from app.services.embeddings import get_embedding_provider

# a lotti, perché un ricettario grande non deve entrare tutto in memoria insieme
BATCH = 64


async def reindex(session: AsyncSession) -> int:
    """Scrive i vettori mancanti e restituisce quanti.

    `EmbeddingUnavailable` risale al chiamante di proposito: un comando che
    «riesce» scrivendo zero vettori è indistinguibile da uno che non serviva, e la
    differenza è esattamente ciò che si vuole sapere.
    """
    provider = get_embedding_provider()
    written = 0
    while True:
        rows = await session.execute(
            select(Recipe).where(Recipe.embedding.is_(None)).limit(BATCH)
        )
        batch = list(rows.scalars())
        if not batch:
            return written
        texts = [f"{recipe.title}. {recipe.description or ''}" for recipe in batch]
        vectors = await provider.embed_passages(texts)
        for recipe, vector in zip(batch, vectors, strict=True):
            recipe.embedding = vector
        await session.flush()
        written += len(batch)


async def main() -> None:
    async with SessionLocal() as session:
        scritti = await reindex(session)
        await session.commit()
    if scritti:
        print(f"scritti {scritti} vettori: la ricerca semantica li vede adesso")
    else:
        print("nessun vettore da scrivere: tutte le ricette ne hanno già uno")


if __name__ == "__main__":
    asyncio.run(main())
