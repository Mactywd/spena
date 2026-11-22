import pytest_asyncio

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus
from app.repositories.ingredients import search_ingredients


@pytest_asyncio.fixture
async def catalogo(db_session):
    pomodoro = Ingredient(name="pomodoro", display_name="Pomodoro",
                          category=IngredientCategory.VERDURA)
    pomodoro.aliases.append(IngredientAlias(alias="pomodori pelati", source="import"))
    yogurt = Ingredient(name="yogurt greco", display_name="Yogurt greco",
                        category=IngredientCategory.LATTICINI)
    prezzemolo = Ingredient(name="prezzemolo", display_name="Prezzemolo",
                            category=IngredientCategory.SPEZIE)
    db_session.add_all([pomodoro, yogurt, prezzemolo])
    await db_session.flush()
    return {"pomodoro": pomodoro, "yogurt": yogurt, "prezzemolo": prezzemolo}


async def test_search_finds_by_exact_prefix(db_session, catalogo):
    results = await search_ingredients(db_session, "pomo")
    assert [i.name for i in results][0] == "pomodoro"


async def test_search_forgives_a_typo(db_session, catalogo):
    results = await search_ingredients(db_session, "yogrut greco")
    assert "yogurt greco" in [i.name for i in results]


async def test_search_matches_on_aliases(db_session, catalogo):
    results = await search_ingredients(db_session, "pelati")
    assert [i.name for i in results][0] == "pomodoro"


async def test_search_returns_each_ingredient_once(db_session, catalogo):
    """Un match sia sul nome sia su un alias non deve duplicare la riga."""
    catalogo["pomodoro"].aliases.append(IngredientAlias(alias="pomodoro rosso", source="manual"))
    await db_session.flush()
    results = await search_ingredients(db_session, "pomodoro")
    names = [i.name for i in results]
    assert names.count("pomodoro") == 1


async def test_frequently_bought_ingredients_rank_first(db_session, catalogo):
    """A pari somiglianza vince ciò che compri davvero."""
    for _ in range(5):
        db_session.add(ShoppingListItem(
            raw_text="prezzemolo", ingredient_id=catalogo["prezzemolo"].id,
            status=ShoppingStatus.DONE, reason=ShoppingReason.MANUAL,
        ))
    await db_session.flush()
    results = await search_ingredients(db_session, "p")
    assert results[0].name == "prezzemolo"


async def test_fuzzy_match_ranks_by_similarity_not_frequency(db_session):
    """Su una query lunga con refuso, la somiglianza vince sulla frequenza d'acquisto.

    Né 'pomodoro' né 'pomodorini' sono prefissi di 'pomodorr' (entrambi i LIKE sono
    falsi), quindi il confronto ricade sulla sola trigram similarity: 'pomodoro' è
    più simile (0.636) di 'pomodorini' (0.538). Comprare 'pomodorini' cinque volte
    non deve ribaltare l'ordine: la frequenza è un criterio secondario, non primario,
    quando il match non è un prefisso esatto.
    """
    pomodoro = Ingredient(name="pomodoro", display_name="Pomodoro",
                          category=IngredientCategory.VERDURA)
    pomodorini = Ingredient(name="pomodorini", display_name="Pomodorini",
                            category=IngredientCategory.VERDURA)
    db_session.add_all([pomodoro, pomodorini])
    await db_session.flush()

    for _ in range(5):
        db_session.add(ShoppingListItem(
            raw_text="pomodorini", ingredient_id=pomodorini.id,
            status=ShoppingStatus.DONE, reason=ShoppingReason.MANUAL,
        ))
    await db_session.flush()

    results = await search_ingredients(db_session, "pomodorr")
    assert results[0].name == "pomodoro"


async def test_search_endpoint_requires_a_session(client):
    assert (await client.get("/api/v1/ingredients/search?q=pomo")).status_code == 401


