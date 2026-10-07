# S14 — «Tutto / Cibo / Casa» in dispensa (bozza di spec)

_Bozza del 2026-10-06, scritta in una fase giorno senza Mattia. Le decisioni marcate
**[da confermare]** hanno una raccomandazione; finché ce ne sono, la voce resta `tbd`._

Voce del backlog: «S14, "Tutto / Cibo / Casa" in dispensa: il server espone
`ingredient_kind` o filtra lui» [S14 in `docs/prossimi-passi.md`]. Va letta insieme a S15
(`2026-10-06-reparti-collassabili-bozza.md`), che tocca lo stesso schermo.

## 1. Il problema

Cibo e non alimentari (D4) stanno nella stessa dispensa, con gli stessi tre stati. Chi
guarda cosa può cucinare non vuole vedere il detersivo; chi controlla le cose di casa non
vuole scorrere trenta righe di cibo. Il modello ha già la distinzione:
`ingredients.kind` (`food` | `non_food`), derivato dal reparto da `kind_for_category`
(`backend/app/domain/rules.py`) e mai scritto a mano. Oggi `PantryItemOut` porta
`ingredient_category` ma non il `kind`.

Il frontend **non deve ricavarlo dal reparto**: sarebbe una seconda copia di
`kind_for_category`, che il giorno in cui un reparto cambia mondo resterebbe indietro (la
prima lezione di `CLAUDE.md`).

## 2. La scelta: il server espone `ingredient_kind`, o filtra lui

### 2.1 Le due strade

**A. `PantryItemOut` prende `ingredient_kind`.** Una riga in `_to_out`
(`backend/app/api/pantry.py`), un campo nel tipo `PantryItem`. Il client riceve tutta la
dispensa, come oggi, e filtra per quel campo.

**B. `GET /api/v1/pantry?kind=food|non_food`.** Il server filtra nella query di
`list_pantry`; il client chiede la dispensa di un mondo alla volta, con il `kind` nella
chiave della cache.

### 2.2 Confronto

| | A. Espone | B. Filtra |
|---|---|---|
| Logica nel client | Un confronto di uguaglianza su un dato del server: non è dominio | Nessuna |
| Cambio di scheda | Istantaneo, niente rete | Un giro in rete, e un «Carico…» o i dati vecchi per un attimo |
| Il riepilogo delle scadenze, la ricerca (S11), l'avviso dopo l'aggiunta | Lavorano sulle stesse voci, filtrate in un punto solo | Ognuno vede solo il mondo caricato; il riepilogo cambierebbe significato |
| Aggiungere una voce dell'altro mondo | La riga c'è nei dati: si passa a «Tutto» e la si porta in vista | La riga non c'è nella risposta: serve un secondo caricamento |
| Cache | Una chiave, `["pantry"]`, come oggi | Tre chiavi; le invalidazioni col prefisso le coprono, ma la Lista e la cottura leggono `["pantry"]` intera |
| Precedente | `ShoppingItemOut.ingredient_kind` c'è già, e «Sistema la spesa» lo usa (`kindOf` in `StockingScreen.tsx`) | Nessuno |
| Costo a dati grandi | La dispensa è di una persona: centinaia di righe, non migliaia | Uguale |

### 2.3 Raccomandazione: A

**Il server espone `ingredient_kind`.** Il client non deduce niente: legge un verdetto già
preso, come legge `expiry` invece di calcolare i sette giorni. È la stessa forma che la
Lista usa già. Filtrare nel server avrebbe senso solo se la dispensa fosse troppo grande
per arrivare intera, e non lo è. **Deciso da Mattia il 2026-10-07: A.**

## 3. Il selettore

```
┌───────────────────────────────────────┐
│ 🔍 Cerca o aggiungi               [+] │   ← ActionBar di oggi
├───────────────────────────────────────┤
│ [ Tutto ]  [ Cibo ]  [ Casa ]         │   ← tre pulsanti da 44 px
├───────────────────────────────────────┤
│ 📅 2 in scadenza questa settimana      │   ← il riepilogo di oggi, se c'è
```

- **Tre pulsanti in fila sotto la barra**, con `aria-pressed`, uno solo premuto. «Casa»
  vuol dire `non_food`: i reparti `casa` e `igiene`. A video «Casa», come nella voce.
  **Deciso da Mattia il 2026-10-07: «Casa».** È corto e ci sta; «Non alimentari» no.
