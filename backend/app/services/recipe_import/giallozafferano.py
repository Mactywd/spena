"""Lettura di una pagina di ricetta di GialloZafferano.

Il parsing è puro: prende il testo della pagina e non sa da dove arriva. È quel che
permetterà al futuro «incolla un link» di riusarlo senza modifiche.

Perché non serve nessun modello linguistico: la pagina porta un blocco
schema.org/Recipe, e nel corpo tiene il nome dell'ingrediente e la quantità in due
elementi separati, con un indirizzo stabile per ogni ingrediente del loro catalogo.
Il nome non va estratto da una stringa: è un elemento.
"""

import re

# Un rimando fotografico è un numero isolato da spazi su entrambi i lati, prima
# della punteggiatura o a fine paragrafo. Lo spazio a sinistra **e** a destra è ciò
# che distingue «per 5 minuti 2 .» da «dividete l'impasto in 4.»: la seconda è
# prosa, e una regola più generosa la mangerebbe.
PHOTO_REFERENCES_BEFORE_PUNCTUATION = re.compile(r"(?:\s\d{1,2})+\s+(?=[.,;:])")
PHOTO_REFERENCES_AT_END = re.compile(r"(?:\s\d{1,2})+\s*$")


def strip_photo_references(text: str) -> str:
    """Via i rimandi alle fotografie, che qui non ci sono."""
    cleaned = text.replace("\xa0", " ")
    cleaned = PHOTO_REFERENCES_BEFORE_PUNCTUATION.sub("", cleaned)
    cleaned = PHOTO_REFERENCES_AT_END.sub("", cleaned)
    return cleaned.strip()


def normalize_steps(raw: object) -> list[str]:
    """`recipeInstructions` arriva in tre forme, e tutte e tre sono nei dati veri.

    Lista di paragrafi, lista di oggetti `HowToStep` con il testo dentro, o una
    stringa sola. Una forma non gestita non solleverebbe niente: produrrebbe una
    ricetta senza procedimento, che è peggio.
    """
    if raw is None:
        return []
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        steps: list[str] = []
        for entry in raw:
            if isinstance(entry, str):
                steps.append(entry)
            elif isinstance(entry, dict) and isinstance(entry.get("text"), str):
                steps.append(entry["text"])
        return steps
    return []


def clean_instructions(raw: object) -> str:
    """I passaggi ripuliti, uniti da una riga vuota."""
    steps = [strip_photo_references(step) for step in normalize_steps(raw)]
    return "\n\n".join(step for step in steps if step)
