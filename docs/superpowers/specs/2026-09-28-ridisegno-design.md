# T3 — Il ridisegno: un linguaggio visivo solo, poi le schermate una alla volta

**Data:** 2026-09-28. **Voce:** T3 di `docs/prossimi-passi.md`, con l'esito del giro del
2026-09-27 (99 osservazioni). **Deciso con Mattia** nel brainstorming dello stesso giorno,
su bozze viste a video; le scelte sotto sono sue, salvo dove è scritto «deciso qui».

## 1. Perché adesso

Ogni voce nuova aggiunge componenti nello stile di oggi, che è già incoerente (tre
aspetti per lo stesso selettore d'ingrediente, cinque forme d'errore, tre colori per
«finito») e che andrebbero poi rifatti uno per uno. Il ridisegno viene prima, perché da lì
in poi ogni componente nasce nello stile nuovo.

## 2. Le decisioni

| Tema | Decisione |
|---|---|
| Direzione | **«Nitido»** (bianco e verde, righe fitte, contrasto alto) con due cose prese da «Vivace»: le **sezioni con titolo, icona e fondo proprio**, e il **riepilogo delle scadenze** in cima alla Dispensa. |
| Sezioni | Una scheda bianca per reparto sul fondo grigio-verde della pagina; in testa un quadratino colorato con l'icona del reparto, il nome e il conteggio. **Dentro la sezione nessuna linea fra le righe**: lo spazio basta a separarle e la sezione resta un blocco solo. |
| Riga di una voce | Nome sopra; sotto, in piccolo, prodotto e scadenza; a destra quanto resta. |
| Quanto resta | **Tre tacche, e sono il controllo** (§4.4). Il cursore sparisce. |
| Barra in cima | Campo + pulsante **+** accanto, sulla stessa riga. |
| Regola delle icone | **Più pulsanti in gruppo → solo icone. Un pulsante da solo → icona e testo.** Ogni pulsante di sola icona ha il nome completo come `aria-label`. |
| Marchio | **Il cesto**, ovunque: login, icona dell'app, favicon e intestazione. La pentola dell'intestazione (T1) se ne va. |
| Ricettario | **Righe compatte con miniatura**, non schede con la foto a tutta larghezza. **«+ Nuova»** in alto a destra nell'intestazione. |
| Tema scuro | Sì, e **segue l'impostazione del telefono** (`prefers-color-scheme`). Nessun interruttore nell'app (deciso qui: YAGNI). |
| Libreria di icone | **Tabler** (`@tabler/icons-react`), la stessa delle bozze: le icone giudicate da Mattia sono quelle che vedrà. Nel pacchetto entra solo ciò che si importa (deciso qui). |
| Carattere | **Inter**, servito dall'app (`@fontsource-variable/inter`), non da Google: la PWA deve funzionare offline e non chiamare terzi (deciso qui). |
| Consegna | **Strada B**: prima le fondamenta, in produzione; poi una schermata alla volta, ciascuna in produzione dopo il via di Mattia e la sua prova sul telefono. Per qualche giorno le schermate non ancora rifatte restano nello stile vecchio, ma con i colori nuovi (§3.1). |

## 3. Consegna 0 — Le fondamenta

Niente schermata cambia disposizione in questa consegna. Cambiano i token, e con loro
colori e carattere di tutta l'app, e nascono le primitive che le consegne seguenti useranno.

### 3.1 I colori

Restano un blocco `@theme` in `frontend/src/index.css`, la sola casa dei colori (regola di
`CLAUDE.md`). Il tema scuro ridefinisce le stesse variabili sotto
`@media (prefers-color-scheme: dark)`: nessuna schermata sa in che tema è.

