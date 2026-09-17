"""Salvare una ricetta che nomina un ingrediente non ancora in anagrafica.

La creazione avviene **al salvataggio**, non alla stesura: una bozza scartata non deve
lasciare ingredienti dietro, e l'anagrafica cresce solo con ciò che una ricetta salvata
usa davvero. Nella stessa transazione, quindi atomica: nessun ingrediente orfano se il
salvataggio fallisce.
"""

from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.repositories.ingredients import create_ingredient
from app.services.ingredient_match import match_name


async def test_una_riga_con_nome_e_categoria_crea_lingrediente(logged_client, db_session):
    payload = {
        "title": "Pasta allo speck",
        "instructions": "1. cuoci",
        "servings": 2,
        "source": "ai",
        "ingredients": [
            {"name": "speck", "category": "carne", "role": "primary", "quantity_text": "100 g"}
        ],
    }
    response = await logged_client.post("/api/v1/recipes", json=payload)
    assert response.status_code == 201

    creato = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "speck"))
    ).scalar_one()
    assert creato.category == "carne"
    assert response.json()["ingredients"][0]["ingredient_name"] == "speck"


async def test_un_nome_che_esiste_gia_si_collega_invece_di_duplicare(logged_client, db_session):
    await create_ingredient(
        db_session, name="speck", display_name="Speck", category=IngredientCategory.CARNE
    )
    payload = {
        "title": "X", "instructions": "1. cuoci", "servings": 2, "source": "ai",
        "ingredients": [{"name": "speck", "category": "pesce", "role": "primary"}],
    }
    response = await logged_client.post("/api/v1/recipes", json=payload)
    assert response.status_code == 201

    quanti = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "speck"))
    ).scalars().all()
    assert len(quanti) == 1
    # la categoria dell'anagrafica vince: il registro è l'autorità, non una bozza
    assert quanti[0].category == "carne"


async def test_una_somiglianza_non_certa_non_si_aggancia_ma_crea(logged_client, db_session):
    """Guardia sulla riga 161: `match.certain and` non è un pleonasmo.

    "pomodorini" è solo un vicino per trigram di "pomodoro" (lo si verifica qui sotto
    con la stessa funzione, non lo si assume), non una coincidenza esatta: deve creare
    un ingrediente nuovo, non agganciarsi in silenzio a quello esistente. È lo stesso
    difetto che rese «Pinoli» un alias permanente di «pisello»: una somiglianza
    presentata come un fatto.
    """
    pomodoro = await create_ingredient(
        db_session, name="pomodoro", display_name="Pomodoro", category=IngredientCategory.VERDURA
    )

    verifica = await match_name(db_session, "pomodorini")
    assert verifica.certain is False
    assert verifica.ingredient_id == pomodoro.id  # è comunque il vicino più simile

    payload = {
        "title": "X", "instructions": "1. cuoci", "servings": 2, "source": "ai",
        "ingredients": [{"name": "pomodorini", "category": "verdura", "role": "primary"}],
    }
    response = await logged_client.post("/api/v1/recipes", json=payload)
    assert response.status_code == 201

    creato = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "pomodorini"))
    ).scalar_one()
    assert creato.id != pomodoro.id


async def test_una_riga_senza_ne_id_ne_nome_e_un_422(logged_client):
    payload = {
        "title": "X", "instructions": "1. cuoci", "servings": 2, "source": "ai",
        "ingredients": [{"role": "primary"}],
    }
    assert (await logged_client.post("/api/v1/recipes", json=payload)).status_code == 422


async def test_un_nome_senza_categoria_e_un_422(logged_client):
    """Senza categoria non si può creare, e indovinarne una popolerebbe il registro
    di «altro» che nessuno correggerà."""
    payload = {
        "title": "X", "instructions": "1. cuoci", "servings": 2, "source": "ai",
        "ingredients": [{"name": "speck", "role": "primary"}],
    }
    assert (await logged_client.post("/api/v1/recipes", json=payload)).status_code == 422


async def test_se_il_salvataggio_fallisce_nessun_ingrediente_resta_orfano(logged_client, db_session):
    """L'atomicità è il motivo per cui la creazione sta dentro la transazione.

    Due righe con lo stesso ingrediente fanno fallire la ricetta con un 409: se la
    creazione fosse fuori transazione, «speck» resterebbe in anagrafica senza che
    nessuna ricetta lo usi.
    """
    payload = {
        "title": "X", "instructions": "1. cuoci", "servings": 2, "source": "ai",
        "ingredients": [
            {"name": "speck", "category": "carne", "role": "primary"},
            {"name": "speck", "category": "carne", "role": "secondary"},
        ],
    }
    response = await logged_client.post("/api/v1/recipes", json=payload)
    assert response.status_code == 409

    trovati = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "speck"))
    ).scalars().all()
    assert trovati == []


async def test_un_nome_che_e_alias_di_una_voce_non_alimentare_non_passa(
    logged_client, db_session
):
    """Il buco vero, e il motivo per cui la guardia sta nell'imbuto.

    Questa riga non *crea* niente — la creazione per nome usa sempre una categoria
    alimentare — ma `match_name` la aggancia alla voce non alimentare tramite il
    suo alias, e senza la guardia la ricetta si salverebbe.
    """
    from app.repositories.ingredients import add_alias, create_ingredient

    sapone = await create_ingredient(
        db_session, name="sapone per le mani", display_name="Sapone per le mani",
        category="igiene",
    )
    await add_alias(db_session, sapone.id, "sapone", source="seed")
    await db_session.commit()

    response = await logged_client.post("/api/v1/recipes", json={
        "title": "Pasta al sapone", "instructions": "1. no", "servings": 2,
        "source": "ai",
        "ingredients": [{"name": "sapone", "category": "condimenti", "role": "primary"}],
    })

    assert response.status_code == 422
    assert "Sapone per le mani" in response.json()["detail"]
