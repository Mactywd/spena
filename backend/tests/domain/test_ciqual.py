"""Come si legge la tabella CIQUAL, senza aprire un file (S4, fetta 1).

Il file vero del 2025 non l'ha visto nessuno di chi ha scritto questo codice (spec §3): le
colonne si riconoscono dal nome, e queste prove guardano soprattutto le piccole differenze
di scrittura che una nuova edizione può portare — un accento, «N°» con o senza spazio, il
micro scritto con la lettera greca — e il rifiuto quando l'unità non è quella attesa.
"""

import pytest

from app.domain.ciqual import (
    CIQUAL_NAMES,
    REQUIRED_KEYS,
    CiqualFormatError,
    food_from_row,
    map_columns,
    normalize_name,
    parse_teneur,
    split_header,
)
from app.domain.nutrients import NUTRIENT_FIELDS

INTESTAZIONE = [
    "alim_grp_code",
    "alim_grp_nom_fr",
    "alim_ssgrp_nom_fr",
    "alim_code",
    "alim_nom_fr",
    "Energie, Règlement UE N° 1169/2011 (kcal/100 g)",
    "Eau (g/100 g)",
    "Protéines, N x facteur de Jones (g/100 g)",
    "Glucides (g/100 g)",
    "Lipides (g/100 g)",
    "Fer (mg/100 g)",
    "Iode (µg/100 g)",
]


@pytest.mark.parametrize(
    ("scritto", "atteso"),
    [
        ("Energie, Règlement UE N° 1169/2011", "energie, reglement ue n°1169/2011"),
        ("Énergie, Règlement UE N°1169/2011", "energie, reglement ue n°1169/2011"),
        ("  AG   saturés ", "ag satures"),
        ("Œuf, cru", "oeuf, cru"),
        ("Protéines, N x facteur de Jones", "proteines, n x facteur de jones"),
    ],
)
def test_normalize_name(scritto, atteso):
    assert normalize_name(scritto) == atteso


@pytest.mark.parametrize(
    ("intestazione", "attesa"),
    [
        ("Fer (mg/100 g)", ("fer", "mg")),
        ("Iode (µg/100 g)", ("iode", "ug")),
        # il micro scritto con la lettera greca, come può capitare in un'altra edizione
        ("Sélénium (μg/100 g)", ("selenium", "ug")),
        ("Energie, Règlement UE N° 1169/2011 (kcal/100 g)", ("energie, reglement ue n°1169/2011", "kcal")),
        ("Eau (g/100g)", ("eau", "g")),
        ("alim_code", None),
    ],
)
def test_split_header(intestazione, attesa):
    assert split_header(intestazione) == attesa


@pytest.mark.parametrize(
    ("cella", "valore"),
    [
        ("10,4", 10.4),
        ("3.2", 3.2),
        (" 18 ", 18.0),
        ("traces", 0.0),
        ("Traces", 0.0),
        # sotto il limite di quantificazione: la metà del limite (spec §4.4)
        ("< 0,5", 0.25),
        ("<0,5", 0.25),
        # assente: mai zero
        ("-", None),
        ("", None),
        ("   ", None),
        (None, None),
    ],
)
def test_parse_teneur(cella, valore):
    assert parse_teneur(cella) == valore


@pytest.mark.parametrize("cella", ["n.d.", "abc", "-3", "nan"])
def test_parse_teneur_illeggibile_solleva(cella):
    with pytest.raises(ValueError):
        parse_teneur(cella)


def test_map_columns_riconosce_le_colonne_per_nome():
    colonne = map_columns(INTESTAZIONE)

    assert (colonne.code, colonne.name, colonne.group, colonne.subgroup) == (3, 4, 1, 2)
    assert colonne.nutrients == {"kcal": 5, "protein": 7, "carbs": 8, "fat": 9, "iron": 10, "iodine": 11}
    # l'acqua non è nel vocabolario: una colonna non usata, detta, non un errore
    assert colonne.unused == ("Eau (g/100 g)",)
    assert "vitamin_c" in colonne.absent and "iron" not in colonne.absent


def test_map_columns_rifiuta_un_unita_diversa_da_quella_del_vocabolario():
    """Il ferro in µg invece che in mg sarebbe mille volte sbagliato su ogni riga: il
    file si rifiuta intero, e il messaggio nomina la colonna."""
    sbagliata = [*INTESTAZIONE[:10], "Fer (µg/100 g)", INTESTAZIONE[11]]

    with pytest.raises(CiqualFormatError, match="Fer"):
        map_columns(sbagliata)


def test_map_columns_rifiuta_un_file_senza_codice():
    with pytest.raises(CiqualFormatError, match="alim_code"):
        map_columns([colonna for colonna in INTESTAZIONE if colonna != "alim_code"])


def test_map_columns_rifiuta_un_file_senza_una_colonna_d_obbligo():
    with pytest.raises(CiqualFormatError, match="Grassi"):
        map_columns([colonna for colonna in INTESTAZIONE if not colonna.startswith("Lipides")])


def test_i_nomi_coprono_il_vocabolario_tranne_cinque():
    """Trenta nutrienti dell'Allegato XIII: fuori la vitamina A (CIQUAL dà retinolo e
    beta-carotene separati) e i quattro che CIQUAL non ha (spec §4.3)."""
    assert set(CIQUAL_NAMES) <= set(NUTRIENT_FIELDS)
    assert set(NUTRIENT_FIELDS) - set(CIQUAL_NAMES) == {
        "vitamin_a", "biotin", "fluoride", "chromium", "molybdenum",
    }
    assert set(REQUIRED_KEYS) == {"kcal", "protein", "carbs", "fat"}
    for nomi in CIQUAL_NAMES.values():
        for nome in nomi:
            assert nome == normalize_name(nome), nome


def test_food_from_row_legge_codice_nome_gruppo_e_valori():
    colonne = map_columns(INTESTAZIONE)
    riga = ["02", "légumes et fruits", "légumes", "20047.0", " Tomate, crue ", "18", "94", "0,86", "2,5", "-", "n.d."]

    alimento, illeggibili = food_from_row(riga, colonne)

    # un codice letto come numero da un foglio («20047.0») torna il codice
    assert alimento.code == "20047"
    assert alimento.name_fr == "Tomate, crue"
    # il sottogruppo dice di più del gruppo
    assert alimento.group_fr == "légumes"
    # i lipidi «-» mancano; il ferro illeggibile manca ed è contato; l'iodio è oltre la
    # fine della riga, cioè una cella vuota
    assert alimento.nutrients == {"kcal": 18.0, "protein": 0.86, "carbs": 2.5}
    assert illeggibili == ["iron"]


def test_food_from_row_salta_una_riga_senza_codice_o_senza_nome():
    colonne = map_columns(INTESTAZIONE)

    assert food_from_row([], colonne) == (None, [])
    assert food_from_row(["02", "x", "y", "", "Tomate"], colonne) == (None, [])
    assert food_from_row(["02", "x", "y", "20047", "  "], colonne) == (None, [])


def test_food_from_row_un_sottogruppo_trattino_lascia_il_gruppo():
    colonne = map_columns(INTESTAZIONE)

    alimento, _ = food_from_row(["02", "légumes et fruits", "-", "20047", "Tomate, crue", "18"], colonne)

    assert alimento.group_fr == "légumes et fruits"
