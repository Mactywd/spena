from datetime import date

import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus


@pytest_asyncio.fixture
async def ingredienti(db_session):
    yogurt = Ingredient(name="yogurt greco", display_name="Yogurt greco",
                        category=IngredientCategory.LATTICINI)
    mela = Ingredient(name="mela", display_name="Mela", category=IngredientCategory.FRUTTA)
    db_session.add_all([yogurt, mela])
    await db_session.flush()
    return {"yogurt": yogurt, "mela": mela}


async def test_free_text_enters_the_list_unresolved(logged_client):
    """Scrivere la lista non deve mai essere interrotto da una disambiguazione."""
    response = await logged_client.post("/api/v1/shopping-list", json={
        "raw_text": "quella cosa verde del mercato",
    })
    assert response.status_code == 201
    assert response.json()["ingredient_id"] is None
    assert response.json()["status"] == "pending"
    assert response.json()["reason"] == "manual"


async def test_item_can_be_resolved_later(logged_client, ingredienti):
    created = await logged_client.post("/api/v1/shopping-list", json={"raw_text": "yogurt"})
    item_id = created.json()["id"]

    patched = await logged_client.patch(f"/api/v1/shopping-list/{item_id}", json={
        "ingredient_id": str(ingredienti["yogurt"].id),
    })
    assert patched.json()["ingredient_name"] == "yogurt greco"


async def test_checking_an_item_stamps_the_time(logged_client, ingredienti):
    created = await logged_client.post("/api/v1/shopping-list", json={"raw_text": "mela"})
    item_id = created.json()["id"]
    patched = await logged_client.patch(f"/api/v1/shopping-list/{item_id}",
                                       json={"status": "checked"})
    assert patched.json()["status"] == "checked"


async def test_stocking_creates_pantry_items_and_closes_list_entries(
    logged_client, db_session, ingredienti
):
    product = Product(ingredient_id=ingredienti["yogurt"].id, name="Total 0%", brand="Fage",
                      source="openfoodfacts")
    db_session.add(product)
    yogurt_item = ShoppingListItem(raw_text="yogurt greco",
                                   ingredient_id=ingredienti["yogurt"].id,
                                   status=ShoppingStatus.CHECKED, reason=ShoppingReason.MANUAL)
    mela_item = ShoppingListItem(raw_text="mele", ingredient_id=ingredienti["mela"].id,
                                 status=ShoppingStatus.CHECKED, reason=ShoppingReason.MANUAL)
    db_session.add_all([yogurt_item, mela_item])
    await db_session.flush()

    response = await logged_client.post("/api/v1/shopping-list/stock", json={"entries": [
        {"shopping_item_id": str(yogurt_item.id),
         "ingredient_id": str(ingredienti["yogurt"].id),
         "product_id": str(product.id)},
        # le mele sfuse entrano senza prodotto
        {"shopping_item_id": str(mela_item.id),
         "ingredient_id": str(ingredienti["mela"].id),
         "product_id": None},
    ]})
    assert response.status_code == 201

    pantry = list((await db_session.execute(select(PantryItem))).scalars())
    assert len(pantry) == 2
    assert {p.status for p in pantry} == {"available"}
    assert sum(1 for p in pantry if p.product_id is None) == 1

    await db_session.refresh(yogurt_item)
    await db_session.refresh(mela_item)
    assert yogurt_item.status == "done"
    assert mela_item.done_at is not None


async def test_la_sistemazione_porta_in_dispensa_anche_le_scadenze(
    logged_client, db_session, ingredienti
):
    """Una voce con la data e una senza, nella stessa richiesta: la scadenza è
    facoltativa per voce, non per sistemazione. Lo yogurt ha una scadenza vera e
    corta, le mele sfuse no — ed è il caso normale."""
    yogurt_item = ShoppingListItem(raw_text="yogurt greco",
                                   ingredient_id=ingredienti["yogurt"].id,
                                   status=ShoppingStatus.CHECKED,
                                   reason=ShoppingReason.MANUAL)
    mela_item = ShoppingListItem(raw_text="mele", ingredient_id=ingredienti["mela"].id,
                                 status=ShoppingStatus.CHECKED,
                                 reason=ShoppingReason.MANUAL)
    db_session.add_all([yogurt_item, mela_item])
    await db_session.flush()

    response = await logged_client.post("/api/v1/shopping-list/stock", json={"entries": [
        {"shopping_item_id": str(yogurt_item.id),
         "ingredient_id": str(ingredienti["yogurt"].id),
         "product_id": None, "expires_on": "2026-10-02"},
        # le mele sfuse entrano senza data, e non è un errore
        {"shopping_item_id": str(mela_item.id),
         "ingredient_id": str(ingredienti["mela"].id), "product_id": None},
    ]})
    assert response.status_code == 201

    voci = list((await db_session.execute(select(PantryItem))).scalars())
    per_ingrediente = {v.ingredient_id: v for v in voci}
    assert per_ingrediente[ingredienti["yogurt"].id].expires_on == date(2026, 10, 2)
    assert per_ingrediente[ingredienti["mela"].id].expires_on is None


