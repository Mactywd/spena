"""La fusione di due ingredienti (S9 §5): tutto quel che punta al perdente passa al
vincitore, le ricette dell'import si rifanno, e le cotture ritrovano la ricetta.

Il mondo di prova ha un pezzo per ogni tabella che la fusione tocca: due pagine
dell'import (una con le due righe che diventano una), una ricetta scritta dall'AI, un
elemento di dispensa, una voce di lista, un prodotto, un alias scritto a mano.
"""

from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.db import Base
from app.db.models.ingredient import Ingredient, IngredientAlias, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.recipe import CookingEvent, RecipeIngredient, RecipeSource
from app.db.models.recipe_import import (
    GIALLOZAFFERANO,
    ImportState,
    ImportTerm,
    RecipeImport,
    TermDecision,
)
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus
from app.domain.rules import PantryStatus
from app.repositories.imports import store_page
from app.repositories.ingredients import add_alias, remember_alias
from app.repositories.recipes import create_recipe
from app.services.recipe_import.materialize import materialize_ready
from app.services.registry import (
    MergeCounts,
    RefusalCode,
    RegistryRefusal,
    merge_ingredients,
    preview_merge,
    recategorize_ingredient,
)

SUGO = "https://esempio.invalid/sugo"
BRUSCHETTA = "https://esempio.invalid/bruschetta"
PAGINE = {
    SUGO: ("Sugo semplice", [("k-pomodori", "Pomodori", "400 g"), ("k-basilico", "Basilico", "q.b.")]),
    BRUSCHETTA: ("Bruschetta", [("k-pomodori", "Pomodori", "2"), ("k-pomodoro", "Pomodoro", "1")]),
}


def _payload(title: str, righe: list[tuple[str, str, str]]) -> dict:
    return {
        "title": title, "description": None, "instructions": "Cuoci.", "servings": 2,
        "ingredients": [
            {"key": key, "name": name, "quantity_text": quantity} for key, name, quantity in righe
        ],
    }


@pytest_asyncio.fixture
async def mondo(db_session):
    def voce(name: str, display: str, category: str) -> Ingredient:
        return Ingredient(name=name, display_name=display, category=category)

    voci = {
        "pomodoro": voce("pomodoro", "Pomodoro", IngredientCategory.VERDURA),
        "pomodori": voce("pomodori", "Pomodori", IngredientCategory.VERDURA),
        "basilico": voce("basilico", "Basilico", IngredientCategory.SPEZIE),
        "detersivo": voce("detersivo", "Detersivo", IngredientCategory.CASA),
    }
    db_session.add_all(voci.values())
    await db_session.flush()

    def termine(key: str, display: str, voce_: str) -> ImportTerm:
        return ImportTerm(
            source=GIALLOZAFFERANO, term_key=key, display_name=display, occurrences=1,
            decision=TermDecision.MAPPED, ingredient_id=voci[voce_].id, decided_by="ai",
            decided_at=datetime.now(UTC),
        )

    termini = [
        termine("k-pomodori", "Pomodori", "pomodori"),
        termine("k-pomodoro", "Pomodoro", "pomodoro"),
        termine("k-basilico", "Basilico", "basilico"),
    ]
    db_session.add_all(termini)
    await db_session.flush()
    for term in termini:
        await remember_alias(db_session, term.ingredient_id, term.display_name)

    for url, (title, righe) in PAGINE.items():
        await store_page(db_session, source=GIALLOZAFFERANO, url=url, payload=_payload(title, righe))
    await materialize_ready(db_session, GIALLOZAFFERANO)

    await add_alias(db_session, voci["pomodori"].id, "pomodorini", source="manual")
    scritta = await create_recipe(
        db_session, title="Insalata dell'AI", description=None, instructions="Taglia.",
        servings=1, source=RecipeSource.AI, source_ref=None,
        ingredients=[(voci["pomodori"].id, "primary", "3", None)], embedding=None,
    )
    db_session.add(PantryItem(ingredient_id=voci["pomodori"].id, status=PantryStatus.AVAILABLE))
    db_session.add(ShoppingListItem(
        raw_text="pomodori", ingredient_id=voci["pomodori"].id,
        status=ShoppingStatus.PENDING, reason=ShoppingReason.MANUAL,
    ))
    db_session.add(Product(ingredient_id=voci["pomodori"].id, name="Pelati Cirio", source="custom"))
    await db_session.flush()
    return {**voci, "scritta": scritta}


def _voce_di_lista(ingredient: Ingredient, status: str, raw_text: str) -> ShoppingListItem:
    return ShoppingListItem(
        raw_text=raw_text, ingredient_id=ingredient.id, status=status,
        reason=ShoppingReason.MANUAL,
    )


