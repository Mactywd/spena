import httpx
import respx
from sqlalchemy import select

from app.cli.import_gz import run_import
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportState, RecipeImport
from app.services.recipe_import.giallozafferano import RECIPE_SITEMAP, build_client

PAGINA = """<html><head>
<script type="application/ld+json">
{"@type": "Recipe", "name": "TITOLO", "description": "Breve",
 "recipeYield": 2, "prepTime": "PT5M", "cookTime": "PT10M",
 "recipeCategory": "Primi piatti",
 "recipeInstructions": ["Cuoci 1 ."]}
</script></head><body>
<dl class="gz-list-ingredients">
<dd class="gz-ingredient"><a href="/ricette-con-la-Pasta/">Pasta</a><span> 320 g </span></dd>
</dl></body></html>"""

SITEMAP = """<?xml version="1.0"?><urlset>
 <url><loc>https://ricette.giallozafferano.it/Uno.html</loc></url>
 <url><loc>https://ricette.giallozafferano.it/Due.html</loc></url>
 <url><loc>https://ricette.giallozafferano.it/Tre.html</loc></url>
</urlset>"""


async def nessuna_pausa(_seconds: float) -> None:
    """La suite non dorme: la cortesia si verifica contando le chiamate."""


@respx.mock
async def test_scarica_fino_al_limite_e_non_oltre(db_session):
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))
    for nome in ("Uno", "Due", "Tre"):
        respx.get(f"https://ricette.giallozafferano.it/{nome}.html").mock(
            return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", nome))
        )

    async with build_client() as client:
        esito = await run_import(db_session, limit=2, client=client, sleep=nessuna_pausa)

    assert esito.taken == 2
    pagine = (await db_session.execute(select(RecipeImport))).scalars().all()
    assert {p.url for p in pagine} == {
        "https://ricette.giallozafferano.it/Uno.html",
        "https://ricette.giallozafferano.it/Due.html",
    }


@respx.mock
async def test_aspetta_fra_una_pagina_e_l_altra(db_session):
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))
    for nome in ("Uno", "Due", "Tre"):
        respx.get(f"https://ricette.giallozafferano.it/{nome}.html").mock(
            return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", nome))
        )
    pause: list[float] = []

    async def registra(seconds: float) -> None:
        pause.append(seconds)

    async with build_client() as client:
        await run_import(db_session, limit=3, client=client, sleep=registra)

    assert len(pause) == 3
    assert all(seconds >= 1.0 for seconds in pause)


@respx.mock
async def test_una_pagina_gia_presa_non_si_riscarica(db_session):
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))
    chiamate = respx.get("https://ricette.giallozafferano.it/Uno.html").mock(
        return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", "Uno"))
    )
    respx.get("https://ricette.giallozafferano.it/Due.html").mock(
        return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", "Due"))
    )

    async with build_client() as client:
        await run_import(db_session, limit=1, client=client, sleep=nessuna_pausa)
        await run_import(db_session, limit=1, client=client, sleep=nessuna_pausa)

    assert chiamate.call_count == 1


@respx.mock
async def test_una_pagina_illeggibile_si_conserva_col_motivo(db_session):
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))
    respx.get("https://ricette.giallozafferano.it/Uno.html").mock(
        return_value=httpx.Response(200, text="<html>niente dati strutturati</html>")
    )

    async with build_client() as client:
        esito = await run_import(db_session, limit=1, client=client, sleep=nessuna_pausa)

    assert esito.skipped == 1
    pagina = (await db_session.execute(select(RecipeImport))).scalars().one()
    assert pagina.state == ImportState.SKIPPED
    assert pagina.skipped_reason


@respx.mock
async def test_due_rifiuti_di_fila_fermano_il_giro(db_session):
    """Insistere contro un 429 è la cosa da non fare, e il lavoro fatto non si perde."""
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))
    respx.get("https://ricette.giallozafferano.it/Uno.html").mock(
        return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", "Uno"))
    )
    respx.get("https://ricette.giallozafferano.it/Due.html").mock(
        return_value=httpx.Response(429)
    )
    terza = respx.get("https://ricette.giallozafferano.it/Tre.html").mock(
        return_value=httpx.Response(429)
    )

    async with build_client() as client:
        esito = await run_import(db_session, limit=3, client=client, sleep=nessuna_pausa)

    assert esito.stopped_early is True
    assert esito.taken == 1
    # la terza viene chiesta (è il secondo rifiuto, quello che fa scattare il freno)
    # e nessuna quarta: il giro si ferma lì
    assert terza.call_count == 1
    pagine = (await db_session.execute(select(RecipeImport))).scalars().all()
    assert [p.url for p in pagine] == ["https://ricette.giallozafferano.it/Uno.html"]


@respx.mock
async def test_lo_scarico_sincronizza_i_termini_e_materializza(db_session):
    """Un giro completo: con l'anagrafica che conosce già `pasta`, la ricetta entra
    senza nessuna revisione."""
    db_session.add(
        Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    )
    await db_session.flush()
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))
    respx.get("https://ricette.giallozafferano.it/Uno.html").mock(
        return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", "Uno"))
    )

    async with build_client() as client:
        await run_import(db_session, limit=1, client=client, sleep=nessuna_pausa)

    from app.db.models.recipe import Recipe

    ricetta = (await db_session.execute(select(Recipe))).scalars().one()
    assert ricetta.title == "Uno"
    assert ricetta.source_ref == "https://ricette.giallozafferano.it/Uno.html"


@respx.mock
async def test_sitemap_irraggiungibile_fermando_presto(db_session):
    """Se la sitemap non risponde (503), il giro si ferma senza chiedere pagine."""
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(503))
    # Nessun mock per le pagine: se ne viene richiesta una, il test fallisce
    pagine = respx.get("https://ricette.giallozafferano.it/Uno.html")

    async with build_client() as client:
        esito = await run_import(db_session, limit=10, client=client, sleep=nessuna_pausa)

    assert esito.taken == 0
    assert esito.skipped == 0
    assert esito.stopped_early is True
    assert pagine.call_count == 0
