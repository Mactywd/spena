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

    risultati = await search_recipes(db_session, max_missing=0)

    assert [r.recipe.title for r in risultati] == ["Pasta in bianco"]


async def test_una_soglia_oltre_lo_zero_vede_oltre_la_piscina(db_session):
    """Il gemello del test qui sopra, per una soglia diversa da zero.

    I due insieme chiudono la condizione da entrambi i lati, ed è il punto di tutto
    il lavoro: scritta `if not max_missing` la soglia zero ricadrebbe sotto il limite
    e lo direbbe il test di sopra; scritta `if max_missing == 0` ci cadrebbe la
    soglia uno, e lo dice solo questo.

    Le ricette di scarto ne hanno due di mancanti, non una: devono restare fuori dal
    filtro e non solo in fondo all'ordine.
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
    nemmeno = Ingredient(
        name="zafferano", display_name="Zafferano", category=IngredientCategory.SPEZIE
    )
    db_session.add_all([ho, non_ho, nemmeno])
    await db_session.flush()
    db_session.add(PantryItem(ingredient_id=ho.id, status="available"))
    await db_session.flush()

    # stessa costruzione del test di sopra: `created_at` assegnato a mano, e quella
    # che ci interessa indiscutibilmente la più vecchia di tutte
    adesso = datetime.now(UTC)
    quasi = await create_recipe(
        db_session, title="Pasta con la bottarga", description="Ne manca una",
        instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
        ingredients=[(ho.id, "primary", "320 g", None), (non_ho.id, "primary", "20 g", None)],
        embedding=None,
    )
    quasi.created_at = adesso - timedelta(seconds=CANDIDATE_POOL + 10)
    for numero in range(CANDIDATE_POOL + 5):
        scarto = await create_recipe(
            db_session, title=f"Introvabile {numero}", description="Ne mancano due",
            instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
            ingredients=[
                (non_ho.id, "primary", "20 g", None),
                (nemmeno.id, "primary", "1 bustina", None),
            ],
            embedding=None,
        )
        scarto.created_at = adesso + timedelta(seconds=numero)
    await db_session.flush()

    risultati = await search_recipes(db_session, max_missing=1)

    assert [r.recipe.title for r in risultati] == ["Pasta con la bottarga"]


async def test_max_missing_filtra_anche_sul_ramo_con_parole_cercate(db_session):
    """Il gemello dei due test sopra, sull'altro ramo di `search_recipes`.

    Tutti i test di `max_missing` fin qui passano dal ramo senza parole cercate.
    Il ramo con le parole applica lo stesso filtro sugli stessi candidati fusi da
    RRF, ma è quello che porta la limitazione dichiarata nel commento sopra
    `_containing_all` (i candidati sono la piscina, non tutto il ricettario) — ed
    era anche l'unico senza un solo test.
    """
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.db.models.pantry import PantryItem
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import search_recipes

    pasta = Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    pomodoro = Ingredient(
        name="pomodoro", display_name="Pomodoro", category=IngredientCategory.VERDURA
    )
    basilico = Ingredient(
        name="basilico", display_name="Basilico", category=IngredientCategory.VERDURA
    )
    db_session.add_all([pasta, pomodoro, basilico])
    await db_session.flush()
    db_session.add(PantryItem(ingredient_id=pasta.id, status="available"))
    await db_session.flush()

    quasi = await create_recipe(
        db_session, title="Pasta rustica al pomodoro", description="Ne manca una",
        instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
        ingredients=[(pasta.id, "primary", "320 g", None), (pomodoro.id, "primary", "6", None)],
        embedding=None,
    )
    lontana = await create_recipe(
        db_session, title="Pasta rustica al pesto", description="Ne mancano due",
        instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
        ingredients=[(pomodoro.id, "primary", "6", None), (basilico.id, "primary", "50 g", None)],
        embedding=None,
    )
    await db_session.flush()

    risultati = await search_recipes(db_session, query="pasta rustica", max_missing=1)

    assert [r.recipe.title for r in risultati] == ["Pasta rustica al pomodoro"]


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


async def test_senza_parole_l_ordine_a_parita_e_deciso_dall_id(db_session):
    """Un import in blocco scrive centinaia di ricette nella stessa transazione, e
    molte hanno lo stesso titolo («Impasto») e gli stessi mancanti. Senza uno
    spareggio, quali finiscono in una pagina — e in quale ordine — non sarebbe
    definito, e «Mostra altre» potrebbe ripetere una ricetta e saltarne un'altra.
    Dal 2026-09-24 (R4) l'ordine è `(mancanti, titolo, id)`: a parità decide l'id.

    Fino a R4 questo test difendeva lo spareggio della piscina delle cento più
    recenti (`created_at`, poi `id`); la piscina se n'è andata, l'intento no.
    L'attesa è calcolata dagli id appena creati, non da una seconda chiamata alla
    funzione sotto test: due letture della stessa tabella immutata passerebbero
    comunque.
    """
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import search_recipes

    ingrediente = Ingredient(
        name="farina", display_name="Farina", category=IngredientCategory.CEREALI
    )
    db_session.add(ingrediente)
    await db_session.flush()

    creati = [
        await create_recipe(
            db_session, title="Impasto", description="Pane",
            instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
            ingredients=[(ingrediente.id, "primary", "500 g", None)], embedding=None,
        )
        for _ in range(45)
    ]
    await db_session.flush()
    attesi = sorted(recipe.id for recipe in creati)

    prima = await search_recipes(db_session, limit=30)
    seconda = await search_recipes(db_session, limit=30, offset=30)

    assert [r.recipe.id for r in prima + seconda] == attesi


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


async def test_i_mancanti_si_chiamano_per_nome_e_in_ordine(db_session):
    """Il conteggio dice quante cose mancano, non quali.

    Con la soglia ferma a zero bastava il numero; oltre lo zero la domanda diventa
    «vale la pena comprarle?», e a quella un numero non risponde.

    Il secondario quasi finito non compare: non manca (regola primario/secondario), e
    se comparisse la scheda direbbe di comprare una cosa che c'è.
    """
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.db.models.pantry import PantryItem
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import search_recipes

    pasta = Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    aglio = Ingredient(name="aglio", display_name="Aglio", category=IngredientCategory.VERDURA)
    bottarga = Ingredient(
        name="bottarga", display_name="Bottarga", category=IngredientCategory.PESCE
    )
    zafferano = Ingredient(
        name="zafferano", display_name="Zafferano", category=IngredientCategory.SPEZIE
    )
    db_session.add_all([pasta, aglio, bottarga, zafferano])
    await db_session.flush()
    db_session.add_all([
        PantryItem(ingredient_id=pasta.id, status="available"),
        PantryItem(ingredient_id=aglio.id, status="low"),
    ])
    await db_session.flush()

    await create_recipe(
        db_session, title="Pasta della domenica", description="Con quel che non ho",
        instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
        ingredients=[
            (pasta.id, "primary", "320 g", None),
            (aglio.id, "secondary", "1 spicchio", None),
            (zafferano.id, "primary", "1 bustina", None),
            (bottarga.id, "primary", "20 g", None),
        ],
        embedding=None,
    )
    await db_session.flush()

    risultati = await search_recipes(db_session)

    assert len(risultati) == 1
    assert risultati[0].missing == 2
    # alfabetico: `recipe_ingredients` non ha una colonna di posizione, e senza un
    # criterio esplicito due letture identiche potrebbero elencarli in ordine diverso
    assert risultati[0].missing_names == ["Bottarga", "Zafferano"]


async def test_la_soglia_in_sql_coincide_con_la_regola(db_session):
    """Ogni combinazione di ruolo e stato in dispensa: le ricette che il filtro SQL
    lascia passare con soglia 0 sono esattamente quelle che `rules.py` dice
    cucinabili. La soglia si calcola in SQL dal 2026-09-24 (R4), ma la regola resta
    una sola: se un giorno cambiasse, il filtro non potrebbe restare indietro in
    silenzio."""
    from datetime import UTC, datetime

    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.db.models.pantry import PantryItem
    from app.db.models.recipe import Recipe, RecipeIngredient
    from app.domain.rules import (
        Availability,
        IngredientRole,
        PantryStatus,
        availability_of,
        is_satisfied,
    )
    from app.services.recipe_search import search_recipes

    # (stati attivi, stati archiviati): un elemento archiviato non conta
    dispense = {
        "assente": ([], []),
        "disponibile": ([PantryStatus.AVAILABLE], []),
        "quasi": ([PantryStatus.LOW], []),
        "finito": ([PantryStatus.FINISHED], []),
        "quasi e disponibile": ([PantryStatus.LOW, PantryStatus.AVAILABLE], []),
        "solo archiviato": ([], [PantryStatus.AVAILABLE]),
    }
    attese: dict[str, bool] = {}
    for nome, (attivi, archiviati) in dispense.items():
        ingrediente = Ingredient(
            name=f"ing {nome}", display_name=nome, category=IngredientCategory.VERDURA
        )
        db_session.add(ingrediente)
        await db_session.flush()
        for status in attivi:
            db_session.add(PantryItem(ingredient_id=ingrediente.id, status=status))
        for status in archiviati:
            db_session.add(
                PantryItem(ingredient_id=ingrediente.id, status=status,
                           archived_at=datetime.now(UTC))
            )
        disponibilita = availability_of(attivi) if attivi else Availability.MISSING
        for ruolo in IngredientRole:
            titolo = f"{nome} {ruolo.value}"
            ricetta = Recipe(title=titolo, instructions="x", source="manual")
            db_session.add(ricetta)
            await db_session.flush()
            db_session.add(
                RecipeIngredient(
                    recipe_id=ricetta.id, ingredient_id=ingrediente.id, role=ruolo.value
                )
            )
            attese[titolo] = is_satisfied(ruolo, disponibilita)
    await db_session.flush()

    cucinabili = await search_recipes(db_session, max_missing=0, limit=100)

    assert {r.recipe.title for r in cucinabili} == {t for t, ok in attese.items() if ok}
    assert all(r.missing == 0 and r.cookable for r in cucinabili)


async def test_senza_parole_il_ricettario_si_sfoglia_tutto(db_session):
    """Prima il ramo senza ricerca guardava le 100 più recenti: dopo la centesima
    non c'era più niente. Ora ogni ricetta si raggiunge, una volta sola."""
    from app.db.models.recipe import Recipe
    from app.services.recipe_search import search_recipes

    for numero in range(130):
        db_session.add(Recipe(title=f"Ricetta {numero:03d}", instructions="x", source="manual"))
    await db_session.flush()

    visti: list[str] = []
    for offset in range(0, 150, 30):
        pagina = await search_recipes(db_session, limit=30, offset=offset)
        visti += [r.recipe.title for r in pagina]

    assert len(visti) == 130
    assert len(set(visti)) == 130
    # stessi mancanti (nessuna riga): allora vale il titolo
    assert visti == sorted(visti)


