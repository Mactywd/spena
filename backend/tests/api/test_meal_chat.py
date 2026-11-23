"""Le rotte della chat del piatto (Task 7): leggere, scrivere (SSE) e annullare."""

import asyncio
import json
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config import get_settings
from app.core.db import get_session_factory
from app.db.models.conversation import ConversationMessage
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.meal import Meal
from app.db.models.recipe import RecipeSource
from app.domain.meal_chat import BUSY_NOTICE, FailureKind, failure_notice
from app.domain.meals import MealSlot
from app.repositories.conversations import get_or_create_dish_conversation
from app.repositories.recipes import create_recipe
from app.services.chat_turns import TurnRegistry, get_turn_registry
from app.services.claude.client import get_claude_client
from app.services.meals import create_meal, link_recipe
from claude_fakes import Fail, FakeClaude, Finish, Say, UseTool

DAY = date(2026, 11, 13)
CHIAVE_FINTA = "chiave-finta-per-i-test"
NO_CHAT = "Questo pasto non ha una chat: è una bozza, è fuori casa o è un avanzo."


@pytest.fixture
def registry():
    return TurnRegistry()


@pytest_asyncio.fixture
async def chat(logged_client, db_session, registry, monkeypatch):
    """Il client con la chiave finta nelle impostazioni, il finto di Claude (da riempire
    con `chat.fake = FakeClaude(...)`), la factory sulla connessione del test e un registro
    per test."""
    from app.main import app

    monkeypatch.setenv("ANTHROPIC_API_KEY", CHIAVE_FINTA)
    get_settings.cache_clear()

    class Chat:
        client = logged_client
        fake = FakeClaude([Say("Ok."), Finish()])

    holder = Chat()
    factory = async_sessionmaker(
        bind=db_session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )
    app.dependency_overrides[get_claude_client] = lambda: holder.fake
    app.dependency_overrides[get_session_factory] = lambda: factory
    app.dependency_overrides[get_turn_registry] = lambda: registry
    yield holder
    get_settings.cache_clear()


@pytest_asyncio.fixture
async def voci(db_session):
    rows = {
        "uova": Ingredient(name="uova", display_name="Uova", category=IngredientCategory.LATTICINI),
        "spinaci": Ingredient(
            name="spinaci", display_name="Spinaci", category=IngredientCategory.VERDURA
        ),
    }
    db_session.add_all(rows.values())
    await db_session.flush()
    return rows


@pytest_asyncio.fixture
async def frittata(db_session, voci):
    meal = await create_meal(
        db_session, day=DAY, slot=MealSlot.DINNER, dish="Frittata di spinaci"
    )
    recipe = await create_recipe(
        db_session, title="Frittata di spinaci", description=None,
        instructions="1. Sbatti le uova.\n2. Cuoci in padella.", servings=1,
        source=RecipeSource.AI, source_ref=None,
        ingredients=[
            (voci["uova"].id, "primary", "3", None),
            (voci["spinaci"].id, "primary", "200 g", None),
        ],
        embedding=None, in_book=False,
    )
    await link_recipe(db_session, meal, recipe)
    await db_session.commit()
    return meal


def spinaci_args(voci):
    return {
        "title": "Frittata di spinaci",
        "servings": 1,
        "instructions": "1. Sbatti le uova.\n2. Cuoci in padella.",
        "ingredients": [
            {"ingredient_id": str(voci["uova"].id), "role": "primary", "quantity": "3"},
            {
                "ingredient_id": str(voci["spinaci"].id), "role": "primary",
                "quantity": "150 g", "note": "congelati, senza scongelare",
            },
        ],
        "summary": "spinaci congelati, padella unica",
    }


def eventi(testo: str) -> list[tuple[str, dict]]:
    out = []
    for blocco in testo.split("\n\n"):
        if not blocco.strip() or blocco.startswith(":"):
            continue
        nome, dati = blocco.split("\n", 1)
        out.append((nome.removeprefix("event: "), json.loads(dati.removeprefix("data: "))))
    return out


def url(meal, resto=""):
    return f"/api/v1/meals/{meal.id}/chat{resto}"


async def scrivi(chat, meal, text="Quanti spinaci?", **extra):
    return await chat.client.post(url(meal, "/messages"), json={"text": text, **extra})


async def test_la_chat_di_un_pasto_nuovo_e_vuota(chat, frittata):
    body = (await chat.client.get(url(frittata))).json()
    assert body["conversation_id"] is None
    assert body["messages"] == []
    assert body["replying"] is False
    assert body["claude_ready"] is True


