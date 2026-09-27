# Spena — prossimi passi

Aggiornato il 2026-09-27, quattro volte. La quarta: **il giro di T3 è fatto** — un
sottoagente ha girato il sito su una copia dei dati di produzione e ha annotato 99
osservazioni. I difetti, ricontrollati sul codice, sono diventati voci loro
(S16–S21 in Parte II, R10 e R11 in Parte III, T4, più tre dettagli in S10 e uno in Parte X); il resto è sotto T3, materiale della
spec. In più, **il parmigiano sotto «burro» è stato sistemato a mano in produzione**
(nota in S9). La terza: **S13 e S8 fatti** — il cursore della
dispensa cambia solo con un tocco e non più scorrendo, e il codice a barre letto segue
anche le uscite dal catalogo — più quattro piccole cose di Parte X (il lint è verde, i
campi data hanno un `max`, `StatusToggle` non è più nominato, e il «+ scadenza» che
«sbordava» non sbordava). Il cursore aspetta la prova sul telefono vero. La seconda: **dieci voci dall'uso vero**, portate
da Mattia. Sono S8–S15 in Parte II (codici a barre, correzione degli errori di
registrazione, «Sistema la spesa», ricerca, riconoscibilità, cursore, cibo/casa e
reparti in dispensa), S3 ripresa, e T3, la revisione di UI e UX che parte da un giro
del sito fatto da un sottoagente. L'ordine proposto è in Parte VIII. La prima:
**l'anagrafica è stata rivista voce per voce e corretta in produzione** — i 35 termini rimasti in coda sono decisi (coda vuota, **8.451 ricette**),
e un piano di 229 passi ha tolto alias sbagliati, doppioni che davano falsi «manca» e
reparti sbagliati; gli ingredienti sono passati da 952 a 884. I dettagli sono in R4,
sotto «La revisione dell'anagrafica». Prima: il 2026-09-24, otto volte. L'ottava: **R4 eseguita** — in produzione ci
sono **8.136 ricette**, 56 termini aspettano una decisione a mano e trattengono 315
pagine, l'AI è costata **0,66 $** e il database pesa **72 MB**; i numeri sono in R4.
La settima: **R4 costruita, non eseguita** — in
`master`, con il runbook per la sessione che la eseguirà
(`docs/import-gz-runbook.md`). Misurando, R4 ha trovato i filtri del ricettario in
errore oltre le ~3.300 ricette: corretti prima che l'import li raggiungesse. La sesta: **un ricontrollo del lavoro della
giornata ha trovato un difetto e tre inesattezze**, tutti corretti. Il difetto: Open
Food Facts scrive ogni `_100g` in grammi, e S4 salvava quei grammi sotto chiavi che il
vocabolario dichiara in mg e µg — mille volte troppo poco; nessun prodotto in
produzione ne era stato toccato. Le inesattezze: le parti dell'Allegato XIII erano
invertite (la A sono vitamine e minerali, la B energia e macronutrienti) e i conteggi
sbagliati; la sitemap delle ricette **esiste** ed è quella che l'import usa già (8.469
indirizzi, contati); e R4 **chiama** l'AI, per decidere i termini. La quinta: **S4 costruita in parte** — il
livello prodotto dei nutrienti (vocabolario canonico dell'Allegato XIII, quattro
nuovi campi raccolti da Open Food Facts: vitamina C, calcio, ferro, potassio),
nessuna migrazione, nessuno schermo nuovo; il livello ingrediente generico e il tasto
«Stima» restano TBD. Il vincolo di storage su R4 è stato tolto nella stessa
conversazione. La quarta: **due ricerche per sbloccare i
prossimi passi** — i campi nutrizionali di S4 (macro invariati, 27 micronutrienti
dall'Allegato XIII del Reg. UE 1169/2011, CREA senza API) e il dimensionamento
storage di R4 (l'intero catalogo, 8.469 ricette, sta in circa 150 MB: il tetto dei
100 non era giustificato dai numeri). Entrambe ricontrollate e corrette lo stesso
giorno: vedi la sesta. La terza: **R9 in
produzione** — migrazione `0010`
applicata, `reread_costs` eseguito (31 costi scritti, 9 pagine senza costo, 0 sparite),
pacchetto servito verificato identico alla build (`index-COEGqsbx.js`,
`index-5M6VGWMn.css`). **Con questo non resta lavoro già impegnato.** La seconda: **R9
costruita** — il costo da uno a cinque `€` c'è, si sceglie nel dettaglio, la bozza AI lo
propone e l'import lo legge dalla pagina; mancava il deploy. La prima: **due voci
nuove**: R9, il costo della ricetta da uno a
cinque `€`, e P3, la pianificazione su più giorni con un budget — il brainstorming
sulla forma del budget è stato fatto in giornata: conta solo la media per pasto,
scelta con dei profili, e gli avanzi non ripagano). Prima: il 2026-09-23 (**la verifica a mano di S7 e R7 è stata fatta ed è
passata**: nessun difetto). Prima: il 2026-09-22 (**S7 e R7 in produzione**: la
scadenza in dispensa e la scala a cinque gradini del ricettario girano su
`spena.mattiagirellini.com`, migrazione `0009` applicata), il
2026-09-21 (**S7 costruito**: la dispensa conosce una data di scadenza facoltativa per
elemento, che si legge sulla riga e non cambia nessuno stato — e con lei `CLAUDE.md` e
la spec madre §2 emendati; lo stesso giorno **R7**: la casella «Solo quelle che posso
cucinare» è diventata una scala a cinque gradini, e la scheda dice quali ingredienti
mancano), il 2026-09-20 (D1 e la metà per porzioni di R2 in produzione, e in giornata
**D5 decisa**: la scadenza entra in dispensa come segnale; prima, lo stesso giorno,
S6 e la porta della creazione riaperta), il 2026-09-18 (D4 e S5, il non alimentare) e
il 2026-09-17 (S1, S2, R1, R3, T1, più la domanda del rientro in lista estesa al
giallo e il filtro per ingrediente rifatto al plurale).

Questo file è **l'unico posto dove sta la lista**. La roadmap per fasi della spec
madre (`docs/superpowers/specs/2026-09-11-spena-design.md`, §4) resta il documento
d'origine, ma da qui in avanti è superata in ampiezza: quel che segue è la cornice
completa di quel che l'app deve diventare.

Non è una spec e non vuole esserlo. È la cornice: serve a vedere tutto insieme, a
sapere cosa dipende da cosa, e a decidere l'ordine. Ogni blocco diventerà una spec
sua, dopo un brainstorming suo.

**Legenda**

- **[D]** deciso, si può scrivere la spec quando tocca
- **[?]** domanda aperta che cambia la forma di altre cose: va chiusa prima
- **TBD** da approfondire in un brainstorming dedicato, prima della spec
- **↳** dipende da

---

## Stato di oggi

v1 completa (24 task), import massivo da GialloZafferano, LLM su OpenRouter che
decide i termini dell'import. Tutto in `master`, tutto in produzione su
`spena.mattiagirellini.com`. Verifica manuale del giro completo fatta il 2026-09-15,
nessun difetto riportato; `import anthropic` fallisce nell'immagine costruita, come
deve.

Sezioni primarie di oggi: **Lista, Dispensa, Ricette** (tre schede in
`TabBar.tsx`). Tutto quel che segue si innesta su queste.

**Le cinque voci indipendenti di Parte VIII** — S1, S2, R1, R3, e in parte T1 —
sono implementate, verdi, **entrate in `master` e distribuite** il 2026-09-17
(migrazione `0006` applicata in produzione). Nello stesso giorno, e con un secondo
deploy, sono andati in produzione anche i due ritocchi che seguirono la verifica a
mano: la domanda del rientro in lista estesa al giallo (S2) e il filtro per
ingrediente rifatto al plurale (R3), quest'ultimo **senza migrazioni**. Dove questo
file dice «FATTO 2026-09-17» qui sotto, intende codice che gira su
`spena.mattiagirellini.com`, non codice fermo in un ramo.

**Il 2026-09-18 sono entrati in `master` e in produzione D4 e S5**, il non
alimentare: migrazione `0007` applicata all'avvio, anagrafica allargata a 18 voci
`casa`/`igiene` caricate con `seed --solo-ingredienti`, ricette non toccate. La
verifica a mano dello stesso giorno ha trovato un difetto **preesistente e non
legato ai non alimentari**: vedi **S6**.

**Il 2026-09-20 S6 è entrato in `master` e in produzione**: la porta che crea un
ingrediente non si chiude più quando la ricerca trova qualcosa. Solo frontend,
**nessuna migrazione**. Che in produzione ci sia davvero il codice nuovo è verificato
sul pacchetto servito — `assets/index-C2_ldMnr.js`, lo stesso nome (cioè lo stesso
contenuto) della build locale del ramo corretto — e non sui container «healthy», che
sarebbero healthy anche con il pacchetto di ieri.

**Lo stesso 2026-09-20, più tardi, sono entrati in `master` e in produzione D1 e la
metà per porzioni di R2**: le quantità strutturate nelle ricette e lo stepper delle
porzioni. Migrazione `0008` applicata all'avvio; pacchetto servito
`assets/index-CBbpl1eW.js`, identico alla build locale del codice fuso. I due comandi
di §9 hanno girato sul database vero: `reparse_quantities` ha letto **382 dosi su 550**
e depositato **27 unità**, `decide_units` le ha decise in tre giri da dodici — il tetto
per lotto, aggiunto dalla revisione finale poche ore prima, ha fatto esattamente quel
che era stato scritto per fare: ventisette unità in una chiamata sola avrebbero
sforato il soffitto dei token, e il comando avrebbe stampato «0 unità decise» uscendo
con successo. Spesa totale all'AI: **0,00019 $**. La verifica a mano è stata fatta e
non ha trovato difetti.

**Il 2026-09-21 S7 è stato costruito** sul ramo `scadenza-dispensa`: undici task,
diciassette commit, suite verdi (644 backend, 292 jsdom, 12 e2e). **Il 2026-09-22 è
entrato in `master` e in produzione**, con un fast-forward e senza conflitti.
Migrazione `0009` applicata all'avvio (`alembic current` sul container risponde
`0009 (head)`, e `pantry_items.expires_on` esiste come `date` annullabile); pacchetto
servito `assets/index-sNWfaC-_.js` e `assets/index-B3fgdiVV.css`, **identici** alla
build locale del codice fuso — che è la prova, non i container «healthy».

**Lo stesso deploy ha finalmente costruito l'immagine di R7.** Il server aveva già il
commit (`355360d`, il merge del 2026-09-21), ma da allora nessuno aveva ricostruito:
la scala a cinque gradini e i nomi degli ingredienti mancanti diventano visibili con
questo deploy, non con quello di ieri. Vale la pena ricordarlo la prossima volta: un
`git pull` sul server non distribuisce niente da solo, perché il frontend è compilato
dentro l'immagine.

**Il 2026-09-23 la verifica a mano di S7 e R7 è stata fatta ed è passata**: nessun
difetto riportato. Le quattro cose che nessun test poteva vedere sono state guardate
sul telefono e stanno tutte: il selettore data nativo di Android chiude il campo in
modo da far scattare il salvataggio (era il secondo difetto grave di S7, qui sotto —
fino a ieri provato in Chromium e non su un telefono vero); una data scaduta **non**
cambia lo stato né la cucinabilità; una data svuotata si cancella senza «riprova»; e
il viola si stacca dal verde e dall'ambra alla luce del giorno.

**Con questo non resta lavoro già impegnato**: tutto quel che segue è scelta, e il
prossimo passo vuole prima la sua spec.

**Il 2026-09-24 R9 è stata costruita**, con la sua spec, sul ramo di lavoro della
sessione: suite verdi (701 backend, 308 jsdom, 13 e2e su uno stack pulito), ed è
**entrata in `master`** lo stesso giorno con un fast-forward (`c8814c2`). Il deploy
non si è potuto fare dalla sessione cloud, che non raggiunge il server; **è stato
fatto lo stesso giorno da una sessione locale con accesso SSH a `hetznerserver`**:
`git pull --ff-only`, `docker compose -f docker-compose.prod.yml up -d --build --wait`,
migrazione `0010` applicata (`alembic current` → `0010 (head)`), `reread_costs`
eseguito una volta (31 costi scritti, 9 pagine senza costo, 0 sparite), pacchetto
servito verificato identico alla build locale. La verifica a mano del grigio dei
gradini spenti alla luce del giorno è stata dichiarata fatta da Mattia, non da un
browser controllato.

Due cose si sono viste solo sui dati veri, e hanno la loro voce in **Parte X**: due
plurali sbagliati dall'AI su ventisette (uno dei quali l'`--azzera` non sapeva
correggere, il che ha prodotto `--imposta` lo stesso giorno), e circa settanta dosi
che contengono una dose vera che il parser non legge, perché l'import le ha scritte
con un aggettivo e lo spazio bianco della pagina davanti al numero.

**Lo stesso 2026-09-24, più tardi, R4 è stata eseguita in produzione** con
`docs/import-gz-runbook.md`, da una sessione locale: deploy di `343d117` (pacchetto
servito `index-CUXgt-G-.js`, alembic `0010 (head)`), backup, via le 26 ricette di
semina, `import_gz --tutto` dalle 15:29 alle 20:15 UTC, `decide_units` in cinque giri.
Il ricettario ha **8.136 ricette**; 56 termini aspettano la mano in «Ingredienti da
abbinare», e con loro 315 pagine che entreranno da sé. I numeri sono in **R4**; una
cosa vista solo sui dati veri (le dosi del tipo «36 mesi») è in **Parte X**.

---

# Parte I — Le decisioni che bloccano il resto

Sono cinque, e **sono tutte chiuse** — tre il 2026-09-17, la quarta il 2026-09-18,
D5 il 2026-09-20. Stanno qui perché cambiano la forma di molte cose a valle: chi apre
una spec di Parte II, III o IV parte da queste. Le prime quattro erano proposte che
consideravo già buone, segnalate qui solo perché toccavano una decisione fondante; D5
era diversa, perché chiedeva di riaprire la stessa decisione fondante dal lato che D1
aveva appena deciso di non toccare — ed è stata riaperta, di quel tanto e non di più.

## D1. Le quantità nelle ricette **[FATTO 2026-09-20]**

> **Decisione: sì, e solo nelle ricette.** La proposta qui sotto è quella adottata,
> ed è quella costruita: `recipe_ingredients` porta `quantity_value` e
> `quantity_unit_id` accanto a `quantity_text` (migrazione `0008`), un parser in
> `backend/app/domain/quantities.py` li riempie al meglio possibile, un registro
> `units` aperto cresce da sé con l'AI che ne decide singolare e plurale (con
> verifica prima di applicare e un comando di undo), e `GET
> /api/v1/recipes/{id}?servings=N` riscala le righe parsate — da schermo, con lo
> stepper delle porzioni. Il dettaglio è nella sua spec,
> `docs/superpowers/specs/2026-09-20-quantita-ricette-design.md`. La dispensa non
> è cambiata di una riga. `CLAUDE.md` (decisione fondante 1) e la spec madre §2
> sono stati emendati lo stesso giorno di questa voce, come il riquadro imponeva.
>
> **In produzione dal 2026-09-20**, con i passi di §9 eseguiti in ordine: migrazione
> `0008` all'avvio, `reparse_quantities` (382 dosi su 550 lette, 27 unità
> depositate), `decide_units` in tre giri da dodici, verifica a mano senza difetti.
> Il codice nuovo c'è davvero: il pacchetto servito è `assets/index-CBbpl1eW.js`,
> lo stesso nome della build locale del codice fuso. La revisione finale dell'intero
> ramo, prima della fusione, ha trovato un difetto critico che nessuna delle undici
> revisioni per task poteva vedere — una parola d'unità più lunga di trenta caratteri
> faceva fallire l'intera scrittura che la conteneva, quindi un 500 dall'API, la
> materializzazione di un'intera pagina d'import persa, e il comando di riempimento
> bloccato — più sette importanti, fra cui lo stepper che a ogni tocco svuotava lo
> schermo e la cottura di una ricetta riscalata che registrava le porzioni sbagliate
> in `cooking_events`, cioè nel dato su cui la fase 3 costruirà.

**Il problema (2026-09-17).** La decisione fondante numero 1 diceva «niente
quantità, da nessuna parte», estesa fino a `recipe_ingredients.quantity_text` — testo
libero, si diceva, buono solo per la visualizzazione e mai per un conto. Ma tre voci
della lista nuova chiedevano esattamente un conto su quel campo: *riporziona*,
*stima nutrienti di una ricetta*, *NutriScore*. Senza una decisione esplicita qui,
quelle tre voci avrebbero fatto deragliare l'app per inerzia, un pezzo alla volta.

**Come (proposto il 2026-09-17, costruito il 2026-09-20).** Restringere la decisione
fondante a dove serviva davvero — **la dispensa** — e dare alle ricette quantità
strutturate accanto al testo:

- `quantity_text` resta la verità da mostrare, non viene mai riscritto né perso;
- si affiancano `quantity_value` e `quantity_unit_id`, **entrambi annullabili**;
- il riempimento è al meglio possibile: «400 g» → `(400, g)`; «q.b.» → `(NULL,
  NULL)`; «2 cucchiai» → `(2, cucchiaio)` con una tabella di conversione dichiarata
  approssimata;
- **la dispensa non cambia di una riga.** Niente quantità, niente unità, niente
  scadenze: è lì che quella decisione ha comprato quel che doveva comprare, cioè
  nessuna manutenzione giornaliera;
- chi non ha parsato non scala e non conta: «q.b.» resta «q.b.» dopo il riporziona —
  ed è giusto — e la nutrizione dichiara la sua copertura («calcolato sull'82% degli
  ingredienti») invece di fingere lo zero, coerente con «i nutrienti mancanti restano
  mancanti».

> **Nota 2026-09-17.** `pantry_items.fill_percent` esiste già (S2 in Parte II): è la
> posizione di un cursore, 0–100, annullabile. Non è un'eccezione al punto sopra
> perché è una **posizione**, non una quantità — non ha unità, non scade, e l'unico
> conto in cui entra è `status_for_fill`, che ne ricava `available`/`low`/`finished`:
> una soglia, non un'aritmetica. Non si somma, non si scala, non nutre. La decisione
> fondante numero 1, ristretta alla dispensa il 2026-09-20, resta intera anche lì:
> questa colonna c'è, e l'emendamento di `CLAUDE.md` l'ha citata apposta perché non
> conti come precedente.

**Perché non l'alternativa.** Quantità vere anche in dispensa avrebbero sbloccato
conti più precisi, ma avrebbero reintrodotto la manutenzione giornaliera che la
decisione fondante esisteva per evitare — la cosa che fa abbandonare le app come
questa. E dire di no del tutto avrebbe fatto cadere riporziona, la nutrizione delle
ricette, il NutriScore e il motore di suggerimento: cioè le Parti IV e V intere.

↳ da questa dipendono: riporziona, nutrizione delle ricette, NutriScore, motore di
suggerimento.

## D2. Cucinare e mangiare sono la stessa azione? **[D — deciso il 2026-09-17]**

> **Decisione: sì, cucinare crea il pasto.** La proposta qui sotto è quella adottata.

Oggi «cucina» aggiorna la dispensa e registra un `cooking_event`. La lista nuova
aggiunge «crea un pasto», che compone un pasto da più ricette. Se restano due azioni
scollegate, cucinare e poi registrare la cena sono due registrazioni della stessa
cena, e il diario mente o raddoppia.

