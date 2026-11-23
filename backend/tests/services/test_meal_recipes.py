import uuid
from datetime import UTC, date, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe
from app.db.models.recipe_change import RecipeChange
from app.domain.meals import MealSlot, MealStatus
from app.repositories.recipes import get_recipe, write_recipe_ingredients
from app.services.meal_recipes import (
    CREATE_ONLY_MESSAGE,
    MEAL_GONE_MESSAGE,
    UNSET,
    ChangeRefusal,
    ChangeRefusalCode,
    DraftLine,
    MealRecipeDraft,
    STALE_WRITE_MESSAGE,
    RecipeWriteRefused,
    change_is_undoable,
    meal_snapshot,
    undo_recipe_change,
    undoable_change_ids,
    untouched_ai_change,
    write_meal_recipe,
)
from app.services.meals import MealRefusal, MealRefusalCode, copy_recipe_to_meal, create_meal
from app.services.registry import merge_ingredients
from app.services.change_cards import (
    ListProposal,
    RowOverride,
    apply_card,
    discard_card,
    get_card,
    propose_card,
)

DAY = date(2026, 11, 11)


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
        "detersivo": Ingredient(
            name="detersivo", display_name="Detersivo", category=IngredientCategory.CASA
        ),
    }
    db_session.add_all(rows.values())
    await db_session.flush()
    return rows


@pytest_asyncio.fixture
async def meal(db_session, voci):
    return await create_meal(
        db_session, day=DAY, slot=MealSlot.DINNER, dish="Frittata", sides="insalata"
    )


def line(ingredient, role="primary", text=None, note=None):
    return DraftLine(
        ingredient_id=ingredient.id, name=None, category=None,
        role=role, quantity_text=text, note=note,
    )


def named(name, category=None, role="primary", text=None):
    return DraftLine(
        ingredient_id=None, name=name, category=category, role=role,
        quantity_text=text, note=None,
    )


def draft(*lines, title="Frittata di spinaci", **extra):
    return MealRecipeDraft(
        title=title, description=None, instructions="Sbatti. Cuoci.", servings=1,
        lines=tuple(lines), summary="Frittata di spinaci", **extra,
    )


async def lines_of(session, meal):
    recipe = await get_recipe(session, meal.recipe_id)
    await session.refresh(recipe)
    return {ri.ingredient_id: ri for ri in recipe.ingredients}


async def test_scrive_da_zero_la_ricetta_di_un_pasto_senza_ricetta(db_session, voci, meal):
    change = await write_meal_recipe(
        db_session, meal,
        draft(line(voci["uova"], text="2"), line(voci["spinaci"], text="150 g")),
    )
    await db_session.flush()
    stored = await get_recipe(db_session, meal.recipe_id)
    assert stored.source == "ai" and stored.in_book is False and stored.servings == 1
    assert meal.recipe_id == stored.id == change.recipe_id
    rows = await lines_of(db_session, meal)
    assert rows[voci["spinaci"].id].quantity_value == 150
    assert change.created_recipe is True
    assert change.before["recipe"] is None


async def _two_writes(db_session, voci, meal):
    first = await write_meal_recipe(
        db_session, meal, draft(line(voci["uova"], text="2"), line(voci["spinaci"], text="200 g"))
    )
    second = await write_meal_recipe(
        db_session, meal,
        draft(
            line(voci["uova"], text="2"),
            line(voci["spinaci"], text="150 g", note="congelati"),
            dish="Frittata di spinaci", sides="pane",
        ),
    )
    await db_session.flush()
    return first, second


async def test_riscrive_la_ricetta_che_c_e_e_ricorda_quella_di_prima(db_session, voci, meal):
    _, second = await _two_writes(db_session, voci, meal)
    spin = str(voci["spinaci"].id)
    before = {x["ingredient_id"]: x for x in second.before["recipe"]["lines"]}
    after = {x["ingredient_id"]: x for x in second.after["recipe"]["lines"]}
    assert before[spin]["quantity_text"] == "200 g"
    assert after[spin]["quantity_text"] == "150 g"
    assert second.created_recipe is False
    assert second.changed["ingredient_ids"] == [spin]


