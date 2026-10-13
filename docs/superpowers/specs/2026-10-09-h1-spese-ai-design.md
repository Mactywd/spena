# H1, le spese dell'AI — design

_2026-10-09 (scritta il 2026-10-13). Voce `[H1]` di `docs/prossimi-passi.md` («## H1. Expense
Tracker»). Piano: `docs/superpowers/plans/2026-10-09-h1-spese-ai.md`._

## 1. Contesto

Da T2 (2026-09-17) ogni chiamata all'LLM lascia una riga in `llm_calls`: la sezione che l'ha
fatta (`call_site`, il valore di `LlmCallSite` in `backend/app/services/llm.py`), se è
riuscita (`ok`), il modello, i token e **il costo che OpenRouter dichiara nella risposta**
(`cost_usd`, `usage.cost`: non una stima). C'è già l'indice che serve a questa voce,
`ix_llm_calls_created_at_call_site` («in questo periodo, quanto per sezione»). Manca chi la
legge: oggi la spesa si vede solo sul sito di OpenRouter, tutta insieme, senza sapere quale
parte dell'app l'ha fatta. `python -m app.cli.llm_prices` stampa i prezzi di listino per
provider: è un'altra cosa e resta fuori.

Cosa registra `llm_calls`, verificato sul codice (2026-10-13):

- **Le chiamate fallite hanno sempre `cost_usd` NULL.** Ogni punto di chiamata, su
  `LlmUnavailable`, registra `LlmUsage()` vuota con `ok = false` (`ai_recipes.py`,
  `recipe_import/decide.py`, `unit_forms.py`): `complete_json` solleva prima di leggere il
  corpo, quindi il costo non c'è mai. Di una richiesta rifiutata non sappiamo se ci è stata
  addebitata (lo dice il modello `LlmCall`).
- **Una chiamata riuscita può avere `cost_usd` NULL** anche lei: `cost` è annullabile nella
  risposta stessa di OpenRouter.
- Le sezioni oggi su `master` sono `term_decision`, `term_collapse`, `recipe_draft`,
  `unit_forms`. Stanotte S12 aggiunge `ingredient_emoji` e R8 `recipe_variant`; la colonna è
  `String(40)`, e il database può contenere un valore che il codice in esercizio non conosce
  (un ramo nuovo, una sezione tolta).

## 2. Le decisioni di Mattia (2026-10-09)

1. **La schermata mostra sempre il totale del periodo, più la divisione per sezione e
   l'andamento per giorno** (costo giorno per giorno). Niente elenco delle chiamate, niente
   sezione dedicata alle fallite. Il costo delle fallite entra comunque nei totali se è costo
   reale.
2. **Periodi:** «Questo mese» di partenza, poi «Ultimi 30 giorni» e «Da sempre» (lo storico
   parte dal 2026-09-17). **I giorni si contano in Europe/Rome** come la scadenza
   (`PANTRY_TZ`), non in UTC.

E i vincoli dati con la voce: nessuna dipendenza nuova (i grafici sono SVG scritti a mano coi
token di colore, nei due temi, contrasto ≥ 3:1 per i segni e ≥ 4,5:1 per i testi, misurato da
`style.spec.ts`); il backend aggrega e il frontend mostra; i giorni senza chiamate valgono
zero; un periodo senza chiamate è una frase, non un grafico vuoto.

## 3. Le decisioni di Claude (su delega di Mattia)

3. **Le fallite nei totali: entrano quanto costano, cioè niente.** Il totale è la somma dei
   `cost_usd` dichiarati. Una fallita ha sempre il costo NULL (§1): sommarla come zero sarebbe
   affermare «gratis», e la regola di casa è che l'assenza resta assenza (come i nutrienti).
   Se un giorno un punto di chiamata registrasse il costo di una fallita, entrerebbe da sé:
   la somma non guarda `ok`. Le chiamate senza costo dichiarato (fallite o no) si **contano**,
   e lo si dice in una riga sotto il totale (decisa da Mattia il 2026-10-13, §6).
