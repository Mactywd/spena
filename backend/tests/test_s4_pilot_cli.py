"""Il comando del pilota (S4): gli argomenti, la tabella vuota, l'AI che non risponde."""

import json

from app.cli import s4_pilot as comando
from app.cli.s4_pilot import main
from app.domain.ciqual import CiqualRow
from app.repositories.ciqual import upsert_foods


class _SessioneFinta:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


def _casi(tmp_path, atteso="^tomate"):
    percorso = tmp_path / "casi.json"
    percorso.write_text(
        json.dumps({"abbinamenti": [{"ingrediente": "pomodoro", "reparto": "verdura", "atteso": atteso}]})
    )
    return str(percorso)


async def test_argomenti_sbagliati_escono_con_errore(capsys):
    assert await main(["--azzera"]) == 2
    assert await main(["--casi"]) == 2
    assert "uso: python -m app.cli.s4_pilot" in capsys.readouterr().out


async def test_casi_illeggibili(tmp_path, capsys):
    assert await main(["--casi", _casi(tmp_path, atteso="(")]) == 1
    assert "I casi del pilota non si leggono" in capsys.readouterr().out


async def test_con_la_tabella_vuota_dice_di_caricarla(db_session, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(comando, "SessionLocal", lambda: _SessioneFinta(db_session))

    assert await main(["--casi", _casi(tmp_path)]) == 1
    assert "La tabella CIQUAL è vuota" in capsys.readouterr().out


async def test_senza_chiave_il_pilota_non_si_fa_e_lo_dice(db_session, tmp_path, monkeypatch, capsys):
    from app.core.config import get_settings

    get_settings.cache_clear()
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    try:
        await upsert_foods(db_session, [CiqualRow("90001", "Tomate, crue", "légumes", {"kcal": 18.0})])
        monkeypatch.setattr(comando, "SessionLocal", lambda: _SessioneFinta(db_session))

        assert await main(["--casi", _casi(tmp_path)]) == 1

        stampato = capsys.readouterr().out
        assert (
            "il pilota non si è potuto fare: l'AI non ha risposto "
            "(OPENROUTER_API_KEY non configurata)." in stampato
        )
        assert "Spesa del pilota: 0,0000 $ in 1 chiamata, 1 senza costo dichiarato." in stampato
    finally:
        get_settings.cache_clear()