async def test_cambia_piatto_e_accompagnamenti_ma_non_il_posto(db_session, voci, meal):
    await write_meal_recipe(
        db_session, meal,
        draft(line(voci["uova"]), dish="  Frittata di zucchine ", sides=None),
    )
    assert meal.dish == "Frittata di zucchine" and meal.sides is None
    assert meal.day == DAY and meal.slot == MealSlot.DINNER.value
    meal.sides = "pane"
    await write_meal_recipe(db_session, meal, draft(line(voci["uova"]), sides=UNSET))
    assert meal.sides == "pane"
    await write_meal_recipe(db_session, meal, draft(line(voci["uova"]), sides="  "))
    assert meal.sides is None


async def test_un_nome_nuovo_passa_dalla_strada_del_modulo(db_session, voci, meal):
    before = len((await db_session.execute(select(Ingredient))).scalars().all())
    await write_meal_recipe(
        db_session, meal,
        draft(named("Spinaci"), named("erba cipollina", IngredientCategory.VERDURA)),
    )
    rows = await lines_of(db_session, meal)
    assert voci["spinaci"].id in rows
    after = (await db_session.execute(select(Ingredient))).scalars().all()
    assert len(after) == before + 1
    assert any(i.name == "erba cipollina" for i in after)


@pytest.mark.parametrize("by_name", [False, True])
async def test_il_non_alimentare_si_rifiuta(db_session, voci, meal, by_name):
    bad = named("detersivo") if by_name else line(voci["detersivo"])
    with pytest.raises(RecipeWriteRefused) as caught:
        await write_meal_recipe(db_session, meal, draft(bad))
    assert "Detersivo" in caught.value.message and "non è un alimento" in caught.value.message
    await db_session.refresh(meal)
    assert meal.recipe_id is None


async def test_un_rifiuto_non_lascia_niente(db_session, voci, meal):
    first = await write_meal_recipe(db_session, meal, draft(line(voci["uova"], text="2")))
    await db_session.flush()
    snap = await meal_snapshot(db_session, meal)
    with pytest.raises(RecipeWriteRefused) as caught:
        await write_meal_recipe(
            db_session, meal,
            draft(
                named("erba cipollina", IngredientCategory.VERDURA),
                line(voci["uova"]), line(voci["uova"]), dish="Altro",
            ),
        )
    assert caught.value.message == (
        "Due righe puntano allo stesso ingrediente, Uova: tienine una."
    )
    names = (await db_session.execute(select(Ingredient.name))).scalars().all()
    assert "erba cipollina" not in names
    assert await meal_snapshot(db_session, meal) == snap
    changes = (await db_session.execute(select(RecipeChange))).scalars().all()
    assert [c.id for c in changes] == [first.id]


async def test_un_id_che_non_c_e_si_rifiuta(db_session, voci, meal):
    missing = uuid.uuid4()
    with pytest.raises(RecipeWriteRefused) as caught:
        await write_meal_recipe(
            db_session, meal,
            draft(DraftLine(missing, None, None, "primary", None, None)),
        )
    assert caught.value.message == (
        f"L'ingrediente {missing} non esiste: cercalo di nuovo con search_ingredients."
    )


@pytest.mark.parametrize("case", ["bozza", "fuori casa", "avanzo"])
async def test_chi_non_puo_avere_una_ricetta(db_session, voci, case):
    if case == "bozza":
        target = await create_meal(
            db_session, day=DAY, slot=MealSlot.LUNCH, dish="Pasta", status=MealStatus.DRAFT
        )
    elif case == "fuori casa":
        target = await create_meal(
            db_session, day=DAY, slot=MealSlot.LUNCH, dish="Pizza", away=True
        )
    else:
        origin = await create_meal(db_session, day=date(2026, 11, 9), slot=MealSlot.LUNCH, dish="Ragù")
        target = await create_meal(
            db_session, day=DAY, slot=MealSlot.LUNCH, dish="Ragù avanzato",
            leftover_of_id=origin.id,
        )
    expected = {
        "bozza": "È una bozza: la ricetta arriva quando diventa ufficiale.",
        "fuori casa": "Un pasto fuori casa non ha una ricetta.",
        "avanzo": "Un avanzo usa la ricetta del pasto da cui viene.",
    }[case]
    with pytest.raises(MealRefusal) as caught:
        await write_meal_recipe(db_session, target, draft(line(voci["uova"])))
    assert caught.value.code == MealRefusalCode.NO_RECIPE_HERE
    assert caught.value.message == expected
    assert (await db_session.execute(select(Recipe))).scalars().all() == []


