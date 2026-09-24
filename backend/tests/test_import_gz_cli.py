import httpx
import pytest
import respx
from sqlalchemy import select

import app.cli.import_gz as import_gz
from app.cli.import_gz import run_import
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe_import import ImportState, RecipeImport
from app.db.models.unit import Unit
from app.services.recipe_import.giallozafferano import RECIPE_SITEMAP, build_client
from llm_fakes import ScriptedLlm, llm_create, llm_map

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


PAGINA_DUE_INGREDIENTI = """<html><head>
<script type="application/ld+json">
{"@type": "Recipe", "name": "Amatriciana", "description": "Breve",
 "recipeYield": 2, "prepTime": "PT5M", "cookTime": "PT10M",
 "recipeCategory": "Primi piatti",
 "recipeInstructions": ["Cuoci 1 ."]}
</script></head><body>
<dl class="gz-list-ingredients">
<dd class="gz-ingredient"><a href="/ricette-con-i-Rigatoni/">Rigatoni</a><span> 320 g </span></dd>
<dd class="gz-ingredient"><a href="/ricette-con-lo-Speck/">Speck</a><span> 100 g </span></dd>
</dl></body></html>"""


def fonte_finta_con_una_ricetta() -> httpx.AsyncClient:
    """La stessa fonte finta usata nel resto di questo file — sitemap più una
    pagina, via `respx` — con due ingredienti da decidere invece di uno solo:
    "Rigatoni" (mappabile su un ingrediente già in anagrafica) e "Speck" (nuovo).
    Va chiamata dentro un test già `@respx.mock`, come le sue vicine qui sopra."""
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))
    respx.get("https://ricette.giallozafferano.it/Uno.html").mock(
        return_value=httpx.Response(200, text=PAGINA_DUE_INGREDIENTI)
    )
    return build_client()


def fonte_finta_intera_con_una_ricetta() -> httpx.AsyncClient:
    """Per `--tutto`, che prende tutta la sitemap: la stessa fonte con una ricetta
    vera, e le altre due pagine sparite (404), cioè scartate e non guasti."""
    client = fonte_finta_con_una_ricetta()
    for nome in ("Due", "Tre"):
        respx.get(f"https://ricette.giallozafferano.it/{nome}.html").mock(
            return_value=httpx.Response(404)
        )
    return client


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
async def test_un_eccezione_a_meta_lotto_non_perde_le_pagine_gia_prese(db_session, monkeypatch):
    """Un'eccezione che non è `SourceUnavailable` né `UnparsablePage` - un guasto
    imprevisto, o un Ctrl-C - non deve buttare via le pagine già scaricate. Nella
    vita vera il chiamante (`main`) chiude la sessione sull'eccezione e SQLAlchemy
    annulla tutto quel che non è stato committato: lo riproduciamo qui con un
    rollback esplicito dopo l'eccezione, sulla stessa sessione."""
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))
    for nome in ("Uno", "Due", "Tre"):
        respx.get(f"https://ricette.giallozafferano.it/{nome}.html").mock(
            return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", nome))
        )

    originale = import_gz.parse_recipe
    chiamate = {"n": 0}

    def rotto(html):
        chiamate["n"] += 1
        if chiamate["n"] == 2:
            raise RuntimeError("guasto a metà lotto")
        return originale(html)

    monkeypatch.setattr(import_gz, "parse_recipe", rotto)

    async with build_client() as client:
        with pytest.raises(RuntimeError):
            await run_import(db_session, limit=3, client=client, sleep=nessuna_pausa)

    await db_session.rollback()

    pagine = (await db_session.execute(select(RecipeImport))).scalars().all()
    assert [p.url for p in pagine] == ["https://ricette.giallozafferano.it/Uno.html"]


