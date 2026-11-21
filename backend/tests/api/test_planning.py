"""Le rotte della pianificazione (piano 6c, Task 9): la conversazione da riaprire o nuova,
il posto di partenza, lo streaming, «Metti nella settimana» con il seguito.

Il finto di Claude, la `session_factory` sulla connessione del test, un registro dei giri e
una coda delle ricette per test arrivano come dipendenze, come nei test della chat del
piatto (`test_meal_chat.py`) e della ricetta chiesta (`test_meal_recipe_ask.py`). Il test
non usa la connessione mentre un giro o la coda lavorano: aspetta `registry.wait` e
`jobs.wait_idle`."""

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.db.models.conversation import ConversationMessage
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.meal import Meal
from app.db.models.pantry import PantryItem
from app.db.models.planning import MealProposal, ProposalKind
from app.domain.meal_chat import FailureKind
from app.domain.meals import MealSlot
from app.domain.rules import today_in_pantry
from app.repositories.conversations import create_planning, get_or_create_dish_conversation
from app.services.chat_turns import TurnRegistry, get_turn_registry
from app.services.claude.client import get_claude_client
from app.services.claude.prompts import day_name
from app.services.meals import create_meal
from app.services.planning import ProposedMeal, propose_meals
from app.services.recipe_jobs import RecipeJobs, get_recipe_jobs
from claude_fakes import Fail, FakeClaude, Finish, Say, UseTool

TODAY = today_in_pantry(datetime.now(UTC))
DAY1, DAY2 = TODAY + timedelta(days=1), TODAY + timedelta(days=2)
CHIAVE_FINTA = "chiave-finta-per-i-test"
NOT_CONFIGURED = "Claude non è collegato: manca il token del piano sul server."
BASE = "/api/v1/planning"


@pytest_asyncio.fixture
async def chat(logged_client, db_session, monkeypatch):
    """Il client con il token finto nelle impostazioni, il finto di Claude (da riempire con
    `chat.fake = FakeClaude(...)`), la factory sulla connessione del test, un registro e una
    coda per test. Alla fine nessun giro e nessuna coda sopravvivono al test."""
    from app.main import app

    monkeypatch.setenv("ANTHROPIC_API_KEY", CHIAVE_FINTA)
    get_settings.cache_clear()
    registry = TurnRegistry()
    jobs = RecipeJobs()

    class Chat:
        client = logged_client
        fake: FakeClaude = FakeClaude([Say("Ok."), Finish()])
        turns = registry
        queue = jobs

    holder = Chat()
    factory = async_sessionmaker(
        bind=db_session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    app.dependency_overrides[get_claude_client] = lambda: holder.fake
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_turn_registry] = lambda: registry
    app.dependency_overrides[get_recipe_jobs] = lambda: jobs
    yield holder
    await jobs.wait_idle()
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def uova(db_session):
    ingredient = Ingredient(name="uova", display_name="Uova", category=IngredientCategory.LATTICINI)
    db_session.add(ingredient)
    await db_session.flush()
    return ingredient


@pytest_asyncio.fixture
async def ricotta(db_session):
    ingredient = Ingredient(
        name="ricotta", display_name="Ricotta", category=IngredientCategory.LATTICINI
    )
    db_session.add(ingredient)
    await db_session.flush()
    item = PantryItem(ingredient_id=ingredient.id, status="available")
    db_session.add(item)
    await db_session.commit()
    return item


def eventi(testo: str) -> list[tuple[str, dict]]:
    out = []
    for blocco in testo.split("\n\n"):
        if not blocco.strip() or blocco.startswith(":"):
            continue
        nome, dati = blocco.split("\n", 1)
        out.append((nome.removeprefix("event: "), json.loads(dati.removeprefix("data: "))))
    return out


def cene(*dishes, kind="official"):
    days = [DAY1, DAY2]
    return {
        "kind": kind,
        "meals": [
            {"day": days[i].isoformat(), "slot": "dinner", "dish": dish}
            for i, dish in enumerate(dishes)
        ],
    }


async def nuova(chat, **body) -> str:
    risposta = await chat.client.post(f"{BASE}/conversations", json=body)
    assert risposta.status_code == 201, risposta.text
    return risposta.json()["conversation_id"]


