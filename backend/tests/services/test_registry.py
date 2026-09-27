"""Il servizio unico dell'anagrafica (S9 §3): una prova per funzione e una per rifiuto.

Su Postgres vero, come tutto: le guardie leggono le righe di ricetta e gli alias con
query, e un finto database proverebbe una copia di quelle query.
"""

import uuid
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.recipe import RecipeSource
from app.db.models.recipe_import import GIALLOZAFFERANO, ImportTerm, TermDecision
from app.domain.rules import IngredientKind, PantryStatus
from app.repositories.ingredients import add_alias, remember_alias
from app.repositories.recipes import create_recipe
from app.services.registry import (
    RecipeRef,
    RefusalCode,
    RegistryRefusal,
    delete_alias,
    delete_product,
    move_alias,
    move_product,
    queue_terms_by_alias,
    recategorize_ingredient,
    rename_ingredient,
    set_barcode,
    update_product,
)


@pytest_asyncio.fixture
async def anagrafica(db_session):
    def voce(name: str, display: str, category: str) -> Ingredient:
        return Ingredient(name=name, display_name=display, category=category)

    voci = {
        "pomodoro": voce("pomodoro", "Pomodoro", IngredientCategory.VERDURA),
        "pomodori": voce("pomodori", "Pomodori", IngredientCategory.VERDURA),
        "burro": voce("burro", "Burro", IngredientCategory.LATTICINI),
        "parmigiano": voce("parmigiano", "Parmigiano", IngredientCategory.LATTICINI),
        "salvia": voce("salvia", "Salvia", IngredientCategory.SPEZIE),
    }
    db_session.add_all(voci.values())
    await db_session.flush()
    return voci


async def _alias(db_session, ingredient_id) -> dict[str, str]:
    """Gli alias di un ingrediente, con la loro fonte."""
    rows = await db_session.execute(
        select(IngredientAlias.alias, IngredientAlias.source).where(
            IngredientAlias.ingredient_id == ingredient_id
        )
    )
    return dict(rows.all())


async def test_rinominare_scrive_i_due_nomi_e_il_vecchio_resta_come_alias(db_session, anagrafica):
    pomodori = anagrafica["pomodori"]

    await rename_ingredient(db_session, pomodori.id, name="Pomodorini", display_name="Pomodorini")

    assert pomodori.name == "pomodorini"
    assert pomodori.display_name == "Pomodorini"
    # «manual» e non «import»: il vecchio nome non è la metà di nessuna decisione della
    # coda, e marcato «import» diventerebbe un alias che l'anagrafica non può toccare
    assert await _alias(db_session, pomodori.id) == {"pomodori": "manual"}


async def test_un_nome_gia_preso_rifiuta_e_porta_l_omonimo(db_session, anagrafica):
    """Il rifiuto porta l'ingrediente che ha già quel nome: lo schermo ne fa «Uniscili»."""
    with pytest.raises(RegistryRefusal) as rifiuto:
        await rename_ingredient(db_session, anagrafica["pomodori"].id, name=" Pomodoro ")

    assert rifiuto.value.code == RefusalCode.NAME_TAKEN
    assert rifiuto.value.obstacle is anagrafica["pomodoro"]
    assert "già in anagrafica" in rifiuto.value.message
    assert anagrafica["pomodori"].name == "pomodori"


async def test_un_nome_vuoto_rifiuta_senza_toccare_niente(db_session, anagrafica):
    """Il controllo viene prima di ogni scrittura: un rifiuto a metà lascerebbe il nome
    nuovo con il nome a video vecchio."""
    with pytest.raises(RegistryRefusal) as rifiuto:
        await rename_ingredient(
            db_session, anagrafica["pomodori"].id, name="Pomodorini", display_name="   "
        )

    assert rifiuto.value.code == RefusalCode.EMPTY_NAME
    assert anagrafica["pomodori"].name == "pomodori"


async def test_rinominare_un_ingrediente_che_non_c_e(db_session):
    with pytest.raises(LookupError):
        await rename_ingredient(db_session, uuid.uuid4(), name="qualcosa")


async def test_cambiare_reparto_ricalcola_il_tipo(db_session, anagrafica):
    salvia = anagrafica["salvia"]

    await recategorize_ingredient(db_session, salvia.id, "casa")

    assert salvia.category == "casa"
    # `kind` non si scrive: lo deriva il `@validates` del modello dal reparto
    assert salvia.kind == IngredientKind.NON_FOOD


