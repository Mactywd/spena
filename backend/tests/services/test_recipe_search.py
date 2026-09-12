import uuid

from app.services.recipe_search import reciprocal_rank_fusion


def test_fusion_rewards_agreement_between_the_two_rankings():
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    # a è secondo in entrambe, b è primo solo nella prima, c solo nella seconda
    scores = reciprocal_rank_fusion([[b, a], [c, a]])
    assert scores[a] > scores[b]
    assert scores[a] > scores[c]


def test_fusion_handles_an_empty_ranking():
    a = uuid.uuid4()
    scores = reciprocal_rank_fusion([[a], []])
    assert set(scores) == {a}


def test_fusion_of_nothing_is_empty():
    assert reciprocal_rank_fusion([[], []]) == {}


async def test_solo_cucinabili_vede_oltre_la_piscina_dei_candidati(db_session):
    """Con più ricette della piscina, il filtro non deve guardare solo le recenti.

    È il difetto che l'import avrebbe introdotto: centinaia di ricette nuove spingono
    fuori dalle cento più recenti proprio quelle che si possono cucinare, e la
    domanda centrale dell'app risponde «niente».
    """
    from datetime import UTC, datetime, timedelta

    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.db.models.pantry import PantryItem
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import CANDIDATE_POOL, search_recipes

    ho = Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    non_ho = Ingredient(
        name="bottarga", display_name="Bottarga", category=IngredientCategory.PESCE
    )
    db_session.add_all([ho, non_ho])
    await db_session.flush()
    db_session.add(PantryItem(ingredient_id=ho.id, status="available"))
    await db_session.flush()

    # `created_at` ha `server_default=func.now()`, e Postgres vede lo stesso istante
    # per tutta la transazione del test (vedi conftest): senza assegnarlo a mano, le
    # 106 righe sotto avrebbero tutte lo stesso `created_at`, e quale entra nei cento
    # più recenti sarebbe deciso dall'ordine di scansione, non dalla logica sotto
    # test. Valori distinti e la cucinabile indiscutibilmente la più vecchia
    # eliminano il caso: la cucinabile è la più vecchia di tutte e le ricette di
    # scarto sono tutte più recenti di lei, una per ciascun secondo successivo.
    adesso = datetime.now(UTC)
    pasta_in_bianco = await create_recipe(
        db_session, title="Pasta in bianco", description="Solo pasta",
        instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
        ingredients=[(ho.id, "primary", "320 g", None)], embedding=None,
    )
    pasta_in_bianco.created_at = adesso - timedelta(seconds=CANDIDATE_POOL + 10)
    for numero in range(CANDIDATE_POOL + 5):
        bottarga = await create_recipe(
            db_session, title=f"Bottarga {numero}", description="Non la hai",
            instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
            ingredients=[(non_ho.id, "primary", "20 g", None)], embedding=None,
        )
        bottarga.created_at = adesso + timedelta(seconds=numero)
    await db_session.flush()

    risultati = await search_recipes(db_session, only_cookable=True)

    assert [r.recipe.title for r in risultati] == ["Pasta in bianco"]


async def test_il_filtro_per_categoria_sceglie_in_sql(db_session):
    """Filtrare dopo il limite significherebbe filtrare dentro un campione."""
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import CANDIDATE_POOL, search_recipes

    ingrediente = Ingredient(
        name="zucchero", display_name="Zucchero", category=IngredientCategory.DOLCI
    )
    db_session.add(ingrediente)
    await db_session.flush()

    dolce = await create_recipe(
        db_session, title="Tiramisù", description="Dolce", instructions="Monta.",
        servings=6, source="dataset", source_ref=None,
        ingredients=[(ingrediente.id, "primary", "100 g", None)], embedding=None,
    )
    dolce.category = "Dolci e Desserts"
    for numero in range(CANDIDATE_POOL + 5):
        primo = await create_recipe(
            db_session, title=f"Primo {numero}", description="Salato",
            instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
            ingredients=[(ingrediente.id, "primary", "1 g", None)], embedding=None,
        )
        primo.category = "Primi piatti"
    await db_session.flush()

    risultati = await search_recipes(db_session, category="Dolci e Desserts")

    assert [r.recipe.title for r in risultati] == ["Tiramisù"]


async def test_senza_parole_la_piscina_dei_candidati_e_stabile(db_session):
    """Un import in blocco scrive centinaia di righe nella stessa transazione, con lo
    stesso `created_at` (il `server_default=func.now()` è costante per tutta la
    transazione). Senza una chiave di spareggio, quali cento righe entrano nella
    piscina — e in quale ordine — non è definito: due richieste identiche potrebbero
    vedere ricettari diversi. `Recipe.id.desc()` come secondo criterio lo impedisce.
    """
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import CANDIDATE_POOL, search_recipes

    ingrediente = Ingredient(
        name="farina", display_name="Farina", category=IngredientCategory.CEREALI
    )
    db_session.add(ingrediente)
    await db_session.flush()

    # nessun `created_at` assegnato a mano: tutte restano sul server_default, che
    # dentro questa stessa transazione è lo stesso istante per ogni riga.
    for numero in range(CANDIDATE_POOL + 5):
        await create_recipe(
            db_session, title=f"Impasto {numero:03d}", description="Pane",
            instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
            ingredients=[(ingrediente.id, "primary", "500 g", None)], embedding=None,
        )
    await db_session.flush()

    prima = await search_recipes(db_session)
    seconda = await search_recipes(db_session)

    assert len(prima) > 0
    assert [r.recipe.id for r in prima] == [r.recipe.id for r in seconda]
