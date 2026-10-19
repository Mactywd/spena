"""Le costanti di stato che Starlette ha deprecato non si usano.

`status.HTTP_422_UNPROCESSABLE_ENTITY` stampava 8 `StarletteDeprecationWarning` a ogni
suite, e nessuno li leggeva. Il `filterwarnings` di pyproject.toml fa di quell'avviso un
errore, ma solo dove un test passa; questa prova guarda il sorgente intero, anche le righe
che nessun test attraversa (pulizie del 2026-10-13).
"""

from pathlib import Path

from starlette import status

APP = Path(__file__).resolve().parents[1] / "app"


def test_nessuna_costante_di_stato_deprecata_in_app():
    deprecated = set(status.__deprecated__)
    trovati = [
        f"{path.relative_to(APP.parent)}:{numero}"
        for path in sorted(APP.rglob("*.py"))
        for numero, riga in enumerate(path.read_text().splitlines(), start=1)
        if any(nome in riga for nome in deprecated)
    ]
    assert trovati == []