async def test_annulla_rimette_la_versione_di_prima(db_session, voci, meal):
    first, second = await _two_writes(db_session, voci, meal)
    # il piatto cambiato dalla seconda scrittura torna com'era
    await undo_recipe_change(db_session, second)
    rows = await lines_of(db_session, meal)
    spin = rows[voci["spinaci"].id]
    assert spin.quantity_text == "200 g" and spin.note is None and spin.quantity_value == 200
    assert second.undone_at is not None
    assert meal.dish == "Frittata" and meal.sides == "insalata"


async def test_annulla_una_ricetta_scritta_da_zero_la_stacca_dal_pasto(db_session, voci, meal):
    change = await write_meal_recipe(db_session, meal, draft(line(voci["uova"])))
    await undo_recipe_change(db_session, change)
    assert meal.recipe_id is None
    recipe = await db_session.get(Recipe, change.recipe_id)
    await db_session.refresh(recipe)
    assert recipe.archived_at is not None


async def test_annulla_dopo_una_correzione_a_mano_si_rifiuta(
    db_session, logged_client, voci, meal
):
    change = await write_meal_recipe(db_session, meal, draft(line(voci["uova"], text="2")))
    await db_session.flush()
    risposta = await logged_client.put(
        f"/api/v1/recipes/{change.recipe_id}",
        json={
            "title": "Titolo corretto", "description": None, "category": None,
            "instructions": "Sbatti. Cuoci.", "servings": 1, "cost": None,
            "ingredients": [
                {"ingredient_id": str(voci["uova"].id), "role": "primary", "quantity_text": "2"}
            ],
        },
    )
    assert risposta.status_code == 200, risposta.text
    with pytest.raises(ChangeRefusal) as caught:
        await undo_recipe_change(db_session, change)
    assert caught.value.code == ChangeRefusalCode.STALE
    assert (await get_recipe(db_session, change.recipe_id)).title == "Titolo corretto"
    assert await change_is_undoable(db_session, change) is False


async def test_annulla_solo_l_ultima(db_session, voci, meal):
    first, second = await _two_writes(db_session, voci, meal)
    with pytest.raises(ChangeRefusal) as caught:
        await undo_recipe_change(db_session, first)
    assert caught.value.code == ChangeRefusalCode.STALE
    await undo_recipe_change(db_session, second)


async def test_annullare_due_volte(db_session, voci, meal):
    change = await write_meal_recipe(db_session, meal, draft(line(voci["uova"])))
    await undo_recipe_change(db_session, change)
    with pytest.raises(ChangeRefusal) as caught:
        await undo_recipe_change(db_session, change)
    assert caught.value.code == ChangeRefusalCode.ALREADY_UNDONE
    assert caught.value.message == "Questa modifica è già stata annullata."


async def test_annulla_con_un_ingrediente_sparito(db_session, voci, meal):
    await write_meal_recipe(
        db_session, meal, draft(line(voci["uova"]), line(voci["parmigiano"], text="30 g"))
    )
    change = await write_meal_recipe(db_session, meal, draft(line(voci["uova"])))
    await merge_ingredients(db_session, voci["parmigiano"].id, voci["spinaci"].id)
    before = await meal_snapshot(db_session, meal)
    with pytest.raises(ChangeRefusal) as caught:
        await undo_recipe_change(db_session, change)
    assert caught.value.code == ChangeRefusalCode.STALE
    assert caught.value.message == (
        "Un ingrediente della versione di prima non c'è più: correggi la ricetta dal modulo."
    )
    assert await meal_snapshot(db_session, meal) == before


