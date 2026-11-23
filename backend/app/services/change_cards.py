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
from datetime import UTC, date, datetime
from enum import StrEnum

from sqlalchemy import or_, select
from sqlalchemy.dialects.postgresql import array
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.models.change_card import (
    CardKind,
    CardStatus,
    ChangeCard,
    ChangeCardRow,
    RowKind,
)
from app.db.models.ingredient import Ingredient
from app.db.models.meal import Meal
from app.db.models.pantry import PantryItem
from app.db.models.shopping import ShoppingListItem, ShoppingStatus
from app.domain.change_cards import adds_to_list, most_consumed
from app.domain.meals import MealStatus
from app.domain.rules import PantryStatus
from app.repositories.pantry import set_status
from app.repositories.shopping import active_item_for, add_item, patch_item
from app.services.ingredient_match import exact_ingredient

ALREADY_LISTED_NOTE = "Già in lista."
GONE_NOTE = "La voce non è più in dispensa."
CHANGED_NOTE = "Cambiata dopo la scheda: controlla prima di rimetterla."
IN_CART_NOTE = "È già nel carrello."
BOUGHT_NOTE = "Già comprata: resta com'è."
REVERSED_NOTE = "Già rimessa da un'altra scheda."
PAST_MEAL_NOTE = "Pasto già passato: rimettila solo se non l'hai mangiato."
NO_LONGER_FINISHED_NOTE = "Non va in lista: nella scheda la voce non diventa più «Finito»."
NOW_FINISHED_NOTE = "In lista perché nella scheda la voce diventa «Finito»."


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


SUPERSEDED_SENTENCE = "Sostituita da una scheda più nuova."


class CardRefusalCode(StrEnum):
    ALREADY_APPLIED = "card_applied"
    DISCARDED = "card_discarded"
    SUPERSEDED = "card_superseded"
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
    _refuse_if_not_food(item.ingredient)
    return item


def _refuse_if_not_food(ingredient: Ingredient | None) -> None:
    """La scheda è di ciò che usano i pasti, in dispensa e fra le cose da comprare
    (C-R5): un non alimentare non ci va mai, nemmeno come riga della lista. Il
    detersivo si scrive in lista da sé."""
    if ingredient is not None and ingredient.kind != "food":
        raise CardRefusal(
            CardRefusalCode.NOT_FOOD,
            f"«{ingredient.name}» non è un alimento: la scheda dei cambi tocca la "
            "dispensa di cibo.",
        )


