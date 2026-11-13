"""Il doppio tocco su due connessioni (decisioni 21 e 12): la scheda si applica una volta
sola, e una proposta si mette nella settimana una volta sola.

Su un database suo, con i dati committati, perché il blocco `FOR UPDATE` si vede solo fra
due transazioni vere; la suite normale gira in una transazione sola e non lo mostrerebbe.
"""

import asyncio
import os
import subprocess
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models.change_card import ChangeCard, ChangeCardRow
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.meal import Meal
from app.db.models.pantry import PantryItem
from app.db.models.planning import ProposalKind
from app.db.models.shopping import ShoppingListItem
from app.domain.meals import MealSlot, MealStatus
from app.domain.rules import PantryStatus
from app.repositories.conversations import create_planning
from app.services.change_cards import (
    CardRefusal,
    CardRefusalCode,
    ListProposal,
    PantryProposal,
    apply_card,
    propose_card,
)
from app.services.meals import create_meal, update_meal
from app.services.planning import (
    PlanningRefusal,
    PlanningRefusalCode,
    ProposedMeal,
    place_proposal,
    propose_meals,
)

TEST_DATABASE_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+asyncpg://spena:spena@localhost:5433/spena_test"
)
SERVER, _, TEST_DB = TEST_DATABASE_URL.rpartition("/")
SCRATCH_DB = f"{TEST_DB}_doppio_tocco"


@pytest_asyncio.fixture
async def scratch_engine():
    admin = create_async_engine(f"{SERVER}/postgres", isolation_level="AUTOCOMMIT")
    engine = None
    try:
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)'))
            await conn.execute(text(f'CREATE DATABASE "{SCRATCH_DB}"'))
        url = f"{SERVER}/{SCRATCH_DB}"
        setup = create_async_engine(url)
        async with setup.begin() as conn:
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await conn.execute(text("CREATE EXTENSION IF NOT EXISTS pg_trgm"))
        await setup.dispose()
        subprocess.run(
            ["alembic", "upgrade", "head"], check=True,
            env={**os.environ, "DATABASE_URL": url},
        )
        engine = create_async_engine(url)
        yield engine
    finally:
        if engine is not None:
            await engine.dispose()
        async with admin.connect() as conn:
            await conn.execute(text(f'DROP DATABASE IF EXISTS "{SCRATCH_DB}" WITH (FORCE)'))
        await admin.dispose()


async def test_applicare_insieme_da_due_connessioni(scratch_engine):
    maker = async_sessionmaker(scratch_engine, expire_on_commit=False)
    async with maker() as setup:
        ricotta = Ingredient(
            name="ricotta", display_name="Ricotta", category=IngredientCategory.LATTICINI
        )
        setup.add(ricotta)
        await setup.flush()
        item = PantryItem(ingredient_id=ricotta.id, status=PantryStatus.AVAILABLE)
        setup.add(item)
        meal = await create_meal(
            setup, day=date(2026, 11, 20), slot=MealSlot.DINNER, dish="Pasta alla ricotta"
        )
        card = await propose_card(
            setup, meals=[meal], pantry=[],
            shopping=[ListProposal(ricotta.id, "Ricotta")],
        )
        card_id = card.id
        await setup.commit()

    sessions: list[AsyncSession] = [maker(), maker()]

    async def tocco(session: AsyncSession):
        try:
            await apply_card(session, card_id, [])
            await session.commit()
            return "applicata"
        except CardRefusal as exc:
            await session.rollback()
            return exc.code

    try:
        risultati = await asyncio.gather(*(tocco(s) for s in sessions))
    finally:
        for s in sessions:
            await s.close()

    assert sorted(map(str, risultati)) == sorted(["applicata", CardRefusalCode.ALREADY_APPLIED.value])
    async with maker() as check:
        voci = (await check.execute(select(func.count()).select_from(ShoppingListItem))).scalar()
    assert voci == 1


