import uuid
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.change_card import CardKind, CardStatus, ChangeCard, ChangeCardRow
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.shopping import ShoppingListItem, ShoppingStatus
from app.domain.meals import MealSlot, MealStatus
from app.domain.rules import PantryStatus
from app.repositories.shopping import add_item
from app.services.change_cards import (
    CardRefusal,
    CardRefusalCode,
    ListProposal,
    PantryProposal,
    RowOverride,
    add_row,
    apply_card,
    cards_with_status,
    create_empty_card,
    discard_card,
    get_card,
    open_card_for_meal,
    _supersedes,
    propose_card,
)
from app.services.meals import create_meal

A, L = PantryStatus.AVAILABLE, PantryStatus.LOW
F = PantryStatus.FINISHED


@pytest_asyncio.fixture
async def mondo(db_session):
    def ing(name, category):
        return Ingredient(name=name, display_name=name.capitalize(), category=category)

    ingredienti = {
        "ricotta": ing("ricotta", IngredientCategory.LATTICINI),
        "parmigiano": ing("parmigiano", IngredientCategory.LATTICINI),
        "pesto": ing("pesto", IngredientCategory.CONDIMENTI),
        "pasta": ing("pasta", IngredientCategory.CONDIMENTI),
        "detersivo": ing("detersivo", IngredientCategory.CASA),
    }
    db_session.add_all(ingredienti.values())
    await db_session.flush()
    prodotto = Product(
        ingredient_id=ingredienti["pesto"].id, name="Pesto Barilla", source="custom"
    )
    db_session.add(prodotto)
    await db_session.flush()
    voci = {}
    for nome, ingrediente in ingredienti.items():
        voci[nome] = PantryItem(
            ingredient_id=ingrediente.id, status=A,
            product_id=prodotto.id if nome == "pesto" else None,
        )
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


def righe(card, kind):
    return [r for r in card.rows if r.kind == kind]


def riga(card, kind, label):
    (r,) = [r for r in card.rows if r.kind == kind and r.label == label]
    return r


async def lista_attiva(db_session, ingredient):
    return list(
        (
            await db_session.execute(
                select(ShoppingListItem).where(
                    ShoppingListItem.ingredient_id == ingredient.id,
                    ShoppingListItem.status.in_(
                        [ShoppingStatus.PENDING, ShoppingStatus.CHECKED]
                    ),
                )
            )
        ).scalars()
    )


async def test_una_scheda_dalla_proposta(db_session, mondo):
    v = mondo["voci"]
    card = await propose_card(
        db_session, meals=[mondo["A"]],
        pantry=[PantryProposal(v["ricotta"].id, F), PantryProposal(v["parmigiano"].id, L)],
        shopping=[ListProposal(mondo["ing"]["ricotta"].id, "Ricotta")],
    )
    await db_session.flush()
    card = await get_card(db_session, card.id)
    assert card.title == "Per «Pasta alla ricotta»"
    assert card.kind == "forward" and card.status == "proposed" and card.list_only is False
    assert [(r.kind, r.label, r.to_status, r.checked) for r in card.rows] == [
        ("pantry", "ricotta", "finished", True),
        ("pantry", "parmigiano", "low", True),
        ("list", "ricotta", None, True),
    ]


async def test_quasi_finito_non_va_in_lista_da_solo(db_session, mondo):
    v = mondo["voci"]
    uno = await propose_card(
        db_session, meals=[mondo["A"]], pantry=[PantryProposal(v["pesto"].id, L)], shopping=[]
    )
    due = await propose_card(
        db_session, meals=[mondo["B"]], pantry=[PantryProposal(v["pesto"].id, L)], shopping=[]
    )
    for card in (uno, due):
        carta = await get_card(db_session, card.id)
        assert righe(carta, "list") == []
        assert [r.label for r in carta.rows] == ["Pesto Barilla"]


async def test_una_voce_gia_in_lista_non_si_ripropone(db_session, mondo):
    await add_item(db_session, "Ricotta", mondo["ing"]["ricotta"].id)
    card = await propose_card(
        db_session, meals=[mondo["A"]],
        pantry=[PantryProposal(mondo["voci"]["ricotta"].id, F)],
        shopping=[ListProposal(mondo["ing"]["ricotta"].id, "Ricotta")],
    )
    (r,) = righe(await get_card(db_session, card.id), "list")
    assert r.checked is False
    assert r.editable is False
    assert r.note == "Già in lista."


