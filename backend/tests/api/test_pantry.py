import pytest
import pytest_asyncio

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.domain.rules import Availability, PantryStatus
from app.repositories.pantry import availability_map


@pytest_asyncio.fixture
async def dispensa(db_session):
    yogurt = Ingredient(name="yogurt greco", display_name="Yogurt greco",
                        category=IngredientCategory.LATTICINI)
    pomodoro = Ingredient(name="pomodoro", display_name="Pomodoro",
                          category=IngredientCategory.VERDURA)
    aglio = Ingredient(name="aglio", display_name="Aglio", category=IngredientCategory.VERDURA)
    db_session.add_all([yogurt, pomodoro, aglio])
    await db_session.flush()
    return {"yogurt": yogurt, "pomodoro": pomodoro, "aglio": aglio}


async def test_availability_map_takes_the_best_status(db_session, dispensa):
    """Due yogurt, uno pieno e uno agli sgoccioli: l'ingrediente è disponibile."""
    fage = Product(ingredient_id=dispensa["yogurt"].id, name="Fage", source="custom")
    carrefour = Product(ingredient_id=dispensa["yogurt"].id, name="Carrefour", source="custom")
    db_session.add_all([fage, carrefour])
    await db_session.flush()
    db_session.add_all([
        PantryItem(ingredient_id=dispensa["yogurt"].id, product_id=fage.id,
                   status=PantryStatus.LOW),
        PantryItem(ingredient_id=dispensa["yogurt"].id, product_id=carrefour.id,
                   status=PantryStatus.AVAILABLE),
        PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.LOW),
    ])
    await db_session.flush()

    result = await availability_map(db_session)
    assert result[dispensa["yogurt"].id] is Availability.AVAILABLE
    assert result[dispensa["pomodoro"].id] is Availability.LOW
    assert result.get(dispensa["aglio"].id, Availability.MISSING) is Availability.MISSING


async def test_finished_and_archived_items_do_not_count(db_session, dispensa):
    from datetime import UTC, datetime

    db_session.add_all([
        PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.FINISHED),
        PantryItem(ingredient_id=dispensa["aglio"].id, status=PantryStatus.AVAILABLE,
                   archived_at=datetime.now(UTC)),
    ])
    await db_session.flush()

    result = await availability_map(db_session)
    assert result.get(dispensa["pomodoro"].id, Availability.MISSING) is Availability.MISSING
    assert result.get(dispensa["aglio"].id, Availability.MISSING) is Availability.MISSING


async def test_availability_map_can_be_restricted_to_some_ingredients(db_session, dispensa):
    db_session.add_all([
        PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE),
        PantryItem(ingredient_id=dispensa["aglio"].id, status=PantryStatus.AVAILABLE),
    ])
    await db_session.flush()
    result = await availability_map(db_session, [dispensa["pomodoro"].id])
    assert set(result) == {dispensa["pomodoro"].id}


async def test_pantry_listing_carries_names_for_display(logged_client, db_session, dispensa):
    product = Product(ingredient_id=dispensa["yogurt"].id, name="Total 0%", brand="Fage",
                      source="openfoodfacts")
    db_session.add(product)
    await db_session.flush()
    db_session.add(PantryItem(ingredient_id=dispensa["yogurt"].id, product_id=product.id,
                              status=PantryStatus.AVAILABLE))
    await db_session.flush()

    body = (await logged_client.get("/api/v1/pantry")).json()
    entry = next(e for e in body if e["ingredient_name"] == "yogurt greco")
    assert entry["product_name"] == "Total 0%"
    assert entry["product_brand"] == "Fage"
    assert entry["ingredient_category"] == "latticini"


async def test_loose_produce_enters_without_a_product(logged_client, dispensa):
    response = await logged_client.post("/api/v1/pantry", json={
        "ingredient_id": str(dispensa["pomodoro"].id), "status": "available",
    })
    assert response.status_code == 201
    assert response.json()["product_id"] is None


async def test_creating_with_a_matching_product_is_stored(
    logged_client, db_session, dispensa
):
    """Il caso corretto: il prodotto è davvero di quell'ingrediente."""
    product = Product(ingredient_id=dispensa["yogurt"].id, name="Total 0%", brand="Fage",
                      source="openfoodfacts")
    db_session.add(product)
    await db_session.flush()

    response = await logged_client.post("/api/v1/pantry", json={
        "ingredient_id": str(dispensa["yogurt"].id), "product_id": str(product.id),
        "status": "available",
    })
    assert response.status_code == 201
    assert response.json()["product_id"] == str(product.id)


