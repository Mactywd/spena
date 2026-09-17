import json
import sys
from pathlib import Path

import pytest

from sqlalchemy import select

from app.cli.seed import load_ingredients, load_recipes
from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.recipe import Recipe, RecipeIngredient

DATA = Path(__file__).parent.parent.parent / "data"


class _SessioneDiTest:
    """Sostituisce `SessionLocal` nel modulo del seme: `main()` apre "una sessione"
    e riceve invece quella della fixture `db_session`, dentro la stessa transazione
    annullata a fine test. Non la chiude in `__aexit__`: la chiude la fixture.
    """

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


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
    assert loaded.created >= 20
    # con un fornitore funzionante nessuna ricetta resta senza vettore: è il numero
    # che il comando stampa, e che distingue un ricettario sano da uno senza vettori
    assert loaded.without_embedding == 0

    aliases = list((await db_session.execute(select(IngredientAlias))).scalars())
    assert len(aliases) > 0

    lines = list((await db_session.execute(select(RecipeIngredient))).scalars())
    assert {line.role for line in lines} == {"primary", "secondary"}

    recipes = list((await db_session.execute(select(Recipe))).scalars())
    assert all(r.source == "dataset" for r in recipes)


async def test_main_con_solo_ingredienti_non_ricarica_le_ricette(db_session, monkeypatch):
    """`main()` è la funzione vera invocata in produzione, non solo `load_ingredients`
    e `load_recipes` chiamate a mano: nessun test la eseguiva, e decide se le
    ricette vengono ricaricate su una macchina vera. `SessionLocal` viene sostituita
    con la sessione di test, `sys.argv` con l'invocazione reale da riga di comando.
    """
    from app.cli import seed as modulo_seme

    monkeypatch.setattr(modulo_seme, "SessionLocal", lambda: _SessioneDiTest(db_session))
    monkeypatch.setattr(sys, "argv", ["app.cli.seed", "--solo-ingredienti"])

    await modulo_seme.main()

    ingredients = list((await db_session.execute(select(Ingredient))).scalars())
    recipes = list((await db_session.execute(select(Recipe))).scalars())
    assert len(ingredients) > 0
    assert recipes == [], "con --solo-ingredienti le ricette non devono entrare"


async def test_main_senza_flag_carica_anche_le_ricette(db_session, monkeypatch):
    """Il gemello del test sopra: senza il flag, il seme resta comportarsi come
    prima, ricette comprese."""
    from app.cli import seed as modulo_seme

    monkeypatch.setattr(modulo_seme, "SessionLocal", lambda: _SessioneDiTest(db_session))
    monkeypatch.setattr(sys, "argv", ["app.cli.seed"])

    await modulo_seme.main()

    ingredients = list((await db_session.execute(select(Ingredient))).scalars())
    recipes = list((await db_session.execute(select(Recipe))).scalars())
    assert len(ingredients) > 0
    assert len(recipes) > 0