async def test_due_pasti_sulla_stessa_voce_fanno_una_riga(db_session, mondo):
    v, a, b = mondo["voci"], mondo["A"], mondo["B"]
    card = await propose_card(
        db_session, meals=[a, b],
        pantry=[
            PantryProposal(v["parmigiano"].id, L, (a.id,)),
            PantryProposal(v["parmigiano"].id, F, (b.id,)),
        ],
        shopping=[],
    )
    card = await get_card(db_session, card.id)
    assert card.title == "Per 2 pasti"
    (r,) = righe(card, "pantry")
    assert r.to_status == "finished"
    assert set(r.meal_ids) == {str(a.id), str(b.id)}
    # e la riga della lista nata dalla finita ha gli stessi pasti
    (lst,) = righe(card, "list")
    assert lst.label == "parmigiano" and set(lst.meal_ids) == {str(a.id), str(b.id)}


async def test_una_bozza_ha_solo_la_lista(db_session, mondo):
    with pytest.raises(CardRefusal) as exc:
        await propose_card(
            db_session, meals=[mondo["bozza"]],
            pantry=[PantryProposal(mondo["voci"]["pasta"].id, L)], shopping=[],
        )
    assert exc.value.code == CardRefusalCode.LIST_ONLY
    card = await propose_card(
        db_session, meals=[mondo["bozza"]], pantry=[],
        shopping=[ListProposal(None, "zenzero candito")],
    )
    card = await get_card(db_session, card.id)
    assert card.list_only is True
    assert card.title == "Per la spesa: «Lasagne» in bozza"


async def test_niente_non_alimentari_e_voci_sparite(db_session, mondo):
    with pytest.raises(CardRefusal) as exc:
        await propose_card(
            db_session, meals=[mondo["A"]],
            pantry=[PantryProposal(mondo["voci"]["detersivo"].id, F)], shopping=[],
        )
    assert exc.value.code == CardRefusalCode.NOT_FOOD
    mondo["voci"]["pasta"].archived_at = datetime.now(UTC)
    await db_session.flush()
    with pytest.raises(CardRefusal) as exc:
        await propose_card(
            db_session, meals=[mondo["A"]],
            pantry=[PantryProposal(mondo["voci"]["pasta"].id, F)], shopping=[],
        )
    assert exc.value.code == CardRefusalCode.NOT_IN_PANTRY


async def _scheda_standard(db_session, mondo):
    v = mondo["voci"]
    return await propose_card(
        db_session, meals=[mondo["A"]],
        pantry=[PantryProposal(v["ricotta"].id, F), PantryProposal(v["parmigiano"].id, L)],
        shopping=[],
    )


async def test_applicare_cambia_dispensa_e_lista_e_ricorda_lo_stato_di_prima(db_session, mondo):
    card = await _scheda_standard(db_session, mondo)
    ricotta = mondo["voci"]["ricotta"]
    ricotta.fill_percent = 80
    prima = ricotta.status_changed_at
    await db_session.flush()

    done = await apply_card(db_session, card.id, [])
    await db_session.flush()
    await db_session.refresh(ricotta)

    assert done.status == "applied" and done.applied_at is not None
    assert ricotta.status == "finished" and ricotta.fill_percent is None
    assert ricotta.status_changed_at != prima
    (voce,) = await lista_attiva(db_session, mondo["ing"]["ricotta"])
    assert voce.status == ShoppingStatus.PENDING
    p = riga(done, "pantry", "ricotta")
    assert (p.before_status, p.applied) == ("available", True)
    lst = riga(done, "list", "ricotta")
    assert lst.shopping_item_id == voce.id and lst.list_added is True and lst.applied is True


