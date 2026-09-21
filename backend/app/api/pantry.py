import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_session, is_missing_reference
from app.core.security import require_session
from app.db.models.pantry import PantryItem
from app.domain.rules import Availability, expiry_state, today_in_pantry
from app.repositories.pantry import (
    ProductIngredientMismatch,
    add_pantry_item,
    archive_item,
    availability_map,
    list_pantry,
    set_expiry,
    set_fill,
    set_status,
    unarchive_item,
)
from app.schemas.pantry import PantryItemCreate, PantryItemOut, PantryItemPatch, RestockOut
from app.services.restock import restock

router = APIRouter(
    prefix="/api/v1/pantry", tags=["pantry"], dependencies=[Depends(require_session)]
)


def _to_out(item: PantryItem) -> PantryItemOut:
    return PantryItemOut(
        id=item.id,
        ingredient_id=item.ingredient_id,
        product_id=item.product_id,
        ingredient_name=item.ingredient.name,
        ingredient_category=item.ingredient.category,
        product_name=item.product.name if item.product else None,
        product_brand=item.product.brand if item.product else None,
        status=item.status,
        fill_percent=item.fill_percent,
        note=item.note,
        expires_on=item.expires_on,
        expiry=expiry_state(item.expires_on, today_in_pantry()),
        added_at=item.added_at,
    )


@router.get("", response_model=list[PantryItemOut])
async def read_pantry(session: AsyncSession = Depends(get_session)) -> list[PantryItemOut]:
    return [_to_out(item) for item in await list_pantry(session)]


@router.get("/availability", response_model=dict[uuid.UUID, Availability])
async def read_availability(
    session: AsyncSession = Depends(get_session),
) -> dict[uuid.UUID, Availability]:
    return await availability_map(session)


@router.post("", response_model=PantryItemOut, status_code=status.HTTP_201_CREATED)
async def create(
    payload: PantryItemCreate, session: AsyncSession = Depends(get_session)
) -> PantryItemOut:
    try:
        item = await add_pantry_item(
            session, ingredient_id=payload.ingredient_id, product_id=payload.product_id,
            status=payload.status, note=payload.note,
        )
        await session.commit()
    except ProductIngredientMismatch as exc:
        # diversa da "non esiste": il prodotto c'è, ma è di un altro ingrediente.
        # Non è un 404 perché non c'è nulla di mancante da correggere con un
        # retry sullo stesso id: è la coppia dichiarata che è sbagliata
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT, "il prodotto appartiene a un altro ingrediente"
        ) from exc
    except IntegrityError as exc:
        # un id pendente (tipico di una PWA con la cache vecchia) non deve essere
        # un muro: 404, come già fa POST /shopping-list/stock. Qualunque altra
        # violazione è un difetto nostro e deve restare visibile come 500, non
        # travestirsi da "inesistente"
        await session.rollback()
        if not is_missing_reference(exc):
            raise
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, "ingrediente o prodotto inesistente"
        ) from exc
    await session.refresh(item, ["ingredient", "product"])
    return _to_out(item)


@router.patch("/{item_id}", response_model=PantryItemOut)
async def patch(
    item_id: uuid.UUID, payload: PantryItemPatch,
    session: AsyncSession = Depends(get_session),
) -> PantryItemOut:
    try:
        if payload.archived is not None:
            item = (
                await archive_item(session, item_id)
                if payload.archived
                else await unarchive_item(session, item_id)
            )
        elif payload.fill_percent is not None:
            # prima dello stato: una richiesta che porta entrambi viene dal cursore,
            # e lì lo stato è una conseguenza, non una seconda opinione
            item = await set_fill(session, item_id, payload.fill_percent)
        elif payload.status is not None:
            item = await set_status(session, item_id, payload.status)
        elif "expires_on" in payload.model_fields_set:
            # ultima della catena, e nessuno oggi manda la data insieme ad altro: una
            # richiesta con stato e scadenza scriverebbe lo stato e perderebbe la data
            # in silenzio. Se un giorno una schermata le mandasse insieme, questa
            # catena va aperta, non riordinata — l'ordine qui sopra è già una regola.
            # per presenza, non per valore: `{"expires_on": null}` è la cancellazione
            item = await set_expiry(session, item_id, payload.expires_on)
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "niente da modificare")
    except KeyError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "voce inesistente") from exc
    await session.commit()
    await session.refresh(item, ["ingredient", "product"])
    return _to_out(item)


@router.post("/{item_id}/restock", response_model=RestockOut)
async def restock_item(
    item_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> RestockOut:
    """Rimette in lista quel che è finito, se non c'è già.

    Una rotta sua e non un campo della PATCH: spostare un cursore e comprare una
    cosa sono due gesti, e l'utente ne compie il secondo rispondendo a una domanda.
    Nessuna sezione ne modifica un'altra in silenzio.
    """
    item = await session.get(PantryItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "voce inesistente")
    added = await restock(session, item)
    await session.commit()
    return RestockOut(added=added)
