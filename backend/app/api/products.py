from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session
from app.core.security import require_session
from app.repositories.products import create_product, find_by_barcode, search_products
from app.schemas.product import (
    BarcodeLookupOut,
    ProductCreate,
    ProductOut,
    ProductSuggestion,
)
from app.services.openfoodfacts import OffUnavailable, OpenFoodFactsClient

router = APIRouter(
    prefix="/api/v1/products", tags=["products"], dependencies=[Depends(require_session)]
)


@router.get("/barcode/{barcode}", response_model=BarcodeLookupOut)
async def lookup_barcode(
    barcode: str, session: AsyncSession = Depends(get_session)
) -> BarcodeLookupOut:
    """Catalogo locale, poi Open Food Facts, poi resa onesta.

    Non restituisce mai un errore: un codice ignoto o un servizio giù devono
    portare alla creazione manuale, che è sempre possibile.
    """
    existing = await find_by_barcode(session, barcode)
    if existing is not None:
        return BarcodeLookupOut(
            found=True, origin="catalog", product=ProductOut.model_validate(existing)
        )

    try:
        remote = await OpenFoodFactsClient().fetch(barcode)
    except OffUnavailable:
        remote = None

    if remote is None:
        return BarcodeLookupOut(found=False, origin="unknown")

    return BarcodeLookupOut(
        found=True,
        origin="openfoodfacts",
        suggestion=ProductSuggestion(
            name=remote.name, brand=remote.brand, barcode=remote.barcode,
            nutrients=remote.nutrients, image_url=remote.image_url,
        ),
    )


@router.get("/search", response_model=list[ProductOut])
async def search(
    q: str = Query(min_length=1), limit: int = Query(default=20, le=50),
    session: AsyncSession = Depends(get_session),
) -> list[ProductOut]:
    found = await search_products(session, q, limit)
    return [ProductOut.model_validate(p) for p in found]


@router.post("", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
async def create(
    payload: ProductCreate, session: AsyncSession = Depends(get_session)
) -> ProductOut:
    try:
        product = await create_product(
            session, ingredient_id=payload.ingredient_id, name=payload.name,
            brand=payload.brand, barcode=payload.barcode, source="custom",
            nutrients=payload.nutrients,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "codice a barre già in catalogo") from exc
    return ProductOut.model_validate(product)