async def test_un_nome_senza_reparto_e_sconosciuto_si_rifiuta(db_session, voci, meal):
    before = (await db_session.execute(select(Ingredient.name))).scalars().all()
    with pytest.raises(RecipeWriteRefused) as caught:
        await write_meal_recipe(db_session, meal, draft(line(voci["uova"]), named("carta forno")))
    assert caught.value.message == (
        "carta forno non è in anagrafica: per crearlo serve anche il reparto."
    )
    assert (await db_session.execute(select(Ingredient.name))).scalars().all() == before
    await db_session.refresh(meal)
    assert meal.recipe_id is None


async def test_una_nota_vuota_si_salva_come_none(db_session, voci, meal):
    await write_meal_recipe(db_session, meal, draft(line(voci["uova"], note="   ")))
    assert (await lines_of(db_session, meal))[voci["uova"].id].note is None


@pytest.mark.parametrize(
    "bad",
    [
        {"lines": "quantity_text"},
        {"servings": 0},
        {"servings": 51},
        {"title": "   "},
        {"instructions": ""},
        {"title": "x" * 201},
    ],
    ids=["dose lunga", "porzioni 0", "porzioni 51", "titolo vuoto", "procedimento vuoto",
         "titolo lungo"],
)
async def test_i_campi_fuori_regola_si_rifiutano(db_session, voci, meal, bad):
    import dataclasses

    base = draft(line(voci["uova"]))
    if "lines" in bad:
        base = draft(line(voci["uova"], text="x" * 101))
    else:
        base = dataclasses.replace(base, **bad)
    with pytest.raises(RecipeWriteRefused):
        await write_meal_recipe(db_session, meal, base)
    await db_session.refresh(meal)
    assert meal.recipe_id is None


async def test_la_ricetta_eliminata_si_rifiuta(db_session, voci, meal):
    from datetime import UTC, datetime

    change = await write_meal_recipe(db_session, meal, draft(line(voci["uova"])))
    recipe = await db_session.get(Recipe, change.recipe_id)
    recipe.archived_at = datetime.now(UTC)
    await db_session.flush()
    with pytest.raises(RecipeWriteRefused) as caught:
        await write_meal_recipe(db_session, meal, draft(line(voci["uova"])))
    assert caught.value.message == (
        "La ricetta di questo pasto è stata eliminata: Mattia deve ripristinarla prima."
    )


async def test_annulla_con_un_ingrediente_diventato_non_alimentare(db_session, voci, meal):
    await write_meal_recipe(
        db_session, meal, draft(line(voci["uova"]), line(voci["parmigiano"], text="30 g"))
    )
    change = await write_meal_recipe(db_session, meal, draft(line(voci["uova"])))
    voci["parmigiano"].category = IngredientCategory.CASA
    await db_session.flush()
    with pytest.raises(ChangeRefusal) as caught:
        await undo_recipe_change(db_session, change)
    assert caught.value.code == ChangeRefusalCode.STALE
    assert "non c'è più" in caught.value.message


async def test_un_errore_inatteso_nel_savepoint_lascia_il_pasto_leggibile(
    db_session, voci, meal, monkeypatch
):
    """Non solo i tre rifiuti: qualsiasi eccezione che annulla il SAVEPOINT scade il pasto,
    che si ricarica prima di risalire (un MissingGreenlet alla prima lettura, altrimenti)."""
    from app.services import meal_recipes

    original = meal_recipes.link_recipe

    async def link_poi_guasto(session, target, recipe):
        await original(session, target, recipe)
        await session.flush()
        raise RuntimeError("guasto del database")

    monkeypatch.setattr(meal_recipes, "link_recipe", link_poi_guasto)
    with pytest.raises(RuntimeError, match="guasto del database"):
        await write_meal_recipe(db_session, meal, draft(line(voci["uova"])))
    # letture sincrone: un oggetto scaduto qui alzerebbe MissingGreenlet
    assert meal.recipe_id is None
    assert meal.dish == "Frittata"


async def _correzione_a_mano(db_session, voci, meal, dose):
    recipe = await get_recipe(db_session, meal.recipe_id)
    await write_recipe_ingredients(
        db_session, recipe,
        [(voci["uova"].id, "primary", "2", None), (voci["spinaci"].id, "primary", dose, None)],
    )
    await db_session.flush()


async def _changes(db_session):
    return list((await db_session.execute(select(RecipeChange))).scalars().all())


