"""La misura dei suggerimenti: quante righe si vedono, e se il bersaglio c'è ancora.

Eseguire con `python -m app.cli.measure_suggestions` dentro il container del backend.
Legge e basta: la transazione è `READ ONLY` e finisce con un rollback, quindi si può
lanciare anche sulla produzione (con il via di Mattia: è una lettura della produzione).

Rifà, sull'anagrafica del database a cui è collegato, la misura della bozza
docs/superpowers/specs/2026-10-06-suggerimenti-soglia-bozza.md (§3.2), con lo stesso seme
del campionamento. Le prove nascono dall'anagrafica stessa:

- «digitazione»: per ogni ingrediente i prefissi di 3, 4, 5 e 6 lettere e il nome
  intero; per un campione di alias (fino a 150) i prefissi di 4 e 6 lettere e l'alias
  intero. Il bersaglio è l'ingrediente da cui la prova nasce;
- «due lettere»: il prefisso di due lettere di ogni nome, a parte, perché lì la
  somiglianza trigram non dice quasi niente;
- «refusi»: tre refusi sul nome intero (se ha almeno 5 lettere) e tre sui suoi primi
  sei caratteri — una lettera che manca, due vicine scambiate, una sostituita.

Ogni prova passa da `search_ingredients` (la lista di prima: lo stesso ordine e il
taglio a dieci di sempre) e da `suggest_ingredients` (quella che l'endpoint mostra
adesso). «Persi» sono le prove il cui bersaglio c'era prima e non c'è più: nella
famiglia «digitazione» devono essere zero; nei refusi a metà parola sono il prezzo
dichiarato del pavimento (§6 della bozza).
"""

import asyncio
import random
import statistics
import uuid
from dataclasses import dataclass, field

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.db.models.ingredient import Ingredient
from app.repositories.ingredients import search_ingredients, suggest_ingredients

SEED = 20261006
ALIAS_SAMPLE = 150
LIMIT = 10
TYPO_LETTERS = "abcdefghilmnoprstuvz"
MAX_LOST_SHOWN = 20
FAMILIES = ("digitazione", "due lettere", "refusi")


@dataclass(frozen=True)
class CatalogEntry:
    id: uuid.UUID
    name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class Probe:
    family: str
    text: str
    target: uuid.UUID


def typos(word: str, rng: random.Random) -> list[str]:
    """Tre refusi di `word`, sempre a una posizione interna (né la prima lettera né
    l'ultima): una lettera che manca, due vicine scambiate (saltato se sono uguali),
    una sostituita con un'altra lettera dell'alfabeto italiano."""
    if len(word) < 4:
        return []
    out = []
    i = rng.randrange(1, len(word) - 1)
    out.append(word[:i] + word[i + 1:])
    j = rng.randrange(1, len(word) - 2)
    if word[j] != word[j + 1]:
        out.append(word[:j] + word[j + 1] + word[j] + word[j + 2:])
    k = rng.randrange(1, len(word) - 1)
    replacement = rng.choice([letter for letter in TYPO_LETTERS if letter != word[k]])
    out.append(word[:k] + replacement + word[k + 1:])
    return out


def build_probes(catalog: list[CatalogEntry], rng: random.Random) -> list[Probe]:
    """Le prove, nell'ordine in cui il seme le rende ripetibili: prima i nomi, poi il
    campione di alias, poi i refusi. `catalog` va passato già ordinato per nome."""
    probes: list[Probe] = []
    for entry in catalog:
        name = entry.name
        for size in (3, 4, 5, 6):
            if len(name) > size:
                probes.append(Probe("digitazione", name[:size], entry.id))
        probes.append(Probe("digitazione", name, entry.id))
        if len(name) > 2:
            probes.append(Probe("due lettere", name[:2], entry.id))
    pairs = sorted((alias, entry.id) for entry in catalog for alias in entry.aliases)
    for alias, target in rng.sample(pairs, min(ALIAS_SAMPLE, len(pairs))):
        for size in (4, 6):
            if len(alias) > size:
                probes.append(Probe("digitazione", alias[:size], target))
        probes.append(Probe("digitazione", alias, target))
    for entry in catalog:
        if len(entry.name) >= 5:
            probes += [Probe("refusi", t, entry.id) for t in typos(entry.name, rng)]
        if len(entry.name) > 6:
            probes += [Probe("refusi", t, entry.id) for t in typos(entry.name[:6], rng)]
    return probes


