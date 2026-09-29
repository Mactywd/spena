# Next steps

_Ultimo aggiornamento: 2026-09-30 (fase notte)_

Questo è il backlog, ed è l'unico: cosa c'è da fare e in che stato. Il ragionamento dietro
ogni voce (decisioni, misure, perché) resta in `docs/prossimi-passi.md`, sotto il codice
indicato fra parentesi quadre, ad esempio [S3] o [Parte X]. I piani stanno in
`docs/superpowers/plans/`, i report notturni in `docs/night-reports/`.

Stati: `idea` → `tbd` → `pronto` → `in corso` → `fatto`, oppure `bloccato` con il motivo.
Una voce `tbd` con «serve il piano» è già decisa nella spec: manca solo il piano.

Il repo è pubblico: qui non vanno dati di produzione.

## Pronti per la notte

Da eseguire **a catena**, in quest'ordine: ogni ramo parte da quello del piano prima, così al merge non ci sono conflitti. Se un piano si blocca, i successivi aspettano.

- [pronto] P1 · T3 Consegna 4, Ricette: «Nuova ricetta», Filtri in linea col numero e «Azzera», «Cosa posso cucinare» visibile, filtri ricordati finché l'app è aperta (Mattia), righe compatte con miniatura e reparto principale, «Hai tutto» / «Manca: …», il totale contato dal server prima del limite, la lapide nell'avviso unico → `docs/superpowers/plans/2026-09-30-ridisegno-ricette.md`, ramo `night/c4-ricette` da `night/c6a-pulsanti` [T3]
- [pronto] P1 · T3 Consegna 5, Dettaglio ricetta: foto col tasto indietro sopra, Modifica/Elimina come icone, costo in sola lettura, porzioni sempre visibili, Principali/Secondari col pallino e «non basta» (Mattia), «Metti in lista ciò che manca», «Cucina» sotto gli ingredienti, tacche nel foglio della cottura, «Salvata.» nell'avviso unico (T4) → `docs/superpowers/plans/2026-09-30-ridisegno-dettaglio-ricetta.md`, ramo `night/c5-dettaglio` da `night/c4-ricette` [T3, T4]
- [pronto] P2 · T3 Consegna 6b, modulo della ricetta, coda d'import e parole: «Proponi» secondario e «Salva» col perché, caselle da 44 px, R12 con «Come si chiama in generale?», `CategorySelect` unico, la coda senza il rosso dell'AI non configurata, via «backend», «autocomplete» e «dataset», «collegato ad astice», maiuscole uniformi a video → `docs/superpowers/plans/2026-09-30-ridisegno-modulo-coda-parole.md`, ramo `night/c6b-modulo-coda-parole` da `night/c5-dettaglio` [T3, R12, Parte X]

## Da approfondire (giorno)

### Ridisegno (T3), spec `docs/superpowers/specs/2026-09-28-ridisegno-design.md`
- [tbd] P3 · Tema scuro: il pulsante primario spento diventa un verde torbido; il velo del ☰ scurisce poco — TBD: come ridisegnarli [T3 Consegna 1]

### Code della Consegna 2 e pulizie
- [tbd] P3 · I suggerimenti degli ingredienti sono sempre dieci righe, anche quando non somigliano più: una soglia o un salto di punteggio nel backend — TBD: quale criterio [T3, esito del giro]

### Voci decise, da portare a spec e piano
- [tbd] P2 · S3, ingresso diretto in dispensa, veloce: scansione e inserimento a mano senza passare dalla lista, estraendo scanner, catalogo e modulo da `StockingScreen.tsx` — TBD: parità subito senza scontrino (è dove pende) o aspettare lo scontrino [S3]
- [tbd] P2 · S12, righe della dispensa riconoscibili: icona per reparto, emoji per ingrediente, foto del prodotto — TBD: brainstorming [S12]
- [tbd] P3 · S14, «Tutto / Cibo / Casa» in dispensa: il server espone `ingredient_kind` o filtra lui — serve la spec [S14]
- [tbd] P3 · S15, reparti della dispensa collassabili, col numero di voci quando sono chiusi e aperti da una ricerca — serve la spec [S15]
- [tbd] P3 · R2, secondo modo: riporzionare a partire da un ingrediente («io ne faccio 150 g») — TBD: solo vista o si salva [R2]
- [tbd] P3 · R5, sostituisci ingrediente, precalcolato — TBD grosso: quante coppie, costo col tetto di 1 $/giorno, dipende dalla ricetta o dalla coppia, come si corregge [R5]
- [tbd] P3 · R8, modifica con AI che salva una ricetta nuova — TBD: il legame con l'originale si tiene e si vede? [R8]
- [tbd] P3 · S4, resto: nutrienti sull'ingrediente generico (CREA, senza API) e il tasto «Stima» con l'AI — TBD: fonte, modello, ricerca web su OpenRouter e il suo costo [S4]
- [tbd] P3 · P1, creazione di un pasto per tipo, ricette adatte senza nascondere il resto — TBD: la stima calorica da foto [P1]
- [tbd] P3 · P2, NutriScore sul periodo — TBD: la funzione non lineare, e come dichiarare i dati parziali [P2]
- [tbd] P3 · H1, Expense Tracker su `llm_calls` — TBD: cosa mostrare [H1]
- [tbd] P3 · H2, Samsung Health — TBD: ricerca su una via praticabile senza diventare partner [H2]
- [tbd] P3 · Dosi dell'import con l'aggettivo davanti (~70) e numeri nel nome letti come dose (~90, «36 mesi»), più le unità spurie in `units`: ripulire `quantity_text` all'import e rilanciare `reparse_quantities` — TBD: tocca i dati di produzione, serve il via di Mattia [Parte X]
- [tbd] P3 · Una pagina `SKIPPED` non torna mai in coda, anche dopo aver corretto la causa — TBD: quale strada la rimette `pending` [Parte X]
- [tbd] P3 · «Rimetti in lista» nel foglio della cottura è pre-spuntata solo per «finito», in dispensa la domanda arriva anche nel giallo — TBD: decidere una volta [Parte X]

