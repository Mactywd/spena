import uuid
from collections import defaultdict
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.domain.rules import Availability, PantryStatus, availability_of


class ProductIngredientMismatch(Exception):
    """Il prodotto esiste ma appartiene a un altro ingrediente: l'accoppiata è respinta.

    È la seconda decisione fondante del CLAUDE.md resa eseguibile: un ingrediente
    generico e un prodotto specifico sono cose diverse, e la chiave esterna da
    sola non lo sa, sa solo che il prodotto esiste. Senza questo controllo una
    dispensa può dire che lo yogurt è disponibile perché un barattolo di
    pomodori, per errore del client, è stato agganciato a quell'ingrediente.
    """

    def __init__(self, product_id: uuid.UUID, ingredient_id: uuid.UUID):
        self.product_id = product_id
        self.ingredient_id = ingredient_id
        super().__init__(
            f"il prodotto {product_id} non appartiene all'ingrediente {ingredient_id}"
        )


async def _ensure_product_matches_ingredient(
    session: AsyncSession, product_id: uuid.UUID, ingredient_id: uuid.UUID
) -> None:
    """Un prodotto inesistente resta compito del vincolo di chiave esterna al
    flush (dà già il 404 "inesistente" che le rotte si aspettano); qui si
    controlla solo che, se il prodotto c'è, sia del giusto ingrediente.
    """
    actual_ingredient_id = await session.scalar(
        select(Product.ingredient_id).where(Product.id == product_id)
    )
    if actual_ingredient_id is not None and actual_ingredient_id != ingredient_id:
        raise ProductIngredientMismatch(product_id=product_id, ingredient_id=ingredient_id)


def _active(statement):
    """Le voci finite o archiviate non esistono, ai fini della disponibilità."""
    return statement.where(
        PantryItem.archived_at.is_(None), PantryItem.status != PantryStatus.FINISHED
    )


async def availability_map(
    session: AsyncSession, ingredient_ids: Sequence[uuid.UUID] | None = None
) -> dict[uuid.UUID, Availability]:
    """Ponte fra il database e le regole pure: stati concreti verso disponibilità.

    Gli ingredienti assenti dalla mappa sono mancanti. I chiamanti usano
    `result.get(id, Availability.MISSING)`.
    """
    statement = _active(select(PantryItem.ingredient_id, PantryItem.status))
    if ingredient_ids is not None:
        if not ingredient_ids:
            return {}
        statement = statement.where(PantryItem.ingredient_id.in_(ingredient_ids))

    grouped: dict[uuid.UUID, list[PantryStatus]] = defaultdict(list)
    for ingredient_id, status in (await session.execute(statement)).all():
        grouped[ingredient_id].append(PantryStatus(status))

    return {
        ingredient_id: availability_of(statuses) for ingredient_id, statuses in grouped.items()
    }


async def list_pantry(session: AsyncSession) -> list[PantryItem]:
    statement = (
        select(PantryItem)
        .options(joinedload(PantryItem.ingredient), joinedload(PantryItem.product))
        .where(PantryItem.archived_at.is_(None))
        .order_by(PantryItem.added_at.desc())
    )
    return list((await session.execute(statement)).unique().scalars())


async def add_pantry_item(
    session: AsyncSession,
    *,
    ingredient_id: uuid.UUID,
    product_id: uuid.UUID | None = None,
    status: PantryStatus = PantryStatus.AVAILABLE,
    note: str | None = None,
) -> PantryItem:
    """Crea la voce di dispensa. Il controllo prodotto-ingrediente vive qui e non
    nei chiamanti: sia la rotta di scorta diretta sia quella che smista la
    lista della spesa (scontrino a barcode o ricerca a catalogo) passano da
    qui, quindi un solo controllo basta per entrambe le strade invece che una
    difesa duplicata in ciascuna.
    """
    if product_id is not None:
        await _ensure_product_matches_ingredient(session, product_id, ingredient_id)
    item = PantryItem(ingredient_id=ingredient_id, product_id=product_id, status=status, note=note)
    session.add(item)
    await session.flush()
    return item


async def set_status(session: AsyncSession, item_id: uuid.UUID, status: PantryStatus) -> PantryItem:
    item = await session.get(PantryItem, item_id)
    if item is None:
        raise KeyError(item_id)
    item.status = status
    item.status_changed_at = datetime.now(UTC)
    await session.flush()
    return item


async def archive_item(session: AsyncSession, item_id: uuid.UUID) -> PantryItem:
    item = await session.get(PantryItem, item_id)
    if item is None:
        raise KeyError(item_id)
    item.archived_at = datetime.now(UTC)
    await session.flush()
    return item


async def unarchive_item(session: AsyncSession, item_id: uuid.UUID) -> PantryItem:
    """L'annulla della X rossa: la voce torna in dispensa com'era.

    Lo stato non si tocca — chi archivia una voce «quasi finita» e si pente la
    rivuole quasi finita, non riportata a un valore scelto da noi.
    """
    item = await session.get(PantryItem, item_id)
    if item is None:
        raise KeyError(item_id)
    item.archived_at = None
    await session.flush()
    return item
