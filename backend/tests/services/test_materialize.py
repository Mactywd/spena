import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.domain.rules import IngredientRole
from app.repositories.imports import store_page
from app.repositories.recipes import get_recipe
from app.services.recipe_import.materialize import materialize_ready


def payload(title: str, ingredients: list[tuple[str, str, str]]) -> dict:
    return {
        "title": title, "description": "Breve", "instructions": "Cuoci.",
        "servings": 4, "category": "Primi piatti",
        "image_url": "https://esempio/foto.jpg", "prep_minutes": 10, "cook_minutes": 15,
        "ingredients": [
            {"key": key, "name": name, "quantity_text": quantity}
            for key, name, quantity in ingredients
        ],
        "nutrition": {"calories": "464,4 kcal"},
    }


@pytest_asyncio.fixture
async def anagrafica(db_session):
    """Due ingredienti e i termini già decisi: questo task parte da lì."""
    farina = Ingredient(
        name="farina", display_name="Farina", category=IngredientCategory.CEREALI
    )
    sale = Ingredient(name="sale", display_name="Sale", category=IngredientCategory.SPEZIE)
    db_session.add_all([farina, sale])
    await db_session.flush()

    db_session.add_all([
        ImportTerm(source=GIALLOZAFFERANO, term_key="farina-00", display_name="Farina 00",
                   occurrences=1, decision=TermDecision.MAPPED, ingredient_id=farina.id,
                   decided_by="human"),
        ImportTerm(source=GIALLOZAFFERANO, term_key="farina-0", display_name="Farina 0",
                   occurrences=1, decision=TermDecision.MAPPED, ingredient_id=farina.id,
                   decided_by="human"),
        ImportTerm(source=GIALLOZAFFERANO, term_key="sale-fino", display_name="Sale fino",
                   occurrences=1, decision=TermDecision.MAPPED, ingredient_id=sale.id,
                   decided_by="human"),
        ImportTerm(source=GIALLOZAFFERANO, term_key="acqua", display_name="Acqua",
                   occurrences=1, decision=TermDecision.IGNORED, decided_by="human"),
        ImportTerm(source=GIALLOZAFFERANO, term_key="bottarga", display_name="Bottarga",
                   occurrences=1, decision=TermDecision.PENDING),
    ])
    await db_session.flush()
    return {"farina": farina, "sale": sale}


async def test_una_ricetta_coi_termini_decisi_entra(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload=payload("Pane", [("farina-00", "Farina 00", "500 g"),
                                 ("sale-fino", "Sale fino", "q.b.")]),
    )

    esito = await materialize_ready(db_session)

    assert (esito.created, esito.skipped) == (1, 0)
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    assert ricetta.title == "Pane"
    assert ricetta.source == "dataset"
    assert ricetta.source_ref == "https://esempio/pane.html"
    assert ricetta.category == "Primi piatti"
    assert ricetta.prep_minutes == 10
    assert ricetta.cook_minutes == 15
    assert ricetta.image_url == "https://esempio/foto.jpg"


async def test_la_pagina_resta_legata_alla_ricetta_che_ha_prodotto(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload=payload("Pane", [("farina-00", "Farina 00", "500 g")]),
    )

    await materialize_ready(db_session)

    pagina = (await db_session.execute(select(RecipeImport))).scalars().one()
    assert pagina.state == ImportState.IMPORTED
    assert pagina.recipe_id is not None


async def test_il_ruolo_viene_dalla_regola(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload=payload("Pane", [("farina-00", "Farina 00", "500 g"),
                                 ("sale-fino", "Sale fino", "q.b.")]),
    )

    await materialize_ready(db_session)

    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    dettaglio = await get_recipe(db_session, ricetta.id)
    ruoli = {line.ingredient.name: line.role for line in dettaglio.ingredients}
    assert ruoli == {"farina": IngredientRole.PRIMARY, "sale": IngredientRole.SECONDARY}


