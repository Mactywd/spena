import pytest

from app.domain.barcodes import has_valid_check_digit


@pytest.mark.parametrize(
    "code,expected",
    [
        # GTIN-13 (EAN-13)
        ("8001120000002", True),
        ("8001120000000", False),
        # il codice delle fixture di Open Food Facts: inventato, e infatti non torna
        ("5201054000138", False),
        ("5201054000137", True),
        ("4006381333931", True),
        # la stessa cifra sbagliata di uno: il caso che la verifica esiste per prendere
        ("4006381333932", False),
        # due cifre scambiate fra posizioni di peso diverso
        ("4006381339331", False),
        # GTIN-8 (EAN-8)
        ("96385074", True),
        ("96385075", False),
        # GTIN-12 (UPC-A)
        ("036000291452", True),
        ("036000291453", False),
        # GTIN-14
        ("10012345678902", True),
        ("10012345678903", False),
        # codice interno di negozio (prefisso 2): anche lui ha la sua cifra di controllo
        ("2000000000015", True),
        ("2000000000008", True),
        # quello del giro di T3 in prossimi-passi.md (S20)
        ("2000000000017", False),
        # tutti zeri: la somma è 0 e la cifra è 0, valido per costruzione
        ("0000000000000", True),
        # lunghezze che nessun GTIN ha
        ("1234", False),
        ("1", False),
        ("123456789", False),
        ("123456789012345", False),
        ("", False),
        # non cifre: un codice con spazi o lettere non è un GTIN
        ("5201054 00138", False),
        ("520105400013A", False),
        (" 5201054000138", False),
        # cifre non ASCII: `str.isdigit` le accetterebbe
        ("٥٢٠١٠٥٤٠٠٠١٣٨", False),
    ],
)
def test_check_digit_over_every_gtin_length(code, expected):
    assert has_valid_check_digit(code) is expected
