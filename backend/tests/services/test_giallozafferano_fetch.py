import httpx
import pytest
import respx

from app.services.recipe_import.giallozafferano import (
    DELAY_SECONDS,
    MAX_CONSECUTIVE_FAILURES,
    RECIPE_SITEMAP,
    USER_AGENT,
    SourceUnavailable,
    UnparsablePage,
    build_client,
    fetch_page,
    fetch_sitemap,
)

SITEMAP = """<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
 <url><loc>https://ricette.giallozafferano.it/Tiramisu.html</loc></url>
 <url><loc>https://ricette.giallozafferano.it/Carbonara.html</loc></url>
 <url><loc>https://ricette.giallozafferano.it/ricette-cat/Dolci/</loc></url>
</urlset>"""


@respx.mock
async def test_la_sitemap_da_solo_pagine_di_ricetta():
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))

    async with build_client() as client:
        urls = await fetch_sitemap(client)

    assert urls == [
        "https://ricette.giallozafferano.it/Tiramisu.html",
        "https://ricette.giallozafferano.it/Carbonara.html",
    ]


@respx.mock
async def test_la_richiesta_si_fa_riconoscere():
    """Lo User-Agent non è decorativo: è il modo di non presentarsi come un crawler
    anonimo a un sito che nel suo robots.txt vieta esplicitamente i crawler AI."""
    route = respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(200, text=SITEMAP))

    async with build_client() as client:
        await fetch_sitemap(client)

    assert route.calls.last.request.headers["user-agent"] == USER_AGENT
    assert "archivio personale" in USER_AGENT


@respx.mock
async def test_una_pagina_si_legge():
    respx.get("https://ricette.giallozafferano.it/Tiramisu.html").mock(
        return_value=httpx.Response(200, text="<html>tiramisù</html>")
    )

    async with build_client() as client:
        html = await fetch_page(client, "https://ricette.giallozafferano.it/Tiramisu.html")

    assert "tiramisù" in html


@respx.mock
@pytest.mark.parametrize("status", [429, 500, 503])
async def test_il_sito_che_chiede_di_smettere_ferma_il_giro(status):
    respx.get("https://ricette.giallozafferano.it/Tiramisu.html").mock(
        return_value=httpx.Response(status)
    )

    async with build_client() as client:
        with pytest.raises(SourceUnavailable):
            await fetch_page(client, "https://ricette.giallozafferano.it/Tiramisu.html")


@respx.mock
async def test_una_pagina_che_non_esiste_e_un_problema_solo_suo():
    """404 non ferma niente: è questa pagina a essere andata, non il sito."""
    respx.get("https://ricette.giallozafferano.it/Spariita.html").mock(
        return_value=httpx.Response(404)
    )

    async with build_client() as client:
        with pytest.raises(UnparsablePage) as errore:
            await fetch_page(client, "https://ricette.giallozafferano.it/Spariita.html")

    assert "404" in errore.value.reason


@respx.mock
async def test_la_sitemap_irraggiungibile_e_un_guasto_della_fonte():
    respx.get(RECIPE_SITEMAP).mock(return_value=httpx.Response(503))

    async with build_client() as client:
        with pytest.raises(SourceUnavailable):
            await fetch_sitemap(client)


def test_le_costanti_di_cortesia_sono_quelle_dichiarate_nello_spec():
    assert DELAY_SECONDS >= 1.0
    assert MAX_CONSECUTIVE_FAILURES == 2