| Token | Chiaro | Scuro | Uso |
|---|---|---|---|
| `page` | `#f1f4f2` | `#0e1210` | fondo |
| `card` | `#ffffff` | `#171c19` | sezioni, campi |
| `ink` / `ink-soft` / `ink-faint` | `#101512` / `#4e5a52` / `#636e66` | `#e7ece9` / `#b4beb8` / `#8f9a94` | testo |
| `line` | `#e1e6e3` | `#28302b` | bordi di campi e pulsanti, non fra le righe |
| `brand` | `#0f7a4a` | `#3cb878` | azione principale, «c'è», tacche piene |
| `low` | `#9a5f0c` (testo) / `#c98a1a` (tacca) | `#e0a63a` | «sta finendo» |
| `finished` | `#b3261e` | `#ff8a80` | «finito», ingrediente mancante |
| `danger` | = `finished` | = `finished` | errori |
| `expiry` | `#5b45a8` | `#b9a6ff` | scadenza |
| cinque tinte di reparto | §3.3 | §3.3 | solo il quadratino del titolo di sezione |

I valori esatti si fissano nella Consegna 0 misurandoli, non a occhio: **ogni coppia testo
su fondo sta sopra 4,5:1**, in chiaro e in scuro, e chi porta testo bianco (o nero, sul verde
scuro) pure. È il vincolo di sempre, scritto in `index.css`: l'app si legge in corsia, al sole.

**Un colore per stato, deciso una volta** (osservazione del giro: «finito» aveva tre colori).
`STATUS_TONE` diventa l'unica mappa stato → token, e la leggono tacche, pallini, pastiglie e
foglio della cottura. Il rosso di «finito» può coincidere con quello degli errori perché la
✕ **non è più rossa**: diventa un'icona grigia, e il rosso resta a «manca» e «non è andata».

### 3.2 Carattere e misure

- Inter a 400, 500 e 600. Titolo di schermata 24/600 con `letter-spacing` leggermente
  negativo; titolo di sezione 14/600; nome di riga 14–15/500; riga secondaria 12/400.
- **I campi restano a 16 px**: sotto quella misura iOS ingrandisce la pagina (da non
  riprogettare via, dal giro).
- **Ogni bersaglio tocca almeno 44×44 px**, anche quando ciò che si vede è più piccolo
  (le tacche, le icone): l'area di tocco è del pulsante, non del disegno.
- Raggi: 16 px le sezioni, 10–12 px campi e pulsanti.

### 3.3 Le icone

**Reparti** (i 14 di `frontend/src/domain/categories.ts`), con cinque tinte per famiglia,
scelte lontane da verde, giallo, rosso e viola, che vogliono già dire «c'è», «sta finendo»,
«finito» e «scade»:

| Tinta | Reparti e icona |
|---|---|
| pesca | verdura `carrot`, frutta `apple` |
| rosa | carne `meat`, dolci `cookie` |
| azzurro | pesce `fish`, latticini `cheese`, bevande `glass-full` |
| sabbia | cereali `wheat`, legumi `seedling`, condimenti `bottle`, spezie `pepper` |
| ardesia | altro `package`, casa `spray`, igiene `bath` |

