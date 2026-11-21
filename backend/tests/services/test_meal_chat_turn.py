"""Il giro della chat del piatto (Task 6): un messaggio di Mattia → una risposta di Claude,
con il finto al posto dell'SDK e una `session_factory` sulla connessione del test."""

from datetime import UTC, date, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.db.models.conversation import ConversationMessage
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.llm_call import LlmCall
from app.db.models.meal import Meal
from app.db.models.recipe import Recipe, RecipeSource
from app.db.models.recipe_change import RecipeChange
from app.domain.meal_chat import FailureKind, failure_notice
from app.domain.meals import MealSlot
from app.domain.rules import PANTRY_TZ
from app.repositories.conversations import get_or_create_dish_conversation
from app.repositories.meals import get_meal
from app.repositories.recipes import create_recipe, get_recipe
from app.services.claude.prompts import dish_system_prompt
from app.services.meal_chat import ChatEvent, dish_chat_view, run_dish_turn
from app.services.meal_recipes import change_is_undoable
from app.services.meals import create_meal, link_recipe
from app.repositories.utensils import create_utensil
from app.services.utensils import utensils_prompt_block
from claude_fakes import Fail, FakeClaude, Finish, Hang, Say, UseTool

DAY = date(2026, 11, 13)


@pytest.fixture
def factory(db_session):
    return async_sessionmaker(
        bind=db_session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )


@pytest_asyncio.fixture
async def voci(db_session):
    rows = {
        "uova": Ingredient(name="uova", display_name="Uova", category=IngredientCategory.LATTICINI),
        "spinaci": Ingredient(
            name="spinaci", display_name="Spinaci", category=IngredientCategory.VERDURA
        ),
        "parmigiano": Ingredient(
            name="parmigiano", display_name="Parmigiano", category=IngredientCategory.LATTICINI
        ),
    }
    db_session.add_all(rows.values())
    await db_session.flush()
    return rows


@pytest_asyncio.fixture
async def frittata(db_session, voci):
    """La cena «Frittata di spinaci e parmigiano», con la ricetta che ha spinaci 200 g."""
    meal = await create_meal(
        db_session, day=DAY, slot=MealSlot.DINNER, dish="Frittata di spinaci e parmigiano"
    )
    recipe = await create_recipe(
        db_session, title="Frittata di spinaci e parmigiano", description=None,
        instructions="1. Sbatti le uova.\n2. Cuoci in padella.", servings=1,
        source=RecipeSource.AI, source_ref=None,
        ingredients=[
            (voci["uova"].id, "primary", "3", None),
            (voci["spinaci"].id, "primary", "200 g", None),
            (voci["parmigiano"].id, "secondary", "30 g", None),
        ],
        embedding=None, in_book=False,
    )
    await link_recipe(db_session, meal, recipe)
    return meal


@pytest_asyncio.fixture
async def senza_ricetta(db_session, voci):
    return await create_meal(db_session, day=DAY, slot=MealSlot.LUNCH, dish="Pasta e ceci")


async def nuovo_messaggio(db_session, meal, text, *, created_at=None):
    conversation = await get_or_create_dish_conversation(db_session, meal.id)
    message = ConversationMessage(
        conversation_id=conversation.id, role="user", text=text, status="pending",
        created_at=created_at or datetime.now(UTC),
    )
    db_session.add(message)
    await db_session.flush()
    return conversation, message


async def giro(factory, fake, conversation, message, *, timeout=5.0):
    events: list[ChatEvent] = []

    async def emit(event):
        events.append(event)

    await run_dish_turn(
        factory, fake, conversation_id=conversation.id, user_message_id=message.id,
        emit=emit, timeout_seconds=timeout,
    )
    return events


def spinaci_args(voci):
    return {
        "title": "Frittata di spinaci e parmigiano",
        "servings": 1,
        "instructions": "1. Sbatti le uova.\n2. Cuoci in padella.",
        "ingredients": [
            {"ingredient_id": str(voci["uova"].id), "role": "primary", "quantity": "3"},
            {
                "ingredient_id": str(voci["spinaci"].id), "role": "primary",
                "quantity": "150 g", "note": "congelati, senza scongelare",
            },
            {"ingredient_id": str(voci["parmigiano"].id), "role": "secondary", "quantity": "30 g"},
        ],
        "summary": "spinaci congelati, padella unica",
    }