async def test_una_scrittura_su_una_ricetta_cambiata_si_rifiuta(db_session, voci, meal):
    await write_meal_recipe(
        db_session, meal, draft(line(voci["uova"], text="2"), line(voci["spinaci"], text="200 g"))
    )
    seen = await meal_snapshot(db_session, meal)
    await _correzione_a_mano(db_session, voci, meal, "300 g")
    before = len(await _changes(db_session))
    with pytest.raises(RecipeWriteRefused) as caught:
        await write_meal_recipe(
            db_session, meal,
            draft(line(voci["uova"], text="2"), line(voci["spinaci"], text="150 g")),
            expected=seen,
        )
    assert caught.value.message == STALE_WRITE_MESSAGE
    assert (await lines_of(db_session, meal))[voci["spinaci"].id].quantity_text == "300 g"
    assert len(await _changes(db_session)) == before


async def test_con_l_istantanea_giusta_si_scrive(db_session, voci, meal):
    await write_meal_recipe(
        db_session, meal, draft(line(voci["uova"], text="2"), line(voci["spinaci"], text="200 g"))
    )
    seen = await meal_snapshot(db_session, meal)
    await write_meal_recipe(
        db_session, meal,
        draft(line(voci["uova"], text="2"), line(voci["spinaci"], text="150 g")),
        expected=seen,
    )
    assert (await lines_of(db_session, meal))[voci["spinaci"].id].quantity_text == "150 g"


# --- C6: «Annulla» toglie gli ingredienti creati da quella modifica --------------------


async def _with_new_ingredient(db_session, voci, meal):
    first = await write_meal_recipe(db_session, meal, draft(line(voci["uova"], text="2")))
    second = await write_meal_recipe(
        db_session, meal,
        draft(
            line(voci["uova"], text="2"),
            named("Spinaci novelli", IngredientCategory.VERDURA, text="100 g"),
        ),
    )
    await db_session.flush()
    novelli = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "spinaci novelli"))
    ).scalar_one()
    return first, second, novelli


async def _exists(db_session, ingredient_id) -> bool:
    return await db_session.get(Ingredient, ingredient_id) is not None


async def test_la_modifica_ricorda_gli_ingredienti_che_crea(db_session, voci, meal):
    change = await write_meal_recipe(
        db_session, meal,
        draft(
            named("Spinaci novelli", IngredientCategory.VERDURA),
            named("Spinaci"),  # lo aggancia a quello che c'è
        ),
    )
    novelli = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "spinaci novelli"))
    ).scalar_one()
    assert change.created_ingredient_ids == [str(novelli.id)]


async def test_annulla_toglie_l_ingrediente_creato(db_session, voci, meal):
    _, second, novelli = await _with_new_ingredient(db_session, voci, meal)
    novelli_id = novelli.id
    await undo_recipe_change(db_session, second)
    assert not await _exists(db_session, novelli_id)
    rows = await lines_of(db_session, meal)
    assert set(rows) == {voci["uova"].id}


@pytest.mark.parametrize("uso", ["ricetta", "dispensa"])
async def test_annulla_non_toglie_un_ingrediente_usato_altrove(db_session, voci, meal, uso):
    from app.db.models.pantry import PantryItem
    from app.db.models.recipe import RecipeSource
    from app.repositories.recipes import create_recipe

    _, second, novelli = await _with_new_ingredient(db_session, voci, meal)
    if uso == "ricetta":
        await create_recipe(
            db_session, title="Altra", description=None, instructions="Cuoci.", servings=1,
            source=RecipeSource.MANUAL, source_ref=None,
            ingredients=[(novelli.id, "primary", None, None)], embedding=None,
        )
    else:
        db_session.add(PantryItem(ingredient_id=novelli.id, status="available"))
    await db_session.flush()
    novelli_id = novelli.id
    await undo_recipe_change(db_session, second)
    assert second.undone_at is not None
    assert await _exists(db_session, novelli_id)