async def _lista(db_session) -> list[tuple[str, str, str]]:
    """Ogni voce di lista: testo, ingrediente, stato."""
    rows = await db_session.execute(
        select(ShoppingListItem.raw_text, Ingredient.name, ShoppingListItem.status)
        .join(Ingredient, Ingredient.id == ShoppingListItem.ingredient_id)
        .order_by(ShoppingListItem.raw_text)
    )
    return [tuple(row) for row in rows.all()]


async def _pagina(db_session, url: str) -> RecipeImport:
    return (
        await db_session.execute(select(RecipeImport).where(RecipeImport.url == url))
    ).scalar_one()


async def _righe(db_session, url: str) -> dict[str, str | None]:
    """Le righe della ricetta nata da quella pagina: ingrediente → dose."""
    page = await _pagina(db_session, url)
    assert page.state == ImportState.IMPORTED, page.state
    rows = await db_session.execute(
        select(Ingredient.name, RecipeIngredient.quantity_text)
        .join(Ingredient, Ingredient.id == RecipeIngredient.ingredient_id)
        .where(RecipeIngredient.recipe_id == page.recipe_id)
    )
    return dict(rows.all())


async def _chi_ha_l_alias(db_session, alias: str) -> list[str]:
    rows = await db_session.execute(
        select(Ingredient.name)
        .join(IngredientAlias, IngredientAlias.ingredient_id == Ingredient.id)
        .where(IngredientAlias.alias == alias)
    )
    return list(rows.scalars())


async def test_unire_porta_tutto_sul_vincitore_e_lo_conta(db_session, mondo):
    perdente, vincitore = mondo["pomodori"].id, mondo["pomodoro"].id

    conti = await merge_ingredients(db_session, perdente, vincitore)

    assert conti == MergeCounts(
        loser_name="pomodori", winner_name="pomodoro",
        recipes_rebuilt=2, recipe_lines_moved=1, pantry_items=1, shopping_items=1,
        shopping_items_dropped=0, products=1, aliases=2, cooking_events_relinked=0,
    )
    assert await db_session.get(Ingredient, perdente) is None
    assert "pomodoro" in await _righe(db_session, SUGO)
    # le due righe della bruschetta diventano una, come nella materializzazione
    assert await _righe(db_session, BRUSCHETTA) == {"pomodoro": "2 + 1"}
    # chi scrive ancora «pomodori» o «pomodorini» nella lista trova il pomodoro
    assert await _chi_ha_l_alias(db_session, "pomodori") == ["pomodoro"]
    assert await _chi_ha_l_alias(db_session, "pomodorini") == ["pomodoro"]
    lista = (await db_session.execute(select(ShoppingListItem))).scalar_one()
    assert lista.ingredient_id == vincitore
    scritta = (
        await db_session.execute(
            select(RecipeIngredient.ingredient_id).where(
                RecipeIngredient.recipe_id == mondo["scritta"].id
            )
        )
    ).scalars().all()
    assert scritta == [vincitore]


async def test_le_cotture_della_ricetta_rifatta_si_ri_legano(db_session, mondo, dal_database):
    """Il caso per cui la fusione è sicura da offrire a un tocco (spec §5.2, §9.3): una
    ricetta importata già cucinata si rifà, e la cottura punta alla ricetta nuova."""
    pagina = await _pagina(db_session, SUGO)
    evento = CookingEvent(recipe_id=pagina.recipe_id, servings=2, snapshot={"title": "Sugo semplice"})
    db_session.add(evento)
    await db_session.flush()
    evento_id, pagina_id, ricetta_vecchia = evento.id, pagina.id, pagina.recipe_id

    conti = await merge_ingredients(db_session, mondo["pomodori"].id, mondo["pomodoro"].id)

    assert conti.cooking_events_relinked == 1
    pagina = await dal_database(RecipeImport, pagina_id)
    cottura = await dal_database(CookingEvent, evento_id)
    assert pagina.recipe_id not in (None, ricetta_vecchia)
    assert cottura.recipe_id == pagina.recipe_id
    assert "cooking_event_ids" not in pagina.payload


async def test_un_alimento_e_una_voce_non_alimentare_non_si_uniscono(db_session, mondo):
    """Non è un vicolo cieco: il messaggio dice il passo (spec §5.3)."""
    with pytest.raises(RegistryRefusal) as rifiuto:
        await merge_ingredients(db_session, mondo["pomodori"].id, mondo["detersivo"].id)

    assert rifiuto.value.code == RefusalCode.KIND_MISMATCH
    assert rifiuto.value.obstacle is mondo["detersivo"]
    assert (
        "Prima porta «Pomodori» nello stesso reparto di «Detersivo», poi uniscili."
        in rifiuto.value.message
    )
    assert await db_session.get(Ingredient, mondo["pomodori"].id) is not None


