"""La CLI dell'anagrafica è un guscio sul servizio (S9 §3).

`test_fix_registry_cli.py` prova che il comando fa ancora quel che faceva, e non si
tocca. Questo prova che lo fa chiamando `app/services/registry.py` e non una sua copia
delle guardie: la prima lezione di CLAUDE.md — se la copia restasse, lo schermo e il
comando avrebbero due guardie, e la prima a scollarsi sarebbe quella sul non alimentare.
"""

import inspect

from app.cli import fix_registry


def test_le_correzioni_passano_dal_servizio():
    sorgente = inspect.getsource(fix_registry)

    assert "from app.services import registry" in sorgente
    for copia in (
        "kind_for_category",
        "delete_ingredient_if_unused",
        "merge_quantities",
        "remember_alias",
    ):
        assert copia not in sorgente, f"fix_registry ha ancora la sua copia: {copia}"
