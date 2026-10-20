"""Il lettore del file CIQUAL (S4, fetta 1), su un XLSX costruito al volo.

Il lettore non ha dipendenze: legge lo zip e i suoi XML. Queste prove guardano le cose
che un foglio vero fa e una tabella pulita no — una cella numerica in mezzo alle
stringhe, una cella vuota che non è scritta, un titolo sopra l'intestazione.
"""

import zipfile

import pytest

from app.domain.ciqual import CiqualFormatError
from app.services.ciqual_file import read_ciqual
from ciqual_fixture import FOODS, HEADER, fixture_xlsx


def _per_codice(letto):
    return {alimento.code: alimento for alimento in letto.foods}


def test_legge_tutti_gli_alimenti_del_file(tmp_path):
    letto = read_ciqual(fixture_xlsx(tmp_path))

    alimenti = _per_codice(letto)
    assert len(alimenti) == 16
    pomodoro = alimenti["90001"]
    assert (pomodoro.name_fr, pomodoro.group_fr) == ("Tomate, crue", "légumes")
    assert pomodoro.nutrients == {
        "kcal": 18.0, "protein": 0.86, "carbs": 2.5, "fat": 0.3, "sugars": 2.4,
        "saturated_fat": 0.05, "fiber": 1.2, "salt": 0.01, "iron": 0.3,
        "vitamin_c": 14.0, "iodine": 0.0,
    }


def test_una_cella_numerica_si_legge_come_le_altre(tmp_path):
    """Le proteine del pomodoro sono un numero nella cella, non una stringa condivisa."""
    alimenti = _per_codice(read_ciqual(fixture_xlsx(tmp_path)))

    assert alimenti["90001"].nutrients["protein"] == 0.86


def test_una_cella_vuota_non_sposta_le_colonne_dopo(tmp_path):
    """La vitamina C del basilico non è scritta: l'iodio, che viene dopo, resta suo."""
    basilico = _per_codice(read_ciqual(fixture_xlsx(tmp_path)))["90007"]

    assert "vitamin_c" not in basilico.nutrients
    assert basilico.nutrients["iodine"] == 1.0


def test_tracce_sotto_il_limite_e_trattini(tmp_path):
    alimenti = _per_codice(read_ciqual(fixture_xlsx(tmp_path)))

    pasta = alimenti["90003"]
    assert pasta.nutrients["salt"] == 0.01  # «< 0,02»
    assert pasta.nutrients["iodine"] == 2.5  # «< 5»
    assert "vitamin_c" not in pasta.nutrients  # «-»
    olio = alimenti["90006"]
    assert olio.nutrients["salt"] == 0.0  # «traces»
    assert "fiber" not in olio.nutrients  # «-»: assente, non zero


def test_un_valore_illeggibile_resta_assente_e_si_conta(tmp_path):
    letto = read_ciqual(fixture_xlsx(tmp_path))

    assert "iron" not in _per_codice(letto)["90012"].nutrients
    assert letto.unreadable == {"iron": 1}


def test_dice_quanti_valori_ha_ogni_nutriente_e_cosa_manca(tmp_path):
    letto = read_ciqual(fixture_xlsx(tmp_path))

    assert letto.with_value["kcal"] == 16
    assert letto.with_value["iron"] == 15
    assert letto.with_value["vitamin_c"] == 12
    assert letto.with_value["iodine"] == 11
    assert "vitamin_d" in letto.absent
    assert letto.unused == ("Eau (g 100 g)",)


def test_l_intestazione_puo_stare_sotto_un_titolo(tmp_path):
    righe = [["Table Ciqual 2025"], [], HEADER, *FOODS[:2]]

    letto = read_ciqual(fixture_xlsx(tmp_path, righe))

    assert sorted(_per_codice(letto)) == ["90001", "90002"]


def test_senza_alim_code_il_file_si_rifiuta(tmp_path):
    righe = [[colonna if colonna != "alim_code" else "codice" for colonna in HEADER], *FOODS]

    with pytest.raises(CiqualFormatError, match="alim_code"):
        read_ciqual(fixture_xlsx(tmp_path, righe))


def test_un_unita_sbagliata_rifiuta_tutto_il_file(tmp_path):
    righe = [[colonna.replace("Fer (mg", "Fer (µg") for colonna in HEADER], *FOODS]

    with pytest.raises(CiqualFormatError, match="Fer"):
        read_ciqual(fixture_xlsx(tmp_path, righe))


def test_un_file_che_non_e_un_xlsx_si_rifiuta(tmp_path):
    finto = tmp_path / "ciqual.xlsx"
    finto.write_text("alim_code;alim_nom_fr\n")

    with pytest.raises(CiqualFormatError, match="ciqual.xlsx"):
        read_ciqual(finto)


def test_doppioni_e_righe_senza_codice_si_contano(tmp_path):
    senza_codice = ["02", "x", "y", None, "Senza codice", "10"]
    righe = [HEADER, FOODS[0], FOODS[0], senza_codice, []]

    letto = read_ciqual(fixture_xlsx(tmp_path, righe))

    assert len(letto.foods) == 1
    assert (letto.duplicate_codes, letto.skipped_rows) == (1, 1)


def test_un_archivio_rovinato_dice_che_il_file_non_va(tmp_path):
    """Un foglio con il flusso deflate guasto non esce come errore di zlib, ma come «il file non va»."""
    path = fixture_xlsx(tmp_path)
    with zipfile.ZipFile(path) as archive:
        header_offset = archive.getinfo("xl/worksheets/sheet1.xml").header_offset
    raw = bytearray(path.read_bytes())
    name_length = int.from_bytes(raw[header_offset + 26 : header_offset + 28], "little")
    extra_length = int.from_bytes(raw[header_offset + 28 : header_offset + 30], "little")
    data_start = header_offset + 30 + name_length + extra_length
    raw[data_start] = 0x07  # primo blocco deflate di tipo 11, non valido: zlib rifiuta
    path.write_bytes(bytes(raw))

    with pytest.raises(CiqualFormatError, match="ciqual-prova.xlsx"):
        read_ciqual(path)