async def test_un_messaggio_e_la_sua_risposta_in_streaming(chat, frittata):
    risposta = await scrivi(chat, frittata)
    assert risposta.status_code == 200
    assert risposta.headers["content-type"].startswith("text/event-stream")
    assert risposta.headers["x-accel-buffering"] == "no"
    nomi = [n for n, _ in eventi(risposta.text)]
    assert nomi[0] == "start" and "delta" in nomi and nomi[-1] == "done"
    start = eventi(risposta.text)[0][1]["message"]
    assert (start["role"], start["status"], start["text"]) == ("user", "pending", "Quanti spinaci?")
    messaggi = (await chat.client.get(url(frittata))).json()["messages"]
    assert [(m["role"], m["status"]) for m in messaggi] == [("user", "sent"), ("assistant", "sent")]
    assert messaggi[1]["text"] == "Ok."


async def test_la_modifica_e_la_sua_riga(chat, frittata, voci):
    chat.fake = FakeClaude([UseTool("write_recipe", spinaci_args(voci)), Say("Fatto."), Finish()])
    risposta = await scrivi(chat, frittata, "Ho solo spinaci congelati.")
    nomi = [n for n, _ in eventi(risposta.text)]
    assert "change" in nomi
    corpo = (await chat.client.get(url(frittata))).json()
    righe = corpo["messages"][-1]["changes"]
    assert [{k: r[k] for k in ("summary", "created_recipe", "undone", "undoable")} for r in righe] == [
        {
            "summary": "spinaci congelati, padella unica", "created_recipe": False,
            "undone": False, "undoable": True,
        }
    ]
    assert corpo["highlight"]["ingredient_ids"] == [str(voci["spinaci"].id)]
    ricetta = (await chat.client.get(f"/api/v1/recipes/{frittata.recipe_id}")).json()
    assert "150 g" in {i["quantity_text"] for i in ricetta["ingredients"]}


async def modifica(chat, frittata, voci):
    chat.fake = FakeClaude([UseTool("write_recipe", spinaci_args(voci)), Say("Fatto."), Finish()])
    await scrivi(chat, frittata, "Ho solo spinaci congelati.")
    corpo = (await chat.client.get(url(frittata))).json()
    return corpo["messages"][-1]["changes"][0]["id"]


async def quantita(chat, frittata):
    ricetta = (await chat.client.get(f"/api/v1/recipes/{frittata.recipe_id}")).json()
    return {i["quantity_text"] for i in ricetta["ingredients"]}


async def test_annulla_dalla_rotta(chat, frittata, voci):
    change_id = await modifica(chat, frittata, voci)
    risposta = await chat.client.post(url(frittata, f"/changes/{change_id}/undo"))
    assert risposta.status_code == 200
    corpo = risposta.json()
    assert corpo["messages"][-1]["changes"][0]["undone"] is True
    assert corpo["highlight"] is None
    assert "200 g" in await quantita(chat, frittata)
    di_nuovo = await chat.client.post(url(frittata, f"/changes/{change_id}/undo"))
    assert di_nuovo.status_code == 409
    assert di_nuovo.json() == {
        "code": "change_undone", "detail": "Questa modifica è già stata annullata."
    }


async def test_annulla_mentre_claude_risponde_e_409(chat, frittata, voci, registry, db_session):
    """Un'altra scheda può premere «Annulla» mentre `write_recipe` scrive: si rifiuta come
    un secondo messaggio, con lo stesso corpo, e la ricetta resta com'è."""
    change_id = await modifica(chat, frittata, voci)
    conversation = await get_or_create_dish_conversation(db_session, frittata.id)
    libera = asyncio.Event()

    async def giro_vivo(emit):
        await libera.wait()

    registry.start(conversation.id, giro_vivo)
    try:
        risposta = await chat.client.post(url(frittata, f"/changes/{change_id}/undo"))
        assert risposta.status_code == 409
        assert risposta.json() == {"code": "claude_busy", "detail": BUSY_NOTICE}
        assert "150 g" in await quantita(chat, frittata)
    finally:
        libera.set()
        await registry.wait(conversation.id)
    dopo = await chat.client.post(url(frittata, f"/changes/{change_id}/undo"))
    assert dopo.status_code == 200