async def test_stocking_is_all_or_nothing(logged_client, db_session, ingredienti):
    """Un riferimento sbagliato nel mezzo non deve lasciare la dispensa a metà."""
    import uuid

    good = ShoppingListItem(raw_text="mele", ingredient_id=ingredienti["mela"].id,
                            status=ShoppingStatus.CHECKED, reason=ShoppingReason.MANUAL)
    db_session.add(good)
    await db_session.flush()
    # Il commit qui sotto rilascia il savepoint della fixture: il rollback che la
    # rotta fa sul percorso d'errore deve annullare solo il lavoro della rotta,
    # non anche questi dati preesistenti (vedi nota di correzione nel brief).
    await db_session.commit()

    response = await logged_client.post("/api/v1/shopping-list/stock", json={"entries": [
        {"shopping_item_id": str(good.id), "ingredient_id": str(ingredienti["mela"].id),
         "product_id": None},
        {"shopping_item_id": str(uuid.uuid4()), "ingredient_id": str(uuid.uuid4()),
         "product_id": None},
    ]})
    assert response.status_code == 404

    pantry = list((await db_session.execute(select(PantryItem))).scalars())
    assert pantry == []
    await db_session.refresh(good)
    assert good.status == "checked"


async def test_stocking_rejects_a_product_of_another_ingredient(
    logged_client, db_session, ingredienti
):
    """La strada dello scontrino/catalogo ha lo stesso buco della diretta: un
    prodotto di pomodoro non deve poter entrare come yogurt greco (brief)."""
    pomodoro = Ingredient(name="pomodoro", display_name="Pomodoro",
                          category=IngredientCategory.VERDURA)
    db_session.add(pomodoro)
    await db_session.flush()
    product = Product(ingredient_id=pomodoro.id, name="Pomodori pelati", source="openfoodfacts")
    db_session.add(product)
    yogurt_item = ShoppingListItem(raw_text="yogurt greco",
                                   ingredient_id=ingredienti["yogurt"].id,
                                   status=ShoppingStatus.CHECKED, reason=ShoppingReason.MANUAL)
    db_session.add(yogurt_item)
    await db_session.flush()

    response = await logged_client.post("/api/v1/shopping-list/stock", json={"entries": [
        {"shopping_item_id": str(yogurt_item.id),
         "ingredient_id": str(ingredienti["yogurt"].id),
         "product_id": str(product.id)},
    ]})
    assert response.status_code == 409
    assert "altro ingrediente" in response.json()["detail"]

    pantry = list((await db_session.execute(select(PantryItem))).scalars())
    assert pantry == []


async def test_stocking_with_a_dangling_product_is_404_not_500(
    logged_client, db_session, ingredienti
):
    """Un product_id che non esiste più resta un 404, non un muro (come già per
    l'ingrediente inesistente)."""
    import uuid

    yogurt_item = ShoppingListItem(raw_text="yogurt greco",
                                   ingredient_id=ingredienti["yogurt"].id,
                                   status=ShoppingStatus.CHECKED, reason=ShoppingReason.MANUAL)
    db_session.add(yogurt_item)
    await db_session.flush()

    response = await logged_client.post("/api/v1/shopping-list/stock", json={"entries": [
        {"shopping_item_id": str(yogurt_item.id),
         "ingredient_id": str(ingredienti["yogurt"].id),
         "product_id": str(uuid.uuid4())},
    ]})
    assert response.status_code == 404
    assert "inesistente" in response.json()["detail"]


