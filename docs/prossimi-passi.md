# Spena — prossimi passi

Aggiornato il 2026-09-24 (**due voci nuove**: R9, il costo della ricetta da uno a
cinque `€`, e P3, la pianificazione su più giorni con un budget — il brainstorming
sulla forma del budget è aperto). Prima: il 2026-09-23 (**la verifica a mano di S7 e R7 è stata fatta ed è
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

Due cose si sono viste solo sui dati veri, e hanno la loro voce in **Parte X**: due
plurali sbagliati dall'AI su ventisette (uno dei quali l'`--azzera` non sapeva
correggere, il che ha prodotto `--imposta` lo stesso giorno), e circa settanta dosi
che contengono una dose vera che il parser non legge, perché l'import le ha scritte
con un aggettivo e lo spazio bianco della pagina davanti al numero.

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

## S4. Valori nutrizionali molto più ampi **[D, con TBD dentro]**
Oggi `products.nutrients` è un JSONB popolato da Open Food Facts, quindi già libero
nella forma ma povero nel contenuto.

- **TODO (sottoagente):** ricerca su quali macro e micronutrienti servono davvero per
  una dieta bilanciata, con le unità e i riferimenti giornalieri. È il lavoro che
  definisce i campi, e va fatto prima della spec.
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

## R4. Via le ricette di semina, e l'import completo di GialloZafferano **[D, con un blocco]**
L'obiettivo è tutto il catalogo. Strategia proposta: **prima uno scarico locale
completo**, poi la messa online e il parsing a ondate.

> **VINCOLO ATTIVO: massimo ~100 ricette totali** finché i volumi Docker non stanno
> su uno storage esterno più capiente. Me lo dirai tu quando è fatto. Fino ad allora
> nessun import di massa, e questo vincolo vale anche per ogni altra voce di questo
> file.

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
↳ R4 (serve l'anagrafica ampia).

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

## R9. Il costo della ricetta **[D, con TBD]**
Ogni ricetta ha un costo da 1 a 5, disegnato come cinque `€` di cui i primi *n* neri
e gli altri grigio chiaro: `€€€··` è una ricetta da 3. È un **livello**, non una
cifra in euro — la stessa scelta della decisione fondante 1 sulle quantità, per la
stessa ragione: un prezzo vero andrebbe tenuto aggiornato e comincerebbe a mentire il
giorno in cui si smette.

**Da dove arriva il valore.** GialloZafferano scrive già sulla pagina «Costo: Molto
basso / Basso / Medio / Elevato / Molto elevato» — esattamente cinque gradini. Oggi
l'import non lo legge (sta nell'HTML, non nel JSON-LD) e non conserva l'HTML, quindi
per le ricette già importate va riscaricata la pagina: si fa insieme all'import
completo di R4. Per le ricette scritte a mano o dall'AI il costo si sceglie nel
modulo; per la bozza AI può proporlo l'AI, come propone il resto.

TBD:
- annullabile o obbligatorio? La regola «ciò che manca resta mancante» vale anche
  qui: una ricetta senza costo non è una ricetta da 1;
- **il costo è della ricetta intera o della porzione?** Per il ricettario non cambia
  niente; per P3, che somma pasti, cambia tutto (vedi lì);
- se il costo di una ricetta cucinata «con quel che ho in dispensa» debba contare
  meno. Proposta: no, almeno all'inizio — la dispensa non sa le quantità e non può
  dire quanto di quella spesa è già pagata.

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

## P3. Pianificare più giorni **[TBD]** ↳ P1, P2, M1, R9
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
«€» non sono euro ma gradini di costo, e **questo è il TBD principale: la forma del
budget confonde**. Il brainstorming è partito il 2026-09-24; le opzioni e le domande
aperte stanno sotto.

**Opzioni sul budget** (nessuna decisa):
- **a. Somma di gettoni con tetto** — la formulazione originale, con un nome che non
  sia «euro» («30 gettoni, fino a 40»). Fedele all'idea, ma il numero giusto cambia
  con i giorni e i pasti: 30 su sette giorni e due pasti è un'altra cosa che su tre.
- **b. Media per pasto** — «in media `€€···`, al massimo `€€€··`». Si esprime con lo
  stesso simbolo della ricetta, non cambia al cambiare della durata e dei pasti fuori,
  e la somma la fa il programma. Proposta.
- **c. Tre profili** — «risparmio / normale / mi concedo», tradotti dietro in b.
  È b con meno manopole; si può aggiungere dopo senza toccare il resto.

