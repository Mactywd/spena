import uuid
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.meal import Meal
from app.db.models.recipe import Recipe
from app.domain.meal_chat import can_chat
from app.domain.meals import MealSlot, MealStatus
from app.repositories.meals import (
    get_meal,
    leftover_candidates,
    meal_at,
    meal_of_recipe,
    meals_between,
)
from app.repositories.recipes import create_recipe, get_recipe
from app.services.meals import (
    MealRefusal,
    MealRefusalCode,
    check_can_take_recipe,
    copy_recipe_to_meal,
    create_meal,
    delete_meal,
    link_recipe,
    release_recipe,
    update_meal,
)

L, D = MealSlot.LUNCH, MealSlot.DINNER


def d(n: int) -> date:
    return date(2026, 11, n)


@pytest_asyncio.fixture
async def frittata(db_session):
    uova = Ingredient(name="uova", display_name="Uova", category=IngredientCategory.LATTICINI)
    zucchine = Ingredient(
        name="zucchine", display_name="Zucchine", category=IngredientCategory.VERDURA
    )
    db_session.add_all([uova, zucchine])
    await db_session.flush()
    return await create_recipe(
        db_session,
        title="Frittata", description="Con le zucchine", instructions="Sbatti. Cuoci.",
        servings=2, source="dataset", source_ref="https://example.test/frittata",
        ingredients=[
            (uova.id, "primary", "4", "grandi"),
            (zucchine.id, "secondary", "200 g", None),
        ],
        embedding=[0.5] * 384, cost=2, category="Secondi",
        image_url="https://example.test/f.jpg", prep_minutes=10, cook_minutes=15,
    )


async def with_copy(session, source, meal, *, in_book=False):
    copy = await copy_recipe_to_meal(session, meal, source)
    if in_book:
        copy.in_book = True
        await session.flush()
    return copy


async def fresh(session, recipe_id):
    recipe = await session.get(Recipe, recipe_id)
    await session.refresh(recipe)  # dal database, non dalla memoria
    return recipe


async def test_un_pasto_scritto_a_mano_nasce_ufficiale(db_session):
    m = await create_meal(db_session, day=d(10), slot=D, dish="Pizza")
    loaded = await get_meal(db_session, m.id)
    assert loaded.status == "official"
    assert loaded.away is False
    assert loaded.recipe_id is None


async def test_un_posto_occupato_rifiuta_e_nomina_chi_c_e(db_session):
    first = await create_meal(db_session, day=d(10), slot=D, dish="Pizza")
    with pytest.raises(MealRefusal) as exc:
        await create_meal(db_session, day=d(10), slot=D, dish="Pasta")
    assert exc.value.code == MealRefusalCode.SLOT_TAKEN
    assert exc.value.occupant.id == first.id
    assert exc.value.message == "C'è già «Pizza» in questo posto."


async def test_sostituire_toglie_il_vecchio_e_archivia_la_sua_ricetta_fuori_dal_ricettario(
    db_session, frittata
):
    old = await create_meal(db_session, day=d(10), slot=D, dish="Frittata")
    copy = await with_copy(db_session, frittata, old)
    old_id = old.id
    new = await create_meal(db_session, day=d(10), slot=D, dish="Pasta", replace=True)
    assert await get_meal(db_session, old_id) is None
    assert (await fresh(db_session, copy.id)).archived_at is not None
    assert (await meal_at(db_session, d(10), D)).id == new.id


async def test_un_avanzo_viene_da_un_pasto_prima(db_session):
    dinner = await create_meal(db_session, day=d(10), slot=D, dish="Lasagne")
    left = await create_meal(
        db_session, day=d(11), slot=L, dish="Lasagne di ieri", leftover_of_id=dinner.id
    )
    assert (await get_meal(db_session, left.id)).leftover_of_id == dinner.id


async def test_un_avanzo_rifiutato(db_session):
    # le origini diverse, per un avanzo al pranzo dell'11
    after = await create_meal(db_session, day=d(11), slot=D, dish="Dopo")
    base = await create_meal(db_session, day=d(9), slot=D, dish="Base")
    is_left = await create_meal(
        db_session, day=d(10), slot=L, dish="Avanzo", leftover_of_id=base.id
    )
    away = await create_meal(db_session, day=d(10), slot=D, dish="Ristorante", away=True)
    for origin in (after.id, is_left.id, away.id, uuid.uuid4()):
        with pytest.raises(MealRefusal) as exc:
            await create_meal(
                db_session, day=d(11), slot=L, dish="Avanzo?", leftover_of_id=origin
            )
        assert exc.value.code == MealRefusalCode.BAD_LEFTOVER
    assert await meal_at(db_session, d(11), L) is None