async def test_annulla_dopo_il_modulo_e_409(chat, frittata, voci):
    change_id = await modifica(chat, frittata, voci)
    ricetta = (await chat.client.get(f"/api/v1/recipes/{frittata.recipe_id}")).json()
    corpo = {
        "title": "Frittata nuova", "description": ricetta.get("description"),
        "instructions": ricetta["instructions"], "servings": ricetta["servings"],
        "ingredients": [
            {
                "ingredient_id": i["ingredient_id"], "role": i["role"],
                "quantity_text": i["quantity_text"], "note": i["note"],
            }
            for i in ricetta["ingredients"]
        ],
    }
    modulo = await chat.client.put(f"/api/v1/recipes/{frittata.recipe_id}", json=corpo)
    assert modulo.status_code == 200, modulo.text
    risposta = await chat.client.post(url(frittata, f"/changes/{change_id}/undo"))
    assert risposta.status_code == 409
    assert risposta.json() == {
        "code": "change_stale",
        "detail": "La ricetta è cambiata dopo questa modifica: non si può più annullare.",
    }


async def test_senza_chiave_503_e_niente_salvato(logged_client, frittata, monkeypatch):
    from app.main import app

    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    get_settings.cache_clear()
    app.dependency_overrides.pop(get_claude_client, None)
    risposta = await logged_client.post(url(frittata, "/messages"), json={"text": "Ciao"})
    assert risposta.status_code == 503
    assert risposta.json() == {
        "code": "claude_not_configured",
        "detail": failure_notice(FailureKind.NOT_CONFIGURED, None, datetime.now(UTC)),
    }
    corpo = (await logged_client.get(url(frittata))).json()
    assert corpo["messages"] == [] and corpo["claude_ready"] is False
    get_settings.cache_clear()


async def test_un_secondo_messaggio_mentre_risponde_e_409(chat, frittata, db_session):
    conversation = await get_or_create_dish_conversation(db_session, frittata.id)
    db_session.add(
        ConversationMessage(
            conversation_id=conversation.id, role="user", text="Prima", status="pending",
            created_at=datetime.now(UTC),
        )
    )
    await db_session.commit()
    risposta = await scrivi(chat, frittata, "Seconda")
    assert risposta.status_code == 409
    assert risposta.json() == {"code": "claude_busy", "detail": BUSY_NOTICE}


async def test_la_chat_dice_se_l_ultima_risposta_si_continua(chat, frittata):
    chat.fake = FakeClaude(
        [Say("Ho iniziato."), Fail(FailureKind.MAX_TURNS, input_tokens=1, output_tokens=1, cost_usd=0.1)]
    )
    await scrivi(chat, frittata)
    messaggi = (await chat.client.get(url(frittata))).json()["messages"]
    assert messaggi[-1]["can_continue"] is True
    assert messaggi[0]["can_continue"] is False


async def test_riprova_toglie_il_tentativo_fallito(chat, frittata):
    chat.fake = FakeClaude([Fail(FailureKind.UNAVAILABLE)])
    risposta = await scrivi(chat, frittata, "Quanti spinaci?")
    assert eventi(risposta.text)[-1][0] == "error"
    messaggi = (await chat.client.get(url(frittata))).json()["messages"]
    assert [(m["role"], m["status"]) for m in messaggi] == [("user", "failed")]
    assert messaggi[0]["notice"] == failure_notice(FailureKind.UNAVAILABLE, None, datetime.now(UTC))

    chat.fake = FakeClaude([Say("Centocinquanta."), Finish()])
    risposta = await scrivi(chat, frittata, "Quanti spinaci?", retry_of=messaggi[0]["id"])
    assert eventi(risposta.text)[-1][0] == "done"
    messaggi = (await chat.client.get(url(frittata))).json()["messages"]
    assert [(m["role"], m["status"]) for m in messaggi] == [("user", "sent"), ("assistant", "sent")]


async def test_riprova_di_un_messaggio_che_non_e_fallito_e_404(chat, frittata):
    await scrivi(chat, frittata)
    sent = (await chat.client.get(url(frittata))).json()["messages"][0]["id"]
    risposta = await scrivi(chat, frittata, "Ancora", retry_of=sent)
    assert risposta.status_code == 404


async def test_il_giro_finisce_anche_se_chi_legge_se_ne_va(
    chat, frittata, voci, registry, db_session
):
    class Lento(FakeClaude):
        async def run(self, **kw):
            async for event in super().run(**kw):
                await asyncio.sleep(0.05)
                yield event

    chat.fake = Lento(
        [Say("Una risposta lunga abbastanza."), UseTool("write_recipe", spinaci_args(voci)), Finish()]
    )
    async with chat.client.stream(
        "POST", url(frittata, "/messages"), json={"text": "Ho gli spinaci congelati"}
    ) as risposta:
        async for riga in risposta.aiter_lines():
            if riga.startswith("event:"):
                break
    conversation = await get_or_create_dish_conversation(db_session, frittata.id)
    await registry.wait(conversation.id)
    corpo = (await chat.client.get(url(frittata))).json()
    assert [m["role"] for m in corpo["messages"]] == ["user", "assistant"]
    assert corpo["messages"][-1]["changes"][0]["summary"] == "spinaci congelati, padella unica"