4. **La rotta:** `GET /api/v1/llm-spending?period=month|30d|all` (default `month`; un altro
   valore → 422), dietro la sessione come tutte. Risponde:
   ```json
   {
     "period": "30d", "first_day": "2026-09-14", "last_day": "2026-10-13",
     "total_usd": 0.025, "calls": 6, "unpriced_calls": 1,
     "sections": [{"call_site": "recipe_draft", "label": "Ricette scritte con l'AI",
                   "cost_usd": 0.02, "share": 0.8, "calls": 3}],
     "days": [{"day": "2026-09-14", "cost_usd": 0.0}]
   }
   ```
   - **Il periodo, in giorni di Roma.** «Oggi» è `today_in_pantry()`. `month`: dal primo del
     mese a oggi. `30d`: i 30 giorni che finiscono oggi, oggi compreso. `all`: dal giorno della
     prima chiamata registrata a oggi (in produzione il 2026-09-17; senza chiamate, oggi). Un
     giorno va da mezzanotte a mezzanotte a Roma (`day_start`), convertito in istanti per la
     query: un'ora legale che cambia non sposta niente.
   - **`sections`**: una per ogni `call_site` con almeno una chiamata nel periodo, anche se
     tutte senza costo. Ordinate dalla più cara (a parità, più chiamate, poi il nome). `share`
     è la quota del totale, 0–1 a quattro decimali (0 se il totale è 0). `label` è il nome a
     video, deciso dal server (§4); **una sezione sconosciuta torna col suo `call_site` grezzo
     come `label`** e non rompe niente.
   - **`days`**: ogni giorno del periodo, in ordine, quelli senza spesa a 0.
   - I costi arrotondati a 8 decimali (la somma di float non porta `0.30000000000000004` a
     video); restano in dollari, l'unità che OpenRouter dichiara.
5. **Il calcolo sta nel backend**: un modulo puro `backend/app/domain/spending.py` (periodi,
   inizio del giorno, serie con gli zeri, quota, nomi delle sezioni), tre letture in
   `backend/app/repositories/llm_calls.py` (per sezione, per giorno di Roma, primo giorno), un
   servizio `backend/app/services/spending.py`, la rotta in `backend/app/api/spending.py`.
   Nessuna migrazione: l'indice c'è già.
6. **Dove si apre: il ☰**, ultima voce dopo «Anagrafica», col percorso `/spese-ai`. È la
   «Spese» delle sezioni secondarie di D3/T1, che `AppHeader.tsx` annuncia in un commento.
7. **Il nome: «Spese dell'AI»**, nel ☰ e come titolo. Non «Spese» da solo: nel ☰ sta sotto
   «Sistema la spesa», e in un'app della spesa «Spese» si leggerebbe come lo scontrino.
8. **Il costo si scrive in dollari, all'italiana**: `Intl.NumberFormat("it-IT")` con il
   simbolo stretto, «0,025 $». Due decimali da 1 $ in su («1,50 $»); sotto 1 $ fino a quattro
   decimali, almeno due («0,0123 $», «0,50 $»), perché qui le cifre vere sono centesimi e
   frazioni di centesimo (una decisione di un termine costa ~0,0001 $); sotto 0,0001 $
   «< 0,0001 $»; zero «0,00 $». Niente conversione in euro: sarebbe un cambio inventato.
   La quota in percentuale intera («80%»), «< 1%» sotto l'uno per cento.
