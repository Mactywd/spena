# Spena — prossimi passi

Aggiornato il 2026-09-17 (le cinque voci indipendenti di Parte VIII: S1, S2, R1,
R3, T1; poi, lo stesso giorno, la domanda del rientro in lista estesa al giallo e
il filtro per ingrediente rifatto al plurale).

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
(migrazione `0006` applicata in produzione). Dove questo file dice «FATTO
2026-09-17» qui sotto, intende codice che gira.

---

# Parte I — Le decisioni che bloccano il resto

Sono quattro, e **le prime tre sono chiuse il 2026-09-17**. Stanno qui perché
cambiano la forma di molte cose a valle: chi apre una spec di Parte II, III o IV parte
da queste. La quarta è una proposta che considero già buona, segnalata solo perché
tocca una decisione fondante.

## D1. Le quantità nelle ricette **[D — deciso il 2026-09-17]**

> **Decisione: sì, e solo nelle ricette.** La proposta qui sotto è quella adottata.
> La dispensa non cambia. Quando questa voce verrà implementata, vanno emendate
> `CLAUDE.md` (decisione fondante 1) e la spec madre §2, che oggi dicono che
> `quantity_text` non deve **mai** entrare in un calcolo.

**Il problema.** La decisione fondante numero 1 dice «niente quantità, da nessuna
parte», e che `recipe_ingredients.quantity_text` è testo libero che **non deve mai
entrare in un calcolo**. Ma tre voci della lista nuova chiedono esattamente un
calcolo su quel campo: *riporziona*, *stima nutrienti di una ricetta*, *NutriScore*.
Senza una decisione esplicita qui, quelle tre voci fanno deragliare l'app per
inerzia, un pezzo alla volta.

**Come.** Restringere la decisione fondante a dove serviva davvero — **la
dispensa** — e dare alle ricette quantità strutturate accanto al testo:

- `quantity_text` resta la verità da mostrare, non viene mai riscritto né perso;
- si affiancano `quantity_value` e `quantity_unit`, **entrambi annullabili**;
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
> fondante numero 1 resta intera. Chi implementerà D1 e toccherà `CLAUDE.md` deve
> sapere che questa colonna c'è, e perché non conta come precedente.

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

## D4. Il non alimentare — proposta, non domanda **[D salvo obiezione]**

Detersivo e carta igienica devono stare in lista e in dispensa senza una seconda
lista. La via più economica è **un campo sull'anagrafica esistente** (`kind:
food | non_food`, categoria «Non alimentari»), non una tabella nuova: la lista, la
dispensa e l'autocomplete continuano a fare una join sola.

Ne discendono tre guardie da scrivere: una ricetta non può puntare a un non
alimentare, la nutrizione lo ignora, e le decisioni dell'AI sull'import non ne creano
mai. La parola «ingrediente» resta nel codice; nell'interfaccia, dove serve, si dice
«voce».

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

## S5. Non alimentari in lista e dispensa **[D]**
Vedi D4. Nessuna informazione nutrizionale, solo la voce con il suo slider.

---

# Parte III — Ricette

## R1. La foto dentro la ricetta **[FATTO 2026-09-17]**
La foto si vede anche nella scheda aperta, non solo nell'elenco. Il ramo
dell'immagine rotta — il difetto già corretto una volta (`6a2175b`) — ora sta in un
componente solo, `RecipeImage` (`frontend/src/features/recipes/RecipeImage.tsx`),
usato da entrambe le schermate: una seconda copia di quella logica si sarebbe
scollata esattamente lì, dove nessuno guarda.

## R2. Riporziona **[D]** ↳ D1
Due modi, e il secondo è quello che manca a tutte le app: per **numero di porzioni**,
e per **quantità assoluta di un ingrediente** — «la ricetta è per 400 g di pasta, io
ne faccio 150 g», indipendentemente dalle porzioni. Il secondo implica scegliere
l'ingrediente su cui ancorare la scala.

TBD: se il riporziona è solo una vista o si può salvare; cosa succede alle righe non
parsate (proposta: restano identiche e si vedono come tali).

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

## R7. Cerca ricette con al massimo *n* ingredienti mancanti **[D]**
Due usi in uno: «tanto devo andare a fare la spesa, ammetto 3 cose da comprare», e
**svuotafrigo** — parto dagli avanzi e allargo di poco la scelta.

⚠️ Attenzione alla sesta lezione di `CLAUDE.md`: *un filtro che lavora sul risultato
non può stare dietro a un limite*. `recipe_search.py` ha già preso questo difetto una
volta. Con il catalogo intero di GialloZafferano è la stessa trappola, moltiplicata.

## R8. Modifica con AI **[D]**
Dentro una ricetta aperta, un tasto «Modifica con AI» con un prompt libero
(«sostituisci lo zucchero con dolcificante», che obbliga a ribilanciare il resto).
**Il salvataggio crea una ricetta nuova**, non tocca l'originale.

TBD: se la nuova ricetta tiene un legame con quella da cui nasce, e se si vede.

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

`call_site` è oggi `TERM_DECISION`, `TERM_COLLAPSE`, `RECIPE_DRAFT`. Ogni punto di
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
T2 è fatto (2026-09-17). Restano le tre decisioni D1–D3.

**Poi, indipendenti e piccole** — si potevano fare in qualunque momento e non
aspettavano nessuno: **fatte il 2026-09-17** S1, S2, R1, R3, e in parte T1 (header,
tasto indietro, schede d'ingresso). **Resta aperto** solo l'hamburger di T1,
rinviato di proposito alla prima sezione secondaria vera — non c'è fretta, perché
niente lo sblocca.

**Poi, il blocco strutturale**: D4/S5 (non alimentari), S4 (nutrienti ampi), D1
applicata (quantità nelle ricette). Da qui in avanti serve la spec.

**Poi, quel che aspetta lo storage**: R4, e a valle R5, R6.

**Ultimo, quel che ha bisogno di tutto il resto**: Pasti (P1, P2), M1, H1, H2.

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
- **`PantryRow.tsx` è il file più affollato dell'app** (oltre 170 righe, tre stati
  locali oltre alle prop). Estrarre la domanda del rientro in lista («Lo rimetto in
  lista?», con la sua lapide e il suo esito) come componente a sé è il taglio
  naturale, quando qualcuno ci tornerà.
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

---

# Parte XI — Note operative

- Il repo sul server è in **`~/sites/spena`** su `hetznerserver`.
- Deploy: `git pull --ff-only` e poi
  `docker compose -f docker-compose.prod.yml up -d --build --wait`. **Il `-f` non è
  opzionale** — terza lezione di `CLAUDE.md`.
- La suite vera gira **sull'host, non in Docker**: `cd backend && .venv/bin/python -m
  pytest` con Postgres su da `docker compose up -d db`; per il frontend
  `npx vitest run`, `npm run typecheck`, `npm run build`. L'immagine del backend non
  contiene pytest, e `tsc --noEmit` non è il type check di questo progetto (settima
  lezione di `CLAUDE.md`).
- **Tetto di spesa: 1$/giorno su OpenRouter.** Ogni voce che fa girare l'AI su tutto
  il catalogo (R5, S4 di massa) deve fare i conti con questo prima della spec.
