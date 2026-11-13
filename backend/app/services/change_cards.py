"""La scheda dei cambi (spec §6.2, piano 6c): Claude propone, Mattia applica.

Claude non scrive mai in dispensa né in lista: costruisce una scheda (`propose_card`),
che è solo una proposta; i cambi veri li fa `apply_card`, quando Mattia la applica, con
le uniche due strade che l'app ha sempre avuto: `set_status` per i tre stati della
dispensa (decisione fondante 1: niente quantità) e `add_item` per la lista.

Tutto fa `flush`, mai `commit`: la transazione è di chi chiama.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.change_card import (
    CardKind,
    CardStatus,
    ChangeCard,
    ChangeCardRow,
    RowKind,
)
from app.db.models.meal import Meal
from app.db.models.pantry import PantryItem
from app.domain.change_cards import adds_to_list, most_consumed
from app.domain.meals import MealStatus
from app.domain.rules import PantryStatus
from app.repositories.pantry import set_status
from app.repositories.shopping import active_item_for, add_item
from app.services.ingredient_match import exact_ingredient

ALREADY_LISTED_NOTE = "Già in lista."
GONE_NOTE = "La voce non è più in dispensa."


@dataclass(frozen=True)
class PantryProposal:
    pantry_item_id: uuid.UUID
    to_status: PantryStatus
    # vuoto = i pasti della scheda
    meal_ids: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True)
class ListProposal:
    ingredient_id: uuid.UUID | None
    raw_text: str
    meal_ids: tuple[uuid.UUID, ...] = ()


@dataclass(frozen=True)
class RowOverride:
    row_id: uuid.UUID
    checked: bool
    to_status: PantryStatus | None = None


class CardRefusalCode(StrEnum):
    ALREADY_APPLIED = "card_applied"
    DISCARDED = "card_discarded"
    LIST_ONLY = "list_only"
    ROW_EXISTS = "row_exists"
    NOT_IN_PANTRY = "not_in_pantry"
    NOT_FOOD = "not_food"
    NO_MEAL = "no_meal"


class CardRefusal(Exception):
    def __init__(self, code: CardRefusalCode, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def _title(meals: Sequence[Meal], list_only: bool) -> str:
    if list_only:
        if len(meals) == 1:
            return f"Per la spesa: «{meals[0].dish}» in bozza"
        return f"Per la spesa: {len(meals)} pasti in bozza"
    if len(meals) == 1:
        return f"Per «{meals[0].dish}»"
    return f"Per {len(meals)} pasti"


def _ids(values: Sequence[uuid.UUID | str]) -> list[str]:
    seen: list[str] = []
    for value in values:
        if str(value) not in seen:
            seen.append(str(value))
    return seen


def _union(a: list[str], b: Sequence[str]) -> list[str]:
    return _ids([*a, *b])


def _label(item: PantryItem) -> str:
    # la marca che avevi comprato è l'informazione più utile in negozio (come `restock`)
    return item.product.name if item.product else item.ingredient.name


async def _live_pantry_item(session: AsyncSession, item_id: uuid.UUID) -> PantryItem:
    item = await session.get(PantryItem, item_id)
    if item is None or item.archived_at is not None:
        raise CardRefusal(
            CardRefusalCode.NOT_IN_PANTRY, "Quella voce non è più in dispensa."
        )
    await session.refresh(item, ["ingredient", "product"])
    if item.ingredient.kind != "food":
        raise CardRefusal(
            CardRefusalCode.NOT_FOOD,
            f"«{item.ingredient.name}» non è un alimento: la scheda dei cambi tocca la "
            "dispensa di cibo.",
        )
    return item


async def _list_row_fields(
    session: AsyncSession, ingredient_id: uuid.UUID | None
) -> dict[str, object]:
    """Una voce già in lista (da comprare o nel carrello) resta visibile ma non si spunta."""
    if ingredient_id is not None and await active_item_for(session, ingredient_id):
        return {"checked": False, "editable": False, "note": ALREADY_LISTED_NOTE}
    return {"checked": True, "editable": True, "note": None}


def _new_card(**fields: object) -> ChangeCard:
    return ChangeCard(created_at=datetime.now(UTC), status=CardStatus.PROPOSED.value, **fields)


async def propose_card(
    session: AsyncSession,
    *,
    meals: Sequence[Meal],
    pantry: Sequence[PantryProposal],
    shopping: Sequence[ListProposal],
    conversation_id: uuid.UUID | None = None,
    turn_message_id: uuid.UUID | None = None,
) -> ChangeCard:
    if not meals:
        raise CardRefusal(CardRefusalCode.NO_MEAL, "Una scheda serve a un pasto almeno.")
    list_only = all(m.status == MealStatus.DRAFT.value for m in meals)
    if pantry and list_only:
        raise CardRefusal(
            CardRefusalCode.LIST_ONLY,
            "Per una bozza la scheda ha solo la lista della spesa: la dispensa si "
            "sistema quando il pasto diventa ufficiale.",
        )
    card_meals = _ids([m.id for m in meals])

    # una riga di dispensa per voce (decisione 18): lo stato più consumato vince
    pantry_rows: dict[str, dict] = {}
    for proposal in pantry:
        item = await _live_pantry_item(session, proposal.pantry_item_id)
        key = str(item.id)
        to_status = PantryStatus(proposal.to_status).value
        mine = _ids(proposal.meal_ids) or card_meals
        if key in pantry_rows:
            row = pantry_rows[key]
            row["to_status"] = most_consumed(row["to_status"], to_status)
            row["meal_ids"] = _union(row["meal_ids"], mine)
        else:
            pantry_rows[key] = {
                "item": item, "to_status": to_status, "meal_ids": mine,
            }

    # una riga di lista per ingrediente: chi finisce ci va da sé (decisione 19)
    list_rows: dict[str, dict] = {}
    free_rows: list[dict] = []

    def add_list(ingredient_id, label: str, mine: list[str]) -> None:
        if ingredient_id is None:
            free_rows.append({"ingredient_id": None, "label": label, "meal_ids": mine})
            return
        key = str(ingredient_id)
        if key in list_rows:
            list_rows[key]["meal_ids"] = _union(list_rows[key]["meal_ids"], mine)
        else:
            list_rows[key] = {"ingredient_id": ingredient_id, "label": label, "meal_ids": mine}

    for row in pantry_rows.values():
        if adds_to_list(row["to_status"]):
            add_list(row["item"].ingredient_id, _label(row["item"]), row["meal_ids"])
    for proposal in shopping:
        ingredient_id = proposal.ingredient_id
        if ingredient_id is None:
            match = await exact_ingredient(session, proposal.raw_text)
            ingredient_id = match.id if match is not None else None
        add_list(ingredient_id, proposal.raw_text.strip(), _ids(proposal.meal_ids) or card_meals)

    card = _new_card(
        kind=CardKind.FORWARD.value, list_only=list_only, title=_title(meals, list_only),
        meal_ids=card_meals, conversation_id=conversation_id, turn_message_id=turn_message_id,
    )
    session.add(card)
    await session.flush()

    position = 0
    for row in pantry_rows.values():
        item = row["item"]
        session.add(ChangeCardRow(
            card_id=card.id, position=position, kind=RowKind.PANTRY.value,
            label=_label(item), pantry_item_id=item.id, ingredient_id=item.ingredient_id,
            to_status=row["to_status"], checked=True, editable=True, meal_ids=row["meal_ids"],
        ))
        position += 1
    for row in [*list_rows.values(), *free_rows]:
        session.add(ChangeCardRow(
            card_id=card.id, position=position, kind=RowKind.LIST.value, label=row["label"],
            ingredient_id=row["ingredient_id"], meal_ids=row["meal_ids"],
            **await _list_row_fields(session, row["ingredient_id"]),
        ))
        position += 1
    await session.flush()
    return await _reload(session, card.id)


async def create_empty_card(session: AsyncSession, meal: Meal) -> ChangeCard:
    """La scheda dell'ufficializzazione a mano: nessuna riga, da compilare."""
    card = _new_card(
        kind=CardKind.FORWARD.value, list_only=False,
        title=f"Per «{meal.dish}»: compila a mano", meal_ids=[str(meal.id)],
    )
    session.add(card)
    await session.flush()
    return await _reload(session, card.id)


