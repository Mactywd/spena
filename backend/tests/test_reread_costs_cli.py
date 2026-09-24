"""`app.cli.reread_costs`: il costo delle ricette già importate, e nient'altro.

Spec R9, §4.
"""

import httpx
import respx
from sqlalchemy import select

from app.cli.reread_costs import reread_costs
from app.db.models.recipe import Recipe, RecipeSource
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportState, RecipeImport
from app.services.recipe_import.giallozafferano import build_client

BASE = "https://ricette.giallozafferano.it"


def pagina(costo: str | None) -> str:
    blocco = (
        f'<span class="gz-name-featured-data">Costo: <strong>{costo}</strong></span>'
        if costo
        else ""
    )
    # Niente JSON-LD, di proposito: il comando legge il costo e basta, e una pagina
    # che il parser completo scarterebbe non deve impedirgli di trovarlo.
    return (
        '<html><body><span class="gz-name-featured-data">Difficoltà: '
        f"<strong>Media</strong></span>{blocco}</body></html>"
    )


async def ricetta(db_session, nome: str, *, cost=None, source=RecipeSource.DATASET,
                  source_ref: str | None = "auto", con_pagina=True) -> Recipe:
    ref = f"{BASE}/{nome}.html" if source_ref == "auto" else source_ref
    recipe = Recipe(title=nome, instructions="x", source=source, source_ref=ref, cost=cost)
    db_session.add(recipe)
    await db_session.flush()
    if con_pagina and ref:
        db_session.add(RecipeImport(
            source=GIALLOZAFFERANO, url=ref, state=ImportState.IMPORTED,
            payload={"title": nome, "ingredients": []}, recipe_id=recipe.id,
        ))
        await db_session.flush()
    return recipe


class Pause:
    def __init__(self) -> None:
        self.count = 0

    async def __call__(self, _seconds: float) -> None:
        self.count += 1


@respx.mock
async def test_scrive_il_costo_sulla_ricetta_e_sulla_pagina(db_session):
    recipe = await ricetta(db_session, "Carbonara")
    respx.get(f"{BASE}/Carbonara.html").mock(
        return_value=httpx.Response(200, text=pagina("Basso"))
    )
    pausa = Pause()
    async with build_client() as client:
        esito = await reread_costs(db_session, client=client, sleep=pausa)

    assert (esito.found, esito.without, esito.gone, esito.stopped_early) == (1, 0, 0, False)
    await db_session.refresh(recipe)
    assert recipe.cost == 2
    page = (await db_session.execute(select(RecipeImport))).scalars().one()
    # un annulla o una rimaterializzazione rileggono il payload: senza, lo perderebbero
    assert page.payload["cost"] == 2
    assert page.payload["title"] == "Carbonara"
    assert pausa.count == 1


@respx.mock
async def test_un_costo_gia_scelto_non_si_tocca_e_non_si_chiede(db_session):
    recipe = await ricetta(db_session, "Filetto", cost=5)
    rotta = respx.get(f"{BASE}/Filetto.html").mock(
        return_value=httpx.Response(200, text=pagina("Molto basso"))
    )
    async with build_client() as client:
        esito = await reread_costs(db_session, client=client, sleep=Pause())

    assert esito.found == 0
    assert not rotta.called
    await db_session.refresh(recipe)
    assert recipe.cost == 5


@respx.mock
async def test_solo_le_ricette_importate_da_un_indirizzo(db_session):
    await ricetta(db_session, "Mia", source=RecipeSource.MANUAL, source_ref=None)
    await ricetta(db_session, "Seme", source_ref="seme iniziale", con_pagina=False)
    async with build_client() as client:
        esito = await reread_costs(db_session, client=client, sleep=Pause())
    # respx fallisce su qualunque richiesta non dichiarata: nessuna è partita
    assert (esito.found, esito.without, esito.gone) == (0, 0, 0)


@respx.mock
async def test_una_pagina_senza_costo_lascia_la_ricetta_senza(db_session):
    recipe = await ricetta(db_session, "Acqua")
    respx.get(f"{BASE}/Acqua.html").mock(return_value=httpx.Response(200, text=pagina(None)))
    async with build_client() as client:
        esito = await reread_costs(db_session, client=client, sleep=Pause())
    assert esito.without == 1
    await db_session.refresh(recipe)
    assert recipe.cost is None


@respx.mock
async def test_una_pagina_sparita_non_ferma_il_giro(db_session):
    await ricetta(db_session, "Sparita")
    seconda = await ricetta(db_session, "Panzanella")
    respx.get(f"{BASE}/Sparita.html").mock(return_value=httpx.Response(404))
    respx.get(f"{BASE}/Panzanella.html").mock(
        return_value=httpx.Response(200, text=pagina("Molto basso"))
    )
    async with build_client() as client:
        esito = await reread_costs(db_session, client=client, sleep=Pause())
    assert (esito.found, esito.gone, esito.stopped_early) == (1, 1, False)
    await db_session.refresh(seconda)
    assert seconda.cost == 1


@respx.mock
async def test_due_rifiuti_di_fila_fermano_il_giro_e_il_fatto_resta(db_session):
    prima = await ricetta(db_session, "A")
    await ricetta(db_session, "B")
    await ricetta(db_session, "C")
    await ricetta(db_session, "D")
    respx.get(f"{BASE}/A.html").mock(return_value=httpx.Response(200, text=pagina("Medio")))
    respx.get(f"{BASE}/B.html").mock(return_value=httpx.Response(429))
    respx.get(f"{BASE}/C.html").mock(return_value=httpx.Response(503))
    d = respx.get(f"{BASE}/D.html").mock(return_value=httpx.Response(200, text=pagina("Medio")))
    async with build_client() as client:
        esito = await reread_costs(db_session, client=client, sleep=Pause())
    assert esito.stopped_early is True
    assert esito.found == 1
    assert not d.called
    await db_session.refresh(prima)
    assert prima.cost == 3
