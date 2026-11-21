"""Il giro della pianificazione (piano 6c, Task 7): lo stesso giro della chat del piatto con
un'altra specie (`TurnSpec`), le proposte e le schede sotto i messaggi. Con il finto al
posto dell'SDK e una `session_factory` sulla connessione del test, come i test del giro
del piatto (`test_meal_chat_turn.py`)."""

from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.db.models.change_card import ChangeCard
from app.db.models.conversation import ConversationMessage
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.llm_call import LlmCall
from app.db.models.pantry import PantryItem
from app.db.models.planning import MealProposal
from app.domain.meal_chat import FailureKind, failure_notice
from app.domain.meals import MealSlot
from app.domain.rules import PANTRY_TZ, today_in_pantry
from app.repositories.conversations import create_planning, get_or_create_dish_conversation
from app.repositories.utensils import create_utensil
from app.services.claude.prompts import day_name, planning_system_prompt
from app.services.meal_chat import ChatEvent, dish_chat_view, run_dish_turn
from app.services.meals import create_meal
from app.services.planning import place_proposal
from app.services.planning_chat import planning_view, run_planning_turn
from app.services.utensils import utensils_prompt_block
from claude_fakes import Fail, FakeClaude, Finish, Say, UseTool

TODAY = today_in_pantry(datetime.now(UTC))
DAY1, DAY2, DAY3 = (TODAY + timedelta(days=n) for n in (1, 2, 3))


@pytest.fixture
def factory(db_session):
    return async_sessionmaker(
        bind=db_session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )


@pytest_asyncio.fixture
async def ricotta(db_session):
    ingredient = Ingredient(
        name="ricotta", display_name="Ricotta", category=IngredientCategory.LATTICINI
    )
    db_session.add(ingredient)
    await db_session.flush()
    item = PantryItem(ingredient_id=ingredient.id, status="available")
    db_session.add(item)
    await db_session.flush()
    return item


async def messaggio(db_session, conversation, text):
    message = ConversationMessage(
        conversation_id=conversation.id, role="user", text=text, status="pending",
        created_at=datetime.now(UTC),
    )
    db_session.add(message)
    await db_session.flush()
    return message


async def giro(factory, fake, conversation, message, *, run=run_planning_turn):
    events: list[ChatEvent] = []

    async def emit(event):
        events.append(event)

    await run(
        factory, fake, conversation_id=conversation.id, user_message_id=message.id,
        emit=emit, timeout_seconds=5.0,
    )
    return events


def tre_cene():
    return {
        "kind": "official",
        "meals": [
            {"day": DAY1.isoformat(), "slot": "dinner", "dish": "Frittata di spinaci"},
            {"day": DAY2.isoformat(), "slot": "dinner", "dish": "Orata al forno", "sides": "patate"},
            {"day": DAY3.isoformat(), "slot": "dinner", "dish": "Pasta al pesto"},
        ],
    }


async def vista(factory, conversation):
    async with factory() as session:
        return await planning_view(
            session, conversation, replying=False, now=datetime.now(UTC)
        )


async def test_un_giro_di_pianificazione_che_propone(db_session, factory, dal_database):
    conversation = await create_planning(db_session)
    message = await messaggio(db_session, conversation, "Cosa ceno nei prossimi giorni?")
    fake = FakeClaude(
        [
            UseTool("propose_meals", tre_cene()),
            Say("Ecco tre cene."),
            Finish(input_tokens=3000, output_tokens=400),
        ]
    )

    events = await giro(factory, fake, conversation, message)

    names = [e.name for e in events]
    assert names[0] == "proposal"
    assert set(names[1:-1]) == {"delta"}
    assert names[-1] == "done"
    proposal = events[0].data["proposal"]
    assert proposal["kind"] == "official" and proposal["status"] == "open"
    assert [r["dish"] for r in proposal["rows"]] == [
        "Frittata di spinaci", "Orata al forno", "Pasta al pesto",
    ]
    assert {r["effect"] for r in proposal["rows"]} == {"new"}
    assert (await dal_database(ConversationMessage, message.id)).status == "sent"

    # nella vista, la proposta sta sotto la risposta di Claude
    chat = events[-1].data["chat"]
    assert chat["conversation_id"] == str(conversation.id)
    assert chat["concluded"] is False
    user, reply = chat["messages"]
    assert user["proposals"] == [] and reply["role"] == "assistant"
    assert [p["id"] for p in reply["proposals"]] == [proposal["id"]]
    view = await vista(factory, conversation)
    assert [str(p.id) for p in view.messages[1].proposals] == [proposal["id"]]
    assert [r.effect for r in view.messages[1].proposals[0].rows] == ["new"] * 3

    [row] = (
        await db_session.execute(select(LlmCall).where(LlmCall.call_site == "meal_planning"))
    ).scalars().all()
    assert row.ok is True
    assert row.prompt_tokens == 3000 and row.completion_tokens == 400
    assert row.cost_usd == 0.05