async def test_creating_with_a_product_of_another_ingredient_is_409(
    logged_client, db_session, dispensa
):
    """Il difetto del brief: un prodotto di pomodoro non entra come yogurt."""
    product = Product(ingredient_id=dispensa["pomodoro"].id, name="Pomodori pelati",
                      source="openfoodfacts")
    db_session.add(product)
    await db_session.flush()

    response = await logged_client.post("/api/v1/pantry", json={
        "ingredient_id": str(dispensa["yogurt"].id), "product_id": str(product.id),
        "status": "available",
    })
    assert response.status_code == 409
    assert "altro ingrediente" in response.json()["detail"]


async def test_creating_with_a_dangling_product_is_404_not_500(logged_client, dispensa):
    """Un prodotto che non esiste resta un 404, come già per l'ingrediente."""
    import uuid

    response = await logged_client.post("/api/v1/pantry", json={
        "ingredient_id": str(dispensa["yogurt"].id), "product_id": str(uuid.uuid4()),
        "status": "available",
    })
    assert response.status_code == 404
    assert "inesistente" in response.json()["detail"]


async def test_patch_changes_status_and_stamps_the_time(logged_client, db_session, dispensa):
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()
    before = item.status_changed_at

    response = await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"status": "low"})
    assert response.status_code == 200
    assert response.json()["status"] == "low"
    await db_session.refresh(item)
    assert item.status_changed_at >= before


async def test_patch_rejects_an_invalid_status(logged_client, db_session, dispensa):
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()
    response = await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"status": "mezzo"})
    assert response.status_code == 422


async def test_availability_endpoint_returns_a_map(logged_client, db_session, dispensa):
    db_session.add(PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.LOW))
    await db_session.flush()
    body = (await logged_client.get("/api/v1/pantry/availability")).json()
    assert body[str(dispensa["pomodoro"].id)] == "low"


async def test_creating_with_a_dangling_ingredient_is_404_not_500(logged_client):
    """Un id che non esiste più (cache della PWA) deve dare 404, non un muro."""
    import uuid

    response = await logged_client.post("/api/v1/pantry", json={
        "ingredient_id": str(uuid.uuid4()), "status": "available",
    })
    assert response.status_code == 404
    assert "inesistente" in response.json()["detail"]


async def test_un_archiviato_torna_in_dispensa(logged_client, db_session, dispensa):
    """L'annulla della X rossa. Archiviare era già reversibile, mancava come chiederlo."""
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()

    await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"archived": True})
    elenco = (await logged_client.get("/api/v1/pantry")).json()
    assert all(voce["id"] != str(item.id) for voce in elenco)

    risposta = await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"archived": False})
    assert risposta.status_code == 200
    elenco = (await logged_client.get("/api/v1/pantry")).json()
    assert any(voce["id"] == str(item.id) for voce in elenco)


async def test_cambiare_stato_non_disarchivia_per_sbaglio(logged_client, db_session, dispensa):
    """`archived` era un bool con default False: ogni PATCH ne portava uno.

    Ora è annullabile, e «non l'ho detto» deve restare diverso da «mettilo a falso».
    Senza questa distinzione una PATCH di solo stato riporterebbe in dispensa una
    voce che l'utente aveva tolto.
    """
    from datetime import UTC, datetime

    item = PantryItem(
        ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE,
        archived_at=datetime.now(UTC),
    )
    db_session.add(item)
    await db_session.flush()

    risposta = await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"status": "low"})
    assert risposta.status_code == 200
    await db_session.refresh(item)
    assert item.archived_at is not None


async def test_una_patch_vuota_resta_un_400(logged_client, db_session, dispensa):
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()

    risposta = await logged_client.patch(f"/api/v1/pantry/{item.id}", json={})
    assert risposta.status_code == 400


async def test_disarchiviare_una_voce_inesistente_e_404(logged_client):
    import uuid

    risposta = await logged_client.patch(
        f"/api/v1/pantry/{uuid.uuid4()}", json={"archived": False}
    )
    assert risposta.status_code == 404