async def test_spostare_su_un_posto_vuoto(db_session):
    m = await create_meal(db_session, day=d(10), slot=D, dish="Pizza")
    await update_meal(db_session, m, {"day": d(13), "slot": "lunch"})
    assert (await meal_at(db_session, d(13), L)).id == m.id
    assert await meal_at(db_session, d(10), D) is None


async def test_spostare_su_un_posto_occupato_chiede_la_sostituzione_e_poi_sostituisce(
    db_session,
):
    m = await create_meal(db_session, day=d(10), slot=D, dish="Pizza")
    other = await create_meal(db_session, day=d(13), slot=L, dish="Pasta")
    other_id = other.id
    with pytest.raises(MealRefusal) as exc:
        await update_meal(db_session, m, {"day": d(13), "slot": "lunch"})
    assert exc.value.code == MealRefusalCode.SLOT_TAKEN
    assert exc.value.occupant.id == other_id
    assert (await meal_at(db_session, d(10), D)).id == m.id
    assert (await meal_at(db_session, d(13), L)).id == other_id
    await update_meal(db_session, m, {"day": d(13), "slot": "lunch"}, replace=True)
    assert await get_meal(db_session, other_id) is None
    assert (await meal_at(db_session, d(13), L)).id == m.id


async def test_fuori_casa_tiene_la_ricetta_e_toglie_l_avanzo(db_session, frittata):
    origin = await create_meal(db_session, day=d(10), slot=D, dish="Frittata")
    copy = await with_copy(db_session, frittata, origin)
    recipe_id = copy.id
    left = await create_meal(
        db_session, day=d(11), slot=L, dish="Frittata fredda", leftover_of_id=origin.id
    )
    await update_meal(db_session, origin, {"away": True})
    assert (await get_meal(db_session, origin.id)).recipe_id == recipe_id
    assert (await fresh(db_session, recipe_id)).archived_at is None
    assert (await get_meal(db_session, left.id)).leftover_of_id is None


async def test_tornare_a_casa_rimette_la_ricetta(db_session, frittata):
    m = await create_meal(db_session, day=d(10), slot=D, dish="Frittata")
    copy = await with_copy(db_session, frittata, m)
    await update_meal(db_session, m, {"away": True})
    back = await update_meal(db_session, m, {"away": False})
    assert back.away is False
    assert back.recipe_id == copy.id
    assert can_chat(back) is True


async def test_eliminare_un_pasto_fuori_casa_archivia_la_ricetta_nascosta(db_session, frittata):
    m = await create_meal(db_session, day=d(10), slot=D, dish="Frittata")
    copy = await with_copy(db_session, frittata, m)
    await update_meal(db_session, m, {"away": True})
    await delete_meal(db_session, m)
    assert (await fresh(db_session, copy.id)).archived_at is not None


async def test_un_pasto_fuori_casa_non_riceve_una_ricetta_nuova(db_session):
    # guarda il vincolo tolto dalla 0024: senza la CHECK, il rifiuto sta solo qui
    m = await create_meal(db_session, day=d(10), slot=D, dish="Fuori", away=True)
    with pytest.raises(MealRefusal) as exc:
        check_can_take_recipe(m)
    assert exc.value.code == MealRefusalCode.NO_RECIPE_HERE


async def test_un_avanzo_che_va_fuori_casa_perde_il_legame_e_l_origine_resta(db_session):
    origin = await create_meal(db_session, day=d(10), slot=D, dish="Frittata")
    left = await create_meal(
        db_session, day=d(11), slot=L, dish="Frittata fredda", leftover_of_id=origin.id
    )
    await update_meal(db_session, left, {"away": True})
    assert (await get_meal(db_session, left.id)).leftover_of_id is None
    assert (await get_meal(db_session, origin.id)) is not None


async def test_un_pasto_fuori_casa_si_crea_senza_legame_d_avanzo(db_session):
    origin = await create_meal(db_session, day=d(10), slot=D, dish="Frittata")
    m = await create_meal(
        db_session, day=d(11), slot=L, dish="Ristorante", away=True, leftover_of_id=origin.id
    )
    assert (await get_meal(db_session, m.id)).leftover_of_id is None


async def test_fuori_casa_lascia_nel_ricettario_la_ricetta_salvata(db_session, frittata):
    m = await create_meal(db_session, day=d(10), slot=D, dish="Frittata")
    copy = await with_copy(db_session, frittata, m, in_book=True)
    await update_meal(db_session, m, {"away": True})
    kept = await fresh(db_session, copy.id)
    assert kept.archived_at is None
    assert kept.in_book is True