async def test_il_giro_usa_sforzo_e_strumenti_della_pianificazione(db_session, factory):
    await create_utensil(db_session, name="padella antiaderente", note="da 24 cm")
    conversation = await create_planning(db_session, focus=(DAY1, MealSlot.DINNER))
    message = await messaggio(db_session, conversation, "Cosa mi proponi?")
    fake = FakeClaude([Say("Vediamo."), Finish()])

    await giro(factory, fake, conversation, message)

    [call] = fake.calls
    assert call["effort"] == "high"
    assert call["max_turns"] == 20
    assert call["tool_names"] == [
        "read_pantry", "read_shopping_list", "read_meals", "search_ingredients",
        "propose_meals", "propose_changes",
    ]
    block = await utensils_prompt_block(db_session)
    assert block is not None
    assert call["system_prompt"] == planning_system_prompt(block)
    assert f"Mattia è partito da: {day_name(DAY1)}, cena." in call["prompt"]
    assert "Sul tavolo non c'è nessuna proposta." in call["prompt"]
    assert call["prompt"].rstrip().endswith("Cosa mi proponi?")


async def test_troppi_passaggi_nella_pianificazione(db_session, factory, dal_database):
    conversation = await create_planning(db_session)
    message = await messaggio(db_session, conversation, "Pianifica la settimana")
    fake = FakeClaude(
        [
            Say("Ecco tre cene. "),
            UseTool("propose_meals", tre_cene()),
            Say("E poi"),
            Fail(FailureKind.MAX_TURNS, input_tokens=4000, output_tokens=900, cost_usd=0.7),
        ]
    )

    events = await giro(factory, fake, conversation, message)

    assert events[-1].name == "done"
    saved = await dal_database(ConversationMessage, message.id)
    assert saved.status == "sent" and saved.notice is None
    user, reply = events[-1].data["chat"]["messages"]
    assert reply["role"] == "assistant" and reply["text"] == "Ecco tre cene. \n\nE poi"
    assert reply["notice"] == failure_notice(FailureKind.MAX_TURNS, None, datetime.now(UTC))
    assert user["proposals"] == [] and len(reply["proposals"]) == 1
    [row] = (
        await db_session.execute(select(LlmCall).where(LlmCall.call_site == "meal_planning"))
    ).scalars().all()
    assert row.ok is False and row.cost_usd == 0.7
    assert row.prompt_tokens == 4000 and row.completion_tokens == 900


async def test_il_limite_a_meta_lascia_la_proposta(db_session, factory, dal_database):
    conversation = await create_planning(db_session)
    message = await messaggio(db_session, conversation, "Pianifica la settimana")
    resets_at = datetime.now(UTC) + timedelta(minutes=30)
    fake = FakeClaude(
        [UseTool("propose_meals", tre_cene()), Fail(FailureKind.RATE_LIMIT, resets_at=resets_at)]
    )

    events = await giro(factory, fake, conversation, message)

    assert [e.name for e in events] == ["proposal", "error"]
    error = events[-1].data
    assert error["code"] == "rate_limit"
    local = resets_at.astimezone(PANTRY_TZ)
    assert f"{local.hour}:{local.minute:02d}" in error["notice"]
    saved = await dal_database(ConversationMessage, message.id)
    assert saved.status == "failed" and saved.notice == error["notice"]
    [proposal] = (await db_session.execute(select(MealProposal))).scalars().all()
    assert proposal.status == "open" and proposal.turn_message_id == message.id
    # senza risposta, la proposta sta sotto il messaggio di Mattia
    [failed] = error["chat"]["messages"]
    assert failed["status"] == "failed"
    assert [p["id"] for p in failed["proposals"]] == [str(proposal.id)]
    [shown] = (await vista(factory, conversation)).messages
    assert [p.id for p in shown.proposals] == [proposal.id]
    [row] = (
        await db_session.execute(select(LlmCall).where(LlmCall.call_site == "meal_planning"))
    ).scalars().all()
    assert row.ok is False

    # e si mette nella settimana
    placement = await place_proposal(
        db_session, proposal.id, replace=False, now=datetime.now(UTC)
    )
    assert [m.dish for m in placement.meals] == [
        "Frittata di spinaci", "Orata al forno", "Pasta al pesto",
    ]
    assert placement.proposal.status == "placed"