**Come.** Cucinare **è** mangiare, salvo dire il contrario: la scheda di
cottura chiede il tipo di pasto e il pasto nasce da lì. Alimentazione permette
comunque di aggiungere un pasto che non è nato da una cottura — il ristorante, lo
spuntino, la foto di un piatto — e di togliere dal pasto una ricetta che hai cucinato
per qualcun altro.

**Perché non l'alternativa.** Tenerli separati avrebbe dato più controllo al prezzo
di inserire la stessa cena due volte: è il doppio lavoro che in un mese fa smettere
di compilare un diario. Lasciare un pasto «da assegnare» non chiede niente mentre
cucini, ma costruisce un arretrato — e un arretrato in un'app di casa non si smaltisce
mai.

↳ da questa dipendono: la forma della scheda di cottura, il modello dei pasti,
`cooking_events`.

## D3. Cosa sta nella navbar, e come si raggiungono le sottosezioni **[D — deciso il 2026-09-17]**

> **Decisione: quattro schede, la quarta «Pasti».** La proposta qui sotto è quella
> adottata, nome compreso.

Oggi tre schede. La lista aggiunge una sezione primaria (Alimentazione) e chiede che
le sottosezioni — «sistema la spesa», «ingredienti da abbinare» — **siano sempre
raggiungibili con un tasto**, anche quando non c'è niente da fare.

**Come.**

- Quattro schede in basso: **Lista, Dispensa, Ricette, Pasti**;
- ogni sottosezione vive come **scheda d'ingresso fissa in cima alla sezione madre**
  — «Sistema la spesa» in cima a Lista e a Dispensa, «Ingredienti da abbinare» in
  cima a Ricette — sempre presente, con un pallino di avviso e un fondo diverso solo
  quando c'è davvero qualcosa da fare;
- l'**hamburger** in alto a destra è l'indice completo: ci trovi le sottosezioni
  *e* le sezioni secondarie (Spese, Profilo, Connettori).

**Il nome.** La spec madre la chiama «diario dei pasti»; in navbar è **«Pasti»**,
corto e concreto. «Alimentazione» copriva anche punteggio e fabbisogni, ma è lungo per
una navbar da quattro su 375px. Il NutriScore vive **dentro** Pasti come seconda
vista, non come scheda sua.

**Perché non cinque schede.** Un hub azioni separato avrebbe reso tutte le
sottosezioni visibili allo stesso livello, ma cinque icone su 375px lasciano ~75px
l'una e la navbar sarebbe diventata il punto stretto dell'app. Le schede d'ingresso in
cima alla sezione madre ottengono la stessa visibilità senza pagare quel prezzo.

↳ da questa dipendono: header globale, hamburger, tasto indietro, tutte le schede
d'ingresso, e il fatto che `TabBar.tsx` passi da `grid-cols-3` a `grid-cols-4`.

## D4. Il non alimentare **[FATTO 2026-09-18]**

Detersivo e carta igienica stanno in lista e in dispensa senza una seconda lista.
La via scelta è stata **un campo sull'anagrafica esistente**, non una tabella
nuova: due assi, non uno — il reparto (`ingredients.category`, ora con due voci in
più, `casa` e `igiene`) e `ingredients.kind` (`food` | `non_food`), che non si
scrive mai a mano ma si deriva dal reparto con `kind_for_category`
(`backend/app/domain/rules.py`). La lista, la dispensa e l'autocomplete continuano
a fare una join sola. Il seme porta diciotto voci non alimentari (sette di
`igiene`, undici di `casa`).

Le guardie sono più di quelle previste in origine, perché due revisioni ne hanno
aggiunte che questa proposta non anticipava: la lista completa, con i file e le
righe, sta in `docs/superpowers/specs/2026-09-17-non-alimentari-design.md`. In
sintesi, l'ultima linea è il funnel in `create_recipe`
(`backend/app/repositories/recipes.py`), che solleva `NonFoodInRecipe`; a monte,
le decisioni dell'AI sull'import (`decide.py`) e i due rifiuti 422 della coda
umana (`api/imports.py`) fanno sì che quel funnel quasi non venga mai raggiunto;
lato client, i tre selettori di ingredienti usati dalle schermate di ricetta
chiedono `kind=food` all'anagrafica. Un numero fisso qui invecchierebbe male — è
già successo una volta nel corso di questo stesso lavoro — quindi la spec, non
questa riga, è la fonte per «quante sono oggi».

**Sulla parola «ingrediente»: verificato, e la premessa era sbagliata.** Non è
vero che lista e dispensa dicano sempre «voce»: `AddItemField.tsx` (lista) e
`StockingScreen.tsx` (sistemazione della spesa) mostrano entrambi «ingrediente»
all'utente — «l'ingrediente si abbina dopo», «Abbina un ingrediente», «Crea
l'ingrediente «…»» — proprio nel momento in cui si collega una voce di testo
libero all'anagrafica. Non è un difetto introdotto da questo lavoro, esisteva
già prima; resta un rinominamento aperto, non chiuso da questo task — voce in
**Parte X**, dove si guarda il lavoro ancora aperto.

## D5. La scadenza in dispensa **[D 2026-09-20, costruita con S7 il 2026-09-21]** — riapre la decisione fondante 1

> **Decisione: sì, la scadenza entra in dispensa, e resta un segnale.** Le due
> domande che decidevano la forma di tutto il resto sono chiuse, e sono quelle che
> seguono.
>
> **Lo stato resta la sola verità** (domanda 1). La scadenza non entra in
> `status_for_fill`, non è un quarto stato, e **una cosa scaduta resta dov'è**:
> disponibile, contata dalle ricette esattamente come il giorno prima. Niente diventa
> non cucinabile di notte senza che nessuno abbia toccato niente. La riga lo dice, e
> chi guarda decide — «scegliamo qualcos'altro» è una decisione di chi cucina, non
> una che il database prende da sé.
>
> **Il colore non è il giallo** (domanda 2). Ne serve uno suo nel blocco `@theme`: il
> giallo del cursore vuol già dire «comincia a mancare», e due fatti diversi sullo
> stesso colore non ne dicono più nessuno.
>
> Le domande 3, 4 e 6 restano come sono scritte qui sotto — erano proposte senza una
> vera alternativa. **Alla spec resta la mezza domanda 5** che il «resta» non chiude:
> se «scaduto» sia lo stesso segnale detto più forte o un terzo colore. La proposta è
> la prima, un token solo a due intensità, perché è lo stesso fatto a due distanze.
>
> **Questo riapre la decisione fondante 1 dal lato della dispensa**, e quando la spec
> si scriverà `CLAUDE.md` e la spec madre §2 si emendano di nuovo e **insieme**, come
> il riquadro impone: la dispensa non conosce quantità né unità, e conosce una data
> che non si mantiene.
>
> **Emendati il 2026-09-21**, nello stesso commit e insieme, come il riquadro
> imponeva: la decisione fondante 1 di `CLAUDE.md` e la nota d'emendamento in cima al
> §2 della spec madre dicono adesso la stessa cosa — la data c'è, è facoltativa, non
> entra in `status_for_fill` né in `availability_map` né in nessun giudizio di
> cucinabilità, e la ragione per cui la regola si piega qui e non per le quantità è
> quella scritta qui sotto: una quantità va mantenuta, una scadenza no.

**Chiesto e deciso il 2026-09-20.** Quando un prodotto entra in dispensa si può scrivere anche
la sua data di scadenza; la dispensa la mostra; e **quando mancano sette giorni la
riga cambia colore** per dire che ci si sta avvicinando.

**Perché sta in Parte I e non in Parte II.** La decisione fondante numero 1 nomina la
scadenza per esteso: «la dispensa non conosce quantità, unità **o date di scadenza**».
Non è una dimenticanza da colmare, è un no scritto apposta — e D1, appena ieri, ha
ristretto quella decisione *alle ricette* lasciando la dispensa intera, emendando
`CLAUDE.md` e la spec madre §2 nello stesso giorno per dirlo. Questa voce chiede di
riaprirla dal lato che D1 aveva appena deciso di proteggere. Va quindi decisa qui,
per iscritto, prima di qualunque spec: se passa, `CLAUDE.md` e la spec madre §2 si
emendano di nuovo, **insieme**, come il riquadro impone.

**L'argomento a favore, che è più forte di quanto sembri.** Il motivo per cui la
regola esiste è la manutenzione giornaliera: è quella che fa abbandonare le app come
questa. Ma una quantità e una scadenza **non costano la stessa manutenzione**. Una
quantità va *mantenuta*: ogni volta che usi la cosa il numero è sbagliato finché non
lo correggi, e il giorno che smetti di correggerlo la dispensa mente. Una data di
scadenza si scrive **una volta sola**, quando il barattolo entra, e non si tocca mai
più — non è un valore che si consuma, è una proprietà di quel barattolo. È il tipo di
dato che il cursore di S2 aveva già mostrato accettabile: una cosa che si scrive
quando si è lì con l'oggetto in mano, e che poi vive da sola. E a differenza della
quantità, se la si lascia vuota non succede niente: chi non la scrive ha esattamente
la dispensa di prima.

**Le domande, e come sono state chiuse.** Non erano di forma: le prime due hanno
deciso che cosa si costruisce.

1. **Lo stato resta la sola verità?** `available` / `low` / `finished` è l'unica cosa
   su cui il resto dell'app ragiona — la disponibilità di un ingrediente, se una
   ricetta è cucinabile. Se la scadenza entrasse nel calcolo dello stato, una ricetta
   diventerebbe non cucinabile in silenzio, di notte, senza che nessuno abbia toccato
   niente. **La risposta che propongo è no**: il colore è un *segnale sulla riga*, non
   un quarto stato e non un ingresso in `status_for_fill`. Se invece la scadenza deve
   davvero togliere una cosa dalla disponibilità, è una decisione molto più grande di
   quel che la richiesta sembra, e va detta adesso.
2. **Il giallo è già occupato.** La zona gialla del cursore vuol già dire «comincia a
   mancare» (S2, `LOW_MAX_FILL = 30`). Se anche «sta per scadere» è giallo, due fatti
   diversi si contendono lo stesso colore, e una riga gialla smette di dire quale dei
   due. Serve un colore suo nel blocco `@theme` — e sopra 4.5:1 come ogni altro, che
   in questa app si legge in corsia alla luce del giorno.
3. **Dove sta il dato.** Sull'**elemento di dispensa**, non sull'ingrediente e non sul
   prodotto: scade *quel* barattolo, non «lo yogurt greco» e nemmeno «Fage Total 0%».
   Quindi `pantry_items.expires_on`, annullabile, una `DATE` e non un timestamp — la
   scadenza è un giorno, non un istante, e trattarla come un istante introduce un fuso
   orario in un dato che non ne ha. Vale per le mele sfuse come per il barattolo di
   marca: l'elemento di dispensa porta sempre un ingrediente e facoltativamente un
   prodotto, e la colonna sta sull'elemento.
4. **Chi sa che giorno è.** Il conto dei sette giorni lo fa il **server**, come ogni
   altra regola di dominio, e manda al client il fatto già deciso. Una sottrazione fra
   date fatta nel browser userebbe il fuso del telefono e comincerebbe a sbagliare di
   un giorno appena si viaggia — ed è esattamente la forma di «il frontend che calcola
   invece di chiedere» che tiene il porting a Capacitor un involucro e non un
   riscrittura. La soglia è una costante come `LOW_MAX_FILL`, e va difesa dal
   ricopiarla: `backend/tests/test_frontend_fill_zones.py` è il precedente — legge la
   soglia dal sorgente TypeScript e fallisce se i due linguaggi divergono.
5. **E il giorno dopo?** Scaduto è un terzo caso, non lo stesso di «sta per scadere»:
   serve un colore diverso, o la stessa cosa detta più forte? E soprattutto: una cosa
   scaduta torna in lista da sé, chiede come fa il cursore a zero («Lo rimetto in
   lista?»), o non fa niente? Chiedere è coerente con S2; fare da sé no.
   **Chiusa la metà che contava: resta.** Non torna in lista da sé e non chiede
   niente — la dispensa la mostra segnata, e basta. Resta da scegliere solo con
   quanta forza lo dice.
6. **Da dove arriva la data.** Da nessuna parte se non a mano: Open Food Facts
   descrive il *prodotto*, non la confezione che hai comprato, quindi non la sa e non
   può saperla. È sempre scrittura umana, il che rende il campo facoltativo non una
   cortesia ma l'unica forma possibile.

**Perché non l'alternativa.** Tenere il no intero sarebbe coerente e costerebbe poco
da difendere, ma rinuncia alla sola cosa che una dispensa sa fare e una lista no:
dirti che stai per buttare qualcosa. E metterla sull'ingrediente invece che
sull'elemento costerebbe meno schema ma sarebbe falsa al primo barattolo doppio.

↳ tocca S1 (l'ingresso in dispensa), S2 (la riga della dispensa e i suoi colori), S3
(l'ingresso diretto, che deve offrire le stesse strade dell'altro).

---

# Parte II — Spesa e dispensa

## S1. La X rossa **[FATTO 2026-09-17]**
«Togli dalla dispensa» è una X rossa. Il TBD sull'annulla era giustificato: l'annulla
c'è, dura sei secondi, e si appoggia ad `archived_at`, che era già reversibile prima
di questo lavoro. Al posto della voce resta una lapide («Tolta dalla dispensa —
Annulla»): la riga sta dov'era invece di sparire, perché una lapide senza posto non
si può annullare. Lato API è nato `unarchive_item`
(`backend/app/repositories/pantry.py`) e la `PATCH /api/v1/pantry/{id}` accetta
`{"archived": false}` oltre a `{"archived": true}`.

## S2. Lo slider a tre zone **[FATTO 2026-09-17]**
`o--o------o`: primo pallino rosso = finito, tratto giallo fino al secondo = quasi
finito, verde dopo = disponibile. Indicativo, e utile soprattutto **in negozio**, per
capire quanto ne resta di qualcosa; serve anche a seguire un prodotto che si consuma
ma non finisce mai.

**Il dominio non è cambiato quanto previsto: la regola primario/secondario in
`domain/rules.py` non si tocca**, ma è nata una seconda regola pura accanto a lei,
`status_for_fill`, con la soglia `LOW_MAX_FILL = 30` (di proposito sotto la metà: la
zona gialla deve dire «comincia a mancare», non «siamo a metà» — vedi il commento in
`app/domain/rules.py`). La posizione vive in `pantry_items.fill_percent`
(annullabile, 0–100, migrazione `0006`), la `PATCH` la accetta e risponde con lo
stato già ricavato dal server — il client chiede, non calcola, come ogni altra
regola di questo modulo. `backend/tests/test_frontend_fill_zones.py` legge la
stessa soglia dal sorgente TypeScript e fallisce se i due linguaggi divergono
(stesso schema di `test_frontend_categories.py`). Scrivere lo stato a mano (senza
passare dal cursore) azzera la posizione: un `available` deciso altrove non deve
mostrare un barattolo pieno che non c'è più. **`StatusToggle` è stato cancellato**:
il cursore lo sostituisce, e `StatusChip` è rimasto l'unico posto in dispensa dove
lo stato si vede.

**Il TBD era mal posto, e la frase sotto correggeva un'idea sbagliata, non un
buco**: chiedeva se il cursore a zero dovesse rimettere la voce in lista «come fa
oggi il passaggio a `finished`» — ma il passaggio a `finished` dalla dispensa
**non lo faceva, né prima né dopo questo lavoro**: `set_status` cambia solo lo
stato, e l'unico punto che scriveva in lista era `cook()`. Il cursore a zero segna
`finished` e **chiede**, con una lapide propria («Lo rimetto in lista?»): non
scrive in lista da sé. Per questo è nato `app/services/restock.py`, un solo posto
con due chiamanti — la cottura e il cursore — che non duplica una voce già in
lista, e la rotta `POST /api/v1/pantry/{item_id}/restock` che il cursore chiama
quando la risposta è sì.

**Dal 2026-09-17 la domanda arriva anche nel giallo, non solo a zero.** «Quasi
finito» è il momento in cui ricomprare è ancora in tempo; allo zero te ne accorgi in
cucina, non in corsia. Quali stati chiedano continua a dirlo il server — la riga in
`PantryRow.tsx` guarda lo `status` che torna dalla `PATCH`, e la soglia delle tre
zone non è ricopiata nel frontend — e i due stati sono scritti per esteso invece di
«diverso da disponibile», così un eventuale quarto stato dovrà essere deciso e non
ereditato per caso.

## S3. Ingresso diretto in dispensa, alla pari di «sistema la spesa» **[D]**
Oggi i due schermi non offrono le stesse strade. L'ingresso diretto deve dare tutte
quelle che dà l'altro: scegliere fra i prodotti già scansionati, scansionare un
codice a barre, **scansionare uno scontrino**, o inserire a mano.

↳ e da S7 anche il campo scadenza: `add_pantry_item` (`backend/app/repositories/pantry.py`)
accetta già `expires_on`, quindi all'ingresso diretto resta solo da mostrarlo.

↳ la scansione dello scontrino è la fase 2 della spec madre e **non esiste ancora**:
questa voce la tira dentro. Va deciso se la parità si fa subito senza scontrino e si
completa dopo, o se aspetta.

**Chiesto di nuovo da Mattia il 2026-09-27, e con un accento preciso: deve essere
*veloce*.** Oggi per mettere in dispensa qualcosa con il suo codice a barre bisogna
scriverlo in lista, spuntarlo e passare da «Sistema la spesa». In dispensa c'è solo
«Aggiungi in dispensa» (`PantryScreen.tsx`, un `IngredientPicker`): sceglie fra gli
ingredienti già in anagrafica, entra come disponibile e senza marca, non scansiona,
non crea un ingrediente nuovo, e quando fallisce dice «scrivilo in lista e sistemalo
da lì». Servono dalla dispensa, senza passare per la lista: **scansione** e
**inserimento a mano**, con la creazione di ingrediente e prodotto quando mancano. La
richiesta fa pendere la domanda qui sopra verso la parità subito, senza scontrino;
resta da confermare nella spec. Chi la scrive non deve copiare i pezzi di
`StockingScreen.tsx` (scanner, catalogo, `CustomProductForm`) in un secondo schermo:
vanno estratti e usati da entrambi, altrimenti le guardie di uno (il controllo
ingrediente/prodotto prima del 409, il codice che non sopravvive a una voce
diversa) mancheranno nell'altro. È la prima lezione di `CLAUDE.md`.

## S4. Valori nutrizionali molto più ampi **[FATTO IN PARTE 2026-09-24 — solo il livello prodotto]**
Oggi `products.nutrients` è un JSONB popolato da Open Food Facts, quindi già libero
nella forma ma povero nel contenuto. Spec:
`docs/superpowers/specs/2026-09-24-nutrienti-ampi-design.md`. **Scopo deciso e
costruito: solo il livello prodotto.** `backend/app/domain/nutrients.py` porta il
vocabolario canonico dell'intero Allegato XIII (Reg. UE 1169/2011: 35 campi con
etichetta, unità e VNR — i sette della parte B, le fibre, i ventisette della parte A),
e `COLLECTED_FIELDS` segna i dodici raccolti davvero oggi; `_NUTRIENT_MAP` in
`openfoodfacts.py` si è allargata di quattro chiavi — vitamina C, calcio, ferro,
potassio — e **converte dai grammi**, perché Open Food Facts scrive ogni `_100g` in
grammi qualunque unità mostri l'etichetta (misurato: il ferro dei Chocapic è `0.012`,
cioè 12 mg). La prima implementazione non lo faceva; corretta lo stesso giorno, prima
che un prodotto in produzione ne fosse toccato. **Nessuna
migrazione** (la colonna era già JSONB libero), **nessuno schermo nuovo**: non c'è
ancora un lettore prima di P2, e `CustomProductForm.tsx` continua solo a nominare in
italiano quel che trasporta senza chiederlo a mano
(`EXTRA_LABELS`). Il livello
ingrediente generico (CREA) e il tasto «Stima» con l'AI restano TBD, fuori da questa
spec — non hanno un'API/fonte pronta.

