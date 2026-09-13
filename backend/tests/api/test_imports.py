import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.recipe import Recipe
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.repositories.imports import store_page
from app.services.recipe_import.terms import sync_terms


def payload(title: str, ingredients: list[tuple[str, str, str]]) -> dict:
    return {
        "title": title, "description": "Breve", "instructions": "Cuoci.",
        "servings": 2, "category": "Primi piatti", "image_url": None,
        "prep_minutes": 5, "cook_minutes": 10,
        "ingredients": [
            {"key": key, "name": name, "quantity_text": quantity}
            for key, name, quantity in ingredients
        ],
        "nutrition": None,
    }


@pytest_asyncio.fixture
async def in_attesa(db_session):
    """Una ricetta scaricata che aspetta un solo termine sconosciuto."""
    db_session.add(
        Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    )
    await db_session.flush()
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/bottarga.html",
        payload=payload("Spaghetti alla bottarga", [
            ("ricette-con-la-Pasta", "Pasta", "320 g"),
            ("ricette-con-la-Bottarga", "Bottarga", "20 g"),
        ]),
    )
    await sync_terms(db_session)


async def test_lo_stato_dice_dove_sta_l_import(logged_client, in_attesa):
    response = await logged_client.get("/api/v1/imports/status")

    assert response.status_code == 200
    assert response.json() == {
        "fetched": 1, "pending_recipes": 1, "imported": 0, "skipped": 0,
        "pending_terms": 1,
    }


async def test_senza_sessione_non_si_guarda_niente(client):
    assert (await client.get("/api/v1/imports/status")).status_code == 401


async def test_la_coda_porta_il_suggerimento_e_i_titoli_in_attesa(logged_client, in_attesa):
    response = await logged_client.get("/api/v1/imports/terms")

    assert response.status_code == 200
    coda = response.json()
    assert [voce["display_name"] for voce in coda] == ["Bottarga"]
    assert coda[0]["occurrences"] == 1
    assert coda[0]["waiting_titles"] == ["Spaghetti alla bottarga"]


@pytest_asyncio.fixture
async def termine_senza_aggancio(db_session):
    """Un termine che resta in attesa perché, al momento della sincronizzazione,
    l'anagrafica non ha ancora l'ingrediente corrispondente: niente auto-decide,
    niente match certo da trovare finché non aggiungiamo l'ingrediente dopo."""
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pomodoro.html",
        payload=payload("Pasta al pomodoro", [
            ("ricette-con-il-Pomodoro", "Pomodoro", "2"),
        ]),
    )
    await sync_terms(db_session)


async def test_un_nome_coincidente_con_l_anagrafica_porta_un_suggerimento_certo(
    logged_client, db_session, termine_senza_aggancio
):
    """`certain` è ciò che impedisce a una somiglianza incerta di presentarsi come
    una risposta già confermata ("Pinoli" che diventa alias di "pisello" in
    silenzio): nessun test qui asseriva `suggestion` affatto, nemmeno nel caso
    opposto, la vera coincidenza esatta. L'ingrediente arriva dopo che il termine è
    già in coda, cosa che una rotta che ricalcola il suggerimento a ogni lettura (e
    non solo alla sincronizzazione) deve comunque cogliere."""
    pomodoro = Ingredient(
        name="pomodoro", display_name="Pomodoro", category=IngredientCategory.VERDURA
    )
    db_session.add(pomodoro)
    await db_session.flush()

    response = await logged_client.get("/api/v1/imports/terms")

    assert response.status_code == 200
    coda = response.json()
    assert coda[0]["display_name"] == "Pomodoro"
    assert coda[0]["suggestion"] == {
        "ingredient_id": str(pomodoro.id), "name": "pomodoro", "certain": True,
    }


@pytest_asyncio.fixture
async def termine_somigliante(db_session):
    """Un termine abbastanza simile a un ingrediente esistente da proporsi, ma non
    identico: resta in attesa da sé, perché solo una coincidenza esatta auto-decide
    in `sync_terms`."""
    db_session.add(
        Ingredient(name="pomodoro", display_name="Pomodoro", category=IngredientCategory.VERDURA)
    )
    await db_session.flush()
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pomodorini.html",
        payload=payload("Insalata di pomodorini", [
            ("ricette-con-i-Pomodorini", "Pomodorini", "200 g"),
        ]),
    )
    await sync_terms(db_session)


async def test_una_somiglianza_incerta_porta_un_suggerimento_non_certo(
    logged_client, db_session, termine_somigliante
):
    pomodoro = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "pomodoro"))
    ).scalars().one()

    response = await logged_client.get("/api/v1/imports/terms")

    assert response.status_code == 200
    coda = response.json()
    assert coda[0]["display_name"] == "Pomodorini"
    assert coda[0]["suggestion"] == {
        "ingredient_id": str(pomodoro.id), "name": "pomodoro", "certain": False,
    }