async def test_le_correzioni_di_mattia(db_session, mondo):
    card = await _scheda_standard(db_session, mondo)
    parm = riga(card, "pantry", "parmigiano")
    ric = riga(card, "pantry", "ricotta")
    done = await apply_card(
        db_session, card.id,
        [RowOverride(parm.id, False), RowOverride(ric.id, True, L)],
    )
    await db_session.refresh(mondo["voci"]["parmigiano"])
    await db_session.refresh(mondo["voci"]["ricotta"])
    assert mondo["voci"]["parmigiano"].status == "available"
    assert riga(done, "pantry", "parmigiano").applied is False
    assert mondo["voci"]["ricotta"].status == "low"
    assert riga(done, "list", "ricotta").applied is True
    assert len(await lista_attiva(db_session, mondo["ing"]["ricotta"])) == 1


async def test_una_voce_entrata_in_lista_dopo_non_si_duplica(db_session, mondo):
    card = await _scheda_standard(db_session, mondo)
    await add_item(db_session, "Ricotta", mondo["ing"]["ricotta"].id)
    done = await apply_card(db_session, card.id, [])
    assert len(await lista_attiva(db_session, mondo["ing"]["ricotta"])) == 1
    assert riga(done, "list", "ricotta").list_added is False


async def test_applicare_due_volte_e_409_e_non_cambia_niente(db_session, mondo):
    card = await _scheda_standard(db_session, mondo)
    await apply_card(db_session, card.id, [])
    ricotta = mondo["voci"]["ricotta"]
    await db_session.refresh(ricotta)
    cambiato = ricotta.status_changed_at
    with pytest.raises(CardRefusal) as exc:
        await apply_card(db_session, card.id, [])
    assert exc.value.code == CardRefusalCode.ALREADY_APPLIED
    await db_session.refresh(ricotta)
    assert ricotta.status_changed_at == cambiato
    assert len(await lista_attiva(db_session, mondo["ing"]["ricotta"])) == 1


async def test_scartare(db_session, mondo):
    card = await _scheda_standard(db_session, mondo)
    done = await discard_card(db_session, card.id)
    assert done.status == "discarded"
    await db_session.refresh(mondo["voci"]["ricotta"])
    assert mondo["voci"]["ricotta"].status == "available"
    assert await lista_attiva(db_session, mondo["ing"]["ricotta"]) == []
    with pytest.raises(CardRefusal) as exc:
        await apply_card(db_session, card.id, [])
    assert exc.value.code == CardRefusalCode.DISCARDED
    altra = await _scheda_standard(db_session, mondo)
    await apply_card(db_session, altra.id, [])
    with pytest.raises(CardRefusal) as exc:
        await discard_card(db_session, altra.id)
    assert exc.value.code == CardRefusalCode.ALREADY_APPLIED


async def test_una_voce_sparita_si_salta(db_session, mondo):
    card = await _scheda_standard(db_session, mondo)
    mondo["voci"]["parmigiano"].archived_at = datetime.now(UTC)
    await db_session.flush()
    done = await apply_card(db_session, card.id, [])
    parm = riga(done, "pantry", "parmigiano")
    assert parm.applied is False and parm.note == "La voce non è più in dispensa."
    assert riga(done, "pantry", "ricotta").applied is True
    assert done.status == "applied"


async def test_la_scheda_vuota_e_le_righe_a_mano(db_session, mondo):
    card = await create_empty_card(db_session, mondo["A"])
    assert card.title == "Per «Pasta alla ricotta»: compila a mano"
    assert list(card.rows) == []
    v = mondo["voci"]
    card = await add_row(db_session, card, pantry_item_id=v["parmigiano"].id)
    (r,) = righe(card, "pantry")
    assert r.to_status == "available" and r.checked is True
    with pytest.raises(CardRefusal) as exc:
        await add_row(db_session, card, pantry_item_id=v["parmigiano"].id)
    assert exc.value.code == CardRefusalCode.ROW_EXISTS
    card = await add_row(db_session, card, raw_text="Ricotta")
    assert riga(card, "list", "Ricotta").ingredient_id == mondo["ing"]["ricotta"].id
    card = await add_row(db_session, card, raw_text="zenzero candito")
    assert riga(card, "list", "zenzero candito").ingredient_id is None
    with pytest.raises(CardRefusal) as exc:
        await add_row(db_session, card, raw_text="RICOTTA")
    assert exc.value.code == CardRefusalCode.ROW_EXISTS