- **TODO (sottoagente) — fatto il 2026-09-24.** Macro: nessuna novità, sono già gli
  otto campi che `OpenFoodFactsClient._NUTRIENT_MAP`
  (`backend/app/services/openfoodfacts.py:17`) mappa oggi — kcal, proteine,
  carboidrati, zuccheri, grassi, saturi, fibre, sale. Micro: ventisette voci (13
  vitamine, 14 minerali), cioè l'**Allegato XIII, parte A del Regolamento UE
  1169/2011** (la parte B sono energia e macronutrienti) — la stessa normativa dell'etichetta nutrizionale italiana, che porta
  già con sé i VNR (valori di riferimento giornalieri) da usare per un futuro %VNR:
  niente da inventare. Esempio: Vit. C 80mg, Calcio 800mg, Ferro 14mg, Potassio
  2000mg, Vit. D 5µg. **Punto debole riportato dalla ricerca, non misurato da noi:**
  Open Food Facts espone i campi anche per i micronutrienti ma li popola raramente —
  meno del 20% dei prodotti avrebbe dati oltre sodio/sale, e per prodotti italiani generici sono quasi sempre assenti.
  Conferma perché il livello ingrediente-generico (CREA) non è ridondante. **CREA**: le
  tabelle esistono (~900 alimenti, 120 nutrienti, `alimentinutrizione.it`) ma **senza
  API né export ufficiale** — solo consultazione web, quindi popolarle richiede
  scraping mirato o inserimento progressivo, non un import in blocco; licenza non
  esplicitamente open, da trattare con cautela. **Raccomandazione per l'MVP:** estendere
  subito i campi già presenti con Vitamina C, Calcio, Ferro, Potassio (miglior
  copertura OFF, rilevanza più immediata), rimandando il resto dell'Allegato XIII a
  quando CREA sarà davvero integrato. Ogni campo assente resta `null`, mai `0`, coerente
  con la regola del progetto.
- **TBD strutturale:** i nutrienti servono su **due** livelli, non uno. Sul prodotto
  (esatti, di marca, da Open Food Facts) e sull'**ingrediente generico** (medi, dalle
  tabelle di composizione tipo CREA), perché le ricette puntano agli ingredienti e non
  ai prodotti. Sono due sorgenti con due affidabilità, e vanno distinte.
- **Tasto «Stima» [D]:** fa partire l'AI che, dall'oggetto e dai suoi ingredienti,
  propone tutti i valori. Terza provenienza, e va marcata come tale: una stima non
  deve mai sembrare una lettura d'etichetta.
- **TBD modello:** se Gemma basta, o serve un modello più forte, o l'accesso al web.
  OpenRouter offre una via per dare la ricerca web a un modello qualsiasi — **da
  verificare com'è fatta oggi e quanto costa**, prima di progettarci sopra.

↳ **il registro delle unità esiste già** (D1, tabella `units`): ogni parola vista in
una ricetta ci sta, con singolare e plurale decisi dall'AI, e `canonical_id` fa
puntare una variante alla sua forma canonica proprio per questo — così il peso della
coppia ingrediente×unità che S4 dovrà riempire un giorno si scrive una volta sola per
unità canonica, non una volta per ogni variante che il ricettario ha scritto
diversamente. L'attacco c'è; riempirlo non chiederà una migrazione.

## S5. Non alimentari in lista e dispensa **[FATTO 2026-09-18]**
Vedi D4: stessa lista, stessa dispensa, nessuna informazione nutrizionale — solo
la voce con il suo slider. Spec:
`docs/superpowers/specs/2026-09-17-non-alimentari-design.md`.

## S6. «Sistema la spesa» chiudeva l'unica porta che crea un ingrediente **[FATTO 2026-09-20]**
*Quel che segue descrive il difetto com'era; la correzione è in fondo alla voce.*

Il menù **Reparto** e il pulsante «Crea l'ingrediente «X»» comparivano solo se la
ricerca non trovava nulla (`frontend/src/features/stocking/StockingScreen.tsx`,
condizione `suggestions.length === 0`). Bastava **un** suggerimento qualsiasi, anche
assurdo, e la via d'uscita spariva: la voce a testo libero restava in lista e non
c'era modo di sistemarla.

Misurato in produzione il 2026-09-18 su «cera per pavimenti» — sette suggerimenti,
nessuno pertinente, soglia `SIMILARITY_FLOOR = 0.15` in
`backend/app/repositories/ingredients.py`:

| suggerimento | punteggio | chi lo tira dentro |
|---|---|---|
| Pera | 0.278 | alias *pere*, *pera abate* |
| Pane per hamburger | 0.167 | alias *panini per hamburger* |
| Polenta | 0.161 | alias *farina per polenta* |
| Mandarino | 0.160 | alias *clementine* |
| Spugne per i piatti | 0.156 | il nome |
| Detersivo per i piatti | 0.156 | alias *sapone per i piatti* |
| Pane | 0.156 | alias *pane per tramezzini* |

Agganciano tutti sul frammento `per` e su `era` di «p**era**»: più parole ha il
nome, più è probabile che qualcosa passi la soglia, e i nomi italiani composti
(`per`, `di`, `da`) sono il caso peggiore.

Non è un caso sfortunato. Provati sette nomi plausibili di prodotti per la casa
(`anticalcare`, `sturalavandini`, `lucidante pavimenti`, `lucido da scarpe`,
`spazzolone`, `cera pavimenti`, `cera per pavimenti`): **tutti** restituiscono
almeno un suggerimento, solo una parola senza senso (`xilofono`) arriva a zero. La
creazione è quindi **di fatto irraggiungibile**, e non esiste un aggiramento — il
pulsante crea col testo del campo, quindi svuotarlo per far sparire i suggerimenti
creerebbe un ingrediente col nome sbagliato.

Aggrava: `Sistema la spesa` è **l'unico posto dell'app che sa creare un
ingrediente** (`createIngredient` ha un solo chiamante), e la dispensa, quando il
suo selettore fallisce, manda proprio qui — «scrivilo in lista e sistemalo da lì».

**Radice.** La condizione codifica una premessa falsa, che il commento sopra di
essa dichiara ad alta voce: «una voce arriva qui proprio perché il suo testo non
somigliava a niente». Non è così: arriva qui perché in lista è stato scritto testo
libero **senza toccare un suggerimento**. «Non è stato scelto un ingrediente» è
stato confuso con «non esiste un ingrediente simile». È la quinta lezione di
`CLAUDE.md` — «mai un vicolo cieco» — violata da un `&&`.

**Non è una regressione del ramo `non-alimentari`:** quel lavoro ha solo sostituito
il reparto fisso «altro» col menù a tendina *dentro* una condizione che esisteva
già. Il non alimentare è però il primo caso in cui creare una voce nuova serviva
davvero, ed è così che è saltato fuori.

**Correzione applicata il 2026-09-20**, esattamente quella decisa: Reparto e «Crea
l'ingrediente «X»» compaiono **sempre** appena la ricerca ha risposto
(`showSuggestions && outcome !== "searching"`, in luogo del vecchio
`&& suggestions.length === 0`), sotto i suggerimenti e con peso visivo minore quando
ce ne sono — `buttonClasses("secondary")` invece di `"warn"`, cioè seconda scelta e
non via principale. La frase «Nessun ingrediente corrisponde» è rimasta al solo caso
vuoto, l'unico in cui è vera. `SIMILARITY_FLOOR` **non** è stato toccato: il problema
non stava nella ricerca.

Il test scritto per primo è quello che questa voce chiedeva — «con suggerimenti
presenti, il pulsante di creazione deve esserci» — ed è
`frontend/src/features/stocking/StockingScreen.test.tsx`, «la creazione resta
raggiungibile anche quando la ricerca trova qualcosa»: dà `Pera` come unico
suggerimento e pretende Reparto, creazione, e l'assenza della frase del caso vuoto.
Visto fallire prima della correzione (`Unable to find a label with the text of:
Reparto`), verde dopo.

**Verificato anche a schermo vero**, a 375px sullo stack `spena-e2e`, perché il peso
visivo e l'impaginazione non li vede jsdom: scritta «cera per pavimenti» in lista come
testo libero, la sistemazione mostra sei suggerimenti (`Pera`, `Pane per hamburger`,
`Polenta`, `Mandarino`, `Detersivo per i piatti`, `Spugne per i piatti` — gli stessi
della misura in produzione) **e sotto di essi** Reparto e il pulsante di creazione, che
su 375px sta su una riga sola. I nove controlli e2e esistenti restano verdi, e lo
stack è stato ricreato con `down -v` dopo il giro a mano, che lo sporca.

**Distribuito il 2026-09-20**, commit `8854ed7`, senza migrazioni: il pacchetto
servito da `spena.mattiagirellini.com` è lo stesso della build locale del codice
corretto.

## S7. La scadenza scritta all'ingresso, e la riga che avvisa **[FATTO 2026-09-21]** ↳ D5
La metà pratica di D5, costruita in undici task; la forma sta nella sua spec,
`docs/superpowers/specs/2026-09-21-scadenza-dispensa-design.md`. I tre pezzi, come
erano elencati qui:

- **all'ingresso**, in «Sistema la spesa», un «+ scadenza» che apre un
  `<input type="date">` nativo sulla riga — dietro un tocco e non sempre a video,
  perché quello schermo è già il più fitto dell'app e dieci campi vuoti sarebbero
  rumore permanente;
- **nella riga della dispensa**, una pastiglia accanto a `StatusChip` che porta la
  data: «Scade il 28/09/2026» prima, «Scadeva il 20/09/2026» dopo — due forme senza
  genere, perché «scaduto» e «scaduta» avrebbero sbagliato metà delle volte fra «Fage
  Total 0%» e «passata di pomodoro» — e toccandola si riapre il campo, anche per
  svuotarlo;
- **il colore a sette giorni**, deciso dal server: `EXPIRY_SOON_DAYS = 7` e
  `expiry_state` stanno in `backend/app/domain/rules.py` accanto a `status_for_fill` e
  **di proposito fuori di lui**, e il verdetto viaggia già preso dentro
  `PantryItemOut` (`expiry`: `"soon"` / `"expired"` / `null`). Il sette non attraversa
  il confine, quindi fra i due linguaggi non c'è niente da tenere allineato: è il modo
  più solido di passare il controllo che `test_frontend_fill_zones.py` fa per
  `LOW_MAX_FILL`, cioè non averne bisogno.

**Il dato.** `pantry_items.expires_on`, `DATE` annullabile, migrazione `0009`, **senza
`CHECK`**: una data già passata è legittima, perché capita di scriverla il giorno dopo
con il barattolo in mano. E il giorno di calendario è quello di `Europe/Rome`
(`PANTRY_TZ`), non di UTC: la data UTC non è il giorno di chi apre l'app a Milano a
mezzanotte e mezza.

**La PATCH riconosce il campo dalla presenza** — `"expires_on" in
payload.model_fields_set` — e non dal valore, perché `{"expires_on": null}` *è* il
comando «cancella la data». Scritta con `is not None`, come gli altri rami della
catena, la cancellazione sarebbe fallita con un 400 che dice che non c'era niente da
modificare.

**Il colore, che era la domanda lasciata all'occhio.** `--color-expiry: #5b45a8` con
`--color-expiry-tint: #efeaf9`: un viola, **l'unica tinta fredda** in una tavolozza di
verde, ambra e rosso, quindi si separa per famiglia di colore e non per chiarezza —
che è la separazione che regge anche in corsia e anche per chi confonde rosso e verde.
Contrasto misurato: **7,34:1** per il bianco sul viola, **6,22:1** per il viola sulla
sua tinta. **Guardato in un browser vero a 375px e lasciato com'era**: sulla stessa
riga X rossa, «Quasi finito» in ambra tenue e «Scadeva il 19/09/2026» in viola pieno
convivono senza un istante di ambiguità, e la coppia di pastiglie più lunga finisce a
263px su 375. Era la decisione che il piano lasciava all'occhio, e l'occhio ha detto
di sì: `index.css` non è stato toccato dopo.

**Le revisioni hanno trovato sette difetti** — due nei controlli per task, cinque in
quello sull'intero ramo. **Questi quattro sono del tipo che torna**, e i due gravi li
ha visti solo la revisione finale, perché nessuno dei due è visibile da dentro un task
solo.

Il primo è **la quinta lezione di `CLAUDE.md` daccapo**: in «Sistema la spesa» un campo
data *svuotato* mandava `""` invece di `null`, Pydantic rispondeva 422, e il messaggio
diceva «riprova» — ma riprovare rimandava lo stesso corpo. La spesa intera restava
bloccata, e l'unica uscita era ricaricare la pagina perdendo ogni abbinamento già
risolto. Il vicolo cieco l'ha aperto la funzione nuova, non un'omissione. Serviva
vedere il frontend e lo schema Pydantic nello stesso sguardo.

Il secondo è che **`input[type="date"]` emette un evento a ogni tasto**: scrivendo
`2027` sopra `2026` passa da `0002-`, `0020-`, `0202-`, e il campo si chiudeva al
primo, salvando l'anno 2 e smontandosi sotto le dita. Nessun test poteva vederlo,
perché `fill()` di Playwright imposta il valore in un colpo solo: è la quarta lezione
(«un selettore CSS non è una superficie di test») spostata sugli eventi. Ora si scrive
uscendo dal campo — campo non controllato, `autoFocus`, e Invio che conferma passando
dal blur — provato con tasti veri in un browser. **Resta da provare sul telefono**: il
selettore data nativo di Android non è quello di Chromium desktop, e come chiuda il
campo lo dice solo l'uso vero.

Gli altri due sono più piccoli, e li hanno presi i controlli per task. `formatExpiry`
costruiva `new Date("2026-09-28")`, che JavaScript legge come mezzanotte **UTC**: ogni
lettore a ovest di Greenwich avrebbe visto il giorno prima. Ora la data si costruisce
dai suoi componenti, un test la fissa, ed è stato visto fallire rimettendo il vecchio
codice sotto `TZ=America/New_York`. E il «+ scadenza» è nato **62×16 px**, contro il
bersaglio da 44px che `frontend/e2e/style.spec.ts` difendeva già su altri tre comandi:
corretto allargando il bersaglio e non il disegno — padding più un margine negativo
uguale — così le due righe restano alte quanto prima (misurato: **152px** in dispensa
e **177px** in «Sistema la spesa», prima e dopo), e `style.spec.ts` ha una quarta
misura d'altezza perché non possa tornare invisibile.

E una cosa che la riga **non** fa: togliere. Lo stato resta la sola verità, quindi
niente sparisce e niente diventa non cucinabile da sé (D5, domanda 1). Non riordina la
dispensa per scadenza, non chiede «Lo rimetto in lista?» — quella domanda nasce da un
gesto sul cursore, mentre una scadenza arriva da sola — e non manda notifiche, che
sarebbero l'unica forma di manutenzione giornaliera che D5 non ha accettato.

Vuoto resta il caso normale e quasi non costa niente: chi non scrive mai una data ha
la dispensa di prima, salvo il «+ scadenza» discreto dove starebbe la pastiglia. È un
costo dichiarato e non una svista: senza di lui la correzione non avrebbe da dove
cominciare, e sarebbe il vicolo cieco appena evitato.

Suite alla fine del lavoro: **644 backend, 292 jsdom, 12 e2e**, tutte verdi.
`CLAUDE.md` (decisione fondante 1) e la spec madre §2 sono stati emendati **insieme e
nello stesso commit**, come D5 imponeva. **In produzione dal 2026-09-22**, migrazione
`0009` applicata; **verifica a mano fatta il 2026-09-23, passata** (vedi «Stato di
oggi»): il selettore data di Android chiude il campo come serviva, che era l'unico
punto rimasto all'uso vero.

## Dall'uso vero, 2026-09-27

Le voci da S8 a S15 le ha portate Mattia dopo qualche giorno di spesa e dispensa
vere. Lo stato di oggi è stato controllato sul codice il giorno stesso. Nessuna ha
ancora una spec. L'ordine proposto è in Parte VIII.

## S8. Il codice a barre scansionato deve restare legato a quel che si crea a mano **[FATTO 2026-09-27]**

> **Fatto il 2026-09-27**, sul ramo `dispensa-difetti`. I due buchi erano quelli
> descritti sotto, e la causa comune era una: la schermata non ricordava per voce il
> codice appena letto, che viveva solo in `creatingFor` e nello stato della ricerca,
> azzerato a ogni apertura dello scanner. Ora `StockingScreen.tsx` tiene
> `unlinkedCode` per voce: si scrive quando la lettura non trova un prodotto (o
> fallisce), si cancella quando trova un prodotto qualunque, anche di un altro
> ingrediente — quel codice non deve seguire la voce, porterebbe solo un 409 o un
> furto. «Crea il prodotto a mano» dal catalogo lo passa al modulo; scegliere a
> catalogo un prodotto lo manda nella conferma come `barcode` della voce. Lo sfuso
> no.
>
> Lato server il codice viaggia **dentro la conferma già tutto-o-niente**
> (`POST /shopping-list/stock`, campo facoltativo `barcode` di `StockEntryIn`) e non
> in una rotta nuova: `give_barcode_if_missing` (`backend/app/repositories/products.py`)
> lo dà al prodotto scelto **solo se il prodotto non ne ha uno e il codice non è già
> di un altro**, e non solleva mai. Non riscrive un codice esistente — quello è un
> legame da correggere, S9 — e non lo ruba a un altro prodotto; in quei casi la voce
> entra in dispensa lo stesso e il legame semplicemente non si fa, senza che la
> schermata lo dica (la risposta resta `{"created": n}`: la schermata se ne va subito,
> e dirlo non costava poco). Nessuna migrazione: `products.barcode` era già
> annullabile e unico. Quattro test sul server e quattro sulla schermata, uno per
> uscita, scritti prima. **S3 deve riusare `give_barcode_if_missing`.**
>
> Resta vero, e non toccato: `openCatalog` non chiude un `CustomProductForm` aperto,
> quindi i due pannelli possono stare aperti insieme. È materia di S10.
>
> **Da provare sul telefono**: (1) codice ignoto → chiudere il modulo → «Cerca a
> catalogo» → «Crea il prodotto a mano» → salvare, e riscansionando lo trova; (2)
> codice ignoto → chiudere il modulo → scegliere a catalogo un prodotto senza codice →
> «Metti in dispensa», e riscansionando lo trova; (3) un prodotto che ha già un codice,
> scelto dopo averne letto un altro, tiene il suo.
Quando si scansiona un codice che né il catalogo né Open Food Facts conoscono e poi
si inserisce il prodotto a mano, quel codice deve restare associato al prodotto
creato. La prossima volta la scansione lo deve trovare.

