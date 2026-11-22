"""Un piccolo XLSX nella forma della tabella CIQUAL, costruito al volo (S4, fetta 1).

I VALORI SONO INVENTATI, per le prove: non sono quelli di CIQUAL, e i codici (900xx) non
esistono nella tabella vera. Questo file serve le prove del lettore e del caricamento. La
tabella vera, `data/ciqual/ciqual-2025.xlsx` del repository, la leggono dal 2026-11-21 le
prove che devono vedere i nomi veri: l'ordine dei candidati (`tabella_vera` di
`tests/ciqual_veri.py`) e le espressioni del pilota (`tests/services/test_s4_pilot.py`).

Si usa in due modi: dai test (`from ciqual_fixture import …`, come `llm_fakes`: pytest
mette `tests/` in `sys.path`), e come script nello stack e2e:

    python tests/ciqual_fixture.py /tmp/ciqual-e2e.xlsx

Il foglio si scrive come lo scrive Excel: le stringhe nella tabella condivisa
(`sharedStrings.xml`) e citate per numero, i numeri nella cella, le celle vuote non
scritte affatto. È questo che il lettore deve saper ricostruire.
"""

import sys
import zipfile
from pathlib import Path
from xml.sax.saxutils import escape

MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
DOC_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
PKG_REL = "http://schemas.openxmlformats.org/package/2006/relationships"

# Le intestazioni sono scritte come nel file vero del 2025, a capo compreso: «\r\n» dove
# una riga sola metterebbe uno spazio o una barra («(kcal\r\n100 g)» per «(kcal/100 g)»).
# Il lettore che passa questa prova è quello che legge il file di Mattia.
HEADER = [
    "alim_grp_code",
    "alim_grp_nom_fr",
    "alim_ssgrp_nom_fr",
    "alim_code",
    "alim_nom_fr",
    "Energie,\r\nRèglement\r\nUE N°\r\n1169\r\n2011 (kcal\r\n100 g)",
    "Eau\r\n(g\r\n100\r\ng)",
    "Protéines,\r\nN x\r\nfacteur de\r\nJones (g\r\n100 g)",
    "Glucides\r\n(g\r\n100 g)",
    "Lipides\r\n(g\r\n100 g)",
    "Sucres\r\n(g\r\n100 g)",
    "AG\r\nsaturés\r\n(g\r\n100 g)",
    "Fibres\r\nalimentaires\r\n(g\r\n100 g)",
    "Sel\r\nchlorure\r\nde\r\nsodium\r\n(g\r\n100 g)",
    "Fer (mg\r\n100 g)",
    "Vitamine\r\nC (mg\r\n100 g)",
    "Iode\r\n(µg\r\n100 g)",
]

_VEG = "fruits, légumes, légumineuses et oléagineux"
_CER = "produits céréaliers"
_FAT = "matières grasses"
_MILK = "lait et produits laitiers"