async def test_senza_parole_prima_le_cucinabili_su_tutte_le_pagine(db_session):
    """L'ordine «prima ciò che puoi cucinare» vale sul ricettario intero, non
    dentro ogni pagina: una ricetta cucinabile non finisce a pagina due perché il
    suo titolo viene dopo."""
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.db.models.pantry import PantryItem
    from app.db.models.recipe import Recipe, RecipeIngredient
    from app.services.recipe_search import search_recipes

    ho = Ingredient(name="ho", display_name="Ho", category=IngredientCategory.VERDURA)
    manca = Ingredient(name="manca", display_name="Manca", category=IngredientCategory.VERDURA)
    db_session.add_all([ho, manca])
    await db_session.flush()
    db_session.add(PantryItem(ingredient_id=ho.id, status="available"))
    for titolo, ingrediente in [("A manca", manca), ("B manca", manca), ("Z cucinabile", ho)]:
        ricetta = Recipe(title=titolo, instructions="x", source="manual")
        db_session.add(ricetta)
        await db_session.flush()
        db_session.add(
            RecipeIngredient(recipe_id=ricetta.id, ingredient_id=ingrediente.id, role="primary")
        )
    await db_session.flush()

    prima = await search_recipes(db_session, limit=1)
    seconda = await search_recipes(db_session, limit=1, offset=1)

    assert [r.recipe.title for r in prima] == ["Z cucinabile"]
    assert [r.recipe.title for r in seconda] == ["A manca"]
    assert seconda[0].missing == 1


async def test_con_parole_l_offset_scorre_i_candidati(db_session):
    from app.db.models.recipe import Recipe
    from app.services.recipe_search import search_recipes

    for numero in range(5):
        db_session.add(Recipe(title=f"Zuppa {numero}", instructions="x", source="manual"))
    await db_session.flush()

    prima = await search_recipes(db_session, "zuppa", limit=3)
    dopo = await search_recipes(db_session, "zuppa", limit=3, offset=3)

    assert len(prima) == 3
    assert len(dopo) == 2
    assert not {r.recipe.id for r in prima} & {r.recipe.id for r in dopo}