async def test_open_card_for_meal(db_session, mondo):
    card = await _scheda_standard(db_session, mondo)
    trovata = await open_card_for_meal(db_session, mondo["A"].id)
    assert trovata is not None and trovata.id == card.id
    assert await open_card_for_meal(db_session, mondo["B"].id) is None
    await apply_card(db_session, card.id, [])
    assert await open_card_for_meal(db_session, mondo["A"].id) is None
    assert [c.id for c in await cards_with_status(db_session, CardStatus.APPLIED)] == [card.id]
    assert await cards_with_status(db_session, CardStatus.PROPOSED) == []
    assert (
        await db_session.execute(select(ChangeCardRow).where(ChangeCardRow.card_id == card.id))
    ).scalars().all()


async def test_niente_non_alimentari_nemmeno_fra_le_cose_da_comprare(db_session, mondo):
    # C-R5: la scheda è di ciò che usano i pasti; il detersivo va in lista da sé
    detersivo = mondo["ing"]["detersivo"]
    for proposta in (ListProposal(detersivo.id, "Detersivo"), ListProposal(None, "detersivo")):
        with pytest.raises(CardRefusal) as exc:
            await propose_card(db_session, meals=[mondo["A"]], pantry=[], shopping=[proposta])
        assert exc.value.code == CardRefusalCode.NOT_FOOD
    card = await create_empty_card(db_session, mondo["A"])
    with pytest.raises(CardRefusal) as exc:
        await add_row(db_session, card, pantry_item_id=mondo["voci"]["detersivo"].id)
    assert exc.value.code == CardRefusalCode.NOT_FOOD
    with pytest.raises(CardRefusal) as exc:
        await add_row(db_session, card, raw_text="Detersivo")
    assert exc.value.code == CardRefusalCode.NOT_FOOD
    card = await get_card(db_session, card.id)
    assert list(card.rows) == []
    # un testo libero che non è niente dell'anagrafica resta permesso
    card = await add_row(db_session, card, raw_text="zenzero candito")
    assert riga(card, "list", "zenzero candito").ingredient_id is None


async def _vuota(db_session, *pasti):
    return await propose_card(db_session, meals=list(pasti), pantry=[], shopping=[])


async def test_una_scheda_nuova_mette_da_parte_quella_vecchia_dello_stesso_pasto(
    db_session, mondo
):
    prima = await _vuota(db_session, mondo["A"])
    seconda = await _vuota(db_session, mondo["A"])
    prima = await get_card(db_session, prima.id)
    assert prima.status == "superseded" and prima.discarded_at is not None
    assert (await get_card(db_session, seconda.id)).status == "proposed"


async def test_la_scheda_della_settimana_mette_da_parte_quelle_dei_piatti(db_session, mondo):
    c = await create_meal(
        db_session, day=date(2026, 11, 23), slot=MealSlot.LUNCH, dish="Frittata"
    )
    solo_a = await _vuota(db_session, mondo["A"])
    a_b = await _vuota(db_session, mondo["A"], mondo["B"])
    nuova = await _vuota(db_session, mondo["A"], mondo["B"], c)
    assert (await get_card(db_session, solo_a.id)).status == "superseded"
    assert (await get_card(db_session, a_b.id)).status == "superseded"
    assert (await get_card(db_session, nuova.id)).status == "proposed"


async def test_la_scheda_di_un_piatto_non_mette_da_parte_quella_della_settimana(
    db_session, mondo
):
    c = await create_meal(
        db_session, day=date(2026, 11, 23), slot=MealSlot.LUNCH, dish="Frittata"
    )
    settimana = await _vuota(db_session, mondo["A"], mondo["B"], c)
    await _vuota(db_session, mondo["A"])
    assert (await get_card(db_session, settimana.id)).status == "proposed"


async def test_non_tocca_le_applicate_ne_le_inverse(db_session, mondo):
    applicata = await _vuota(db_session, mondo["A"])
    await apply_card(db_session, applicata.id, [])
    inversa = ChangeCard(
        created_at=datetime.now(UTC), status=CardStatus.PROPOSED.value,
        kind=CardKind.INVERSE.value, list_only=False, title="Inversa",
        meal_ids=[str(mondo["A"].id)],
    )
    db_session.add(inversa)
    await db_session.flush()
    nuova = await _vuota(db_session, mondo["A"])
    assert (await get_card(db_session, applicata.id)).status == "applied"
    assert (await get_card(db_session, inversa.id)).status == "proposed"
    assert (await get_card(db_session, nuova.id)).status == "proposed"