async def _list_ingredient(
    session: AsyncSession, ingredient_id: uuid.UUID | None, raw_text: str
) -> uuid.UUID | None:
    """L'ingrediente di una riga della lista: quello dato, o la coincidenza esatta del
    testo (come `add_item`). Un non alimentare si rifiuta; un testo che non è niente
    dell'anagrafica resta libero."""
    if ingredient_id is not None:
        ingredient = await session.get(Ingredient, ingredient_id)
    else:
        ingredient = await exact_ingredient(session, raw_text)
    _refuse_if_not_food(ingredient)
    if ingredient_id is not None:
        return ingredient_id
    return ingredient.id if ingredient is not None else None


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

    # una riga di lista per ingrediente: chi finisce ci va da sé (decisione 19). Ognuna
    # ricorda le voci di dispensa che l'hanno portata e se Claude l'ha chiesta da sé:
    # chiesta, sta in piedi da sola (decisione 15).
    list_rows: dict[str, dict] = {}
    free_rows: list[dict] = []

    def add_list(
        ingredient_id, label: str, mine: list[str], *, from_item: str | None = None
    ) -> None:
        if ingredient_id is None:
            free_rows.append({
                "ingredient_id": None, "label": label, "meal_ids": mine,
                "from_items": [], "asked": True,
            })
            return
        key = str(ingredient_id)
        if key in list_rows:
            list_rows[key]["meal_ids"] = _union(list_rows[key]["meal_ids"], mine)
        else:
            list_rows[key] = {
                "ingredient_id": ingredient_id, "label": label, "meal_ids": mine,
                "from_items": [], "asked": False,
            }
        if from_item is None:
            list_rows[key]["asked"] = True
        else:
            list_rows[key]["from_items"].append(from_item)

    for key, row in pantry_rows.items():
        if adds_to_list(row["to_status"]):
            add_list(
                row["item"].ingredient_id, _label(row["item"]), row["meal_ids"], from_item=key
            )
    for proposal in shopping:
        ingredient_id = await _list_ingredient(
            session, proposal.ingredient_id, proposal.raw_text
        )
        add_list(ingredient_id, proposal.raw_text.strip(), _ids(proposal.meal_ids) or card_meals)

    card = _new_card(
        kind=CardKind.FORWARD.value, list_only=list_only, title=_title(meals, list_only),
        meal_ids=card_meals, conversation_id=conversation_id, turn_message_id=turn_message_id,
    )
    session.add(card)
    await session.flush()

    # prima le righe di dispensa, perché quelle di lista ne ricordano gli id
    position = 0
    written: dict[str, ChangeCardRow] = {}
    for key, row in pantry_rows.items():
        item = row["item"]
        written[key] = ChangeCardRow(
            card_id=card.id, position=position, kind=RowKind.PANTRY.value,
            label=_label(item), pantry_item_id=item.id, ingredient_id=item.ingredient_id,
            to_status=row["to_status"], checked=True, editable=True, meal_ids=row["meal_ids"],
        )
        session.add(written[key])
        position += 1
    await session.flush()
    pantry_row_ids = {key: str(written_row.id) for key, written_row in written.items()}
    for row in [*list_rows.values(), *free_rows]:
        session.add(ChangeCardRow(
            card_id=card.id, position=position, kind=RowKind.LIST.value, label=row["label"],
            ingredient_id=row["ingredient_id"], meal_ids=row["meal_ids"],
            from_pantry_row_ids=(
                [] if row["asked"] else [pantry_row_ids[key] for key in row["from_items"]]
            ),
            **await _list_row_fields(session, row["ingredient_id"]),
        ))
        position += 1
    await session.flush()
    await _supersede_older(session, card)
    return await _reload(session, card.id)


def _supersedes(old_meal_ids: Sequence[str], new_meal_ids: Sequence[str]) -> bool:
    # "Lo stesso pasto" per una scheda di più pasti: tutti i suoi pasti sono nella nuova
    # (Mattia, 2026-11-21; piano 2026-11-18-pasti-correzioni, decisione 10).
    return bool(old_meal_ids) and set(old_meal_ids) <= set(new_meal_ids)


async def _supersede_older(session: AsyncSession, new_card: ChangeCard) -> None:
    """Le schede in avanti ancora proposte, tutte nei pasti della nuova, si mettono da parte.
    Le inverse non si toccano mai."""
    older = (
        await session.execute(
            select(ChangeCard).where(
                ChangeCard.kind == CardKind.FORWARD.value,
                ChangeCard.status == CardStatus.PROPOSED.value,
                ChangeCard.id != new_card.id,
            )
            # Il lock chiude la corsa con `apply_card`: se la vecchia scheda è appena stata
            # applicata, Postgres rilegge lo stato dopo l'attesa e la salta.
            .order_by(ChangeCard.id)
            .with_for_update()
        )
    ).scalars().all()
    now = datetime.now(UTC)
    for old in older:
        if _supersedes(old.meal_ids, new_card.meal_ids):
            old.status = CardStatus.SUPERSEDED.value
            old.discarded_at = now


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
    if card.status == CardStatus.SUPERSEDED.value:
        raise CardRefusal(CardRefusalCode.SUPERSEDED, SUPERSEDED_SENTENCE)


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
        ingredient_id = await _list_ingredient(session, None, text)
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


async def open_cards_for_meals(
    session: AsyncSession, meal_ids: Sequence[uuid.UUID]
) -> dict[uuid.UUID, uuid.UUID]:
    """La scheda aperta di ciascun pasto, con una query sola (C-R7): per ogni pasto la
    proposta più recente. Un pasto senza scheda aperta non compare."""
    if not meal_ids:
        return {}
    wanted = {str(m): m for m in meal_ids}
    statement = (
        select(ChangeCard.id, ChangeCard.meal_ids)
        .where(
            ChangeCard.status == CardStatus.PROPOSED.value,
            ChangeCard.meal_ids.has_any(array(list(wanted))),
        )
        .order_by(ChangeCard.created_at.desc(), ChangeCard.id)
    )
    found: dict[uuid.UUID, uuid.UUID] = {}
    for card_id, card_meals in (await session.execute(statement)).all():
        for meal in card_meals:
            if meal in wanted:
                found.setdefault(wanted[meal], card_id)
    return found


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