async def test_la_scheda_dopo_la_messa(db_session, factory, ricotta):
    conversation = await create_planning(db_session)
    first = await messaggio(db_session, conversation, "Una cena per domani")
    await giro(
        factory,
        FakeClaude(
            [
                UseTool(
                    "propose_meals",
                    {
                        "kind": "official",
                        "meals": [{"day": DAY1.isoformat(), "slot": "dinner", "dish": "Cheesecake"}],
                    },
                ),
                Say("Cheesecake."),
                Finish(),
            ]
        ),
        conversation, first,
    )
    proposal = (await db_session.execute(select(MealProposal))).scalar_one()
    placement = await place_proposal(
        db_session, proposal.id, replace=False, now=datetime.now(UTC)
    )
    await db_session.flush()
    second = await messaggio(db_session, conversation, placement.follow_up)
    fake = FakeClaude(
        [
            UseTool(
                "propose_changes",
                {
                    "meals": [{"day": DAY1.isoformat(), "slot": "dinner"}],
                    "pantry": [{"pantry_item_id": str(ricotta.id), "to": "finished"}],
                },
            ),
            Say("Ecco la scheda."),
            Finish(),
        ]
    )

    events = await giro(factory, fake, conversation, second)

    names = [e.name for e in events]
    assert names[0] == "card" and names[-1] == "done"
    card = events[0].data["card"]
    assert card["status"] == "proposed" and card["kind"] == "forward"
    assert any(r["label"] == "ricotta" and r["to_status"] == "finished" for r in card["rows"])
    assert placement.follow_up in fake.calls[0]["prompt"]
    messages = events[-1].data["chat"]["messages"]
    assert [m["role"] for m in messages] == ["user", "assistant", "user", "assistant"]
    assert [c["id"] for c in messages[3]["cards"]] == [card["id"]]
    assert messages[2]["cards"] == []
    # la proposta del primo giro resta sotto la sua risposta, messa
    assert [p["status"] for p in messages[1]["proposals"]] == ["placed"]
    saved = (await db_session.execute(select(ChangeCard))).scalar_one()
    assert saved.turn_message_id == second.id


async def test_la_chat_del_piatto_resta_quella_di_prima(db_session, factory, ricotta):
    meal = await create_meal(db_session, day=DAY1, slot=MealSlot.DINNER, dish="Cheesecake")
    conversation = await get_or_create_dish_conversation(db_session, meal.id)
    message = await messaggio(db_session, conversation, "Ho usato tutta la ricotta")
    fake = FakeClaude(
        [
            UseTool(
                "propose_changes",
                {"pantry": [{"pantry_item_id": str(ricotta.id), "to": "finished"}]},
            ),
            Say("Ti mando la scheda."),
            Finish(),
        ]
    )

    events = await giro(factory, fake, conversation, message, run=run_dish_turn)

    names = [e.name for e in events]
    assert names[0] == "card" and names[-1] == "done"
    assert fake.calls[0]["effort"] == "medium" and fake.calls[0]["max_turns"] == 12
    chat = events[-1].data["chat"]
    assert chat["meal_id"] == str(meal.id)
    assert [c["id"] for c in chat["messages"][1]["cards"]] == [events[0].data["card"]["id"]]
    assert chat["messages"][1]["proposals"] == []
    [row] = (
        await db_session.execute(select(LlmCall).where(LlmCall.call_site == "meal_chat"))
    ).scalars().all()
    assert row.ok is True
    async with factory() as session:
        view = await dish_chat_view(session, meal, replying=False, now=datetime.now(UTC))
    assert len(view.messages[1].cards) == 1


async def test_la_storia_della_pianificazione_torna_nel_prompt(db_session, factory):
    conversation = await create_planning(db_session)
    first = await messaggio(db_session, conversation, "Tre cene, per favore")
    await giro(
        factory,
        FakeClaude([UseTool("propose_meals", tre_cene()), Say("Eccole."), Finish()]),
        conversation, first,
    )
    second = await messaggio(db_session, conversation, "Cambia la seconda")
    fake = FakeClaude([Say("Va bene."), Finish()])

    await giro(factory, fake, conversation, second)

    prompt = fake.calls[0]["prompt"]
    line = "Proposta: Frittata di spinaci; Orata al forno; Pasta al pesto — aperta"
    assert line in prompt
    assert prompt.index("Tre cene, per favore") < prompt.index("Eccole.") < prompt.index(line)
    assert prompt.index(line) < prompt.index("Cambia la seconda")
    # e la proposta aperta è sul tavolo
    assert "La proposta sul tavolo (ufficiale):" in prompt
    assert "Orata al forno, con patate" in prompt
    assert prompt.count("Cambia la seconda") == 1


async def test_la_vista_senza_conversazione(db_session):
    view = await planning_view(db_session, None, replying=False, now=datetime.now(UTC))
    assert view.conversation_id is None and view.messages == []
    assert view.focus is None and view.concluded is False and view.replying is False


async def test_la_vista_con_il_posto(db_session, factory):
    conversation = await create_planning(db_session, focus=(DAY2, MealSlot.LUNCH))
    view = await vista(factory, conversation)
    assert view.conversation_id == conversation.id
    assert view.focus is not None
    assert view.focus.day == DAY2 and view.focus.slot == MealSlot.LUNCH
    assert isinstance(view.focus.day, date)