async def test_il_non_alimentare_con_ricette_rifiuta_e_le_elenca(db_session, anagrafica):
    burro = anagrafica["burro"]
    risotto = await create_recipe(
        db_session, title="Risotto al burro", description=None, instructions="Manteca.",
        servings=2, source=RecipeSource.AI, source_ref=None,
        ingredients=[(burro.id, "primary", "50 g", None)], embedding=None,
    )

    with pytest.raises(RegistryRefusal) as rifiuto:
        await recategorize_ingredient(db_session, burro.id, "casa")

    assert rifiuto.value.code == RefusalCode.NON_FOOD_IN_RECIPES
    assert rifiuto.value.obstacle.count == 1
    assert rifiuto.value.obstacle.recipes == (RecipeRef(id=risotto.id, title="Risotto al burro"),)
    assert "non può diventare non alimentare" in rifiuto.value.message
    assert burro.category == "latticini"


async def test_un_reparto_sconosciuto_rifiuta(db_session, anagrafica):
    with pytest.raises(RegistryRefusal) as rifiuto:
        await recategorize_ingredient(db_session, anagrafica["salvia"].id, "bagno")
    assert rifiuto.value.code == RefusalCode.UNKNOWN_CATEGORY


@pytest_asyncio.fixture
async def deciso(db_session, anagrafica):
    """Un termine della coda deciso su «pomodori», con il suo alias «import».

    Lo spazio in coda al nome è voluto: `remember_alias` normalizza, e la guardia deve
    riconoscere l'alias con la stessa normalizzazione, non con una sua.
    """
    term = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-pelati", display_name="Pomodori pelati ",
        occurrences=1, decision=TermDecision.MAPPED, ingredient_id=anagrafica["pomodori"].id,
        decided_by="ai", decided_at=datetime.now(UTC),
    )
    db_session.add(term)
    await db_session.flush()
    await remember_alias(db_session, term.ingredient_id, term.display_name)
    alias = (
        await db_session.execute(
            select(IngredientAlias).where(IngredientAlias.alias == "pomodori pelati")
        )
    ).scalar_one()
    return term, alias


async def test_un_alias_scritto_a_mano_si_sposta(db_session, anagrafica):
    pomodori, pomodoro = anagrafica["pomodori"], anagrafica["pomodoro"]
    alias = await add_alias(db_session, pomodori.id, "pomodoro ciliegino", source="manual")

    spostato = await move_alias(db_session, alias.id, pomodoro.id)

    assert spostato is not None
    assert spostato.ingredient_id == pomodoro.id
    assert spostato.source == "manual"
    assert await _alias(db_session, pomodori.id) == {}


async def test_un_alias_uguale_al_nome_di_arrivo_sparisce(db_session, anagrafica):
    """Un alias uguale al nome è un doppione del nome: spostarlo lì vuol dire toglierlo."""
    alias = await add_alias(db_session, anagrafica["pomodori"].id, "pomodoro", source="seed")

    assert await move_alias(db_session, alias.id, anagrafica["pomodoro"].id) is None
    rimasti = (
        await db_session.execute(select(IngredientAlias).where(IngredientAlias.alias == "pomodoro"))
    ).scalars().all()
    assert rimasti == []


async def test_un_alias_della_coda_non_si_tocca_e_porta_il_termine(db_session, anagrafica, deciso):
    """Spostarlo da qui lascerebbe la coda a dire una cosa e l'anagrafica un'altra."""
    term, alias = deciso

    with pytest.raises(RegistryRefusal) as spostamento:
        await move_alias(db_session, alias.id, anagrafica["pomodoro"].id)
    with pytest.raises(RegistryRefusal) as rimozione:
        await delete_alias(db_session, alias.id)

    assert spostamento.value.code == RefusalCode.IMPORT_ALIAS
    assert spostamento.value.obstacle is term
    assert "nella coda" in spostamento.value.message
    assert rimozione.value.code == RefusalCode.IMPORT_ALIAS
    assert await _alias(db_session, anagrafica["pomodori"].id) == {"pomodori pelati": "import"}


async def test_un_alias_import_senza_termine_si_corregge_da_qui(db_session, anagrafica):
    """Il vecchio nome scritto da un `merge` o da un `rename` della CLI prima di S9 porta
    `source="import"` ma non è la metà di nessuna decisione: rifiutarlo sarebbe un
    vicolo cieco, perché nella coda non c'è niente da correggere."""
    alias = await add_alias(
        db_session, anagrafica["pomodori"].id, "pomodoro san marzano", source="import"
    )

    await delete_alias(db_session, alias.id)

    assert await _alias(db_session, anagrafica["pomodori"].id) == {}


async def test_i_termini_della_coda_per_alias(db_session, anagrafica, deciso):
    term, _ = deciso
    assert await queue_terms_by_alias(db_session, anagrafica["pomodori"].id) == {
        "pomodori pelati": term
    }


async def test_un_alias_che_non_c_e(db_session):
    with pytest.raises(LookupError):
        await delete_alias(db_session, uuid.uuid4())


