"""Le rotte dell'anagrafica sul prodotto (S9 §4, §6.4): il caso del parmigiano sotto
«burro», e i due rifiuti del codice a barre con la loro uscita.

Come in `test_registry_ingredients.py`, il mondo si salva con `commit` e si passano id.
"""

import uuid
from datetime import UTC, datetime

import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.domain.rules import PantryStatus

BASE = "/api/v1/products"


@pytest_asyncio.fixture
async def scaffale(db_session):
    burro = Ingredient(name="burro", display_name="Burro", category=IngredientCategory.LATTICINI)
    parmigiano = Ingredient(
        name="parmigiano", display_name="Parmigiano", category=IngredientCategory.LATTICINI
    )
    db_session.add_all([burro, parmigiano])
    await db_session.flush()
    reggiano = Product(
        ingredient_id=burro.id, name="Parmigiano Reggiano 24 mesi", brand="Latteria",
        barcode="8009876543217", source="custom",
    )
    grana = Product(
        ingredient_id=parmigiano.id, name="Grana Padano 200 g", barcode="8001234567897",
        source="custom",
    )
    db_session.add_all([reggiano, grana])
    await db_session.flush()
    attivo = PantryItem(ingredient_id=burro.id, product_id=reggiano.id, status=PantryStatus.AVAILABLE)
    archiviato = PantryItem(
        ingredient_id=burro.id, product_id=reggiano.id, status=PantryStatus.FINISHED,
        archived_at=datetime.now(UTC),
    )
    db_session.add_all([attivo, archiviato])
    await db_session.flush()
    ids = {
        "burro": burro.id, "parmigiano": parmigiano.id, "reggiano": reggiano.id,
        "grana": grana.id, "attivo": attivo.id, "archiviato": archiviato.id,
    }
    await db_session.commit()
    return ids


async def _voce(db_session, item_id) -> PantryItem:
    return (
        await db_session.execute(
            select(PantryItem).where(PantryItem.id == item_id).execution_options(populate_existing=True)
        )
    ).scalar_one()


async def test_la_scheda_dice_ingrediente_codice_e_dispensa_attiva(logged_client, scaffale):
    risposta = await logged_client.get(f"{BASE}/{scaffale['reggiano']}")

    assert risposta.status_code == 200
    corpo = risposta.json()
    assert (corpo["name"], corpo["brand"], corpo["barcode"]) == (
        "Parmigiano Reggiano 24 mesi", "Latteria", "8009876543217",
    )
    assert corpo["valid_checksum"] is True
    assert corpo["ingredient"] == {
        "id": str(scaffale["burro"]), "name": "burro", "display_name": "Burro",
    }
    # l'archiviato non è in dispensa: la scheda mostra quel che si vede
    assert [voce["id"] for voce in corpo["pantry_items"]] == [str(scaffale["attivo"])]


async def test_un_prodotto_che_non_c_e_e_un_404(logged_client):
    assert (await logged_client.get(f"{BASE}/{uuid.uuid4()}")).status_code == 404


async def test_spostarlo_porta_con_se_tutta_la_dispensa(logged_client, db_session, scaffale):
    risposta = await logged_client.patch(
        f"{BASE}/{scaffale['reggiano']}", json={"ingredient_id": str(scaffale["parmigiano"])}
    )

    assert risposta.status_code == 200
    assert risposta.json()["ingredient"]["display_name"] == "Parmigiano"
    assert len(risposta.json()["pantry_items"]) == 1
    for voce in ("attivo", "archiviato"):
        assert (await _voce(db_session, scaffale[voce])).ingredient_id == scaffale["parmigiano"]


async def test_un_codice_gia_preso_e_un_409_e_si_puo_prendere(logged_client, scaffale):
    url = f"{BASE}/{scaffale['reggiano']}"

    rifiuto = await logged_client.patch(url, json={"barcode": "8001234567897"})
    assert rifiuto.status_code == 409
    assert rifiuto.json()["code"] == "barcode_taken"
    assert rifiuto.json()["existing"]["name"] == "Grana Padano 200 g"

    presa = await logged_client.patch(url, json={"barcode": "8001234567897", "take_barcode": True})
    assert presa.status_code == 200
    assert presa.json()["barcode"] == "8001234567897"
    grana = (await logged_client.get(f"{BASE}/{scaffale['grana']}")).json()
    assert grana["barcode"] is None


async def test_un_codice_che_non_torna_e_un_avviso_che_si_supera(logged_client, scaffale):
    url = f"{BASE}/{scaffale['reggiano']}"

    avviso = await logged_client.patch(url, json={"barcode": "8001234567890"})
    assert avviso.status_code == 409
    assert avviso.json()["code"] == "bad_checksum"

    usato = await logged_client.patch(
        url, json={"barcode": "8001234567890", "accept_bad_checksum": True}
    )
    assert usato.status_code == 200
    assert usato.json()["barcode"] == "8001234567890"
    assert usato.json()["valid_checksum"] is False


async def test_null_toglie_il_codice_e_la_marca(logged_client, scaffale):
    risposta = await logged_client.patch(
        f"{BASE}/{scaffale['reggiano']}", json={"barcode": None, "brand": None}
    )

    assert risposta.status_code == 200
    assert risposta.json()["barcode"] is None
    assert risposta.json()["valid_checksum"] is None
    assert risposta.json()["brand"] is None


async def test_il_nome_si_corregge(logged_client, scaffale):
    risposta = await logged_client.patch(
        f"{BASE}/{scaffale['reggiano']}", json={"name": "Parmigiano Reggiano 30 mesi"}
    )
    assert risposta.status_code == 200
    assert risposta.json()["name"] == "Parmigiano Reggiano 30 mesi"


async def test_un_corpo_vuoto_e_un_400(logged_client, scaffale):
    assert (await logged_client.patch(f"{BASE}/{scaffale['reggiano']}", json={})).status_code == 400


async def test_null_sul_nome_e_un_422(logged_client, scaffale):
    """F17: `name` non può mai essere nullo in colonna, quindi un `null` esplicito è
    respinto dallo schema, non preso in silenzio come «nessun cambiamento»."""
    risposta = await logged_client.patch(f"{BASE}/{scaffale['reggiano']}", json={"name": None})
    assert risposta.status_code == 422


async def test_null_sull_ingrediente_e_un_422(logged_client, scaffale):
    risposta = await logged_client.patch(
        f"{BASE}/{scaffale['reggiano']}", json={"ingredient_id": None}
    )
    assert risposta.status_code == 422


async def test_eliminarlo_lascia_la_dispensa_sfusa_e_lo_dice(logged_client, db_session, scaffale):
    risposta = await logged_client.delete(f"{BASE}/{scaffale['reggiano']}")

    assert risposta.status_code == 200
    assert risposta.json() == {"loose_pantry_items": 1}
    assert (await logged_client.get(f"{BASE}/{scaffale['reggiano']}")).status_code == 404
    for voce in ("attivo", "archiviato"):
        riletta = await _voce(db_session, scaffale[voce])
        assert riletta.product_id is None
        assert riletta.ingredient_id == scaffale["burro"]