@respx.mock
async def test_un_indirizzo_doppio_nella_sitemap_non_abortisce_il_giro(db_session):
    """Un `<loc>` ripetuto nella sitemap non deve far fallire `store_page` con un
    `IntegrityError` che abortirebbe tutto il giro per un solo indirizzo doppio."""
    sitemap_doppia = """<?xml version="1.0"?><urlset>
 <url><loc>https://ricette.giallozafferano.it/Uno.html</loc></url>
 <url><loc>https://ricette.giallozafferano.it/Uno.html</loc></url>
 <url><loc>https://ricette.giallozafferano.it/Due.html</loc></url>
</urlset>"""
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=sitemap_doppia))
    respx.get("https://ricette.giallozafferano.it/Uno.html").mock(
        return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", "Uno"))
    )
    respx.get("https://ricette.giallozafferano.it/Due.html").mock(
        return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", "Due"))
    )

    async with build_client() as client:
        esito = await run_import(db_session, limit=10, client=client, sleep=nessuna_pausa)

    assert esito.taken == 2
    pagine = (await db_session.execute(select(RecipeImport))).scalars().all()
    assert {p.url for p in pagine} == {
        "https://ricette.giallozafferano.it/Uno.html",
        "https://ricette.giallozafferano.it/Due.html",
    }


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


@respx.mock
async def test_lo_scarico_decide_i_termini_e_materializza(db_session, monkeypatch):
    """Un comando solo: scarica, decide, e le ricette entrano.

    È il criterio di riuscita numero 1 della spec. Prima di questo cambiamento il
    comando finiva su «0 importate, 5 in attesa» e aspettava una persona.
    """
    from app.core.config import get_settings
    from app.db.models.recipe import Recipe

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    try:
        # "pasta" deve esistere già in anagrafica perché il "map" dell'AI su
        # "Rigatoni" sia verificabile: senza un ingrediente da quel nome
        # `decide_one` non ha niente da confermare, e il termine resterebbe
        # `pending` — esattamente il caso che `test_senza_chiave...` copre già.
        db_session.add(
            Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
        )
        await db_session.flush()

        client = fonte_finta_con_una_ricetta()
        llm = ScriptedLlm(
            {"Rigatoni": llm_map("pasta"), "Speck": llm_create("speck", "Speck", "carne")}
        )

        esito = await run_import(
            db_session, limit=1, client=client, sleep=nessuna_pausa, llm_client=llm
        )

        assert esito.taken == 1
        assert esito.decided >= 1
        ricette = (await db_session.execute(select(Recipe))).scalars().all()
        assert len(ricette) == 1
    finally:
        get_settings.cache_clear()


@respx.mock
async def test_senza_chiave_lo_scarico_non_fallisce_e_lascia_i_termini_in_coda(
    db_session, monkeypatch
):
    """La degradazione dichiarata: mai un vicolo cieco.

    Senza chiave il comando deve comportarsi come prima di questa feature — pagine
    salvate, termini in coda, uscita pulita — non morire su un'eccezione.
    """
    from app.core.config import get_settings
    from app.db.models.recipe_import import ImportTerm, TermDecision

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        client = fonte_finta_con_una_ricetta()
        esito = await run_import(db_session, limit=1, client=client, sleep=nessuna_pausa)

        assert esito.taken == 1
        assert esito.decided == 0
        in_coda = (
            await db_session.execute(
                select(ImportTerm).where(ImportTerm.decision == TermDecision.PENDING)
            )
        ).scalars().all()
        assert in_coda != []
    finally:
        get_settings.cache_clear()


@respx.mock
async def test_lo_scarico_dice_le_unita_nuove_che_ha_depositato(db_session, monkeypatch):
    """Chi importa deve sapere che c'è un comando da lanciare dopo.

    `run_import` non chiama `decide_unit_forms` di proposito — sarebbe una chiamata
    AI in più dentro un comando che ne fa già una sua, sul tetto di 1$/giorno di chi
    possiede il progetto — quindi le unità appena depositate restano non decise. Se
    nessuno lo dice, le dosi di ogni ricetta importata dopo questo cambiamento
    mostrano la parola grezza per sempre.
    """
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    try:
        db_session.add(
            Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
        )
        await db_session.flush()

        client = fonte_finta_con_una_ricetta()
        llm = ScriptedLlm(
            {"Rigatoni": llm_map("pasta"), "Speck": llm_create("speck", "Speck", "carne")}
        )

        esito = await run_import(
            db_session, limit=1, client=client, sleep=nessuna_pausa, llm_client=llm
        )

        # le due righe della pagina finta dicono «320 g» e «100 g»: una sola unità
        assert esito.new_units == 1
        unita = (await db_session.execute(select(Unit))).scalars().all()
        assert [u.key for u in unita] == ["g"]
        assert unita[0].decided_by is None
    finally:
        get_settings.cache_clear()


