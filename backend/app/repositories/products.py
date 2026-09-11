import uuid
from typing import Any

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.product import Product

SIMILARITY_FLOOR = 0.1


async def find_by_barcode(session: AsyncSession, barcode: str) -> Product | None:
    result = await session.execute(select(Product).where(Product.barcode == barcode))
    return result.scalar_one_or_none()


async def search_products(session: AsyncSession, query: str, limit: int = 20) -> list[Product]:
    """Ricerca per affinamento progressivo: da "yogurt greco" a "carrefour pesca".

    Ogni parola della query viene cercata su nome e marca insieme, così
    aggiungere termini restringe invece di azzerare i risultati.
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
        .where(or_(*word_matches))
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
