import pytest

from app.domain.change_cards import STATUS_RANK, adds_to_list, most_consumed

STATI = list(STATUS_RANK)


@pytest.mark.parametrize("a", STATI)
@pytest.mark.parametrize("b", STATI)
def test_most_consumed(a, b):
    expected = a if STATUS_RANK[a] >= STATUS_RANK[b] else b
    assert most_consumed(a, b) == expected
    assert most_consumed(b, a) == expected


def test_adds_to_list():
    assert [s for s in STATI if adds_to_list(s)] == ["finished"]