async def scrivi(chat, conversation_id, text="Cosa ceno?", **extra):
    risposta = await chat.client.post(
        f"{BASE}/conversations/{conversation_id}/messages", json={"text": text, **extra}
    )
    if risposta.status_code == 200:
        await chat.turns.wait(uuid.UUID(conversation_id))
    return risposta


async def proponi(chat, *dishes, kind="official") -> tuple[str, str]:
    conversation_id = await nuova(chat)
    chat.fake = FakeClaude([UseTool("propose_meals", cene(*dishes, kind=kind)), Say("Ecco."), Finish()])
    risposta = await scrivi(chat, conversation_id)
    assert risposta.status_code == 200, risposta.text
    proposal = next(d for n, d in eventi(risposta.text) if n == "proposal")["proposal"]
    return conversation_id, proposal["id"]


async def metti(chat, proposal_id, **body):
    risposta = await chat.client.post(f"{BASE}/proposals/{proposal_id}/place", json=body)
    await chat.queue.wait_idle()  # la coda delle ricette usa la stessa connessione
    return risposta


def ricetta(uova, title):
    return [
        UseTool(
            "write_recipe",
            {
                "title": title,
                "servings": 1,
                "instructions": "1. Sbatti le uova.\n2. Cuoci in padella.",
                "ingredients": [
                    {"ingredient_id": str(uova.id), "role": "primary", "quantity": "2"}
                ],
                "summary": "due uova in padella",
            },
        ),
        Say("fatta"),
        Finish(),
    ]


async def test_senza_conversazioni_la_vista_e_vuota(chat):
    risposta = await chat.client.get(f"{BASE}/current")
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["conversation_id"] is None
    assert corpo["concluded"] is False
    assert corpo["messages"] == [] and corpo["focus"] is None
    assert corpo["claude_ready"] is True


async def test_nuova_con_il_posto(chat):
    risposta = await chat.client.post(
        f"{BASE}/conversations", json={"focus": {"day": "2026-11-13", "slot": "dinner"}}
    )
    assert risposta.status_code == 201
    corpo = risposta.json()
    assert corpo["focus"] == {"day": "2026-11-13", "slot": "dinner"}
    conversation_id = corpo["conversation_id"]

    current = (await chat.client.get(f"{BASE}/current")).json()
    assert current["conversation_id"] == conversation_id
    assert current["focus"] == {"day": "2026-11-13", "slot": "dinner"}

    tolto = await chat.client.patch(f"{BASE}/conversations/{conversation_id}", json={"focus": None})
    assert tolto.status_code == 200
    assert tolto.json()["focus"] is None
    assert (await chat.client.get(f"{BASE}/current")).json()["focus"] is None

    # «Nuova» senza posto: la più recente è lei
    altra = await nuova(chat)
    assert altra != conversation_id
    assert (await chat.client.get(f"{BASE}/current")).json()["conversation_id"] == altra


async def test_un_messaggio_che_propone_in_streaming(chat, db_session):
    await create_meal(db_session, day=DAY2, slot=MealSlot.DINNER, dish="Pizza", status="draft")
    await db_session.commit()
    conversation_id = await nuova(chat)
    chat.fake = FakeClaude(
        [UseTool("propose_meals", cene("Frittata", "Orata")), Say("Ecco due cene."), Finish()]
    )

    risposta = await scrivi(chat, conversation_id)

    assert risposta.status_code == 200
    assert risposta.headers["content-type"].startswith("text/event-stream")
    assert risposta.headers["x-accel-buffering"] == "no"
    nomi = [n for n, _ in eventi(risposta.text)]
    assert nomi[0] == "start" and nomi[1] == "proposal" and nomi[-1] == "done"
    assert "delta" in nomi
    start = eventi(risposta.text)[0][1]["message"]
    assert (start["role"], start["status"]) == ("user", "pending")
    assert start["proposals"] == [] and start["cards"] == []

    corpo = (await chat.client.get(f"{BASE}/conversations/{conversation_id}")).json()
    user, reply = corpo["messages"]
    assert (user["status"], reply["role"]) == ("sent", "assistant")
    [proposal] = reply["proposals"]
    assert proposal["status"] == "open" and proposal["kind"] == "official"
    assert [(r["dish"], r["effect"]) for r in proposal["rows"]] == [
        ("Frittata", "new"), ("Orata", "officialize"),
    ]
    assert proposal["rows"][1]["occupant"]["dish"] == "Pizza"