@pytest.mark.parametrize(
    "posizione, stato_atteso",
    [(0, "finished"), (15, "low"), (30, "low"), (31, "available"), (100, "available")],
)
async def test_la_posizione_arriva_con_lo_stato_gia_ricavato(
    logged_client, db_session, dispensa, posizione, stato_atteso
):
    """Il client manda dove ha lasciato il dito; lo stato lo decide il dominio.

    È la riga che tiene la regola dalla parte giusta: se lo stato lo calcolasse il
    frontend, due schermi potrebbero non essere d'accordo su cosa vuol dire «quasi
    finito», e la cucinabilità delle ricette dipenderebbe da quale dei due ha
    scritto per ultimo.
    """
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()

    risposta = await logged_client.patch(
        f"/api/v1/pantry/{item.id}", json={"fill_percent": posizione}
    )
    assert risposta.status_code == 200
    assert risposta.json()["fill_percent"] == posizione
    assert risposta.json()["status"] == stato_atteso


async def test_una_posizione_fuori_scala_e_422(logged_client, db_session, dispensa):
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()
    risposta = await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"fill_percent": 101})
    assert risposta.status_code == 422


async def test_cambiare_lo_stato_a_mano_azzera_la_posizione(
    logged_client, db_session, dispensa
):
    """Una posizione lasciata lì sarebbe una bugia.

    Il foglio di cottura cambia lo stato senza toccare nessun cursore: se la
    posizione restasse a 80 mentre lo stato è «finito», la dispensa mostrerebbe un
    barattolo pieno per qualcosa che non c'è più. Sconosciuta è la verità.
    """
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()
    await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"fill_percent": 80})

    risposta = await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"status": "finished"})
    assert risposta.json()["status"] == "finished"
    assert risposta.json()["fill_percent"] is None


async def test_la_rotta_di_rientro_scrive_in_lista_e_lo_dice(
    logged_client, db_session, dispensa
):
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.FINISHED)
    db_session.add(item)
    await db_session.flush()

    risposta = await logged_client.post(f"/api/v1/pantry/{item.id}/restock")
    assert risposta.status_code == 200
    assert risposta.json() == {"added": True}

    lista = (await logged_client.get("/api/v1/shopping-list")).json()
    assert [voce["raw_text"] for voce in lista] == ["pomodoro"]

    # una seconda volta non duplica, e lo dice invece di fingere di aver scritto
    ancora = await logged_client.post(f"/api/v1/pantry/{item.id}/restock")
    assert ancora.json() == {"added": False}


async def test_il_rientro_di_una_voce_inesistente_e_404(logged_client):
    import uuid

    risposta = await logged_client.post(f"/api/v1/pantry/{uuid.uuid4()}/restock")
    assert risposta.status_code == 404