def _origins(row: ChangeCardRow) -> list[uuid.UUID]:
    """Le righe d'origine di una riga inversa; una scritta prima della 0024 ha solo
    `source_row_id`."""
    if row.source_row_ids:
        return [uuid.UUID(value) for value in row.source_row_ids]
    return [row.source_row_id] if row.source_row_id is not None else []


async def _follow_the_pantry(
    session: AsyncSession, card: ChangeCard, rows: list[ChangeCardRow]
) -> set[uuid.UUID]:
    """Le righe di lista seguono la scheda come Mattia l'ha corretta (decisioni 4 e 15).

    Aggiunge a `rows` una riga di lista per ogni riga di dispensa spuntata che adesso va a
    `finished`, la cui voce viva non è già finita, e il cui ingrediente non ha nessuna riga
    di lista nella scheda; se quella riga c'è e viene da altre righe di dispensa, questa si
    aggiunge alle sue origini, così non si salta proprio quando la voce diventa «Finito».
    Restituisce le righe di lista da saltare: quelle che hanno origini e nessuna delle quali
    diventa più `finished`. Una riga senza origini sta in piedi da sola e non si salta mai.
    """
    finished = PantryStatus.FINISHED.value
    by_ingredient = {
        row.ingredient_id: row
        for row in rows
        if row.kind == RowKind.LIST.value and row.ingredient_id is not None
    }
    position = max((row.position for row in rows), default=-1) + 1
    added = False
    for row in list(rows):
        if row.kind != RowKind.PANTRY.value or not row.checked or row.to_status != finished:
            continue
        item = (
            await session.get(PantryItem, row.pantry_item_id)
            if row.pantry_item_id is not None
            else None
        )
        if item is None or item.archived_at is not None or item.status == finished:
            continue
        listed = by_ingredient.get(item.ingredient_id)
        if listed is None:
            await session.refresh(item, ["ingredient", "product"])
            listed = ChangeCardRow(
                card_id=card.id, position=position, kind=RowKind.LIST.value,
                label=_label(item), ingredient_id=item.ingredient_id, checked=True,
                editable=True, note=NOW_FINISHED_NOTE, meal_ids=list(row.meal_ids),
                from_pantry_row_ids=[str(row.id)],
            )
            session.add(listed)
            rows.append(listed)
            by_ingredient[item.ingredient_id] = listed
            position += 1
            added = True
        elif listed.from_pantry_row_ids and str(row.id) not in listed.from_pantry_row_ids:
            listed.from_pantry_row_ids = [*listed.from_pantry_row_ids, str(row.id)]
            listed.meal_ids = _union(listed.meal_ids, row.meal_ids)
    if added:
        await session.flush()

    finishing = {
        str(row.id)
        for row in rows
        if row.kind == RowKind.PANTRY.value and row.to_status == finished
    }
    return {
        row.id
        for row in rows
        if row.kind == RowKind.LIST.value
        and row.from_pantry_row_ids
        and finishing.isdisjoint(row.from_pantry_row_ids)
    }


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

    Una scheda inversa ha righe `pantry` come le altre e righe `unlist`, che tolgono
    dalla lista con `patch_item` (la strada di «Togli») una voce ancora da comprare o
    nel carrello; ogni sua riga applicata segna la riga d'origine con `reversed_at`, e
    una riga la cui origine è già annullata si salta con la sua nota, senza toccare
    niente: due inverse non rimettono mai due volte, nemmeno applicate insieme, perché le
    righe d'origine si bloccano (`FOR UPDATE`, in ordine di id) prima di leggere
    `reversed_at`. Una riga inversa di dispensa ha più origini (`source_row_ids`): le
    segna tutte, e si salta se una qualunque è già annullata.

    **La lista segue la scheda corretta** (decisioni 4 e 15): la regola del barattolo
    avviato — solo `finished` porta in lista — vale sulla scheda come Mattia l'ha
    corretta, non su quella che Claude aveva proposto. Dopo le correzioni, una riga di
    lista portata da righe di dispensa (`from_pantry_row_ids`) si salta, con
    `NO_LONGER_FINISHED_NOTE`, se nessuna di loro va più a `finished`; e una riga di
    dispensa spuntata che adesso va a `finished`, su una voce non ancora finita, porta in
    lista il suo ingrediente con una riga nuova (`NOW_FINISHED_NOTE`), se la scheda non ne
    ha già una. La riga nuova passa da `add_item` come le altre, quindi non duplica mai.
    La spunta di una riga di dispensa non conta per il salto: una riga non spuntata che
    va a `finished` lascia la sua riga di lista com'è. Una riga di lista senza origini —
    chiesta da Claude, aggiunta a mano, o scritta prima della 0026 — sta in piedi da sola
    e si applica come sempre: perché la voce serve, non perché finisce. Vale solo per le
    schede in avanti: un'inversa che rimette una voce «Finito» non la porta in lista.
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

    # Le righe d'origine di un'inversa si bloccano anche loro, in ordine di id (niente
    # stalli), prima di leggere `reversed_at`: due inverse **diverse** con la stessa
    # origine applicate insieme si mettono in fila, e la seconda la trova già annullata.
    source_ids = sorted({origin for row in rows for origin in _origins(row)})
    sources: dict[uuid.UUID, ChangeCardRow] = {}
    if source_ids:
        locked = await session.execute(
            select(ChangeCardRow)
            .where(ChangeCardRow.id.in_(source_ids))
            .order_by(ChangeCardRow.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        sources = {source.id: source for source in locked.scalars()}

    no_longer_finished = (
        await _follow_the_pantry(session, card, rows)
        if card.kind == CardKind.FORWARD.value
        else set()
    )

    for row in rows:
        if not row.checked:
            row.applied = False
            continue
        if row.id in no_longer_finished:
            row.applied = False
            row.note = NO_LONGER_FINISHED_NOTE
            continue
        origins = [sources[o] for o in _origins(row) if o in sources]
        if any(origin.reversed_at is not None for origin in origins):
            # un'altra inversa l'ha già rimessa: rimetterla di nuovo cancellerebbe
            # quello che è successo dopo (decisione 22)
            row.applied = False
            row.note = REVERSED_NOTE
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
        elif row.kind == RowKind.UNLIST.value:
            # la stessa strada di «Togli» della lista; una voce comprata nel frattempo
            # (sistemata, o tolta a mano) resta com'è
            listed = (
                await session.get(ShoppingListItem, row.shopping_item_id)
                if row.shopping_item_id is not None
                else None
            )
            if listed is None or listed.status not in (
                ShoppingStatus.PENDING, ShoppingStatus.CHECKED
            ):
                row.applied = False
                row.note = BOUGHT_NOTE
                continue
            await patch_item(session, listed.id, status=ShoppingStatus.ARCHIVED)
            row.applied = True
        if row.applied:
            # le righe della scheda in avanti sono annullate: un'altra inversa non le rimette
            for origin in origins:
                origin.reversed_at = datetime.now(UTC)

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


# --- la scheda inversa (decisione 22) ------------------------------------------------


class InverseReason(StrEnum):
    DELETED = "deleted"
    REPLACED = "replaced"
    AWAY = "away"


def _inverse_title(meal: Meal, reason: InverseReason) -> str:
    if reason == InverseReason.DELETED:
        return f"Hai tolto «{meal.dish}»: rimetti quello che usava?"
    if reason == InverseReason.REPLACED:
        return f"Hai sostituito «{meal.dish}»: rimetti quello che usava?"
    return f"«{meal.dish}» è fuori casa: rimetti quello che usava?"


async def _still_used_elsewhere(
    session: AsyncSession, row: ChangeCardRow, meal_id: str
) -> bool:
    """La riga serve anche a un altro pasto ancora ufficiale e non fuori casa: la usa
    ancora lui, e rimetterla gli toglierebbe quello che la scheda gli aveva dato."""
    for other in row.meal_ids:
        if other == meal_id:
            continue
        meal = await session.get(Meal, uuid.UUID(other))
        if meal is not None and meal.status == MealStatus.OFFICIAL.value and not meal.away:
            return True
    return False


async def _list_still_needed(
    session: AsyncSession, source: ChangeCardRow, meal_id: str
) -> bool:
    """La voce di lista serve ancora a un altro pasto: o lo dice la riga stessa
    (`_still_used_elsewhere`), o un'altra scheda in avanti, proposta o applicata, ha una
    riga di lista per lo stesso ingrediente al servizio di un altro pasto ufficiale e non
    fuori casa (anche se la sua riga era «Già in lista.» e non è mai stata applicata). Non
    conta una riga saltata con `NO_LONGER_FINISHED_NOTE`: la scheda stessa ha detto che al
    suo pasto non serve. Non conta nemmeno una riga che Mattia ha lasciato senza spunta
    applicando la scheda (modificabile, `applied` falso): non dice che la voce serve a
    quel pasto (decisione 5 del piano «pasti, quarto giro»)."""
    if await _still_used_elsewhere(session, source, meal_id):
        return True
    if source.ingredient_id is None:
        return False
    others = (
        await session.execute(
            select(ChangeCardRow.meal_ids)
            .join(ChangeCard, ChangeCard.id == ChangeCardRow.card_id)
            .where(
                ChangeCard.kind == CardKind.FORWARD.value,
                ChangeCard.status.in_(
                    [CardStatus.PROPOSED.value, CardStatus.APPLIED.value]
                ),
                ChangeCardRow.kind == RowKind.LIST.value,
                ChangeCardRow.ingredient_id == source.ingredient_id,
                ChangeCardRow.id != source.id,
                # una riga che la sua scheda ha saltato perché la voce non finisce più
                # non serve al suo pasto (F-R5)
                ChangeCardRow.note.is_distinct_from(NO_LONGER_FINISHED_NOTE),
                # una riga modificabile che Mattia ha smarcato su una scheda già applicata
                # non tiene la voce (decisione 5): contano le schede ancora proposte, le
                # righe applicate e quelle non modificabili («Già in lista.»)
                or_(
                    ChangeCard.status == CardStatus.PROPOSED.value,
                    ChangeCardRow.applied.is_(True),
                    ChangeCardRow.editable.is_(False),
                ),
            )
        )
    ).scalars().all()
    for meal_ids in others:
        probe = ChangeCardRow(meal_ids=meal_ids)
        if await _still_used_elsewhere(session, probe, meal_id):
            return True
    return False


async def _drop_meal_from_proposed(session: AsyncSession, meal_id: str) -> None:
    """Le schede in avanti ancora proposte di quel pasto perdono le righe che servivano
    solo a lui; una che resta senza righe e senza pasti si scarta da sola."""
    cards = (
        await session.execute(
            select(ChangeCard)
            .options(selectinload(ChangeCard.rows))
            .where(
                ChangeCard.kind == CardKind.FORWARD.value,
                ChangeCard.status == CardStatus.PROPOSED.value,
                ChangeCard.meal_ids.contains([meal_id]),
            )
            .execution_options(populate_existing=True)
        )
    ).scalars().all()
    for card in cards:
        remaining = 0
        for row in card.rows:
            if meal_id not in row.meal_ids:
                remaining += 1
                continue
            others = [m for m in row.meal_ids if m != meal_id]
            if others:
                row.meal_ids = others
                remaining += 1
            else:
                await session.delete(row)
        card.meal_ids = [m for m in card.meal_ids if m != meal_id]
        if remaining == 0 and not card.meal_ids:
            card.status = CardStatus.DISCARDED.value
            card.discarded_at = datetime.now(UTC)
    if cards:
        await session.flush()


async def discard_proposed_inverses(session: AsyncSession, meal_id: str) -> None:
    """Una scheda inversa sola per pasto: quella nuova si ricalcola dalle stesse righe
    d'origine sullo stato di adesso, quindi prende il posto delle vecchie ancora
    proposte (per esempio quella del «fuori casa» quando poi il pasto si toglie)."""
    cards = (
        await session.execute(
            select(ChangeCard)
            .where(
                ChangeCard.kind == CardKind.INVERSE.value,
                ChangeCard.status == CardStatus.PROPOSED.value,
                ChangeCard.meal_ids.contains([meal_id]),
            )
            .execution_options(populate_existing=True)
        )
    ).scalars().all()
    for card in cards:
        card.status = CardStatus.DISCARDED.value
        card.discarded_at = datetime.now(UTC)
    if cards:
        await session.flush()


async def _inverse_pantry_group(
    session: AsyncSession, sources: Sequence[ChangeCardRow]
) -> dict[str, object] | None:
    """L'effetto netto del pasto su una voce di dispensa. `sources` sono le righe
    d'origine della voce, dalla più recente alla più vecchia: si rimette lo stato di
    prima della più vecchia, e la riga è spuntata se la voce è ancora nello stato che le
    ha dato la più recente."""
    newest, oldest = sources[0], sources[-1]
    if newest.pantry_item_id is None or oldest.before_status is None:
        return None
    item = await session.get(PantryItem, newest.pantry_item_id)
    if item is None or item.archived_at is not None:
        return None  # la voce non c'è più
    if item.status == oldest.before_status:
        return None  # è già com'era prima delle schede
    await session.refresh(item, ["ingredient", "product"])
    unchanged = item.status == newest.to_status
    return {
        "kind": RowKind.PANTRY.value, "label": _label(item), "pantry_item_id": item.id,
        "ingredient_id": item.ingredient_id, "to_status": oldest.before_status,
        "checked": unchanged, "editable": True,
        "note": None if unchanged else CHANGED_NOTE,
        "source_row_id": oldest.id,
        "source_row_ids": [str(source.id) for source in sources],
    }


async def _inverse_list_row(
    session: AsyncSession, source: ChangeCardRow
) -> dict[str, object] | None:
    # solo ciò che la scheda aveva davvero aggiunto: una voce che era già in lista
    # c'era prima della scheda, e resta
    if source.list_added is not True or source.shopping_item_id is None:
        return None
    item = await session.get(ShoppingListItem, source.shopping_item_id)
    if item is None:
        return None
    if item.status == ShoppingStatus.PENDING:
        checked, note = True, None
    elif item.status == ShoppingStatus.CHECKED:
        checked, note = False, IN_CART_NOTE
    else:
        return None  # sistemata (comprata di nuovo) o tolta a mano: non si tocca
    return {
        "kind": RowKind.UNLIST.value, "label": item.raw_text, "shopping_item_id": item.id,
        "ingredient_id": item.ingredient_id, "checked": checked, "editable": True,
        "note": note,
    }


async def propose_inverse_card(
    session: AsyncSession, meal: Meal, reason: InverseReason, *, today: date | None = None
) -> ChangeCard | None:
    """La scheda che rimette quello che le schede applicate di `meal` avevano usato.

    Si chiama prima che il pasto si tolga, si sostituisca o vada fuori casa, dentro la
    transazione di chi chiama; spostarlo non la chiama. Nasce solo per un pasto
    ufficiale (una bozza non ha mai toccato la dispensa) e solo se ha almeno una riga.

    Perché serve una scheda conservata (spec §6.2): senza quantità l'inverso non si
    ricava dallo stato di oggi. «La ricotta è finita» non dice quanta ne usava questo
    pasto né com'era prima; lo dice solo la riga della scheda applicata, che ha tenuto
    lo stato di prima (`before_status`) e i pasti a cui serviva (`meal_ids`). Così
    l'inversa propone «ora → stato di prima» riga per riga, e Mattia la applica o la
    scarta.

    Le tre regole di sicurezza, perché rimettere a torto sbaglia quanto non rimettere:
    - **serve ancora a un altro pasto**: una riga che serve anche a un pasto ancora
      ufficiale e non fuori casa si salta, perché lui la usa ancora; per una voce di lista
      vale anche la riga di lista di un'altra scheda (proposta o applicata) per lo stesso
      ingrediente, al servizio di un altro pasto così;
    - **cambiata dopo**: una voce di dispensa che non è più nello stato che la scheda le
      aveva dato è stata toccata da qualcuno dopo, e la riga c'è ma non è spuntata, con
      la nota; una voce già tornata allo stato di prima, o sparita, non ha riga;
    - **comprata di nuovo**: dalla lista si toglie solo ciò che la scheda aveva davvero
      aggiunto e che è ancora da comprare (spuntato) o nel carrello (non spuntato); una
      voce sistemata in dispensa o tolta non si tocca, e la voce di dispensa nuova della
      spesa non è mai una riga di nessuna scheda, quindi resta com'è.

    **Per voce**: le righe di dispensa d'origine si raggruppano per voce e la scheda
    propone l'effetto netto del pasto: lo stato di prima della riga più vecchia, spuntato
    se la voce è ancora nello stato che le ha dato la più recente. Se una riga del gruppo
    serve ancora a un altro pasto, si salta il gruppo. La riga ricorda tutte le origini.

    Le righe già annullate (`reversed_at`, scritto da `apply_card` quando applica
    un'inversa) non si ripropongono. Le righe si leggono dall'ultima scheda applicata
    alla prima, così applicandole in ordine si torna indietro nell'ordine giusto.

    **Un pasto passato che si elimina** (`reason` `DELETED`, `meal.day < today`): la scheda
    nasce lo stesso, ma nessuna riga è spuntata e quelle senza nota hanno
    `PAST_MEAL_NOTE` (`CHANGED_NOTE` e `IN_CART_NOTE` restano, più precise). Un pasto
    passato di solito si è mangiato, e quello che ha usato è davvero finito: rimettere di
    default sbaglierebbe; se non si è mangiato, Mattia spunta da sé. Sostituirlo o
    mandarlo fuori casa dice invece che non si è mangiato, e lì le spunte restano.
    `today` è di chi chiama (la rotta, con `today_in_pantry`): `None` vuol dire nessun
    controllo.

    Pulisce anche le schede in avanti ancora proposte del pasto, anche di una bozza:
    perdono le righe che servivano solo a lui, e si scartano se restano vuote e senza
    pasti. E scarta sempre, anche quando la nuova non nasce, le inverse ancora proposte
    del pasto: una sola per pasto, la più recente.
    """
    meal_id = str(meal.id)
    await _drop_meal_from_proposed(session, meal_id)
    await discard_proposed_inverses(session, meal_id)
    if meal.status != MealStatus.OFFICIAL.value:
        return None

    sources = (
        await session.execute(
            select(ChangeCardRow)
            .join(ChangeCard, ChangeCard.id == ChangeCardRow.card_id)
            .where(
                ChangeCard.kind == CardKind.FORWARD.value,
                ChangeCard.status == CardStatus.APPLIED.value,
                ChangeCardRow.applied.is_(True),
                ChangeCardRow.reversed_at.is_(None),
                ChangeCardRow.kind.in_([RowKind.PANTRY.value, RowKind.LIST.value]),
                ChangeCardRow.meal_ids.contains([meal_id]),
            )
            .order_by(
                ChangeCard.applied_at.desc(), ChangeCard.id, ChangeCardRow.position
            )
            .execution_options(populate_existing=True)
        )
    ).scalars().all()

    pantry_rows: list[dict[str, object]] = []
    unlist_rows: list[dict[str, object]] = []
    groups: dict[uuid.UUID | None, list[ChangeCardRow]] = {}
    for source in sources:
        if source.kind == RowKind.PANTRY.value:
            groups.setdefault(source.pantry_item_id, []).append(source)
            continue
        if await _list_still_needed(session, source, meal_id):
            continue
        fields = await _inverse_list_row(session, source)
        if fields is not None:
            unlist_rows.append(
                {**fields, "source_row_id": source.id, "source_row_ids": [str(source.id)]}
            )
    for group in groups.values():
        served = False
        for source in group:
            if await _still_used_elsewhere(session, source, meal_id):
                served = True
                break
        if served:
            continue
        fields = await _inverse_pantry_group(session, group)
        if fields is not None:
            pantry_rows.append(fields)
    if not pantry_rows and not unlist_rows:
        return None
    if reason == InverseReason.DELETED and today is not None and meal.day < today:
        for fields in [*pantry_rows, *unlist_rows]:
            fields["checked"] = False
            if fields["note"] is None:
                fields["note"] = PAST_MEAL_NOTE

    card = _new_card(
        kind=CardKind.INVERSE.value, list_only=False,
        title=_inverse_title(meal, InverseReason(reason)), meal_ids=[meal_id],
    )
    session.add(card)
    await session.flush()
    for position, fields in enumerate([*pantry_rows, *unlist_rows]):
        session.add(ChangeCardRow(
            card_id=card.id, position=position, meal_ids=[meal_id], **fields
        ))
    await session.flush()
    return await _reload(session, card.id)