async def test_il_ruolo_corretto_a_mano_vince_sulla_regola(db_session, anagrafica):
    termine = (
        await db_session.execute(
            select(ImportTerm).where(ImportTerm.term_key == "farina-00")
        )
    ).scalars().one()
    termine.role_override = IngredientRole.SECONDARY
    await db_session.flush()
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload=payload("Pane", [("farina-00", "Farina 00", "500 g")]),
    )

    await materialize_ready(db_session)

    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    dettaglio = await get_recipe(db_session, ricetta.id)
    assert dettaglio.ingredients[0].role == IngredientRole.SECONDARY


async def test_due_righe_sullo_stesso_ingrediente_diventano_una(db_session, anagrafica):
    """Senza il collasso l'inserimento fallirebbe sul vincolo di unicità."""
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/torta.html",
        payload=payload("Torta", [("farina-00", "Farina 00", "500 g"),
                                  ("farina-0", "Farina 0", "50 g")]),
    )

    esito = await materialize_ready(db_session)

    assert esito.created == 1
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    dettaglio = await get_recipe(db_session, ricetta.id)
    assert len(dettaglio.ingredients) == 1
    assert dettaglio.ingredients[0].quantity_text == "500 g + 50 g"


async def test_nel_collasso_il_ruolo_piu_forte_vince(db_session, anagrafica):
    """La farina per la frolla è principale anche se per la spolverata è «q.b.»."""
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/torta.html",
        payload=payload("Torta", [("farina-0", "Farina 0", "q.b."),
                                  ("farina-00", "Farina 00", "500 g")]),
    )

    await materialize_ready(db_session)

    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    dettaglio = await get_recipe(db_session, ricetta.id)
    assert dettaglio.ingredients[0].role == IngredientRole.PRIMARY


async def test_nel_collasso_il_ruolo_piu_forte_vince_indipendentemente_dall_ordine(db_session, anagrafica):
    """PRIMARY vince anche quando la riga principale arriva prima della secondaria."""
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/torta2.html",
        payload=payload("Torta", [("farina-00", "Farina 00", "500 g"),
                                  ("farina-0", "Farina 0", "q.b.")]),
    )

    await materialize_ready(db_session)

    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    dettaglio = await get_recipe(db_session, ricetta.id)
    assert dettaglio.ingredients[0].role == IngredientRole.PRIMARY


async def test_un_termine_ignorato_non_produce_una_riga(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload=payload("Pane", [("farina-00", "Farina 00", "500 g"),
                                 ("acqua", "Acqua", "300 g")]),
    )

    esito = await materialize_ready(db_session)

    assert esito.created == 1
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    dettaglio = await get_recipe(db_session, ricetta.id)
    assert [line.ingredient.name for line in dettaglio.ingredients] == ["farina"]


async def test_una_ricetta_con_un_termine_ancora_da_decidere_aspetta(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/bottarga.html",
        payload=payload("Spaghetti alla bottarga", [("farina-00", "Farina 00", "500 g"),
                                                    ("bottarga", "Bottarga", "20 g")]),
    )

    esito = await materialize_ready(db_session)

    assert (esito.created, esito.skipped) == (0, 0)
    pagina = (await db_session.execute(select(RecipeImport))).scalars().one()
    assert pagina.state == ImportState.PENDING


async def test_una_ricetta_che_resterebbe_vuota_si_scarta_col_motivo(db_session, anagrafica):
    """Una ricetta senza ingredienti è sempre cucinabile: è la bugia peggiore."""
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/acqua.html",
        payload=payload("Acqua bollente", [("acqua", "Acqua", "1 l")]),
    )

    esito = await materialize_ready(db_session)

    assert (esito.created, esito.skipped) == (0, 1)
    pagina = (await db_session.execute(select(RecipeImport))).scalars().one()
    assert pagina.state == ImportState.SKIPPED
    assert "senza" in pagina.skipped_reason
    assert (await db_session.execute(select(Recipe))).scalars().all() == []


async def test_una_ricetta_cancellata_non_viene_ricreata(db_session, anagrafica):
    """`recipe_id` va a NULL, ma lo stato resta `imported`: è lo stato a dire
    «questa pagina è già stata importata una volta»."""
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload=payload("Pane", [("farina-00", "Farina 00", "500 g")]),
    )
    await materialize_ready(db_session)
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    await db_session.delete(ricetta)
    await db_session.flush()

    esito = await materialize_ready(db_session)

    assert (esito.created, esito.skipped) == (0, 0)
    assert (await db_session.execute(select(Recipe))).scalars().all() == []