async def test_il_seme_conta_e_annuncia_le_ricette_salvate_senza_vettore(
    db_session, monkeypatch, caplog
):
    """Con il fornitore guasto le ricette entrano comunque, ma il numero si deve vedere.

    È il caso vero di un'immagine senza sentence-transformers: prima il comando
    stampava soltanto «caricati 169 ingredienti e 26 ricette», identico a una semina
    sana, e l'unico modo di scoprire i vettori mancanti era cercare invano.
    """
    import logging

    from app.cli import seed as modulo_seme
    from app.services import embeddings
    from app.services.embeddings import EmbeddingUnavailable

    class FornitoreGuasto:
        async def embed_query(self, text: str):
            raise EmbeddingUnavailable("sentence-transformers non installato")

        async def embed_passages(self, texts: list[str]):
            raise EmbeddingUnavailable("sentence-transformers non installato")

    monkeypatch.setattr(modulo_seme, "get_embedding_provider", lambda: FornitoreGuasto())
    monkeypatch.setattr(embeddings, "_degradation_logged", False)

    await load_ingredients(db_session, DATA / "ingredients_seed.json")
    with caplog.at_level(logging.WARNING):
        loaded = await load_recipes(db_session, DATA / "recipes_seed.json")

    assert loaded.created >= 20
    assert loaded.without_embedding == loaded.created

    salvate = list((await db_session.execute(select(Recipe))).scalars())
    assert len(salvate) == loaded.created, "la ricetta vale anche senza vettore"
    assert all(r.embedding is None for r in salvate)

    assert any("INSTALL_EMBEDDINGS=1" in r.getMessage() for r in caplog.records)


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
    ricerca la semina dentro il container moriva con FileNotFoundError.
    """
    from app.cli.seed import INGREDIENTS_FILE, find_data_dir

    mounted = tmp_path / "data"
    mounted.mkdir(parents=True)
    (mounted / INGREDIENTS_FILE).write_text("[]")

    assert find_data_dir((tmp_path / "non-esiste", mounted)) == mounted


def test_un_seme_assente_dice_cosa_manca_e_come_rimediare(tmp_path):
    from app.cli.seed import find_data_dir

    with pytest.raises(FileNotFoundError) as failure:
        find_data_dir((tmp_path / "vuota",))
    message = str(failure.value)
    # Il bersaglio del montaggio, non solo la parola «data»: il messaggio e i file
    # Compose devono restare d'accordo, ed è l'unica cosa che chi semina ha in mano.
    assert "./data:/data" in message, "il messaggio deve dire dove va montata data/"
    assert "docker-compose" in message


def test_il_seme_porta_i_non_alimentari():
    from app.domain.rules import NON_FOOD_CATEGORIES

    voci = json.loads((DATA / "ingredients_seed.json").read_text())
    non_alimentari = [v for v in voci if v["category"] in NON_FOOD_CATEGORIES]

    assert len(non_alimentari) >= 18
    nomi = {v["name"] for v in non_alimentari}
    assert {"detersivo per i piatti", "carta igienica", "sacchi per la spazzatura"} <= nomi


async def test_il_seme_scrive_il_kind_corretto_nel_database(db_session):
    """`load_ingredients` costruisce `Ingredient(...)` a mano: nessun test finora
    rileggeva `.kind` da un ingrediente caricato così, quindi se il validator
    `_deduce_kind` smettesse di scattare proprio su questa via, questo test se
    ne accorgerebbe da solo, mentre gli altri due test del seme (che leggono
    solo il file JSON) resterebbero verdi lo stesso.

    Rilegge davvero dal database con una `select` nuova, non si fida
    dell'oggetto Python già in mano, che potrebbe non riflettere quanto scritto.
    """
    from app.domain.rules import IngredientKind

    await load_ingredients(db_session, DATA / "ingredients_seed.json")

    non_alimentare = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "candeggina"))
    ).scalar_one()
    assert non_alimentare.kind == IngredientKind.NON_FOOD

    alimentare = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "pomodoro"))
    ).scalar_one()
    assert alimentare.kind == IngredientKind.FOOD


def test_nessun_alias_del_seme_e_ripetuto_fra_due_voci():
    """L'invariante che `remember_alias` difende a runtime — «un alias già preso da
    un altro ingrediente non si ruba» — ma il seme scrive gli alias direttamente,
    senza passare di lì. Due voci che rispondono alla stessa parola sono un
    autocomplete che dà due risposte a una domanda sola.
    """
    import collections

    voci = json.loads((DATA / "ingredients_seed.json").read_text())
    conteggio = collections.Counter(
        alias for voce in voci for alias in voce.get("aliases", [])
    )
    ripetuti = {alias: n for alias, n in conteggio.items() if n > 1}

    assert ripetuti == {}, f"alias su più voci: {ripetuti}"