@pytest_asyncio.fixture
async def scaffale(db_session, anagrafica):
    """Il caso del parmigiano (spec §1): un prodotto sotto «burro», con un elemento di
    dispensa attivo e uno archiviato, e un secondo prodotto che ha già un codice."""
    reggiano = Product(
        ingredient_id=anagrafica["burro"].id, name="Parmigiano Reggiano 24 mesi",
        brand="Latteria", barcode="8009876543217", source="custom",
    )
    grana = Product(
        ingredient_id=anagrafica["parmigiano"].id, name="Grana Padano 200 g",
        barcode="8001234567897", source="custom",
    )
    db_session.add_all([reggiano, grana])
    await db_session.flush()
    attivo = PantryItem(
        ingredient_id=anagrafica["burro"].id, product_id=reggiano.id,
        status=PantryStatus.AVAILABLE,
    )
    archiviato = PantryItem(
        ingredient_id=anagrafica["burro"].id, product_id=reggiano.id,
        status=PantryStatus.FINISHED, archived_at=datetime.now(UTC),
    )
    db_session.add_all([attivo, archiviato])
    await db_session.flush()
    return {"reggiano": reggiano, "grana": grana, "attivo": attivo, "archiviato": archiviato}


async def test_spostare_un_prodotto_porta_con_se_tutta_la_sua_dispensa(db_session, anagrafica, scaffale):
    """Anche gli archiviati: `add_pantry_item` rifiuta la coppia ingrediente–prodotto
    incoerente, e un archiviato rimasto sotto «burro» tornerebbe in dispensa incoerente
    al primo annulla."""
    parmigiano = anagrafica["parmigiano"]

    attivi = await move_product(db_session, scaffale["reggiano"].id, parmigiano.id)

    assert attivi == 1
    assert scaffale["reggiano"].ingredient_id == parmigiano.id
    for voce in (scaffale["attivo"], scaffale["archiviato"]):
        await db_session.refresh(voce)
        assert voce.ingredient_id == parmigiano.id


async def test_nome_e_marca_si_correggono_e_la_marca_si_toglie(db_session, scaffale):
    reggiano = scaffale["reggiano"]

    await update_product(db_session, reggiano.id, name=" Parmigiano Reggiano 30 mesi ", brand="")

    assert reggiano.name == "Parmigiano Reggiano 30 mesi"
    assert reggiano.brand is None
    with pytest.raises(RegistryRefusal) as rifiuto:
        await update_product(db_session, reggiano.id, name="  ")
    assert rifiuto.value.code == RefusalCode.EMPTY_NAME


async def test_togliere_il_codice(db_session, scaffale):
    await set_barcode(db_session, scaffale["reggiano"].id, None)
    assert scaffale["reggiano"].barcode is None


async def test_un_codice_gia_preso_rifiuta_e_porta_chi_lo_ha(db_session, scaffale):
    with pytest.raises(RegistryRefusal) as rifiuto:
        await set_barcode(db_session, scaffale["reggiano"].id, "8001234567897")

    assert rifiuto.value.code == RefusalCode.BARCODE_TAKEN
    assert rifiuto.value.obstacle is scaffale["grana"]
    assert scaffale["reggiano"].barcode == "8009876543217"


async def test_prendere_il_codice_lo_toglie_all_altro(db_session, scaffale):
    await set_barcode(db_session, scaffale["reggiano"].id, "8001234567897", take=True)

    assert scaffale["reggiano"].barcode == "8001234567897"
    assert scaffale["grana"].barcode is None


async def test_un_codice_che_non_torna_avvisa_e_si_usa_lo_stesso(db_session, scaffale):
    """S20: l'avviso e «Usalo lo stesso», mai un rifiuto che non si supera — i codici
    interni dei negozi esistono."""
    with pytest.raises(RegistryRefusal) as rifiuto:
        await set_barcode(db_session, scaffale["reggiano"].id, "8001234567890")
    assert rifiuto.value.code == RefusalCode.BAD_CHECKSUM

    await set_barcode(
        db_session, scaffale["reggiano"].id, "8001234567890", accept_bad_checksum=True
    )
    assert scaffale["reggiano"].barcode == "8001234567890"


async def test_eliminare_un_prodotto_lascia_la_dispensa_sfusa(db_session, anagrafica, scaffale):
    sfusi = await delete_product(db_session, scaffale["reggiano"].id)

    assert sfusi == 1
    assert await db_session.get(Product, scaffale["reggiano"].id) is None
    for voce in (scaffale["attivo"], scaffale["archiviato"]):
        await db_session.refresh(voce)
        assert voce.product_id is None
        assert voce.ingredient_id == anagrafica["burro"].id