**Com'è oggi.** La via diretta lo fa già: con un codice sconosciuto, o una lettura
fallita, `StockingScreen.tsx` apre `CustomProductForm` con il codice
(`creatingFor.barcode`), e il modulo lo manda a `POST /products`. Il caso del burro
(S9) dimostra che almeno una volta è stato salvato. **Ma non tutte le uscite lo
portano con sé**:
- dal pannello del catalogo, «Crea il prodotto a mano» chiama `createByHand(item, "")`,
  cioè senza codice, anche se un attimo prima era stato letto;
- confermare la voce come sfusa dopo un codice sconosciuto perde il codice. Lì è
  giusto, perché non c'è un prodotto a cui legarlo;
- scegliere dal catalogo un prodotto esistente **senza** codice non gli aggiunge quello
  appena letto. Oggi non c'è modo di dare un codice a un prodotto che non ce l'ha.

**Cosa fare.** Prima capire con Mattia quale strada ha preso quando il codice non è
rimasto. Poi fare in modo che il codice letto segua ogni uscita che crea o sceglie un
prodotto: il catalogo e la creazione a mano dal catalogo; lo sfuso no. Scrivere prima
il test di ciascuna uscita. Vale anche per l'ingresso diretto in dispensa (S3), che
deve usare gli stessi pezzi.

## S9. Correggere quel che è stato registrato male **[D, con TBD sulla forma]**
Mattia ha legato per sbaglio il codice a barre di un parmigiano a «burro», e non c'è
modo di sistemarlo dall'app. *(Quel parmigiano è stato sistemato a mano in produzione
il 2026-09-27: prodotto `ace228d2…` e il suo unico elemento di dispensa spostati da
«burro» a «parmigiano», in una transazione con la guardia sull'ingrediente di
partenza. S9 resta aperta per il caso generale.)* **Il problema è generale: un errore
di registrazione resta per sempre.** Verificato sul codice: le rotte di `ingredients.py` e
`products.py` creano e basta, nessuna `PATCH` e nessuna `DELETE`. Oggi dall'app non
si può:
- **su un prodotto**: cambiare l'ingrediente sotto cui sta, il nome, la marca, o
  togliere o spostare il codice a barre;
- **su un ingrediente**: cambiare il reparto, e quindi `kind` (un ingrediente creato
  nel reparto sbagliato ci resta), cambiare il nome, o unirlo a un doppione.

Mai un vicolo cieco (quinta lezione di `CLAUDE.md`) vale anche per gli errori di chi
usa l'app, non solo per quelli della rete.

**Da dove partire.** La logica esiste già per la riga di comando:
`app.cli.fix_registry` sa fare `merge`, `recategorize` e `rename` sugli ingredienti,
con le guardie giuste. Per esempio, il reparto non alimentare è rifiutato se
l'ingrediente ha righe di ricetta. Lo schermo deve chiamare gli stessi servizi,
spostati fuori dal comando, e non una seconda copia. Sui prodotti non c'è ancora
niente: servono la modifica e la rimozione del codice. Una rimozione non deve rompere
gli elementi di dispensa che puntano al prodotto (`pantry_items.product_id`).

**TBD**: dove vive la correzione. Proposta: dalla riga della dispensa (tocco sul nome
→ scheda dell'elemento con prodotto e ingrediente modificabili) e da una pagina
«Anagrafica» nell'hamburger (T1) per ingredienti e prodotti che non sono in dispensa.

**Il caso concreto resta sbagliato in produzione** finché la voce non c'è. Se Mattia
vuole, si corregge prima a mano sul database, dicendo quale prodotto spostare. Nessuno
l'ha ancora fatto.

## S10. «Sistema la spesa»: lo scanner e il modulo si aprono in fondo, fuori vista **[D]**
Con molte voci, ognuna con le sue tre opzioni, premere «scansiona» su una voce in alto
apre lo scanner **in fondo alla pagina**, dove non si vede. Lo stesso succede al
pannello del catalogo e a `CustomProductForm`: in `StockingScreen.tsx` sono tutti
disegnati dopo la lista. **Richiesta di Mattia**: quando si scansiona, si cerca a
catalogo o si crea un prodotto per una voce, le altre voci si nascondono per quel
momento, e ricompaiono quando si conferma o si annulla. Le risoluzioni già fatte
restano dove sono: sono indicizzate per voce e non dipendono da cosa è a video. Va
verificato a 375 px in un browser vero, perché jsdom non vede dove finisce un
pannello.

**Il giro di T3 aggiunge tre dettagli**, verificati sul codice:
- **il pannello del codice non dice per quale voce è aperto.** Il nome sta solo nel
  testo per lo screen reader del pulsante che lo apre, mentre il catalogo e il modulo
  lo scrivono nel titolo. Arrivati in fondo, non si sa più cosa si stava scansionando;
- **il codice scritto a mano si cerca solo con Invio.** Manca un pulsante «Cerca», e il
  campo non ha `inputMode="numeric"`, quindi escono tredici cifre sulla tastiera delle
  lettere;
- **senza fotocamera il pannello promette «Puoi inserire il prodotto a mano»** e non
  offre quella strada: c'è solo il campo del codice, con «Annulla» in mezzo.

## S11. Cercare in dispensa **[D]**
Per sapere se c'è il sale oggi bisogna scorrere tutta la dispensa. Serve un campo che
filtri le righe mentre si scrive. **TBD**: se è lo stesso campo di «Aggiungi in
dispensa» (scrivo «sale»: se c'è mi mostra la riga, se non c'è mi offre di
aggiungerlo) o un campo a parte. Il primo è più veloce, ma un campo che fa due cose
deve dire chiaramente quale sta facendo. Con i reparti chiusi (S15) una ricerca apre
quelli che contengono un risultato.

## S12. Le righe della dispensa sono tutte uguali **[TBD — brainstorming]**
Serve un modo di riconoscere una riga senza leggerla. Le strade proposte da Mattia
sono una foto per tipo, un'icona o un'emoji per reparto o per ingrediente, un fondo,
un SVG. Cosa c'è già e cosa costa:
- **per reparto** (una ventina, lista chiusa): icona o emoji decise una volta, a mano.
  È la via più economica;
- **per ingrediente** (884): un'emoji decisa dall'AI una volta sola, sotto il tetto di
  1 $/giorno, con la stessa verifica e lo stesso undo delle altre decisioni dell'AI.
  Molti ingredienti non hanno un'emoji giusta, quindi serve un ripiego (quella del
  reparto);
- **per prodotto**: `products.image_url` c'è già per quelli da Open Food Facts. Gli
  altri non l'hanno, e sarebbe solo una parte delle righe.

Vincoli: un fondo colorato passa dal blocco `@theme`, con il contrasto sopra 4.5:1, e
non deve confondersi con i colori che vogliono già dire qualcosa (le zone del cursore,
il viola della scadenza). Da decidere insieme alla revisione di T3.

## S13. Il cursore della dispensa si sposta mentre si scorre **[FATTO 2026-09-27 — manca la prova sul telefono]**

> **Fatto il 2026-09-27**, sul ramo `dispensa-difetti`. `FillSlider.tsx` resta un
> `<input type="range">` — ruolo, nome, valore letto a voce e frecce della tastiera
> sono i suoi, e la tastiera scrive come prima, al rilascio del tasto o all'uscita —
> ma con `pointer-events-none`: il trascinamento nativo non esiste più, e i gesti li
> legge il contenitore. Un gesto è un tocco se il dito, dall'appoggio al sollievo, non
> si è mai allontanato più di **10px** (il tragitto, non solo l'arrivo; Android usa 8dp
> per la stessa distinzione); il valore è quello del punto in cui il dito si è
> **posato**, sul passo di 5. Un `pointercancel` (il browser che si prende lo
> scorrimento), un secondo dito o il mouse che esce annullano il gesto. Il contenitore
> è `touch-manipulation` e non `pan-y`: lo scorrimento passa alla pagina, e lo zoom a
> due dita resta a chi ne ha bisogno. Il mouse segue la stessa regola: un clic sposta,
> un trascinamento no.
>
> Provato in Chromium con emulazione di un telefono e tocchi veri (375×812): prima
> uno scorrimento verticale partito su un cursore lo portava da 70 a 20, ora la pagina
> scorre e il valore resta, zero scritture; un trascinamento orizzontale non cambia
> niente; un tocco a 20 scrive una volta. `e2e/non-alimentari.spec.ts` usava
> `fill("0")` più un `pointerup` finto, che il cursore nuovo ignora giustamente: ora
> tocca il contenitore a sinistra. **Quel file non è stato fatto girare**, vuole lo
> stack e2e.
>
> **Sul telefono vero, da Mattia**: uno scorrimento che parte da un cursore scorre e
> non cambia mai uno stato; un tocco lo cambia; lo zoom a due dita partito da un
> cursore funziona; 10px di tolleranza si sentono giusti per un tocco svelto.
Scorrendo la dispensa col dito, se il tocco parte sopra un cursore il valore cambia, e
con lui lo stato: una voce può diventare «quasi finita» o «finita» senza che nessuno
l'abbia voluto. È un dato sbagliato scritto in silenzio. `FillSlider.tsx` è un
`<input type="range">` nativo: il valore segue ogni `onChange` durante il
trascinamento e si salva al `pointerup`. **Richiesta di Mattia**: il cursore cambia
solo con un tocco, dove il dito si appoggia e si solleva nello stesso punto, e non con
un trascinamento. Lo scorrimento verticale deve passare alla pagina (`touch-action`).
La tastiera deve continuare a funzionare. Si prova **solo sul telefono vero**, come il
selettore data di S7: nessun test in jsdom e nessun `fill()` di Playwright riproduce un
dito che scorre.

## S14. Cibo e casa separati in dispensa **[D]**
Oggi cibo e non alimentari stanno nella stessa dispensa. Serve un modo per vedere solo
il cibo o solo le cose di casa, per esempio un selettore «Tutto / Cibo / Casa» in cima.
`ingredients.kind` esiste già (D4), quindi il modello non cambia. Va però esposto:
`PantryItemOut` porta `ingredient_category` ma non il `kind`. Il frontend non deve
ricavarlo dal reparto, perché sarebbe una seconda copia di `kind_for_category`: il
server aggiunge `ingredient_kind`, oppure filtra lui. Il selettore
ricordato fra una visita e l'altra è una comodità per dispositivo, quindi
`localStorage` basta.

## S15. Reparti della dispensa collassabili **[D]**
`PantryScreen.tsx` raggruppa per reparto (`groupByCategory`) con un titolo per gruppo.
I titoli diventano apribili e chiudibili, così la dispensa si naviga per reparto.
Anche qui lo stato ricordato è una comodità per dispositivo. Due cose da non
sbagliare: una ricerca (S11) apre i reparti con un risultato, e un reparto chiuso deve
dire quante voci contiene, altrimenti chiuso sembra vuoto.

## S16. La lista scorre di lato quando una voce porta la nota del rientro **[D, difetto, dal giro di T3]**
Una voce tornata dalla cottura porta la nota «rientrata perché finita cucinando». A
375 px, quella voce allarga la pagina a 394 px: tutta la lista si sposta di lato, e la
X di quella voce resta mezza fuori dallo schermo.

**La causa.** In `ShoppingListScreen.tsx` la riga è una sola linea `flex`. La nota è
`shrink-0` e non va a capo. Il nome è `flex-1` ma senza `min-w-0`, quindi non si
stringe sotto la sua parola più lunga. Casella, nome, nota e X fanno circa 385 px in
una scheda da 343 px, e `Card` non taglia quel che esce.

**Cosa fare.** Mettere la nota su una seconda riga sotto il nome, oppure togliere
`shrink-0` e dare `min-w-0` alle due parti. In `e2e/style.spec.ts` va aggiunto un
controllo `scrollWidth <= clientWidth` su ogni schermata: jsdom non lo vede.

## S17. In lista si spunta solo sulla casella da 20×20 **[D, difetto, dal giro di T3]**
In corsia, spuntare è il gesto che si fa di più, e oggi lo prende solo la casella.
Toccare il nome non fa niente. Il nome è uno `<span>` nudo, e la casella ha solo un
`aria-label`, senza un `<label>` intorno (`ShoppingListScreen.tsx`).

**Cosa fare.** Mettere casella e nome dentro un `<label>` alto almeno 44 px. La X resta
un bersaglio a parte.

## S18. «latte» + Invio crea una voce libera accanto al «latte» vero **[FATTO 2026-09-27]**

> **Fatto:** la prima strada, nel backend. `add_item`
> (`backend/app/repositories/shopping.py`), quando il client non manda un
> ingrediente, prova `exact_ingredient` (`backend/app/services/ingredient_match.py`):
> la sola metà esatta di `match_name`, stessa normalizzazione (spazi attorno e
> maiuscole, niente accenti: non c'è un normalizzatore che li tolga, e i nomi si
> scrivono già così) e stessa precedenza — il nome canonico decide per primo, poi gli
> alias. Mai trigram: l'aggancio è silenzioso, e un «latt» agganciato a latte
> sposterebbe la voce di reparto senza che nessuno lo abbia chiesto. Una differenza
> voluta da `match_name`: un alias che sta su due ingredienti non sceglie, e la voce
> resta libera, abbinabile dopo come prima. I non alimentari si agganciano come il
> resto: il filtro `kind=food` è delle ricette, non della lista.
>
> Il doppione: con un ingrediente, agganciato o mandato dal tocco sul suggerimento,
> se ce n'è già una voce da comprare o nel carrello non se ne scrive una seconda. La
> `POST /shopping-list` risponde con la voce che c'era, **200 invece di 201** e
> `added: false` — lo stesso `added` di `RestockOut`, nella nuova
> `ShoppingItemAddOut`. «Che cosa è già in lista» sta ora in un posto solo,
> `active_item_for`, che anche `already_in_list` del rientro dalla dispensa usa. Il
> testo libero non si confronta con niente: senza ingrediente non c'è un'identità su
> cui dire «è la stessa cosa». Nel campo (`AddItemField.tsx`) la risposta diventa
> «Era già in lista.», con le parole e il tono grigio della dispensa, `role="status"`;
> il campo si svuota e l'avviso se ne va appena si scrive altro. Nessuna spec e2e
> scriveva in lista col tasto Invio, quindi nessuna è cambiata.
Si scrive «latte» nel campo della lista, e il primo suggerimento è proprio «Latte». Se
si preme Invio o «Aggiungi», la voce entra come testo libero sotto «Senza reparto», e
in lista compaiono due latte. Poi la sistemazione chiede di abbinarla.

**La causa.** `AddItemField.tsx` chiama sempre `add(trimmed, undefined)`: solo il tocco
su un suggerimento lega un ingrediente. Nemmeno il backend prova: `add_item` salva
l'`ingredient_id` così come arriva, e `match_name` lo usano ricette e import ma non la
lista.

**Cosa fare.** Due strade:
- quando il testo coincide con il nome o con un alias, senza badare alle maiuscole,
  agganciare quell'ingrediente;
- se no, evidenziare il primo suggerimento e far scegliere quello a Invio.

La prima è più robusta se sta nel backend, perché vale anche per il Capacitor. Nello
stesso passaggio si può evitare il doppione di un ingrediente già in lista, rispondendo
come fa già la dispensa con «Era già in lista.».

## S19. «Sistema la spesa» perde l'abbinamento fatto, e il doppione dà l'errore sbagliato **[FATTO 2026-09-27]**
Una voce a testo libero viene abbinata a un ingrediente, o gliene viene creato uno. Se
quella voce non entra nella spesa di oggi, al ritorno chiede di nuovo l'abbinamento, e
in lista resta sotto «Senza reparto». Riprovare a creare lo stesso ingrediente risponde
«Forse esiste già con un altro nome», ma esiste con lo stesso nome ed è il primo
suggerimento.

**La causa.** L'abbinamento vive solo nello stato React di `StockingScreen.tsx`
(`matchedIngredient`), fino a «Metti in dispensa». Il backend scrive `ingredient_id`
sulla voce solo per le voci sistemate (`repositories/shopping.py`). Un 409 della
creazione, «ingrediente già presente», finisce nello stesso messaggio di ogni altro
fallimento.

**Cosa fare.**
- Appena si sceglie o si crea l'ingrediente, scriverlo sulla voce con
  `patchShoppingItem(id, {ingredient_id})`: la rotta c'è già, e `patch_item` lo
  accetta.
- Dare al 409 un messaggio suo, «C'è già: sceglilo qui sopra», oppure agganciare
  direttamente l'ingrediente omonimo.

**Fatto:** l'ingrediente scelto o creato si scrive sulla voce nel momento stesso, con
`patchShoppingItem(id, {ingredient_id})`, e la lista in cache si rilegge, così la voce
torna nel suo reparto anche se oggi non entra in dispensa. Il match locale resta: se
la scrittura fallisce, accanto alla voce compare «Non sono riuscito a ricordare
l'abbinamento in lista…» con «Riprova», e la voce si sistema lo stesso. Il doppione
non ha un messaggio suo, si aggancia: il 409 di `POST /ingredients` porta
l'ingrediente omonimo in `existing` (cercato con la stessa normalizzazione della
creazione, `canonical_name` in `repositories/ingredients.py`), `detail` resta la
stringa di sempre, e lo schermo lo aggancia come fosse stato scelto. `ApiError`
porta ora il corpo intero in `body`. Ogni altro fallimento tiene il messaggio di prima.

## S20. Un prodotto di Open Food Facts di tutt'altro tipo entra sotto l'ingrediente della voce **[FATTO 2026-09-27]**
Sulla voce «pomodoro» si legge il codice degli Spaghetti Barilla. Il modulo si apre
come «Nuovo prodotto per «pomodoro»», precompilato con nome, marca e valori, e «Salva»
è verde pieno. Con un tocco, gli spaghetti diventano per sempre un prodotto di
pomodoro, e le ricette al pomodoro diventano cucinabili con la pasta. È la stessa classe
d'errore del parmigiano sotto «burro» (S9).

**La causa.** La guardia «è di un altro ingrediente» (`StockingScreen.tsx`) guarda solo
i prodotti già nel nostro catalogo. Quando il codice è nuovo, i dati di Open Food Facts
riempiono il modulo per l'ingrediente della voce, e niente confronta le due cose.

**Cosa fare.** Mostrare in grande la domanda: «È un «pomodoro»?», con il nome di Open
Food Facts accanto. «Salva» diventa secondario, e compare «No, è un'altra cosa», che
riporta ai tre pulsanti. Il confronto testuale fra nome e ingrediente, se si vuole, sta
nel backend, perché è logica di dominio.

Due cose piccole dallo stesso modulo:
- **il nome segnaposto.** Un codice che Open Food Facts conosce senza nome propone
  «Prodotto 2000000000017» come se fosse un valore vero. Meglio un campo vuoto e
  obbligatorio.
- **il modulo non dice cosa è successo.** Non si legge se il codice è stato trovato o
  no, né quale codice verrà legato.

Un codice come `1234` passa senza controllo: la cifra di controllo EAN/UPC si può
verificare prima di chiedere.

