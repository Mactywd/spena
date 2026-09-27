import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.refusals import refusal_response
from app.core.db import get_session, is_missing_reference, is_unique_violation
from app.core.security import require_session
from app.db.models.ingredient import Ingredient
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.domain.barcodes import has_valid_check_digit
from app.repositories.products import create_product, find_by_barcode, search_products
from app.schemas.product import (
    BarcodeLookupOut,
    IngredientRefOut,
    ProductCreate,
    ProductDeletedOut,
    ProductDetailOut,
    ProductOut,
    ProductPantryItemOut,
    ProductPatch,
    ProductSuggestion,
)
from app.services import registry
from app.services.openfoodfacts import OffUnavailable, OpenFoodFactsClient
from app.services.registry import RegistryRefusal

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

    `find_by_barcode` cerca sul solo codice, quindi la referenza restituita può
    appartenere a un ingrediente diverso da quello della voce su cui il codice è
    stato letto. Qui è giusto così — il codice a barre identifica il prodotto, non
    l'uso che se ne fa — e sta al chiamante confrontare `ingredient_id` prima di
    agganciarla: `add_pantry_item` respinge la coppia incoerente con 409.

    `valid_checksum` dice se la cifra di controllo torna, e non ferma niente: un
    codice battuto male si cerca lo stesso, perché anche un codice interno di
    negozio che non torna può essere già nel nostro catalogo.
    """
    valid_checksum = has_valid_check_digit(barcode)
    existing = await find_by_barcode(session, barcode)
    if existing is not None:
        return BarcodeLookupOut(
            found=True, origin="catalog", product=ProductOut.model_validate(existing),
            valid_checksum=valid_checksum,
        )

    try:
        remote = await OpenFoodFactsClient().fetch(barcode)
    except OffUnavailable:
        remote = None

    if remote is None:
        return BarcodeLookupOut(found=False, origin="unknown", valid_checksum=valid_checksum)

    return BarcodeLookupOut(
        found=True,
        origin="openfoodfacts",
        suggestion=ProductSuggestion(
            name=remote.name, brand=remote.brand, barcode=remote.barcode,
            nutrients=remote.nutrients, image_url=remote.image_url,
        ),
        valid_checksum=valid_checksum,
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
            brand=payload.brand, barcode=payload.barcode, source=payload.source,
            nutrients=payload.nutrients, image_url=payload.image_url,
            source_payload=payload.source_payload,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        # due cause diverse, due risposte diverse: un ingrediente inesistente non è
        # un codice a barre duplicato
        if is_missing_reference(exc):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente") from exc
        if not is_unique_violation(exc):
            raise
        raise HTTPException(status.HTTP_409_CONFLICT, "codice a barre già in catalogo") from exc
    return ProductOut.model_validate(product)


_CONFLICT = {status.HTTP_409_CONFLICT: {
    "description": "rifiuto dell'anagrafica: `code`, `detail` e l'ostacolo accanto",
}}


async def _detail(session: AsyncSession, product_id: uuid.UUID) -> ProductDetailOut:
    product = await session.get(Product, product_id)
    if product is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "prodotto inesistente")
    ingredient = await session.get(Ingredient, product.ingredient_id)
    items = list(
        (
            await session.execute(
                select(PantryItem)
                .where(PantryItem.product_id == product_id, PantryItem.archived_at.is_(None))
                .order_by(PantryItem.added_at, PantryItem.id)
            )
        ).scalars()
    )
    return ProductDetailOut(
        id=product.id,
        name=product.name,
        brand=product.brand,
        barcode=product.barcode,
        valid_checksum=has_valid_check_digit(product.barcode) if product.barcode else None,
        ingredient=IngredientRefOut.model_validate(ingredient),
        pantry_items=[ProductPantryItemOut.model_validate(item) for item in items],
    )


@router.get("/{product_id}", response_model=ProductDetailOut)
async def read_one(
    product_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ProductDetailOut:
    return await _detail(session, product_id)


@router.patch("/{product_id}", response_model=ProductDetailOut, responses=_CONFLICT)
async def update(
    product_id: uuid.UUID, payload: ProductPatch,
    session: AsyncSession = Depends(get_session),
) -> ProductDetailOut | JSONResponse:
    fields = payload.model_fields_set - {"take_barcode", "accept_bad_checksum"}
    if not fields:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "niente da cambiare")
    try:
        if "name" in fields or "brand" in fields:
            await registry.update_product(
                session, product_id,
                name=payload.name if "name" in fields else None,
                # `null` è «togli la marca», che per il servizio è la stringa vuota
                brand=(payload.brand or "") if "brand" in fields else None,
            )
        if "ingredient_id" in fields:
            await registry.move_product(session, product_id, payload.ingredient_id)
        if "barcode" in fields:
            await registry.set_barcode(
                session, product_id, payload.barcode,
                take=payload.take_barcode, accept_bad_checksum=payload.accept_bad_checksum,
            )
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "prodotto o ingrediente inesistente"
        ) from exc
    except RegistryRefusal as exc:
        response = refusal_response(exc)
        await session.rollback()
        return response
    await session.commit()
    return await _detail(session, product_id)


@router.delete("/{product_id}", response_model=ProductDeletedOut)
async def remove(
    product_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> ProductDeletedOut:
    """200 e non 204: la risposta dice quanti elementi di dispensa sono rimasti sfusi, e
    un 204 non ha corpo."""
    try:
        loose = await registry.delete_product(session, product_id)
    except LookupError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "prodotto inesistente") from exc
    await session.commit()
    return ProductDeletedOut(loose_pantry_items=loose)
