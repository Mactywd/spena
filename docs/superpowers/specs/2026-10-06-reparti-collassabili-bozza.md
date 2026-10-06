# S15 — Reparti della dispensa collassabili (bozza di spec)

_Bozza del 2026-10-06, scritta in una fase giorno senza Mattia. Le decisioni marcate
**[da confermare]** hanno una raccomandazione; finché ce ne sono, la voce resta `tbd`._

Voce del backlog: «S15, reparti della dispensa collassabili, col numero di voci quando
sono chiusi e aperti da una ricerca» [S15 in `docs/prossimi-passi.md`]. Va letta insieme a
S14 (`2026-10-06-cibo-casa-bozza.md`).

## 1. Il problema

La Dispensa raggruppa per reparto (`groupForDisplay` in `pantryView.ts`), ogni gruppo in
una `Section` con l'icona, il nome e il numero di voci (`Section.tsx`). Con una dispensa
vera si scorre molto per arrivare a un reparto. I titoli diventano apribili e chiudibili,
così la dispensa si naviga per reparto.

Due cose da non sbagliare, già scritte nella voce: **una ricerca apre i reparti che hanno
un risultato**, e **un reparto chiuso dice quante voci contiene**, altrimenti chiuso
sembra vuoto.

## 2. Il titolo che apre e chiude

```
┌───────────────────────────────────────┐
│ [🧀] Latticini              5    ⌄    │   ← aperto: le righe sotto, come oggi
│   Mozzarella   ▬ ▬ ▬  ✕                │
│   …                                   │
└───────────────────────────────────────┘
┌───────────────────────────────────────┐
│ [🥕] Verdura       7 · 1 finito   ›   │   ← chiuso: numero, e quel che chiede attenzione
└───────────────────────────────────────┘
```

- **Tutto il titolo è il pulsante**: icona, nome, numero e chevron, alto almeno 44 px. Il
  `<h2>` resta (la struttura delle sezioni la leggono gli screen reader) e contiene il
  `<button aria-expanded aria-controls>`: è lo schema ARIA dell'accordion. Il contenuto
  chiuso ha `hidden`, quindi le sue tacche e le sue ✕ escono anche dall'ordine del Tab.
- **Chevron** `chevron-down` aperto, `chevron-right` chiuso, in `ink-faint`. Nessuna
  animazione: a 375 px un'altezza che si apre sposta il resto sotto il dito.
- **Il numero c'è già** (`count`) e resta lo stesso aperto e chiuso.
- **Chiuso, il titolo dice anche quel che chiede attenzione** **[da confermare]**: le voci
  finite («1 finito», in `finished`) e quelle in scadenza («2 in scadenza», in `expiry`),
  solo quando ci sono. Raccomandato: un reparto chiuso non deve nascondere proprio le
  righe che hanno un pulsante da toccare («In lista» su una finita) o un tempo che corre.
  Il testo è corto e in parole, non un pallino: un colore solo non dice niente a chi non lo
  distingue. Se a 375 px non ci sta accanto al nome, va a capo sotto il nome, piccolo.

## 3. Cosa apre un reparto chiuso

Lo stato **salvato** (quel che l'utente ha chiuso) e lo stato **a video** sono due cose:

| Situazione | Cosa si vede | Cosa si salva |
|---|---|---|
| Nessun filtro | lo stato salvato | — |
| Ricerca scritta (S11) | **aperti tutti i reparti con un risultato**; quelli senza non ci sono già oggi | niente: lo stato salvato resta com'era |
| Riepilogo delle scadenze premuto | aperti i reparti con una voce in scadenza | niente |
| Mondo scelto (S14) | lo stato salvato, sui reparti di quel mondo | — |
| Voce appena aggiunta (`revealId`) in un reparto chiuso | il suo reparto si apre e la riga si porta in vista | **sì, si salva aperto**: l'utente ha appena messo lì qualcosa |
| Toccare il titolo durante una ricerca | chiude o apre per davvero | sì |

Cancellata la ricerca o spento il riepilogo, la dispensa torna allo stato salvato. La regola
è: **un filtro mostra quel che ha trovato, e non cambia quel che l'utente aveva deciso**.
Ricerca e riepilogo sono filtri; il mondo (S14) è una vista, e una vista non apre niente.

## 4. Dove si ricorda

**`localStorage`**, chiave `spena.dispensa.reparti-chiusi`, l'elenco dei reparti chiusi
(non degli aperti: un reparto nuovo nasce aperto, e chi non ha mai chiuso niente vede la
dispensa di oggi). Con lo stesso involucro di `recipeFilters.ts`: se lo spazio del sito è
bloccato o il valore è illeggibile, tutto aperto; un nome di reparto che non esiste più si
ignora.

`localStorage` e non `sessionStorage`, a differenza di S14 **[da confermare]**: chiudere
«Spezie» perché non si guardano mai è una disposizione della propria dispensa, come
l'ordine delle cartelle, e ritrovarla domani è il punto. E non nasconde niente in
silenzio, perché il titolo chiuso dice quante voci ha e quali chiedono attenzione (§2).

## 5. Cosa cambia nel codice (per il piano)

- `Section` prende due props facoltative, `collapsed` e `onToggle`: senza, è la sezione di
  oggi. La usano anche Lista, Sistema la spesa e altri schermi, e lì non cambia niente.
  Il testo «1 finito · 2 in scadenza» lo passa la Dispensa (una prop `closedNote`), perché
  `Section` non sa cosa sia una voce di dispensa.
- In `pantryView.ts` una funzione pura che, dati i gruppi, i reparti chiusi salvati e i
  filtri accesi, dice quali reparti sono aperti a video; test a tabella sulle righe della
  tabella di §3.
- L'involucro dello spazio locale col suo test.
- `PantryScreen`: il `revealId` apre il reparto prima di portare la riga in vista;
  `revealAtTop` deve trovare la riga montata (oggi la trova sempre, chiuso non c'è).
- `e2e/style.spec.ts`: un reparto chiuso a 375 px nei due temi (titolo con «1 finito» e
  «in scadenza», i colori sopra 4,5:1 su `card` come oggi), e la ricerca che apre un reparto
  chiuso. I due colori sono già testo su `card` oggi (il «Finito» delle righe e la
  scadenza in `PantryRow`), quindi `style.spec.ts` li misura già: nessun token nuovo.

## 6. Decisioni per Mattia

1. **Chiuso, il titolo dice «N finito» e «N in scadenza»** oltre al numero — raccomandato.
2. **`localStorage`** per i reparti chiusi (diverso da S14) — raccomandato.
3. **Il riepilogo delle scadenze premuto apre i reparti con una scadenza**, come la
   ricerca — raccomandato.
4. **Una voce aggiunta in un reparto chiuso lo apre e lo salva aperto** — raccomandato.
5. **Niente «chiudi tutto / apri tutto»** per ora: con una ventina di reparti al massimo
   (14 oggi), toccarli uno per uno basta. Si aggiunge se sul telefono manca.

## 7. Fuori scope

- Reparti collassabili in Lista e in Sistema la spesa (la Lista si scorre camminando, e
  un reparto chiuso in corsia è una cosa dimenticata).
- Riordinare i reparti a mano.
- Animazioni di apertura.