**Domande aperte:**
- il margine è simmetrico? Proposta: no — spendere meno dell'ideale non è mai un
  errore, quindi è un ideale e un tetto, non un ±;
- sommare livelli è lecito? `€€€€` non costa per forza il doppio di `€€`: la somma
  tratta una scala ordinale come se fosse in euro. Si può accettare come
  approssimazione dichiarata, o dare ai gradini un peso non lineare nascosto;
- **porzioni e avanzi**: una ricetta da 4 porzioni mangiata in due giorni sottrae il
  suo costo una volta o due? E il piano deve saper proporre «ceni e ti avanza il
  pranzo di domani»? Si lega a R2 e a «costo per ricetta o per porzione» di R9;
- i pasti fuori pesano sul budget? Proposta: no di default — il budget è quello della
  spesa — con un costo facoltativo per chi lo vuole;
- cosa fa il piano quando budget e nutrienti non stanno insieme: rispetta il tetto e
  lo dice, mai un «impossibile» secco (Mai un vicolo cieco);
- il piano finito **chiude l'anello**: quel che manca per le ricette scelte va in
  lista della spesa, come oggi va quel che finisce cucinando.

**Cosa si può fare prima di P2 e S4.** I nutrienti per ricetta non esistono ancora:
un primo piano può guardare solo budget, pasti al giorno, dispensa e varietà, e
imparare i nutrienti quando arrivano — come P2 senza H2 impara l'attività dopo.

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

**Poi, quel che aspetta lo storage**: R4, e a valle R5, R6.

**Indipendente e piccola, quando si vuole**: R9, il costo della ricetta — una colonna
annullabile, un campo nel modulo e cinque `€`; il valore per le ricette importate
arriva con R4.

**Ultimo, quel che ha bisogno di tutto il resto**: Pasti (P1, P2, P3), M1, H1, H2.

---

# Parte IX — Lavoro già impegnato: i controlli end-to-end

Lo stile è l'unica parte dell'app che Vitest non può vedere: Tailwind genera il CSS
alla costruzione e jsdom non lo calcola. Girano sullo stack `spena-e2e`, che ha una
password finta e nota in `.env.e2e`: nessuna credenziale vera, nessuna chiave,
nessuna rete.

```bash
E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
$E2E up -d --build --wait
$E2E exec -T backend python -m app.cli.seed
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
- **La guardia sugli argomenti sconosciuti di `app.cli.seed` stampa il rifiuto
  ma esce con codice 0** (`backend/app/cli/seed.py`, vicino a
  `FLAG_SOLO_INGREDIENTI`): un refuso come `--solo-ingredient` viene detto a
  schermo, ma niente lo farebbe fallire in uno script che controlla l'exit
  code invece di leggere l'output. Innocuo finché quel comando resta digitato
  a mano.
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
- **Il bersaglio di «+ scadenza» sborda di 4px su quello del cursore** in dispensa.
  Il comando è alto 16px e viene portato a 44 con `-my-3.5 py-3.5`, cioè 14px per
  parte, mentre lo spazio fra i due controlli è un `gap-2.5` da 10px: restano 4px in
  cui il tocco può prendere «+ scadenza» invece del cursore. **E il commento accanto
  dice «10px per parte, cioè esattamente il `gap-2.5`»**, che sarebbe vero per un
  contenuto alto 24px, non 16. Trovato dalla revisione finale e lasciato lì di
  proposito: il giro di correzioni era speso e la suite era verde. Si sistema
  cambiando due classi e il commento.
- **Nessuno dei due campi data ha un `max`**, quindi Chromium accetta un anno a sei
  cifre. Non rompe niente — il backend prende qualunque `DATE` — ma si vede.
- **`npm run lint` è rosso: 5 errori e 1 avviso.** Quattro errori sono preesistenti
  (`FillSlider.tsx`, due in `PantryRow.tsx`, uno in `MissingBudgetFilter.tsx`). **Il
  quinto l'ha introdotto S7**: in `StockingScreen.test.tsx` un parametro inutilizzato
  è stato rinominato `_init` per soddisfare `noUnusedParameters` di TypeScript — che
  esenta il trattino basso — ma la regola `@typescript-eslint/no-unused-vars` di
  questo progetto non è configurata per esentarlo, quindi lo segnala. Si chiude con
  `argsIgnorePattern: "^_"` nella configurazione di ESLint, che è anche il modo di
  allineare le due regole una volta per tutte. Il lint non è nei comandi di verifica
  del progetto (Parte XI), quindi nessuna suite se n'è accorta.
- **Restano riferimenti a `StatusToggle` in alcuni commenti**
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
