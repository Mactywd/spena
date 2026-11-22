"""Il registro dei giri (decisione 11): un giro per conversazione, staccato da chi legge."""

import asyncio
import uuid

import pytest

from app.services.chat_turns import TurnBusy, TurnRegistry, get_turn_registry
from app.services.meal_chat import ChatEvent


async def test_un_giro_alla_volta():
    registry = TurnRegistry()
    conversation_id = uuid.uuid4()
    go = asyncio.Event()

    async def run(emit):
        await go.wait()
        await emit(ChatEvent("done", {}))

    events = registry.start(conversation_id, run)
    assert registry.running(conversation_id)
    assert not registry.running(uuid.uuid4())
    with pytest.raises(TurnBusy):
        registry.start(conversation_id, run)

    go.set()
    assert [e.name async for e in events] == ["done"]
    await registry.wait(conversation_id)
    assert not registry.running(conversation_id)


async def test_il_giro_finisce_anche_senza_chi_legge():
    registry = TurnRegistry()
    conversation_id = uuid.uuid4()
    finished = []

    async def run(emit):
        await emit(ChatEvent("delta", {"text": "Ciao"}))
        await asyncio.sleep(0.05)
        await emit(ChatEvent("delta", {"text": " Mattia"}))
        await emit(ChatEvent("done", {}))
        finished.append(True)

    events = registry.start(conversation_id, run)
    first = await anext(events)
    assert first.data == {"text": "Ciao"}
    await events.aclose()

    await registry.wait(conversation_id)
    assert finished == [True]
    assert not registry.running(conversation_id)


async def test_un_eccezione_del_giro_chiude_lo_stream(caplog):
    registry = TurnRegistry()
    conversation_id = uuid.uuid4()

    async def run(emit):
        await emit(ChatEvent("delta", {"text": "x"}))
        raise RuntimeError("rotto")

    events = registry.start(conversation_id, run)
    assert [e.name async for e in events] == ["delta"]
    await registry.wait(conversation_id)
    assert not registry.running(conversation_id)
    assert "rotto" in caplog.text


async def test_wait_senza_giro_torna_subito():
    await TurnRegistry().wait(uuid.uuid4())


def test_il_registro_e_uno_solo():
    assert get_turn_registry() is get_turn_registry()