- **Compare solo se servono entrambi**: se in dispensa (voci attive) c'è un mondo solo, il
  selettore non si mostra e vale «Tutto». Un selettore che può solo svuotare la pagina non
  serve. Se sparisce mentre era su «Casa» (l'ultima voce di casa tolta), torna a «Tutto»
  nello stesso disegno — come fa già il riepilogo delle scadenze col suo filtro, per la
  stessa ragione: una dispensa vuota per un filtro che non si vede più sarebbe una bugia.
- **Ricordato per dispositivo**, nella `sessionStorage` (chiave
  `spena.dispensa.mondo`), con un involucro che non lancia se lo spazio del sito è
  bloccato, come `recipeFilters.ts`. **Deciso da Mattia il 2026-10-07: `sessionStorage`.** La voce in `prossimi-passi.md`
  diceva `localStorage`; la raccomandazione qui è `sessionStorage` perché il 2026-09-29
  Mattia ha deciso così per i filtri del ricettario, con un argomento che vale anche qui —
  chiusa l'app, la dispensa riparte intera, invece di aprirsi su «Casa» per una scelta di
  tre giorni fa e sembrare senza cibo.

## 4. Come si combina col resto della Dispensa

L'ordine dei filtri è uno, ed è scritto in una funzione pura in `pantryView.ts`
(`inWorld(item, world)` più la composizione esistente):

1. **mondo** (S14) → 2. **ricerca** (S11, `matchesQuery`) → 3. **in scadenza**
   (`hasExpiry`, col riepilogo premuto) → raggruppamento per reparto (`groupForDisplay`).

- **Il riepilogo delle scadenze conta il mondo scelto.** Su «Cibo» dice quanti cibi
  scadono. Contare tutto e poi mostrare solo il cibo darebbe «2 in scadenza» col riepilogo
  premuto e zero righe sotto.
- **Ricerca vuota nel mondo scelto**: «Niente in Casa per «sale»» con **«Cerca in
  tutto»** (passa a «Tutto» e tiene il testo), prima dell'offerta di aggiungere. Il sale
  può essere in dispensa, sotto «Cibo»: offrire di aggiungerlo farebbe un doppione. È lo
  stesso caso già risolto per il riepilogo premuto («Niente in scadenza per «…»» con
  «Mostra tutto»).
- **Aggiungere una voce dell'altro mondo** (sono su «Casa» e aggiungo il latte): a
  aggiunta riuscita il selettore passa a «Tutto», come oggi la barra si svuota e il
  riepilogo si spegne, perché la riga nuova deve potersi vedere (`revealId`).
- **«Dispensa vuota»** resta il messaggio della dispensa davvero vuota: col selettore
  nascosto quando un mondo manca (§3), un mondo scelto non è mai vuoto.
- **S15**: il mondo non apre e non chiude i reparti; nasconde quelli senza voci di quel
  mondo, che spariscono interi (un reparto `casa` sotto «Cibo» non c'è, non è chiuso).

## 5. Cosa cambia nel codice (per il piano)

- Backend: `PantryItemOut.ingredient_kind: IngredientKind`; `_to_out` lo legge da
  `item.ingredient.kind`. Test: la rotta lo restituisce per un alimentare e per un non
  alimentare, letto dal modello e non ricalcolato.
- Frontend: `PantryItem.ingredient_kind: "food" | "non_food"`; un componente del
  selettore (`SegmentedControl` in `components/ui/` se il piano vede un secondo uso, se no
  dentro `features/pantry/`); la funzione del filtro con il suo test a tabella; l'involucro
  della `sessionStorage` col suo test (valore sconosciuto → «Tutto»).
- `e2e/style.spec.ts`: la Dispensa col selettore, nei due temi, a 375 px (il seme ha voci
  dei due mondi).
- Nessun colore nuovo: il pulsante premuto è quello di `aria-pressed` che l'app usa già
  (il riepilogo delle scadenze), coi token esistenti.

## 6. Decisioni per Mattia

1. **Il server espone `ingredient_kind`** (A) — raccomandato. **Deciso da Mattia il
   2026-10-07: A.**
2. **`sessionStorage` e non `localStorage`** — raccomandato, per coerenza col ricettario.
   **Deciso da Mattia il 2026-10-07: `sessionStorage`.**
3. **Il selettore nascosto quando la dispensa ha un mondo solo** — raccomandato. **Deciso
   da Mattia il 2026-10-07: nascosto.**
4. **Il nome «Casa»** — raccomandato. **Deciso da Mattia il 2026-10-07: «Casa».**
5. **Il riepilogo delle scadenze segue il mondo scelto** — raccomandato.

## 7. Fuori scope

- Lo stesso selettore in Lista e in Sistema la spesa (la Lista segue il giro del
  supermercato, dove i due mondi sono corsie come le altre).
- Un terzo mondo o mondi definiti dall'utente.
- Contatori dentro i pulsanti («Cibo 42»): a 375 px ci starebbero, ma ogni numero va
  tenuto vero con la ricerca accesa; si aggiunge se serve.
