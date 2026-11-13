"""Le proposte di pasti della pianificazione e «Metti nella settimana» (spec §5.2, piano
6c, decisioni 11–14 e 26).

Claude propone i pasti con `propose_meals`: una proposta è una scheda posto per posto,
e una nuova sostituisce quella aperta della stessa conversazione. Mattia la mette nella
settimana con `place_proposal`, una volta sola. Che cosa fa ogni riga su un posto già
occupato lo decide il backend (`row_occupants`), non il telefono.

Tutto fa `flush`, mai `commit`: la transazione è di chi chiama.
"""

import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Any, Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.change_card import CardStatus, ChangeCard
from app.db.models.conversation import Conversation
from app.db.models.meal import Meal
from app.db.models.planning import MealProposal, ProposalKind, ProposalStatus
from app.domain.meals import MealSlot, MealStatus, slot_rank
from app.repositories.meals import meal_at
from app.schemas.meal import MealRefOut
from app.schemas.meal_proposal import MealProposalOut, ProposalRowOut
from app.services.claude.prompts import SLOT_NAMES, day_name
from app.services.meals import create_meal, update_meal


@dataclass(frozen=True)
class ProposedMeal:
    day: date
    slot: MealSlot
    dish: str
    sides: str | None


class PlanningRefusalCode(StrEnum):
    PAST = "proposal_past"
    DUPLICATE_SLOT = "proposal_duplicate"
    PLACED = "proposal_placed"
    SUPERSEDED = "proposal_superseded"
    SLOTS_TAKEN = "slots_taken"


