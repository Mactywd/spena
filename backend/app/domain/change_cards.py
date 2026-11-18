"""Le regole pure della scheda dei cambi (piano 6c, decisioni 18 e 19). Senza database."""

STATUS_RANK = {"available": 0, "low": 1, "finished": 2}


def most_consumed(a: str, b: str) -> str:
    """Il più consumato dei due stati (`finished` su `low` su `available`): se Claude
    nomina due volte la stessa voce di dispensa, per due pasti, la riga è una e vince
    questo (decisione 18)."""
    return a if STATUS_RANK[a] >= STATUS_RANK[b] else b


def adds_to_list(to_status: str) -> bool:
    """Solo una voce che diventa `finished` porta con sé la riga «in lista». Una `low`
    no: è la regola del sugo avviato fatta struttura, non solo prompt (decisione 19)."""
    return to_status == "finished"
