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
    piscina — e in quale ordine — non è definito. `Recipe.id.desc()` come secondo
    criterio lo impedisce: a `created_at` pari, la piscina è sempre le cento righe
    con l'id più grande, in ordine decrescente di id.

    L'attesa è calcolata qui dagli id delle ricette appena creati, non da una
    seconda chiamata a `search_recipes`: confrontare due letture della stessa
    tabella immutata, nella stessa transazione, non dimostra nulla — passerebbe
    comunque, spareggio o non spareggio, perché niente cambia fra le due letture.
    """
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import CANDIDATE_POOL, search_recipes

    ingrediente = Ingredient(
        name="farina", display_name="Farina", category=IngredientCategory.CEREALI
    )
    db_session.add(ingrediente)
    await db_session.flush()

    # stesso titolo per tutte: il riordinamento finale di search_recipes è per
    # (missing, -score, title), e qui missing e score pareggiano già (nessuna ha
    # "farina" in dispensa, il punteggio RRF è 0.0 per tutte senza parole cercate).
    # Con anche il titolo in parità non resta nulla su cui il sort possa rimescolare
    # l'ordine arrivato dalla query: il sort di Python è stabile, quindi l'ordine dei
    # risultati è l'ordine della query, ed è proprio quell'ordine che il test vuole
    # verificare.
    #
    # nessun `created_at` assegnato a mano: tutte restano sul server_default, che
    # dentro questa stessa transazione è lo stesso istante per ogni riga.
    creati = [
        await create_recipe(
            db_session, title="Impasto", description="Pane",
            instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
            ingredients=[(ingrediente.id, "primary", "500 g", None)], embedding=None,
        )
        for _ in range(CANDIDATE_POOL + 5)
    ]
    await db_session.flush()

    # calcolato dagli id creati, non dalla funzione sotto test: con `created_at`
    # tutti pari, le cento righe che la piscina deve contenere sono per definizione
    # le cento con l'id più grande, in ordine decrescente.
    attesi = sorted((recipe.id for recipe in creati), reverse=True)[:CANDIDATE_POOL]

    risultati = await search_recipes(db_session, limit=CANDIDATE_POOL)

    assert [r.recipe.id for r in risultati] == attesi


async def test_il_filtro_per_ingrediente_sceglie_in_sql(db_session):
    """Sesta lezione di CLAUDE.md: un filtro dietro a un limite guarda un campione.

    Con il catalogo intero, filtrare dopo aver preso le cento più recenti
    risponderebbe «con il pomodoro non ci fai niente» solo perché le ricette col
    pomodoro sono più vecchie di ieri.
    """
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import CANDIDATE_POOL, search_recipes

    pomodoro = Ingredient(
        name="pomodoro", display_name="Pomodoro", category=IngredientCategory.VERDURA
    )
    farina = Ingredient(
        name="farina", display_name="Farina", category=IngredientCategory.CEREALI
    )
    db_session.add_all([pomodoro, farina])
    await db_session.flush()

    voluta = await create_recipe(
        db_session, title="Pomodori al riso", description="Con il pomodoro",
        instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
        ingredients=[(pomodoro.id, "primary", "6", None)], embedding=None,
    )
    assert voluta is not None
    for numero in range(CANDIDATE_POOL + 5):
        await create_recipe(
            db_session, title=f"Pane {numero}", description="Senza pomodoro",
            instructions="Inforna.", servings=2, source="dataset", source_ref=None,
            ingredients=[(farina.id, "primary", "500 g", None)], embedding=None,
        )
    await db_session.flush()

    risultati = await search_recipes(db_session, ingredient_ids=[pomodoro.id])

    assert [r.recipe.title for r in risultati] == ["Pomodori al riso"]


async def test_un_ingrediente_secondario_fa_trovare_la_ricetta(db_session):
    """«Contiene» vuol dire contiene, qualunque sia il ruolo.

    Fino al 2026-09-17 questo filtro guardava solo i principali, e la ragione era
    buona per la domanda di allora: si chiamava «cosa hai in casa», cioè «ho questo,
    cosa ci faccio», e un secondario non caratterizza il piatto — «cosa faccio col
    sale» non è una domanda, e accettarlo avrebbe risposto «tutto».

    La domanda di oggi è un'altra: il filtro si chiama «contiene ingredienti» e si
    combina. Chi chiede le ricette col sale le vuole davvero tutte, e per restringere
    aggiunge il secondo ingrediente invece di sperare in un ruolo che non ha scelto
    lui. Con questa domanda escludere i secondari nasconderebbe ricette che
    quell'ingrediente ce l'hanno eccome: è una risposta sbagliata, non una prudenza.
    """
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import search_recipes

    sale = Ingredient(name="sale", display_name="Sale", category=IngredientCategory.CONDIMENTI)
    pasta = Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    db_session.add_all([sale, pasta])
    await db_session.flush()

    await create_recipe(
        db_session, title="Pasta in bianco", description="Solo pasta",
        instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
        ingredients=[(pasta.id, "primary", "320 g", None), (sale.id, "secondary", "q.b.", None)],
        embedding=None,
    )
    await db_session.flush()

    assert [r.recipe.title for r in await search_recipes(db_session, ingredient_ids=[sale.id])] == [
        "Pasta in bianco"
    ]
    assert [
        r.recipe.title for r in await search_recipes(db_session, ingredient_ids=[pasta.id])
    ] == ["Pasta in bianco"]


async def test_piu_ingredienti_devono_esserci_tutti(db_session):
    """Il plurale è una congiunzione, non un elenco di alternative.

    Chi sceglie due ingredienti sta restringendo: una ricetta che ne ha uno solo è
    esattamente ciò che il secondo ingrediente serve a togliere di mezzo. Con l'OR il
    secondo tocco allargherebbe l'elenco invece di stringerlo, cioè farebbe il
    contrario di quello che il gesto promette.
    """
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import search_recipes

    pomodoro = Ingredient(
        name="pomodoro", display_name="Pomodoro", category=IngredientCategory.VERDURA
    )
    basilico = Ingredient(
        name="basilico", display_name="Basilico", category=IngredientCategory.VERDURA
    )
    pasta = Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    db_session.add_all([pomodoro, basilico, pasta])
    await db_session.flush()

    await create_recipe(
        db_session, title="Pasta al pomodoro e basilico", description="D'estate",
        instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
        ingredients=[
            (pasta.id, "primary", "320 g", None),
            (pomodoro.id, "primary", "6", None),
            # secondario di proposito: il filtro chiede che ci sia, non che comandi
            (basilico.id, "secondary", "q.b.", None),
        ],
        embedding=None,
    )
    await create_recipe(
        db_session, title="Pasta al pomodoro", description="Di sempre",
        instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
        ingredients=[(pasta.id, "primary", "320 g", None), (pomodoro.id, "primary", "6", None)],
        embedding=None,
    )
    await create_recipe(
        db_session, title="Pesto", description="Al mortaio",
        instructions="Pesta.", servings=2, source="dataset", source_ref=None,
        ingredients=[(basilico.id, "primary", "50 g", None)], embedding=None,
    )
    await db_session.flush()

    risultati = await search_recipes(db_session, ingredient_ids=[pomodoro.id, basilico.id])

    assert [r.recipe.title for r in risultati] == ["Pasta al pomodoro e basilico"]
