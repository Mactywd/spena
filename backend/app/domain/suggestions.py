"""Dove si taglia la lista dei suggerimenti. Modulo puro: nessun accesso al database.

Spec: docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md (§6, §10). La
misura dice che il punteggio non separa il giusto dal rumore — un prefisso lungo ha una
somiglianza trigram bassa per come è fatta `similarity`, e il rumore sta fra 0,17 e 0,30
come una parte dei bersagli — mentre «contiene il testo» sì. Per questo il taglio guarda
prima chi contiene il testo, e il punteggio solo quando nessuno lo contiene.
"""

from collections.abc import Sequence
from typing import Protocol, TypeVar

# Senza riscontri passano gli sfumati con best ≥ max(FUZZY_FLOOR, FUZZY_RELATIVE × il
# più simile). Il pavimento l'ha deciso Mattia il 2026-10-07 (decisione 1): senza, un
# ingrediente che non c'è mostrerebbe quasi sempre una o due righe sbagliate.
FUZZY_RELATIVE = 0.8
FUZZY_FLOOR = 0.30

# Quel che il riscontro non distingue: gli accenti (decisione 2) e i separatori di parola,
# che diventano spazi. `translate()` di Postgres riceve queste due stringhe com'è, e
# `fold_for_match` ne fa la tabella di Python: una copia sola, per i due lati del
# confronto. Devono restare lunghe uguali (`translate()` cancella un carattere senza
# corrispondente, in silenzio).
FOLD_FROM = "àáâäèéêëìíîïòóôöùúûüçñ'’-"
FOLD_TO = "aaaaeeeeiiiioooouuuucn   "

_FOLD_TABLE = str.maketrans(FOLD_FROM, FOLD_TO)


def fold_for_match(text: str) -> str:
    """Il testo cercato come lo confronta il riscontro: senza accenti, con apostrofi e
    trattini diventati spazi, e gli spazi ridotti a uno. Riceve testo già in minuscolo,
    come i nomi e gli alias dell'anagrafica."""
    return " ".join(text.translate(_FOLD_TABLE).split())


class Candidate(Protocol):
    @property
    def best(self) -> float: ...

    @property
    def is_hit(self) -> bool: ...


C = TypeVar("C", bound=Candidate)


def trim_suggestions(candidates: Sequence[C], limit: int) -> list[C]:
    """Le righe da mostrare, al massimo `limit`, nell'ordine in cui arrivano.

    1. Un riscontro (`is_hit`) è un candidato che contiene il testo all'inizio di una
       parola, nel nome o in un alias: lo calcola la query.
    2. Se c'è almeno un riscontro, passano solo i riscontri.
    3. Se non ce n'è nessuno, passano gli sfumati con best ≥ max(FUZZY_FLOOR,
       FUZZY_RELATIVE × il più simile): è il caso del refuso.
    4. Se non resta niente, la lista è vuota, e il chiamante mostra la sua via d'uscita.

    Non riordina mai: chi arriva primo ed è tenuto resta primo.
    """
    hits = [candidate for candidate in candidates if candidate.is_hit]
    if hits:
        return hits[:limit]
    if not candidates:
        return []
    threshold = max(FUZZY_FLOOR, FUZZY_RELATIVE * max(c.best for c in candidates))
    return [candidate for candidate in candidates if candidate.best >= threshold][:limit]
