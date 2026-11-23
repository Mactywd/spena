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
    NO_LONGER_FINISHED_NOTE,
    PAST_MEAL_NOTE,
    InverseReason,
    ListProposal,
    PantryProposal,
    RowOverride,
    apply_card,
    discard_card,
    get_card,
    propose_card,
    propose_inverse_card,
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
    insieme = await propose_card(
        db_session, meals=[a, b],
        pantry=[
            PantryProposal(v["parmigiano"].id, L),
            PantryProposal(v["ricotta"].id, F, (a.id,)),
        ],
        shopping=[],
    )
    # dopo «insieme»: una scheda del solo pasto A non mette da parte quella di A e B
    sola = await propose_card(
        db_session, meals=[a], pantry=[PantryProposal(v["pesto"].id, L)], shopping=[]
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


async def test_una_scheda_inversa_sola_per_pasto(db_session, mondo):
    # fuori casa, l'inversa resta proposta; poi il pasto si toglie: la vecchia si scarta
    a = mondo["A"]
    await applicata(db_session, [a], [PantryProposal(mondo["voci"]["ricotta"].id, F)])
    await update_meal(db_session, a, {"away": True})
    (fuori,) = await inverse(db_session)
    await delete_meal(db_session, a)

    fuori = await get_card(db_session, fuori.id)
    assert fuori.status == CardStatus.DISCARDED and fuori.discarded_at is not None
    (proposta,) = [c for c in await inverse(db_session) if c.status == CardStatus.PROPOSED]
    assert proposta.title == "Hai tolto «Pasta alla ricotta»: rimetti quello che usava?"


async def test_una_riga_gia_rimessa_non_si_rimette_due_volte(db_session, mondo):
    # la ricotta serve ad A e alla bozza: due pasti diversi, due inverse dalla stessa riga
    a, bozza, v = mondo["A"], mondo["bozza"], mondo["voci"]
    await applicata(db_session, [a, bozza], [PantryProposal(v["ricotta"].id, F)])
    await update_meal(db_session, a, {"away": True})
    await update_meal(db_session, bozza, {"status": MealStatus.OFFICIAL})
    await update_meal(db_session, bozza, {"away": True})
    prima, seconda = await inverse(db_session)
    assert [r.kind for r in prima.rows] == [r.kind for r in seconda.rows] == ["pantry", "unlist"]

    await apply_card(db_session, prima.id, [])
    await set_status(db_session, v["ricotta"].id, F)  # Mattia la usa di nuovo
    await db_session.refresh(v["ricotta"])
    cambiata = v["ricotta"].status_changed_at

    done = await apply_card(db_session, seconda.id, [])
    assert [(r.applied, r.note) for r in done.rows] == [
        (False, "Già rimessa da un'altra scheda."),
        (False, "Già rimessa da un'altra scheda."),
    ]
    await db_session.refresh(v["ricotta"])
    assert v["ricotta"].status == "finished"
    assert v["ricotta"].status_changed_at == cambiata
    voce = await voce_in_lista(db_session, mondo["ing"]["ricotta"])
    await db_session.refresh(voce)
    assert voce.status == ShoppingStatus.ARCHIVED


async def test_fuori_casa_propone_ancora_l_inversa(db_session, mondo):
    # il pasto tiene la ricetta (nascosta), ma l'inversa nasce come prima
    a = mondo["A"]
    await applicata(db_session, [a], [PantryProposal(mondo["voci"]["ricotta"].id, F)])
    await update_meal(db_session, a, {"away": True})
    card = await l_inversa(db_session)
    assert card.title == "«Pasta alla ricotta» è fuori casa: rimetti quello che usava?"
    (p,) = righe(card, "pantry")
    assert (p.label, p.to_status) == ("ricotta", "available")


async def test_due_schede_dello_stesso_pasto_che_si_annullano_sulla_voce(db_session, mondo):
    # il caso del rilievo: la scheda 2 rimette gli spinaci, la 1 li aveva finiti
    a, v = mondo["A"], mondo["voci"]
    await applicata(db_session, [a], [PantryProposal(v["ricotta"].id, F)])
    await applicata(
        db_session, [a],
        [PantryProposal(v["ricotta"].id, A), PantryProposal(v["parmigiano"].id, F)],
    )
    await delete_meal(db_session, a)
    card = await l_inversa(db_session)
    assert [r.label for r in righe(card, "pantry")] == ["parmigiano"]
    p = riga(card, "pantry", "parmigiano")
    assert (p.to_status, p.checked) == ("available", True)


async def test_due_schede_sulla_stessa_voce_rimettono_lo_stato_di_partenza(db_session, mondo):
    a, ricotta = mondo["A"], mondo["voci"]["ricotta"]
    await applicata(db_session, [a], [PantryProposal(ricotta.id, L)])
    await applicata(db_session, [a], [PantryProposal(ricotta.id, F)])
    await delete_meal(db_session, a)
    (p,) = righe(await l_inversa(db_session), "pantry")
    assert (p.label, p.to_status, p.checked) == ("ricotta", "available", True)
    assert len(p.source_row_ids) == 2


async def test_una_voce_toccata_dopo_l_ultima_scheda_non_si_spunta(db_session, mondo):
    a, ricotta = mondo["A"], mondo["voci"]["ricotta"]
    await applicata(db_session, [a], [PantryProposal(ricotta.id, L)])
    await applicata(db_session, [a], [PantryProposal(ricotta.id, F)])
    await set_status(db_session, ricotta.id, L)  # a mano, dopo l'ultima scheda
    await delete_meal(db_session, a)
    (p,) = righe(await l_inversa(db_session), "pantry")
    assert (p.to_status, p.checked, p.note) == ("available", False, CHANGED)


async def test_applicare_l_inversa_segna_tutte_le_origini(db_session, mondo):
    a, ricotta = mondo["A"], mondo["voci"]["ricotta"]
    await applicata(db_session, [a], [PantryProposal(ricotta.id, L)])
    await applicata(db_session, [a], [PantryProposal(ricotta.id, F)])
    await delete_meal(db_session, a)
    card = await l_inversa(db_session)
    await apply_card(db_session, card.id, [])
    origini = (
        await db_session.execute(
            select(ChangeCardRow)
            .join(ChangeCard, ChangeCard.id == ChangeCardRow.card_id)
            .where(ChangeCard.kind == "forward", ChangeCardRow.kind == "pantry")
            .execution_options(populate_existing=True)
        )
    ).scalars().all()
    assert len(origini) == 2 and all(o.reversed_at is not None for o in origini)
    await db_session.refresh(ricotta)
    assert ricotta.status == "available"


async def test_l_inversa_del_fuori_casa_applicata_non_si_ripropone_all_eliminazione(
    db_session, mondo
):
    a, ricotta = mondo["A"], mondo["voci"]["ricotta"]
    await applicata(db_session, [a], [PantryProposal(ricotta.id, L)])
    await applicata(db_session, [a], [PantryProposal(ricotta.id, F)])
    await update_meal(db_session, a, {"away": True})
    (fuori,) = await inverse(db_session)
    await apply_card(db_session, fuori.id, [])
    await update_meal(db_session, a, {"away": False})
    await delete_meal(db_session, a)
    nuove = [c for c in await inverse(db_session) if c.id != fuori.id]
    assert all(righe(c, "pantry") == [] for c in nuove)


async def test_un_gruppo_che_serve_a_un_altro_pasto_si_salta(db_session, mondo):
    a, b, ricotta = mondo["A"], mondo["B"], mondo["voci"]["ricotta"]
    await applicata(db_session, [a, b], [PantryProposal(ricotta.id, L)])
    await applicata(db_session, [a], [PantryProposal(ricotta.id, F)])
    await delete_meal(db_session, a)
    assert all(righe(c, "pantry") == [] for c in await inverse(db_session))


async def _scheda_a_con_pesto_in_lista(db_session, mondo):
    """La scheda di A mette il pesto in lista (applicata, `list_added`)."""
    pesto = mondo["ing"]["pesto"]
    await applicata(db_session, [mondo["A"]], [], [ListProposal(pesto.id, "Pesto")])
    return pesto


@pytest.mark.parametrize("applicata_b", [False, True], ids=["proposta", "applicata"])
async def test_l_inversa_non_toglie_dalla_lista_cio_che_serve_a_un_altro_pasto(
    db_session, mondo, applicata_b
):
    pesto = await _scheda_a_con_pesto_in_lista(db_session, mondo)
    scheda_b = await propose_card(
        db_session, meals=[mondo["B"]], pantry=[], shopping=[ListProposal(pesto.id, "Pesto")]
    )
    (riga_b,) = righe(scheda_b, "list")
    assert riga_b.note == "Già in lista." and riga_b.checked is False
    if applicata_b:
        await apply_card(db_session, scheda_b.id, [])

    await delete_meal(db_session, mondo["A"])
    assert await inverse(db_session) == []  # era l'unica riga: l'inversa non nasce


async def test_una_riga_smarcata_sulla_scheda_di_un_altro_pasto_non_tiene_la_voce_in_lista(
    db_session, mondo
):
    pesto = mondo["ing"]["pesto"]
    scheda_b = await propose_card(
        db_session, meals=[mondo["B"]], pantry=[], shopping=[ListProposal(pesto.id, "Pesto")]
    )
    (riga_b,) = righe(scheda_b, "list")
    assert riga_b.editable is True and riga_b.checked is True
    await apply_card(db_session, scheda_b.id, [RowOverride(riga_b.id, checked=False)])
    riga_b = (await db_session.execute(
        select(ChangeCardRow).where(ChangeCardRow.id == riga_b.id)
    )).scalar_one()
    await db_session.refresh(riga_b)
    assert riga_b.applied is False

    await applicata(db_session, [mondo["A"]], [], [ListProposal(pesto.id, "Pesto")])
    await delete_meal(db_session, mondo["A"])

    card = await l_inversa(db_session)
    assert [(r.kind, r.label, r.checked) for r in card.rows] == [("unlist", "Pesto", True)]


async def test_una_riga_smarcata_su_una_scheda_ancora_proposta_tiene_la_voce(
    db_session, mondo
):
    pesto = await _scheda_a_con_pesto_in_lista(db_session, mondo)
    scheda_b = await propose_card(
        db_session, meals=[mondo["B"]], pantry=[], shopping=[ListProposal(pesto.id, "Pesto")]
    )
    (riga_b,) = righe(scheda_b, "list")
    assert riga_b.applied is None  # la scheda è ancora proposta
    await delete_meal(db_session, mondo["A"])
    assert await inverse(db_session) == []


async def test_una_riga_modificabile_su_una_scheda_proposta_prima_tiene_la_voce(
    db_session, mondo
):
    """B è proposta PRIMA che A metta il pesto in lista: la riga di B è modificabile
    (non «Già in lista.») e con `applied` NULL: la tiene solo il ramo «scheda proposta»."""
    pesto = mondo["ing"]["pesto"]
    scheda_b = await propose_card(
        db_session, meals=[mondo["B"]], pantry=[], shopping=[ListProposal(pesto.id, "Pesto")]
    )
    (riga_b,) = righe(scheda_b, "list")
    assert riga_b.editable is True and riga_b.applied is None
    await applicata(db_session, [mondo["A"]], [], [ListProposal(pesto.id, "Pesto")])
    await delete_meal(db_session, mondo["A"])
    assert await inverse(db_session) == []


async def test_una_scheda_scartata_non_tiene_la_voce_in_lista(db_session, mondo):
    pesto = await _scheda_a_con_pesto_in_lista(db_session, mondo)
    scheda_b = await propose_card(
        db_session, meals=[mondo["B"]], pantry=[], shopping=[ListProposal(pesto.id, "Pesto")]
    )
    await discard_card(db_session, scheda_b.id)
    await delete_meal(db_session, mondo["A"])
    assert [(r.kind, r.label) for r in (await l_inversa(db_session)).rows] == [
        ("unlist", "Pesto")
    ]


async def test_un_pasto_bozza_non_tiene_la_voce_in_lista(db_session, mondo):
    pesto = await _scheda_a_con_pesto_in_lista(db_session, mondo)
    await propose_card(
        db_session, meals=[mondo["bozza"]], pantry=[], shopping=[ListProposal(pesto.id, "Pesto")]
    )
    await delete_meal(db_session, mondo["A"])
    assert [(r.kind, r.label) for r in (await l_inversa(db_session)).rows] == [
        ("unlist", "Pesto")
    ]


# --- l'inversa di un pasto passato (decisioni 3 e 16 del piano 2026-11-21) -----------

PAST = "Pasto già passato: rimettila solo se non l'hai mangiato."


async def _a_con_ricotta_e_parmigiano_cambiato(db_session, mondo):
    """La scheda di A (20 novembre) finisce la ricotta e avvia il parmigiano; poi il
    parmigiano si finisce a mano: la sua riga inversa avrà `CHANGED_NOTE`."""
    v = mondo["voci"]
    await applicata(
        db_session, [mondo["A"]],
        [PantryProposal(v["ricotta"].id, F), PantryProposal(v["parmigiano"].id, L)],
    )
    await set_status(db_session, v["parmigiano"].id, F)


async def test_eliminare_un_pasto_passato_propone_l_inversa_senza_spunte(db_session, mondo):
    assert PAST_MEAL_NOTE == PAST
    await _a_con_ricotta_e_parmigiano_cambiato(db_session, mondo)
    await delete_meal(db_session, mondo["A"], today=date(2026, 11, 23))

    card = await l_inversa(db_session)
    assert card.status == "proposed"
    assert [(r.kind, r.label) for r in card.rows] == [
        ("pantry", "ricotta"), ("pantry", "parmigiano"), ("unlist", "ricotta"),
    ]
    assert all(r.checked is False and r.editable is True for r in card.rows)
    assert riga(card, "pantry", "ricotta").note == PAST
    assert riga(card, "unlist", "ricotta").note == PAST
    assert riga(card, "pantry", "parmigiano").note == CHANGED


async def test_eliminare_un_pasto_passato_tiene_la_nota_del_carrello(db_session, mondo):
    await applicata(db_session, [mondo["A"]], [PantryProposal(mondo["voci"]["ricotta"].id, F)])
    voce = await voce_in_lista(db_session, mondo["ing"]["ricotta"])
    await patch_item(db_session, voce.id, status=ShoppingStatus.CHECKED)
    await delete_meal(db_session, mondo["A"], today=date(2026, 11, 23))
    card = await l_inversa(db_session)
    assert riga(card, "unlist", "ricotta").note == IN_CART
    assert riga(card, "pantry", "ricotta").note == PAST


async def test_eliminare_un_pasto_di_oggi_spunta_come_sempre(db_session, mondo):
    await _a_con_ricotta_e_parmigiano_cambiato(db_session, mondo)
    await delete_meal(db_session, mondo["A"], today=date(2026, 11, 20))

    card = await l_inversa(db_session)
    assert [(r.kind, r.label, r.checked, r.note) for r in card.rows] == [
        ("pantry", "ricotta", True, None),
        ("pantry", "parmigiano", False, CHANGED),
        ("unlist", "ricotta", True, None),
    ]


async def test_senza_oggi_l_inversa_e_quella_di_sempre(db_session, mondo):
    await _a_con_ricotta_e_parmigiano_cambiato(db_session, mondo)
    await delete_meal(db_session, mondo["A"])  # il 20 novembre 2026 è passato, ma nessun controllo

    card = await l_inversa(db_session)
    assert [(r.kind, r.label, r.checked, r.note) for r in card.rows] == [
        ("pantry", "ricotta", True, None),
        ("pantry", "parmigiano", False, CHANGED),
        ("unlist", "ricotta", True, None),
    ]


@pytest.mark.parametrize("come", ["create_meal", "diretta", "fuori_casa"])
async def test_sostituire_un_pasto_passato_spunta_come_sempre(db_session, mondo, come):
    # decisione 16: solo l'eliminazione di un pasto passato toglie le spunte; sostituirlo o
    # mandarlo fuori casa vuol dire che quel pasto non si è mangiato
    a = mondo["A"]
    await applicata(db_session, [a], [PantryProposal(mondo["voci"]["ricotta"].id, F)])
    if come == "create_meal":
        await create_meal(
            db_session, day=a.day, slot=MealSlot(a.slot), dish="Frittata", replace=True
        )
    elif come == "diretta":
        await propose_inverse_card(
            db_session, a, InverseReason.REPLACED, today=date(2026, 11, 23)
        )
    else:
        await propose_inverse_card(db_session, a, InverseReason.AWAY, today=date(2026, 11, 23))
    card = await l_inversa(db_session)
    assert [(r.kind, r.checked, r.note) for r in card.rows] == [
        ("pantry", True, None), ("unlist", True, None),
    ]


async def test_l_inversa_toglie_la_riga_aggiunta_all_applicazione(db_session, mondo):
    # la panna proposta «Quasi finito» e corretta a «Finito»: la riga di lista nata
    # all'applicazione si toglie con l'inversa, come una qualunque altra
    panna = Ingredient(name="panna", display_name="Panna", category=IngredientCategory.LATTICINI)
    db_session.add(panna)
    await db_session.flush()
    voce = PantryItem(ingredient_id=panna.id, status=A)
    db_session.add(voce)
    await db_session.flush()
    card = await propose_card(
        db_session, meals=[mondo["A"]], pantry=[PantryProposal(voce.id, L)], shopping=[]
    )
    (dispensa,) = righe(card, "pantry")
    done = await apply_card(db_session, card.id, [RowOverride(dispensa.id, True, F)])
    (aggiunta,) = righe(done, "list")
    assert aggiunta.list_added is True

    await delete_meal(db_session, mondo["A"])
    card = await l_inversa(db_session)
    (u,) = righe(card, "unlist")
    assert (u.label, u.checked, u.note) == ("panna", True, None)
    assert u.shopping_item_id == aggiunta.shopping_item_id
    assert u.source_row_ids == [str(aggiunta.id)]
    (p,) = righe(card, "pantry")
    assert (p.pantry_item_id, p.to_status) == (voce.id, "available")


async def test_applicare_l_inversa_non_aggiunge_righe_di_lista(db_session, mondo):
    # F-R4: la lista segue la dispensa solo nelle schede in avanti. L'inversa che rimette
    # la ricotta «Finito» (com'era prima del pasto) non la porta in lista.
    ricotta = mondo["voci"]["ricotta"]
    await set_status(db_session, ricotta.id, F)
    await applicata(db_session, [mondo["A"]], [PantryProposal(ricotta.id, A)])
    await delete_meal(db_session, mondo["A"])
    card = await l_inversa(db_session)
    (p,) = righe(card, "pantry")
    assert (p.to_status, p.checked) == ("finished", True)

    done = await apply_card(db_session, card.id, [])
    assert righe(done, "list") == []
    await db_session.refresh(ricotta)
    assert ricotta.status == "finished"
    listed = (
        await db_session.execute(
            select(ShoppingListItem).where(
                ShoppingListItem.ingredient_id == mondo["ing"]["ricotta"].id
            )
        )
    ).scalars().all()
    assert listed == []


async def test_una_riga_saltata_non_tiene_in_lista_l_ingrediente(db_session, mondo):
    # F-R5: la scheda di B ha saltato la sua riga di lista (passata corretta a «Quasi
    # finito»): non serve a B, quindi eliminando A l'inversa toglie la passata dalla lista.
    passata = Ingredient(
        name="passata", display_name="Passata", category=IngredientCategory.CONDIMENTI
    )
    db_session.add(passata)
    await db_session.flush()
    voce = PantryItem(ingredient_id=passata.id, status=A)
    db_session.add(voce)
    await db_session.flush()

    di_b = await propose_card(
        db_session, meals=[mondo["B"]], pantry=[PantryProposal(voce.id, F)], shopping=[]
    )
    (riga_b,) = righe(di_b, "pantry")
    di_b = await apply_card(db_session, di_b.id, [RowOverride(riga_b.id, True, L)])
    (saltata,) = righe(di_b, "list")
    assert saltata.applied is False and saltata.note == NO_LONGER_FINISHED_NOTE

    di_a = await applicata(db_session, [mondo["A"]], [PantryProposal(voce.id, F)])
    (in_lista,) = righe(di_a, "list")
    assert in_lista.list_added is True

    await delete_meal(db_session, mondo["A"])
    card = await l_inversa(db_session)
    (u,) = righe(card, "unlist")
    assert u.shopping_item_id == in_lista.shopping_item_id and u.checked is True