async def righe_dal_database(factory, recipe_id):
    """Da una sessione nuova, come una richiesta dopo il giro: quella del test ha in
    memoria la ricetta di prima."""
    async with factory() as session:
        recipe = await get_recipe(session, recipe_id)
        return {ri.ingredient.name: (ri.quantity_text, ri.note) for ri in recipe.ingredients}


async def chiamate(db_session):
    rows = await db_session.execute(select(LlmCall).where(LlmCall.call_site == "meal_chat"))
    return list(rows.scalars().all())


async def test_un_giro_che_risponde(db_session, factory, frittata, dal_database):
    conversation, message = await nuovo_messaggio(db_session, frittata, "Quanti spinaci?")
    fake = FakeClaude([Say("Prendine 150 g."), Finish(input_tokens=1200, output_tokens=80)])

    events = await giro(factory, fake, conversation, message)

    assert [e.name for e in events[:-1]] == ["delta"] * (len(events) - 1)
    assert "".join(e.data["text"] for e in events[:-1]) == "Prendine 150 g."
    assert events[-1].name == "done"
    assert (await dal_database(ConversationMessage, message.id)).status == "sent"
    reply = (
        await db_session.execute(
            select(ConversationMessage).where(ConversationMessage.reply_to_id == message.id)
        )
    ).scalar_one()
    assert reply.role == "assistant" and reply.text == "Prendine 150 g."
    assert reply.status == "sent"
    [row] = await chiamate(db_session)
    assert row.ok is True
    assert row.prompt_tokens == 1200 and row.completion_tokens == 80
    assert row.cost_usd is None
    assert row.model == "claude-opus-5-5" and row.generation_id == "sessione-finta"
    chat = events[-1].data["chat"]
    assert [m["role"] for m in chat["messages"]] == ["user", "assistant"]
    assert chat["replying"] is False


async def test_il_giro_usa_prompt_strumenti_e_sforzo_della_chat_del_piatto(
    db_session, factory, frittata
):
    await create_utensil(db_session, name="padella antiaderente", note="da 24 cm")
    conversation, message = await nuovo_messaggio(db_session, frittata, "Posso farla al forno?")
    fake = FakeClaude([Say("Sì."), Finish()])

    await giro(factory, fake, conversation, message)

    [call] = fake.calls
    assert call["effort"] == "medium"
    assert call["max_turns"] == 12
    assert call["tool_names"] == [
        "read_pantry", "read_shopping_list", "read_meals", "search_ingredients", "write_recipe",
        "propose_changes",
    ]
    block = await utensils_prompt_block(db_session)
    assert block is not None
    assert call["system_prompt"] == dish_system_prompt(block)
    assert "Frittata di spinaci e parmigiano" in call["prompt"]
    assert "Posso farla al forno?" in call["prompt"]
    assert "200 g" in call["prompt"]


async def test_l_esempio_degli_spinaci(db_session, factory, frittata, voci):
    conversation, message = await nuovo_messaggio(
        db_session, frittata, "Ho solo spinaci congelati, e voglio sporcare una padella sola."
    )
    fake = FakeClaude(
        [
            UseTool("write_recipe", spinaci_args(voci)),
            Say("Fatto: 150 g di spinaci congelati, direttamente in padella."),
            Finish(),
        ]
    )

    events = await giro(factory, fake, conversation, message)

    names = [e.name for e in events]
    assert names[0] == "change"
    assert set(names[1:-1]) == {"delta"}
    assert names[-1] == "done"
    change = events[0].data["change"]
    assert change["summary"] == "spinaci congelati, padella unica"
    assert change["undoable"] is True
    assert change["undone"] is False and change["created_recipe"] is False
    righe = await righe_dal_database(factory, frittata.recipe_id)
    assert righe["spinaci"] == ("150 g", "congelati, senza scongelare")
    chat = events[-1].data["chat"]
    assert chat["highlight"]["ingredient_ids"] == [str(voci["spinaci"].id)]
    # la modifica sta sotto la risposta di Claude
    assert chat["messages"][0]["changes"] == []
    assert [c["summary"] for c in chat["messages"][1]["changes"]] == [
        "spinaci congelati, padella unica"
    ]


