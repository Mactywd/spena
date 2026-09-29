import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session, is_missing_reference
from app.core.security import require_session
from app.db.models.shopping import ShoppingListItem
from app.repositories.pantry import ProductIngredientMismatch
from app.repositories.shopping import (
    AlreadyListed,
    StockEntry,
    add_item,
    list_items,
    patch_item,
    stock_items,
)
from app.schemas.shopping import (
    ShoppingItemAddOut,
    ShoppingItemCreate,
    ShoppingItemOut,
    ShoppingItemPatch,
    StockRequest,
)

router = APIRouter(
    prefix="/api/v1/shopping-list", tags=["shopping"], dependencies=[Depends(require_session)]
)


def _to_out(item: ShoppingListItem) -> ShoppingItemOut:
    return ShoppingItemOut(
        id=item.id,
        raw_text=item.raw_text,
        ingredient_id=item.ingredient_id,
        ingredient_name=item.ingredient.name if item.ingredient else None,
        ingredient_category=item.ingredient.category if item.ingredient else None,
        ingredient_kind=item.ingredient.kind if item.ingredient else None,
        status=item.status,
        reason=item.reason,
        created_at=item.created_at,
    )


@router.get("", response_model=list[ShoppingItemOut])
async def read_list(
    status_filter: list[str] | None = Query(default=None, alias="status"),
    session: AsyncSession = Depends(get_session),
) -> list[ShoppingItemOut]:
    return [_to_out(item) for item in await list_items(session, status_filter)]


@router.post("", response_model=ShoppingItemAddOut, status_code=status.HTTP_201_CREATED)
async def create(
    payload: ShoppingItemCreate,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> ShoppingItemAddOut:
    """Scrive in lista, o restituisce la voce che c'era già (`added` falso, 200).

    Un ingrediente già da comprare non è un conflitto da rifiutare: chi l'ha
    scritto voleva che fosse in lista, e lo è.
    """
    try:
        result = await add_item(session, payload.raw_text, payload.ingredient_id)
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        # solo un riferimento pendente è un "inesistente": qualunque altra
        # violazione è un difetto nostro e deve restare visibile come 500
        if not is_missing_reference(exc):
            raise
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente") from exc
    if not result.added:
        response.status_code = status.HTTP_200_OK
    await session.refresh(result.item, ["ingredient"])
    return ShoppingItemAddOut(**_to_out(result.item).model_dump(), added=result.added)


@router.patch("/{item_id}", response_model=ShoppingItemOut)
async def patch(
    item_id: uuid.UUID, payload: ShoppingItemPatch,
    session: AsyncSession = Depends(get_session),
) -> ShoppingItemOut:
    try:
        item = await patch_item(
            session, item_id, status=payload.status, ingredient_id=payload.ingredient_id
        )
        await session.commit()
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "voce inesistente") from exc
    except AlreadyListed as exc:
        # sollevata prima di ogni scrittura: non c'è niente da annullare. Un 409 e non un
        # 200 con la voce che c'era (come la POST di S18): chi ha chiesto di rimettere
        # *questa* voce deve sapere che non è tornata
        raise HTTPException(status.HTTP_409_CONFLICT, "l'ingrediente è già in lista") from exc
    except IntegrityError as exc:
        await session.rollback()
        # solo un riferimento pendente è un "inesistente": qualunque altra
        # violazione è un difetto nostro e deve restare visibile come 500
        if not is_missing_reference(exc):
            raise
        raise HTTPException(status.HTTP_404_NOT_FOUND, "ingrediente inesistente") from exc
    return _to_out(item)


@router.post("/stock", status_code=status.HTTP_201_CREATED)
async def stock(
    payload: StockRequest, session: AsyncSession = Depends(get_session)
) -> dict[str, int]:
    """Tutto o niente: un riferimento sbagliato annulla l'intera sistemazione."""
    entries = [
        StockEntry(
            shopping_item_id=e.shopping_item_id, ingredient_id=e.ingredient_id,
            product_id=e.product_id, expires_on=e.expires_on, barcode=e.barcode,
        )
        for e in payload.entries
    ]
    try:
        created = await stock_items(session, entries)
        await session.commit()
    except KeyError as exc:
        await session.rollback()
        raise HTTPException(status.HTTP_404_NOT_FOUND, "voce di lista inesistente") from exc
    except ProductIngredientMismatch as exc:
        # diversa da "non esiste": il prodotto c'è, ma è di un altro ingrediente.
        # Vale sia per la strada del barcode sia per quella della ricerca a
        # catalogo, perché entrambe arrivano allo stesso controllo in
        # add_pantry_item
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "il prodotto appartiene a un altro ingrediente"
        ) from exc
    except IntegrityError as exc:
        await session.rollback()
        # solo un riferimento pendente è un "inesistente": qualunque altra
        # violazione è un difetto nostro e deve restare visibile come 500
        if not is_missing_reference(exc):
            raise
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "ingrediente o prodotto inesistente"
        ) from exc
    return {"created": len(created)}