**Fatto:** un codice nuovo al catalogo che Open Food Facts conosce apre prima la
domanda, in grande: «È un «pomodoro»?», con accanto «Su Open Food Facts è «Spaghetti
n.5», di Barilla.». «Sì» porta al modulo di sempre; «No, è un'altra cosa» torna ai
pulsanti della voce senza salvare niente, e il codice non segue la voce verso il
catalogo. Nessun confronto testuale, né qui né nel backend: la domanda si fa sempre,
perché un confronto che a volte tace è peggio di un tocco in più. La guardia «è di un
altro ingrediente» per i codici già nostri è rimasta com'era.
- Il nome segnaposto non c'è più: `OffProduct.name` e `ProductSuggestion.name` sono
  `None` quando Open Food Facts non lo conosce, il campo parte vuoto, e «Salva
  prodotto» resta spento con sotto «Scrivi il nome del prodotto per salvarlo.».
- Il modulo dice cosa è successo — «Trovato su Open Food Facts…», «Non trovato su
  Open Food Facts…» o, se il lookup è fallito, «Non ho potuto cercare il codice…» —
  e quale codice lega: «Il codice … verrà legato a questo prodotto.», oppure
  «Nessun codice a barre verrà legato…».
- La cifra di controllo sta in `backend/app/domain/barcodes.py`
  (`has_valid_check_digit`, GTIN-8/12/13/14, test a tabella) e arriva come
  `valid_checksum` nella risposta di `GET /products/barcode/{code}`, che non respinge
  niente. Un codice nuovo che non torna si ferma nel pannello del codice con «Questo
  codice non torna: ricontrollalo.», il codice resta nel campo da correggere, e «Usa
  questo codice lo stesso» va avanti: i codici interni di negozio esistono. Un codice
  che non torna ma è già nel nostro catalogo si aggancia senza avviso. Il
  `2000000000017` citato qui sopra, per inciso, non torna.

L'aspetto — la domanda davvero «in grande» su un telefono, l'avviso nel pannello — non
l'ha visto nessun test: va guardato in un browser vero.

## S21. L'ordine delle righe della dispensa cambia fra un caricamento e l'altro **[FATTO 2026-09-27]**
Dentro un reparto, le voci entrate con la stessa spesa si scambiano di posto da un
caricamento all'altro, e la riga che si stava per toccare non è più lì.

**La causa.** `added_at` è `server_default=func.now()`, e in Postgres `now()` è l'ora
d'inizio della transazione. Una spesa si salva con un commit solo, quindi tutte le sue
voci hanno lo stesso `added_at`. La query ordina per `added_at desc` senza un secondo
criterio (`repositories/pantry.py`). Il frontend ordina i reparti ma dentro tiene
l'ordine del server.

**Cosa fare.** Aggiungere un secondo criterio stabile, per esempio
`.order_by(added_at.desc(), PantryItem.id)`, oppure il nome. Da decidere con S12: se a
video convenga l'alfabetico dentro il reparto.

**Fatto:** `list_pantry` ordina per `added_at desc, id`. L'id non è un ordine che
qualcuno legge: serve solo a non pareggiare mai, così le voci della stessa spesa
restano ferme fra un caricamento e l'altro. È l'unica query che elenca la dispensa per
mostrarla — il foglio della cottura legge la stessa `GET /pantry`, quindi vale anche
lì. Il test (`test_le_voci_della_stessa_spesa_restano_nello_stesso_ordine`) inserisce
otto voci nello stesso commit con gli id in ordine inverso e rilegge tre volte: prima
della correzione Postgres restituiva l'ordine d'inserimento. L'alfabetico dentro il
reparto resta una domanda di S12, non di qui: se S12 lo sceglie, cambia il primo
criterio e l'id resta in coda come spareggio.

---

# Parte III — Ricette

## R1. La foto dentro la ricetta **[FATTO 2026-09-17]**
La foto si vede anche nella scheda aperta, non solo nell'elenco. Il ramo
dell'immagine rotta — il difetto già corretto una volta (`6a2175b`) — ora sta in un
componente solo, `RecipeImage` (`frontend/src/features/recipes/RecipeImage.tsx`),
usato da entrambe le schermate: una seconda copia di quella logica si sarebbe
scollata esattamente lì, dove nessuno guarda.

## R2. Riporziona **[FATTO IN PARTE 2026-09-20: la metà per porzioni]** ↳ D1
Due modi, e il secondo è quello che manca a tutte le app: per **numero di porzioni**,
e per **quantità assoluta di un ingrediente** — «la ricetta è per 400 g di pasta, io
ne faccio 150 g», indipendentemente dalle porzioni.

**Il primo è fatto e in produzione dal 2026-09-20**, dentro D1: `GET
/api/v1/recipes/{id}?servings=N` riscala le righe parsate, con lo stepper delle
porzioni da schermo; una riga non parsata resta identica e si vede come tale, invece
di scalare o contare per zero, e la riga di copertura dice quante sono — contate
**sulle dosi, non sugli ingredienti**, perché una riga che non ha mai avuto una dose
non è una dose che non si riscala.

**Resta il secondo modo**, ancorato a un ingrediente invece che alle porzioni, e
implica scegliere quell'ingrediente prima di poter scalare. TBD, invariato dalla
proposta originale: se anche questo riporziona è solo una vista o si può salvare.

## R3. Filtra per ingrediente **[FATTO 2026-09-17, rifatto lo stesso giorno]**
«Contiene questi ingredienti» — `GET /api/v1/recipes/search?ingredient_id=…&ingredient_id=…`.
Il parametro **si ripete, e ogni ripetizione stringe**: un `EXISTS` per ciascuno, in
AND. Con l'OR il secondo tocco allargherebbe l'elenco, cioè farebbe il contrario di
quel che il gesto promette. Il campo è quello dell'anagrafica, con il suo
autocomplete, e **resta a video anche a filtro acceso**: gli ingredienti scelti si
sommano e stanno sotto come pastiglie, ciascuna con la sua X (bersaglio da 44px,
difeso in `frontend/e2e/style.spec.ts` perché una X piccola la vede solo un browser).
Lo stesso ingrediente scelto due volte resta uno.

**Il ruolo non entra più, e prima entrava.** La prima stesura guardava i soli
primari, e la ragione era buona per la domanda di allora: il filtro si chiamava
«cosa hai in casa», cioè «ho questo, cosa ci faccio», e lì un secondario non
caratterizza il piatto — col sale avrebbe risposto «tutto», che non è una risposta.
La domanda di oggi è un'altra e si combina: chi vuole restringere aggiunge il secondo
ingrediente, e nascondergli una ricetta che quell'ingrediente ce l'ha davvero sarebbe
una risposta sbagliata, non una prudenza. **La regola primario/secondario resta
intera dove serve**, cioè nel decidere se una ricetta si può cucinare
(`domain/rules.py`): questo filtro non la tocca.

Filtrato in SQL **prima** del limite **nel ramo senza parole cercate** (sesta lezione
di `CLAUDE.md`: un filtro che lavora sul risultato non può stare dietro a un limite).
Con una ricerca testuale, invece, il filtro si applica **dopo** la piscina dei
candidati della fusione RRF (`CANDIDATE_POOL` per graduatoria): comportamento
accettabile, perché lì le parole cercate sono già un ordinamento e la domanda è sul
risultato della ricerca — ma è una scelta, non un fatto provato, e nessun test ha più
ricette pertinenti della piscina. Il filtro al plurale stringe più di quello singolo,
quindi il caso è semmai meno frequente di prima. Il limite è dichiarato nel commento
accanto al filtro in `backend/app/services/recipe_search.py`. Il selettore vive nel
ricettario. Non ha richiesto niente di nuovo nel modello.

Il nome del parametro **resta al singolare** perché è il nome di ogni ripetizione, e
questo ha un secondo effetto utile: una copia vecchia del frontend, servita dal
service worker dalla sua cache, ne manda ancora uno solo e continua a filtrare bene,
invece di vedersi ignorare il parametro e mostrare il ricettario intero sotto
l'etichetta di un filtro acceso.

## R4. Via le ricette di semina, e l'import completo di GialloZafferano **[FATTO 2026-09-24, in produzione]**
L'obiettivo è tutto il catalogo. La strategia di partenza era «prima uno scarico
locale completo, poi la messa online e il parsing a ondate»: nata per lo storage, che
non è più un problema, e sostituita dal brainstorming del 2026-09-24 con un comando che
svuota la sitemap direttamente sul server.

> **Eseguita il 2026-09-24**, seguendo `docs/import-gz-runbook.md` passo per passo.
> Deploy di `343d117` verificato sul pacchetto servito (`index-CUXgt-G-.js`, diverso
> da quello di prima) e con alembic a `0010 (head)`; backup
> `~/spena-prima-di-r4-2026-09-24.sql.gz` (126 kB, 13 tabelle su 13) — **si può
> cancellare dopo qualche giorno**; cancellate le 26 ricette di semina.
>
> - **Tempo**: `import_gz --tutto` dalle 15:29 alle 20:15 UTC, 4 ore e 46 minuti,
>   senza una fermata. Circa 450 pagine ogni quarto d'ora.
> - **Pagine**: la sitemap ne aveva 8.469, 40 già importate; delle 8.429 nuove,
>   **8.410 prese e 19 scartate**, tutte con lo stesso motivo: «nessuna riga
>   dd.gz-ingredient nella pagina». In `recipe_imports`: 8.135 `imported`,
>   315 `pending`, 19 `skipped`.
> - **Ricette**: **8.136** (le 8.135 importate più una scritta a mano), con 79.833
>   righe d'ingrediente, di cui 49.058 (61 %) con una dose strutturata.
> - **Termini**: 1.563 abbinati dall'AI e 12 ignorati dall'AI, 247 abbinati da sé,
>   24 a mano (tutti di prima), **56 ancora in coda**. Sono loro a trattenere le 315
>   pagine `pending`: si decidono da «Ingredienti da abbinare» in cima al ricettario,
>   e le ricette entrano da sé. I più frequenti: Stracciatella (50 righe), Farina di
>   mais fioretto (33), Cioccolato al latte (30), Filetto di manzo (24), Carne di
>   suino (20). L'anagrafica è arrivata a 935 ingredienti.
> - **Unità**: 70 parole nuove, decise da `decide_units` in cinque giri (dodici per
>   giro, 0 risposte rifiutate). Non tutte sono unità: vedi Parte X, «36 mesi».
> - **Costo**: **0,66 $** in tutto, dentro il limite di credito di 1 $ messo sulla
>   chiave per l'occasione. `term_decision` 1.562 chiamate per 0,656 $,
>   `term_collapse` 155 per 0,005 $, `unit_forms` 10 per 0,0007 $. Il limite non è
>   mai scattato, e l'AI non è mai stata lasciata stare.
> - **Spazio**: il database è passato da 10 MB a **72 MB**, meno della metà dei 150
>   stimati; disco a 42 GB su 75, 30 liberi.
> - **La ricerca sulle ricette vere**, lo script di §7 del runbook in tre giri: a
>   caldo **92–244 ms** per ogni caso (ricettario intero, `offset` 3000, soglia 0 e 3,
>   «pasta» con e senza soglia). La prima chiamata di un processo nuovo costa
>   390–448 ms. Sopra i 73–143 ms delle 8.500 ricette sintetiche, sotto i 300 ms per
>   i quali il runbook chiedeva un `EXPLAIN ANALYZE`.
> - **La verifica a schermo sul telefono** (§7.5 del runbook) **resta da fare** a
>   Mattia: vuole il login, e una sessione di Claude non scrive password.

> **La revisione dell'anagrafica, 2026-09-27.** Dei 56 termini in coda Mattia ne ha
> decisi 21 a mano; gli altri 35 li ha decisi una sessione di Claude, e la stessa
> sessione ha riletto tutte le 952 voci. Circa il 3 % delle 1.563 decisioni dell'AI era
> sbagliato in modo che si vede: «lampascioni» sotto «lampone disidratato», «oro
> alimentare» sotto bottarga, «primosale» sotto sale, «ostia» sotto ostrica, «berberè»
> sotto birra, «codette colorate» sotto pasta. Più grave per l'uso erano i **doppioni**, perché danno
> falsi «manca»: la piadina in dispensa e la piadella nelle ricette (con «Piadine»
> collegato alla tortilla), grana padano (603 righe) accanto al parmigiano, 30 formati
> di pasta creati a parte invece che come alias di «pasta», vini e confetture per nome.
> Tre decisioni prese a mano erano sviste (fagioli rossi → fagiolo nero, pepe verde →
> pepe nero, risoni → riso), altre due scelte da rivedere (stracciatella → stracchino,
> carne di suino → macinato di manzo).
>
> - **Come**: `app.cli.fix_registry` con il piano `data/fixes/2026-09-27-anagrafica.json`,
>   provato prima su una copia locale del database di produzione e poi in produzione
>   senza `--conferma`. Backup `~/spena-prima-di-anagrafica-2026-09-27.sql.gz` (16 MB,
>   13 tabelle su 13) — **si può cancellare dopo qualche giorno**; il resoconto passo
>   per passo è in `~/fix-registry-2026-09-27.log` sul server.
> - **Numeri**: 229 passi, 2.351 ricette rimesse in attesa e 2.408 rifatte dalla pagina
>   scaricata, 0 scartate; 0 termini in coda; ricette da 8.394 a **8.451**, ingredienti
>   da 952 a **884**, nessun alias su due ingredienti. Nessuna ricetta persa, nessun
>   costo cambiato (confrontati uno per uno), dosi strutturate al 61 % come prima.
> - **Decisioni di Mattia** (2026-09-27): grana e parmigiano **uniti** («Parmigiano o
>   grana», 1.527 righe); il pomodoro **diviso in quattro** — fresco (253 righe),
>   passata-polpa-pelati (584, è la «polpa di pomodoro» che era in dispensa), concentrato
>   (205), pomodori secchi (130); vini col nome del vitigno in vino rosso/bianco,
>   confetture per gusto in marmellata, mandorle pelate e granella in mandorle, yogurt
>   bianco in yogurt, fagioli bianchi in cannellini.
> - **Lasciati com'erano, di proposito**: accorpamenti larghi ma non sbagliati per la
>   cucinabilità — guanciale sotto pancetta, maggiorana sotto origano, filetto sotto
>   controfiletto, alette sotto coscia di pollo, «formaggio» generico sotto formaggio
>   fuso, «manzo» generico sotto macinato di manzo, latte vegetale sotto latte. E la
>   `soppressa` in dispensa accanto alla `soppressata` di una ricetta: sono due salumi
>   diversi. Chi li vuole cambiare scrive un piano nuovo in `data/fixes/`.
> - **Una correzione al codice, trovata strada facendo**: annullare una decisione
>   rifaceva le ricette dal `payload` e perdeva il costo scelto a mano dal dettaglio
>   (R9). Ora l'annullamento lo scrive nel `payload` prima di cancellare la ricetta.

> **Costruita il 2026-09-24.** Il codice è entrato in `master` e su `origin` quel
> giorno. Deploy, cancellazione delle ricette di semina e lancio
> dell'import sono in **`docs/import-gz-runbook.md`**, scritto per la sessione che li
> farà. Spec: `docs/superpowers/specs/2026-09-24-import-completo-design.md`;
> piano: `docs/superpowers/plans/2026-09-24-import-completo.md`.
>
> Cosa c'è: il seme carica le ricette solo con `--con-ricette` (in produzione un seme
> rilanciato non rimette quelle di semina); `python -m app.cli.drop_seed_recipes`, che
> senza `--conferma` elenca e basta; `import_gz --tutto`, che legge la sitemap una
> volta e va a lotti da 50 allineando, decidendo e materializzando dopo ognuno, con i
> termini già chiesti esclusi dal giro e l'AI lasciata stare dopo due giri senza una
> decisione; «Mostra altre» nel ricettario. Tre risposte di Mattia nel brainstorming:
> via **tutte** le ricette di semina, il tetto di spesa resta **un limite di credito su
> OpenRouter** e non codice, e il ricettario si sfoglia con **«Mostra altre»**.
>
> **E la cosa che nessuno aveva chiesto, trovata misurando.** Su 8.500 ricette
> sintetiche la ricerca con una soglia («Ora / +1 / +2 / +3») andava **in errore**:
> `availability_map` riceveva un id per riga, duplicati compresi, oltre i 32.767
> parametri di asyncpg — già intorno alle 3.300 ricette, cioè a metà dell'import. Dove
> passava, dentro una categoria, costava un secondo. È la sesta lezione di `CLAUDE.md`,
> e il commento nel codice la prevedeva. Ora `rules.py` decide quali ingredienti della
> dispensa soddisfano ciascun ruolo e SQL conta le righe fuori da quegli insiemi,
> filtra, ordina per `(mancanti, titolo, id)` e pagina: **73–143 ms** in ogni caso, e
> un test a tabella lega il conteggio SQL alla regola. Senza parole cercate il
> ricettario non è più la piscina delle cento più recenti ma il ricettario intero.
> Verificato anche a schermo, a 375 px: «Mostra altre» è alto 44 px, porta la pagina
> dopo senza doppioni e sparisce alla fine.
>
> Suite alla fine del lavoro: 726 backend, 313 jsdom, typecheck pulito. Gli e2e non
> sono girati: lo stack `spena-e2e` vuole un `.env` nella radice, che in questa
> macchina non c'è e che Claude non crea.

> **Vincolo di storage tolto il 2026-09-24.** Era «massimo ~100 ricette totali finché
> i volumi Docker non stanno su uno storage esterno più capiente». Il dimensionamento
> sotto mostra che non era più giustificato dai numeri: l'intero catalogo pesa
> centinaia di MB, non i GB per cui il vincolo era nato prudenzialmente. Resta invece
> attivo, e vale per questa voce come per ogni altra, il **tetto di spesa 1$/giorno su
> OpenRouter** (Parte XI), che qui morde davvero: `import_gz` fa decidere all'LLM i
> termini sconosciuti di ogni lotto (`MAX_TERMS_PER_RUN`), quindi un catalogo intero
> sono migliaia di termini e va misurato contro quel tetto prima di partire.

**Dimensionamento del 2026-09-24, misurato in produzione.** La sitemap che `import_gz`
legge già, `https://ricette.giallozafferano.it/sitemap/ricette.xml`, elenca **8.469
ricette** (contate il 2026-09-24; una prima stima di un sottoagente diceva che una
sitemap di ricette non esisteva, ed era sbagliata). Sul database vero, con 67 ricette e
40 pagine importate, `recipes` pesa 376 kB, `recipe_ingredients` 288 kB e
`recipe_imports` 296 kB: circa **17 KB per ricetta importata**, pagina d'import
compresa — che è il payload già analizzato, ~2 KB, non l'HTML. Tutto il catalogo fa
quindi **circa 150 MB**. **Le immagini non vengono scaricate**, resta solo l'URL
(`recipe.image_url`), ed è il fattore che tiene basso il conto. Gli embedding in
produzione non ci sono (`INSTALL_EMBEDDINGS=0`, 0 vettori su 67); accesi,
aggiungerebbero pochi KB a ricetta. Il server ha **75 GB di disco, 31 liberi** (più
17,6 GB di immagini Docker e 7,2 GB di cache di build recuperabili): nessuno storage
esterno serve.

Il tempo invece conta: con una pagina ogni `DELAY_SECONDS = 1.2` secondi, 8.469
pagine sono almeno tre ore di sole pause, e `--limit` vale 50 per lotto. Il
`robots.txt` della fonte vieta `Claude-Web` e `anthropic-ai`; l'import non è quei
crawler e lo dichiara nel suo `User-Agent` (`SpenaPersonalArchive/1.0`), decisione già
presa in §3 della spec dell'import.