async def test_annulla_non_toglie_un_ingrediente_in_lista(db_session, voci, meal):
    from app.db.models.shopping import ShoppingListItem

    _, second, novelli = await _with_new_ingredient(db_session, voci, meal)
    db_session.add(
        ShoppingListItem(
            raw_text="Spinaci novelli", ingredient_id=novelli.id, status="pending",
            reason="manual",
        )
    )
    await db_session.flush()
    novelli_id = novelli.id
    await undo_recipe_change(db_session, second)
    assert second.undone_at is not None
    assert await _exists(db_session, novelli_id)


async def test_annullare_una_ricetta_scritta_lascia_gli_ingredienti_alla_ricetta_archiviata(
    db_session, voci, meal
):
    change = await write_meal_recipe(
        db_session, meal,
        draft(line(voci["uova"]), named("Spinaci novelli", IngredientCategory.VERDURA)),
    )
    assert change.created_recipe is True
    novelli = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "spinaci novelli"))
    ).scalar_one()
    novelli_id = novelli.id
    await undo_recipe_change(db_session, change)
    recipe = await db_session.get(Recipe, change.recipe_id)
    await db_session.refresh(recipe)
    assert recipe.archived_at is not None
    assert await _exists(db_session, novelli_id)


async def _three_writes(db_session, voci, meal):
    changes = []
    for grams in ("100 g", "150 g", "200 g"):
        changes.append(
            await write_meal_recipe(
                db_session, meal,
                draft(line(voci["uova"], text="2"), line(voci["spinaci"], text=grams)),
            )
        )
    await db_session.flush()
    return changes


async def test_undoable_change_ids(db_session, voci, meal):
    first, second, third = await _three_writes(db_session, voci, meal)
    everything = [first, second, third]
    assert await undoable_change_ids(db_session, everything) == {third.id}
    assert await undoable_change_ids(db_session, []) == set()

    await undo_recipe_change(db_session, third)
    # la ricetta è tornata com'è la ha lasciata la penultima
    assert await undoable_change_ids(db_session, everything) == {second.id}
    assert await change_is_undoable(db_session, second) is True
    assert await change_is_undoable(db_session, first) is False


async def test_undoable_change_ids_con_la_ricetta_archiviata(db_session, voci, meal):
    changes = await _three_writes(db_session, voci, meal)
    recipe = await db_session.get(Recipe, changes[0].recipe_id)
    recipe.archived_at = datetime.now(UTC)
    await db_session.flush()
    assert await undoable_change_ids(db_session, changes) == set()


async def test_solo_una_ricetta_nuova_rifiuta_quella_che_c_era_gia(db_session, voci, meal):
    """`allowed_recipe_ids` (i giri della coda): una ricetta che il giro non ha scritto non si
    riscrive, e il rifiuto arriva prima di ogni scrittura."""
    await write_meal_recipe(db_session, meal, draft(line(voci["uova"]), title="A mano"))
    before = await meal_snapshot(db_session, meal)
    changes = (await db_session.execute(select(RecipeChange))).scalars().all()

    with pytest.raises(RecipeWriteRefused) as caught:
        await write_meal_recipe(
            db_session, meal, draft(line(voci["spinaci"])), allowed_recipe_ids=frozenset({None})
        )
    assert caught.value.message == CREATE_ONLY_MESSAGE == (
        "Il pasto ha già una ricetta: non riscriverla."
    )
    assert await meal_snapshot(db_session, meal) == before
    assert (await db_session.execute(select(RecipeChange))).scalars().all() == changes


async def test_solo_una_ricetta_nuova_riscrive_la_sua(db_session, voci, meal):
    first = await write_meal_recipe(
        db_session, meal, draft(line(voci["uova"])), allowed_recipe_ids=frozenset({None})
    )
    await write_meal_recipe(
        db_session, meal, draft(line(voci["spinaci"]), title="Rifatta"),
        allowed_recipe_ids=frozenset({None, first.recipe_id}),
    )
    assert meal.recipe_id == first.recipe_id
    assert meal.recipe.title == "Rifatta"


async def test_il_pasto_sparito_non_si_scrive(db_session, voci, meal):
    recipes = (await db_session.execute(select(Recipe))).scalars().all()
    await db_session.delete(meal)
    await db_session.flush()
    with pytest.raises(RecipeWriteRefused) as caught:
        await write_meal_recipe(db_session, meal, draft(line(voci["uova"])))
    assert caught.value.message == MEAL_GONE_MESSAGE == "Il pasto non esiste più."
    assert (await db_session.execute(select(Recipe))).scalars().all() == recipes