async def test_un_ingrediente_non_si_unisce_a_se_stesso(db_session, mondo):
    with pytest.raises(RegistryRefusal) as rifiuto:
        await merge_ingredients(db_session, mondo["pomodoro"].id, mondo["pomodoro"].id)
    assert rifiuto.value.code == RefusalCode.SAME_INGREDIENT


async def test_un_termine_dell_import_non_si_puo_ridecidere_su_un_non_alimentare(
    db_session, mondo
):
    """Un ingrediente con un termine dell'AI ma senza righe di ricetta — la sua pagina
    non è mai stata materializzata — non è bloccato da nessuna ricetta e può diventare
    non alimentare, come farebbe la scheda dell'anagrafica. Unirlo in un altro non
    alimentare (stesso `kind`, quindi oltre il controllo di KIND_MISMATCH) prova a
    ridecidere quel termine sul vincitore, e lì `decide_by_hand` rifiuta sempre:
    un termine di ricetta non si lega a una voce non alimentare, chiunque sia il
    perdente. Il messaggio deve indicare la coda dove si annulla o si ignora, non
    «scegline un'altra», che dentro una fusione non è un passo percorribile
    (round 1 di revisione, F8)."""
    fungo = Ingredient(name="fungo", display_name="Fungo", category=IngredientCategory.VERDURA)
    db_session.add(fungo)
    await db_session.flush()
    termine = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-fungo", display_name="Funghi", occurrences=1,
        decision=TermDecision.MAPPED, ingredient_id=fungo.id, decided_by="ai",
        decided_at=datetime.now(UTC),
    )
    db_session.add(termine)
    await db_session.flush()
    await recategorize_ingredient(db_session, fungo.id, "casa")

    with pytest.raises(RegistryRefusal) as rifiuto:
        await merge_ingredients(db_session, fungo.id, mondo["detersivo"].id)

    assert rifiuto.value.code == RefusalCode.DECISION_REFUSED
    assert rifiuto.value.obstacle is termine
    assert "Funghi" in rifiuto.value.message
    assert "Ingredienti da abbinare" in rifiuto.value.message


# Le tabelle che la fusione tocca (spec §5), più `units`: la rimaterializzazione passa
# da `create_recipe`, che può crearne una. `embedding` e `search_tsv` restano fuori dal
# confronto: un vettore non si confronta con `==`, e la seconda è calcolata dalle altre.
TABELLE_TOCCATE = (
    "ingredients", "ingredient_aliases", "import_terms", "recipe_imports", "recipes",
    "recipe_ingredients", "units", "pantry_items", "shopping_list_items", "products",
    "cooking_events",
)
NON_CONFRONTABILI = {"embedding", "search_tsv"}


async def _fotografia(db_session) -> dict[str, list[str]]:
    """Il contenuto di ogni tabella toccata, riga per riga. I conteggi da soli non
    vedrebbero un UPDATE: un elemento di dispensa spostato e rimesso a posto a metà ha
    lo stesso conteggio di uno mai toccato."""
    foto: dict[str, list[str]] = {}
    for nome in TABELLE_TOCCATE:
        tabella = Base.metadata.tables[nome]
        colonne = [c for c in tabella.c if c.name not in NON_CONFRONTABILI]
        righe = (await db_session.execute(select(*colonne))).all()
        foto[nome] = sorted(repr(tuple(riga)) for riga in righe)
    return foto


async def test_l_anteprima_non_scrive_niente_e_dice_i_numeri_della_fusione(db_session, mondo):
    """Spec §5.1 e §9.4: dopo l'anteprima il database è identico — confrontato riga per
    riga, non sul valore di ritorno — e la fusione vera fatta subito dopo dà gli stessi
    numeri. Gli id si prendono prima: dopo il rollback del SAVEPOINT gli oggetti toccati
    sono scaduti, e leggerne un attributo in una sessione async è un MissingGreenlet."""
    pagina = await _pagina(db_session, SUGO)
    db_session.add(CookingEvent(recipe_id=pagina.recipe_id, servings=2, snapshot={}))
    await db_session.flush()
    perdente, vincitore = mondo["pomodori"].id, mondo["pomodoro"].id

    prima = await _fotografia(db_session)
    anteprima = await preview_merge(db_session, perdente, vincitore)
    dopo = await _fotografia(db_session)

    assert dopo == prima
    vera = await merge_ingredients(db_session, perdente, vincitore)
    assert anteprima == vera
    assert vera.cooking_events_relinked == 1


async def test_un_anteprima_rifiutata_non_lascia_niente(db_session, mondo):
    perdente, vincitore = mondo["pomodori"].id, mondo["detersivo"].id
    prima = await _fotografia(db_session)

    with pytest.raises(RegistryRefusal) as rifiuto:
        await preview_merge(db_session, perdente, vincitore)

    assert rifiuto.value.code == RefusalCode.KIND_MISMATCH
    assert await _fotografia(db_session) == prima


