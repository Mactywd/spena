import pytest

from app.domain.rules import (
    Availability,
    IngredientRole,
    PantryStatus,
    availability_of,
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
