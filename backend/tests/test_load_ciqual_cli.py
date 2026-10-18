"""Il comando che carica la tabella CIQUAL (S4, fetta 1): quel che dice a chi lo lancia,
e quel che non fa. Il lavoro vero lo provano i test del lettore e del repository."""

from sqlalchemy import select

from app.cli import load_ciqual
from app.cli.load_ciqual import main
from app.db.models.nutrition import CiqualFood
from app.repositories.ciqual import count_foods
from ciqual_fixture import FOODS, HEADER, fixture_xlsx


class _SessioneFinta:
    """`SessionLocal()` nel test: consegna la sessione della fixture invece di aprirne una
    vera. Stessa forma di `test_decide_units_cli.py`."""

    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, *exc_info):
        return False


def _nessun_database():
    raise AssertionError("la prova a secco non apre il database")


async def test_la_prova_a_secco_conta_e_non_apre_il_database(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(load_ciqual, "SessionLocal", _nessun_database)

    assert await main(["--dry-run", str(fixture_xlsx(tmp_path))]) == 0

    stampato = capsys.readouterr().out
    assert "ciqual-prova.xlsx: 16 alimenti letti." in stampato
    assert "  Energia (kcal): 16 alimenti" in stampato
    assert "  Ferro (mg): 15 alimenti, 1 illeggibile" in stampato
    assert "Nel vocabolario ma non nel file: " in stampato
    assert "Colonne non usate: 1, per esempio «Eau (g/100 g)»." in stampato
    assert stampato.rstrip().endswith("Prova a secco: niente è stato scritto.")


async def test_carica_e_ricaricato_aggiorna_per_codice(db_session, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(load_ciqual, "SessionLocal", lambda: _SessioneFinta(db_session))
    percorso = str(fixture_xlsx(tmp_path))

    assert await main([percorso]) == 0
    assert await main([percorso]) == 0

    assert await count_foods(db_session) == 16
    assert "16 alimenti scritti in CIQUAL 2025." in capsys.readouterr().out


async def test_un_alimento_che_il_file_non_ha_piu_resta_e_si_dice(
    db_session, tmp_path, monkeypatch, capsys
):
    db_session.add(CiqualFood(code="99999", name_fr="Vecchio", group_fr=None, nutrients={}, version="2020"))
    await db_session.flush()
    monkeypatch.setattr(load_ciqual, "SessionLocal", lambda: _SessioneFinta(db_session))

    assert await main([str(fixture_xlsx(tmp_path))]) == 0

    assert "1 alimento già nel database non è nel file: resta com'è." in capsys.readouterr().out
    assert (
        await db_session.execute(select(CiqualFood.name_fr).where(CiqualFood.code == "99999"))
    ).scalar_one() == "Vecchio"


async def test_un_file_sbagliato_non_scrive_niente(db_session, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(load_ciqual, "SessionLocal", lambda: _SessioneFinta(db_session))
    righe = [[colonna.replace("Fer (mg", "Fer (µg") for colonna in HEADER], *FOODS]

    assert await main([str(fixture_xlsx(tmp_path, righe))]) == 1

    stampato = capsys.readouterr().out
    assert "Il file non va:" in stampato and "Fer (µg/100 g)" in stampato
    assert "Niente è stato scritto." in stampato
    assert await count_foods(db_session) == 0


async def test_senza_file_dice_dove_scaricarlo(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(load_ciqual, "CANDIDATE_FILES", (tmp_path / "manca.xlsx",))

    assert await main([]) == 1
    assert "https://doi.org/10.57745/RDMHWY" in capsys.readouterr().out

    assert await main([str(tmp_path / "altro.xlsx")]) == 1
    assert "Non trovo il file" in capsys.readouterr().out


async def test_argomenti_sbagliati_escono_con_errore(capsys):
    assert await main(["--azzera"]) == 2
    assert "argomento sconosciuto: --azzera" in capsys.readouterr().out
    assert await main(["uno.xlsx", "due.xlsx"]) == 2