# gruppo, sottogruppo, codice, nome, kcal, acqua, proteine, glucidi, lipidi, zuccheri,
# saturi, fibre, sale, ferro, vitamina C, iodio. Un numero Python diventa una cella
# numerica (le proteine del pomodoro); `None` una cella non scritta (la vitamina C del
# basilico); «n.d.» un valore illeggibile (il ferro della cipolla).
FOODS: list[list[object]] = [
    ["02", _VEG, "légumes", "90001", "Tomate, crue", "18", 94.5, 0.86, "2,5", "0,3", "2,4", "0,05", "1,2", "0,01", "0,3", "14", "traces"],
    ["02", _VEG, "légumes", "90002", "Tomate, concentré", "77", "74", "4,3", "12", "0,5", "11", "0,1", "4,1", "0,2", "3", "22", "-"],
    ["03", _CER, "pâtes, riz et céréales", "90003", "Pâtes sèches, crues", "357", "10", "12,5", "70,9", "1,6", "3,1", "0,4", "3,7", "< 0,02", "1,4", "-", "< 5"],
    ["03", _CER, "pâtes, riz et céréales", "90004", "Pâtes sèches, cuites", "157", "61", "5,4", "30,6", "0,9", "0,6", "0,2", "1,8", "0,01", "0,5", "-", "-"],
    ["02", _VEG, "légumes", "90005", "Ail, cru", "131", "64", "5,8", "21,2", "0,4", "1,4", "0,1", "4,7", "0,04", "1,1", "18", "2"],
    ["04", _FAT, "huiles et graisses végétales", "90006", "Huile d'olive vierge extra", "900", "0", "0", "0", "100", "0", "15,4", "-", "traces", "0,2", "-", "-"],
    ["02", _VEG, "herbes", "90007", "Basilic, frais", "31", "92", "3,2", "1,8", "0,6", "0,3", "0,04", "1,6", "0,01", "3,2", None, "1"],
    ["05", _MILK, "beurres", "90008", "Beurre doux", "745", "16", "0,7", "0,8", "82", "0,8", "54", "0", "0,03", "0,02", "0", "3"],
    ["06", "viandes, œufs, poissons", "œufs", "90009", "Oeuf, cru", "140", "76", "12,7", "0,3", "9,8", "0,3", "2,7", "0", "0,35", "1,9", "0", "48"],
    ["05", _MILK, "fromages", "90010", "Parmesan", "392", "29", "33", "0", "28", "0", "18", "0", "1,6", "0,8", "0", "30"],
    ["03", _CER, "pâtes, riz et céréales", "90011", "Riz blanc, cru", "354", "12", "7,4", "78", "0,7", "0,2", "0,2", "1,4", "0,01", "0,8", "0", "< 2"],
    ["02", _VEG, "légumes", "90012", "Oignon, cru", "37", "89", "1", "6,8", "0,2", "5", "0,03", "1,8", "0,01", "n.d.", "6", "1"],
    ["05", _MILK, "laits", "90013", "Lait entier, pasteurisé", "65", "88", "3,3", "4,8", "3,6", "4,8", "2,3", "0", "0,1", "0,03", "1", "13"],
    ["03", _CER, "farines", "90014", "Farine de blé tendre ou froment T55", "343", "13", "10", "72", "1,2", "1,5", "0,2", "3,1", "0,01", "1,1", "0", "-"],
    ["07", "produits sucrés", "sucres", "90015", "Sucre blanc", "400", "0", "0", "100", "0", "100", "0", "0", "0", "0,1", "0", "-"],
    ["08", "aides culinaires", "sels", "90016", "Sel blanc alimentaire, iodé", "0", "0", "0", "0", "0", "0", "0", "0", "99,8", "0,1", "0", "1500"],
]


def _letters(index: int) -> str:
    """0 → A, 25 → Z, 26 → AA: il riferimento di colonna di un foglio."""
    letters = ""
    index += 1
    while index:
        index, rest = divmod(index - 1, 26)
        letters = chr(ord("A") + rest) + letters
    return letters


def write_xlsx(path: Path | str, rows: list[list[object]]) -> None:
    strings: list[str] = []
    positions: dict[str, int] = {}

    def shared(text: str) -> int:
        if text not in positions:
            positions[text] = len(strings)
            strings.append(text)
        return positions[text]

    sheet_rows = []
    for number, row in enumerate(rows, start=1):
        cells = []
        for column, value in enumerate(row):
            if value is None:
                continue  # una cella vuota non si scrive, come fa Excel
            reference = f"{_letters(column)}{number}"
            if isinstance(value, (int, float)):
                cells.append(f'<c r="{reference}"><v>{value}</v></c>')
            else:
                cells.append(f'<c r="{reference}" t="s"><v>{shared(str(value))}</v></c>')
        sheet_rows.append(f'<row r="{number}">{"".join(cells)}</row>')

    head = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            f'{head}<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
            '<Default Extension="xml" ContentType="application/xml"/></Types>',
        )
        archive.writestr(
            "xl/workbook.xml",
            f'{head}<workbook xmlns="{MAIN}" xmlns:r="{DOC_REL}"><sheets>'
            '<sheet name="Ciqual" sheetId="1" r:id="rId1"/></sheets></workbook>',
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            f'{head}<Relationships xmlns="{PKG_REL}"><Relationship Id="rId1" '
            f'Type="{DOC_REL}/worksheet" Target="worksheets/sheet1.xml"/></Relationships>',
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f'{head}<worksheet xmlns="{MAIN}"><sheetData>{"".join(sheet_rows)}</sheetData></worksheet>',
        )
        archive.writestr(
            "xl/sharedStrings.xml",
            f'{head}<sst xmlns="{MAIN}" count="{len(strings)}" uniqueCount="{len(strings)}">'
            + "".join(f"<si><t>{escape(text)}</t></si>" for text in strings)
            + "</sst>",
        )


def fixture_xlsx(directory: Path, rows: list[list[object]] | None = None) -> Path:
    """L'estratto (o le righe date) scritto in `directory`, e il suo percorso."""
    path = directory / "ciqual-prova.xlsx"
    write_xlsx(path, rows if rows is not None else [HEADER, *FOODS])
    return path


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("uso: python tests/ciqual_fixture.py <percorso.xlsx>")
        sys.exit(2)
    write_xlsx(sys.argv[1], [HEADER, *FOODS])
    print(f"estratto di prova di CIQUAL scritto in {sys.argv[1]}: {len(FOODS)} alimenti inventati")
