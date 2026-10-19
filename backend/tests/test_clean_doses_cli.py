"""Il comando che pulisce le dosi già scritte, le rilegge e toglie le unità orfane.

Il mondo di prova ricalca le forme misurate in produzione il 2026-10-13. I valori delle
righe sono quelli che il parser di prima aveva lasciato: «½», «1 + ½» e «+ q.b.» non li
leggeva, «36 mesi» sì, e male.

Le righe si rileggono a colonne, non a oggetti: il comando scrive con Core, e gli oggetti
che la sessione tiene in memoria sono di prima del comando.
"""

import asyncio
from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy import select, update

from app.cli.clean_doses import Cleaned, Sample, clean_doses, main, report
from app.cli.reparse_quantities import reparse
from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.recipe import Recipe, RecipeIngredient
from app.db.models.unit import Unit
from app.domain.quantities import DoseShape
from app.repositories.ingredients import create_ingredient
from app.repositories.recipes import create_recipe


async def _unita(db_session, key: str) -> Unit:
    return (await db_session.execute(select(Unit).where(Unit.key == key))).scalars().one()


@pytest_asyncio.fixture
async def mondo(db_session):
    ing = {}
    for nome in [
        "parmigiano", "acqua", "burro", "sale", "zucchero", "limone", "olio", "uova",
        "pecorino", "pane",
    ]:
        ing[nome] = await create_ingredient(
            db_session, name=nome, display_name=nome.capitalize(),
            category=IngredientCategory.CEREALI,
        )
    importata = await create_recipe(
        db_session,
        title="Importata", description=None, instructions="i", servings=4,
        source="dataset", source_ref="https://esempio.invalid/importata",
        ingredients=[
            (ing["parmigiano"].id, "primary", "36 mesi\n\t\t\t50\n\t\t\tg", None),
            (ing["acqua"].id, "primary", "fredda\n\t\t\t330\n\t\t\tg", None),
            (ing["burro"].id, "primary", "100\n\t\t\tg", None),
            (ing["sale"].id, "secondary", "secco\n\n\t\t\tq.b.", None),
            (ing["zucchero"].id, "primary", "½\n\t\t\tcucchiaino", None),
            (ing["limone"].id, "primary", "1 + ½", None),
            (ing["olio"].id, "primary", "10\n\t\t\tg + q.b.", None),
            (ing["uova"].id, "primary", "1 intera\n\t\t\t60\n\t\t\tg", None),
        ],
        embedding=None,
    )
    # adottata (scritta a mano o modificata da Mattia) e archiviata: si può ripristinare,
    # quindi si pulisce come le altre, ma solo dove c'è ancora la forma dell'import
    adottata = await create_recipe(
        db_session,
        title="Adottata", description=None, instructions="i", servings=2,
        source="manual", source_ref=None,
        ingredients=[
            (ing["pecorino"].id, "primary", "da grattugiare\n\t\t\t30\n\t\t\tg", "mia"),
            (ing["burro"].id, "primary", "freddo 50 g", None),
            (ing["pane"].id, "primary", "2 intere", None),
        ],
        embedding=None,
    )
    await db_session.execute(
        update(Recipe).where(Recipe.id == adottata.id).values(archived_at=datetime.now(UTC))
    )
    # quel che il parser di prima non leggeva
    await db_session.execute(
        update(RecipeIngredient)
        .where(
            RecipeIngredient.quantity_text.in_(
                ["½\n\t\t\tcucchiaino", "1 + ½", "10\n\t\t\tg + q.b."]
            )
        )
        .values(quantity_value=None, quantity_unit_id=None)
    )
    # «intere» ha per singolare «intera», che esiste: ci punta, come fa decide_units
    (await _unita(db_session, "intere")).canonical_id = (await _unita(db_session, "intera")).id
    # un'unità già senza righe prima della pulizia: non è la pulizia ad averla lasciata sola
    db_session.add(Unit(key="cchiaio"))
    await db_session.flush()
    return {"importata": importata.id, "adottata": adottata.id}