async def test_mettere_nella_settimana_e_il_seguito(chat, uova, db_session):
    conversation_id, proposal_id = await proponi(chat, "Frittata", "Omelette")
    chat.fake = FakeClaude.per_call(ricetta(uova, "Frittata"), ricetta(uova, "Omelette"))

    risposta = await chat.client.post(f"{BASE}/proposals/{proposal_id}/place", json={})

    assert risposta.status_code == 200, risposta.text
    corpo = risposta.json()
    assert [(m["dish"], m["status"], m["recipe_state"]) for m in corpo["meals"]] == [
        ("Frittata", "official", "preparing"), ("Omelette", "official", "preparing"),
    ]
    assert corpo["follow_up"] == (
        f"Ho messo nella settimana: {day_name(DAY1)} · cena, Frittata; "
        f"{day_name(DAY2)} · cena, Omelette. Mandami la scheda dei cambi."
    )
    assert corpo["chat"]["conversation_id"] == conversation_id
    [placed] = corpo["chat"]["messages"][1]["proposals"]
    assert placed["status"] == "placed"

    await chat.queue.wait_idle()
    for meal in corpo["meals"]:
        letto = (await chat.client.get(f"/api/v1/meals/{meal['id']}")).json()
        assert letto["recipe"] is not None, letto
        assert letto["recipe_state"] == "none"


async def test_mettere_su_un_posto_occupato_e_409_con_gli_occupanti(chat, db_session):
    await create_meal(db_session, day=DAY1, slot=MealSlot.DINNER, dish="Pizza")
    await db_session.commit()
    _, proposal_id = await proponi(chat, "Frittata")

    rifiuto = await metti(chat, proposal_id)

    assert rifiuto.status_code == 409
    corpo = rifiuto.json()
    assert corpo["code"] == "slots_taken"
    assert corpo["detail"] == "Alcuni posti sono occupati."
    assert corpo["occupants"][0]["dish"] == "Pizza"
    assert corpo["chat"]["messages"][1]["proposals"][0]["status"] == "open"
    # niente è cambiato
    [pizza] = (await db_session.execute(select(Meal).where(Meal.day == DAY1))).scalars().all()
    assert pizza.dish == "Pizza"

    chat.fake = FakeClaude([Say("niente"), Finish()])
    sostituito = await metti(chat, proposal_id, replace=True)
    assert sostituito.status_code == 200, sostituito.text
    assert [m["dish"] for m in sostituito.json()["meals"]] == ["Frittata"]


async def test_mettere_due_volte_e_409(chat):
    chat.fake = FakeClaude([Say("niente"), Finish()])
    conversation_id, proposal_id = await proponi(chat, "Frittata")
    chat.fake = FakeClaude([Say("niente"), Finish()])
    assert (await metti(chat, proposal_id)).status_code == 200

    di_nuovo = await metti(chat, proposal_id)

    assert di_nuovo.status_code == 409
    corpo = di_nuovo.json()
    assert corpo["code"] == "proposal_placed"
    assert corpo["detail"] == "Questa proposta è già nella settimana."
    assert corpo["chat"]["conversation_id"] == conversation_id
    assert "occupants" not in corpo