async def test_scrivere_e_cancellare_la_scadenza(db_session, dispensa):
    """`None` non è «non l'ho detto», è «cancellala»: chi ha battuto male una data
    deve poterla togliere, non solo cambiarla."""
    from datetime import date

    from app.repositories.pantry import set_expiry

    item = PantryItem(ingredient_id=dispensa["yogurt"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()

    await set_expiry(db_session, item.id, date(2026, 9, 28))
    assert item.expires_on == date(2026, 9, 28)

    await set_expiry(db_session, item.id, None)
    assert item.expires_on is None


async def test_la_scadenza_non_e_un_cambio_di_stato(db_session, dispensa):
    """`status_changed_at` risponde a «da quanto è in questo stato»: muoverlo qui
    direbbe che qualcosa è cambiato nella disponibilità, che è precisamente quel che
    D5 ha deciso non succeda."""
    from datetime import date

    from app.repositories.pantry import set_expiry

    item = PantryItem(ingredient_id=dispensa["yogurt"].id, status=PantryStatus.LOW)
    db_session.add(item)
    await db_session.flush()
    prima = item.status_changed_at

    await set_expiry(db_session, item.id, date(2026, 9, 28))

    assert item.status_changed_at == prima
    assert item.status == PantryStatus.LOW


async def test_scadenza_su_una_voce_inesistente(db_session):
    import uuid as _uuid
    from datetime import date

    import pytest as _pytest

    from app.repositories.pantry import set_expiry

    with _pytest.raises(KeyError):
        await set_expiry(db_session, _uuid.uuid4(), date(2026, 9, 28))


async def test_una_voce_entra_gia_con_la_sua_scadenza(db_session, dispensa):
    """La strada dell'ingresso: la data si scrive con il barattolo in mano, quindi
    `add_pantry_item` deve saperla accettare — è il punto unico da cui passano sia la
    scorta diretta sia la sistemazione della spesa."""
    from datetime import date

    from app.repositories.pantry import add_pantry_item

    item = await add_pantry_item(
        db_session, ingredient_id=dispensa["yogurt"].id, expires_on=date(2026, 10, 5)
    )

    assert item.expires_on == date(2026, 10, 5)


async def test_la_dispensa_manda_la_data_e_il_verdetto(logged_client, db_session, dispensa):
    """Due campi e non uno: la data serve a mostrarla e a riaprirla in correzione, il
    verdetto a colorarla. Con la sola data il browser dovrebbe rifare il conto dei
    sette giorni, che è esattamente quel che la spec §4 evita; con il solo verdetto si
    perderebbe quel che l'utente ha scritto."""
    from datetime import timedelta

    from app.domain.rules import today_in_pantry

    oggi = today_in_pantry()
    db_session.add_all([
        PantryItem(ingredient_id=dispensa["yogurt"].id, status=PantryStatus.AVAILABLE,
                   expires_on=oggi + timedelta(days=3)),
        PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE,
                   expires_on=oggi - timedelta(days=1)),
        PantryItem(ingredient_id=dispensa["aglio"].id, status=PantryStatus.AVAILABLE),
    ])
    await db_session.flush()
    await db_session.commit()

    risposta = await logged_client.get("/api/v1/pantry")
    assert risposta.status_code == 200
    per_nome = {v["ingredient_name"]: v for v in risposta.json()}

    assert per_nome["yogurt greco"]["expiry"] == "soon"
    assert per_nome["yogurt greco"]["expires_on"] == (oggi + timedelta(days=3)).isoformat()
    assert per_nome["pomodoro"]["expiry"] == "expired"
    assert per_nome["aglio"]["expiry"] is None
    assert per_nome["aglio"]["expires_on"] is None


async def test_una_voce_scaduta_resta_disponibile(logged_client, db_session, dispensa):
    """Il cuore di D5. Se questo test diventa rosso, qualcuno ha fatto entrare la
    scadenza nel giudizio di disponibilità, e una ricetta ha smesso di essere
    cucinabile di notte senza che nessuno abbia toccato niente."""
    from datetime import timedelta

    from app.domain.rules import today_in_pantry

    db_session.add(
        PantryItem(ingredient_id=dispensa["yogurt"].id, status=PantryStatus.AVAILABLE,
                   expires_on=today_in_pantry() - timedelta(days=30))
    )
    await db_session.flush()
    await db_session.commit()

    risposta = await logged_client.get("/api/v1/pantry/availability")
    assert risposta.json()[str(dispensa["yogurt"].id)] == "available"


async def test_patch_cancella_la_scadenza_con_null(logged_client, db_session, dispensa):
    """Il test che difende il difetto più probabile di tutto questo lavoro. Scritto
    con `payload.expires_on is not None`, il ramo sembra funzionare — scrive le date
    e non cancella mai niente — e un corpo `{"expires_on": null}` finisce nell'`else`,
    che risponde «niente da modificare». Cioè la cancellazione fallisce dicendo che
    non c'era niente da fare."""
    from datetime import date

    item = PantryItem(ingredient_id=dispensa["yogurt"].id, status=PantryStatus.AVAILABLE,
                      expires_on=date(2026, 9, 28))
    db_session.add(item)
    await db_session.flush()
    await db_session.commit()

    risposta = await logged_client.patch(f"/api/v1/pantry/{item.id}",
                                         json={"expires_on": None})

    assert risposta.status_code == 200
    assert risposta.json()["expires_on"] is None
    assert risposta.json()["expiry"] is None


async def test_patch_scrive_la_scadenza(logged_client, db_session, dispensa):
    item = PantryItem(ingredient_id=dispensa["yogurt"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()
    await db_session.commit()

    risposta = await logged_client.patch(f"/api/v1/pantry/{item.id}",
                                         json={"expires_on": "2026-09-28"})

    assert risposta.status_code == 200
    assert risposta.json()["expires_on"] == "2026-09-28"


async def test_patch_vuota_resta_un_400(logged_client, db_session, dispensa):
    """Il campo nuovo non deve trasformare «non hai chiesto niente» in un successo
    muto: un corpo `{}` non nomina `expires_on`, quindi non è una cancellazione."""
    item = PantryItem(ingredient_id=dispensa["yogurt"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()
    await db_session.commit()

    assert (await logged_client.patch(f"/api/v1/pantry/{item.id}", json={})).status_code == 400
