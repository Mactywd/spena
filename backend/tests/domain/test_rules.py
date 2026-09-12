import pytest

from app.db.models.ingredient import IngredientCategory
from app.domain.rules import (
    Availability,
    SECONDARY_CATEGORIES,
    IngredientRole,
    PantryStatus,
    availability_of,
    default_role,
    is_cookable,
    is_satisfied,
    missing_count,
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


def test_ogni_categoria_e_decisa(category=None):
    """Nessuna categoria dell'anagrafica resta senza risposta."""
    for value in IngredientCategory:
        assert default_role(value, "100 g") in tuple(IngredientRole)


def test_le_categorie_secondarie_esistono_in_anagrafica():
    """`rules.py` è puro e non importa i modelli: le due stringhe potrebbero
    diventare nomi di categorie che non esistono più, e la deduzione smetterebbe
    di funzionare senza che nessun test se ne accorga."""
    assert SECONDARY_CATEGORIES <= {str(value) for value in IngredientCategory}