async def test_un_rifiuto_a_meta_messa_non_lascia_niente(chat, db_session, monkeypatch):
    """C-R9: un posto preso fra il controllo e la scrittura (`MealRefusal` dopo che le prime
    righe sono già scritte) è un 409 JSON, e il rollback toglie tutto quello che la messa
    aveva scritto."""
    import app.api.planning as planning_api
    from app.services.meals import MealRefusal, MealRefusalCode

    _, proposal_id = await proponi(chat, "Frittata", "Omelette")
    vera = planning_api.place_proposal

    async def a_meta(session, proposal_id, **kwargs):
        await vera(session, proposal_id, **kwargs)  # scrive tutto, poi la corsa
        raise MealRefusal(MealRefusalCode.SLOT_TAKEN, "C'è già «Pizza» in questo posto.")

    monkeypatch.setattr(planning_api, "place_proposal", a_meta)
    risposta = await metti(chat, proposal_id)

    assert risposta.status_code == 409
    assert risposta.json() == {
        "code": "slot_taken", "detail": "C'è già «Pizza» in questo posto."
    }
    assert (await db_session.execute(select(Meal))).scalars().all() == []
    proposal = await db_session.get(MealProposal, uuid.UUID(proposal_id))
    await db_session.refresh(proposal)
    assert proposal.status == "open"
    assert chat.queue.live_ids() == frozenset()


async def test_una_proposta_inesistente_e_404(chat):
    assert (await metti(chat, uuid.uuid4())).status_code == 404


async def test_senza_token_i_pasti_entrano_con_l_avviso(logged_client, db_session, monkeypatch):
    from app.main import app

    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    app.dependency_overrides.pop(get_claude_client, None)
    jobs = RecipeJobs()
    app.dependency_overrides[get_recipe_jobs] = lambda: jobs
    conversation = await create_planning(db_session)
    message = ConversationMessage(
        conversation_id=conversation.id, role="user", text="Due cene", status="sent",
        created_at=datetime.now(UTC),
    )
    db_session.add(message)
    await db_session.flush()
    proposal = await propose_meals(
        db_session, conversation_id=conversation.id, turn_message_id=message.id,
        kind=ProposalKind.OFFICIAL,
        meals=[ProposedMeal(DAY1, MealSlot.DINNER, "Frittata", None)], today=TODAY,
    )
    await db_session.commit()

    risposta = await logged_client.post(f"{BASE}/proposals/{proposal.id}/place", json={})

    assert risposta.status_code == 200, risposta.text
    [meal] = risposta.json()["meals"]
    assert meal["recipe_state"] == "failed"
    assert meal["recipe_notice"] == NOT_CONFIGURED
    assert meal["can_ask_recipe"] is True
    assert jobs.live_ids() == frozenset()
    saved = await db_session.get(Meal, uuid.UUID(meal["id"]))
    await db_session.refresh(saved)
    assert saved.recipe_requested_at is None and saved.recipe_notice == NOT_CONFIGURED
    letto = (await logged_client.get(f"/api/v1/meals/{meal['id']}")).json()
    assert (letto["recipe_state"], letto["recipe_notice"]) == ("failed", NOT_CONFIGURED)

    vietato = await logged_client.post(
        f"{BASE}/conversations/{conversation.id}/messages", json={"text": "Ciao"}
    )
    assert vietato.status_code == 503
    assert vietato.json() == {"code": "claude_not_configured", "detail": NOT_CONFIGURED}
    corpo = (await logged_client.get(f"{BASE}/conversations/{conversation.id}")).json()
    assert [m["text"] for m in corpo["messages"]] == ["Due cene"]
    assert corpo["claude_ready"] is False and corpo["claude_notice"] == NOT_CONFIGURED
    await jobs.wait_idle()
    get_settings.cache_clear()


async def test_riprova_si_porta_dietro_la_proposta(chat, db_session):
    conversation_id = await nuova(chat)
    chat.fake = FakeClaude(
        [UseTool("propose_meals", cene("Frittata")), Fail(FailureKind.UNAVAILABLE)]
    )
    fallito = await scrivi(chat, conversation_id, "Una cena")
    assert [n for n, _ in eventi(fallito.text)][-1] == "error"
    [messaggio] = (await chat.client.get(f"{BASE}/conversations/{conversation_id}")).json()[
        "messages"
    ]
    assert messaggio["status"] == "failed"
    [proposta] = messaggio["proposals"]

    chat.fake = FakeClaude([Say("Eccola di nuovo."), Finish()])
    risposta = await scrivi(chat, conversation_id, "Una cena", retry_of=messaggio["id"])

    assert [n for n, _ in eventi(risposta.text)][-1] == "done"
    corpo = (await chat.client.get(f"{BASE}/conversations/{conversation_id}")).json()
    utente = [m for m in corpo["messages"] if m["role"] == "user"]
    assert len(utente) == 1 and utente[0]["id"] != messaggio["id"]
    sotto = [p["id"] for m in corpo["messages"] for p in m["proposals"]]
    assert sotto == [proposta["id"]]
    saved = await db_session.get(MealProposal, uuid.UUID(proposta["id"]))
    await db_session.refresh(saved)
    assert saved.turn_message_id == uuid.UUID(utente[0]["id"])


