"""Come si legge la tabella CIQUAL, senza aprire un file (S4, fetta 1).

Il codice è stato scritto senza aver visto il file vero del 2025 (spec §3), e il file vero
l'ha rifiutato: le sue intestazioni vanno a capo dove le prove le scrivevano su una riga.
Da allora c'è anche l'intestazione vera, copiata dal file (`INTESTAZIONE_2025`). Le
colonne si riconoscono dal nome, e queste prove guardano soprattutto le piccole differenze
di scrittura che una nuova edizione può portare — un accento, «N°» con o senza spazio, il
micro scritto con la lettera greca, un a capo — e il rifiuto quando l'unità non è quella
attesa.
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

# L'intestazione vera, copiata cella per cella da `Table Ciqual 2025_FR_2025_11_03.xlsx`
# (https://doi.org/10.57745/RDMHWY, md5 0d9758ce23f3f13dd63a005bc1bb4f2c). Nel foglio ogni
# cella va a capo con «\r\n»; il parser XML lo legge «\n», ed è così che arriva qui.
INTESTAZIONE_2025 = [
    "alim_grp_code",
    "alim_ssgrp_code",
    "alim_ssssgrp_code",
    "alim_grp_nom_fr",
    "alim_ssgrp_nom_fr",
    "alim_ssssgrp_nom_fr",
    "alim_code",
    "alim_nom_fr",
    "alim_nom_sci",
    "Energie,\nRèglement\nUE N°\n1169\n2011 (kJ\n100 g)",
    "Energie,\nRèglement\nUE N°\n1169\n2011 (kcal\n100 g)",
    "Energie, N x\nfacteur\nJones, avec\nfibres (kJ\n100 g)",
    "Energie, N x\nfacteur\nJones, avec\nfibres (kcal\n100 g)",
    "Eau\n(g\n100\ng)",
    "Protéines,\nN x\nfacteur de\nJones (g\n100 g)",
    "Protéines,\nN x 6.25\n(g\n100 g)",
    "Glucides\n(g\n100 g)",
    "Lipides\n(g\n100 g)",
    "Sucres\n(g\n100 g)",
    "Fructose\n(g\n100 g)",
    "Galactose\n(g\n100 g)",
    "Glucose\n(g\n100 g)",
    "Lactose\n(g\n100 g)",
    "Maltose\n(g\n100 g)",
    "Saccharose\n(g\n100 g)",
    "Amidon\n(g\n100 g)",
    "Fibres\nalimentaires\n(g\n100 g)",
    "Polyols\ntotaux\n(g\n100 g)",
    "Cendres\n(g\n100 g)",
    "Alcool\n(éthanol)\n(g\n100 g)",
    "Acides\norganiques\n(g\n100 g)",
    "AG\nsaturés\n(g\n100 g)",
    "AG\nmonoinsaturés\n(g\n100 g)",
    "AG\npolyinsaturés\n(g\n100 g)",
    "AG 4:0,\nbutyrique\n(g\n100 g)",
    "AG 6:0,\ncaproïque\n(g\n100 g)",
    "AG 8:0,\ncaprylique\n(g\n100 g)",
    "AG 10:0,\ncaprique\n(g\n100 g)",
    "AG\n12:0,\nlaurique\n(g\n100 g)",
    "AG 14:0,\nmyristique\n(g\n100 g)",
    "AG 16:0,\npalmitique\n(g\n100 g)",
    "AG 18:0,\nstéarique\n(g\n100 g)",
    "AG 18:1\n9c (n-9),\noléique\n(g\n100 g)",
    "AG 18:2\n9c,12c\n(n-6),\nlinoléique\n(g\n100 g)",
    "AG 18:3\nc9,c12,c15 (n-3),\nalpha-linolénique\n(g\n100 g)",
    "AG 20:4\n5c,8c,11c,14c\n(n-6),\narachidonique\n(g\n100 g)",
    "AG 20:5\n5c,8c,11c,14c,17c\n(n-3) EPA (g\n100 g)",
    "AG 22:6\n4c,7c,10c,13c,16c,19c\n(n-3) DHA (g\n100 g)",
    "Cholestérol\n(mg\n100 g)",
    "Sel\nchlorure\nde\nsodium\n(g\n100 g)",
    "Calcium\n(mg\n100 g)",
    "Chlorure\n(mg\n100 g)",
    "Cuivre\n(mg\n100 g)",
    "Fer (mg\n100 g)",
    "Iode\n(µg\n100 g)",
    "Magnésium\n(mg\n100 g)",
    "Manganèse\n(mg\n100 g)",
    "Phosphore\n(mg\n100 g)",
    "Potassium\n(mg\n100 g)",
    "Sélénium\n(µg\n100 g)",
    "Sodium\n(mg\n100 g)",
    "Zinc\n(mg\n100 g)",
    "Activité\nvitaminique\nA,\néquivalents\nrétinol (µg\n100 g)",
    "Rétinol\n(µg\n100 g)",
    "Beta-Carotène\n(µg\n100 g)",
    "Vitamine\nD (µg\n100 g)",
    "Vitamine D2\n(ergocalciférol)\n(µg\n100 g)",
    "Vitamine D3\n(cholécalciférol)\n(µg\n100 g)",
    "Alpha-tocophérol\n(vitamine E) (mg\n100 g)",
    "Vitamine\nE (mg\n100 g)",
    "Vitamine\nK1 (µg\n100 g)",
    "Vitamine\nK2 (µg\n100 g)",
    "Vitamine\nC (mg\n100 g)",
    "Vitamine\nB1 ou\nThiamine\n(mg\n100 g)",
    "Vitamine\nB2 ou\nRiboflavine\n(mg\n100 g)",
    "Vitamine\nB3 ou PP\nou\nNiacine\n(mg\n100 g)",
    "Vitamine B5\nou Acide\npantothénique\n(mg\n100 g)",
    "Vitamine\nB6 (mg\n100 g)",
    "Vitamine B9 ou\nFolates totaux,\néquivalents folates\nalimentaires, DFE (µg\n100 g)",
    "Vitamine\nB9 ou\nFolates\ntotaux (µg\n100 g)",
    "Folates\nintrinsèques\n(µg\n100 g)",
    "Acide folique\n(enrichissement)\n(µg\n100 g)",
    "Vitamine\nB12 (µg\n100 g)",
    "Facteur\nde\nJones",
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
        # Le intestazioni vere, copiate dal file del 2025 (`Table Ciqual 2025_FR_2025_11_03.xlsx`):
        # vanno a capo dove la scrittura su una riga mette uno spazio o una barra. Nell'unità
        # l'a capo prima di «100 g» è la barra; nel nome è uno spazio, anche dove su una riga
        # c'era una barra («1169/2011»): è `map_columns` a confrontare i nomi senza badare
        # alla differenza fra barra e spazio.
        ("Energie,\nRèglement\nUE N°\n1169\n2011 (kcal\n100 g)", ("energie, reglement ue n°1169 2011", "kcal")),
        ("Protéines,\nN x\nfacteur de\nJones (g\n100 g)", ("proteines, n x facteur de jones", "g")),
        ("Glucides\n(g\n100 g)", ("glucides", "g")),
        ("Lipides\n(g\n100 g)", ("lipides", "g")),
        ("Eau\n(g\n100\ng)", ("eau", "g")),
        ("Fer (mg\n100 g)", ("fer", "mg")),
        ("Iode\n(µg\n100 g)", ("iode", "ug")),
        ("Vitamine\nB9 ou\nFolates\ntotaux (µg\n100 g)", ("vitamine b9 ou folates totaux", "ug")),
        ("Alpha-tocophérol\n(vitamine E) (mg\n100 g)", ("alpha-tocopherol (vitamine e)", "mg")),
        ("AG 18:2\n9c,12c\n(n-6),\nlinoléique\n(g\n100 g)", ("ag 18:2 9c,12c (n-6), linoleique", "g")),
        # com'è nell'archivio, prima che il parser XML lo riduca a «\n»
        ("Lipides\r\n(g\r\n100 g)", ("lipides", "g")),
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


def test_map_columns_riconosce_le_intestazioni_vere_del_2025():
    """Il file vero va a capo dentro le intestazioni, dove una riga sola metterebbe uno
    spazio o una barra: le trenta colonne del vocabolario si trovano tutte lo stesso."""
    colonne = map_columns(INTESTAZIONE_2025)

    assert (colonne.code, colonne.name, colonne.group, colonne.subgroup) == (6, 7, 3, 4)
    assert colonne.absent == ()
    assert set(colonne.nutrients) == set(CIQUAL_NAMES)
    # l'energia in kcal, non quella in kJ accanto né quella «avec fibres»; le proteine
    # col fattore di Jones, non quelle N x 6.25
    assert {chiave: colonne.nutrients[chiave] for chiave in REQUIRED_KEYS} == {
        "kcal": 10, "protein": 14, "carbs": 16, "fat": 17,
    }
    assert colonne.nutrients["folate"] == 79 and colonne.nutrients["vitamin_e"] == 69
    # le colonne non usate si dicono su una riga, come le scrive chi le legge
    assert colonne.unused[0] == "Energie, Règlement UE N° 1169 2011 (kJ 100 g)"
    assert all("\n" not in colonna for colonna in colonne.unused)


def test_map_columns_rifiuta_un_unita_diversa_da_quella_del_vocabolario():
    """Il ferro in µg invece che in mg sarebbe mille volte sbagliato su ogni riga: il
    file si rifiuta intero, e il messaggio nomina la colonna."""
    sbagliata = [*INTESTAZIONE[:10], "Fer (µg/100 g)", INTESTAZIONE[11]]

    with pytest.raises(CiqualFormatError, match="Fer"):
        map_columns(sbagliata)


@pytest.mark.parametrize("kj_prima", [True, False])
def test_map_columns_l_energia_in_kj_accanto_a_quella_in_kcal_non_rifiuta_il_file(kj_prima):
    """Nel CIQUAL vero l'energia compare due volte con lo stesso nome, in kJ e in kcal: si
    usa la colonna nell'unità giusta e quella in kJ resta fra le non usate, qualunque
    sia l'ordine."""
    kj = "Energie, Règlement UE N° 1169/2011 (kJ/100 g)"
    kcal = INTESTAZIONE[5]
    coppia = [kj, kcal] if kj_prima else [kcal, kj]
    intestazione = [*INTESTAZIONE[:5], *coppia, *INTESTAZIONE[6:]]

    colonne = map_columns(intestazione)

    assert colonne.nutrients["kcal"] == intestazione.index(kcal)
    assert colonne.unused == (kj, "Eau (g/100 g)")
    assert "kcal" not in colonne.absent


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