async def _righe(db_session, recipe_id) -> dict[str, tuple]:
    """(testo, nota, valore, chiave dell'unità) per ingrediente, letti dal database."""
    risultato = await db_session.execute(
        select(
            Ingredient.name, RecipeIngredient.quantity_text, RecipeIngredient.note,
            RecipeIngredient.quantity_value, Unit.key,
        )
        .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
        .outerjoin(Unit, Unit.id == RecipeIngredient.quantity_unit_id)
        .where(RecipeIngredient.recipe_id == recipe_id)
    )
    return {nome: (testo, nota, valore, chiave) for nome, testo, nota, valore, chiave in risultato.all()}


async def test_le_righe_dell_import_si_puliscono_e_si_rileggono(db_session, mondo):
    await clean_doses(db_session)

    righe = await _righe(db_session, mondo["importata"])
    assert righe["parmigiano"] == ("50 g", "36 mesi", Decimal("50"), "g")
    assert righe["acqua"] == ("330 g", "fredda", Decimal("330"), "g")
    assert righe["burro"] == ("100 g", None, Decimal("100"), "g")
    assert righe["sale"] == ("q.b.", "secco", None, None)
    assert righe["zucchero"] == ("½ cucchiaino", None, Decimal("0.5"), "cucchiaino")
    assert righe["limone"] == ("1 + ½", None, Decimal("1.5"), None)
    assert righe["olio"] == ("10 g + q.b.", None, Decimal("10"), "g")
    assert righe["uova"] == ("60 g", "1 intera", Decimal("60"), "g")


async def test_nella_ricetta_adottata_cambia_solo_la_riga_con_la_forma_dell_import(
    db_session, mondo
):
    await clean_doses(db_session)

    righe = await _righe(db_session, mondo["adottata"])
    # la nota scritta a mano resta davanti a quella che arriva dalla pulizia
    assert righe["pecorino"] == ("30 g", "mia; da grattugiare", Decimal("30"), "g")
    # scritte a mano, senza a capo: il testo non cambia, nemmeno con l'aggettivo davanti
    assert righe["burro"] == ("freddo 50 g", None, None, None)
    assert righe["pane"] == ("2 intere", None, Decimal("2"), "intere")


async def test_i_conti_per_forma_e_le_dosi_lette(db_session, mondo):
    esito = await clean_doses(db_session)

    assert esito.rows == 11
    assert esito.shapes == Counter({
        DoseShape.SPACES: 3,  # burro «100 g», zucchero, olio
        DoseShape.WORDS_BEFORE: 2,  # acqua, pecorino
        DoseShape.NUMBER_IN_NAME: 2,  # parmigiano, uova
        DoseShape.NOTE_QB: 1,  # sale
    })
    assert esito.cleaned == 8
    # prima: parmigiano (36 mesi), burro dell'import, uova (1 intera), pane
    assert esito.parsed_before == 4
    # dopo: tutte tranne sale («q.b.») e il burro scritto a mano
    assert esito.parsed_after == 9
    # lette prima e dopo, ma diverse: 36 mesi → 50 g, 1 intera → 60 g
    assert esito.changed_values == 2
    assert esito.new_units == []
    # il campione: una riga per forma, qui (il massimo è cinque)
    assert {campione.shape for campione in esito.sample} == set(esito.shapes)
    assert Sample(
        DoseShape.NUMBER_IN_NAME, "36 mesi\n\t\t\t50\n\t\t\tg", "50 g", "36 mesi"
    ) in esito.sample


async def test_le_unita_rimaste_senza_righe_se_ne_vanno_le_altre_restano(db_session, mondo):
    esito = await clean_doses(db_session)

    chiavi = set((await db_session.execute(select(Unit.key))).scalars())
    assert esito.removed_units == ["mesi"]
    assert "mesi" not in chiavi
    # «intera» non ha più righe, ma «intere» la usa ancora come suo singolare
    assert esito.kept_units == ["intera"]
    assert {"intera", "intere", "g", "cucchiaino"} <= chiavi
    # già senza righe prima: si elenca e resta
    assert "cchiaio" in esito.idle_units
    assert "cchiaio" in chiavi