## R5. Sostituisci ingrediente **[D, con TBD pesante]**
Dentro la ricetta, accanto a ogni ingrediente, un tasto «Sostituisci». Tre esiti, e
sono tre cose diverse:
1. **uno o più sostituti** (pollo → tacchino);
2. **si può omettere** — una spezia il cui sapore non si emula ma che non rompe il
   piatto;
3. **insostituibile** — la farina nel pane.

**Precalcolato**, non chiesto all'AI ogni volta: finito l'import avremo un'anagrafica
molto ampia, e si fa girare il calcolo una volta e si salva.

TBD grosso, da affrontare prima della spec: quante coppie sono, quanto costano con il
tetto di 1$/giorno, se la sostituibilità dipende dalla ricetta o solo dalla coppia di
ingredienti (il burro nella besciamella non è il burro nei biscotti), e come si
corregge una risposta sbagliata.
↳ R4 (serve l'anagrafica ampia) — **fatta il 2026-09-24**: l'anagrafica ha 935
ingredienti, e R5 non aspetta più niente se non la sua spec.

## R6. Filtra per ricette cucinabili **con sostituti** **[D]** ↳ R5
Oggi si filtra per «cucinabile». Serve anche «cucinabile usando quel che ho al posto
di quel che manca».

«Cucinabile» adesso è un gradino di una scala, non una casella: quando R6 arriverà,
«cucinabile con sostituti» va pensata come una seconda scala o come un interruttore
accanto a questa, non come una casella in più.

## R7. Cerca ricette con al massimo *n* ingredienti mancanti **[FATTO 2026-09-21]**
Due usi in uno: «tanto devo andare a fare la spesa, ammetto 3 cose da comprare», e
**svuotafrigo** — parto dagli avanzi e allargo di poco la scelta.

La casella «Solo quelle che posso cucinare» non c'è più: è diventata il gradino zero
di una scala a cinque — Tutte, Ora, +1, +2, +3 — dove «Tutte» è l'assenza di soglia e
non una soglia altissima, perché è il server a distinguere le due cose. E la scheda
elenca i nomi di quel che manca invece del solo numero (i primi tre, poi «e un
altro»): «mancano 3 ingredienti» non basta a decidere se vale la spesa.

La sesta lezione di `CLAUDE.md` è stata presa in parola: il limite della piscina cade
per **qualunque** soglia, zero compreso — anche «cosa posso cucinare adesso» filtra
sul risultato, e prima stava dietro alle cento ricette più recenti. Il ramo con le
parole cercate resta dietro alla piscina RRF, come già dichiarato in R3. Il gradino
scelto si distingue dagli altri solo per il CSS, quindi la prova sta dove il CSS
esiste davvero: `frontend/e2e/style.spec.ts` misura fondo e contrasto in un browser.

**In produzione dal 2026-09-22, non dal 21.** Il commit era sceso sul server il giorno
del merge, ma l'immagine è stata ricostruita solo con il deploy di S7: fino ad allora
il browser riceveva il pacchetto di prima. Nessuna migrazione, quindi niente da
applicare; la verifica a mano del 2026-09-23 vale anche per questa voce ed è passata.

## R8. Modifica con AI **[D]**
Dentro una ricetta aperta, un tasto «Modifica con AI» con un prompt libero
(«sostituisci lo zucchero con dolcificante», che obbliga a ribilanciare il resto).
**Il salvataggio crea una ricetta nuova**, non tocca l'originale.

TBD: se la nuova ricetta tiene un legame con quella da cui nasce, e se si vede.

## R9. Il costo della ricetta **[FATTO 2026-09-24, in produzione]**
Ogni ricetta ha un costo da 1 a 5, disegnato come cinque `€` di cui i primi *n* neri
e gli altri grigio chiaro: `€€€··` è una ricetta da 3. È un **livello**, non una
cifra in euro — la stessa scelta della decisione fondante 1 sulle quantità, per la
stessa ragione: un prezzo vero andrebbe tenuto aggiornato e comincerebbe a mentire il
giorno in cui si smette. Spec: `docs/superpowers/specs/2026-09-24-costo-ricetta-design.md`.

**Com'è fatto.** `recipes.cost`, annullabile, con un CHECK sulla scala (migrazione
`0010`): una ricetta senza costo non è una ricetta da 1. Si sceglie toccando i `€`
nel dettaglio (ritoccare quello scelto lo toglie), con `PATCH /recipes/{id}`; nel
modulo «Scrivi una ricetta» la bozza AI lo propone nella stessa chiamata, e a mano
si sceglie uguale. Nessun filtro né ordinamento per costo: chi lo leggerà è P3.

**La fonte.** GialloZafferano scrive «Costo: …» fuori dal JSON-LD, e l'import ora lo
legge: **R4 lo troverà fatto**, senza rifare niente. Due cose viste sulle pagine vere
il 2026-09-24: le parole sono cinque come i nostri gradini, ma **non concordano nel
genere** — «Elevato» sul filetto, «Molto elevata» sul risotto al tartufo — quindi il
parser legge per radice; e qualunque parola diversa è nessun costo, mai un gradino
indovinato.

**Fatto al deploy, il 2026-09-24:** la migrazione `0010` si è applicata all'avvio,
`python -m app.cli.reread_costs` ha girato una volta (31 costi scritti, 9 pagine senza
costo, 0 sparite dalla fonte). La verifica a mano sul telefono — che il grigio dei
gradini spenti si veda alla luce del giorno e non si confonda col nero — è dichiarata
fatta; `e2e/style.spec.ts` misura i due colori, non come li legge un occhio in corsia.

## R10. Una ricetta salvata non si corregge né si cancella **[D, difetto, dal giro di T3]**
Una ricetta scritta a mano o dalla bozza AI resta per sempre com'è: un refuso nel
titolo, un ingrediente dimenticato, una ricetta di prova. È lo stesso principio di S9,
applicato alle ricette. Non esiste una `DELETE`, e la `PATCH /recipes/{id}` cambia solo
`cost`.

**Cosa fare.** Serve una decisione prima del codice:
- una ricetta già cucinata ha `cooking_events` che la nominano;
- una ricetta importata si rilegge dalla fonte, e una modifica a mano verrebbe
  sovrascritta.

La proposta: «Modifica» riapre lo stesso modulo di «Scrivi una ricetta», precompilato,
solo per le ricette scritte qui. «Elimina» archivia, con la lapide, invece di
cancellare.

## R11. Le decisioni prese a mano nella coda non si annullano dall'app **[D, dal giro di T3]**
In «Ingredienti da abbinare», una decisione dell'AI ha il suo «Annulla» sotto «Deciso
dall'AI». Una decisione presa a mano sparisce dalla schermata, eppure si sbaglia
altrettanto.

**Il backend c'è già.** `GET /imports/terms` accetta `decided_by=human`, e l'annulla
funziona per qualunque termine deciso. È `ImportQueueScreen.tsx` che chiede solo
`fetchImportTerms("ai")`.

**Cosa fare.** Chiedere anche `human` e mostrarle con lo stesso `DecidedTermRow`, sotto
«Decisioni recenti» con un'etichetta «AI» / «tu», oppure in una seconda sezione.

---

# Parte IV — Pasti (sezione primaria nuova) ↳ D1, D2, D3

## P1. Creazione di un pasto **[D]**
Si sceglie il tipo — Colazione, Pranzo, Merenda, Cena, Spuntino — e l'app mostra
ricette adatte **senza nascondere il resto**: a colazione la bistecca non sta fra i
primi risultati, ma l'elenco completo resta raggiungibile. Si scelgono più ricette, o
se ne inserisce una nuova, o **si fotografa un piatto per la stima calorica**.

TBD: la stima da foto è un pezzo suo, con la stessa domanda sul modello di S4.

## P2. NutriScore **[D, con TBD]**
Per il periodo scelto — pasto, giorno, settimana — confronta quel che si doveva
mangiare con quel che si è mangiato, e dà un punteggio.

- i fabbisogni vengono da **peso, altezza e il resto**, che vanno inseriti da qualche
  parte: serve una **sezione Profilo** (proposta: nell'hamburger);
- il punteggio è 100 se tutto torna, e cala **in modo non lineare**: 500 calorie in
  più o in meno su una settimana devono restare 100. **TBD: la funzione.** È la scelta
  che decide se il punteggio è utile o se diventa un numero che si ignora dopo tre
  giorni;
- con «i nutrienti mancanti restano mancanti», un punteggio calcolato su dati parziali
  deve dire di esserlo.

↳ P1 per i dati mangiati, S4 per i nutrienti, D1 per le quantità.

## P3. Pianificare più giorni **[D in parte il 2026-09-24, con TBD]** ↳ P1, P2, M1, R9
Nella sezione Pasti, oltre al pasto singolo, si pianifica un periodo — una settimana,
o più.

Il giro, come l'ha descritto Mattia il 2026-09-24:
1. si segnano i pasti **già decisi** — una cena fuori, un pranzo dai genitori — che il
   piano non deve riempire;
2. si dice **quanti pasti al giorno** si vogliono fare;
3. si dà un **budget di costo** per il periodo, con un margine accettabile;
4. il programma sceglie le ricette guardando nutrienti (↳ P2, S4), budget (↳ R9) e,
   come M1, la dispensa.

Il budget è una somma di livelli: ogni ricetta scelta sottrae tanti `€` quanti ne
porta. Nella prima formulazione era «ideale 30 €, con margine di 10 €» — dove però
«€» non sono euro ma gradini di costo, e la forma confondeva. Il brainstorming del
2026-09-24 l'ha chiusa così.

**Deciso il 2026-09-24:**
- **conta solo la media, mai il singolo piatto.** Nessun tetto per pasto: una
  bistecca `€€€€€` ci sta, purché gli altri pasti la bilancino. Il budget si esprime
  come **costo medio per pasto** sul periodo — con lo stesso simbolo delle ricette,
  e quindi valido uguale su tre giorni o su dieci, con o senza cene fuori — e il
  programma ne ricava il totale da spendere;
- **si sceglie con dei profili** — «risparmio / normale / mi concedo» o simili, nomi
  e valori da fissare nella spec — che dietro diventano una media ideale e un
  margine sopra. Il margine è a senso unico: spendere meno dell'ideale non è mai un
  errore;
- **avanzi: un pasto «Altro» che non sottrae niente.** Se domani pranzo con l'avanzo
  di stasera, è perché stasera ho cucinato di più: il costo è già stato contato
  nel pasto in cui si è cucinato, e contarlo di nuovo sarebbe sbagliato. Niente
  logica di porzioni e avanzi nel piano, almeno all'inizio: «Altro» è un posto
  riservato, come una cena fuori;
- **i pasti fuori non pesano sul budget**: il budget è quello della spesa;
- **la somma dei livelli resta lineare, per ora.** `€€€€` non costa davvero il doppio
  di `€€`, e lo sappiamo: è un'approssimazione dichiarata, da riprendere dopo (pesi
  non lineari per gradino) se il piano risulta sbilanciato nei fatti;
- **i nutrienti aspettano P2 e S4** (sotto).

**Ancora aperto:**
- nomi e valori dei profili, e se si può anche scegliere una media a mano;
- cosa fa il piano quando budget e nutrienti non stanno insieme: rispetta il tetto e
  lo dice, mai un «impossibile» secco (Mai un vicolo cieco);
- il piano finito **chiude l'anello**: quel che manca per le ricette scelte va in
  lista della spesa, come oggi va quel che finisce cucinando.

**Cosa si può fare prima di P2 e S4.** I nutrienti per ricetta non esistono ancora:
un primo piano può guardare solo budget, pasti al giorno, dispensa e varietà, e
imparare i nutrienti quando arrivano — come P2 senza H2 impara l'attività dopo.
**Deciso il 2026-09-24: si aspetta.** P3 non parte prima di P2 e S4; la versione
senza nutrienti resta scritta qui come ripiego, non come piano.

---

# Parte V — Motori

## M1. Motore di suggerimento ricette **[TBD]** ↳ P2, S4
Chiamato ogni volta che l'app propone ricette. Tiene conto di:
- tipo di pasto;
- calorie e nutrienti già mangiati, **sia sull'ultimo giorno che sull'ultima
  settimana** — se oggi ho mangiato pochi carboidrati ma nella settimana tanti, non
  deve spingermi comunque sui carboidrati;
