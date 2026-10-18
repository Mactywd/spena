# Next steps

_Ultimo aggiornamento: 2026-10-14 (fase giorno: altri nove piani `pronto`, dal 12 al 20 — uno in coda alla catena, uno dal ramo del piano prima, sette da `master`; le domande rimaste decise da Mattia)_

Questo è il backlog, ed è l'unico: cosa c'è da fare e in che stato. Il ragionamento dietro
ogni voce (decisioni, misure, perché) resta in `docs/prossimi-passi.md`, sotto il codice
indicato fra parentesi quadre, ad esempio [S3] o [Parte X]. I piani stanno in
`docs/superpowers/plans/`, i report notturni in `docs/night-reports/`.

Stati: `idea` → `tbd` → `pronto` → `in corso` → `fatto`, oppure `bloccato` con il motivo.
Una voce `tbd` con «serve il piano» è già decisa nella spec: manca solo il piano.

Il repo è pubblico: qui non vanno dati di produzione.

## Pronti per la notte

Una catena e dei rami a sé, da eseguire in quest'ordine (decisa nelle fasi giorno del
2026-10-09 e del 2026-10-13). I piani 2, 3, 5, 6 e 7 partono ciascuno dal ramo del piano prima,
il 10 da quello del 7, il 13 da quello del 10; se un anello manca, quelli dopo si fermano nella
loro Preparazione. Il 18 parte dal ramo del 17. Il 4, l'8, il 9, l'11, il 12, il 14, il 15, il
16, il 17, il 19 e il 20 partono da `master`. La migrazione `0013` di S12 si eredita lungo la
catena (R8 aggiunge la `0014` sopra): per questo i piani dopo S12 fanno girare pytest su un
database dei test loro (`spena_test_<slug>`), e `spena_test` resta per chi parte da `master`
finché è alla `0012`. Il 16, il 17, il 18 e il 19 aggiungono migrazioni con un numero riservato
(`0015`, `0016`, `0017` sopra la `0016`, `0018`) e partono dalla `0012`: al merge Mattia ripunta
la `down_revision` sulla testa di `master` di quel momento, e `alembic heads` deve dire una testa
sola. Ogni piano ha la sua sezione «Al merge» e «Dopo il deploy».