async def test_la_scheda_gia_applicata_non_diventa_sostituita(db_session, mondo):
    # Il caso sequenziale: la vecchia è applicata, poi ne nasce una nuova per lo stesso pasto.
    vecchia = await _vuota(db_session, mondo["A"])
    await apply_card(db_session, vecchia.id, [])
    nuova = await _vuota(db_session, mondo["A"])
    assert (await get_card(db_session, vecchia.id)).status == "applied"
    assert (await get_card(db_session, nuova.id)).status == "proposed"


async def test_la_corsa_fra_applicare_e_mettere_da_parte_lascia_applicata(engine):
    # Due sessioni vere (database committato, ripulito alla fine): `apply_card` tiene la
    # vecchia scheda FOR UPDATE e la passa ad `applied`; `_supersede_older` parte nel frattempo
    # e deve aspettare il lock, rivedere lo stato e saltarla, non riscriverla «superseded».
    import asyncio

    from sqlalchemy import delete
    from sqlalchemy.ext.asyncio import async_sessionmaker

    from app.services.change_cards import _supersede_older

    fabbrica = async_sessionmaker(engine, expire_on_commit=False)
    meal_id = str(uuid.uuid4())
    vecchia = ChangeCard(
        created_at=datetime.now(UTC), status=CardStatus.PROPOSED.value,
        kind=CardKind.FORWARD.value, list_only=False, title="Corsa", meal_ids=[meal_id],
    )
    nuova = ChangeCard(
        id=uuid.uuid4(), created_at=datetime.now(UTC), status=CardStatus.PROPOSED.value,
        kind=CardKind.FORWARD.value, list_only=False, title="Nuova", meal_ids=[meal_id],
    )
    async with fabbrica() as setup:
        setup.add(vecchia)
        await setup.commit()
        vecchia_id = vecchia.id
    try:
        async with fabbrica() as applica, fabbrica() as sostituisce:
            tenuta = (
                await applica.execute(
                    select(ChangeCard).where(ChangeCard.id == vecchia_id).with_for_update()
                )
            ).scalar_one()
            tenuta.status = CardStatus.APPLIED.value
            await applica.flush()

            async def parte():
                await _supersede_older(sostituisce, nuova)
                await sostituisce.commit()

            lavoro = asyncio.create_task(parte())
            await asyncio.sleep(0.5)
            await applica.commit()
            await asyncio.wait_for(lavoro, timeout=10)
        async with fabbrica() as lettura:
            finale = (
                await lettura.execute(select(ChangeCard).where(ChangeCard.id == vecchia_id))
            ).scalar_one()
            assert finale.status == "applied"
            assert finale.discarded_at is None
    finally:
        async with fabbrica() as pulizia:
            await pulizia.execute(delete(ChangeCard).where(ChangeCard.id == vecchia_id))
            await pulizia.commit()


async def test_mette_da_parte_anche_una_scheda_compilata_a_mano(db_session, mondo):
    a_mano = await create_empty_card(db_session, mondo["A"])
    await add_row(db_session, a_mano, raw_text="Besciamella")
    await _vuota(db_session, mondo["A"])
    assert (await get_card(db_session, a_mano.id)).status == "superseded"


async def test_una_scheda_messa_da_parte_non_si_applica(db_session, mondo):
    prima = await _vuota(db_session, mondo["A"])
    await add_row(db_session, prima, raw_text="Besciamella")
    await _vuota(db_session, mondo["A"])
    with pytest.raises(CardRefusal) as exc:
        await apply_card(db_session, prima.id, [])
    assert exc.value.code == CardRefusalCode.SUPERSEDED
    assert exc.value.message == "Sostituita da una scheda più nuova."
    letta = await get_card(db_session, prima.id)
    assert [r.label for r in letta.rows] == ["Besciamella"]


def test_supersedes():
    assert _supersedes(["a"], ["a"]) is True
    assert _supersedes(["a", "b"], ["a", "b", "c"]) is True
    assert _supersedes(["a", "b", "c"], ["a"]) is False
    assert _supersedes([], ["a"]) is False