async def test_un_anteprima_rifiutata_per_decisione_lascia_l_ostacolo_leggibile(
    db_session, mondo
):
    """Ruling F12: la rotta di Task 9 serializza `refusal.obstacle` dopo che
    `preview_merge` è tornata o ha sollevato. A quel punto il SAVEPOINT è già stato
    annullato, e un rollback annidato scade gli oggetti toccati al suo interno — il
    termine di DECISION_REFUSED è uno di quelli, e leggerne un attributo dopo sarebbe un
    caricamento pigro, in una sessione async un MissingGreenlet. `preview_merge` deve
    quindi ricaricare l'ostacolo con `session.refresh` dopo il rollback, prima di
    rilanciare, così chi chiama lo trova già leggibile.

    Il campo che conta è `decision`/`ingredient_id`, non `display_name`: `undo_decision`
    (dentro `merge_ingredients`, prima del rifiuto) li porta a `PENDING`/`None`, mentre
    `display_name` non lo tocca mai — un test che guardasse solo `display_name`
    passerebbe anche senza il rollback del SAVEPOINT (Task 6, round 1 di revisione). La
    fotografia dell'intero database, prima e dopo, prova che l'anteprima rifiutata non
    lascia scritto nient'altro."""
    fungo = Ingredient(name="fungo", display_name="Fungo", category=IngredientCategory.VERDURA)
    db_session.add(fungo)
    await db_session.flush()
    termine = ImportTerm(
        source=GIALLOZAFFERANO, term_key="k-fungo", display_name="Funghi", occurrences=1,
        decision=TermDecision.MAPPED, ingredient_id=fungo.id, decided_by="ai",
        decided_at=datetime.now(UTC),
    )
    db_session.add(termine)
    await db_session.flush()
    await recategorize_ingredient(db_session, fungo.id, "casa")

    prima = await _fotografia(db_session)

    with pytest.raises(RegistryRefusal) as rifiuto:
        await preview_merge(db_session, fungo.id, mondo["detersivo"].id)

    assert rifiuto.value.code == RefusalCode.DECISION_REFUSED
    assert rifiuto.value.obstacle.display_name == "Funghi"
    assert rifiuto.value.obstacle.decision == TermDecision.MAPPED
    assert rifiuto.value.obstacle.ingredient_id == fungo.id
    assert await _fotografia(db_session) == prima


@pytest.mark.parametrize("stato_del_vincitore", [ShoppingStatus.PENDING, ShoppingStatus.CHECKED])
async def test_se_il_vincitore_e_gia_in_lista_la_voce_del_perdente_si_toglie(
    db_session, mondo, stato_del_vincitore
):
    """Revisione finale di S9: la fusione spostava ogni voce di lista senza guardare,
    e il vincitore finiva due volte in lista. Se il vincitore ha già una voce attiva —
    da comprare o nel carrello, come per `active_item_for` — quella attiva del
    perdente si toglie come la toglie la X della lista: archiviata, e sul vincitore
    per la storia. La voce che resta è quella del vincitore, col suo testo: il testo
    del perdente («pomodori») non vi si aggiunge. La storia si sposta sempre."""
    pomodoro, pomodori = mondo["pomodoro"], mondo["pomodori"]
    db_session.add_all([
        _voce_di_lista(pomodoro, stato_del_vincitore, "pomodoro"),
        _voce_di_lista(pomodori, ShoppingStatus.DONE, "pomodori comprati"),
    ])
    await db_session.flush()

    conti = await merge_ingredients(db_session, pomodori.id, pomodoro.id)

    assert (conti.shopping_items, conti.shopping_items_dropped) == (1, 1)
    assert await _lista(db_session) == [
        ("pomodori", "pomodoro", ShoppingStatus.ARCHIVED),
        ("pomodori comprati", "pomodoro", ShoppingStatus.DONE),
        ("pomodoro", "pomodoro", stato_del_vincitore),
    ]


async def test_se_il_vincitore_ha_in_lista_solo_la_storia_la_voce_del_perdente_si_sposta(
    db_session, mondo
):
    pomodoro, pomodori = mondo["pomodoro"], mondo["pomodori"]
    db_session.add(_voce_di_lista(pomodoro, ShoppingStatus.ARCHIVED, "pomodoro tolto"))
    await db_session.flush()

    conti = await merge_ingredients(db_session, pomodori.id, pomodoro.id)

    assert (conti.shopping_items, conti.shopping_items_dropped) == (1, 0)
    assert await _lista(db_session) == [
        ("pomodori", "pomodoro", ShoppingStatus.PENDING),
        ("pomodoro tolto", "pomodoro", ShoppingStatus.ARCHIVED),
    ]
