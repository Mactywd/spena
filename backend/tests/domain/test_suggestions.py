"""La regola che decide quali suggerimenti si vedono (spec
docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md, §6 e §10).

Table-driven come `test_rules.py`: la regola è pura, e qui si prova ogni ramo — solo
riscontri, riscontri e sfumati, solo sfumati sopra e sotto le due soglie, il limite.
"""

from dataclasses import dataclass

import pytest

from app.domain.suggestions import FOLD_FROM, FOLD_TO, fold_for_match, trim_suggestions


@dataclass(frozen=True)
class C:
    name: str
    best: float
    is_hit: bool


def names(rows: list[C]) -> list[str]:
    return [row.name for row in rows]


@pytest.mark.parametrize(
    "candidates,limit,expected",
    [
        pytest.param([], 10, [], id="niente in ingresso, niente in uscita"),
        pytest.param(
            [C("zucchero", 0.5, True), C("zucchina", 0.5, True), C("zucchero a velo", 0.29, True)],
            10,
            ["zucchero", "zucchina", "zucchero a velo"],
            id="solo riscontri: passano tutti, anche sotto il pavimento",
        ),
        pytest.param(
            [C("olio di oliva", 0.45, True), C("olive verdi", 0.9, False)],
            10,
            ["olio di oliva"],
            id="un riscontro basta a tenere fuori ogni sfumato, anche il più simile",
        ),
        pytest.param(
            [C("pomodoro", 0.60, False), C("pomodorini", 0.50, False), C("porro", 0.45, False)],
            10,
            ["pomodoro", "pomodorini"],
            id="senza riscontri, gli sfumati da 0,8 per il primo in su (0,48)",
        ),
        pytest.param(
            [C("bietola", 0.35, False), C("bresaola", 0.30, False), C("burro", 0.29, False)],
            10,
            ["bietola", "bresaola"],
            id="il pavimento vale quando 0,8 per il primo gli sta sotto, e 0,30 passa",
        ),
        pytest.param(
            [C("zucchero", 0.28, False)],
            10,
            [],
            id="senza riscontri e sotto il pavimento: la lista è vuota",
        ),
        pytest.param(
            [C(f"pasta {i:02}", 0.4, True) for i in range(12)],
            10,
            [f"pasta {i:02}" for i in range(10)],
            id="più riscontri del limite: i primi dieci",
        ),
        pytest.param(
            [C(f"riso {i:02}", 0.5, False) for i in range(12)],
            10,
            [f"riso {i:02}" for i in range(10)],
            id="più sfumati del limite: i primi dieci",
        ),
        pytest.param(
            [C("tè", 0.2, True), C("tempeh", 0.25, True), C("patate", 0.4, False)],
            1,
            ["tè"],
            id="il limite vale anche sotto dieci, e l'ordine non cambia",
        ),
    ],
)
def test_trim_suggestions(candidates, limit, expected):
    assert names(trim_suggestions(candidates, limit)) == expected


def test_le_due_stringhe_di_translate_sono_lunghe_uguali():
    """`translate()` di Postgres cancella in silenzio un carattere di FOLD_FROM senza il
    suo corrispondente in FOLD_TO: una lettera accentata aggiunta da una parte sola
    sparirebbe dal nome, invece di perdere l'accento, e nessun errore lo direbbe."""
    assert len(FOLD_FROM) == len(FOLD_TO)


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("caffè", "caffe"),
        ("tè", "te"),
        ("perché più così", "perche piu cosi"),
        ("sott'olio", "sott olio"),
        ("sott’olio", "sott olio"),
        ("pan-carré", "pan carre"),
        ("  olio   di  semi ", "olio di semi"),
        ("jalapeño, açaí", "jalapeno, acai"),
    ],
)
def test_fold_for_match(raw, expected):
    assert fold_for_match(raw) == expected
