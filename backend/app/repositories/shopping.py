import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from app.db.models.pantry import PantryItem
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus
from app.domain.rules import PantryStatus
from app.repositories.pantry import add_pantry_item
from app.repositories.products import give_barcode_if_missing
from app.services.ingredient_match import exact_ingredient


@dataclass(frozen=True)
class StockEntry:
    shopping_item_id: uuid.UUID
    ingredient_id: uuid.UUID
    product_id: uuid.UUID | None
    expires_on: date | None
    # il codice letto per questa voce, da dare al prodotto scelto se non ne ha
    # uno (S8): vedi give_barcode_if_missing
    barcode: str | None = None


async def list_items(
    session: AsyncSession, statuses: Sequence[str] | None = None
) -> list[ShoppingListItem]:
    statement = (
        select(ShoppingListItem)
        .options(joinedload(ShoppingListItem.ingredient))
        .order_by(ShoppingListItem.created_at.asc())
    )
    if statuses:
        statement = statement.where(ShoppingListItem.status.in_(statuses))
    return list((await session.execute(statement)).unique().scalars())


@dataclass(frozen=True)
class AddedItem:
    item: ShoppingListItem
    # falso non è un errore: l'ingrediente era già da comprare, e `item` è quella
    # voce. Stessa informazione di `restock`, per poter dire «era già in lista»
    added: bool


async def active_item_for(
    session: AsyncSession, ingredient_id: uuid.UUID
) -> ShoppingListItem | None:
    """La voce che ha già in lista quell'ingrediente, da comprare o nel carrello.

    Sistemata o archiviata non conta: la prima è già in dispensa, la seconda è
    stata tolta. Se per la storia ce ne fossero due, la più vecchia: è quella che
    si legge per prima scorrendo la lista.
    """
    statement = (
        select(ShoppingListItem)
        .where(
            ShoppingListItem.ingredient_id == ingredient_id,
            ShoppingListItem.status.in_([ShoppingStatus.PENDING, ShoppingStatus.CHECKED]),
        )
        .order_by(ShoppingListItem.created_at.asc())
        .limit(1)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def add_item(
    session: AsyncSession,
    raw_text: str,
    ingredient_id: uuid.UUID | None = None,
    reason: ShoppingReason = ShoppingReason.MANUAL,
) -> AddedItem:
    """Scrive una voce in lista, agganciandola se il testo *è* un ingrediente (S18).

    Senza id dal client si prova la coincidenza esatta col nome o con un alias —
    mai una somiglianza: l'aggancio qui è silenzioso, e un ingrediente sbagliato in
    silenzio sposta la voce di reparto e poi la manda in dispensa col nome d'altri.
    Sta qui e non nel campo della lista perché valga per qualunque client.

    Con un ingrediente, agganciato o mandato, non si scrive un doppione di una voce
    ancora da comprare: si restituisce quella, con `added` falso. Il testo libero
    non si confronta con nulla — senza ingrediente non c'è un'identità su cui
    dire «è la stessa cosa».
    """
    cleaned = raw_text.strip()
    if ingredient_id is None:
        match = await exact_ingredient(session, cleaned)
        ingredient_id = match.id if match is not None else None
    if ingredient_id is not None:
        existing = await active_item_for(session, ingredient_id)
        if existing is not None:
            return AddedItem(existing, added=False)
    item = ShoppingListItem(
        raw_text=cleaned, ingredient_id=ingredient_id,
        status=ShoppingStatus.PENDING, reason=reason,
    )
    session.add(item)
    await session.flush()
    return AddedItem(item, added=True)


class AlreadyListed(Exception):
    """Rimettere in lista una voce tolta farebbe un doppione: il suo ingrediente è già
    da comprare, o nel carrello, in un'altra voce (T3 Consegna 2, l'«Annulla» della ✕).

    `existing` è quella voce: la stessa che S18 restituisce alla POST con `added`
    falso.
    """

    def __init__(self, existing: ShoppingListItem):
        self.existing = existing
        super().__init__(f"l'ingrediente {existing.ingredient_id} è già in lista")


async def patch_item(
    session: AsyncSession,
    item_id: uuid.UUID,
    *,
    status: ShoppingStatus | None = None,
    ingredient_id: uuid.UUID | None = None,
) -> ShoppingListItem:
    item = await session.get(ShoppingListItem, item_id)
    if item is None:
        raise KeyError(item_id)
    # L'«Annulla» della ✕ riporta una voce archiviata in lista. Se nel frattempo la
    # stessa cosa ci è tornata dalla barra, rimetterla farebbe il doppione che S18 esiste
    # per evitare. Il controllo sta qui e non nel client, che lo guarda nella sua cache:
    # fra la POST della barra e il refetch la cache non lo sa ancora. Conta l'ingrediente
    # che la voce avrebbe dopo questa PATCH, e si guarda prima di scrivere niente. Una
    # voce libera non è mai un doppione: senza ingrediente non c'è un'identità (S18).
    # Le altre PATCH non si toccano: il controllo è del ritorno da `archived`.
    target_ingredient = ingredient_id if ingredient_id is not None else item.ingredient_id
    if (
        item.status == ShoppingStatus.ARCHIVED
        and status in (ShoppingStatus.PENDING, ShoppingStatus.CHECKED)
        and target_ingredient is not None
    ):
        existing = await active_item_for(session, target_ingredient)
        if existing is not None:
            raise AlreadyListed(existing)
    if ingredient_id is not None:
        item.ingredient_id = ingredient_id
    if status is not None:
        item.status = status
        now = datetime.now(UTC)
        if status is ShoppingStatus.CHECKED:
            item.checked_at = now
        elif status is ShoppingStatus.DONE:
            item.done_at = now
    await session.flush()
    await session.refresh(item, ["ingredient"])
    return item


async def stock_items(session: AsyncSession, entries: list[StockEntry]) -> list[PantryItem]:
    """Dalla lista spuntata alla dispensa, tutto dentro una sola transazione.

    Il chiamante non fa commit prima della fine: un riferimento sbagliato a metà
    strada non deve lasciare la dispensa popolata a metà.
    """
    created: list[PantryItem] = []
    now = datetime.now(UTC)
    for entry in entries:
        shopping_item = await session.get(ShoppingListItem, entry.shopping_item_id)
        if shopping_item is None:
            raise KeyError(entry.shopping_item_id)
        item = await add_pantry_item(
            session, ingredient_id=entry.ingredient_id, product_id=entry.product_id,
            status=PantryStatus.AVAILABLE, expires_on=entry.expires_on,
        )
        # dopo add_pantry_item e non prima: il codice va solo a un prodotto che
        # quel controllo ha già riconosciuto come dell'ingrediente della voce
        if entry.product_id is not None and entry.barcode:
            await give_barcode_if_missing(session, entry.product_id, entry.barcode)
        shopping_item.ingredient_id = entry.ingredient_id
        shopping_item.status = ShoppingStatus.DONE
        shopping_item.done_at = now
        created.append(item)
    await session.flush()
    return created
