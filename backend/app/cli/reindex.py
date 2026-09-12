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
from app.services.embeddings import (
    SEMANTIC_OFF_HOWTO,
    EmbeddingUnavailable,
    get_embedding_provider,
    log_degradation_once,
    recipe_document,
)

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
        texts = [recipe_document(recipe.title, recipe.description) for recipe in batch]
        vectors = await provider.embed_passages(texts)
        for recipe, vector in zip(batch, vectors, strict=True):
            recipe.embedding = vector
        await session.flush()
        written += len(batch)


async def main() -> None:
    """Mai un vicolo cieco: se il modello non c'è, lo dice e indica come accenderlo,
    invece di lasciar risalire un traceback fino alla shell di chi esegue il comando.

    Non fa `commit()` su questo percorso. I lotti già scritti restano nella
    transazione della sessione e vengono persi quando il blocco `async with` la
    chiude senza commit: o il giro è riuscito per intero, o il ricettario resta
    esattamente com'era prima di lanciarlo. In pratica il caso comune (modello mai
    installato) fallisce già al primo lotto, quindi non c'è nulla da perdere; ma un
    fallimento a metà giro (modello che sparisce mentre gira) non deve lasciare un
    ricettario per metà indicizzato senza che nessuno lo sappia.
    """
    async with SessionLocal() as session:
        try:
            scritti = await reindex(session)
        except EmbeddingUnavailable as exc:
            log_degradation_once(exc)
            print(SEMANTIC_OFF_HOWTO % exc)
            return
        await session.commit()
    if scritti:
        print(f"scritti {scritti} vettori: la ricerca semantica li vede adesso")
    else:
        print("nessun vettore da scrivere: tutte le ricette ne hanno già uno")


if __name__ == "__main__":
    asyncio.run(main())