async def test_create_ingredient_and_alias_via_api(logged_client, db_session):
    created = await logged_client.post("/api/v1/ingredients", json={
        "name": "basilico", "display_name": "Basilico", "category": "spezie",
    })
    assert created.status_code == 201
    ingredient_id = created.json()["id"]

    aliased = await logged_client.post(
        f"/api/v1/ingredients/{ingredient_id}/aliases",
        json={"alias": "basilico genovese", "source": "manual"},
    )
    assert aliased.status_code == 201

    found = await logged_client.get("/api/v1/ingredients/search?q=genovese")
    assert found.json()[0]["name"] == "basilico"


async def test_duplicate_ingredient_name_returns_409(logged_client):
    body = {"name": "basilico", "display_name": "Basilico", "category": "spezie"}
    assert (await logged_client.post("/api/v1/ingredients", json=body)).status_code == 201
    assert (await logged_client.post("/api/v1/ingredients", json=body)).status_code == 409


async def test_a_duplicate_name_answers_with_the_ingredient_that_already_has_it(logged_client):
    """«Sistema la spesa» riprovava a creare «pomodoro», riceveva un 409 e diceva
    «forse esiste già con un altro nome» — esisteva con lo stesso (S19). Il 409
    porta l'ingrediente che ha quel nome, così chi crea può agganciarlo invece di
    cercarlo; `detail` resta la stringa di sempre."""
    first = await logged_client.post(
        "/api/v1/ingredients",
        json={"name": "basilico", "display_name": "Basilico", "category": "spezie"},
    )
    again = await logged_client.post(
        "/api/v1/ingredients",
        # la stessa normalizzazione della creazione: maiuscole e spazi non fanno un
        # nome diverso
        json={"name": "  Basilico ", "display_name": "Basilico", "category": "verdura"},
    )

    assert again.status_code == 409
    assert again.json()["detail"] == "ingrediente già presente"
    assert again.json()["existing"] == first.json()


async def test_alias_on_a_missing_ingredient_is_404_not_409(logged_client):
    """Un ingrediente inesistente non è un alias duplicato: dirlo bene importa."""
    import uuid

    response = await logged_client.post(
        f"/api/v1/ingredients/{uuid.uuid4()}/aliases",
        json={"alias": "basilico genovese", "source": "manual"},
    )
    assert response.status_code == 404
    assert "ingrediente" in response.json()["detail"]


async def test_duplicate_alias_is_still_409(logged_client):
    created = await logged_client.post("/api/v1/ingredients", json={
        "name": "basilico", "display_name": "Basilico", "category": "spezie",
    })
    ingredient_id = created.json()["id"]
    body = {"alias": "basilico genovese", "source": "manual"}
    url = f"/api/v1/ingredients/{ingredient_id}/aliases"
    assert (await logged_client.post(url, json=body)).status_code == 201
    conflict = await logged_client.post(url, json=body)
    assert conflict.status_code == 409
    assert "alias" in conflict.json()["detail"]


async def test_la_ricerca_filtra_per_kind_solo_se_glielo_chiedi(logged_client, db_session):
    """Senza parametro si vede tutto: è la lista della spesa, dove il detersivo
    deve comparire. Con `kind=food` no: è il ricettario."""
    from app.repositories.ingredients import create_ingredient

    await create_ingredient(db_session, "detersivo per i piatti", "Detersivo per i piatti", "casa")
    await create_ingredient(db_session, "detersivo alimentare finto", "Dado", "condimenti")
    await db_session.commit()

    tutti = (await logged_client.get("/api/v1/ingredients/search?q=deter")).json()
    assert "Detersivo per i piatti" in [i["display_name"] for i in tutti]

    solo_cibo = (await logged_client.get("/api/v1/ingredients/search?q=deter&kind=food")).json()
    assert "Detersivo per i piatti" not in [i["display_name"] for i in solo_cibo]
    assert "Dado" in [i["display_name"] for i in solo_cibo], "il filtro deve mantenere i cibi, non svuotare il risultato"


async def test_la_ricerca_dice_il_kind_di_ogni_voce(logged_client, db_session):
    """Il frontend non lo calcola: lo legge. La partizione dei reparti vive nel
    backend, e ricopiarla nel client sarebbe la seconda copia che si scolla."""
    from app.repositories.ingredients import create_ingredient

    await create_ingredient(db_session, "candeggina", "Candeggina", "casa")
    await db_session.commit()

    trovati = (await logged_client.get("/api/v1/ingredients/search?q=cande")).json()
    assert trovati[0]["kind"] == "non_food"