def _must_be_proposed(card: ChangeCard) -> None:
    if card.status == CardStatus.APPLIED.value:
        raise CardRefusal(CardRefusalCode.ALREADY_APPLIED, "La scheda era già applicata.")
    if card.status == CardStatus.DISCARDED.value:
        raise CardRefusal(CardRefusalCode.DISCARDED, "La scheda è stata scartata.")


async def add_row(
    session: AsyncSession,
    card: ChangeCard,
    *,
    pantry_item_id: uuid.UUID | None = None,
    raw_text: str | None = None,
) -> ChangeCard:
    """La riga a mano, con le regole della proposta."""
    card = await _reload(session, card.id)
    _must_be_proposed(card)
    if (pantry_item_id is None) == (raw_text is None):
        raise ValueError("serve una voce di dispensa oppure un testo, non entrambi")
    rows = list(card.rows)
    position = max((r.position for r in rows), default=-1) + 1
    mine = list(card.meal_ids)

    if pantry_item_id is not None:
        if card.list_only:
            raise CardRefusal(
                CardRefusalCode.LIST_ONLY,
                "Per una bozza la scheda ha solo la lista della spesa.",
            )
        item = await _live_pantry_item(session, pantry_item_id)
        if any(r.kind == RowKind.PANTRY.value and r.pantry_item_id == item.id for r in rows):
            raise CardRefusal(CardRefusalCode.ROW_EXISTS, "Questa voce è già nella scheda.")
        session.add(ChangeCardRow(
            card_id=card.id, position=position, kind=RowKind.PANTRY.value, label=_label(item),
            pantry_item_id=item.id, ingredient_id=item.ingredient_id, to_status=item.status,
            checked=True, editable=True, meal_ids=mine,
        ))
    else:
        text = (raw_text or "").strip()
        match = await exact_ingredient(session, text)
        ingredient_id = match.id if match is not None else None
        for r in rows:
            if r.kind != RowKind.LIST.value:
                continue
            same = (
                r.ingredient_id == ingredient_id
                if ingredient_id is not None
                else r.ingredient_id is None and r.label.casefold() == text.casefold()
            )
            if same:
                raise CardRefusal(CardRefusalCode.ROW_EXISTS, "Questa voce è già nella scheda.")
        session.add(ChangeCardRow(
            card_id=card.id, position=position, kind=RowKind.LIST.value, label=text,
            ingredient_id=ingredient_id, meal_ids=mine,
            **await _list_row_fields(session, ingredient_id),
        ))
    await session.flush()
    return await _reload(session, card.id)


