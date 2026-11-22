"""I sostituti di un ingrediente (R5): il vocabolario e le regole pure.

Tre esiti per «Sostituisci», e sono tre cose diverse (docs/prossimi-passi.md, R5): uno o
più sostituti; «si può omettere»; «insostituibile». Si decidono per ingrediente e per
contesto — dolce o salato —, perché il burro nella besciamella non è il burro nei
biscotti; il contesto di una ricetta si ricava dalla sua categoria, senza AI.

Niente database qui: chi legge e chi scrive (`repositories/substitutions.py`,
`services/substitutions.py`) importa questi nomi. La regola che R6 userà per dire
«cucinabile con sostituti» è scritta nella spec R5 (§8), non qui: R5 non la costruisce.
"""

from enum import StrEnum


class SubstitutionContext(StrEnum):
    # in quest'ordine: è quello delle schede in Anagrafica, e la gran parte del
    # ricettario è salata
    SAVORY = "salato"
    SWEET = "dolce"


class SubstitutionVerdict(StrEnum):
    SUBSTITUTES = "substitutes"
    # soddisfa qualunque riga, anche principale (decisione 3 di Mattia, per R6)
    OMIT = "omit"
    IRREPLACEABLE = "irreplaceable"


class DecidedBy(StrEnum):
    """Chi ha scritto una risposta. Le stesse due parole di `import_terms.decided_by`."""

    AI = "ai"
    HUMAN = "human"


# Da uno a tre sostituti, dal migliore: più di tre in un pannello sotto una riga, al
# telefono, sono una lista da scorrere invece di una risposta
SUBSTITUTES_MAX = 3
# «metà dose», «sciolto in acqua»: poche parole. È anche la larghezza della colonna
SUBSTITUTE_NOTE_MAX = 60

# La prima parola della categoria di una ricetta dolce: «Dolci e Desserts», «Dolci»
SWEET_CATEGORY_WORD = "dolci"


def recipe_context(category: str | None) -> SubstitutionContext:
    """Dolce se la prima parola della categoria è «dolci», salato in ogni altro caso.

    La prima parola e non l'inizio della stringa: «Dolcificanti» non è un dolce. Senza
    categoria — le ricette scritte a mano, quelle del seme — è salato: è il caso più
    comune, e dove sbaglia c'è la correzione della singola ricetta.
    """
    words = (category or "").casefold().split()
    if words and words[0] == SWEET_CATEGORY_WORD:
        return SubstitutionContext.SWEET
    return SubstitutionContext.SAVORY


def clean_note(note: str | None) -> str | None:
    """La nota di un sostituto senza spazi di troppo; vuota non è una nota."""
    if note is None:
        return None
    cleaned = " ".join(note.split())
    return cleaned or None