# --- I suggerimenti tagliati (spec docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md)
#
# Passano tutti dall'endpoint che il frontend chiama, su Postgres vero (prima lezione di
# CLAUDE.md: si prova la cosa che gira). Le somiglianze nei docstring sono quelle di
# pg_trgm: `similarity` di tutta la stringa.


async def _ingredienti(db_session, *voci):
    """Ogni voce è un nome, o una tupla (nome, alias, …). Il reparto è uno qualunque del
    cibo: la ricerca non lo guarda."""
    creati = {}
    for voce in voci:
        nome, *alias = (voce,) if isinstance(voce, str) else voce
        ingrediente = Ingredient(name=nome, display_name=nome.capitalize(),
                                 category=IngredientCategory.ALTRO)
        for uno in alias:
            ingrediente.aliases.append(IngredientAlias(alias=uno, source="manual"))
        db_session.add(ingrediente)
        creati[nome] = ingrediente
    await db_session.flush()
    return creati


async def _suggeriti(client, q: str, **params) -> list[str]:
    risposta = await client.get("/api/v1/ingredients/search", params={"q": q, **params})
    assert risposta.status_code == 200
    return [voce["name"] for voce in risposta.json()]


async def test_i_suggerimenti_tengono_solo_chi_contiene_il_testo(logged_client, db_session):
    """Il caso del giro di T3. Zucchero e zucchina cominciano con «zucch» (0,500 tutti e
    due); la zucca no, anche se somiglia uguale (0,500): esce. Fra i due resta l'ordine di
    sempre, alfabetico a parità di tutto (decisione 5: nessuno spareggio nuovo). La ricerca
    di `match_name` e dei vicini dell'AI la zucca la vede ancora."""
    await _ingredienti(db_session, "zucchero", "zucchina", "zucca")

    assert await _suggeriti(logged_client, "zucch") == ["zucchero", "zucchina"]
    assert "zucca" in [i.name for i in await search_ingredients(db_session, "zucch")]


async def test_un_alias_con_il_testo_a_inizio_parola_e_un_riscontro(logged_client, db_session):
    """Decisione 4 (Mattia): l'inizio di una parola vale in ogni alias. «tonno sott'olio»
    ha «olio» dopo l'apostrofo, quindi Tonno in scatola resta; «olive verdi» (0,214) non
    contiene «olio» ed esce."""
    await _ingredienti(
        db_session, "olio di oliva", ("tonno in scatola", "tonno sott'olio"), "olive verdi"
    )

    assert set(await _suggeriti(logged_client, "olio")) == {"olio di oliva", "tonno in scatola"}


async def test_i_vicini_per_l_ai_restano_sfumati(db_session):
    """Decisione 3: il taglio vale solo per l'endpoint. `decide.py` chiede a
    `search_ingredients` tre vicini, e lì uno sfumato che non contiene il testo è
    proprio quel che serve all'AI."""
    await _ingredienti(
        db_session, "olio di oliva", ("tonno in scatola", "tonno sott'olio"), "olive verdi"
    )

    vicini = [i.name for i in await search_ingredients(db_session, "olio", limit=3)]
    assert "olive verdi" in vicini


async def test_pollo_trova_le_parti_del_pollo_a_meta_nome(logged_client, db_session):
    """Le parole di Mattia: «se scrivo "pollo" voglio "petto di pollo", "ali di pollo"».
    «pollame» (0,400) non contiene «pollo» ed esce."""
    await _ingredienti(db_session, "petto di pollo", "ali di pollo", "pollame")

    assert set(await _suggeriti(logged_client, "pollo")) == {"petto di pollo", "ali di pollo"}


