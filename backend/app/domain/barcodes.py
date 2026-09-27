"""La cifra di controllo dei codici a barre, senza database e senza rete.

Un codice battuto a mano con una cifra sbagliata non è un prodotto ignoto: è un
errore di battitura, e trattarlo come «codice nuovo» apre la creazione di un
prodotto sotto un codice che nessuna confezione porta. La verifica non respinge
niente — i codici interni dei negozi e le etichette rovinate esistono, e chi ha la
confezione in mano ha l'ultima parola — dice solo se il codice torna.
"""

GTIN_LENGTHS = frozenset({8, 12, 13, 14})
_DIGITS = frozenset("0123456789")


def has_valid_check_digit(code: str) -> bool:
    """Vero se `code` è un GTIN-8/12/13/14 la cui ultima cifra torna.

    Pesi 3 e 1 alternati partendo dalla cifra accanto a quella di controllo,
    verso sinistra: la stessa regola vale per EAN-8, UPC-A, EAN-13 e GTIN-14,
    perché sono tutti lo stesso GTIN allineato a destra. Solo cifre ASCII:
    `str.isdigit` accetterebbe anche le cifre arabo-indiche, che nessuno scanner
    produce e nessun catalogo contiene.
    """
    if len(code) not in GTIN_LENGTHS or not set(code) <= _DIGITS:
        return False
    *body, check = (int(c) for c in code)
    weighted = sum(
        digit * (3 if position % 2 == 0 else 1)
        for position, digit in enumerate(reversed(body))
    )
    return (10 - weighted % 10) % 10 == check
