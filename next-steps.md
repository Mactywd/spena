# Next steps

_Ultimo aggiornamento: 2026-09-29 (fase giorno: migrazione da `docs/prossimi-passi.md`)_

Questo è il backlog, ed è l'unico: cosa c'è da fare e in che stato. Il ragionamento dietro
ogni voce (decisioni, misure, perché) resta in `docs/prossimi-passi.md`, sotto il codice
indicato fra parentesi quadre, ad esempio [S3] o [Parte X]. I piani stanno in
`docs/superpowers/plans/`, i report notturni in `docs/night-reports/`.

Stati: `idea` → `tbd` → `pronto` → `in corso` → `fatto`, oppure `bloccato` con il motivo.
Una voce `tbd` con «serve il piano» è già decisa nella spec: manca solo il piano.

Il repo è pubblico: qui non vanno dati di produzione.

## Pronti per la notte

_(nessuno: i piani di oggi sono in scrittura)_

## Da approfondire (giorno)

### Ridisegno (T3), spec `docs/superpowers/specs/2026-09-28-ridisegno-design.md`
- [tbd] P1 · Consegna 3, Sistema la spesa: una riga per voce con le icone, i pannelli sotto la voce (S10 e i suoi tre dettagli), «Abbina» chiuso, «Metti in dispensa N» con l'avviso in Dispensa (T4) — serve il piano (spec §4.3) [T3, S10, T4]
- [tbd] P1 · Consegna 4, Ricette: «+ Nuova», Filtri col contatore, «Cosa posso cucinare», righe compatte con «Hai tutto»/«Manca: …» — serve il piano (spec §4.5) [T3]
- [tbd] P1 · Consegna 5, Dettaglio ricetta: «Metti in lista ciò che manca», `StatusDot` per riga, `StockGauge` nel foglio della cottura, costo in sola lettura, «Apri l'originale» a 44 px — serve il piano (spec §4.6) [T3]
- [tbd] P2 · Consegna 6, il resto: modulo della ricetta con R12, Anagrafica, coda d'import, accesso con «Mostra password», parole a video — serve il piano (spec §4.7) [T3, R12]
- [tbd] P2 · «Salva nel ricettario» senza avviso: l'ultimo punto aperto di T4; nessuna consegna lo nomina — TBD: va nella Consegna 5 o nella 6? [T4]
- [tbd] P2 · Tema scuro, l'avviso con «Annulla» si rovescia in una pastiglia chiara, mentre la spec §3.5 dice «fondo scuro» — TBD per Mattia: va bene il rovescio, o scuro in tutti e due i temi? [T3 Consegna 0]
- [tbd] P3 · Tema scuro: il pulsante primario spento diventa un verde torbido; il velo del ☰ scurisce poco — TBD: come ridisegnarli [T3 Consegna 1]

### Code della Consegna 2 e pulizie
- [tbd] P2 · Il doppione sull'«Annulla» della ✕ in Lista lo evita solo la cache del client: serve un controllo lato server sulla PATCH che rimanda a `pending`/`checked` — serve il piano [T3 Consegna 2]
- [tbd] P2 · La ✕ di Lista usa ancora `disabled` (manca una variante `aria-disabled` di `Button`): dopo una ✕ fallita il fuoco cade sulla pagina — serve il piano [T3 Consegna 2]
- [tbd] P3 · I suggerimenti sotto la barra appiccicata della Lista non hanno un'altezza massima — serve il piano [T3 Consegna 2]
- [tbd] P3 · La vecchia pulizia e2e di `style.spec.ts` (prodotto e dispensa, righe ~985-1072) avvisa soltanto: deve far fallire la prova come la nuova — serve il piano [T3 Consegna 2]
- [tbd] P2 · Togliere `set_fill` e la sua `PATCH` dal backend: nessun client la usa più dalla Consegna 1; `fill_percent` resta nello schema — TBD: si toglie solo la rotta o anche la colonna? [D1]
- [tbd] P2 · Un 404 viene ritentato e poi offre «Riprova»: escluderlo in `lib/queryRetry.ts`, con «Questa ricetta non c'è più» e il ritorno al ricettario — serve il piano [Parte X]
- [tbd] P2 · «1 ricetta in attesa» con due ricette sotto: `undo_decision` non riconta `occurrences` — serve il piano [T3, esito del giro]
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

## Bloccati
- [bloccato] P3 · R6, cucinabili con sostituti — attende: R5
- [bloccato] P3 · H3, Profilo — attende: la spec di P2, che dice cosa serve
- [bloccato] P3 · P3, pianificare più giorni — attende: P2 e S4 (deciso il 2026-09-24 di non partire prima); aperti anche i profili di budget [P3]
- [bloccato] P3 · M1, motore di suggerimento — attende: pasti, nutrienti e sostituti (P2, S4, R5)

## Da fare a mano (solo Mattia)
- [tbd] P1 · Prove sul telefono della Lista (Consegna 2): la barra resta sotto l'intestazione scorrendo, con i suggerimenti che si aprono sotto; spuntare camminando senza le linee fra le righe; «Annulla» dopo la ✕ su una voce nel carrello
- [tbd] P1 · Prove sul telefono della Dispensa (Consegna 1): le tacche col pollice, il selettore data nativo, le righe «Finito»
- [tbd] P2 · Prove sul telefono del tema scuro (Consegna 0): tema vero, barra di stato nei due temi, icona reinstallata, Inter senza rete, schermata d'avvio (probabile lampo chiaro)
- [tbd] P3 · Sul server: restringere `Bash(ssh hetznerserver:*)` in `.claude/settings.local.json`; togliere `ANTHROPIC_API_KEY` dal `.env`; decidere dei due file non tracciati `.env.bak` e `imposta-password.sh` [Parte X]

## In corso
_(niente)_

## Fatti (recenti)
- [fatto] 2026-09-28 · T3 Consegna 2, Lista → `master` c614e80, in produzione
- [fatto] 2026-09-28 · T3 Consegna 1, Dispensa, con la riga a 375 px e l'Esc sulla data → in produzione
- [fatto] 2026-09-28 · T3 Consegna 0, fondamenta (token chiari e scuri, Inter, icone, primitive) → in produzione
- [fatto] 2026-09-28 · R10, una ricetta si modifica e si elimina → in produzione
- [fatto] 2026-09-28 · S9, correggere quel che è registrato male («Anagrafica») → in produzione
- [fatto] 2026-09-27 · S8, S13, S16–S21, R11, T4 in parte → in produzione

Lo storico completo, con le misure e i perché, è in `docs/prossimi-passi.md`.