async def test_un_riscontro_non_resta_fuori_dal_limite_ne_sotto_il_pavimento(
    logged_client, db_session
):
    """La sesta lezione di CLAUDE.md: un filtro sul risultato non può stare dietro un
    limite. Undici «pollame NN» somigliano a «pollo» più (0,308) di «coscia di pollo
    disossata» (0,250, sotto il pavimento): nell'ordine di `search_ingredients` la coscia
    resta fuori dai dieci, e il taglio dopo non la ritroverebbe. Nei suggerimenti
    `is_hit` la porta davanti, e un riscontro non guarda il pavimento. `match_name`
    (`limit=1`) prende ancora lo sfumato più simile."""
    pollame = [f"pollame {i:02}" for i in range(1, 12)]
    await _ingredienti(db_session, *pollame, "coscia di pollo disossata")

    assert await _suggeriti(logged_client, "pollo") == ["coscia di pollo disossata"]
    oggi = [i.name for i in await search_ingredients(db_session, "pollo")]
    assert "coscia di pollo disossata" not in oggi
    assert (await search_ingredients(db_session, "pollo", limit=1))[0].name in pollame


async def test_senza_accenti_te_trova_il_te(logged_client, db_session):
    """Decisione 2. «tè» somiglia a «te» solo 0,200, sotto il pavimento: senza togliere
    gli accenti sarebbe uno sfumato, e con «tempeh» che è un riscontro resterebbe fuori.
    «patate» contiene «te» ma non all'inizio di una parola."""
    await _ingredienti(db_session, "tè", "tempeh", "patate")

    assert set(await _suggeriti(logged_client, "te")) == {"tè", "tempeh"}


async def test_senza_accenti_caffe_e_un_prefisso_di_caffe(logged_client, db_session):
    """Scelta 10 del piano: anche il prefisso, nei suggerimenti, si confronta senza
    accenti. Tutti e due sono prefissi di «caffe», e vince la somiglianza: caffè 0,500,
    caffelatte 0,417."""
    await _ingredienti(db_session, "caffè", "caffelatte")

    assert await _suggeriti(logged_client, "caffe") == ["caffè", "caffelatte"]


async def test_senza_riscontri_passano_gli_sfumati_vicini_al_primo(logged_client, db_session):
    """Il refuso nella parola intera: nessuno contiene «pomodorr». La soglia è
    max(0,30; 0,8 × 0,636) = 0,509: pomodorini (0,538) passa, pomodori secchi (0,389)
    no."""
    await _ingredienti(db_session, "pomodoro", "pomodorini", "pomodori secchi")

    assert await _suggeriti(logged_client, "pomodorr") == ["pomodoro", "pomodorini"]


async def test_un_ingrediente_che_non_c_e_da_una_lista_vuota(logged_client, db_session):
    """«zenzero» somiglia a «zucchero» 0,214: oggi è un suggerimento (sopra lo 0,15), e
    toccarlo legava la voce all'ingrediente sbagliato. Sotto il pavimento la lista è
    vuota, e il chiamante mostra la sua via d'uscita."""
    await _ingredienti(db_session, "zucchero")

    assert [i.name for i in await search_ingredients(db_session, "zenzero")] == ["zucchero"]
    assert await _suggeriti(logged_client, "zenzero") == []


async def test_percento_e_trattino_basso_sono_lettere(logged_client, db_session, catalogo):
    """Prima, «p%» faceva `LIKE 'p%%'` e trovava come prefisso ogni nome che comincia per
    p. Ora `%` e `_` sono lettere, nei suggerimenti e in `search_ingredients`; e una sola
    lettera somiglia a ogni nome meno di 0,15."""
    assert await search_ingredients(db_session, "p%") == []
    assert await search_ingredients(db_session, "p_") == []
    assert await _suggeriti(logged_client, "p%") == []
    assert await _suggeriti(logged_client, "p_") == []


async def test_i_suggerimenti_non_superano_il_limite(logged_client, db_session):
    await _ingredienti(db_session, *[f"pasta {i:02}" for i in range(1, 13)])

    assert len(await _suggeriti(logged_client, "pasta")) == 10
    assert len(await _suggeriti(logged_client, "pasta", limit=3)) == 3