async def test_due_unita_orfane_che_si_puntano_se_ne_vanno_insieme(db_session):
    """La FK di `canonical_id` è RESTRICT: fra due che se ne vanno, il puntatore si azzera
    prima, o la DELETE fallisce e con lei tutta la pulizia."""
    grana = await create_ingredient(
        db_session, name="grana", display_name="Grana", category=IngredientCategory.CEREALI
    )
    fontina = await create_ingredient(
        db_session, name="fontina", display_name="Fontina", category=IngredientCategory.CEREALI
    )
    await create_recipe(
        db_session,
        title="Formaggi", description=None, instructions="i", servings=2,
        source="dataset", source_ref=None,
        ingredients=[
            (grana.id, "primary", "24 mesi\n\t\t\t40\n\t\t\tg", None),
            (fontina.id, "primary", "1 mese\n\t\t\t30\n\t\t\tg", None),
        ],
        embedding=None,
    )
    (await _unita(db_session, "mesi")).canonical_id = (await _unita(db_session, "mese")).id
    await db_session.flush()

    esito = await clean_doses(db_session)

    assert esito.removed_units == ["mese", "mesi"]
    chiavi = set((await db_session.execute(select(Unit.key))).scalars())
    assert not {"mese", "mesi"} & chiavi


async def test_rilanciato_non_cambia_niente(db_session, mondo):
    await clean_doses(db_session)
    importata = await _righe(db_session, mondo["importata"])
    adottata = await _righe(db_session, mondo["adottata"])

    secondo = await clean_doses(db_session)

    assert secondo.cleaned == 0
    assert secondo.parsed_before == secondo.parsed_after == 9
    assert secondo.changed_values == 0
    assert (secondo.new_units, secondo.removed_units) == ([], [])
    assert await _righe(db_session, mondo["importata"]) == importata
    assert await _righe(db_session, mondo["adottata"]) == adottata


async def test_dopo_la_pulizia_reparse_quantities_legge_le_stesse_dosi(db_session, mondo):
    """La rilettura del comando è quella di `reparse_quantities`: l'altro comando, dopo di
    lui, non deve trovare niente da cambiare. Due strade che leggono le dosi devono
    leggerle uguali (prima lezione di CLAUDE.md)."""
    await clean_doses(db_session)
    importata = await _righe(db_session, mondo["importata"])
    adottata = await _righe(db_session, mondo["adottata"])

    # `reparse` legge oggetti ORM: quelli in memoria sono di prima del comando
    db_session.expunge_all()
    esito = await reparse(db_session)

    assert esito.new_units == 0
    assert await _righe(db_session, mondo["importata"]) == importata
    assert await _righe(db_session, mondo["adottata"]) == adottata


def test_il_resoconto_dice_i_conti_e_il_campione():
    esito = Cleaned(
        rows=11,
        shapes=Counter({DoseShape.NUMBER_IN_NAME: 1}),
        parsed_before=4,
        parsed_after=9,
        changed_values=2,
        removed_units=["mesi"],
        kept_units=["intera"],
        idle_units=["cchiaio"],
        sample=[Sample(DoseShape.NUMBER_IN_NAME, "36 mesi\n\t\t\t50\n\t\t\tg", "50 g", "36 mesi")],
    )

    assert report(esito).splitlines() == [
        "Righe lette: 11. Ripulite: 1.",
        "  solo a capo e tabulazioni: 0",
        "  parole davanti alla dose, ora nella nota: 0",
        "  numero nel nome, ora nella nota: 1",
        "  nota e q.b.: 0",
        "Dosi lette: 4 prima, 9 dopo; 2 lette diverse da prima.",
        "Unità nuove: nessuna.",
        "Unità tolte, nessuna riga le usa più: mesi.",
        "Unità senza righe tenute, perché canoniche di un'altra: intera.",
        "Unità già senza righe prima, lasciate: cchiaio.",
        "Campione:",
        "  [numero nel nome, ora nella nota] «36 mesi⏎50⏎g» → «50 g», nota «36 mesi»",
    ]


def test_un_argomento_sconosciuto_esce_senza_toccare_niente():
    """Un refuso («--conferma», il flag di fix_registry) non deve diventare una scrittura
    vera: argparse esce con 2 prima di aprire la sessione."""
    with pytest.raises(SystemExit) as uscita:
        asyncio.run(main(["--conferma"]))
    assert uscita.value.code == 2
