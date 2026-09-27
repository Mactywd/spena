"""Il piano che corregge l'anagrafica: ogni passo usa i percorsi dell'import.

Il mondo di prova ricalca i difetti trovati in produzione il 2026-09-27: la piadina
in dispensa e la piadella nelle ricette, «Piadine» collegato alla tortilla, la
stracciatella allo stracchino.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.cli.fix_registry import PlanError, apply_plan
from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.recipe import Recipe, RecipeIngredient, RecipeSource
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus
from app.domain.rules import IngredientKind, PantryStatus
from app.repositories.imports import store_page
from app.repositories.ingredients import remember_alias
from app.repositories.recipes import create_recipe
from app.services.recipe_import.materialize import materialize_ready

PAGINE = {
    "https://esempio.invalid/piadina": ("Piadina romagnola", [("k-piadelle", "Piadelle", "2"),
                                                              ("k-salame", "Salame", "100 g")]),
    "https://esempio.invalid/wrap": ("Wrap", [("k-piadine", "Piadine", "4"),
                                              ("k-tortillas", "Tortillas", "2")]),
    "https://esempio.invalid/burrata": ("Crostini", [("k-stracciatella", "Stracciatella",
                                                      "200 g")]),
    "https://esempio.invalid/doppia": ("Piadina doppia", [("k-piadelle", "Piadelle", "1"),
                                                          ("k-sfogliata", "Piadina sfogliata",
                                                           "2")]),
    "https://esempio.invalid/bottarga": ("Spaghetti alla bottarga", [("k-bottarga", "Bottarga",
                                                                      "30 g")]),
}


def _payload(title: str, righe: list[tuple[str, str, str]]) -> dict:
    return {
        "title": title, "description": None, "instructions": "Cuoci.", "servings": 2,
        "ingredients": [
            {"key": key, "name": name, "quantity_text": quantity}
            for key, name, quantity in righe
        ],
    }


@pytest_asyncio.fixture
async def mondo(db_session):
    def ingrediente(name: str, display: str, category: str) -> Ingredient:
        return Ingredient(name=name, display_name=display, category=category)

    voci = {
        "piadina": ingrediente("piadina", "Piadina", IngredientCategory.CEREALI),
        "piadella": ingrediente("piadella", "Piadelle", IngredientCategory.CEREALI),
        "tortilla": ingrediente("tortilla", "Tortilla", IngredientCategory.CEREALI),
        "salame": ingrediente("salame", "Salame", IngredientCategory.CARNE),
        "stracchino": ingrediente("stracchino", "Stracchino", IngredientCategory.LATTICINI),
        "mozzarella": ingrediente("mozzarella", "Mozzarella", IngredientCategory.LATTICINI),
        "eglefino": ingrediente("eglefino", "Eglefino", IngredientCategory.CARNE),
        "tormini": ingrediente("tormini", "Tomini", IngredientCategory.LATTICINI),
        "detersivo": ingrediente("detersivo", "Detersivo", IngredientCategory.CASA),
    }
    db_session.add_all(voci.values())
    await db_session.flush()

    def termine(key: str, display: str, voce: str | None, by: str = "ai") -> ImportTerm:
        return ImportTerm(
            source=GIALLOZAFFERANO, term_key=key, display_name=display, occurrences=1,
            decision=TermDecision.MAPPED if voce else TermDecision.PENDING,
            ingredient_id=voci[voce].id if voce else None,
            decided_by=by if voce else None,
            decided_at=datetime.now(UTC) if voce else None,
        )

    termini = [
        termine("k-piadelle", "Piadelle", "piadella"),
        termine("k-salame", "Salame", "salame"),
        termine("k-piadine", "Piadine", "tortilla"),
        termine("k-tortillas", "Tortillas", "tortilla"),
        termine("k-stracciatella", "Stracciatella", "stracchino", by="human"),
        termine("k-sfogliata", "Piadina sfogliata", "piadina"),
        termine("k-bottarga", "Bottarga", None),
    ]
    db_session.add_all(termini)
    await db_session.flush()
    for term in termini:
        if term.ingredient_id is not None:
            await remember_alias(db_session, term.ingredient_id, term.display_name)
    await remember_alias(db_session, voci["tortilla"].id, "piadina ripiena")

    for url, (title, righe) in PAGINE.items():
        await store_page(db_session, source=GIALLOZAFFERANO, url=url, payload=_payload(title, righe))
    await materialize_ready(db_session, GIALLOZAFFERANO)

    db_session.add(PantryItem(ingredient_id=voci["piadina"].id, status=PantryStatus.AVAILABLE))
    db_session.add(ShoppingListItem(
        raw_text="piadelle", ingredient_id=voci["piadella"].id,
        status=ShoppingStatus.PENDING, reason=ShoppingReason.MANUAL,
    ))
    await db_session.flush()
    return voci


async def _righe(db_session, url: str) -> dict[str, tuple[str, str | None]]:
    """Le righe della ricetta nata da quella pagina: ingrediente → (ruolo, dose)."""
    page = (
        await db_session.execute(select(RecipeImport).where(RecipeImport.url == url))
    ).scalar_one()
    assert page.state == ImportState.IMPORTED, page.state
    rows = await db_session.execute(
        select(Ingredient.name, RecipeIngredient.role, RecipeIngredient.quantity_text)
        .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
        .where(RecipeIngredient.recipe_id == page.recipe_id)
    )
    return {name: (role, quantity) for name, role, quantity in rows}


async def _alias(db_session, alias: str) -> list[str]:
    rows = await db_session.execute(
        select(Ingredient.name)
        .join(IngredientAlias, IngredientAlias.ingredient_id == Ingredient.id)
        .where(IngredientAlias.alias == alias)
    )
    return list(rows.scalars())


async def _applica(db_session, plan: list[dict]) -> list[str]:
    righe: list[str] = []
    await apply_plan(db_session, plan, log=righe.append)
    return righe


async def test_unire_porta_ricette_dispensa_e_lista_sul_vincitore(db_session, mondo):
    await _applica(db_session, [{"op": "merge", "from": "piadella", "into": "piadina"}])

    assert "piadina" in await _righe(db_session, "https://esempio.invalid/piadina")
    assert await db_session.get(Ingredient, mondo["piadella"].id) is None
    lista = (await db_session.execute(select(ShoppingListItem))).scalar_one()
    assert lista.ingredient_id == mondo["piadina"].id
    # chi scrive ancora «piadella» nella lista trova la piadina
    assert await _alias(db_session, "piadella") == ["piadina"]
    assert await _alias(db_session, "piadelle") == ["piadina"]


async def test_unire_fonde_le_due_righe_della_stessa_ricetta(db_session, mondo):
    await _applica(db_session, [{"op": "merge", "from": "piadella", "into": "piadina"}])

    righe = await _righe(db_session, "https://esempio.invalid/doppia")
    assert list(righe) == ["piadina"]
    assert righe["piadina"][1] == "1 + 2"


async def test_unire_sposta_anche_le_righe_delle_ricette_non_importate(db_session, mondo):
    scritta = await create_recipe(
        db_session, title="Piadina dell'AI", description=None, instructions="Scalda.",
        servings=1, source=RecipeSource.AI, source_ref=None,
        ingredients=[
            (mondo["piadina"].id, "secondary", "1", None),
            (mondo["piadella"].id, "primary", "2", None),
        ],
        embedding=None,
    )
    await _applica(db_session, [{"op": "merge", "from": "piadella", "into": "piadina"}])

    rows = (
        await db_session.execute(
            select(RecipeIngredient).where(RecipeIngredient.recipe_id == scritta.id)
        )
    ).scalars().all()
    assert [(r.ingredient_id, r.role, r.quantity_text) for r in rows] == [
        (mondo["piadina"].id, "primary", "1 + 2")
    ]
    assert rows[0].quantity_value is None


async def test_un_alimento_non_si_unisce_a_una_voce_non_alimentare(db_session, mondo):
    with pytest.raises(PlanError, match="non alimentare"):
        await _applica(db_session, [{"op": "merge", "from": "salame", "into": "detersivo"}])


async def test_ricollegare_rifa_la_ricetta_e_sposta_lalias(db_session, mondo):
    await _applica(db_session, [
        {"op": "remap", "term": "Piadine", "map": "piadina"},
        {"op": "move_alias", "alias": "piadina ripiena", "to": "piadina"},
    ])

    assert await _righe(db_session, "https://esempio.invalid/wrap") == {
        "piadina": ("primary", "4"), "tortilla": ("primary", "2"),
    }
    assert await _alias(db_session, "piadine") == ["piadina"]
    assert await _alias(db_session, "piadina ripiena") == ["piadina"]
    term = (
        await db_session.execute(select(ImportTerm).where(ImportTerm.term_key == "k-piadine"))
    ).scalar_one()
    assert term.decided_by == "human"


async def test_ricollegare_non_perde_il_costo_scelto_a_mano(db_session, mondo):
    url = "https://esempio.invalid/burrata"
    page = (await db_session.execute(select(RecipeImport).where(RecipeImport.url == url))).scalar_one()
    (await db_session.get(Recipe, page.recipe_id)).cost = 4
    await db_session.flush()

    await _applica(db_session, [{"op": "remap", "term": "Stracciatella", "map": "mozzarella"}])

    await db_session.refresh(page)
    assert "mozzarella" in await _righe(db_session, url)
    assert (await db_session.get(Recipe, page.recipe_id)).cost == 4


async def test_decidere_un_termine_in_coda_sblocca_la_sua_ricetta(db_session, mondo):
    righe = await _applica(db_session, [{
        "op": "decide", "term": "Bottarga", "role": "secondary",
        "create": {"name": "bottarga", "category": "pesce"},
    }])

    assert await _righe(db_session, "https://esempio.invalid/bottarga") == {
        "bottarga": ("secondary", "30 g"),
    }
    assert "1 rifatte" in righe[-1]
    assert "0 termini ancora in coda" in righe[-1]


async def test_decide_su_un_termine_gia_deciso_rimanda_a_remap(db_session, mondo):
    with pytest.raises(PlanError, match="passo 2 .*remap"):
        await _applica(db_session, [
            {"op": "recategorize", "ingredient": "eglefino", "category": "pesce"},
            {"op": "decide", "term": "Salame", "map": "piadina"},
        ])


async def test_un_nome_di_termine_ambiguo_si_rifiuta(db_session, mondo):
    db_session.add(ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-salame-2", display_name="salame",
        occurrences=1, decision=TermDecision.PENDING,
    ))
    await db_session.flush()
    with pytest.raises(PlanError, match="trovati 2"):
        await _applica(db_session, [{"op": "remap", "term": "Salame", "map": "piadina"}])

    await _applica(db_session, [{"op": "decide", "term_key": "k-salame-2", "map": "salame"}])


async def test_cambiare_reparto_ricalcola_il_tipo(db_session, mondo):
    await _applica(db_session, [{"op": "recategorize", "ingredient": "eglefino", "category": "pesce"}])
    assert mondo["eglefino"].category == "pesce"
    assert mondo["eglefino"].kind == IngredientKind.FOOD

    with pytest.raises(PlanError, match="non può diventare non alimentare"):
        await _applica(db_session, [{"op": "recategorize", "ingredient": "salame", "category": "casa"}])


async def test_rinominare_lascia_il_vecchio_nome_come_alias(db_session, mondo):
    await _applica(db_session, [
        {"op": "rename", "ingredient": "tormini", "name": "tomino", "display_name": "Tomini"},
    ])
    assert mondo["tormini"].name == "tomino"
    assert await _alias(db_session, "tormini") == ["tomino"]

    with pytest.raises(PlanError, match="già in anagrafica"):
        await _applica(db_session, [{"op": "rename", "ingredient": "tomino", "name": "salame"}])


async def test_un_passo_sconosciuto_o_incompleto_si_rifiuta(db_session, mondo):
    with pytest.raises(PlanError, match="operazione sconosciuta"):
        await _applica(db_session, [{"op": "cancella", "ingredient": "salame"}])
    with pytest.raises(PlanError, match="manca il campo 'into'"):
        await _applica(db_session, [{"op": "merge", "from": "salame"}])


def test_i_piani_nel_repository_usano_solo_passi_che_esistono():
    """Un piano si scrive a mano: un refuso nel nome di un passo deve cadere qui, non
    a metà di una prova in produzione."""
    import json
    from pathlib import Path

    from app.cli.fix_registry import OPERATIONS

    piani = list((Path(__file__).parents[2] / "data" / "fixes").glob("*.json"))
    assert piani
    for piano in piani:
        passi = json.loads(piano.read_text(encoding="utf-8"))
        assert {passo["op"] for passo in passi} <= set(OPERATIONS), piano.name