- disponibilità in dispensa (c'è già, `recipe_search.py`);
- sostituibilità (↳ R5), stagionalità, ripetizione recente: **da decidere insieme**.

È l'ultimo pezzo in ordine di dipendenze: ha bisogno che esistano i pasti, i nutrienti
e i sostituti. Brainstorming suo, a valle di tutto.

---

# Parte VI — Sezioni secondarie (hamburger)

## H1. Expense Tracker **[TBD]** ↳ T2
Spesa totale su OpenRouter nel periodo scelto, con una torta di come si divide.

**Dipendenza sciolta il 2026-09-17:** T2 è fatto, quindi `llm_calls` sta già
accumulando una riga per chiamata con sezione e costo reale. Lo storico parte da quel
giorno: prima non c'è niente da dividere, e non ci sarà mai.

TBD: brainstorming su cosa mostrare. La materia prima è `llm_calls` (costo per
sezione, per giorno, riusciti e falliti); `python -m app.cli.llm_prices` stampa invece
i prezzi di listino per provider, che è un'altra cosa e serve semmai a scegliere il
modello.

## H2. Connettore Samsung Health **[TBD]**
Serve a Pasti: l'attività fisica cambia il fabbisogno, e inserirla a mano non si fa.

**TODO (sottoagente):** verificare se esiste una via praticabile. L'SDK ufficiale
chiede di diventare partner e non conviene; da capire se ci sono strade alternative
davvero utilizzabili. **Finché non c'è una risposta, il fabbisogno calorico di P2 non
può dipendere dall'attività**: va progettato per funzionare senza, e migliorare se
arriva.

## H3. Profilo **[D]** ↳ P2
Peso, altezza, e quel che serve ai fabbisogni. Nasce perché P2 lo richiede.

---

# Parte VII — Trasversali

## T1. Navigazione **[FATTO IN PARTE 2026-09-17]**
- **Header globale** «Spena», `AppHeader.tsx`: il TBD sul logo si è chiuso disegnando
  il segno a mano, in SVG dentro il componente stesso (una pentola col vapore, solo
  tratti, `currentColor`) — niente libreria di icone per un marchio solo.
- **Tasto indietro** dentro le sottosezioni: `BackLink.tsx`, e `Screen`
  (`frontend/src/components/ui/Screen.tsx`) accetta una prop `back` che dichiara la
  destinazione, così il tasto non torna mai a un posto indovinato.
- **Schede d'ingresso sempre presenti**: `SectionEntryCard.tsx`, con un pallino di
  avviso e un fondo diverso solo quando c'è davvero qualcosa da fare. Il caso «non ho
  spesa da mettere a posto» non fa sparire il tasto.

**Resta aperto l'hamburger**, e non è una dimenticanza: è rinviato di proposito alla
prima sezione secondaria vera (Pasti, Spese, Profilo, Connettori). Un indice che
ripete le tre schede della navbar non è un indice — costruirlo ora avrebbe significato
disegnare un menu che porta esattamente dove portano già Lista, Dispensa e Ricette.

## T2. Attribuzione delle chiamate su OpenRouter **[FATTO 2026-09-17]**
Fatto e in produzione (merge `b7b842f`). Com'è finita, perché non è come era scritta
qui sopra:

**La richiesta originale non era costruibile.** Per OpenRouter un'app *è* un
indirizzo: `HTTP-Referer` è l'identificatore, `X-Title` cambia solo il nome
visualizzato e da solo non crea nessuna app. Mandare un titolo diverso per sezione
avrebbe prodotto **una sola app con il nome che sfarfalla**, non cinque voci di spesa.

**Quel che è stato costruito invece:** la divisione per sezione la teniamo noi, nella
tabella `llm_calls` — una riga per chiamata con `call_site`, modello, `generation_id`,
token e **il costo che OpenRouter dichiara in `usage.cost` nella risposta stessa**.
Non è una stima: è la cifra addebitata, e la buttavamo via da mesi leggendo solo
`choices[0].message.content`. I fallimenti si registrano con `ok = false` e costo
`NULL` (non zero: di una richiesta rifiutata non sappiamo se ci è stata addebitata) —
un modello giù è spesa sprecata, ed è il giro che paga e non conclude che una torta
delle spese esiste per scoprire.

`call_site` è oggi `TERM_DECISION`, `TERM_COLLAPSE`, `RECIPE_DRAFT` e — dal 2026-09-20,
con D1 — `UNIT_FORMS`. Ogni punto di
chiamata nuovo ne aggiunge uno: `complete_json` lo pretende come argomento
obbligatorio, e `tests/test_llm_spend_is_recorded.py` legge i sorgenti e fallisce se un
modulo chiama l'LLM senza registrare. Serve perché la dimenticanza qui non rompe
niente e non si vede: si vede mesi dopo, come un conto che sembra giusto e sottostima.

**`OPENROUTER_APP_URL` è valorizzata nel `.env` del server** dal 2026-09-17
(`https://spena.mattiagirellini.com`): da qui in avanti la colonna «App» nei loro log
smette di essere «Unknown». Resta da guardare, alla prossima azione AI, che compaia
davvero.

↳ H1 ora è sbloccata: da oggi lo storico si può dividere.

## T3. Revisione di UI e UX, a partire da un giro del sito fatto da un sottoagente **[D, chiesto da Mattia il 2026-09-27 — il giro è fatto, la spec no]**
Oltre alle voci puntuali di S8–S15 serve una revisione dell'interfaccia. L'esempio di
Mattia: **pulsanti con icone al posto di testo cliccabile**, a cominciare dalla
scansione del codice a barre. Prima di progettarla, però, serve sapere tutto quel che
c'è da rivedere, non solo quel che è saltato all'occhio finora.

**Il primo passo è un sottoagente, su Opus.** Naviga il sito con una checklist di
pagine da guardare e menù da aprire, e si annota man mano tutto quel che è ambiguo,
brutto o migliorabile. Il risultato torna in questo file come voci nuove, e solo dopo
si scrive la spec della revisione. La checklist di partenza, da allargare se il giro
trova altro:
- **Accesso**: la schermata di login e il suo errore;
- **Lista**: il campo di aggiunta con i suggerimenti, una voce a testo libero, la
  spunta, lo svuotamento;
- **Sistema la spesa**: ciascuna delle tre opzioni per voce, lo scanner (anche
  dove la fotocamera non c'è), il codice scritto a mano, il catalogo, il modulo del
  prodotto nuovo precompilato e vuoto, il prodotto di un altro ingrediente, la creazione
  dell'ingrediente con il reparto, l'errore della sistemazione;
- **Dispensa**: «Aggiungi in dispensa», il cursore e le sue tre zone, la X e la
  lapide con l'annulla, «Lo rimetto in lista?», il «+ scadenza» e le due pastiglie,
  i gruppi per reparto, la dispensa vuota;
- **Ricette**: la ricerca, la scala «Tutte / Ora / +1 / +2 / +3», il filtro per
  ingredienti con le pastiglie, le schede con i mancanti, «Mostra altre», la
  voce d'ingresso «Ingredienti da abbinare»;
- **Dettaglio ricetta**: la foto, lo stepper delle porzioni con la riga di
  copertura, il costo in `€`, il foglio della cottura con «Rimetti in lista»;
- **Scrivi una ricetta e bozza AI**: il modulo, le righe escluse (vedi la voce
  «non in anagrafica» in Parte X), il salvataggio;
- **Ingredienti da abbinare**: la coda (vuota oggi: serve un seme con termini in
  coda), «Deciso dall'AI», l'annullamento con il suo riquadro;
- **In tutto il sito**: header, tabbar, tasto indietro, schede d'ingresso, stati
  vuoti, di caricamento e d'errore, bersagli sotto i 44 px, testi che vanno a capo
  male.

Ogni osservazione va annotata con la schermata, cosa si vede (con uno screenshot), e
perché è un problema: ambiguo, brutto, scomodo, incoerente con un'altra schermata. Va
aggiunta anche una proposta, e un peso da «da fare» a «gusto». Il giro si fa **a
375 px**, la larghezza per cui l'app è pensata, e poi una volta in larghezza desktop.

**Dove gira.** Una sessione di Claude non scrive la password vera, quindi due strade:
lo stack locale `spena-e2e` con la password finta di `.env.e2e` e il seme
`--con-ricette`, che è la strada preferita perché lì il giro può anche scrivere; oppure
la produzione, dopo che Mattia ha fatto l'accesso nel browser dell'app, **solo
guardando**, senza sistemare spese né cucinare. Attenzione alla nota di R4: lo stack
e2e vuole un `.env` nella radice, che Claude non crea. La coda «Ingredienti da
abbinare» e le ricette vere si vedono bene solo con i dati di produzione.

**Da decidere nella spec, non adesso**: T1 ha disegnato a mano il marchio in SVG
proprio per non portare una libreria di icone per un segno solo. Con un'icona per
ogni azione e forse una per reparto (S12), una libreria piccola e ad albero (per
esempio `lucide-react`) può diventare la scelta giusta. Un'icona senza testo deve
comunque avere il suo `aria-label`, e restare riconoscibile in corsia.

### Esito del giro **[FATTO 2026-09-27]**
Il giro è stato fatto sullo stack `spena-e2e` caricato con una copia dei dati di
produzione, poi distrutto. La password era quella finta, e il giro ha potuto anche
scrivere. È passato a 375 px con il tocco emulato, poi a 1280 px e con
`prefers-color-scheme: dark`. **99 osservazioni**: 11 difetti, 17 da fare, 32 che
confondono, 7 brutte, 32 di gusto.

- **I difetti** sono stati ricontrollati sul codice e hanno ora una voce loro. Sono
  S16–S21 in Parte II, R10 e R11 in Parte III, T4 qui sotto, e uno in Parte X. S10 ha
  ricevuto tre dettagli nuovi.
- **Il resto** è elencato qui sotto, una riga per osservazione, ed è il materiale della
  spec di T3.
- **Il rapporto completo**, con gli screenshot, non è in git: mostra la dispensa vera e
  il repo è pubblico.

Il giro non ha potuto vedere:
- la tastiera del telefono che copre i campi;
- un codice a barre riconosciuto dalla fotocamera vera;
- il selettore data nativo;
- la ricerca semantica e la stesura AI vera, perché nello stack mancano gli embedding e
  la chiave;
- iOS e uno screen reader vero.

Queste restano per il telefono.

**Da non riprogettare via**, perché funziona:
- gli errori stanno accanto alla riga che li ha causati e dicono che il dato è ancora
  lì;
- un caricamento fallito non si traveste da lista vuota;
- la scheda «Sistema la spesa» è uguale in Lista e in Dispensa;
- la lapide con «Annulla»;
- «Era già in lista.» invece di un doppione;
- la stesura AI che degrada al modulo a mano;
- il «Salva» disabilitato con il motivo scritto sotto;
- gli stati vuoti del ricettario, che spiegano il perché;
- i nomi accessibili dei pulsanti ripetuti, che portano il nome della voce;
- i campi a 16 px, così iOS non ingrandisce la pagina;
- il catalogo che si apre già cercando il nome della voce.

**In tutto il sito**
- **Non c'è un tema scuro.** Con il telefono in tema scuro l'app resta chiara. Il
  commento di `index.css` dice già che è l'unico file da toccare, ma i contrasti vanno
  rifatti coppia per coppia. È il candidato più netto fra i «da fare».
- **Il marchio cambia.** È un cesto al login, nella favicon e nelle icone della PWA, e
  una pentola nell'intestazione (T1). Va scelto un segno solo.
- **Le icone al posto del testo**, la richiesta di Mattia. Oggi sono icone solo la X, i
  chevron e la barra delle schede. I candidati sono i tre pulsanti per voce della
  sistemazione, che oggi fanno due righe per voce, poi «+ scadenza», «Cambia» e «Apri
  l'originale». La proposta è icona più un'etichetta corta, non l'icona sola.
- **Lo stesso selettore d'ingrediente ha tre aspetti**, uno per lista, dispensa e
  ricette, e sistemazione. In sistemazione il nome accessibile fonde nome e reparto
  («Caffèbevande»), e l'albero `listbox > listitem > option` non è ARIA valido. Serve un
  solo componente.
- **I suggerimenti sono rumorosi.** Sono sempre dieci righe, anche quando dopo la terza
  non somigliano più («zucch» → Zucchero prima di Zucchina). Un tocco sbagliato lega la
  voce all'ingrediente sbagliato, e poi c'è S9. Va sistemato lato server, con una soglia
  o un salto di punteggio.
- **Le conferme mancano o stanno fuori vista.** Sono T4.
- **«Finito» ha tre colori**: rosso sul cursore, grigio sulla pastiglia, nero nel
  foglio della cottura. Il rosso è anche il colore della X e degli errori. Serve un
  colore per stato, deciso una volta in `STATUS_TONE`.
- **Lo stesso giudizio ha due controlli**: il cursore a tre zone in dispensa, i tre
  pulsanti nel foglio della cottura. Va deciso nella spec se unificarli.
- **Gli errori di caricamento hanno cinque forme**, e due di queste non hanno il
  pulsante «Riprova» («Riprova più tardi» chiede di ricaricare a mano). Serve un
  componente d'errore unico.
- **Ci sono parole tecniche a video**: «backend», `OPENROUTER_API_KEY`, «dataset» su
  ogni scheda ricetta, «Cerca in anagrafica».
- **Maiuscole a caso** negli ingredienti, e le etichette di stato scritte in modi
  diversi fra dispensa e dettaglio ricetta.
- **Accordi sbagliati**: «kiwi Tolta dalla dispensa», «collegato a astice».
- **Titoli e intestazioni di sezione hanno stili diversi**: «Sistema la spesa» è più
  piccolo, e «INGREDIENTI» nella bozza non è un `SectionHeading`.
- **Un indirizzo inesistente dà una pagina vuota.** Manca una rotta `*`.
- **La barra delle schede non segna niente su `/sistema`.** Dovrebbe segnare «Lista».
- **Su desktop non si rompe niente**: è una colonna da 448 px in mezzo al vuoto. Non è
  urgente.

**Accesso**
- l'errore «Password errata» resta sotto il campo svuotato;
- il campo non prende il fuoco all'apertura;
- manca «Mostra password».

**Lista**
- **Il campo di aggiunta scorrendo copre l'intestazione.** Sono tutti e due `sticky
  top-0`, con lo stesso `z-index`, e la scheda «Sistema la spesa» esce tagliata sotto.
- **La X della lista non ha la lapide con «Annulla»**, che la dispensa invece ha.
- **Le voci spuntate restano in mezzo alle altre.** Potrebbero andare in fondo al
  reparto.
- **C'è una scheda per reparto anche con una voce sola.**

**Sistema la spesa** (oltre a S10, S19 e S20)
- **Una voce risolta si riconosce solo dal colore verde.** Non dice «sfuso» né quale
  prodotto, e «Cambia» pesa quanto le azioni principali.
- **Il blocco «non abbinata» è sempre aperto** e occupa una schermata e mezza per voce.
- **Il nome dell'ingrediente creato è tutto il testo della voce** («zucchine tonde di
  Nizza della signora Pina»). Niente invita a scrivere il nome generico.
- **«È di un altro ingrediente» non dice quale**, ed è in rosso anche se non è un
  guasto.
- **Il catalogo dà due messaggi che si contraddicono**: «altri 2 prodotti, di un altro
  ingrediente» e «nessun prodotto». L'esempio «yogurt greco» compare anche cercando
  uova.
- **«+ scadenza» apre un campo data** senza un'etichetta visibile e senza modo di
  richiuderlo.
- **«Metti in dispensa» non dice quante voci entrano, né che le altre restano in
  lista.**
- **L'ordine delle voci non è quello per reparto della lista.**
- **Con niente da sistemare**, il pulsante disabilitato non serve, e «lista» potrebbe
  essere un collegamento.

**Dispensa** (oltre a S11, S12, S14, S15)
- **Le righe sono alte circa 150 px**, e ci stanno 5 righe per schermo. Metà della riga
  è il vuoto fra il nome e il cursore.
- **Il cursore non dice come si usa.** Il pallino è grigio e non prende il colore della
  zona, non ci sono etichette sotto la traccia, e niente dice che si tocca e non si
  trascina (S13).
- **La riga mostra il prodotto e non l'ingrediente**, quindi un aggancio sbagliato come
  il parmigiano sotto «burro» è invisibile proprio qui. È anche la porta naturale di S9.
- **Due confezioni dello stesso prodotto non si distinguono**, né in dispensa né nel
  foglio della cottura, dove manca la scadenza.
- **Un «Finito» ignorato resta fra le altre righe**, e «Lo rimetto in lista?» non torna
  più.
- **«Sì» e «No» sono larghi 35 e 43 px** e non sembrano pulsanti.
- **La lapide dura 6 secondi** e non lo dice.
- **Le scadenze non hanno un riepilogo**: si trovano per caso a metà pagina. Una scheda
  d'ingresso «2 in scadenza» resterebbe un segnale, come vuole D5.
- **Le date sono scritte assolute e con l'anno.** Sotto i 7 giorni si leggerebbero
  meglio relative.
- **«Aggiungi in dispensa»** non dice cosa fare se l'ingrediente non c'è (S3).
- **La domanda del rientro compare anche per ciò che è già in lista.**
- **Prima della prima riga ci sono due schede.** Si risolve con S11.
- **Una X rossa per ogni riga** (S1).

**Ricette**
- **I filtri occupano tutta la prima schermata**: la prima ricetta è sotto la piega.
  Categoria e ingredienti potrebbero stare dietro «Filtri».
- **La scala «Tutte / Ora / +1 / +2 / +3» non ha un'etichetta visibile.**
- **I mancanti sulla scheda si leggono come un sottotitolo.** Andrebbe scritto «Manca:
  …».
- **Le schede sono alte 386 px**, e mentre la foto carica mostrano un rettangolo
  bianco.
- **La ricetta a mano si scrive da «Scrivi con l'AI».** Andrebbe «+ Nuova ricetta».
- **La scheda «Ingredienti da abbinare»** sta in cima anche quando la coda è vuota.
- **Il filtro per ingredienti** non conta i risultati e non ha «azzera».
- **Tecniche e preparazioni di base** («Come legare l'arrosto», «Uova sode») sono
  mescolate alle ricette.
- **Alcune spaziature sono strette** fra la nota e le pastiglie.

**Dettaglio ricetta** (oltre a R10 e T4)
- **«N dosi su M non si riscalano»** non dice quali (Parte X).
- **Il procedimento è un blocco unico** con i numeri spuri dell'import.
- **«Cucina» sta in fondo e sembra dire «inizia a cucinare».**
- **I mancanti non si mettono in lista dal dettaglio**: la freccia ricetta → lista
  esiste solo dopo aver cucinato.
- **I cinque € sono pulsanti che non sembrano pulsanti**: un tocco scorrendo cambia il
  costo.
- **«Apri l'originale» è alto 19 px.**
- **Senza porzioni lo stepper sparisce** senza dirlo.

**Scrivi una ricetta**
- **Il ruolo delle righe proposte dall'AI non si cambia**, mentre quello delle righe a
  mano sì. Eppure è il ruolo che decide se la ricetta è cucinabile.
- **Mancano categoria e descrizione**, quindi una ricetta scritta non esce mai
  filtrando per categoria.
- **Le righe a mano si tolgono solo togliendo la spunta**, e il nome è scritto due
  volte.
- **La riga non alimentare** ripete il nome ed è scritta nello stile delle righe da
  confermare (Parte X).
- **«Proponi» e «Salva» sono due pulsanti primari.**
- **Le caselle sono da 20×20.**
- **Lo stesso guasto dell'AI** è ambra qui e rosso nella coda.

**Ingredienti da abbinare** (oltre a R11)
- **Il messaggio dell'AI non configurata** è rosso, cita il nome della variabile e
  resta anche con la coda vuota.
- **«1 ricetta in attesa»** compare con due ricette elencate sotto.
- **Il suggerimento testuale è enorme anche quando è assurdo** («Aragosta» → «lonza di
  maiale»).
- **Un ingrediente creato è detto «collegato a»**.
- **Non si cerca** nell'elenco delle decisioni.
- **«Annulla» parte senza lapide.**

## T4. Le azioni grosse non danno una conferma che si veda **[FATTO IN PARTE 2026-09-27 — «Ho cucinato» e il foglio]**
Le azioni che cambiano più cose dicono poco, o lo dicono dove non si guarda:
- **«Ho cucinato».** L'esito («Segnato. Una cosa è tornata in lista della spesa.»)
  compare in cima al dettaglio, mentre si è scorsi in fondo, dove stava il foglio. Chi
  non lo vede può ripetere la cottura. Non c'è un solo `scrollIntoView` in tutto
  `src`.
- **Il foglio della cottura** si apre al posto di ingredienti e procedimento, ma la
  pagina resta in fondo. Le prime righe e «Tocca solo ciò che è cambiato» sono fuori
  vista.
- **«Metti in dispensa»** porta in Dispensa senza dire cosa è entrato né che le voci
  non risolte restano in lista.
- **«Aggiungi in dispensa»** svuota il campo e basta, e la riga nuova è venti schermate
  più in basso.
- **«Salva nel ricettario»** porta al dettaglio senza un messaggio.

**Cosa fare.** Un avviso breve in un punto fisso, uguale in tutta l'app («4 voci in
dispensa · 3 restano in lista»). Dopo un'aggiunta, scorrere alla riga nuova e
evidenziarla per un attimo. Il foglio si apre scorrendo al suo inizio. Il primo dei
cinque punti è un difetto; gli altri sono da fare.

**Fatto:** i primi due punti, quelli del dettaglio ricetta. Aprire «Cucina» porta in
vista l'inizio del foglio; dopo «Ho cucinato» l'esito viene in vista e prende il fuoco
(`role="status"` con `tabIndex={-1}`), così anche lo screen reader lo legge. Entrambi
passano da `revealAtTop` (`frontend/src/lib/revealAtTop.ts`): `scrollIntoView({block:
"start"})`, animato tranne per chi ha chiesto al sistema meno movimento. Dove fermarsi
sotto l'intestazione fissa lo dice uno `scroll-mt-*` sull'elemento, non un numero in
JavaScript. I test in jsdom controllano a chi si chiede di venire in vista e dove
finisce il fuoco; che arrivi davvero sotto l'header si guarda in un browser vero.
**Restano aperti** «Metti in dispensa», «Aggiungi in dispensa» e «Salva nel
ricettario», con l'avviso uguale in tutta l'app che li servirebbe: aspettano la spec
del ridisegno di T3, perché dove sta quell'avviso è una domanda sua.

---

# Parte VIII — Ordine consigliato

Non è un impegno, è quel che le dipendenze permettono.

**Subito, perché sbloccano o smettono di perdere dati**
T2 è fatto (2026-09-17), e D1–D3 sono decise (le tre il 2026-09-17; D1 costruita e in
produzione il 2026-09-20). **Anche D5 è decisa**, il 2026-09-20: non resta ferma
nessuna decisione, e la sua metà pratica, S7, è **fatta il 2026-09-21**, in produzione
dal 2026-09-22 e verificata a mano il 2026-09-23.

**Poi, indipendenti e piccole** — si potevano fare in qualunque momento e non
aspettavano nessuno: **fatte il 2026-09-17** S1, S2, R1, R3, e in parte T1 (header,
tasto indietro, schede d'ingresso). **Resta aperto** solo l'hamburger di T1,
rinviato di proposito alla prima sezione secondaria vera — non c'è fretta, perché
niente lo sblocca.

**Poi, il blocco strutturale**: S4 (nutrienti ampi). D1 era qui ed è fatta il
2026-09-20 — con lei la metà per porzioni di R2 — e D4/S5 (non alimentari) lo erano
il 2026-09-18. Da qui in avanti serve la spec.

**Fuori ordine, perché dipendeva solo da una decisione e non da uno schema**: S7,
**fatto il 2026-09-21**. Qui c'era scritto «si può fare quando si vuole, anche subito»,
ed è andata proprio così: non ha aspettato né S4 né lo storage, e il lavoro è stato
quel che si diceva — una colonna annullabile, un campo data e un colore. Fuso,
distribuito il 2026-09-22 e verificato a mano il 2026-09-23.

**Poi**: R4, **eseguita il 2026-09-24** (8.136 ricette in produzione). A valle, R5 e
R6 non aspettano più R4: aspettano la spec di R5.

**Indipendente e piccola**: R9, il costo della ricetta, **fatta il 2026-09-24** — una
colonna annullabile, un selettore e cinque `€`, più la lettura del costo dall'import,
così R4 lo porta già.

**Ultimo, quel che ha bisogno di tutto il resto**: Pasti (P1, P2, P3), M1, H1, H2.

**Dal 2026-09-27, per l'uso di tutti i giorni: le voci di Mattia (S8–S15, T3, e S3
di nuovo).** Proposta d'ordine, da confermare:
1. **prima quel che scrive dati sbagliati o li lascia sbagliati**: S13 (il cursore
   che cambia lo stato scorrendo), S9 (niente si corregge) e S8 (il codice che non
   resta). Sono difetti, non miglioramenti. **S13 e S8 fatti il 2026-09-27**; resta
   S9, che vuole prima un brainstorming sulla forma;
2. **poi il giro del sottoagente di T3**, prima di toccare la forma delle schermate:
   S10, S11, S12, S14, S15 e l'ingresso diretto di S3 cambiano tutti le stesse due
   schermate, Dispensa e Sistema la spesa, e il giro porterà altre voci sulle stesse.
   Rifarle una volta sola, con la spec della revisione in mano, costa meno che
   rifarle sei volte;
3. **poi la revisione**, con S3 dentro. Chi scrive la spec controlli se estrarre
   scanner, catalogo e modulo da `StockingScreen.tsx` sia lo stesso lavoro di S3
   e S10.

**Il giro di T3 è fatto (2026-09-27), e ha portato sette difetti che non aspettano la
revisione**: S16–S21, più la prima metà di T4, l'esito di «Ho cucinato» fuori vista.
Sono piccoli, stanno su righe che la revisione non ridisegna, e alcuni scrivono dati
sbagliati:
- S20 lega prodotti a ingredienti sbagliati;
- S18 (fatto il 2026-09-27) e S19 lasciano voci senza ingrediente.

Proposta: **prima S20, S19, S18**, perché sporcano l'anagrafica; **poi S16, S17, S21 e
T4-«Ho cucinato»**. R11 costa poco, perché il backend è già pronto, e può andare con
loro. R10 invece vuole prima una decisione, e va con S9, perché è lo stesso principio.
Solo dopo, la spec di T3 con l'elenco del giro in mano.

---

# Parte IX — Lavoro già impegnato: i controlli end-to-end

Lo stile è l'unica parte dell'app che Vitest non può vedere: Tailwind genera il CSS
alla costruzione e jsdom non lo calcola. Girano sullo stack `spena-e2e`, che ha una
password finta e nota in `.env.e2e`: nessuna credenziale vera, nessuna chiave,
nessuna rete.

```bash
E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
$E2E up -d --build --wait
$E2E exec -T backend python -m app.cli.seed --con-ricette
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
$E2E down -v
```

**a. Il contrasto misurato, non calcolato a mano** — in `frontend/e2e/style.spec.ts`.
Leggere dal browser il colore calcolato e il fondo dietro, calcolare il rapporto in
pagina, asserire ≥ 4.5. Oggi `index.css` *afferma* che `ink-faint` è «il più chiaro
che regge 4.5:1 sul fondo» e non lo verifica niente.

| Token | Colore | Su `--color-page` `#eef1ee` | Margine |
|---|---|---|---|
| `--color-low` | `#9a5f0c` | 4.60:1 | +2% |
| `--color-ink-faint` | `#636e66` | 4.58:1 | +2% |

Entrambi in `text-xs`, dove la soglia è 4.5 e non 3.

**b. Le schermate della revisione** — nuovo `frontend/e2e/import-review.spec.ts`,
senza stub di rete: seminare i termini decisi passando dal codice vero e lasciare che
il browser chiami l'endpoint vero. Controlla la sezione «Deciso dall'AI», il
comportamento **a 375px** di un nome lungo in `truncate` dentro un `justify-between`,
e il riquadro di conferma dell'annullamento.

**c. La riga «da creare salvando»** — con `page.route`, e con un commento che dichiari
il limite: è un test che si costruisce l'oggetto da sé, quindi vale solo per il
layout a 375px.

---

# Parte X — Piccole cose aperte

- **Un 404 viene ritentato e poi offre «Riprova».** `lib/queryRetry.ts` ritenta ogni
  errore tranne il 401, 404 compreso. Così una ricetta che non c'è più risponde dopo
  qualche secondo con «Non sono riuscito a caricare questa ricetta. Riprova.», e
  riprovare non può riuscire. Va escluso il 404 dal ritentare, con un messaggio suo
  («Questa ricetta non c'è più») e il ritorno al ricettario. Dal giro di T3, verificato
  sul codice.
- **«Ingrediente» invece di «voce» in due schermate.** `AddItemField.tsx` (lista)
  e `StockingScreen.tsx` (sistemazione della spesa) dicono entrambi
  «ingrediente» all'utente — «l'ingrediente si abbina dopo», «Abbina un
  ingrediente», «Crea l'ingrediente «…»» — proprio dove si collega una voce di
  testo libero all'anagrafica, che ora può anche non essere cibo. Non è un
  difetto introdotto dal lavoro sul non alimentare (D4), esisteva già prima;
  resta un rinominamento aperto.
- **Nella stesura AI, «non in anagrafica» è la formula sbagliata per una riga non
  alimentare.** `AiDraftScreen.tsx:104` mostra, per ogni riga senza `ingredientId`,
  «"X" non in anagrafica, sarà escluso». Per «carta forno» il match c'è — l'anagrafica
  ce l'ha — solo che è non alimentare, e `ai_recipes.py` azzera l'aggancio proprio per
  questo (stesso principio della guardia di D4). Il messaggio confonde due motivi
  d'esclusione diversi («non esiste» contro «esiste ma non è cibo»); non è un dead
  end — la riga resta esclusa, il picker manuale resta lì, nessun errore — quindi
  resta una formulazione da scegliere con calma, non una stringa da correggere di
  fretta.
- **`skipped_reason` non affiora da nessuna rotta né da nessuna schermata**,
  solo il conteggio aggregato in `/api/v1/imports/status` — vale sia per il
  nuovo motivo «riga non alimentare» (`NonFoodInRecipe`, D4) sia per il
  preesistente `EMPTY_REASON` (`backend/app/services/recipe_import/materialize.py`).
  Una pagina `SKIPPED` non si ritenta da sola: chi vuole sapere perché deve
  aprire il database.
- ~~**La guardia sugli argomenti sconosciuti di `app.cli.seed` stampa il rifiuto
  ma esce con codice 0.**~~ **Chiusa con R4, il 2026-09-24**: un flag sconosciuto o
  contraddittorio esce con codice 1.
- **Il gate a password resta** — deciso il 2026-09-15. `SESSION_MAX_AGE` è già **un
  anno** (`backend/app/core/security.py:9`): in produzione la password si digita una
  volta per browser e poi mai più. Senza gate, `POST /api/v1/imports/...` diventerebbe
  un endpoint pubblico che fa scaricare GialloZafferano dal nostro server su richiesta
  anonima, e il tetto di 1$/giorno non copre quello.
- **In locale l'app non parte**, e non è il login: `SESSION_SECRET` nel `.env` è un
  segnaposto e `main.py:42` rifiuta di avviarsi. Si risolve una volta sola generando
  un segreto con `python3 -c "import secrets; print(secrets.token_urlsafe(48))"`.
  (Quel file non lo tocca Claude, per accordo.)
- **La regola di permesso `Bash(ssh hetznerserver:*)`** in `.claude/settings.local.json`
  è larga quanto tutta la macchina, concessa per un deploy finito. Da restringere.
- **`ANTHROPIC_API_KEY` è ancora nel `.env` del server** e non la usa più niente.
- **Nel `.env` locale `OPENROUTER_APP_URL` non c'è** (quel file non lo tocca Claude,
  per accordo). Le chiamate fatte in sviluppo restano quindi senza attribuzione. Se
  un giorno danno fastidio, valorizzarla con qualcosa di diverso dal dominio vero —
  `http://localhost` — le separa dalla produzione nei log di OpenRouter invece di
  mescolarcisi; lasciarla vuota è l'altra scelta legittima, e oggi è quella in atto.
- **Due file non tracciati sul server**, in `~/sites/spena`: `.env.bak` e
  `imposta-password.sh`.
- **I warning `"argon2id" variable is not set`** sul server sono l'interpolazione
  `${VAR}` di Compose dentro lo YAML, cosmetici e preesistenti. Non inseguirli.
- **Nel foglio della cottura la casella «Rimetti in lista» è pre-spuntata solo per
  «finito»** (`frontend/src/features/cooking/CookSheet.tsx`), mentre in dispensa la
  domanda arriva anche nel giallo dal 2026-09-17. Non è un difetto: là la casella c'è
  sempre e visibile per ogni riga, quindi pre-spuntarla è un valore di partenza, non
  un'offerta che appare o non appare. Ma le due sezioni ora rispondono in modo
  diverso alla stessa domanda — «quasi finito va ricomprato?» — e vale la pena
  deciderlo una volta invece di riscoprirlo.
- **`PantryRow.tsx` è il file più affollato dell'app** (304 righe dopo S7, che ne ha
  aggiunte un centinaio, e quattro stati locali oltre alle prop). Estrarre la domanda
  del rientro in lista («Lo rimetto in lista?», con la sua lapide e il suo esito) come
  componente a sé è il taglio naturale, quando qualcuno ci tornerà; la scadenza è il
  secondo candidato.
- ~~**Il bersaglio di «+ scadenza» sborda di 4px su quello del cursore** in dispensa.~~
  **Chiusa il 2026-09-27, e la premessa era sbagliata**: misurato in Chromium, il
  bordo alto del bersaglio cade esattamente sul bordo basso del cursore, 0px di
  sovrapposizione. Il testo di 16px sta centrato nella riga della pastiglia, alta 24px:
  4 dei 14px di imbottitura cadono dentro la riga, 10 ne escono, cioè proprio il
  `gap-2.5`. Il commento era giusto ma saltava quel passaggio; ora ha il conto intero e
  avvisa che dipende dai 24px di `StatusChip`. Le classi sono rimaste. Il testo di
  prima, per la storia:
  Il comando è alto 16px e viene portato a 44 con `-my-3.5 py-3.5`, cioè 14px per
  parte, mentre lo spazio fra i due controlli è un `gap-2.5` da 10px: restano 4px in
  cui il tocco può prendere «+ scadenza» invece del cursore. **E il commento accanto
  dice «10px per parte, cioè esattamente il `gap-2.5`»**, che sarebbe vero per un
  contenuto alto 24px, non 16. Trovato dalla revisione finale e lasciato lì di
  proposito: il giro di correzioni era speso e la suite era verde. Si sistema
  cambiando due classi e il commento.
- ~~**Nessuno dei due campi data ha un `max`**, quindi Chromium accetta un anno a sei
  cifre. Non rompe niente — il backend prende qualunque `DATE` — ma si vede.~~
  **Chiusa il 2026-09-27**: `EXPIRY_INPUT_MAX = "9999-12-31"` in `expiryLabels.ts`,
  lo stesso `date.max` di Python, usato da entrambi i campi. Nessun `min`: una data
  passata è legittima (D5).
- **Chiusa il 2026-09-27: `npm run lint` è verde**, zero problemi. `eslint.config.js`
  esenta i nomi col trattino basso; gli altri errori sono stati corretti, non spenti
  (i due `setState` in un effetto ora si riallineano durante il disegno, le costanti
  di `MissingBudgetFilter` sono in `missingBudget.ts`). Il testo di prima:
  ~~**`npm run lint` è rosso: 5 errori e 1 avviso.**~~ Quattro errori sono preesistenti
  (`FillSlider.tsx`, due in `PantryRow.tsx`, uno in `MissingBudgetFilter.tsx`). **Il
  quinto l'ha introdotto S7**: in `StockingScreen.test.tsx` un parametro inutilizzato
  è stato rinominato `_init` per soddisfare `noUnusedParameters` di TypeScript — che
  esenta il trattino basso — ma la regola `@typescript-eslint/no-unused-vars` di
  questo progetto non è configurata per esentarlo, quindi lo segnala. Si chiude con
  `argsIgnorePattern: "^_"` nella configurazione di ESLint, che è anche il modo di
  allineare le due regole una volta per tutte. Il lint non è nei comandi di verifica
  del progetto (Parte XI), quindi nessuna suite se n'è accorta.
- **Chiusa il 2026-09-27**, `grep -rn StatusToggle frontend/src` non trova più niente
  (erano quattro, c'era anche `StatusChip.test.tsx`). Il testo di prima:
  ~~**Restano riferimenti a `StatusToggle` in alcuni commenti**~~
  (`frontend/src/components/ui/StatusChip.tsx`,
  `frontend/src/features/cooking/CookSheet.test.tsx`,
  `frontend/src/features/ai-draft/AiDraftScreen.tsx`), di un componente che questo
  lavoro ha cancellato insieme al vecchio schema a tre pulsanti (S2, sopra). Non
  rompono niente, ma nominano qualcosa che non esiste più.
- **Prima di questo lavoro `StatusChip` non aveva un test suo**: il legame fra la
  mappa dei colori (`STATUS_TONE`/`STATUS_LABELS`) e il componente lo provava solo
  `StatusToggle.test.tsx`, cancellato con il resto di quel componente proprio in
  questo lavoro. La copertura è stata ricostruita
  (`frontend/src/components/ui/StatusChip.test.tsx`), ma vale la pena sapere che
  prima non c'era: è lo stesso difetto della prima lezione di `CLAUDE.md` — una
  mappa può essere giusta mentre il controllo che la gente tocca non la usa — e qui
  è sopravvissuto abbastanza a lungo da valere una nota.
- **Non esiste una schermata per correggere un plurale sbagliato nel registro
  `units` (D1).** Se l'AI decide un singolare o un plurale sbagliato per una
  parola — «cucchiai» → singolare sbagliato — non c'è modo di sistemarlo da
  interfaccia. Si corregge da riga di comando: `python -m app.cli.decide_units
  --azzera <chiave>` azzera la decisione per quella chiave, così la prossima
  esecuzione del comando la ridecide da capo. Scelta deliberata, non un buco: il
  registro è una ventina di righe, un errore si vede subito nella ricetta stessa,
  e costruire una schermata per una correzione così rara non vale ancora il
  lavoro. Dichiarata qui perché resti visibile, non perché sia urgente.

  **Misurato in produzione il 2026-09-20, e il rimedio qui sopra non basta.** Delle
  27 unità decise al primo giro, due erano sbagliate: `cucchiai` → singolare
  `cchiaio` (una «u» mangiata) e `cucchiaino` → plurale `cucchiaiaini`. La verifica
  prima di applicare fa il suo mestiere — controlla che la chiave sia in anagrafica
  e che le forme non siano vuote né troppo lunghe — ma **non può controllare
  l'ortografia**, e non deve: sarebbe un secondo giudizio sul primo. L'`--azzera`
  ha sistemato `cucchiaino` al secondo tentativo e **non ha sistemato `cucchiai`**:
  il modello ha rifatto lo stesso errore. Quindi per una parola che sbaglia in modo
  ripetibile l'unica via sarebbe stata una `UPDATE` a mano sul database, cioè fuori
  da ogni strada progettata.

  **Chiuso lo stesso giorno**: `python -m app.cli.decide_units --imposta <chiave>
  <singolare> <plurale>` scrive le forme a mano e segna `decided_by = "human"`, che
  toglie la riga dalla coda di `undecided_units` — una decisione umana è definitiva
  finché non la si azzera, altrimenti il giro dopo il modello rifarebbe l'errore
  appena corretto. Scrive attraverso lo stesso `_write_forms` che usa l'AI, così il
  puntatore al canonico non può divergere fra le due strade. `cucchiai` è stato
  corretto in produzione con questo comando. **Resta vero il resto della voce**: una
  schermata per farlo dall'interfaccia continua a non valere il lavoro, e l'annulla
  da solo continua a non bastare — ma adesso non è più da solo.
- **Circa settanta dosi in produzione contengono una dose vera che il parser non
  legge, per colpa di come l'import le ha scritte (D1).** Misurato il 2026-09-20 su
  67 ricette: `reparse_quantities` ha parsato 382 dosi su 550 e ne ha lasciate 168.
  Di quelle, una novantina sono `q.b.` e le sue combinazioni, che è giusto così —
  ma le restanti hanno questa forma, presa da GialloZafferano con tutto il suo
  spazio bianco: `"fredda\n\t\t\t330\n\t\t\tg"`, `"denocciolate\n\t\t\t20\n\t\t\tg"`.
  La dose c'è (`330 g`), ma davanti ha un aggettivo, quindi `parse_quantity` — che
  pretende il numero in testa — torna `(None, None)` e quella riga non si riscala.
  Non è un difetto di D1: il parser fa quel che la spec §4.1 dice. È qualità del
  dato all'ingresso. Due strade, e la prima è meglio: che l'import ripulisca
  `quantity_text` quando la scrive (una sola volta, e il testo mostrato migliora
  anche a schermo), oppure che il parser tolleri un aggettivo iniziale (ma allora
  ogni parola prima del numero diventa un caso da decidere, ed è la strada che la
  spec ha già scartato una volta). Qualunque si scelga, poi basta rilanciare
  `reparse_quantities`: è rieseguibile apposta.
- **Il rovescio della voce sopra, visto con R4: un numero nel nome letto come la
  dose.** Misurato il 2026-09-24 sulle 8.136 ricette. `"36 mesi\n\t\t\t50\n\t\t\tg"`
  (un Parmigiano stagionato) è parsato come 36 della unità `mesi`, e la dose vera,
  `50 g`, si perde. Al doppio delle porzioni la riga direbbe **72 mesi**. Stessa
  forma per `1 da … 150 g`, `2 intere … 600 g`, `2 per un totale di 150 g`,
  `380/420 W … 410 g`, `24 K, in foglie`. Sono circa 90 righe su 79.833 (56 solo
  `mesi`), e hanno portato in `units` parole che unità non sono: `mesi`, `da`, `di`,
  `e`, `per`, `già`, `circa`, `q`, `k`, `w`, `grande`, `piccola`, `rossa`… —
  `decide_units` le ha decise come qualunque parola, perché il suo compito è
  singolare e plurale, non se sia un'unità. Il rimedio è quello della voce sopra:
  ripulire `quantity_text` all'ingresso, poi `reparse_quantities`. Chi lo fa tenga
  conto che le unità spurie restano in `units` finché qualcuno non le toglie.
- **Ogni test di schermata si costruisce il proprio client react-query con
  `retry: false`, mentre `frontend/src/App.tsx` usa
  `defaultQueryRetryPredicate`.** È esattamente la prima lezione di `CLAUDE.md` —
  «un test che si costruisce il proprio oggetto non sta testando quello che usa la
  produzione» — trovata di nuovo, questa volta sul client di query invece che sul
  client AI o su una funzione di dominio duplicata. `grep -rln "retry: false"
  frontend/src --include=*.test.tsx` trova undici file
  (`IngredientPicker.test.tsx`, `CustomProductForm.test.tsx`,
  `RecipeBookScreen.test.tsx`, `CookSheet.test.tsx`, `AiDraftScreen.test.tsx` e
  altri): nessuno di questi esercita il comportamento di retry vero dell'app, che
  su un errore 5xx riprova mentre `retry: false` non riprova mai. Un backend che
  iniziasse a rispondere 500 in modo intermittente potrebbe non essere notato da
  nessuno di questi test, che vedrebbero solo il fallimento secco che hanno chiesto
  loro stessi. Preesistente, non causato da questo lavoro; trovato passando mentre
  si verificava lo stesso principio altrove.

---

# Parte XI — Note operative

- Il repo sul server è in **`~/sites/spena`** su `hetznerserver`.
- **L'import completo (R4) ha un runbook suo**, `docs/import-gz-runbook.md`: deploy,
  backup, ricette di semina, lancio in background, cosa guardare e cosa fare dopo.
- Deploy: `git pull --ff-only` e poi
  `docker compose -f docker-compose.prod.yml up -d --build --wait`. **Il `-f` non è
  opzionale** — terza lezione di `CLAUDE.md`.
- **Il `git pull` da solo non distribuisce niente**, e non lo dice nessun errore: il
  frontend è compilato dentro l'immagine, quindi finché non si ricostruisce il browser
  riceve il pacchetto di prima. Misurato il 2026-09-22: R7 era sul server dal 21 e
  nessuno l'aveva mai visto. La prova che il codice nuovo gira è il nome del pacchetto
  servito — `curl -s https://spena.mattiagirellini.com/ | grep -o "assets/index-[^\"]*"`
  contro `frontend/dist/assets/` dopo un `npm run build` locale — e non i container
  «healthy», che sarebbero healthy anche con l'immagine di ieri.
- La suite vera gira **sull'host, non in Docker**: `cd backend && .venv/bin/python -m
  pytest` con Postgres su da `docker compose up -d db`; per il frontend
  `npx vitest run`, `npm run typecheck`, `npm run build`. L'immagine del backend non
  contiene pytest, e `tsc --noEmit` non è il type check di questo progetto (settima
  lezione di `CLAUDE.md`).
- **Tetto di spesa: 1$/giorno su OpenRouter.** Ogni voce che fa girare l'AI su tutto
  il catalogo (R5, S4 di massa) deve fare i conti con questo prima della spec.