9. **La forma.** Il totale in grande (`text-4xl`), con sopra «Totale, dall'1 al 13 ottobre» e
   sotto il numero delle chiamate. **Per sezione:** una riga per sezione col nome, «0,02 $ ·
   80%» e una barra orizzontale lunga quanto la quota — un colore solo, `brand` su una traccia
   `brand-tint` (4,5:1 fra loro e sulla scheda, già in `theme.test.ts`): le sezioni si
   riconoscono dal nome scritto, non da sei tinte da imparare. **Per giorno:** colonne in SVG,
   una per giorno con una spesa, `brand`, alte in proporzione al giorno più caro (che è alto
   tutto); un giorno con una spesa minuscola resta visibile (2% dell'altezza); i giorni a zero
   non hanno colonna, sopra una linea di base `line`. Fino a 62 giorni ogni colonna ha uno
   spazio accanto; oltre (Da sempre, fra qualche mese) si toccano e fanno una sagoma, senza
   far scorrere niente di lato. Con meno di 14 giorni (i primi del mese) la colonna non si
   allarga oltre la misura che avrebbe con 14. Sopra il grafico «Il giorno più caro: 13
   ottobre, 0,021 $»; sotto, le date ai due capi («14 set», «13 ott»). Niente testo dentro
   l'SVG: i testi stanno in HTML e li misura lo scanner del contrasto.
10. **Niente tocco sulle colonne.** Trenta colonne su 375 px sono larghe 10 px: un tocco per
    giorno non arriva ai 44 px di casa. Il valore di ogni giorno arriva a chi non vede da una
    tabella `sr-only` dei giorni con una spesa, e il grafico è un'immagine col nome che lo
    riassume.
11. **Il periodo si sceglie con tre pulsanti** «Questo mese» / «Ultimi 30 giorni» / «Da
    sempre», a larghezza uguale, in un gruppo «Periodo», quello scelto `primary` con
    `aria-pressed`, gli altri `secondary`: la forma di «Tutto / Cibo / Casa» (S14). Non si
    ricorda: entrando si riparte da «Questo mese», come ha deciso Mattia.
12. **Vuoti e guasti.** Senza chiamate nel periodo: una frase in una scheda, nessun totale né
    grafico, e i pulsanti del periodo restano lì (si passa a «Da sempre»). Con chiamate ma
    nessun costo dichiarato (solo fallite): il totale «0,00 $», il numero delle chiamate e la
    riga di §3, nessun grafico (sarebbe vuoto). Il server che non risponde: `ErrorState` con
    «Riprova».
13. **I nomi delle sezioni** sono una tabella del backend (`CALL_SITE_LABELS`), con le sei
    sezioni, comprese le due che arrivano stanotte da S12 e R8: un test fallisce se un valore
    di `LlmCallSite` non ha il suo nome, così la settima sezione non arriva a video come
    `snake_case`.

## 4. Le parole a video

- Nel ☰ e titolo: **«Spese dell'AI»**. Sotto il titolo: «Quanto ha speso l'AI su OpenRouter,
  e per cosa.»
- Il gruppo «Periodo»: **«Questo mese»**, **«Ultimi 30 giorni»**, **«Da sempre»**.
- Caricando: «Carico le spese…». Guasto: «Non sono riuscito a leggere le spese.» con «Riprova».
- Vuoto: «Nessuna chiamata all'AI questo mese.» / «Nessuna chiamata all'AI negli ultimi 30
  giorni.» / «Nessuna chiamata all'AI, finora.»
- Totale: «Totale, {intervallo}», poi la cifra, poi «1 chiamata» / «42 chiamate».
  L'intervallo: «13 ottobre» (un giorno), «dall'1 al 13 ottobre», «dal 2 all'8 ottobre»,
  «dal 14 settembre al 13 ottobre», «dal 20 dicembre 2025 al 18 gennaio 2026» (l'anno solo se
  cambia); «dall'»/«all'» davanti a 1, 8, 11.
- Le chiamate senza costo: «1 senza un costo dichiarato da OpenRouter (di solito, una chiamata
  fallita): non è nel totale.» / «3 senza un costo dichiarato da OpenRouter (di solito,
  chiamate fallite): non sono nel totale.»
- I titoli: «Per sezione», «Per giorno». La riga di una sezione: «{nome}» e «{costo} ·
  {quota}». Sopra le colonne: «Il giorno più caro: {giorno}, {costo}». Il nome del grafico:
  «Costo per giorno, {intervallo}. Il giorno più caro: {giorno}, {costo}.» La tabella per chi
  non vede: «I giorni con una spesa».
- I nomi delle sezioni:

  | `call_site` | a video |
  |---|---|
  | `term_decision` | Abbinare gli ingredienti dell'import |
  | `term_collapse` | Unire i doppioni dell'import |
  | `unit_forms` | Forme delle unità |
  | `recipe_draft` | Ricette scritte con l'AI |
  | `recipe_variant` (R8) | Varianti con l'AI |
  | `ingredient_emoji` (S12) | Figure della dispensa |
  | qualunque altro | il valore com'è |

## 5. Fuori scope

- L'elenco delle chiamate e una vista delle fallite (decisione 1).
- I prezzi di listino (`app.cli.llm_prices`), la conversione in euro, un tetto di spesa che
  avvisa, il confronto col conto di OpenRouter (`/credits`).
- Un periodo scelto a mano (da… a…), il periodo ricordato fra una visita e l'altra.
- Il dettaglio di un giorno per sezione, e il tocco su una colonna (§3, 10).
- I token: sono nella tabella, ma la domanda di H1 è quanto si spende, non quanto si legge.

## 6. Domande aperte

Nessuna. **La riga delle chiamate senza costo** (§3, 3) è decisa da Mattia il 2026-10-13: si
tiene. Mattia ha escluso una *sezione* delle fallite; questa è una riga sotto il totale, e c'è
solo quando ce n'è almeno una. Senza, il totale sottostimerebbe in silenzio — «una torta che
sottostima è peggio di nessuna torta, perché la si crede» (`tests/test_llm_spend_is_recorded.py`).