La mappa reparto → icona e tinta vive in un posto solo, accanto a `categories.ts`, e un test
controlla che copra ogni reparto (come `test_frontend_categories.py` fa con l'elenco).

**Azioni:**

| Dove | Azione → icona |
|---|---|
| Ovunque | menu `menu-2`, indietro `chevron-left`, chiudi/togli `x`, cerca `search`, aggiungi `plus`, annulla `arrow-back-up`, riprova `refresh` |
| Lista | sistema la spesa `basket-check`, togli le spuntate `clear-all` |
| Sistema la spesa | leggi il codice `barcode`, cerca a catalogo `list-search`, sfuso `scale`, crea a mano `pencil-plus`, cambia `replace`, scadenza `calendar-plus`, metti in dispensa `package-import` |
| Dispensa | rimetti in lista `shopping-cart-plus`, in scadenza `calendar-event` |
| Ricette | filtri `adjustments-horizontal`, nuova ricetta `pencil-plus`, scrivi con l'AI `sparkles`, ingredienti da abbinare `link`, cucina `chef-hat`, ho cucinato `circle-check`, mancanti in lista `shopping-cart-plus`, modifica `pencil`, elimina `trash`, ripristina `restore`, apri l'originale `external-link` |
| Anagrafica | rinomina `cursor-text`, cambia reparto `category`, sposta sotto `arrows-transfer-down`, unisci `arrows-join-2`, togli il codice `barcode-off` |
| Barra delle schede | Lista `list-check`, Dispensa `box`, Ricette `tools-kitchen-2` |

Due icone ripetute di proposito, perché vogliono dire la stessa cosa: la **matita con il +**
è «creare a mano» (prodotto, ricetta), il **carrello con il +** è «va in lista» (voce finita,
mancanti di una ricetta).

### 3.4 Il marchio

Il cesto che oggi è al login, nella favicon e nelle icone della PWA (`frontend/public/`)
diventa anche il segno dell'intestazione (`AppHeader.tsx`), al posto della pentola. Resta un
SVG disegnato a mano: la libreria di icone serve alle azioni, non al marchio.

### 3.5 Le primitive

In `frontend/src/components/ui/`. Ognuna sostituisce le copie sparse che il giro ha contato,
e le consegne seguenti migrano le schermate su di esse.

- **`Button`** — varianti `primary` (una sola per vista), `secondary`, `ghost`, `danger`;
  con icona e testo, o **solo icona**, nel qual caso `label` è obbligatorio nel tipo, così un
  pulsante muto non compila. Sostituisce `buttonClasses`.
- **`IconToolbar`** — un gruppo di pulsanti di sola icona: la regola del §2 in un componente.
- **`ActionBar`** — il campo più il **+** della barra in cima. Il segnaposto del campo fa da
  etichetta al +, che ha comunque il suo `aria-label`.
- **`Section`** — la scheda di reparto: quadratino con icona e tinta, titolo, conteggio,
  righe senza separatori. Prende il reparto e trova da sé icona e tinta.
- **`StockGauge`** — le tre tacche, §4.4.
- **`StatusDot`** — il pallino dello stato di un ingrediente di ricetta.
- **`Chip`** — pastiglie di stato e di scadenza; sostituisce `StatusChip` ed `ExpiryChip`.
- **`Notice`** — l'**avviso di conferma unico** (resto di T4): in basso, sopra la barra delle
  schede, fondo scuro, testo breve, un'azione facoltativa («Annulla», «Vedi»), dura 6 secondi
  e lo dice con una barra che si accorcia (dal giro: «la lapide dura 6 secondi e non lo
  dice»). `role="status"`. Assorbe la lapide di dispensa e ricettario.
- **`ErrorState`** — l'**errore di caricamento unico**: cosa non è andato, che il dato è
  ancora lì quando lo è, e sempre **«Riprova»**. Sostituisce le cinque forme del giro.
- **`EmptyState`** — titolo, una riga, un'azione.
- **`IngredientPicker`** — **uno solo** per lista, dispensa, ricette e sistemazione (il giro
  ne ha trovati tre). ARIA valido (`listbox` > `option`, niente `listitem` in mezzo); nome
  accessibile del solo ingrediente, con il reparto come descrizione, non fuso («Caffèbevande»);
  quando non trova niente offre **«Aggiungi «…»»** (è R12, che così si chiude qui).
- **`Screen`** — titolo, azione in alto a destra, contenuto; e **`TabBar`** con le icone,
  che segna «Lista» anche su `/sistema` (osservazione del giro).

### 3.6 Cosa esce in produzione con la Consegna 0

I token nuovi (colori chiari e scuri, Inter), il cesto nell'intestazione, la barra delle
schede con le icone, la rotta `*` che manda a una pagina «Non trovata» con un link a Lista
(oggi un indirizzo inesistente dà una pagina vuota), e le primitive con i loro test. Le
schermate prendono colori e carattere nuovi attraverso i token, senza cambiare disposizione.
Perché regga, ogni schermata di oggi deve già passare dal tema scuro senza testo illeggibile:
la Consegna 0 lo misura su tutte.

## 4. Consegne 1–6 — Le schermate

Ogni consegna porta una schermata sulle primitive e ci chiude le osservazioni del giro che
la riguardano. Ciò che è elencato in «Da non riprogettare via» nel giro resta com'è.

### 4.1 Consegna 1 — Dispensa

- **Barra «Cerca o aggiungi» con il +**: scrivendo filtra le righe della dispensa (è S11);
  il + apre l'aggiunta di oggi con quel testo. Assorbe «Aggiungi in dispensa».
- **Riepilogo delle scadenze** sotto la barra, solo se c'è qualcosa: «N in scadenza questa
  settimana», in viola; toccandolo mostra solo quelle righe. Il conteggio usa `expiry`
  (`"soon"` / `"expired"`) che arriva già deciso dal backend: il 7 non entra nel TypeScript.
- **Sezioni per reparto** (`Section`). Le righe finite vanno **in fondo alla loro sezione**,
  nell'ordine stabile di S21.
- **Riga**: nome; sotto prodotto (o «sfuso») e scadenza **relativa** sotto i 7 giorni («tra 3
  gg», «oggi», «scaduto ieri»), assoluta oltre; a destra `StockGauge`. Il nome resta il link
  alla scheda di S9.
- **Finito**: la riga mostra «Finito» in rosso e il pulsante **«In lista»** (carrello con +,
  icona e testo perché è da solo). Sostituisce «Lo rimetto in lista? Sì / No», che aveva
  bersagli da 35 px; ignorarlo è il «No». La risposta `added: false` diventa l'avviso «Era già
  in lista.».
- **Togli** (la ✕, grigia) → `Notice` con «Annulla».
- **Nessuna percentuale.** `FillSlider` e `fillZones` escono; le tacche mandano `status`.
  `fill_percent` resta nel database, annullabile, e non lo scrive più nessuno: `set_status`
  lo azzera già. Nessuna migrazione. `CLAUDE.md` e la nota sotto D1 si aggiornano: la colonna
  non è più la posizione di un cursore che esiste.

### 4.2 Consegna 2 — Lista

- Barra con campo «Cosa manca?» e +; il comportamento di S18 («latte» + Invio si aggancia,
  «Era già in lista.») non cambia.
- Scheda d'ingresso «Sistema la spesa · N nel carrello».
- Sezioni per reparto; le voci spuntate **in fondo al loro reparto**.
- La ✕ archivia e mostra `Notice` con «Annulla», che rimette la voce nello stato che aveva
  (da comprare o nel carrello) con la `PATCH` di sempre (osservazione: la lista non aveva la
  lapide che la dispensa ha).
- La barra in cima non copre più l'intestazione scorrendo (oggi sono due `sticky top-0`
  con lo stesso `z-index`).

