import json
from pathlib import Path

import pytest

from sqlalchemy import select

from app.cli.seed import load_ingredients, load_recipes
from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.recipe import Recipe, RecipeIngredient

DATA = Path(__file__).parent.parent.parent / "data"


def test_seed_files_are_valid_and_substantial():
    ingredients = json.loads((DATA / "ingredients_seed.json").read_text())
    recipes = json.loads((DATA / "recipes_seed.json").read_text())
    assert len(ingredients) >= 120, "un'anagrafica povera rende l'autocomplete inutile"
    assert len(recipes) >= 20, "un ricettario vuoto fa sembrare l'app rotta"


def test_every_seed_category_is_a_known_one():
    ingredients = json.loads((DATA / "ingredients_seed.json").read_text())
    known = {c.value for c in IngredientCategory}
    assert {i["category"] for i in ingredients} <= known


def test_every_recipe_ingredient_exists_in_the_registry():
    """Un nome che non esiste in anagrafica farebbe fallire il caricamento."""
    ingredients = json.loads((DATA / "ingredients_seed.json").read_text())
    recipes = json.loads((DATA / "recipes_seed.json").read_text())
    names = {i["name"] for i in ingredients}
    for recipe in recipes:
        for line in recipe["ingredients"]:
            assert line["name"] in names, f"{line['name']} manca dall'anagrafica"


def test_every_recipe_has_at_least_one_primary_ingredient():
    recipes = json.loads((DATA / "recipes_seed.json").read_text())
    for recipe in recipes:
        roles = {line["role"] for line in recipe["ingredients"]}
        assert "primary" in roles, f"{recipe['title']} non ha ingredienti principali"


async def test_loading_is_idempotent(db_session):
    first = await load_ingredients(db_session, DATA / "ingredients_seed.json")
    second = await load_ingredients(db_session, DATA / "ingredients_seed.json")
    assert first > 0
    assert second == 0, "ricaricare non deve duplicare"

    total = len(list((await db_session.execute(select(Ingredient))).scalars()))
    assert total == first


async def test_recipes_load_with_roles_and_aliases(db_session):
    await load_ingredients(db_session, DATA / "ingredients_seed.json")
    loaded = await load_recipes(db_session, DATA / "recipes_seed.json")
    assert loaded >= 20

    aliases = list((await db_session.execute(select(IngredientAlias))).scalars())
    assert len(aliases) > 0

    lines = list((await db_session.execute(select(RecipeIngredient))).scalars())
    assert {line.role for line in lines} == {"primary", "secondary"}

    recipes = list((await db_session.execute(select(Recipe))).scalars())
    assert all(r.source == "dataset" for r in recipes)


def test_il_seme_si_trova_nella_radice_del_repository():
    """Fuori dal container vince il primo candidato, cioè il layout della spec."""
    from app.cli.seed import CANDIDATE_DATA_DIRS, INGREDIENTS_FILE, RECIPES_FILE, find_data_dir

    found = find_data_dir()
    assert found == CANDIDATE_DATA_DIRS[0]
    assert (found / INGREDIENTS_FILE).is_file()
    assert (found / RECIPES_FILE).is_file()


def test_il_seme_si_trova_anche_nel_montaggio_del_container(tmp_path):
    """Dentro Docker l'immagine contiene solo backend/: data/ arriva montata.

    Il primo candidato (la radice del repository) lì non esiste, e prima di questa
    ricerca la semina dentro il container moriva con FileNotFoundError su «/data».
    """
    from app.cli.seed import INGREDIENTS_FILE, find_data_dir

    mounted = tmp_path / "app" / "data"
    mounted.mkdir(parents=True)
    (mounted / INGREDIENTS_FILE).write_text("[]")

    assert find_data_dir((tmp_path / "non-esiste", mounted)) == mounted


def test_un_seme_assente_dice_cosa_manca_e_come_rimediare(tmp_path):
    from app.cli.seed import find_data_dir

    with pytest.raises(FileNotFoundError) as failure:
        find_data_dir((tmp_path / "vuota",))
    message = str(failure.value)
    assert "/app/data" in message, "il messaggio deve dire dove va montata data/"
    assert "docker-compose" in message