async def test_la_ricetta_scritta_da_zero(db_session, factory, senza_ricetta, voci):
    conversation, message = await nuovo_messaggio(db_session, senza_ricetta, "Scrivimi la ricetta.")
    args = spinaci_args(voci) | {"title": "Pasta e ceci", "summary": "pasta e ceci per uno"}
    fake = FakeClaude([UseTool("write_recipe", args), Say("Eccola."), Finish()])

    events = await giro(factory, fake, conversation, message)

    assert events[0].data["change"]["created_recipe"] is True
    async with factory() as session:
        meal = await get_meal(session, senza_ricetta.id)
        assert meal.recipe_id is not None
        recipe = await session.get(Recipe, meal.recipe_id)
        assert recipe.source == "ai" and recipe.in_book is False
        change = (
            await session.execute(select(RecipeChange).where(RecipeChange.meal_id == meal.id))
        ).scalar_one()
        assert change.created_recipe is True
        assert change.turn_message_id == message.id


async def test_il_limite_del_piano(db_session, factory, frittata, dal_database):
    conversation, message = await nuovo_messaggio(db_session, frittata, "E con le zucchine?")
    resets_at = datetime.now(UTC) + timedelta(minutes=30)
    fake = FakeClaude([Fail(FailureKind.PLAN_LIMIT, resets_at=resets_at)])

    events = await giro(factory, fake, conversation, message)

    [event] = events
    assert event.name == "error"
    assert event.data["code"] == "plan_limit"
    local = resets_at.astimezone(PANTRY_TZ)
    assert f"{local.hour}:{local.minute:02d}" in event.data["notice"]
    saved = await dal_database(ConversationMessage, message.id)
    assert saved.status == "failed" and saved.failure == "plan_limit"
    assert saved.notice == event.data["notice"]
    [row] = await chiamate(db_session)
    assert row.ok is False
    failed = event.data["chat"]["messages"][0]
    assert failed["status"] == "failed" and failed["notice"] == event.data["notice"]


async def test_senza_token_nessuna_riga_di_spesa(db_session, factory, frittata):
    conversation, message = await nuovo_messaggio(db_session, frittata, "Ciao")
    fake = FakeClaude([Fail(FailureKind.NOT_CONFIGURED)])

    events = await giro(factory, fake, conversation, message)

    assert [e.name for e in events] == ["error"]
    assert events[0].data["code"] == "not_configured"
    assert await chiamate(db_session) == []


async def test_il_tempo_massimo(db_session, factory, frittata, dal_database):
    conversation, message = await nuovo_messaggio(db_session, frittata, "Ciao")
    fake = FakeClaude([Say("Allora…"), Hang()])

    events = await giro(factory, fake, conversation, message, timeout=0.2)

    assert events[-1].name == "error"
    assert events[-1].data["code"] == "timeout"
    assert events[-1].data["notice"] == failure_notice(
        FailureKind.TIMEOUT, None, datetime.now(UTC)
    )
    assert (await dal_database(ConversationMessage, message.id)).status == "failed"
    [row] = await chiamate(db_session)
    assert row.ok is False


async def test_una_modifica_resta_anche_se_poi_il_giro_fallisce(
    db_session, factory, frittata, voci, dal_database
):
    conversation, message = await nuovo_messaggio(db_session, frittata, "Spinaci congelati")
    fake = FakeClaude([UseTool("write_recipe", spinaci_args(voci)), Fail(FailureKind.UNAVAILABLE)])

    events = await giro(factory, fake, conversation, message)

    assert [e.name for e in events] == ["change", "error"]
    righe = await righe_dal_database(factory, frittata.recipe_id)
    assert righe["spinaci"][0] == "150 g"
    async with factory() as session:
        change = (
            await session.execute(
                select(RecipeChange).where(RecipeChange.turn_message_id == message.id)
            )
        ).scalar_one()
        assert await change_is_undoable(session, change)
    assert (await dal_database(ConversationMessage, message.id)).status == "failed"
    # senza risposta, la modifica sta sotto il messaggio di Mattia
    [failed] = events[-1].data["chat"]["messages"]
    assert [c["summary"] for c in failed["changes"]] == ["spinaci congelati, padella unica"]