async def test_fuori_casa_scollega_gli_avanzi_che_venivano_dal_pasto(db_session):
    # ruling A-R2
    origin = await create_meal(db_session, day=d(10), slot=D, dish="Lasagne")
    left = await create_meal(
        db_session, day=d(11), slot=L, dish="Lasagne di ieri", leftover_of_id=origin.id
    )
    await update_meal(db_session, origin, {"away": True})
    again = await get_meal(db_session, left.id)
    assert again.leftover_of_id is None
    assert again.dish == "Lasagne di ieri"


async def test_una_bozza_diventa_ufficiale_e_non_torna_indietro(db_session):
    m = await create_meal(db_session, day=d(10), slot=D, dish="Idea", status=MealStatus.DRAFT)
    assert (await get_meal(db_session, m.id)).status == "draft"
    await update_meal(db_session, m, {"status": "official"})
    assert (await get_meal(db_session, m.id)).status == "official"
    with pytest.raises(MealRefusal) as exc:
        await update_meal(db_session, m, {"status": "draft"})
    assert exc.value.code == MealRefusalCode.STAYS_OFFICIAL


async def test_eliminare_archivia_la_ricetta_fuori_dal_ricettario(db_session, frittata):
    m = await create_meal(db_session, day=d(10), slot=D, dish="Frittata")
    copy = await with_copy(db_session, frittata, m)
    mid = m.id
    await delete_meal(db_session, m)
    assert await get_meal(db_session, mid) is None
    assert (await fresh(db_session, copy.id)).archived_at is not None


async def test_eliminare_lascia_la_ricetta_del_ricettario(db_session, frittata):
    m = await create_meal(db_session, day=d(10), slot=D, dish="Frittata")
    copy = await with_copy(db_session, frittata, m, in_book=True)
    await delete_meal(db_session, m)
    kept = await fresh(db_session, copy.id)
    assert kept.archived_at is None
    assert kept.in_book is True


async def test_eliminare_il_pasto_d_origine_lascia_l_avanzo_senza_legame(db_session):
    origin = await create_meal(db_session, day=d(10), slot=D, dish="Lasagne")
    left = await create_meal(
        db_session, day=d(11), slot=L, dish="Lasagne di ieri", leftover_of_id=origin.id
    )
    await delete_meal(db_session, origin)
    again = await get_meal(db_session, left.id)
    assert again is not None
    assert again.leftover_of_id is None
    assert again.dish == "Lasagne di ieri"


async def test_la_copia_e_una_ricetta_nuova_fuori_dal_ricettario(db_session, frittata):
    m = await create_meal(db_session, day=d(10), slot=D, dish="Frittata")
    copy = await copy_recipe_to_meal(db_session, m, frittata)
    copy = await get_recipe(db_session, copy.id)
    await db_session.refresh(copy)
    src = await get_recipe(db_session, frittata.id)
    assert copy.id != src.id
    assert copy.in_book is False
    assert copy.source == "manual"
    assert copy.source_ref is None
    assert copy.derived_from_id is None
    for field in (
        "title", "description", "instructions", "servings", "category", "cost", "image_url",
        "prep_minutes", "cook_minutes",
    ):
        assert getattr(copy, field) == getattr(src, field)
    assert list(copy.embedding) == list(src.embedding)

    def lines(r):
        return sorted(
            (str(i.ingredient_id), i.role, i.quantity_text, i.note, i.quantity_value)
            for i in r.ingredients
        )

    assert lines(copy) == lines(src)
    assert (await get_meal(db_session, m.id)).recipe_id == copy.id


async def test_la_copia_non_tocca_l_originale(db_session, frittata):
    m = await create_meal(db_session, day=d(10), slot=D, dish="Frittata")
    before = sorted(
        (str(i.ingredient_id), i.role, i.quantity_text, i.note)
        for i in (await get_recipe(db_session, frittata.id)).ingredients
    )
    await copy_recipe_to_meal(db_session, m, frittata)
    src = await get_recipe(db_session, frittata.id)
    await db_session.refresh(src)
    after = sorted(
        (str(i.ingredient_id), i.role, i.quantity_text, i.note) for i in src.ingredients
    )
    assert after == before
    assert src.in_book is True
    assert await meal_of_recipe(db_session, src.id) is None


async def test_non_si_copia_una_ricetta_eliminata(db_session, frittata):
    m = await create_meal(db_session, day=d(10), slot=D, dish="Frittata")
    frittata.archived_at = datetime.now(UTC)
    await db_session.flush()
    with pytest.raises(MealRefusal) as exc:
        await copy_recipe_to_meal(db_session, m, frittata)
    assert exc.value.code == MealRefusalCode.RECIPE_ARCHIVED
    assert (await get_meal(db_session, m.id)).recipe_id is None