async def test_listing_can_be_filtered_by_status(logged_client, db_session, ingredienti):
    db_session.add_all([
        ShoppingListItem(raw_text="a", status=ShoppingStatus.PENDING,
                         reason=ShoppingReason.MANUAL),
        ShoppingListItem(raw_text="b", status=ShoppingStatus.DONE, reason=ShoppingReason.MANUAL),
    ])
    await db_session.flush()

    open_items = (await logged_client.get(
        "/api/v1/shopping-list?status=pending&status=checked"
    )).json()
    assert [i["raw_text"] for i in open_items] == ["a"]


async def test_creating_with_a_dangling_ingredient_is_404_not_500(logged_client):
    import uuid

    response = await logged_client.post("/api/v1/shopping-list", json={
        "raw_text": "yogurt", "ingredient_id": str(uuid.uuid4()),
    })
    assert response.status_code == 404
    assert "inesistente" in response.json()["detail"]


async def test_resolving_to_a_dangling_ingredient_is_404_not_500(logged_client):
    """Risolvere una voce su un ingrediente cancellato non deve essere un muro."""
    import uuid

    created = await logged_client.post("/api/v1/shopping-list", json={"raw_text": "yogurt"})
    item_id = created.json()["id"]
    response = await logged_client.patch(f"/api/v1/shopping-list/{item_id}", json={
        "ingredient_id": str(uuid.uuid4()),
    })
    assert response.status_code == 404
    assert "inesistente" in response.json()["detail"]


async def test_una_voce_di_lista_porta_il_kind_del_suo_ingrediente(logged_client, db_session):
    """Serve alla sistemazione della spesa, che deve sapere se nascondere i campi
    dei nutrienti — e deve saperlo senza ricalcolare la partizione nel client."""
    from app.repositories.ingredients import create_ingredient

    candeggina = await create_ingredient(db_session, "candeggina", "Candeggina", "casa")
    await db_session.commit()

    await logged_client.post(
        "/api/v1/shopping-list",
        json={"raw_text": "candeggina", "ingredient_id": str(candeggina.id)},
    )
    voci = (await logged_client.get("/api/v1/shopping-list")).json()

    assert voci[0]["ingredient_kind"] == "non_food"


# S8: il codice appena letto segue la scelta dal catalogo. Chi scansiona un codice
# che nessuno conosce e poi sceglie a catalogo un prodotto che un codice non ce
# l'ha, la prossima volta deve ritrovarlo scansionando. Il codice viaggia con la
# voce della sistemazione, e il backend lo dà al prodotto solo se il prodotto non
# ne ha uno e il codice non è già di un altro: correggere un legame sbagliato è
# un'altra cosa (S9), non un effetto collaterale del mettere in dispensa.
async def _yogurt_da_sistemare(db_session, ingredienti, **product_fields):
    product = Product(ingredient_id=ingredienti["yogurt"].id, name="Total 0%", brand="Fage",
                      source="custom", **product_fields)
    item = ShoppingListItem(raw_text="yogurt greco", ingredient_id=ingredienti["yogurt"].id,
                            status=ShoppingStatus.CHECKED, reason=ShoppingReason.MANUAL)
    db_session.add_all([product, item])
    await db_session.flush()
    return product, item


def _voce(item, product, barcode):
    return {"shopping_item_id": str(item.id), "ingredient_id": str(product.ingredient_id),
            "product_id": str(product.id), "barcode": barcode}


async def test_il_codice_letto_va_al_prodotto_scelto_che_non_ne_ha(
    logged_client, db_session, ingredienti
):
    product, item = await _yogurt_da_sistemare(db_session, ingredienti)

    response = await logged_client.post("/api/v1/shopping-list/stock", json={
        "entries": [_voce(item, product, "8001234567890")]})
    assert response.status_code == 201

    await db_session.refresh(product)
    assert product.barcode == "8001234567890"
    # ed è quel che rende vero il «la prossima volta lo trova»
    found = (await logged_client.get("/api/v1/products/barcode/8001234567890")).json()
    assert found["product"]["id"] == str(product.id)


async def test_lo_stesso_codice_gia_sul_prodotto_non_cambia_niente(
    logged_client, db_session, ingredienti
):
    product, item = await _yogurt_da_sistemare(db_session, ingredienti, barcode="52010")

    response = await logged_client.post("/api/v1/shopping-list/stock", json={
        "entries": [_voce(item, product, "52010")]})
    assert response.status_code == 201

    await db_session.refresh(product)
    assert product.barcode == "52010"


