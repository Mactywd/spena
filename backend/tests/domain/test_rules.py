import pytest

from app.db.models.ingredient import IngredientCategory
from app.domain.rules import (
    LOW_MAX_FILL,
    Availability,
    IngredientKind,
    IngredientRole,
    NON_FOOD_CATEGORIES,
    PantryStatus,
    SECONDARY_CATEGORIES,
    availability_of,
    default_role,
    is_cookable,
    is_satisfied,
    kind_for_category,
    missing_count,
    status_for_fill,
)

AVAILABLE, LOW, FINISHED = PantryStatus.AVAILABLE, PantryStatus.LOW, PantryStatus.FINISHED
PRIMARY, SECONDARY = IngredientRole.PRIMARY, IngredientRole.SECONDARY


@pytest.mark.parametrize(
    "statuses,expected",
    [
        ([], Availability.MISSING),
        ([FINISHED], Availability.MISSING),
        ([FINISHED, FINISHED], Availability.MISSING),
        ([LOW], Availability.LOW),
        ([LOW, FINISHED], Availability.LOW),
        ([AVAILABLE], Availability.AVAILABLE),
        ([AVAILABLE, FINISHED], Availability.AVAILABLE),
        # il migliore vince: due yogurt, uno pieno e uno agli sgoccioli
        ([LOW, AVAILABLE], Availability.AVAILABLE),
        ([FINISHED, LOW, AVAILABLE], Availability.AVAILABLE),
    ],
)
def test_availability_takes_the_best_active_status(statuses, expected):
    assert availability_of(statuses) is expected


@pytest.mark.parametrize(
    "role,availability,expected",
    [
        (PRIMARY, Availability.AVAILABLE, True),
        (PRIMARY, Availability.LOW, False),
        (PRIMARY, Availability.MISSING, False),
        (SECONDARY, Availability.AVAILABLE, True),
        (SECONDARY, Availability.LOW, True),
        (SECONDARY, Availability.MISSING, False),
    ],
)
def test_satisfaction_depends_on_role(role, availability, expected):
    assert is_satisfied(role, availability) is expected


def test_missing_count_and_cookability():
    # pasta al pomodoro: pomodoro principale e quasi finito, aglio secondario e quasi finito
    requirements = [
        (PRIMARY, Availability.LOW),
        (SECONDARY, Availability.LOW),
    ]
    assert missing_count(requirements) == 1
    assert is_cookable(requirements) is False

    # soffritto: lo stesso pomodoro, ma in ruolo secondario
    requirements = [
        (SECONDARY, Availability.LOW),
        (PRIMARY, Availability.AVAILABLE),
    ]
    assert missing_count(requirements) == 0
    assert is_cookable(requirements) is True


def test_recipe_without_ingredients_is_cookable():
    assert is_cookable([]) is True
    assert missing_count([]) == 0


@pytest.mark.parametrize(
    "category, quantity, expected",
    [
        # la dose decide da sola: «q.b.» vuol dire che si aggiusta a piacere
        ("cereali", "q.b.", IngredientRole.SECONDARY),
        ("cereali", "qb", IngredientRole.SECONDARY),
        ("cereali", "q.b. (circa due cucchiai)", IngredientRole.SECONDARY),
        ("cereali", "a piacere", IngredientRole.SECONDARY),
        ("cereali", "quanto basta", IngredientRole.SECONDARY),
        # la categoria decide da sola: spezie e condimenti si riducono senza
        # snaturare il piatto, anche quando la dose è precisa
        ("spezie", "2 foglie", IngredientRole.SECONDARY),
        ("condimenti", "2 cucchiai", IngredientRole.SECONDARY),
        # tutto il resto con una dose vera è principale
        ("cereali", "320 g", IngredientRole.PRIMARY),
        ("carne", "80 g", IngredientRole.PRIMARY),
        ("latticini", "100 g", IngredientRole.PRIMARY),
        ("verdura", "1 spicchio", IngredientRole.PRIMARY),
        # dose assente non è dose «q.b.»: non si inventa un secondario
        ("verdura", None, IngredientRole.PRIMARY),
        ("verdura", "", IngredientRole.PRIMARY),
    ],
)
def test_default_role(category, quantity, expected):
    assert default_role(category, quantity) is expected