@pytest.mark.parametrize(
    ("case", "code", "message"),
    [
        ("has", MealRefusalCode.HAS_RECIPE, "Il pasto ha già una ricetta."),
        (
            "leftover", MealRefusalCode.NO_RECIPE_HERE,
            "Un avanzo usa la ricetta del pasto da cui viene.",
        ),
        ("away", MealRefusalCode.NO_RECIPE_HERE, "Un pasto fuori casa non ha una ricetta."),
        (
            "draft", MealRefusalCode.NO_RECIPE_HERE,
            "È una bozza: la ricetta arriva quando diventa ufficiale.",
        ),
    ],
)
async def test_chi_non_puo_ricevere_una_ricetta(db_session, frittata, case, code, message):
    if case == "has":
        m = await create_meal(db_session, day=d(10), slot=D, dish="Frittata")
        await copy_recipe_to_meal(db_session, m, frittata)
    elif case == "leftover":
        o = await create_meal(db_session, day=d(9), slot=D, dish="Base")
        m = await create_meal(db_session, day=d(10), slot=D, dish="Avanzo", leftover_of_id=o.id)
    elif case == "away":
        m = await create_meal(db_session, day=d(10), slot=D, dish="Fuori", away=True)
    else:
        m = await create_meal(db_session, day=d(10), slot=D, dish="Idea", status=MealStatus.DRAFT)
    with pytest.raises(MealRefusal) as exc:
        await copy_recipe_to_meal(db_session, m, frittata)
    assert exc.value.code == code
    assert exc.value.message == message
    with pytest.raises(MealRefusal):
        check_can_take_recipe(m)
    with pytest.raises(MealRefusal):
        await link_recipe(db_session, m, frittata)


async def test_gli_avanzi_possibili(db_session):
    await create_meal(db_session, day=d(7), slot=D, dish="Fuori finestra")
    nine = await create_meal(db_session, day=d(9), slot=D, dish="Nove")
    await create_meal(db_session, day=d(10), slot=L, dish="Fuori", away=True)
    await create_meal(db_session, day=d(10), slot=D, dish="Avanzo", leftover_of_id=nine.id)
    eleven = await create_meal(db_session, day=d(11), slot=L, dish="Undici")
    got = await leftover_candidates(db_session, d(11), D)
    assert [m.id for m in got] == [eleven.id, nine.id]


async def test_meals_between_in_ordine(db_session):
    a = await create_meal(db_session, day=d(10), slot=D, dish="a")
    b = await create_meal(db_session, day=d(11), slot=L, dish="b")
    c = await create_meal(db_session, day=d(10), slot=L, dish="c")
    await create_meal(db_session, day=d(17), slot=D, dish="fuori")
    got = await meals_between(db_session, d(10), d(16))
    assert [m.id for m in got] == [c.id, a.id, b.id]


async def test_le_scritture_restituiscono_un_pasto_serializzabile(db_session, frittata):
    # ruling A-R1: `recipe` e `leftover_of` sono lazy="raise"
    origin = await create_meal(db_session, day=d(9), slot=D, dish="Base")
    copy = await copy_recipe_to_meal(
        db_session, await create_meal(db_session, day=d(10), slot=D, dish="F"), frittata
    )
    created = await create_meal(
        db_session, day=d(11), slot=L, dish="Avanzo", leftover_of_id=origin.id
    )
    assert created.recipe is None
    assert created.leftover_of.id == origin.id
    moved = await update_meal(db_session, created, {"dish": "Avanzo 2"})
    assert moved.recipe is None and moved.leftover_of.id == origin.id
    # il pasto che riceve la copia ha `recipe` caricata sull'oggetto che chi chiama ha in mano
    m2 = await create_meal(db_session, day=d(12), slot=D, dish="G")
    got = await copy_recipe_to_meal(db_session, m2, frittata)
    assert m2.recipe.id == got.id
    assert copy.id != got.id


async def test_release_recipe_fuori_dal_ricettario_archivia(db_session, frittata):
    m = await create_meal(db_session, day=d(10), slot=D, dish="F")
    copy = await with_copy(db_session, frittata, m)
    await release_recipe(db_session, m)
    assert (await get_meal(db_session, m.id)).recipe_id is None
    assert (await fresh(db_session, copy.id)).archived_at is not None
    rows = (await db_session.execute(select(Meal))).scalars().all()
    assert len(rows) == 1

