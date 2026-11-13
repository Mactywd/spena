"""La scheda inversa (piano 6c, Task 3, decisione 22): un pasto ufficiale che si toglie,
si sostituisce o va fuori casa propone di rimettere quello che le sue schede avevano
usato, senza rimettere ciò che serve ancora, che è cambiato dopo o che è stato
ricomprato."""

from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.change_card import CardStatus, ChangeCard, ChangeCardRow
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.shopping import ShoppingListItem, ShoppingStatus
from app.domain.meals import MealSlot, MealStatus
from app.domain.rules import PantryStatus
from app.repositories.pantry import set_status
from app.repositories.shopping import StockEntry, patch_item, stock_items
from app.services.change_cards import (
    ListProposal,
    PantryProposal,
    apply_card,
    get_card,
    propose_card,
)
from app.services.meals import create_meal, delete_meal, update_meal

A, L = PantryStatus.AVAILABLE, PantryStatus.LOW
F = PantryStatus.FINISHED

CHANGED = "Cambiata dopo la scheda: controlla prima di rimetterla."
IN_CART = "È già nel carrello."


@pytest_asyncio.fixture
async def mondo(db_session):
    def ing(name, category):
        return Ingredient(name=name, display_name=name.capitalize(), category=category)

    ingredienti = {
        "ricotta": ing("ricotta", IngredientCategory.LATTICINI),
        "parmigiano": ing("parmigiano", IngredientCategory.LATTICINI),
        "pesto": ing("pesto", IngredientCategory.CONDIMENTI),
    }
    db_session.add_all(ingredienti.values())
    await db_session.flush()
    voci = {
        nome: PantryItem(ingredient_id=ingrediente.id, status=A)
        for nome, ingrediente in ingredienti.items()
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    pasto_a = await create_meal(
        db_session, day=date(2026, 11, 20), slot=MealSlot.DINNER, dish="Pasta alla ricotta"
    )
    pasto_b = await create_meal(
        db_session, day=date(2026, 11, 21), slot=MealSlot.LUNCH, dish="Risotto"
    )
    bozza = await create_meal(
        db_session, day=date(2026, 11, 22), slot=MealSlot.DINNER, dish="Lasagne",
        status=MealStatus.DRAFT,
    )
    return {"ing": ingredienti, "voci": voci, "A": pasto_a, "B": pasto_b, "bozza": bozza}


async def applicata(db_session, meals, pantry, shopping=()):
    card = await propose_card(db_session, meals=meals, pantry=pantry, shopping=list(shopping))
    return await apply_card(db_session, card.id, [])


async def inverse(db_session) -> list[ChangeCard]:
    ids = (
        await db_session.execute(
            select(ChangeCard.id)
            .where(ChangeCard.kind == "inverse")
            .order_by(ChangeCard.created_at, ChangeCard.id)
        )
    ).scalars().all()
    return [await get_card(db_session, card_id) for card_id in ids]


async def l_inversa(db_session) -> ChangeCard:
    (card,) = await inverse(db_session)
    return card


def righe(card, kind):
    return [r for r in card.rows if r.kind == kind]


def riga(card, kind, label):
    (r,) = [r for r in card.rows if r.kind == kind and r.label == label]
    return r


async def voce_in_lista(db_session, ingredient) -> ShoppingListItem:
    (voce,) = (
        await db_session.execute(
            select(ShoppingListItem).where(ShoppingListItem.ingredient_id == ingredient.id)
        )
    ).scalars().all()
    return voce


async def test_togliere_un_pasto_propone_l_inversa(db_session, mondo):
    await applicata(db_session, [mondo["A"]], [PantryProposal(mondo["voci"]["ricotta"].id, F)])
    await delete_meal(db_session, mondo["A"])

    card = await l_inversa(db_session)
    assert card.kind == "inverse" and card.status == "proposed"
    assert card.title == "Hai tolto «Pasta alla ricotta»: rimetti quello che usava?"
    (p,) = righe(card, "pantry")
    assert (p.label, p.to_status, p.checked, p.note) == ("ricotta", "available", True, None)
    assert p.pantry_item_id == mondo["voci"]["ricotta"].id
    (u,) = righe(card, "unlist")
    assert u.checked is True and u.note is None
    assert u.shopping_item_id == (await voce_in_lista(db_session, mondo["ing"]["ricotta"])).id
    assert righe(card, "list") == []


async def test_applicare_l_inversa_rimette_e_toglie_dalla_lista(db_session, mondo):
    a, b, v = mondo["A"], mondo["B"], mondo["voci"]
    # la ricotta serve ad A e a B; B va fuori casa, quindi togliendo A nessuno la usa più
    avanti = await applicata(db_session, [a, b], [PantryProposal(v["ricotta"].id, F)])
    await update_meal(db_session, b, {"away": True})
    assert await inverse(db_session) == []  # la usava ancora A

    await delete_meal(db_session, a)
    card = await l_inversa(db_session)
    done = await apply_card(db_session, card.id, [])

    assert done.status == "applied"
    await db_session.refresh(v["ricotta"])
    assert v["ricotta"].status == "available"
    voce = await voce_in_lista(db_session, mondo["ing"]["ricotta"])
    await db_session.refresh(voce)
    assert voce.status == ShoppingStatus.ARCHIVED
    assert all(r.applied for r in done.rows)
    avanti = await get_card(db_session, avanti.id)
    assert all(r.reversed_at is not None for r in avanti.rows)

    # B, fuori casa, si toglie anche lui: le righe annullate non si ripropongono
    await delete_meal(db_session, b)
    assert [c.id for c in await inverse(db_session)] == [card.id]


@pytest.mark.parametrize("come", ["sostituito", "sostituito_spostando", "fuori", "spostato"])
async def test_sostituire_e_fuori_casa_propongono_spostare_no(db_session, mondo, come):
    a = mondo["A"]
    await applicata(db_session, [a], [PantryProposal(mondo["voci"]["ricotta"].id, F)])
    if come == "sostituito":
        await create_meal(
            db_session, day=a.day, slot=MealSlot(a.slot), dish="Frittata", replace=True
        )
        titolo = "Hai sostituito «Pasta alla ricotta»: rimetti quello che usava?"
    elif come == "sostituito_spostando":
        await update_meal(
            db_session, mondo["B"], {"day": a.day, "slot": a.slot}, replace=True
        )
        titolo = "Hai sostituito «Pasta alla ricotta»: rimetti quello che usava?"
    elif come == "fuori":
        await update_meal(db_session, a, {"away": True})
        titolo = "«Pasta alla ricotta» è fuori casa: rimetti quello che usava?"
    else:
        await update_meal(db_session, a, {"day": date(2026, 11, 25)})
        assert await inverse(db_session) == []
        return
    card = await l_inversa(db_session)
    assert card.title == titolo
    assert [r.kind for r in card.rows] == ["pantry", "unlist"]


async def test_l_inversa_non_rimette_cio_che_serve_ancora_a_un_altro_pasto(db_session, mondo):
    a, b, v = mondo["A"], mondo["B"], mondo["voci"]
    await applicata(
        db_session, [a, b],
        [
            PantryProposal(v["parmigiano"].id, L),  # serve ad A e a B
            PantryProposal(v["ricotta"].id, L, (a.id,)),  # solo ad A
        ],
    )
    await delete_meal(db_session, a)
    prima = await l_inversa(db_session)
    assert [(r.kind, r.label) for r in prima.rows] == [("pantry", "ricotta")]

    await delete_meal(db_session, b)
    seconda = [c for c in await inverse(db_session) if c.id != prima.id]
    (seconda,) = seconda
    assert [(r.kind, r.label, r.to_status) for r in seconda.rows] == [
        ("pantry", "parmigiano", "available")
    ]


async def test_l_inversa_dopo_una_spesa_nel_frattempo(db_session, mondo):
    ricotta, ing = mondo["voci"]["ricotta"], mondo["ing"]["ricotta"]
    await applicata(db_session, [mondo["A"]], [PantryProposal(ricotta.id, F)])
    voce = await voce_in_lista(db_session, ing)
    (nuova,) = await stock_items(db_session, [StockEntry(voce.id, ing.id, None, None)])
    await db_session.refresh(nuova)
    nuova_id, nuova_cambiata = nuova.id, nuova.status_changed_at
    assert nuova.status == "available"

    await delete_meal(db_session, mondo["A"])
    card = await l_inversa(db_session)
    assert righe(card, "unlist") == []
    (p,) = righe(card, "pantry")
    assert p.pantry_item_id == ricotta.id
    assert (p.to_status, p.checked) == ("available", True)

    await apply_card(db_session, card.id, [])
    await db_session.refresh(ricotta)
    assert ricotta.status == "available"
    nuova = await db_session.get(PantryItem, nuova_id)
    await db_session.refresh(nuova)
    assert nuova.id == nuova_id and nuova.status_changed_at == nuova_cambiata
    await db_session.refresh(voce)
    assert voce.status == ShoppingStatus.DONE


async def test_una_voce_cambiata_dopo_non_si_spunta(db_session, mondo):
    parmigiano = mondo["voci"]["parmigiano"]
    await applicata(db_session, [mondo["A"]], [PantryProposal(parmigiano.id, L)])
    await set_status(db_session, parmigiano.id, F)  # Mattia, dalla dispensa

    await delete_meal(db_session, mondo["A"])
    (p,) = (await l_inversa(db_session)).rows
    assert p.label == "parmigiano" and p.to_status == "available"
    assert p.checked is False and p.editable is True
    assert p.note == CHANGED


async def test_una_voce_gia_tornata_allo_stato_di_prima_non_c_e(db_session, mondo):
    v = mondo["voci"]
    await applicata(
        db_session, [mondo["A"]],
        [PantryProposal(v["ricotta"].id, F), PantryProposal(v["parmigiano"].id, L)],
    )
    await set_status(db_session, v["ricotta"].id, A)  # rimessa a mano
    await delete_meal(db_session, mondo["A"])
    card = await l_inversa(db_session)
    assert [(r.kind, r.label) for r in card.rows] == [
        ("pantry", "parmigiano"), ("unlist", "ricotta"),
    ]

    # se non resta nessuna riga, nessuna scheda
    await applicata(db_session, [mondo["B"]], [PantryProposal(v["pesto"].id, L)])
    await set_status(db_session, v["pesto"].id, A)
    await delete_meal(db_session, mondo["B"])
    assert [c.id for c in await inverse(db_session)] == [card.id]


async def test_nel_carrello_non_si_spunta(db_session, mondo):
    await applicata(db_session, [mondo["A"]], [PantryProposal(mondo["voci"]["ricotta"].id, F)])
    voce = await voce_in_lista(db_session, mondo["ing"]["ricotta"])
    await patch_item(db_session, voce.id, status=ShoppingStatus.CHECKED)

    await delete_meal(db_session, mondo["A"])
    (u,) = righe(await l_inversa(db_session), "unlist")
    assert u.checked is False and u.note == IN_CART


async def test_una_bozza_non_propone_niente(db_session, mondo):
    await applicata(
        db_session, [mondo["bozza"]], [], [ListProposal(mondo["ing"]["ricotta"].id, "Ricotta")]
    )
    await delete_meal(db_session, mondo["bozza"])
    assert await inverse(db_session) == []
    voce = await voce_in_lista(db_session, mondo["ing"]["ricotta"])
    assert voce.status == ShoppingStatus.PENDING


async def test_le_schede_proposte_del_pasto_tolto_si_puliscono(db_session, mondo):
    a, b, v = mondo["A"], mondo["B"], mondo["voci"]
    sola = await propose_card(
        db_session, meals=[a], pantry=[PantryProposal(v["pesto"].id, L)], shopping=[]
    )
    insieme = await propose_card(
        db_session, meals=[a, b],
        pantry=[
            PantryProposal(v["parmigiano"].id, L),
            PantryProposal(v["ricotta"].id, F, (a.id,)),
        ],
        shopping=[],
    )
    await delete_meal(db_session, a)

    sola = await get_card(db_session, sola.id)
    assert sola.status == CardStatus.DISCARDED and sola.discarded_at is not None
    insieme = await get_card(db_session, insieme.id)
    assert insieme.status == CardStatus.PROPOSED
    assert [(r.kind, r.label) for r in insieme.rows] == [("pantry", "parmigiano")]
    assert insieme.meal_ids == [str(b.id)]
    assert insieme.rows[0].meal_ids == [str(b.id)]
    # nessuna scheda inversa: niente era stato applicato
    assert await inverse(db_session) == []
    assert (
        await db_session.execute(
            select(ChangeCardRow).where(ChangeCardRow.card_id == sola.id)
        )
    ).scalars().all() == []