async def test_la_cronologia_torna_nel_prompt(db_session, factory, frittata, voci):
    conversation, first = await nuovo_messaggio(db_session, frittata, "Ho spinaci congelati")
    await giro(
        factory,
        FakeClaude([UseTool("write_recipe", spinaci_args(voci)), Say("Li uso così."), Finish()]),
        conversation, first,
    )
    _, second = await nuovo_messaggio(db_session, frittata, "E il parmigiano?")
    fake = FakeClaude([Say("Resta."), Finish()])

    await giro(factory, fake, conversation, second)

    prompt = fake.calls[0]["prompt"]
    assert "Ho spinaci congelati" in prompt
    assert "Li uso così." in prompt
    assert "Ricetta aggiornata: spinaci congelati, padella unica" in prompt
    assert prompt.index("Ho spinaci congelati") < prompt.index("Li uso così.")
    assert prompt.index("Li uso così.") < prompt.index("Ricetta aggiornata")
    assert prompt.index("Ricetta aggiornata") < prompt.index("E il parmigiano?")
    # il messaggio di questo giro è in fondo, una volta sola
    assert prompt.count("E il parmigiano?") == 1


async def test_la_cronologia_non_porta_i_messaggi_falliti(db_session, factory, frittata):
    conversation, first = await nuovo_messaggio(db_session, frittata, "Messaggio non risposto")
    await giro(factory, FakeClaude([Fail(FailureKind.UNAVAILABLE)]), conversation, first)
    _, second = await nuovo_messaggio(db_session, frittata, "Riprovo")
    fake = FakeClaude([Say("Ok."), Finish()])

    await giro(factory, fake, conversation, second)

    assert "Messaggio non risposto" not in fake.calls[0]["prompt"]


async def test_l_evidenza_sparisce_al_messaggio_dopo(db_session, factory, frittata, voci):
    conversation, message = await nuovo_messaggio(db_session, frittata, "Spinaci congelati")
    await giro(
        factory,
        FakeClaude([UseTool("write_recipe", spinaci_args(voci)), Say("Fatto."), Finish()]),
        conversation, message,
    )
    now = datetime.now(UTC)
    async with factory() as session:
        meal = await get_meal(session, frittata.id)
        view = await dish_chat_view(session, meal, replying=False, now=now)
        assert view.highlight is not None

    await nuovo_messaggio(db_session, frittata, "E il formaggio?")

    async with factory() as session:
        meal = await get_meal(session, frittata.id)
        view = await dish_chat_view(session, meal, replying=True, now=now)
    assert view.highlight is None


async def test_un_attesa_orfana_conta_come_interrotta(db_session, frittata, dal_database):
    now = datetime.now(UTC)
    _, message = await nuovo_messaggio(
        db_session, frittata, "Ciao", created_at=now - timedelta(minutes=10)
    )

    view = await dish_chat_view(db_session, frittata, replying=False, now=now)

    [shown] = view.messages
    assert shown.status == "failed"
    assert shown.notice == "La risposta si è interrotta. Riprova."
    saved = await dal_database(ConversationMessage, message.id)
    assert saved.status == "failed" and saved.failure == "interrupted"


async def test_un_attesa_con_il_giro_vivo_resta_in_attesa(db_session, frittata):
    now = datetime.now(UTC)
    await nuovo_messaggio(db_session, frittata, "Ciao", created_at=now - timedelta(minutes=10))

    view = await dish_chat_view(db_session, frittata, replying=True, now=now)

    assert [m.status for m in view.messages] == ["pending"]


async def test_la_vista_di_un_pasto_senza_chat(db_session, frittata, monkeypatch):
    # il token si fissa vuoto: in un container che ce l'ha, l'esito non deve cambiare
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    try:
        view = await dish_chat_view(
            db_session, frittata, replying=False, now=datetime.now(UTC)
        )
    finally:
        get_settings.cache_clear()

    assert view.conversation_id is None and view.messages == []
    assert view.highlight is None
    assert view.claude_ready is False
    assert view.claude_notice == failure_notice(FailureKind.NOT_CONFIGURED, None, datetime.now(UTC))