async def test_conclusa_e_nuova(chat, ricotta):
    conversation_id, proposal_id = await proponi(chat, "Cheesecake")
    chat.fake = FakeClaude([Say("niente"), Finish()])  # il giro della ricetta
    messa = await metti(chat, proposal_id)
    assert messa.status_code == 200
    chat.fake = FakeClaude(
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
    risposta = await scrivi(chat, conversation_id, messa.json()["follow_up"])
    card = next(d for n, d in eventi(risposta.text) if n == "card")["card"]
    assert (await chat.client.get(f"{BASE}/current")).json()["conversation_id"] == conversation_id

    applicata = await chat.client.post(f"/api/v1/change-cards/{card['id']}/apply", json={})
    assert applicata.status_code == 200, applicata.text

    current = (await chat.client.get(f"{BASE}/current")).json()
    assert current["conversation_id"] is None and current["concluded"] is False
    letta = (await chat.client.get(f"{BASE}/conversations/{conversation_id}")).json()
    assert letta["concluded"] is True
    assert [c["id"] for c in letta["messages"][3]["cards"]] == [card["id"]]


async def _giro(chat, meals: list[dict], kind: str, cambi: dict) -> str:
    """Una conversazione nuova con un giro intero: la proposta, la messa nella settimana
    (la ricetta, se c'è, non arriva) e la scheda dei cambi applicata."""
    conversation_id = await nuova(chat)
    chat.fake = FakeClaude(
        [UseTool("propose_meals", {"kind": kind, "meals": meals}), Say("Ecco."), Finish()]
    )
    risposta = await scrivi(chat, conversation_id)
    proposal = next(d for n, d in eventi(risposta.text) if n == "proposal")["proposal"]
    chat.fake = FakeClaude([Say("niente"), Finish()])  # il giro della ricetta
    messa = await metti(chat, proposal["id"])
    assert messa.status_code == 200, messa.text
    places = [{"day": m["day"], "slot": m["slot"]} for m in meals]
    chat.fake = FakeClaude(
        [UseTool("propose_changes", {"meals": places, **cambi}), Say("La scheda."), Finish()]
    )
    risposta = await scrivi(chat, conversation_id, messa.json()["follow_up"])
    card = next(d for n, d in eventi(risposta.text) if n == "card")["card"]
    applicata = await chat.client.post(f"/api/v1/change-cards/{card['id']}/apply", json={})
    assert applicata.status_code == 200, applicata.text
    return conversation_id


async def test_dopo_la_spesa_riapre_il_giro_della_bozza_anche_dopo_una_conclusa(
    chat, uova, ricotta
):
    """Decisione 26: sabato la bozza della settimana con la sua lista (A resta aperta, le
    bozze sono da oggi in avanti); martedì una cena veloce in una conversazione nuova, messa
    e con la scheda applicata (B conclusa). «Pianifica con Claude» riporta ad A."""
    bozza = await _giro(
        chat,
        [{"day": d.isoformat(), "slot": "dinner", "dish": "Frittata"} for d in (DAY1, DAY2)],
        "draft",
        {"shopping": [{"ingredient_id": str(uova.id)}]},
    )
    veloce = await _giro(
        chat,
        [{"day": DAY1.isoformat(), "slot": "lunch", "dish": "Insalata di ricotta"}],
        "official",
        {"pantry": [{"pantry_item_id": str(ricotta.id), "to": "finished"}]},
    )
    assert (await chat.client.get(f"{BASE}/conversations/{veloce}")).json()["concluded"] is True

    current = (await chat.client.get(f"{BASE}/current")).json()
    assert current["conversation_id"] == bozza
    assert current["concluded"] is False


async def test_tutte_concluse_la_vista_e_vuota(chat, ricotta):
    for slot in ("lunch", "dinner"):
        await _giro(
            chat,
            [{"day": DAY1.isoformat(), "slot": slot, "dish": "Insalata di ricotta"}],
            "official",
            {"pantry": [{"pantry_item_id": str(ricotta.id), "to": "low"}]},
        )
    current = (await chat.client.get(f"{BASE}/current")).json()
    assert current["conversation_id"] is None and current["concluded"] is False


async def test_una_vecchia_lasciata_a_meta_senza_bozze_non_si_riapre(chat, ricotta):
    """La lettura prudente: dopo una conclusa si torna indietro solo per un giro della bozza
    ancora aperto. Una conversazione vecchia lasciata a metà (una proposta mai messa) non
    si riapre da sola: resta raggiungibile dal suo indirizzo."""
    abbandonata = await nuova(chat)
    chat.fake = FakeClaude([UseTool("propose_meals", cene("Pasta")), Say("Ecco."), Finish()])
    assert (await scrivi(chat, abbandonata)).status_code == 200
    await _giro(
        chat,
        [{"day": DAY1.isoformat(), "slot": "lunch", "dish": "Insalata di ricotta"}],
        "official",
        {"pantry": [{"pantry_item_id": str(ricotta.id), "to": "low"}]},
    )
    letta = (await chat.client.get(f"{BASE}/conversations/{abbandonata}")).json()
    assert letta["concluded"] is False
    current = (await chat.client.get(f"{BASE}/current")).json()
    assert current["conversation_id"] is None


async def test_una_conversazione_del_piatto_non_e_una_pianificazione(chat, db_session):
    meal = await create_meal(db_session, day=DAY1, slot=MealSlot.DINNER, dish="Frittata")
    conversation = await get_or_create_dish_conversation(db_session, meal.id)
    await db_session.commit()
    for risposta in (
        await chat.client.get(f"{BASE}/conversations/{conversation.id}"),
        await chat.client.get(f"{BASE}/conversations/{uuid.uuid4()}"),
        await chat.client.patch(f"{BASE}/conversations/{conversation.id}", json={"focus": None}),
        await chat.client.post(
            f"{BASE}/conversations/{conversation.id}/messages", json={"text": "Ciao"}
        ),
    ):
        assert risposta.status_code == 404
        assert risposta.json() == {"detail": "conversazione inesistente"}


async def test_la_chat_del_piatto_ha_la_sua_scheda(chat, db_session, ricotta):
    meal = await create_meal(db_session, day=DAY1, slot=MealSlot.DINNER, dish="Cheesecake")
    await db_session.commit()
    chat.fake = FakeClaude(
        [
            UseTool("propose_changes", {"pantry": [{"pantry_item_id": str(ricotta.id), "to": "finished"}]}),
            Say("Ti mando la scheda."),
            Finish(),
        ]
    )
    risposta = await chat.client.post(
        f"/api/v1/meals/{meal.id}/chat/messages", json={"text": "Ho finito la ricotta"}
    )
    assert risposta.status_code == 200
    conversation = await get_or_create_dish_conversation(db_session, meal.id)
    await chat.turns.wait(conversation.id)
    card = next(d for n, d in eventi(risposta.text) if n == "card")["card"]

    corpo = (await chat.client.get(f"/api/v1/meals/{meal.id}/chat")).json()
    user, reply = corpo["messages"]
    assert user["cards"] == [] and reply["proposals"] == []
    assert [c["id"] for c in reply["cards"]] == [card["id"]]
    assert reply["cards"][0]["status"] == "proposed"


async def test_un_testo_vuoto_e_422(chat):
    conversation_id = await nuova(chat)
    risposta = await chat.client.post(
        f"{BASE}/conversations/{conversation_id}/messages", json={"text": "  "}
    )
    assert risposta.status_code == 422


@pytest.mark.parametrize(
    "metodo, percorso",
    [
        ("get", "/current"),
        ("post", "/conversations"),
        ("post", f"/proposals/{uuid.uuid4()}/place"),
    ],
)
async def test_senza_accesso_401(client, metodo, percorso):
    risposta = await getattr(client, metodo)(f"{BASE}{percorso}")
    assert risposta.status_code == 401