async def test_mettere_insieme_da_due_connessioni(scratch_engine):
    """«Metti nella settimana» toccato due volte (decisione 12): la proposta si mette una
    volta sola, e ogni posto ha un pasto solo."""
    maker = async_sessionmaker(scratch_engine, expire_on_commit=False)
    async with maker() as setup:
        conversation = await create_planning(setup)
        proposal = await propose_meals(
            setup, conversation_id=conversation.id, turn_message_id=None,
            kind=ProposalKind.OFFICIAL,
            meals=[
                ProposedMeal(date(2026, 11, 20), MealSlot.DINNER, "Orata", None),
                ProposedMeal(date(2026, 11, 21), MealSlot.LUNCH, "Risotto", None),
            ],
            today=date(2026, 11, 12),
        )
        proposal_id = proposal.id
        await setup.commit()

    sessions: list[AsyncSession] = [maker(), maker()]

    async def tocco(session: AsyncSession):
        try:
            await place_proposal(session, proposal_id, replace=False, now=datetime.now(UTC))
            await session.commit()
            return "messa"
        except PlanningRefusal as exc:
            await session.rollback()
            return exc.code

    try:
        risultati = await asyncio.gather(*(tocco(s) for s in sessions))
    finally:
        for s in sessions:
            await s.close()

    assert sorted(map(str, risultati)) == sorted(["messa", PlanningRefusalCode.PLACED.value])
    async with maker() as check:
        pasti = (await check.execute(select(func.count()).select_from(Meal))).scalar()
    assert pasti == 2


async def test_due_inverse_della_stessa_riga_insieme_da_due_connessioni(scratch_engine):
    """Due schede inverse **diverse** con la stessa riga d'origine (decisione 22: la ricotta
    serviva ad A e alla bozza, A va fuori casa, poi la bozza ufficializzata anche), applicate
    nello stesso istante: una sola rimette, l'altra trova l'origine già annullata. Senza il
    blocco `FOR UPDATE` sulle righe d'origine le due leggerebbero entrambe `reversed_at`
    vuoto e rimetterebbero due volte."""
    maker = async_sessionmaker(scratch_engine, expire_on_commit=False)
    async with maker() as setup:
        ricotta = Ingredient(
            name="ricotta", display_name="Ricotta", category=IngredientCategory.LATTICINI
        )
        setup.add(ricotta)
        await setup.flush()
        item = PantryItem(ingredient_id=ricotta.id, status=PantryStatus.AVAILABLE)
        setup.add(item)
        await setup.flush()
        a = await create_meal(
            setup, day=date(2026, 11, 20), slot=MealSlot.DINNER, dish="Pasta alla ricotta"
        )
        bozza = await create_meal(
            setup, day=date(2026, 11, 22), slot=MealSlot.DINNER, dish="Lasagne",
            status=MealStatus.DRAFT,
        )
        avanti = await propose_card(
            setup, meals=[a, bozza], pantry=[PantryProposal(item.id, PantryStatus.FINISHED)],
            shopping=[],
        )
        await apply_card(setup, avanti.id, [])
        await update_meal(setup, a, {"away": True})
        await update_meal(setup, bozza, {"status": MealStatus.OFFICIAL})
        await update_meal(setup, bozza, {"away": True})
        inverse_ids = (
            await setup.execute(
                select(ChangeCard.id)
                .where(ChangeCard.kind == "inverse")
                .order_by(ChangeCard.created_at, ChangeCard.id)
            )
        ).scalars().all()
        await setup.commit()
    assert len(inverse_ids) == 2

    sessions: list[AsyncSession] = [maker(), maker()]

    async def tocco(session: AsyncSession, card_id):
        await apply_card(session, card_id, [])
        await session.commit()

    try:
        await asyncio.gather(*(tocco(s, c) for s, c in zip(sessions, inverse_ids, strict=True)))
    finally:
        for s in sessions:
            await s.close()

    async with maker() as check:
        rows = (
            await check.execute(
                select(ChangeCardRow.card_id, ChangeCardRow.applied, ChangeCardRow.note).where(
                    ChangeCardRow.card_id.in_(inverse_ids)
                )
            )
        ).all()
    per_card = {
        card_id: {(applied, note) for c, applied, note in rows if c == card_id}
        for card_id in inverse_ids
    }
    rimesse = [c for c, esiti in per_card.items() if esiti == {(True, None)}]
    saltate = [
        c for c, esiti in per_card.items()
        if esiti == {(False, "Già rimessa da un'altra scheda.")}
    ]
    assert len(rimesse) == 1 and len(saltate) == 1, per_card