def test_ogni_categoria_e_decisa():
    """Nessuna categoria dell'anagrafica resta senza risposta, e ognuna delle
    dodici ha il suo ruolo atteso scritto qui — non ricalcolato dall'implementazione,
    altrimenti il test proverebbe solo che la funzione è d'accordo con se stessa."""
    ruoli_attesi = {
        IngredientCategory.VERDURA: IngredientRole.PRIMARY,
        IngredientCategory.FRUTTA: IngredientRole.PRIMARY,
        IngredientCategory.CARNE: IngredientRole.PRIMARY,
        IngredientCategory.PESCE: IngredientRole.PRIMARY,
        IngredientCategory.LATTICINI: IngredientRole.PRIMARY,
        IngredientCategory.CEREALI: IngredientRole.PRIMARY,
        IngredientCategory.LEGUMI: IngredientRole.PRIMARY,
        IngredientCategory.CONDIMENTI: IngredientRole.SECONDARY,
        IngredientCategory.SPEZIE: IngredientRole.SECONDARY,
        IngredientCategory.BEVANDE: IngredientRole.PRIMARY,
        IngredientCategory.DOLCI: IngredientRole.PRIMARY,
        IngredientCategory.ALTRO: IngredientRole.PRIMARY,
        # Non raggiungono qui oggi: la guardia che li fermerà arriva in create_recipe
        # (Task 5). Stanno qui per integrità della mappa e per il ruolo corretto se mai vi arrivassero.
        IngredientCategory.CASA: IngredientRole.PRIMARY,
        IngredientCategory.IGIENE: IngredientRole.PRIMARY,
    }
    assert set(ruoli_attesi) == set(IngredientCategory)
    for category, expected in ruoli_attesi.items():
        assert default_role(category, "100 g") is expected


def test_le_categorie_secondarie_esistono_in_anagrafica():
    """`rules.py` è puro e non importa i modelli: le due stringhe potrebbero
    diventare nomi di categorie che non esistono più, e la deduzione smetterebbe
    di funzionare senza che nessun test se ne accorga."""
    assert SECONDARY_CATEGORIES <= {str(value) for value in IngredientCategory}


@pytest.mark.parametrize(
    "posizione, atteso",
    [
        (0, PantryStatus.FINISHED),
        (1, PantryStatus.LOW),
        (15, PantryStatus.LOW),
        (LOW_MAX_FILL, PantryStatus.LOW),
        (LOW_MAX_FILL + 1, PantryStatus.AVAILABLE),
        (100, PantryStatus.AVAILABLE),
    ],
)
def test_la_posizione_del_cursore_decide_lo_stato(posizione, atteso):
    assert status_for_fill(posizione) is atteso


def test_le_tre_zone_coprono_tutto_e_non_tornano_indietro():
    """Nessun buco fra 0 e 100, e nessuna inversione.

    Una soglia scritta con un `<` al posto di un `<=` lascia un valore scoperto o
    crea un'isola gialla dentro il verde, e un test a campione può non passarci
    sopra. Qui si controllano tutti e 101 i valori.
    """
    ordine = {PantryStatus.FINISHED: 0, PantryStatus.LOW: 1, PantryStatus.AVAILABLE: 2}
    gradini = [ordine[status_for_fill(posizione)] for posizione in range(0, 101)]
    assert gradini == sorted(gradini)
    assert set(gradini) == {0, 1, 2}


def test_kind_for_category_su_ogni_reparto():
    """Ogni valore dell'enum, non un campione: è la mappa che decide le guardie.

    Scritta per esteso e non come «tutto quel che non è in NON_FOOD_CATEGORIES»,
    che sarebbe la stessa frase della produzione ricopiata nel test — e un test
    che ripete l'implementazione non può vederla sbagliata.
    """
    atteso = {
        IngredientCategory.VERDURA: IngredientKind.FOOD,
        IngredientCategory.FRUTTA: IngredientKind.FOOD,
        IngredientCategory.CARNE: IngredientKind.FOOD,
        IngredientCategory.PESCE: IngredientKind.FOOD,
        IngredientCategory.LATTICINI: IngredientKind.FOOD,
        IngredientCategory.CEREALI: IngredientKind.FOOD,
        IngredientCategory.LEGUMI: IngredientKind.FOOD,
        IngredientCategory.CONDIMENTI: IngredientKind.FOOD,
        IngredientCategory.SPEZIE: IngredientKind.FOOD,
        IngredientCategory.BEVANDE: IngredientKind.FOOD,
        IngredientCategory.DOLCI: IngredientKind.FOOD,
        IngredientCategory.ALTRO: IngredientKind.FOOD,
        IngredientCategory.CASA: IngredientKind.NON_FOOD,
        IngredientCategory.IGIENE: IngredientKind.NON_FOOD,
    }

    assert set(atteso) == set(IngredientCategory), (
        "un reparto nuovo è nato senza che nessuno decidesse da che parte sta"
    )
    for categoria, kind in atteso.items():
        assert kind_for_category(str(categoria)) is kind, categoria


def test_i_reparti_non_alimentari_esistono_davvero():
    """Come per SECONDARY_CATEGORIES: un nome scritto male qui non è un errore
    visibile, è una guardia che smette di scattare in silenzio."""
    assert NON_FOOD_CATEGORIES <= {str(value) for value in IngredientCategory}