async def test_collegare_un_termine_sblocca_le_ricette_e_lo_dice(
    logged_client, db_session, in_attesa
):
    pasta = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "pasta"))
    ).scalars().one()
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    response = await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "map", "ingredient_id": str(pasta.id)},
    )

    assert response.status_code == 200
    assert response.json() == {"unlocked": 1, "remaining_terms": 0}
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    assert ricetta.title == "Spaghetti alla bottarga"


async def test_collegare_scrive_l_alias_in_anagrafica(logged_client, db_session, in_attesa):
    """È ciò che fa valere la decisione per sempre, e che insegna il nome anche
    all'autocomplete della lista della spesa."""
    pasta = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "pasta"))
    ).scalars().one()
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "map", "ingredient_id": str(pasta.id)},
    )

    alias = (
        await db_session.execute(
            select(IngredientAlias).where(IngredientAlias.alias == "bottarga")
        )
    ).scalars().all()
    assert [a.ingredient_id for a in alias] == [pasta.id]
    assert alias[0].source == "import"


async def test_un_alias_che_esiste_gia_altrove_non_si_duplica(
    logged_client, db_session, in_attesa
):
    """Lo stesso alias su due ingredienti è un autocomplete con due risposte."""
    altro = Ingredient(
        name="muggine", display_name="Muggine", category=IngredientCategory.PESCE
    )
    altro.aliases.append(IngredientAlias(alias="bottarga", source="import"))
    db_session.add(altro)
    await db_session.flush()
    pasta = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "pasta"))
    ).scalars().one()
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    response = await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "map", "ingredient_id": str(pasta.id)},
    )

    assert response.status_code == 200
    alias = (
        await db_session.execute(
            select(IngredientAlias).where(IngredientAlias.alias == "bottarga")
        )
    ).scalars().all()
    assert [a.ingredient_id for a in alias] == [altro.id], "l'alias esistente resta dov'è"
    await db_session.refresh(termine)
    assert termine.ingredient_id == pasta.id, "la decisione vale comunque"


async def test_creare_un_ingrediente_nuovo_decide_il_termine(
    logged_client, db_session, in_attesa
):
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    response = await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "create", "name": "bottarga", "display_name": "Bottarga",
              "category": "pesce"},
    )

    assert response.status_code == 200
    nuovo = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "bottarga"))
    ).scalars().one()
    assert nuovo.category == "pesce"
    await db_session.refresh(termine)
    assert termine.ingredient_id == nuovo.id
    assert termine.decided_by == "human"


async def test_creare_un_nome_che_esiste_gia_dice_di_collegare(
    logged_client, db_session, in_attesa
):
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    response = await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "create", "name": "pasta", "display_name": "Pasta",
              "category": "cereali"},
    )

    assert response.status_code == 409
    assert "collega" in response.json()["detail"]


async def test_ignorare_un_termine_lo_toglie_dalla_coda(logged_client, db_session, in_attesa):
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    response = await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision", json={"action": "ignore"}
    )

    assert response.status_code == 200
    assert response.json()["remaining_terms"] == 0
    await db_session.refresh(termine)
    assert termine.decision == TermDecision.IGNORED


async def test_un_termine_inesistente_e_un_404(logged_client, in_attesa):
    response = await logged_client.post(
        "/api/v1/imports/terms/00000000-0000-0000-0000-000000000000/decision",
        json={"action": "ignore"},
    )

    assert response.status_code == 404


async def test_collegare_a_un_ingrediente_inesistente_e_un_404(
    logged_client, db_session, in_attesa
):
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    response = await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "map",
              "ingredient_id": "00000000-0000-0000-0000-000000000000"},
    )

    assert response.status_code == 404


async def test_senza_claude_le_proposte_dicono_di_decidere_a_mano(
    logged_client, db_session, in_attesa, monkeypatch
):
    """La coda resta usabile: è la regola «mai un vicolo cieco»."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()
    try:
        response = await logged_client.post(
            "/api/v1/imports/terms/proposals", json={"term_ids": [str(termine.id)]}
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 503
    assert "a mano" in response.json()["detail"]


async def test_una_decisione_umana_resiste_a_un_nuovo_sync(
    logged_client, db_session, in_attesa
):
    """Una decisione presa qui non deve sparire al prossimo giro di sincronizzazione,
    che gira dopo ogni lotto scaricato."""
    pasta = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "pasta"))
    ).scalars().one()
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.display_name == "Bottarga")
        )
    ).scalars().one()

    await logged_client.post(
        f"/api/v1/imports/terms/{termine.id}/decision",
        json={"action": "map", "ingredient_id": str(pasta.id)},
    )

    await sync_terms(db_session, GIALLOZAFFERANO)

    await db_session.refresh(termine)
    assert termine.decision == TermDecision.MAPPED
    assert termine.ingredient_id == pasta.id