@respx.mock
async def test_una_unita_gia_vista_non_si_riconta(db_session, monkeypatch):
    """Il numero è «quante ne ha depositate questo giro», non «quante ne esistono»:
    un secondo lotto che non porta parole nuove non deve chiedere un comando inutile."""
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    try:
        db_session.add(Unit(key="g", singular="g", plural="g", decided_by="human"))
        db_session.add(
            Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
        )
        await db_session.flush()

        client = fonte_finta_con_una_ricetta()
        llm = ScriptedLlm(
            {"Rigatoni": llm_map("pasta"), "Speck": llm_create("speck", "Speck", "carne")}
        )

        esito = await run_import(
            db_session, limit=1, client=client, sleep=nessuna_pausa, llm_client=llm
        )

        assert esito.new_units == 0
    finally:
        get_settings.cache_clear()


@respx.mock
async def test_tutto_svuota_la_sitemap_leggendola_una_volta(db_session):
    """`--tutto` va a lotti fino in fondo, e la sitemap (800 KB, vera) si chiede una
    volta sola, non una per lotto."""
    sitemap = respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))
    for nome in ("Uno", "Due", "Tre"):
        respx.get(f"https://ricette.giallozafferano.it/{nome}.html").mock(
            return_value=httpx.Response(200, text=PAGINA.replace("TITOLO", nome))
        )
    righe: list[str] = []

    async with build_client() as client:
        esito = await import_gz.run_all(
            db_session, client=client, sleep=nessuna_pausa, chunk=2, log=righe.append
        )

    assert esito.taken == 3
    assert sitemap.call_count == 1
    # una riga di avanzamento per lotto: due pagine, poi una
    assert sum("pagine" in riga for riga in righe) == 2


@respx.mock
async def test_tutto_non_richiede_un_termine_gia_chiesto(db_session, monkeypatch):
    """Il primo della coda ha una risposta non verificabile: senza esclusione ogni
    giro richiederebbe lui, e il secondo non verrebbe mai chiesto."""
    from app.core.config import get_settings
    from app.db.models.recipe_import import ImportTerm, TermDecision

    get_settings.cache_clear()
    monkeypatch.setenv("OPENROUTER_API_KEY", "chiave-finta")
    monkeypatch.setattr(import_gz, "MAX_TERMS_PER_RUN", 1)
    try:
        client = fonte_finta_intera_con_una_ricetta()
        # a parità di frequenza la coda va per nome: «Rigatoni» prima di «Speck».
        # Un «map» su un ingrediente che non esiste non è verificabile: resta in coda.
        llm = ScriptedLlm(
            {"Rigatoni": llm_map("non-esiste"), "Speck": llm_create("speck", "Speck", "carne")}
        )
        esito = await import_gz.run_all(
            db_session, client=client, sleep=nessuna_pausa, llm_client=llm,
            log=lambda _: None,
        )

        per_nome = {
            t.display_name: t.decision
            for t in (await db_session.execute(select(ImportTerm))).scalars()
        }
        assert per_nome["Rigatoni"] == TermDecision.PENDING
        assert per_nome["Speck"] != TermDecision.PENDING
        assert esito.decided == 1
    finally:
        get_settings.cache_clear()


@respx.mock
async def test_tutto_senza_chiave_finisce_e_lascia_i_termini_in_coda(db_session, monkeypatch):
    """Nessun giro all'infinito quando l'AI non c'è: le pagine restano, i termini in
    coda, e il comando esce."""
    from app.core.config import get_settings
    from app.db.models.recipe_import import ImportTerm, TermDecision

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        client = fonte_finta_intera_con_una_ricetta()
        esito = await import_gz.run_all(
            db_session, client=client, sleep=nessuna_pausa, log=lambda _: None
        )

        assert esito.taken == 1
        assert esito.decided == 0
        in_coda = (
            await db_session.execute(
                select(ImportTerm).where(ImportTerm.decision == TermDecision.PENDING)
            )
        ).scalars().all()
        assert in_coda != []
    finally:
        get_settings.cache_clear()


async def test_tutto_e_limit_insieme_sono_un_errore(monkeypatch):
    import sys

    monkeypatch.setattr(sys, "argv", ["app.cli.import_gz", "--tutto", "--limit", "5"])
    with pytest.raises(SystemExit) as uscita:
        await import_gz.main()
    assert uscita.value.code == 2