1. [pronto] P2 · S3, ingresso diretto in dispensa, veloce: «Scansiona» in serie con la scheda di conferma, il + che crea l'ingrediente, «Articolo aggiuntivo» e «+ un'altra confezione» in Sistema la spesa; le tre scelte A, B, C decise da Mattia il 2026-10-09 [S3] → `docs/superpowers/plans/2026-10-08-s3-ingresso-diretto.md`, ramo `night/s3-ingresso-diretto` da `master`
2. [pronto] P2 · S12, righe della dispensa riconoscibili: emoji dell'ingrediente (elenco chiuso, 148, fino a Emoji 14.0) col ripiego sull'icona del reparto, «Cambia figura» in Anagrafica, migrazione `0013` e `decide_emoji` (da lanciare in produzione solo da Mattia dopo il deploy) [S12] → `docs/superpowers/plans/2026-10-08-s12-righe-dispensa.md`, ramo `night/s12-righe-dispensa` da `night/s3-ingresso-diretto`
3. [pronto] P3 · Tema scuro: il pulsante primario spento diventa un verde torbido; il velo del ☰ scurisce poco — grigio pieno coi token `disabled` / `on-disabled`, velo 45% / 60% col bordo `panel-edge` [T3 Consegna 1] → `docs/superpowers/plans/2026-10-08-tema-scuro-spenti.md`, ramo `night/tema-scuro-spenti` da `night/s12-righe-dispensa`
4. [pronto] P3 · I suggerimenti degli ingredienti sono sempre dieci righe, anche quando non somigliano più — criterio B col pavimento a 0,30, l'inizio di parola anche negli alias, `%` e `_` non più jolly, la nota di ripiego in `IngredientPicker` [T3, esito del giro] → `docs/superpowers/plans/2026-10-08-suggerimenti-soglia.md`, ramo `night/suggerimenti-soglia` da `master`
5. [pronto] P3 · S14, «Tutto / Cibo / Casa» in dispensa: `ingredient_kind` dal server, scelta in `sessionStorage`, una voce aggiunta dello stesso mondo lascia il mondo com'è (Mattia, 2026-10-09) [S14] → `docs/superpowers/plans/2026-10-08-s14-cibo-casa.md`, ramo `night/s14-cibo-casa` da `night/tema-scuro-spenti`
6. [pronto] P3 · S15, reparti della dispensa collassabili, col numero e «N finiti» / «N in scadenza» da chiusi, in `localStorage`; le tre scelte su ricerca, scadenze e reparto che torna decise da Mattia il 2026-10-09 [S15] → `docs/superpowers/plans/2026-10-08-s15-reparti-collassabili.md`, ramo `night/s15-reparti-collassabili` da `night/s14-cibo-casa`
7. [pronto] P3 · «Rimetti in lista» anche per «quasi finito», ovunque: in Dispensa la riga gialla ha «In lista» come la rossa (`RestockLine.tsx`), nel foglio della cottura la casella c'è anche su una confezione già gialla e invariata, vuota; il titolo chiuso dei reparti di S15 resta «N finito» (Mattia, 2026-10-09 e 2026-10-13) [Parte X] → `docs/superpowers/plans/2026-10-09-rimetti-in-lista.md`, ramo `night/rimetti-in-lista` da `night/s15-reparti-collassabili`
8. [pronto] P3 · R2, secondo modo: riporzionare a partire da un ingrediente, solo vista — tocco sulla dose, «Quanto ne fai?» con l'unità accanto, lo stepper dice «≈ 1,5», la cottura registra la dose nello `snapshot`, senza migrazione (Mattia, 2026-10-09 e 2026-10-13) [R2] → `docs/superpowers/plans/2026-10-09-r2-riporziona-ingrediente.md`, ramo `night/r2-riporziona-ingrediente` da `master`
9. [pronto] P3 · Le pagine `SKIPPED` dell'import a video e rimesse in coda: sezione «Scartate (N)» nella coda, col perché e la strada per ogni pagina, «Rimetti in coda» che materializza subito; le illeggibili con «Apri la pagina» e senza rimessa (Mattia, 2026-10-09 e 2026-10-13) [Parte X] → `docs/superpowers/plans/2026-10-09-scartate-in-coda.md`, ramo `night/scartate-in-coda` da `master`
10. [pronto] P3 · R8, modifica con AI che salva una ricetta nuova: il modulo già compilato dalla proposta, il legame «Variante di «…»» che si vede (`recipes.derived_from_id`, migrazione `0014`), foto e tempi copiati dall'originale (Mattia, 2026-10-09 e 2026-10-13) [R8] → `docs/superpowers/plans/2026-10-09-r8-modifica-con-ai.md`, ramo `night/r8-modifica-con-ai` da `night/rimetti-in-lista`
11. [pronto] P3 · H1, Expense Tracker su `llm_calls`: «Spese dell'AI» dal ☰, il totale del periodo con la divisione per sezione e l'andamento per giorno di Roma, «Questo mese» / «Ultimi 30 giorni» / «Da sempre», grafici SVG senza dipendenze, una riga per le chiamate senza costo (Mattia, 2026-10-09 e 2026-10-13) [H1] → `docs/superpowers/plans/2026-10-09-h1-spese-ai.md`, ramo `night/h1-spese-ai` da `master`
12. [pronto] P3 · Dosi dell'import con l'aggettivo davanti o coi numeri del nome («fredda ⏎ 330 ⏎ g», «36 mesi ⏎ 50 ⏎ g»): le parole vanno nella nota della riga e la dose torna a riscalarsi; il parser legge ½ ¼ ¾ e «50 g + q.b.»; l'import pulisce all'ingresso; `clean_doses` pulisce le righe che ci sono, anche delle ricette adottate, e toglie da `units` le parole che unità non sono, decise guardando il `--dry-run` (da lanciare in produzione solo da Mattia dopo il deploy); la nota si vede nel dettaglio (Mattia, 2026-10-13) [Parte X] → `docs/superpowers/plans/2026-10-13-pulizia-dosi.md`, ramo `night/pulizia-dosi` da `master`
13. [pronto] P3 · Pulizie: controlli spenti e fuoco — i controlli fuori da `Button` smettono di sbiadire con l'`opacity`, le due caselle da 20 px diventano `Checkbox`, nessun controllo si spegne col fuoco addosso (stepper, `IngredientPicker`, `InlineField`, «Salva prodotto»), il segno d'attesa sui pulsanti di sola icona, i `<button>` del modulo della ricetta diventano `Button`, il fuoco dopo un annullamento nella coda [T3 Consegne 2–6b] → `docs/superpowers/plans/2026-10-13-pulizie-controlli.md`, ramo `night/pulizie-controlli` da `night/r8-modifica-con-ai`
14. [pronto] P3 · Pulizie: test instabili e piccoli difetti del backend — attese più lunghe sotto carico, un client react-query dei test fatto come quello dell'app, le date dell'e2e nel giorno di Roma, via gli avvisi di Starlette, `occurrences` ricontato con una `COUNT`, il 409 delle due righe che nomina l'ingrediente, i pulsanti della coda con una decisione in volo [T3 Consegne 5–6b, Parte X] → `docs/superpowers/plans/2026-10-13-pulizie-test.md`, ramo `night/pulizie-test` da `master`
15. [pronto] P3 · Pulizie: parole a video — «È «…»?» senza l'articolo sbagliato, la maiuscola al titolo del foglio della cottura e, solo a video, in Lista e Sistema la spesa; «non è un alimento» nella bozza AI; la nota vera delle righe da creare; scegliere dal selettore aggancia la riga nuova con lo stesso nome invece di farne due (Mattia, 2026-10-13) [T3 Consegna 6b, Parte X] → `docs/superpowers/plans/2026-10-13-pulizie-parole.md`, ramo `night/pulizie-parole` da `master`
16. [in corso] P3 · R5, sostituisci ingrediente, precalcolato: una voce per ingrediente × dolce/salato, solo sostituti già in anagrafica, decisa subito dall'AI e segnata come tale, «Sostituisci» nel dettaglio della ricetta con la correzione per quella ricetta, la sezione «Sostituti» in Anagrafica; migrazione `0015`; `decide_substitutes` da lanciare in produzione solo da Mattia dopo il deploy (Mattia, 2026-10-13) [R5] → `docs/superpowers/plans/2026-10-13-r5-sostituti.md`, ramo `night/r5-sostituti` da `master`
17. [pronto] P3 · S4 fetta 1, i nutrienti dell'ingrediente da CIQUAL 2025: `load_ciqual`, `ingredient_nutrition` (migrazione `0016`), `decide_ciqual` in due passi (parole francesi, poi la scelta fra candidati veri), il pilota su Gemma, «Valori nutrizionali» in Anagrafica; il file CIQUAL lo scarica e committa Mattia (Mattia, 2026-10-13) [S4] → `docs/superpowers/plans/2026-10-13-s4-ciqual.md`, ramo `night/s4-ciqual` da `master`
18. [pronto] P3 · S4 fetta 2, i grammi per ingrediente × unità e i nutrienti di una ricetta con la copertura dichiarata («q.b.» fuori, e lo si dice): `ingredient_unit_grams` (migrazione `0017`), `decide_grams`, «Pesi per unità» in Anagrafica, il pannello nel dettaglio della ricetta (Mattia, 2026-10-13) [S4] → `docs/superpowers/plans/2026-10-13-s4-grammi.md`, ramo `night/s4-grammi` da `night/s4-ciqual`
19. [pronto] P3 · H2, l'attività da Health Connect via HC Webhook: passi, allenamenti e peso (anche dal Galaxy Watch, senza doppioni), la chiave del webhook, «Attività» dal ☰; migrazione `0018`; il collegamento sul telefono lo fa Mattia dopo il deploy (Mattia, 2026-10-13) [H2] → `docs/superpowers/plans/2026-10-13-h2-health-connect.md`, ramo `night/h2-health-connect` da `master`
20. [pronto] P3 · Modulo della ricetta: la nota di ogni riga si legge, si corregge e si toglie; un nome nuovo che in anagrafica è un non alimentare lo dice il passo del nome mentre lo si scrive, col collegamento all'Anagrafica in un'altra scheda (Mattia, 2026-10-13) [T3 Consegna 6b, R12] → `docs/superpowers/plans/2026-10-13-modulo-nota-nome.md`, ramo `night/modulo-nota-nome` da `master`