### 4.3 Consegna 3 — Sistema la spesa

- **Una riga per voce**: nome e, a destra, le tre icone **codice / catalogo / sfuso**
  (`IconToolbar`). Una voce risolta dice **cosa** («Sfuso», o il nome del prodotto) e ha
  «Cambia» come icona `replace`, non come un'azione principale.
- **I pannelli si aprono sotto la voce che li ha chiesti** e ci portano la vista (è S10):
  scanner, catalogo e modulo del prodotto.
- **La voce non abbinata** è chiusa: una riga con «Abbina», che apre il `IngredientPicker`.
  Creando l'ingrediente il nome parte dal testo della voce ma è un campo da correggere, con
  la domanda «Come si chiama in generale?» (dal giro: «zucchine tonde di Nizza della signora
  Pina» diventava il nome).
- **«È di un altro ingrediente»** dice quale, e non è rosso: non è un guasto.
- **Il catalogo** non dà più due messaggi che si contraddicono; l'esempio «yogurt greco»
  non compare cercando altro.
- **«+ scadenza»** apre un campo con etichetta visibile e una ✕ per richiuderlo.
- **Le voci stanno nell'ordine per reparto della lista.**
- **«Metti in dispensa»** dice quante voci entrano («Metti in dispensa 4»); dopo, un `Notice`
  in Dispensa: «4 in dispensa · 3 restano in lista» (T4).