### Idee
- [idea] P3 · `NewIngredientFields` copia il `<select>` del reparto di `registry/CategoryForm.tsx`: unirli con R12 (Consegna 6) [T3]
- [idea] P3 · «Ingrediente» invece di «voce» in `AddItemField.tsx` e `StockingScreen.tsx` (forse dentro le Consegne 3 e 6) [Parte X]
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
- [idea] P3 · La suite del backend stampa 7 `StarletteDeprecationWarning` per `HTTP_422_UNPROCESSABLE_ENTITY` (preesistente, non tracciato) [Parte X]
- [idea] P3 · `InlineField.tsx` (nome, marca e codice del prodotto) ha ancora `<button disabled>`: dopo un salvataggio riuscito il «Salva» si spegne e il fuoco cade sulla pagina. Il motivo sotto un pulsante che sta nella riga del campo non ci sta, e «invariato» è lo stato di ogni campo a riposo — decidere la forma [T3 Consegna 6a]
- [idea] P3 · `CustomProductForm.tsx` («Salva prodotto») spegne ancora con `disabled`: passarlo alla regola dei pulsanti (`unavailableReason` col perché) [T3 Consegna 6a]
- [idea] P3 · Una prova e2e di `style.spec.ts` («il campo data si vede…») calcola la data con `toISOString()`, in UTC: fra mezzanotte e le 2 ora italiana manda il giorno sbagliato e fallisce («tra 4 gg» invece di «tra 5 gg»). Calcolarla nel giorno di Europe/Rome, come il backend [T3 Consegna 6a]
- [idea] P3 · `ShoppingListScreen.test.tsx` è fallito in alcune corse della suite intera sotto carico, ogni volta su un'asserzione diversa, e passa da solo e nelle corse successive: un'attesa troppo corta da trovare [T3 Consegna 6a]
- [idea] P3 · `Button` con `disabled` e `unavailableReason` insieme non è definito: il `disabled` nativo toglie il fuoco e il perché resta irraggiungibile da tastiera. Oggi nessun chiamante lo fa; far vincere `unavailableReason` o scriverlo nel JSDoc [T3 Consegna 6a]
- [idea] P3 · In `MergePanel.tsx` «Cambia» è un `Button` dentro un `<p class="flex">`: oggi ha solo `busy`, ma se un giorno prende un `unavailableReason` il perché diventa un `<p>` dentro un `<p>`. Cambiare il contenitore in `<div>` [T3 Consegna 6a]

## Bloccati
- [bloccato] P3 · R6, cucinabili con sostituti — attende: R5
- [bloccato] P3 · H3, Profilo — attende: la spec di P2, che dice cosa serve
- [bloccato] P3 · P3, pianificare più giorni — attende: P2 e S4 (deciso il 2026-09-24 di non partire prima); aperti anche i profili di budget [P3]
- [bloccato] P3 · M1, motore di suggerimento — attende: pasti, nutrienti e sostituti (P2, S4, R5)

## Da fare a mano (solo Mattia)
- [tbd] P2 · Prove sul telefono della Consegna 6a: l'accesso (la tastiera col campo che ha il fuoco, l'occhio, la password mostrata senza maiuscola), le icone delle correzioni in Anagrafica senza testo, «Metti in dispensa» spento col perché sotto
- [tbd] P1 · Prove sul telefono di Sistema la spesa (Consegna 3): un pannello aperto su una voce in fondo, lo scanner con la fotocamera vera e negata, il codice a mano con «Cerca», il campo data e la sua ✕, l'avviso in Dispensa
- [tbd] P1 · Prove sul telefono della Lista (Consegna 2): la barra resta sotto l'intestazione scorrendo, con i suggerimenti che si aprono sotto; spuntare camminando senza le linee fra le righe; «Annulla» dopo la ✕ su una voce nel carrello
- [tbd] P1 · Prove sul telefono della Dispensa (Consegna 1): le tacche col pollice, il selettore data nativo, le righe «Finito»
- [tbd] P2 · Prove sul telefono del tema scuro (Consegna 0): tema vero, barra di stato nei due temi, icona reinstallata, Inter senza rete, schermata d'avvio (probabile lampo chiaro)
- [tbd] P3 · Sul server: restringere `Bash(ssh hetznerserver:*)` in `.claude/settings.local.json`; togliere `ANTHROPIC_API_KEY` dal `.env`; decidere dei due file non tracciati `.env.bak` e `imposta-password.sh` [Parte X]
- [tbd] P3 · Prova sul telefono delle pulizie: con la tastiera aperta i suggerimenti della barra della Lista scorrono nel loro elenco, e l'ultimo si raggiunge senza scorrere la pagina

## In corso
_(niente)_

## Fatti (recenti)
- [fatto] 2026-09-30 · T3 Consegna 6a, pulsanti, accesso e anagrafica: `Button` con `unavailableReason` e `accessibleName` (una regola sola per i pulsanti spenti), «Sistema la spesa» senza pulsanti scritti a mano, l'accesso col fuoco nel campo e «Mostra password», le correzioni dell'anagrafica come icone accanto al titolo, «Cerca un ingrediente o un prodotto» → branch night/c6a-pulsanti (da revisionare)
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
