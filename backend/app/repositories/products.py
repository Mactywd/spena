import uuid
from typing import Any

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product

SIMILARITY_FLOOR = 0.1


async def find_by_barcode(session: AsyncSession, barcode: str) -> Product | None:
    result = await session.execute(select(Product).where(Product.barcode == barcode))
    return result.scalar_one_or_none()


async def search_products(session: AsyncSession, query: str, limit: int = 20) -> list[Product]:
    """Ricerca per affinamento progressivo: da "yogurt greco" a "carrefour pesca".

    Ogni parola deve comparire (`and_`), ma cercata su nome e marca insieme e con la
    somiglianza trigram come riserva: è questo che fa restringere senza azzerare —
    aggiungere la marca non pretende che esista un campo in cui tutta la frase
    compaia, e un errore di battitura non cancella il risultato.

    Misurato sul catalogo di prova (Yogurt greco pesca/Carrefour, Yogurt greco
    naturale/Fage): «yogurt greco» → 2 referenze, «yogurt greco carrefour» → la sola
    Carrefour, «yogurtt greco» → ancora 2. Con `or_` al posto di `and_` la seconda
    query ne restituiva 2, cioè allargava dove il nome della funzione dice il
    contrario; l'ordinamento per somiglianza complessiva lo mascherava portando in
    cima la referenza giusta.
    """
    words = [w for w in query.strip().lower().split() if w]
    if not words:
        return []

    haystack = func.lower(func.concat(Product.name, " ", func.coalesce(Product.brand, "")))
    word_matches = [
        or_(haystack.like(f"%{word}%"), func.similarity(haystack, word) >= SIMILARITY_FLOOR)
        for word in words
    ]
    overall_similarity = func.similarity(haystack, " ".join(words))

    statement = (
        select(Product)
        .where(and_(*word_matches))
        .order_by(overall_similarity.desc(), Product.name.asc())
        .limit(limit)
    )
    return list((await session.execute(statement)).scalars())


async def create_product(
    session: AsyncSession,
    *,
    ingredient_id: uuid.UUID,
    name: str,
    brand: str | None = None,
    barcode: str | None = None,
    source: str = "custom",
    nutrients: dict[str, Any] | None = None,
    image_url: str | None = None,
    source_payload: dict[str, Any] | None = None,
) -> Product:
    product = Product(
        ingredient_id=ingredient_id, name=name, brand=brand, barcode=barcode,
        source=source, nutrients=nutrients, image_url=image_url, source_payload=source_payload,
    )
    session.add(product)
    await session.flush()
    return product