- **Niente da sistemare**: `EmptyState` con un link a Lista, senza il pulsante spento.

### 4.4 Il controllo `StockGauge`

Tre tacche orizzontali a destra della riga. **Il livello arriva fino alla tacca toccata**:

| Tacca toccata | Stato mandato | Come appare |
|---|---|---|
| terza | `available` | tre tacche verdi |
| seconda | `low` | due tacche gialle |
| prima | `finished` | una tacca rossa |

Ogni stato ha almeno una tacca accesa, e la tacca toccata è sempre l'ultima accesa: si tocca
dove si vuole che arrivi. Ogni tacca è un bersaglio di 44 px (le tre insieme ne occupano
circa 132), il disegno è una barretta di circa 16×6. Toccare la tacca dello stato attuale
non manda niente.

- **Accessibilità**: `radiogroup` con tre `radio` chiamati «c'è», «sta finendo», «finito»;
  le frecce della tastiera scorrono fra loro, come oggi il cursore.
- **Lo scorrimento**: un gesto che si muove oltre 10 px non è un tocco (la stessa regola di
  S13), così scorrere partendo dalle tacche non cambia mai uno stato.
- **Dove si usa**: in Dispensa e nel **foglio della cottura**, al posto dei suoi tre pulsanti
  (dal giro: «lo stesso giudizio ha due controlli»).

### 4.5 Consegna 4 — Ricette

- **«+ Nuova»** in alto a destra: apre il modulo di R10, da cui si può ancora chiedere la
  bozza all'AI. «Scrivi con l'AI» smette di essere l'ingresso del modulo.
- **Barra di ricerca** con accanto il pulsante **Filtri**, con il numero dei filtri attivi;
  categoria e ingredienti stanno in un pannello che conta i risultati e ha «Azzera». La
  prima ricetta sale nella prima schermata.
- **La scala «Tutte / Ora / +1 / +2 / +3»** ha un'etichetta visibile: «Cosa posso cucinare».
- **Righe compatte**: miniatura di 56 px (la foto; l'icona del reparto principale se la
  ricetta non ne ha, mai un rettangolo bianco mentre carica), titolo, **«Hai tutto»** o
  **«Manca: …»** da `missing_names`, poi categoria e costo.
- **La scheda «Ingredienti da abbinare»** compare solo quando la coda non è vuota.

### 4.6 Consegna 5 — Dettaglio ricetta

- Foto in alto con il tasto indietro sopra; titolo, categoria e costo.
- **Modifica ed Elimina** come `IconToolbar` accanto al titolo.
- **Il costo si legge e basta**: si cambia da «Modifica», dove il modulo di R10 ce l'ha già.
  Oggi un tocco scorrendo sui € lo cambiava (osservazione del giro).
- **Porzioni**: lo stepper si vede sempre; senza porzioni dice «porzioni non indicate»
  invece di sparire.
- **Ingredienti**, divisi in Principali e Secondari, con il `StatusDot` per riga preso da
  `availability` e `satisfied`, che il backend già manda e nessuna schermata leggeva.
- **Nuovo: «Metti in lista ciò che manca»** (carrello con +): per ogni riga non soddisfatta
  chiama la `POST /shopping-list` con l'ingrediente, che già non crea doppioni (S18); un
  `Notice` riassume («2 in lista · 1 c'era già»). Nessuna rotta nuova: quali righe mancano lo
  dice `satisfied`, che viene dal backend, quindi il frontend non calcola la cucinabilità.
- **«Cucina»**, icona e testo, pulsante principale in fondo agli ingredienti; il foglio usa
  `StockGauge`. «Ho cucinato» mostra l'esito con `Notice` (T4 era già fatto con
  `revealAtTop`; resta il comportamento, cambia la forma).