async def _claude_wrote(db_session, voci, meal):
    return await write_meal_recipe(
        db_session, meal, draft(line(voci["uova"], text="2")),
        allowed_recipe_ids=frozenset({None}),
    )


async def test_la_ricetta_appena_scritta_da_claude_e_intatta(db_session, voci, meal):
    change = await _claude_wrote(db_session, voci, meal)
    await db_session.flush()
    found = await untouched_ai_change(db_session, meal)
    assert found is not None and found.id == change.id
    assert found.created_recipe is True


async def test_senza_ricetta_niente(db_session, voci, meal):
    assert await untouched_ai_change(db_session, meal) is None


async def test_toccata_dalla_chat_non_e_intatta(db_session, voci, meal):
    await _claude_wrote(db_session, voci, meal)
    await write_meal_recipe(
        db_session, meal, draft(line(voci["uova"], text="3"), line(voci["spinaci"], text="100 g"))
    )
    await db_session.flush()
    assert await untouched_ai_change(db_session, meal) is None


async def test_annullata_non_e_intatta(db_session, voci, meal):
    change = await _claude_wrote(db_session, voci, meal)
    await db_session.flush()
    await undo_recipe_change(db_session, change)
    await db_session.flush()
    assert await untouched_ai_change(db_session, meal) is None


async def test_corretta_a_mano_non_e_intatta(db_session, voci, meal):
    change = await _claude_wrote(db_session, voci, meal)
    await db_session.flush()
    recipe = await get_recipe(db_session, change.recipe_id)
    recipe.title = "Titolo corretto"
    await db_session.flush()
    assert await untouched_ai_change(db_session, meal) is None


async def test_nel_ricettario_non_e_intatta(db_session, voci, meal):
    change = await _claude_wrote(db_session, voci, meal)
    await db_session.flush()
    recipe = await get_recipe(db_session, change.recipe_id)
    recipe.in_book = True
    await db_session.flush()
    assert await untouched_ai_change(db_session, meal) is None


async def test_scelta_dal_ricettario_non_e_di_claude(db_session, voci, meal):
    source = Recipe(
        title="Dal libro", instructions="Cuoci.", servings=2, source="manual", in_book=True
    )
    db_session.add(source)
    await db_session.flush()
    await copy_recipe_to_meal(db_session, meal, source)
    await db_session.flush()
    assert await untouched_ai_change(db_session, meal) is None


async def test_annulla_non_toglie_un_ingrediente_di_una_scheda_proposta(db_session, voci, meal):
    _, second, novelli = await _with_new_ingredient(db_session, voci, meal)
    novelli_id = novelli.id
    card = await propose_card(
        db_session, meals=[meal], pantry=[],
        shopping=[ListProposal(novelli_id, "Spinaci novelli")],
    )
    await db_session.flush()
    await undo_recipe_change(db_session, second)
    assert await _exists(db_session, novelli_id)
    card = await get_card(db_session, card.id)
    assert [r.ingredient_id for r in card.rows] == [novelli_id]


@pytest.mark.parametrize("chiusa", ["applicata", "scartata", "superata"])
async def test_una_scheda_chiusa_non_tiene_l_ingrediente(db_session, voci, meal, chiusa):
    _, second, novelli = await _with_new_ingredient(db_session, voci, meal)
    novelli_id = novelli.id
    card = await propose_card(
        db_session, meals=[meal], pantry=[],
        shopping=[ListProposal(novelli_id, "Spinaci novelli")],
    )
    await db_session.flush()
    if chiusa == "applicata":
        riga = (await get_card(db_session, card.id)).rows[0]
        await apply_card(db_session, card.id, [RowOverride(riga.id, checked=False)])
    elif chiusa == "scartata":
        await discard_card(db_session, card.id)
    else:
        await propose_card(
            db_session, meals=[meal], pantry=[],
            shopping=[ListProposal(None, "Altro")],
        )
    await db_session.flush()
    await undo_recipe_change(db_session, second)
    assert not await _exists(db_session, novelli_id)