async def _reload(session: AsyncSession, card_id: uuid.UUID) -> ChangeCard:
    card = await get_card(session, card_id)
    assert card is not None
    return card


async def get_card(session: AsyncSession, card_id: uuid.UUID) -> ChangeCard | None:
    statement = (
        select(ChangeCard)
        .options(selectinload(ChangeCard.rows))
        .where(ChangeCard.id == card_id)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def cards_with_status(session: AsyncSession, status: CardStatus) -> list[ChangeCard]:
    statement = (
        select(ChangeCard)
        .options(selectinload(ChangeCard.rows))
        .where(ChangeCard.status == CardStatus(status).value)
        .order_by(ChangeCard.created_at.desc(), ChangeCard.id)
        .execution_options(populate_existing=True)
    )
    return list((await session.execute(statement)).scalars())


async def open_card_for_meal(session: AsyncSession, meal_id: uuid.UUID) -> ChangeCard | None:
    statement = (
        select(ChangeCard)
        .options(selectinload(ChangeCard.rows))
        .where(
            ChangeCard.status == CardStatus.PROPOSED.value,
            ChangeCard.meal_ids.contains([str(meal_id)]),
        )
        .order_by(ChangeCard.created_at.desc(), ChangeCard.id)
        .limit(1)
        .execution_options(populate_existing=True)
    )
    return (await session.execute(statement)).scalar_one_or_none()


async def _locked(session: AsyncSession, card_id: uuid.UUID) -> ChangeCard:
    statement = (
        select(ChangeCard)
        .where(ChangeCard.id == card_id)
        .with_for_update()
        .execution_options(populate_existing=True)
    )
    card = (await session.execute(statement)).scalar_one_or_none()
    if card is None:
        raise KeyError(card_id)
    return card


async def apply_card(
    session: AsyncSession, card_id: uuid.UUID, overrides: Sequence[RowOverride]
) -> ChangeCard:
    """Applica la scheda, una volta sola, dentro la transazione di chi chiama.

    Prima di ogni altra cosa blocca la riga della scheda (`SELECT … FOR UPDATE`) e solo
    poi guarda lo stato (decisione 21): due «Applica» contemporanei si mettono in fila,
    il secondo trova `applied` e si ferma con `ALREADY_APPLIED` prima di toccare
    dispensa o lista. Senza il blocco i due leggerebbero entrambi `proposed`.

    Le righe di lista passano da `add_item` e non da una copia della sua logica: la
    regola del non duplicare sta in un posto solo, e così non duplica nemmeno ciò che è
    entrato in lista dopo la proposta (decisione 19).

    Una correzione su una riga non modificabile, o un nuovo stato su una riga che non è
    di dispensa, si ignora. Una voce sparita o archiviata si salta con la sua nota, e il
    resto si applica.
    """
    card = await _locked(session, card_id)
    _must_be_proposed(card)
    rows = list(
        (
            await session.execute(
                select(ChangeCardRow)
                .where(ChangeCardRow.card_id == card.id)
                .order_by(ChangeCardRow.position)
                .execution_options(populate_existing=True)
            )
        ).scalars()
    )
    by_id = {row.id: row for row in rows}
    for override in overrides:
        row = by_id.get(override.row_id)
        if row is None or not row.editable:
            continue
        row.checked = override.checked
        if override.to_status is not None and row.kind == RowKind.PANTRY.value:
            row.to_status = PantryStatus(override.to_status).value

    for row in rows:
        if not row.checked:
            row.applied = False
            continue
        if row.kind == RowKind.PANTRY.value:
            item = (
                await session.get(PantryItem, row.pantry_item_id)
                if row.pantry_item_id is not None
                else None
            )
            if item is None or item.archived_at is not None:
                row.applied = False
                row.note = GONE_NOTE
                continue
            row.before_status = item.status
            if item.status != row.to_status:
                await set_status(session, item.id, PantryStatus(row.to_status))
            row.applied = True
        elif row.kind == RowKind.LIST.value:
            added = await add_item(session, row.label, row.ingredient_id)
            row.shopping_item_id = added.item.id
            row.list_added = added.added
            row.applied = True
        # `unlist` è delle schede inverse (Task 3)

    card.status = CardStatus.APPLIED.value
    card.applied_at = datetime.now(UTC)
    await session.flush()
    return await _reload(session, card.id)


async def discard_card(session: AsyncSession, card_id: uuid.UUID) -> ChangeCard:
    card = await _locked(session, card_id)
    _must_be_proposed(card)
    card.status = CardStatus.DISCARDED.value
    card.discarded_at = datetime.now(UTC)
    await session.flush()
    return await _reload(session, card.id)