- **«Apri l'originale»** alto 44 px.

### 4.7 Consegna 6 — Il resto

- **Modulo della ricetta** (R10): «Proponi» secondario, «Salva» principale; caselle da 44 px;
  il `IngredientPicker` unico, con «Aggiungi «…»» (R12). Il guasto dell'AI ha un colore solo
  in tutta l'app.
- **Anagrafica e schede di S9**: le azioni come `IconToolbar` (rinomina, reparto, sposta,
  unisci, togli il codice); «Cerca in anagrafica» diventa «Cerca un ingrediente o un
  prodotto».
- **Coda d'import**: l'AI non configurata non è rossa, non cita `OPENROUTER_API_KEY`, e non
  compare a coda vuota; il suggerimento testuale non è più grande del resto; l'annulla passa
  da `Notice`.
- **Accesso**: il campo prende il fuoco all'apertura, «Password errata» se ne va appena si
  riscrive, **«Mostra password»** con l'icona `eye`.
- **Parole a video**: via «backend», «dataset» e i nomi di variabili; maiuscole degli
  ingredienti uniformi; accordi («Tolto dalla dispensa: kiwi», «collegato ad astice»).

## 5. Fuori da questo lavoro

Restano voci a sé in `docs/prossimi-passi.md`, perché non sono stile né disposizione:

- **i suggerimenti rumorosi** (sempre dieci righe): una soglia nel backend;
- **«1 ricetta in attesa» con due ricette sotto**: il riconteggio in `undo_decision`;
- **i minuti di una ricetta**: stanno nei dati grezzi dell'import, non nel modello;
- **il procedimento diviso in passi**, e i numeri spuri dell'import;
- **tecniche e preparazioni mescolate alle ricette**;
- **«N dosi su M non si riscalano»** che non dice quali (Parte X);
- **il layout da desktop** (una colonna da 448 px: non si rompe niente);
- **S3, S12 oltre alle icone, S14, S15**, e tutto Parte IV e oltre.

## 6. Come si verifica

Per ogni consegna, prima del deploy:

- `npx vitest run`, `npm run lint`, `npm run typecheck`, `npm run build`, e la suite del
  backend se la consegna lo tocca;
- **`frontend/e2e/style.spec.ts` misura nel browser**, perché jsdom non calcola il CSS
  (quarta lezione di `CLAUDE.md`): il contrasto di ogni coppia di token **in chiaro e in
  scuro** (Playwright con `colorScheme: "dark"`), 44 px su ogni bersaglio nuovo, nessuno
  scorrimento orizzontale a 375 px, il carattere caricato davvero, un nome accessibile su
  ogni pulsante di sola icona;
- l'e2e intera sullo stack `spena-e2e`;
- un giro in un browser vero a 375 px, in chiaro e in scuro;
- poi il via di Mattia per il deploy, e la sua prova sul telefono.

**Nomi accessibili stabili.** Un pulsante che diventa di sola icona tiene come `aria-label`
il testo che aveva: i test che lo cercano per ruolo e nome restano validi, e ciò che uno
screen reader legge non cambia.

## 7. Rischi

- **Il tema scuro sulle schermate non ancora rifatte.** Prendono i token nuovi dalla
  Consegna 0: se una usa un colore fuori token, in scuro si legge male. La Consegna 0 misura
  ogni schermata in scuro, e il grep di `CLAUDE.md` (`emerald`, `neutral-`) resta vuoto.
- **Le tacche al posto del cursore** sono la scelta che cambia di più l'uso quotidiano, e
  nessun test dice se si toccano bene col pollice. È la prima cosa da provare sul telefono
  dopo la Consegna 1.
- **`@tabler/icons-react` è una dipendenza nuova**, e grande se importata male: si importa
  icona per icona, e la build della Consegna 0 confronta le dimensioni del pacchetto prima e
  dopo.
