import random
import uuid

from app.cli.measure_suggestions import (
    SEED,
    CatalogEntry,
    Probe,
    build_probes,
    format_report,
    load_catalog,
    measure,
    typos,
)
from app.db.models.ingredient import Ingredient, IngredientCategory


def test_tre_refusi_diversi_dalla_parola_e_sempre_gli_stessi():
    primi = typos("pomodoro", random.Random(1))
    assert primi == typos("pomodoro", random.Random(1))
    assert len(primi) == 3
    assert all(refuso != "pomodoro" for refuso in primi)
    # una lettera che manca, due scambiate, una sostituita: la lunghezza cambia di uno
    # solo nel primo
    assert [len(refuso) for refuso in primi] == [7, 8, 8]


def test_le_prove_nascono_dal_nome_e_dagli_alias():
    """Le regole del §3.2 della bozza: i prefissi di 3–6 lettere e il nome intero, i
    prefissi di 4 e 6 lettere e l'alias intero, i due caratteri a parte, tre refusi sul
    nome intero e tre sui primi sei caratteri."""
    target = uuid.uuid4()
    probes = build_probes([CatalogEntry(target, "pomodoro", ("pelati",))], random.Random(SEED))

    def testi(family: str) -> list[str]:
        return [p.text for p in probes if p.family == family]

    assert testi("digitazione") == ["pom", "pomo", "pomod", "pomodo", "pomodoro", "pela", "pelati"]
    assert testi("due lettere") == ["po"]
    assert len(testi("refusi")) == 6
    assert {p.target for p in probes} == {target}


async def test_la_misura_conta_chi_resta_e_chi_si_perde(db_session):
    """Sul Postgres vero, con le due funzioni vere. «zucch» → zucchina: c'è prima e dopo,
    ma non è prima (zucchero, alfabetico); le righe scendono da 3 a 2 (via la zucca).
    «zenzero» → zucchero: prima c'era (0,214), dopo no, ed è un perso."""
    for nome in ("zucchero", "zucchina", "zucca"):
        db_session.add(Ingredient(name=nome, display_name=nome.capitalize(),
                                  category=IngredientCategory.ALTRO))
    await db_session.flush()
    catalog = {entry.name: entry for entry in await load_catalog(db_session)}
    assert {"zucchero", "zucchina", "zucca"} <= catalog.keys()

    stats = await measure(db_session, [
        Probe("digitazione", "zucch", catalog["zucchina"].id),
        Probe("digitazione", "zenzero", catalog["zucchero"].id),
    ])

    digitazione = stats["digitazione"]
    assert digitazione.probes == 2
    assert (digitazione.kept_before, digitazione.kept_after) == (2, 1)
    assert (digitazione.first_before, digitazione.first_after) == (1, 0)
    assert digitazione.rows_before == [3, 1]
    assert digitazione.rows_after == [2, 0]
    assert digitazione.lost == ["zenzero"]
    assert "digitazione: 2 prove" in format_report(stats)