async def test_un_prodotto_con_un_altro_codice_non_viene_riscritto(
    logged_client, db_session, ingredienti
):
    """Il burro col codice del parmigiano (S9) è esattamente questo: un legame
    sbagliato. Sovrascrivere il codice di un prodotto ne farebbe uno nuovo, in
    silenzio, a ogni sistemazione."""
    product, item = await _yogurt_da_sistemare(db_session, ingredienti, barcode="52010")

    response = await logged_client.post("/api/v1/shopping-list/stock", json={
        "entries": [_voce(item, product, "8001234567890")]})
    assert response.status_code == 201

    await db_session.refresh(product)
    assert product.barcode == "52010"
    assert len(list((await db_session.execute(select(PantryItem))).scalars())) == 1


async def test_un_codice_gia_di_un_altro_prodotto_non_si_sposta_e_la_spesa_entra(
    logged_client, db_session, ingredienti
):
    """Né furto né muro: il codice resta dov'era, e la voce entra in dispensa lo
    stesso. Rifiutare l'intera sistemazione — che è tutto-o-niente — per un legame
    che non si può fare sarebbe il vicolo cieco che CLAUDE.md vieta."""
    owner = Product(ingredient_id=ingredienti["yogurt"].id, name="Yogurt greco pesca",
                    brand="Carrefour", barcode="8001234567890", source="custom")
    db_session.add(owner)
    product, item = await _yogurt_da_sistemare(db_session, ingredienti)
    mele = ShoppingListItem(raw_text="mele", ingredient_id=ingredienti["mela"].id,
                            status=ShoppingStatus.CHECKED, reason=ShoppingReason.MANUAL)
    db_session.add(mele)
    await db_session.flush()

    response = await logged_client.post("/api/v1/shopping-list/stock", json={"entries": [
        _voce(item, product, "8001234567890"),
        {"shopping_item_id": str(mele.id), "ingredient_id": str(ingredienti["mela"].id),
         "product_id": None},
    ]})
    assert response.status_code == 201

    await db_session.refresh(product)
    await db_session.refresh(owner)
    assert product.barcode is None
    assert owner.barcode == "8001234567890"
    pantry = list((await db_session.execute(select(PantryItem))).scalars())
    assert {p.product_id for p in pantry} == {product.id, None}


# S18: «latte» + Invio entrava come testo libero sotto «Senza reparto», accanto al
# «latte» vero, perché solo il tocco su un suggerimento legava un ingrediente. Ora
# lo lega il backend quando il testo *coincide* — col nome o con un alias, senza
# badare a maiuscole e spazi attorno — così vale per qualunque client. E un
# ingrediente già da comprare non si doppia: si risponde come la dispensa quando
# rimette in lista, «era già in lista».


@pytest_asyncio.fixture
async def anagrafica_s18(db_session):
    latte = Ingredient(name="latte", display_name="Latte", category=IngredientCategory.LATTICINI)
    pasta = Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    pasta.aliases.append(IngredientAlias(alias="rigatoni", source="import"))
    detersivo = Ingredient(name="detersivo per i piatti", display_name="Detersivo per i piatti",
                           category=IngredientCategory.CASA)
    db_session.add_all([latte, pasta, detersivo])
    await db_session.flush()
    return {"latte": latte, "pasta": pasta, "detersivo": detersivo}


async def _righe_in_lista(db_session) -> list[ShoppingListItem]:
    return list((await db_session.execute(select(ShoppingListItem))).scalars())


async def test_il_nome_esatto_scritto_a_mano_aggancia_l_ingrediente(
    logged_client, anagrafica_s18
):
    response = await logged_client.post("/api/v1/shopping-list", json={"raw_text": "  Latte "})
    assert response.status_code == 201
    body = response.json()
    assert body["ingredient_id"] == str(anagrafica_s18["latte"].id)
    assert body["ingredient_category"] == "latticini"
    assert body["added"] is True
    # quel che hai scritto resta quel che leggi in lista
    assert body["raw_text"] == "Latte"


async def test_un_alias_esatto_aggancia_il_suo_ingrediente(logged_client, anagrafica_s18):
    response = await logged_client.post("/api/v1/shopping-list", json={"raw_text": "Rigatoni"})
    assert response.status_code == 201
    assert response.json()["ingredient_id"] == str(anagrafica_s18["pasta"].id)