async def test_un_pasto_che_non_ha_piu_la_chat_interrompe_il_giro(
    db_session, factory, senza_ricetta, dal_database
):
    conversation, message = await nuovo_messaggio(db_session, senza_ricetta, "Ciao")
    meal = await db_session.get(Meal, senza_ricetta.id)
    meal.away = True
    await db_session.flush()
    fake = FakeClaude([Say("No."), Finish()])

    events = await giro(factory, fake, conversation, message)

    assert [e.name for e in events] == ["error"]
    assert events[0].data["code"] == "interrupted"
    assert fake.calls == []
    assert (await dal_database(ConversationMessage, message.id)).failure == "interrupted"


class RottoSubito(FakeClaude):
    def run(self, **kwargs):
        async def stream():
            raise RuntimeError("guasto inatteso")
            yield  # pragma: no cover

        self.calls.append(kwargs)
        return stream()


async def test_un_eccezione_inattesa_lascia_il_messaggio_fallito(
    db_session, factory, frittata, dal_database, caplog
):
    conversation, message = await nuovo_messaggio(db_session, frittata, "Ciao")

    events = await giro(factory, RottoSubito([]), conversation, message)

    assert [e.name for e in events] == ["error"]
    assert events[0].data["code"] == "unavailable"
    saved = await dal_database(ConversationMessage, message.id)
    assert saved.status == "failed" and saved.failure == "unavailable"
    assert "guasto inatteso" in caplog.text


class ScadeTutto(FakeClaude):
    """Durante il giro scade tutto quello che la sessione del giro ha in mano, come un
    SAVEPOINT annullato da un errore inatteso: dopo il flusso il giro non deve rileggere
    gli oggetti caricati prima."""

    def __init__(self, script, sessions):
        super().__init__(script)
        self.sessions = sessions

    async def run(self, **kwargs):
        for session in self.sessions:
            session.expire_all()
        async for event in super().run(**kwargs):
            yield event


def spia(factory, sessions):
    def make():
        session = factory()
        sessions.append(session)
        return session

    return make


async def test_un_successo_con_gli_oggetti_scaduti_finisce_con_done(
    db_session, factory, frittata, dal_database
):
    conversation, message = await nuovo_messaggio(db_session, frittata, "Ciao")
    sessions: list = []
    fake = ScadeTutto([Say("Ok."), Finish()], sessions)

    events = await giro(spia(factory, sessions), fake, conversation, message)

    assert [e.name for e in events][-1] == "done"
    assert (await dal_database(ConversationMessage, message.id)).status == "sent"
    [row] = await chiamate(db_session)
    assert row.ok is True


async def test_il_tempo_massimo_con_gli_oggetti_scaduti_resta_timeout(
    db_session, factory, frittata, dal_database
):
    conversation, message = await nuovo_messaggio(db_session, frittata, "Ciao")
    sessions: list = []
    fake = ScadeTutto([Say("Allora…"), Hang()], sessions)

    events = await giro(spia(factory, sessions), fake, conversation, message, timeout=0.2)

    assert events[-1].name == "error"
    assert events[-1].data["code"] == "timeout"
    assert (await dal_database(ConversationMessage, message.id)).failure == "timeout"
    [row] = await chiamate(db_session)
    assert row.ok is False


async def test_il_giro_non_tiene_aperta_la_transazione_mentre_claude_pensa(
    db_session, factory, frittata
):
    """Le letture del giro finiscono prima di chiamare Claude: la sessione non resta
    «idle in transaction» per tutto il giro."""
    conversation, message = await nuovo_messaggio(db_session, frittata, "Ciao")
    sessions: list = []
    seen: list[bool] = []

    class Guarda(FakeClaude):
        async def run(self, **kwargs):
            seen.append(sessions[0].in_transaction())
            async for event in super().run(**kwargs):
                yield event

    await giro(spia(factory, sessions), Guarda([Say("Ok."), Finish()]), conversation, message)

    assert seen == [False]