async def test_la_materializzazione_e_rieseguibile(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload=payload("Pane", [("farina-00", "Farina 00", "500 g")]),
    )

    await materialize_ready(db_session)
    seconda = await materialize_ready(db_session)

    assert (seconda.created, seconda.skipped) == (0, 0)
    assert len((await db_session.execute(select(Recipe))).scalars().all()) == 1


async def test_una_pagina_con_riga_non_alimentare_si_scarta_senza_fermare_il_lotto(
    db_session, anagrafica
):
    """`create_recipe` è l'ultima linea di difesa e solleva `NonFoodInRecipe`: senza
    una protezione per pagina, quella riga avrebbe fatto fallire con un errore non
    gestito la materializzazione di tutto il lotto pronto, buona ricetta compresa —
    il vicolo cieco che questo task chiude.
    """
    sapone = Ingredient(
        name="sapone", display_name="Sapone", category=IngredientCategory.IGIENE
    )
    db_session.add(sapone)
    await db_session.flush()
    db_session.add(
        ImportTerm(
            source=GIALLOZAFFERANO, term_key="detersivo", display_name="Detersivo",
            occurrences=1, decision=TermDecision.MAPPED, ingredient_id=sapone.id,
            decided_by="human",
        )
    )
    await db_session.flush()
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/torta-al-sapone.html",
        payload=payload("Torta al sapone", [("farina-00", "Farina 00", "500 g"),
                                             ("detersivo", "Detersivo", "1 tappo")]),
    )
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload=payload("Pane", [("farina-00", "Farina 00", "500 g")]),
    )

    esito = await materialize_ready(db_session)

    assert (esito.created, esito.skipped) == (1, 1)
    pagina_cattiva = (
        await db_session.execute(
            select(RecipeImport).where(
                RecipeImport.url == "https://esempio/torta-al-sapone.html"
            )
        )
    ).scalars().one()
    assert pagina_cattiva.state == ImportState.SKIPPED
    assert "Sapone" in pagina_cattiva.skipped_reason
    ricette = (await db_session.execute(select(Recipe))).scalars().all()
    assert [r.title for r in ricette] == ["Pane"]


async def test_una_categoria_troppo_lunga_viene_troncata(db_session, anagrafica):
    """Una categoria più lunga di 60 caratteri viene troncata senza errore."""
    long_category = "Categoria molto lunga che sicuramente supera il limite di sessanta caratteri"
    assert len(long_category) > 60

    payloaded = payload("Ricetta", [("farina-00", "Farina 00", "500 g")])
    payloaded["category"] = long_category
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/ricetta-lunga.html",
        payload=payloaded,
    )

    esito = await materialize_ready(db_session)

    assert esito.created == 1
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    assert len(ricetta.category) == 60
    assert ricetta.category == long_category[:60]


async def test_il_costo_della_pagina_arriva_sulla_ricetta(db_session, anagrafica):
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload={**payload("Pane", [("farina-00", "Farina 00", "500 g")]), "cost": 2},
    )
    await materialize_ready(db_session)
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    assert ricetta.cost == 2


async def test_una_pagina_salvata_prima_del_costo_resta_senza(db_session, anagrafica):
    """Le pagine scaricate prima di R9 non hanno la chiave: niente costo, non un errore."""
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload=payload("Pane", [("farina-00", "Farina 00", "500 g")]),
    )
    await materialize_ready(db_session)
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    assert ricetta.cost is None


async def test_un_costo_fuori_scala_nel_payload_non_ferma_il_lotto(db_session, anagrafica):
    """Il CHECK lo rifiuterebbe facendo fallire tutte le pagine della chiamata."""
    await store_page(
        db_session, source=GIALLOZAFFERANO, url="https://esempio/pane.html",
        payload={**payload("Pane", [("farina-00", "Farina 00", "500 g")]), "cost": 9},
    )
    await materialize_ready(db_session)
    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    assert ricetta.cost is None