## Da approfondire (giorno)

### Voci decise, da portare a spec e piano
- [tbd] P3 · S4 fetta 3, il tasto «Stima» sul prodotto senza valori: prima la media del suo ingrediente (CIQUAL), poi l'AI con la ricerca web, ogni valore segnato come stima e mai come lettura d'etichetta — deciso il 2026-10-13, serve il piano (e prima una misura del costo della ricerca web su OpenRouter) [S4] → spec `docs/superpowers/specs/2026-10-13-s4-nutrienti-ingrediente-design.md` §8
- [tbd] P3 · P1, creazione di un pasto per tipo, ricette adatte senza nascondere il resto — TBD: la stima calorica da foto [P1]
- [tbd] P3 · P2, NutriScore sul periodo — TBD: la funzione non lineare, e come dichiarare i dati parziali [P2]

### Idee
- [idea] P3 · Annullando una decisione nella coda la riga sparisce e il fuoco cade sulla pagina: portarlo alla scheda del termine tornato in coda [T3 Consegna 6b]
- [idea] P3 · Il titolo del foglio della cottura, per una confezione senza prodotto, è il nome dell'ingrediente in minuscolo: `capitalizeFirst` come nelle righe [T3 Consegna 6b]
- [idea] P3 · La domanda di Open Food Facts in Sistema la spesa dice sempre «È un «…»?» (`OffSuggestionQuestion.tsx`): con un nome femminile esce «È un «zucchina»?». Riformulare senza articolo, per esempio «È «zucchina»?» o «Va bene come «zucchina»?» [giro nel browser 2026-10-07]
- [idea] P3 · Lista e Sistema la spesa mostrano il testo della voce com'è stato scritto, anche in minuscolo (di proposito: è il testo di chi l'ha scritto) — da confermare con Mattia [T3 Consegna 6b]
- [idea] P3 · Nel modulo, un nome nuovo che coincide con un non alimentare dell'anagrafica si scopre solo salvando (422 con la frase): il selettore cerca solo cibo, quindi non lo mostra prima [T3 Consegna 6b, R12]
- [idea] P3 · La casella della Lista (`ListRow.tsx`) è ancora un quadratino da 20 px: `Checkbox` è pronta [T3 Consegna 6b]
- [idea] P3 · Il 409 «Due righe puntano allo stesso ingrediente» non dice quale: nominarlo, così non si cercano le due righe (backend) [T3 Consegna 6b]
- [idea] P3 · Nella coda d'import nessun test di schermo prova i pulsanti di una voce mentre una decisione è in volo [T3 Consegna 6b]
- [idea] P3 · Lo stepper delle porzioni spegne il «−» con `disabled` quando arriva a 1: premuto da tastiera, il fuoco finisce sul `body` (la stessa forma della ✕ di Lista); `unavailableReason` lo terrebbe, ma con una frase in più sotto lo stepper [T3 Consegna 5]
- [idea] P3 · Nel foglio della cottura una riga cambiata si distingue da una intatta solo per la posizione della tacca: valutare un segno in più per «hai dichiarato qualcosa qui». [T3 Consegna 5]
- [idea] P3 · «Elimina» di sola icona non mostra niente mentre archivia (prima diceva «Elimino…»): `Button` potrebbe disegnare un segno di attesa sui pulsanti di sola icona `busy`. [T3 Consegna 5]
- [idea] P3 · Se il ricaricamento della dispensa dopo «Ho cucinato» fallisce, «Cucina» lascia il posto all'avviso e il fuoco cade sulla pagina. [T3 Consegna 5]
- [idea] P3 · Oltre a `ShoppingListScreen.test.tsx`, anche `IngredientScreen.test.tsx` è fallito una volta nella suite intera mentre girava l'e2e: le attese troppo corte sotto carico sono più d'una. [T3 Consegna 5]
- [idea] P3 · Con la piscina delle parole piena e un filtro che scarta tutti i candidati, il ricettario dice «Nessuna ricetta»: ricette fuori dalla piscina potrebbero rispondere. Stesso limite già scritto in `recipe_search.py`, ma qui lo zero non è qualificato [T3 Consegna 4]
- [idea] P3 · Una categoria ricordata che il pannello non può mostrare (le categorie non si caricano, o quella categoria non c'è più): il filtro vale e «Filtri» dice «1 attivo», ma il menu mostra «Tutte». Non è un vicolo cieco («Azzera» c'è), ma il pannello dice il falso [T3 Consegna 4]
- [idea] P3 · Un aggiornamento di sfondo fallito della prima pagina (per esempio dopo un'eliminazione) sostituisce l'elenco già a video con l'errore: meglio tenere le righe e dire che l'aggiornamento non è riuscito [T3 Consegna 4]
- [idea] P3 · Il «Riprova» di un'eliminazione fallita, toccato dopo essere usciti dal dettaglio, porta comunque al ricettario sostituendo la pagina corrente [T3 Consegna 4]
- [idea] P3 · Nella bozza AI, «non in anagrafica» è la formula sbagliata per una riga non alimentare [Parte X]
- [idea] P3 · `skipped_reason` non affiora da nessuna rotta né schermata [Parte X]
- [idea] P3 · «Deciso nella coda» porta a una coda che mostra solo le 50 decisioni più recenti: filtro per termine o annulla dalla scheda [Parte X]
- [idea] P3 · Cercare nell'elenco delle decisioni della coda [T3, esito del giro]
- [idea] P3 · I test di schermata si costruiscono il client react-query con `retry: false` e non provano il retry vero dell'app [Parte X]
- [idea] P3 · Estrarre da `PantryRow.tsx` la domanda del rientro in lista, poi la scadenza [Parte X]
- [idea] P3 · Due confezioni dello stesso prodotto non si distinguono, né in dispensa né nel foglio della cottura [T3, esito del giro]
- [idea] P3 · Tecniche e preparazioni di base mescolate alle ricette; procedimento diviso in passi; i minuti dai dati grezzi; «N dosi su M non si riscalano» che dice quali — fuori dal ridisegno, spec §5 [T3]
- [idea] P3 · Un layout da desktop (oggi una colonna da 448 px) [T3]
- [idea] P3 · Una schermata per correggere i plurali di `units` (oggi `decide_units --imposta` da riga di comando basta) [Parte X]
- [idea] P3 · `IngredientPicker` spegne campo e suggerimenti con `disabled` mentre la scelta è in volo (dalla Consegna 6a «Aggiungi «…»» usa `busy`): lo stesso fuoco perso della ✕ di Lista, in una forma diversa [T3 Consegna 2]
- [idea] P3 · L'annullamento riconta `occurrences` caricando tutte le pagine in attesa col loro JSONB intero, per contare una chiave sola, moltiplicato nel ciclo di merge dell'anagrafica: va bene finché l'annullamento è raro, ma un conteggio SQL dovrebbe restare identico a `count_pending_keys` [S9/T3]
- [idea] P3 · La suite del backend stampa 8 `StarletteDeprecationWarning` per `HTTP_422_UNPROCESSABLE_ENTITY` (preesistente, non tracciato) [Parte X]
- [idea] P3 · `InlineField.tsx` (nome, marca e codice del prodotto) ha ancora `<button disabled>`: dopo un salvataggio riuscito il «Salva» si spegne e il fuoco cade sulla pagina. Il motivo sotto un pulsante che sta nella riga del campo non ci sta, e «invariato» è lo stato di ogni campo a riposo — decidere la forma [T3 Consegna 6a]
- [idea] P3 · `CustomProductForm.tsx` («Salva prodotto») spegne ancora con `disabled`: passarlo alla regola dei pulsanti (`unavailableReason` col perché) [T3 Consegna 6a]
- [idea] P3 · Una prova e2e di `style.spec.ts` («il campo data si vede…») calcola la data con `toISOString()`, in UTC: fra mezzanotte e le 2 ora italiana manda il giorno sbagliato e fallisce («tra 4 gg» invece di «tra 5 gg»). Calcolarla nel giorno di Europe/Rome, come il backend [T3 Consegna 6a]
- [idea] P3 · `ShoppingListScreen.test.tsx` è fallito in alcune corse della suite intera sotto carico, ogni volta su un'asserzione diversa, e passa da solo e nelle corse successive: un'attesa troppo corta da trovare [T3 Consegna 6a]
- [idea] P3 · `Button` con `disabled` e `unavailableReason` insieme non è definito: il `disabled` nativo toglie il fuoco e il perché resta irraggiungibile da tastiera. Oggi nessun chiamante lo fa; far vincere `unavailableReason` o scriverlo nel JSDoc [T3 Consegna 6a]
- [idea] P3 · In `MergePanel.tsx` «Cambia» è un `Button` dentro un `<p class="flex">`: oggi ha solo `busy`, ma se un giorno prende un `unavailableReason` il perché diventa un `<p>` dentro un `<p>`. Cambiare il contenitore in `<div>` [T3 Consegna 6a]
- [idea] P3 · Nel modulo della ricetta, dopo «Aggiungi «pasta»» scegliere anche «Pasta» dai suggerimenti fa due righe (`attach` non confronta con le righe nuove): al salvataggio arriva il 409 delle due righe. Si esce togliendone una, ma confonde: `attach` dovrebbe riconoscere la riga nuova con lo stesso nome. [T3 Consegna 6b]
- [idea] P3 · «Non è in anagrafica: lo creo io salvando.» può essere falso: con «Aggiungi «…»» sempre offerto, si può aggiungere un nome che c'è già (il server poi collega quello esistente e ignora il reparto scelto). [T3 Consegna 6b]
- [idea] P3 · In `RecipeForm.tsx` restano due `<button>` scritti a mano: la ✕ «Togli» (con un SVG in linea: c'è `IconX`) e i due ruoli; passarli a `Button` (`aria-pressed` per i ruoli). [T3 Consegna 6b]

- [idea] P3 · Altri controlli spenti fuori da `Button` usano ancora `opacity` e si leggono male (in chiaro ~1,8:1): `Checkbox` e la casella di `ListRow`, le tacche di `StockGauge`, il nome in `PantryRow` (`aria-disabled:opacity-40`), `CostPicker` (`disabled:opacity-60`), `IngredientPicker` e `OptionList` (`disabled:opacity-50`). Da portare alla regola che la bozza del tema scuro propone per `Button` [T3, bozza 2026-10-06]
- [idea] P3 · Una voce già in lista (in attesa o spuntata) che entra dall'ingresso diretto: la lista continua a chiederla. La scheda di conferma potrebbe dire «è anche in lista» con «Toglila» — fuori dalla bozza di S3, da valutare dopo l'uso [S3, bozza 2026-10-06]
- [idea] P3 · La foto del prodotto (`products.image_url`) nella scheda del prodotto e nella scheda di conferma di S3, dove è grande e una sola; porta con sé la domanda delle immagini chieste a Open Food Facts (rete, privacy, senza rete) [S12, bozza 2026-10-06]
- [idea] P3 · `search_ingredients` non protegge il testo cercato nel `LIKE`: un `%` o un `_` digitati fanno da jolly (`backend/app/repositories/ingredients.py`) [bozza suggerimenti 2026-10-06]
- [idea] P3 · Un suggerimento non dice da quale alias arriva: «Ketchup» per «sal» («salsa ketchup») o «Olio di cocco» per «burro» («burro di cocco») sembrano rumore e non lo sono [bozza suggerimenti 2026-10-06]
- [idea] P3 · Il database di sviluppo locale (`spena`) non ha tabelle: per misurare sui dati in sviluppo va migrato e seminato prima (le misure del 2026-10-06 sono state fatte sul seme) [report 2026-10-06]

## Bloccati
- [bloccato] P3 · R6, cucinabili con sostituti — attende: R5
- [bloccato] P3 · H3, Profilo — attende: la spec di P2, che dice cosa serve
- [bloccato] P3 · P3, pianificare più giorni — attende: P2 e S4 (deciso il 2026-09-24 di non partire prima); aperti anche i profili di budget [P3]
- [bloccato] P3 · M1, motore di suggerimento — attende: pasti, nutrienti e sostituti (P2, S4, R5)

## Da fare a mano (solo Mattia)

_Il 2026-10-07 Claude ha fatto il giro nel browser, a 375 px e nei due temi, sullo stack e2e
usa e getta (seme, nessun dato di produzione): quel che lì è passato è tolto dalle voci qui
sotto, e resta solo ciò che vuole il telefono vero (tastiera, fotocamera, pollice, barra di
stato, installazione) o dati che il seme non ha (foto delle ricette, termini veri della
coda). Difetti trovati: i pulsanti spenti a `opacity` 0,4 in scuro, già nella voce del tema
scuro; «È un «zucchina»?», fra le idee; il nome in minuscolo nel foglio della cottura, già
fra le idee._
- [tbd] P1 · Prove sul telefono della Consegna 6b: R12 con la tastiera vera aperta (il passo del nome, il reparto col selettore nativo senza perdere il filo, il fuoco sulla quantità); la coda con un termine vero dell'import. Nel browser passati il fuoco sul nome e poi sulla quantità, le caselle tutte da 44, l'avviso dopo un annullamento, «L'AI non è disponibile» con la coda che funziona a mano
- [tbd] P1 · Prove sul telefono del Dettaglio ricetta (Consegna 5): il tasto «Ricette» sopra una foto chiara e una scura (il seme non ha foto), le tacche del foglio col pollice, «Salvata.» dopo una bozza dell'AI vera. Nel browser passati lo stepper spento col perché a capo sotto, «Metti in lista ciò che manca» con «1 in lista», tacche da 44 e fuoco di ritorno su «Cucina», «Salvata.» dopo il salvataggio a mano
- [tbd] P1 · Prove sul telefono del Ricettario (Consegna 4): «Filtri» col pollice, le miniature con la rete lenta (il seme non ha foto). Nel browser passati la prima ricetta in vista, il numero su «Filtri», il filtro che resta tornando da una ricetta, «Elimina» e «Annulla» (l'avviso dura 6 s)
- [tbd] P2 · Prove sul telefono della Consegna 6a: la tastiera che si apre da sola sul campo password, e se toccare l'occhio la chiude (nel browser il fuoco passa dal campo al pulsante). Nel browser passati il fuoco nel campo, l'occhio con `autocapitalize="none"`, le icone delle correzioni in Anagrafica (44 px, col nome per lo screen reader), «Metti in dispensa» spento col perché sotto
- [tbd] P1 · Prove sul telefono di Sistema la spesa (Consegna 3): lo scanner con la fotocamera vera, il permesso negato dalle impostazioni del telefono, il selettore data nativo. Nel browser passati il pannello sull'ultima voce, «Fotocamera non disponibile» con la strada a mano, il codice a mano con «Cerca» (anche sbagliato: «ricontrollalo» e «Usa questo codice lo stesso»), la ✕ della data, l'avviso in Dispensa
- [tbd] P1 · Prove sul telefono della Lista (Consegna 2): spuntare camminando col pollice. Nel browser passati la barra sotto l'intestazione scorrendo, i suggerimenti sotto la barra, la riga intera che spunta senza linee fra le righe, «Annulla» dopo la ✕ su una voce nel carrello
- [tbd] P1 · Prove sul telefono della Dispensa (Consegna 1): le tacche col pollice, il selettore data nativo. Nel browser passati il tocco sul bordo di ogni tacca, il campo data col fuoco, la riga «Finito» con «In lista» nei due temi
- [tbd] P2 · Prove sul telefono del tema scuro (Consegna 0): barra di stato nei due temi, icona reinstallata, Inter senza rete, schermata d'avvio (probabile lampo chiaro). Nel browser passati il cambio di tema senza ricaricare e i due `theme-color`
- [tbd] P3 · Sul server: restringere `Bash(ssh hetznerserver:*)` in `.claude/settings.local.json`; togliere `ANTHROPIC_API_KEY` dal `.env`; decidere dei due file non tracciati `.env.bak` e `imposta-password.sh` [Parte X]
- [tbd] P3 · Prova sul telefono delle pulizie: con la tastiera vera aperta, l'ultimo suggerimento della barra della Lista si raggiunge senza scorrere la pagina. Nel browser passato senza tastiera: l'elenco scorre nel suo riquadro (`overscroll-behavior: contain`) e la pagina resta ferma

## In corso
_(niente)_

## Fatti (recenti)
- [fatto] 2026-09-30 · T3 Consegna 6b, l'ultima del ridisegno: il modulo della ricetta con «Salva» principale e il motivo sotto, caselle da 44, R12 («Aggiungi «…»» e il passo del nome, l'ingrediente nasce salvando); `CategorySelect` unico; la coda d'import senza rosso né variabili e senza messaggio a coda vuota, «Forse» della misura del resto, l'annullamento nell'avviso; il guasto dell'AI ambra ovunque; «il server», niente «dataset», «ad astice», le maiuscole solo a video [T3, R12, Parte X] → `master` 69cd9b2, in produzione dal 2026-09-30
- [fatto] 2026-09-30 · `CategorySelect` sostituisce i quattro `<select>` del reparto (anche quello copiato da `NewIngredientFields`) [T3] → `master` 69cd9b2, in produzione dal 2026-09-30
- [fatto] 2026-09-30 · «Ingrediente» o «voce», rivisti caso per caso: cambia la frase della barra della Lista [Parte X] → `master` 69cd9b2, in produzione dal 2026-09-30
- [fatto] 2026-09-30 · T3 Consegna 5, Dettaglio ricetta: il tasto sopra la foto, «Modifica»/«Elimina» come icone, costo in sola lettura, stepper sempre visibile, `StatusDot` e «non basta», «Metti in lista ciò che manca», `StockGauge` nel foglio della cottura, «Apri l'originale» a 44 px; e «Salva nel ricettario» con l'avviso «Salvata.» (T4 chiuso) → `master` 69cd9b2, in produzione dal 2026-09-30
- [fatto] 2026-09-30 · T3 Consegna 4, Ricette: «Nuova», «Filtri» col numero e il pannello in linea, «Cosa posso cucinare» a video, i filtri ricordati finché l'app è aperta, righe compatte con la miniatura, l'avviso al posto della lapide (`useArchiveRecipe`); nel backend `X-Total-Count` e `main_department` → `master` 69cd9b2, in produzione dal 2026-09-30
- [fatto] 2026-09-30 · T3 Consegna 6a, pulsanti, accesso e anagrafica: `Button` con `unavailableReason` e `accessibleName` (una regola sola per i pulsanti spenti), «Sistema la spesa» senza pulsanti scritti a mano, l'accesso col fuoco nel campo e «Mostra password», le correzioni dell'anagrafica come icone accanto al titolo, «Cerca un ingrediente o un prodotto» → `master` 69cd9b2, in produzione dal 2026-09-30
- [fatto] 2026-09-29 · T3 Consegna 3, Sistema la spesa: una riga per voce, un pannello alla volta sotto la sua voce (S10), «Abbina» col selettore unico, «Metti in dispensa N» con l'avviso in Dispensa (T4) → `master` 28d0cdd, in produzione dal 2026-09-29
- [fatto] 2026-09-29 · Pulizie dopo la Lista: il 409 sull'«Annulla» che farebbe un doppione, `Button` con `busy` (la ✕ tiene il fuoco), i suggerimenti che scorrono da sé, le pulizie e2e che fanno fallire, via `set_fill`, il 404 non ritentato con «Questa ricetta non c'è più.», `occurrences` ricontato dopo l'annullamento → `master` 28d0cdd, in produzione dal 2026-09-29
- [fatto] 2026-09-29 · Tema scuro: l'avviso rovesciato (chiaro sullo scuro) va bene, deciso da Mattia; spec §3.5 aggiornata
- [fatto] 2026-09-28 · T3 Consegna 2, Lista → `master` c614e80, in produzione
- [fatto] 2026-09-28 · T3 Consegna 1, Dispensa, con la riga a 375 px e l'Esc sulla data → in produzione
- [fatto] 2026-09-28 · T3 Consegna 0, fondamenta (token chiari e scuri, Inter, icone, primitive) → in produzione
- [fatto] 2026-09-28 · R10, una ricetta si modifica e si elimina → in produzione
- [fatto] 2026-09-28 · S9, correggere quel che è registrato male («Anagrafica») → in produzione
- [fatto] 2026-09-27 · S8, S13, S16–S21, R11, T4 in parte → in produzione

Lo storico completo, con le misure e i perché, è in `docs/prossimi-passi.md`.