class PlanningRefusal(Exception):
    def __init__(
        self,
        code: PlanningRefusalCode,
        message: str,
        occupants: list[Meal] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.occupants: list[Meal] = list(occupants or [])


RowEffect = Literal["new", "officialize", "replace"]


@dataclass(frozen=True)
class Placement:
    proposal: MealProposal
    meals: list[Meal] = field(default_factory=list)
    follow_up: str = ""


def _place_label(day: date, slot: MealSlot | str) -> str:
    """«venerdì 13 novembre · cena», come `longDayLabel` e `SLOT_LABELS` del frontend."""
    return f"{day_name(day)} · {SLOT_NAMES[MealSlot(slot).value]}"


def _row_place(row: dict[str, Any]) -> tuple[date, MealSlot]:
    return date.fromisoformat(row["day"]), MealSlot(row["slot"])


async def propose_meals(
    session: AsyncSession,
    *,
    conversation_id: uuid.UUID,
    turn_message_id: uuid.UUID | None,
    kind: ProposalKind,
    meals: Sequence[ProposedMeal],
    today: date,
) -> MealProposal:
    """Salva la proposta di Claude, legata al giro che l'ha fatta (decisione 11), e rende
    `superseded` le proposte ancora aperte della conversazione (decisione 12). Mai nel
    passato e mai due pasti nello stesso posto: i rifiuti arrivano prima di scrivere."""
    seen: set[tuple[date, str]] = set()
    for meal in meals:
        if meal.day < today:
            raise PlanningRefusal(
                PlanningRefusalCode.PAST,
                f"Non si pianifica nel passato: {day_name(meal.day)} è prima di oggi.",
            )
    for meal in meals:
        place = (meal.day, MealSlot(meal.slot).value)
        if place in seen:
            raise PlanningRefusal(
                PlanningRefusalCode.DUPLICATE_SLOT,
                f"Due pasti nello stesso posto: {_place_label(meal.day, meal.slot)}.",
            )
        seen.add(place)

    await session.execute(
        update(MealProposal)
        .where(
            MealProposal.conversation_id == conversation_id,
            MealProposal.status == ProposalStatus.OPEN.value,
        )
        .values(status=ProposalStatus.SUPERSEDED.value)
        .execution_options(synchronize_session="fetch")
    )
    ordered = sorted(meals, key=lambda m: (m.day, slot_rank(MealSlot(m.slot))))
    proposal = MealProposal(
        conversation_id=conversation_id,
        turn_message_id=turn_message_id,
        kind=ProposalKind(kind).value,
        status=ProposalStatus.OPEN.value,
        rows=[
            {
                "day": m.day.isoformat(),
                "slot": MealSlot(m.slot).value,
                "dish": m.dish.strip(),
                "sides": (m.sides or "").strip() or None,
                "meal_id": None,
            }
            for m in ordered
        ],
        # scritto qui: due proposte nella stessa transazione hanno un ordine, `now()` no
        created_at=datetime.now(UTC),
    )
    session.add(proposal)
    await session.flush()
    return proposal


def _effect(proposal: MealProposal, occupant: Meal | None) -> RowEffect:
    if occupant is None:
        return "new"
    if (
        proposal.kind == ProposalKind.OFFICIAL.value
        and occupant.status == MealStatus.DRAFT.value
        and not occupant.away
        and occupant.leftover_of_id is None
    ):
        return "officialize"
    return "replace"


async def row_occupants(
    session: AsyncSession, proposal: MealProposal
) -> list[tuple[dict[str, Any], Meal | None, RowEffect]]:
    """Per ogni riga, chi c'è adesso nel suo posto e che cosa la riga gli farebbe
    (decisione 13), letto dal vivo: posto vuoto → `new`; proposta ufficiale su una bozza
    → `officialize`; qualunque altro occupante → `replace`, che chiede la conferma.

    Una bozza fuori casa o avanzo di un altro pasto non si ufficializza riscrivendone il
    piatto: si sostituisce, con la conferma."""
    found: list[tuple[dict[str, Any], Meal | None, RowEffect]] = []
    for row in proposal.rows:
        day, slot = _row_place(row)
        occupant = await meal_at(session, day, slot)
        found.append((row, occupant, _effect(proposal, occupant)))
    return found


def _ref(meal: Meal) -> MealRefOut:
    return MealRefOut(
        id=meal.id, day=meal.day, slot=MealSlot(meal.slot), dish=meal.dish,
        recipe_id=meal.recipe_id,
    )


async def proposal_out(session: AsyncSession, proposal: MealProposal) -> MealProposalOut:
    """La proposta per la chat. Finché è aperta, ogni riga dice che cosa farebbe al suo
    posto adesso (`row_occupants`, dal vivo). Messa o sostituita non fa più niente: le
    righe sono `new` senza occupante, perché l'occupante di una proposta messa sarebbe il
    pasto che lei stessa ha messo."""
    if proposal.status == ProposalStatus.OPEN.value:
        live = await row_occupants(session, proposal)
    else:
        live = [(row, None, "new") for row in proposal.rows]
    return MealProposalOut(
        id=proposal.id,
        kind=proposal.kind,  # type: ignore[arg-type]
        status=proposal.status,  # type: ignore[arg-type]
        rows=[
            ProposalRowOut(
                day=date.fromisoformat(row["day"]),
                slot=MealSlot(row["slot"]),
                dish=row["dish"],
                sides=row.get("sides"),
                effect=effect,
                occupant=_ref(occupant) if occupant is not None else None,
                meal_id=uuid.UUID(row["meal_id"]) if row.get("meal_id") else None,
            )
            for row, occupant, effect in live
        ],
        created_at=proposal.created_at,
    )


def _follow_up(kind: ProposalKind, rows: Sequence[dict[str, Any]]) -> str:
    listed = "; ".join(
        f"{_place_label(*_row_place(row))}, {row['dish']}" for row in rows
    )
    if kind == ProposalKind.OFFICIAL:
        return f"Ho messo nella settimana: {listed}. Mandami la scheda dei cambi."
    return (
        f"Ho messo nella settimana come bozza: {listed}. Mandami le cose da mettere in lista."
    )


async def place_proposal(
    session: AsyncSession, proposal_id: uuid.UUID, *, replace: bool, now: datetime
) -> Placement:
    """«Metti nella settimana»: mette i pasti della proposta, una volta sola.

    Prima blocca la proposta (`SELECT … FOR UPDATE`) e solo dopo ne guarda lo stato: due
    tocchi contemporanei si mettono in fila e il secondo trova `placed` (decisione 12),
    invece di creare due volte gli stessi pasti.

    Ogni riga fa quello che dice la decisione 13: posto vuoto → un pasto nuovo, ufficiale o
    bozza come la proposta; proposta ufficiale su una bozza → la bozza diventa ufficiale,
    stesso pasto con piatto e accompagnamenti nuovi, senza conferma, perché è proprio
    l'ufficializzazione; qualunque altro occupante (ufficiale, fuori casa, bozza sotto una
    proposta di bozza) si sostituisce solo con `replace`, passando da
    `create_meal(replace=True)`, quindi con la scheda inversa del vecchio se ne ha una.

    Tutto si controlla prima di scrivere: un posto occupato senza conferma rifiuta la
    messa intera con l'elenco degli occupanti, e niente è cambiato. Se si scrivesse riga
    per riga, il rifiuto arriverebbe a metà, con i primi pasti già nella settimana e una
    proposta ancora aperta che a rimetterla li troverebbe come occupanti.

    Sui pasti ufficiali `recipe_requested_at = now`: le ricette si scrivono dopo
    l'ufficializzazione (decisione 4), e chi chiama le mette in coda dopo il commit.
    """
    proposal = (
        await session.execute(
            select(MealProposal)
            .where(MealProposal.id == proposal_id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
    ).scalar_one_or_none()
    if proposal is None:
        raise KeyError(proposal_id)
    if proposal.status == ProposalStatus.PLACED.value:
        raise PlanningRefusal(
            PlanningRefusalCode.PLACED, "Questa proposta è già nella settimana."
        )
    if proposal.status == ProposalStatus.SUPERSEDED.value:
        raise PlanningRefusal(
            PlanningRefusalCode.SUPERSEDED, "C'è una proposta più nuova: usa quella."
        )

    rows = await row_occupants(session, proposal)
    taken = [occupant for _, occupant, effect in rows if effect == "replace"]
    if taken and not replace:
        raise PlanningRefusal(
            PlanningRefusalCode.SLOTS_TAKEN, "Alcuni posti sono occupati.", taken
        )

    kind = ProposalKind(proposal.kind)
    official = kind == ProposalKind.OFFICIAL
    meals: list[Meal] = []
    placed_rows: list[dict[str, Any]] = []
    for row, occupant, effect in rows:
        day, slot = _row_place(row)
        if effect == "officialize":
            assert occupant is not None
            meal = await update_meal(
                session, occupant,
                {"dish": row["dish"], "sides": row["sides"], "status": MealStatus.OFFICIAL.value},
            )
        else:
            meal = await create_meal(
                session, day=day, slot=slot, dish=row["dish"], sides=row["sides"],
                status=MealStatus.OFFICIAL if official else MealStatus.DRAFT,
                replace=effect == "replace",
            )
        if official:
            meal.recipe_requested_at = now
            meal.recipe_notice = None
        meals.append(meal)
        placed_rows.append({**row, "meal_id": str(meal.id)})

    # una lista nuova: JSONB non vede le modifiche fatte dentro la lista di prima
    proposal.rows = placed_rows
    proposal.status = ProposalStatus.PLACED.value
    proposal.placed_at = now
    await session.flush()
    return Placement(proposal=proposal, meals=meals, follow_up=_follow_up(kind, placed_rows))


async def planning_concluded(
    session: AsyncSession, conversation: Conversation, today: date
) -> bool:
    """Calcolato, non salvato (decisione 26): la conversazione è conclusa quando ha almeno
    una proposta messa, nessuna aperta, nessuna sua scheda ancora proposta, una sua scheda
    applicata o scartata dopo l'ultima messa, e nessuna bozza messa da lei che sia ancora
    bozza da oggi in avanti. Così il giro della bozza resta aperto fino
    all'ufficializzazione, e «Pianifica con Claude» riporta Mattia lì dopo la spesa."""
    proposals = (
        await session.execute(
            select(MealProposal.status, MealProposal.placed_at, MealProposal.rows).where(
                MealProposal.conversation_id == conversation.id
            )
        )
    ).all()
    if any(status == ProposalStatus.OPEN.value for status, _, _ in proposals):
        return False
    placed = [
        (placed_at, rows)
        for status, placed_at, rows in proposals
        if status == ProposalStatus.PLACED.value
    ]
    if not placed:
        return False
    last_placed = max(placed_at for placed_at, _ in placed)

    cards = (
        await session.execute(
            select(ChangeCard.status, ChangeCard.applied_at, ChangeCard.discarded_at).where(
                ChangeCard.conversation_id == conversation.id
            )
        )
    ).all()
    if any(status == CardStatus.PROPOSED.value for status, _, _ in cards):
        return False
    if not any(
        (applied_at is not None and applied_at > last_placed)
        or (discarded_at is not None and discarded_at > last_placed)
        for _, applied_at, discarded_at in cards
    ):
        return False

    meal_ids = {
        uuid.UUID(row["meal_id"]) for _, rows in placed for row in rows if row.get("meal_id")
    }
    if not meal_ids:
        return True
    open_draft = (
        await session.execute(
            select(Meal.id)
            .where(
                Meal.id.in_(meal_ids),
                Meal.status == MealStatus.DRAFT.value,
                Meal.day >= today,
            )
            .limit(1)
        )
    ).scalar_one_or_none()
    return open_draft is None


async def conversation_for_meal(
    session: AsyncSession, meal_id: uuid.UUID
) -> uuid.UUID | None:
    """La conversazione in cui il pasto è stato deciso: quella dell'ultima proposta messa
    che lo contiene (decisione 17, per la storia del giro della ricetta)."""
    statement = (
        select(MealProposal.conversation_id)
        .where(
            MealProposal.status == ProposalStatus.PLACED.value,
            MealProposal.rows.contains([{"meal_id": str(meal_id)}]),
        )
        .order_by(MealProposal.placed_at.desc(), MealProposal.id)
        .limit(1)
    )
    return (await session.execute(statement)).scalar_one_or_none()