async def test_il_refuso_e_l_alias_di_sempre_passano_anche_dall_endpoint(logged_client, catalogo):
    """I due test di sempre che passavano dagli sfumati, ora attraverso l'endpoint:
    «yogrut greco» non contiene niente e somiglia 0,529, sopra le due soglie; «pelati»
    sta a metà dell'alias «pomodori pelati», e con la decisione 4 è un riscontro."""
    assert (await _suggeriti(logged_client, "yogrut greco"))[0] == "yogurt greco"
    assert await _suggeriti(logged_client, "pelati") == ["pomodoro"]


async def test_l_elenco_intero_mostra_il_quasi_doppione_accanto_al_riscontro(logged_client, db_session):
    """Il caso 2 della revisione del 2026-10-18, deciso da Mattia il 2026-11-18 (strada b):
    l'Anagrafica chiede l'elenco intero, perché esiste per trovare i doppioni. «zuchina»
    (0,700) non contiene «zucchina»: il taglio la toglie, l'elenco intero no."""
    await _ingredienti(db_session, "zucchina", "zuchina")

    assert await _suggeriti(logged_client, "zucchina") == ["zucchina"]
    assert await _suggeriti(logged_client, "zucchina", trim="false") == ["zucchina", "zuchina"]


async def test_l_elenco_intero_trova_l_ingrediente_nel_testo_lungo_della_voce(logged_client, db_session):
    """Il caso 1: «Abbina» precompila il testo della voce. Nessun nome contiene «pasta
    barilla integrale», e pasta somiglia 0,250, sotto il pavimento: tagliato è vuoto,
    intero la pasta viene prima."""
    await _ingredienti(db_session, "pasta", "pane")

    assert await _suggeriti(logged_client, "pasta barilla integrale") == []
    intero = await _suggeriti(logged_client, "pasta barilla integrale", trim="false")
    assert intero[0] == "pasta"


async def test_l_elenco_tagliato_e_l_inizio_di_quello_intero(logged_client, db_session):
    """Decisione 4 del piano: il taglio non riordina, e i riscontri vengono prima di ogni
    sfumato, quindi la lista tagliata è sempre la testa di quella intera. Senza `trim` è
    la tagliata (il default che tutti gli altri chiamanti usano)."""
    await _ingredienti(
        db_session, "zucchero", "zucchina", "zucca", "olio di oliva",
        ("tonno in scatola", "tonno sott'olio"), "olive verdi", "pomodoro", "pomodorini",
        "pomodori secchi", "caffè", "caffelatte", "pasta",
    )

    for testo in ["zucch", "olio", "pomodorr", "caffe", "te", "zenzero", "pasta barilla integrale"]:
        tagliato = await _suggeriti(logged_client, testo)
        assert await _suggeriti(logged_client, testo, trim="true") == tagliato, testo
        intero = await _suggeriti(logged_client, testo, trim="false")
        assert intero[: len(tagliato)] == tagliato, testo
        assert len(intero) >= len(tagliato), testo


async def test_l_elenco_intero_tiene_il_limite_e_il_kind(logged_client, db_session):
    """Senza taglio il `LIMIT` della query è il solo freno, e il filtro del cibo vale
    come sempre: una ricetta non nomina un non alimentare (decisione 2 di CLAUDE.md)."""
    from app.repositories.ingredients import create_ingredient

    await _ingredienti(db_session, *[f"pollame {i:02}" for i in range(1, 13)])
    await create_ingredient(db_session, "candeggina", "Candeggina", "casa")
    await create_ingredient(db_session, "canditi", "Canditi", "dolci")
    await db_session.commit()

    assert len(await _suggeriti(logged_client, "pollo", trim="false")) == 10
    assert len(await _suggeriti(logged_client, "pollo", trim="false", limit="3")) == 3
    cibo = await _suggeriti(logged_client, "cand", trim="false", kind="food")
    assert "canditi" in cibo and "candeggina" not in cibo


async def test_trim_che_non_e_un_booleano_e_un_422(logged_client):
    risposta = await logged_client.get("/api/v1/ingredients/search", params={"q": "zucch", "trim": "boh"})
    assert risposta.status_code == 422
