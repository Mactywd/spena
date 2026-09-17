"""Chi chiama l'LLM ne registra la spesa. Una guardia, non una raccomandazione.

Il difetto che questo file esiste per impedire non è un errore di calcolo: è
un'omissione. Una sezione nuova che chiama `complete_json` e si dimentica di
registrare non rompe niente, non fa fallire niente, e non si vede da nessuna parte —
si vede solo mesi dopo, come una torta delle spese che sembra giusta e sottostima.
Una torta che sottostima è peggio di nessuna torta, perché la si crede.

È un controllo sul sorgente e non sul comportamento, e quindi è grossolano per
costruzione: prova che il richiamo c'è, non che sia corretto. Quello lo provano i test
per punto di chiamata. Questo copre il caso che quelli non possono coprire, cioè il
punto di chiamata che nessuno ha ancora scritto.

Sta in famiglia con `test_image_dependencies.py` e `test_compose.py`, che leggono
anche loro dei file invece di eseguire del codice.
"""

from pathlib import Path

APP = Path(__file__).resolve().parent.parent / "app"
DEFINIZIONE = APP / "services" / "llm.py"


def moduli_che_chiamano_llm() -> list[Path]:
    return [
        percorso
        for percorso in sorted(APP.rglob("*.py"))
        if percorso != DEFINIZIONE and "await complete_json(" in percorso.read_text()
    ]


def test_ci_sono_chiamanti_da_controllare():
    """Senza questo, la guardia sotto passerebbe su una lista vuota.

    È l'asserzione vacua classica: il giorno in cui un rinominamento cambia
    `complete_json` in altro, il controllo vero smetterebbe di controllare e
    resterebbe verde per sempre.
    """
    assert moduli_che_chiamano_llm(), (
        "nessun modulo chiama più `await complete_json(`: o la guardia non sa più "
        "cosa cercare, oppure il client è stato rinominato e va aggiornata qui"
    )


def test_ogni_chiamante_dellllm_registra_la_spesa():
    senza = [
        percorso.relative_to(APP.parent).as_posix()
        for percorso in moduli_che_chiamano_llm()
        if "record_llm_call" not in percorso.read_text()
    ]
    assert not senza, (
        f"{', '.join(senza)}: chiama l'LLM e non ne registra la spesa. Ogni chiamata "
        "costa, e una che non entra in `llm_calls` non comparirà mai nel conto per "
        "sezione — il conto sembrerà giusto e sarà più basso del vero."
    )