@dataclass
class FamilyStats:
    probes: int = 0
    kept_before: int = 0
    kept_after: int = 0
    first_before: int = 0
    first_after: int = 0
    rows_before: list[int] = field(default_factory=list)
    rows_after: list[int] = field(default_factory=list)
    lost: list[str] = field(default_factory=list)

    def add(self, probe: Probe, before: list[uuid.UUID], after: list[uuid.UUID]) -> None:
        self.probes += 1
        self.kept_before += probe.target in before
        self.kept_after += probe.target in after
        self.first_before += bool(before) and before[0] == probe.target
        self.first_after += bool(after) and after[0] == probe.target
        self.rows_before.append(len(before))
        self.rows_after.append(len(after))
        if probe.target in before and probe.target not in after:
            self.lost.append(probe.text)


async def load_catalog(session: AsyncSession) -> list[CatalogEntry]:
    """Tutta l'anagrafica, ordinata per nome: l'ordine fa parte del seme."""
    ingredients = (await session.execute(select(Ingredient).order_by(Ingredient.name))).scalars()
    return [
        CatalogEntry(i.id, i.name, tuple(sorted(a.alias for a in i.aliases)))
        for i in ingredients
    ]


async def measure(session: AsyncSession, probes: list[Probe]) -> dict[str, FamilyStats]:
    stats: dict[str, FamilyStats] = {}
    for probe in probes:
        before = [i.id for i in await search_ingredients(session, probe.text, LIMIT)]
        after = [i.id for i in await suggest_ingredients(session, probe.text, LIMIT)]
        stats.setdefault(probe.family, FamilyStats()).add(probe, before, after)
    return stats


def _pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:.1f} %" if whole else "–"


def format_report(stats: dict[str, FamilyStats]) -> str:
    lines: list[str] = []
    for family in FAMILIES:
        s = stats.get(family)
        if s is None or s.probes == 0:
            continue
        lost = f"persi: {len(s.lost)}"
        if s.lost:
            lost += f" (i primi: {', '.join(repr(t) for t in s.lost[:MAX_LOST_SHOWN])})"
        lines += [
            f"{family}: {s.probes} prove",
            f"  bersaglio in lista: {_pct(s.kept_before, s.probes)} prima, {_pct(s.kept_after, s.probes)} dopo",
            f"  bersaglio primo:    {_pct(s.first_before, s.probes)} prima, {_pct(s.first_after, s.probes)} dopo",
            f"  righe, media:       {statistics.mean(s.rows_before):.2f} prima, {statistics.mean(s.rows_after):.2f} dopo",
            f"  righe, mediana:     {statistics.median(s.rows_before):g} prima, {statistics.median(s.rows_after):g} dopo",
            f"  liste da {LIMIT}:       {_pct(s.rows_before.count(LIMIT), s.probes)} prima, {_pct(s.rows_after.count(LIMIT), s.probes)} dopo",
            f"  liste vuote:        {_pct(s.rows_before.count(0), s.probes)} prima, {_pct(s.rows_after.count(0), s.probes)} dopo",
            f"  {lost}",
        ]
    return "\n".join(lines)


async def main() -> int:
    async with SessionLocal() as session:
        # la prima istruzione della transazione: da qui in poi Postgres rifiuta ogni
        # scrittura, qualunque cosa faccia il codice sotto
        await session.execute(text("SET TRANSACTION READ ONLY"))
        catalog = await load_catalog(session)
        if not catalog:
            print("L'anagrafica è vuota: niente da misurare. Semina prima (python -m app.cli.seed).")
            await session.rollback()
            return 0
        probes = build_probes(catalog, random.Random(SEED))
        stats = await measure(session, probes)
        await session.rollback()
    print(f"Anagrafica: {len(catalog)} ingredienti, {sum(len(e.aliases) for e in catalog)} alias.")
    print(format_report(stats))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