async def test_anche_un_non_alimentare_si_aggancia(logged_client, anagrafica_s18):
    """In lista i non alimentari sono di casa: il filtro kind=food è delle ricette."""
    response = await logged_client.post(
        "/api/v1/shopping-list", json={"raw_text": "detersivo per i piatti"}
    )
    assert response.status_code == 201
    assert response.json()["ingredient_id"] == str(anagrafica_s18["detersivo"].id)
    assert response.json()["ingredient_kind"] == "non_food"


async def test_una_somiglianza_non_basta_e_la_voce_resta_libera(logged_client, anagrafica_s18):
    """Solo l'uguaglianza aggancia in silenzio: «latt» somiglia, ma non è latte."""
    for testo in ["latt", "latte intero"]:
        response = await logged_client.post("/api/v1/shopping-list", json={"raw_text": testo})
        assert response.status_code == 201
        assert response.json()["ingredient_id"] is None


async def test_un_alias_di_due_ingredienti_non_sceglie_a_caso(
    logged_client, db_session, anagrafica_s18
):
    """Lo stesso alias su due ingredienti è raggiungibile — l'unicità è per coppia
    (ingrediente, alias) — e sceglierne uno sarebbe un aggancio arbitrario."""
    riso = Ingredient(name="riso", display_name="Riso", category=IngredientCategory.CEREALI)
    riso.aliases.append(IngredientAlias(alias="rigatoni", source="import"))
    db_session.add(riso)
    await db_session.flush()

    response = await logged_client.post("/api/v1/shopping-list", json={"raw_text": "rigatoni"})
    assert response.status_code == 201
    assert response.json()["ingredient_id"] is None


async def test_un_ingrediente_gia_in_lista_non_si_doppia(
    logged_client, db_session, anagrafica_s18
):
    first = await logged_client.post("/api/v1/shopping-list", json={"raw_text": "latte"})
    again = await logged_client.post("/api/v1/shopping-list", json={"raw_text": "LATTE"})

    # 200 e non 201: niente è stato creato, e non è un errore
    assert again.status_code == 200
    assert again.json()["added"] is False
    assert again.json()["id"] == first.json()["id"]
    assert len(await _righe_in_lista(db_session)) == 1


async def test_anche_il_suggerimento_scelto_non_doppia(
    logged_client, db_session, anagrafica_s18
):
    """Il tocco sul suggerimento manda l'id: stesso controllo. E una voce già nel
    carrello conta come in lista, come per la dispensa."""
    esistente = ShoppingListItem(raw_text="latte", ingredient_id=anagrafica_s18["latte"].id,
                                 status=ShoppingStatus.CHECKED, reason=ShoppingReason.MANUAL)
    db_session.add(esistente)
    await db_session.flush()

    response = await logged_client.post("/api/v1/shopping-list", json={
        "raw_text": "latte", "ingredient_id": str(anagrafica_s18["latte"].id),
    })
    assert response.status_code == 200
    assert response.json()["added"] is False
    assert response.json()["id"] == str(esistente.id)
    assert len(await _righe_in_lista(db_session)) == 1


async def test_una_voce_gia_sistemata_o_tolta_non_blocca(
    logged_client, db_session, anagrafica_s18
):
    """Quel che è già in dispensa o è stato tolto dalla lista non è «da comprare»."""
    db_session.add_all([
        ShoppingListItem(raw_text="latte", ingredient_id=anagrafica_s18["latte"].id,
                         status=ShoppingStatus.DONE, reason=ShoppingReason.MANUAL),
        ShoppingListItem(raw_text="latte", ingredient_id=anagrafica_s18["latte"].id,
                         status=ShoppingStatus.ARCHIVED, reason=ShoppingReason.MANUAL),
    ])
    await db_session.flush()

    response = await logged_client.post("/api/v1/shopping-list", json={"raw_text": "latte"})
    assert response.status_code == 201
    assert response.json()["added"] is True


async def test_il_testo_libero_non_si_confronta_col_testo_libero(logged_client, db_session):
    """Senza ingrediente non c'è un'identità su cui dire «è la stessa cosa»: due
    voci libere uguali restano due, come prima."""
    for _ in range(2):
        response = await logged_client.post(
            "/api/v1/shopping-list", json={"raw_text": "quella cosa verde"}
        )
        assert response.status_code == 201
    assert len(await _righe_in_lista(db_session)) == 2