async def _pasto(db_session, tipo):
    if tipo == "bozza":
        meal = await create_meal(db_session, day=DAY, slot=MealSlot.LUNCH, dish="Pasta", status="draft")
    elif tipo == "fuori casa":
        meal = await create_meal(db_session, day=DAY, slot=MealSlot.LUNCH, dish="Pizza", away=True)
    else:
        origine = await create_meal(db_session, day=DAY, slot=MealSlot.LUNCH, dish="Lasagne")
        meal = await create_meal(
            db_session, day=date(2026, 11, 14), slot=MealSlot.LUNCH, dish="Lasagne",
            leftover_of_id=origine.id,
        )
    await db_session.commit()
    return meal


@pytest.mark.parametrize("tipo", ["bozza", "fuori casa", "avanzo"])
async def test_niente_chat_per_bozza_fuori_casa_avanzo(chat, db_session, tipo):
    meal = await _pasto(db_session, tipo)
    for risposta in (await chat.client.get(url(meal)), await scrivi(chat, meal)):
        assert risposta.status_code == 409
        assert risposta.json() == {"code": "no_chat_here", "detail": NO_CHAT}


async def test_un_pasto_inesistente_e_404(chat, frittata):
    import uuid

    assert (await chat.client.get(f"/api/v1/meals/{uuid.uuid4()}/chat")).status_code == 404


async def test_il_pasto_dice_se_ha_la_chat(chat, frittata, db_session):
    fuori = await _pasto(db_session, "fuori casa")
    assert (await chat.client.get(f"/api/v1/meals/{frittata.id}")).json()["can_chat"] is True
    assert (await chat.client.get(f"/api/v1/meals/{fuori.id}")).json()["can_chat"] is False


@pytest.mark.parametrize("testo", ["", "   "])
async def test_un_testo_vuoto_e_422(chat, frittata, testo):
    assert (await scrivi(chat, frittata, testo)).status_code == 422


async def test_senza_accesso_401(client, frittata):
    assert (await client.get(url(frittata))).status_code == 401
    assert (await client.post(url(frittata, "/messages"), json={"text": "x"})).status_code == 401


def _scrivi_con_novelli(voci):
    args = spinaci_args(voci)
    args["ingredients"].append(
        {"name": "Spinaci novelli", "department": "verdura", "role": "secondary"}
    )
    return args


async def test_annullare_una_ricetta_scritta_dice_gli_ingredienti_che_restano(
    chat, db_session, voci
):
    senza_ricetta = await create_meal(
        db_session, day=DAY, slot=MealSlot.LUNCH, dish="Frittata di spinaci"
    )
    await db_session.commit()
    chat.fake = FakeClaude(
        [UseTool("write_recipe", _scrivi_con_novelli(voci)), Say("Fatto."), Finish()]
    )
    await scrivi(chat, senza_ricetta, "Scrivila.")
    corpo = (await chat.client.get(url(senza_ricetta))).json()
    change = corpo["messages"][-1]["changes"][0]
    assert change["created_recipe"] is True and change["kept_note"] is None
    risposta = await chat.client.post(url(senza_ricetta, f"/changes/{change['id']}/undo"))
    annullata = risposta.json()["messages"][-1]["changes"][0]
    assert annullata["undone"] is True
    assert annullata["kept_note"] == "Resta in Anagrafica: Spinaci novelli."


async def test_annullare_una_modifica_che_toglie_l_ingrediente_non_dice_niente(
    chat, frittata, voci
):
    chat.fake = FakeClaude(
        [UseTool("write_recipe", _scrivi_con_novelli(voci)), Say("Fatto."), Finish()]
    )
    await scrivi(chat, frittata, "Aggiungi qualcosa.")
    corpo = (await chat.client.get(url(frittata))).json()
    change_id = corpo["messages"][-1]["changes"][0]["id"]
    risposta = await chat.client.post(url(frittata, f"/changes/{change_id}/undo"))
    annullata = risposta.json()["messages"][-1]["changes"][0]
    assert annullata["undone"] is True
    assert annullata["kept_note"] is None


async def test_una_modifica_annullata_senza_ingredienti_creati_non_dice_niente(
    chat, frittata, voci
):
    change_id = await modifica(chat, frittata, voci)
    risposta = await chat.client.post(url(frittata, f"/changes/{change_id}/undo"))
    assert risposta.json()["messages"][-1]["changes"][0]["kept_note"] is None
