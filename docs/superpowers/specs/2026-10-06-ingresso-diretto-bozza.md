# S3 — Ingresso diretto in dispensa, veloce (bozza)

_Bozza del 2026-10-06, scritta in una fase giorno senza Mattia. Le decisioni marcate
**[da confermare]** hanno una raccomandazione ma aspettano il suo sì; finché ce ne sono, la
voce resta `tbd`._

Voce del backlog: «S3, ingresso diretto in dispensa, veloce» [S3 in `docs/prossimi-passi.md`].

## 1. Il problema

Per mettere in dispensa una confezione col suo codice a barre oggi bisogna scriverla in
lista, spuntarla e passare da «Sistema la spesa». La Dispensa ha solo il + della barra
«Cerca o aggiungi»: apre un `IngredientPicker` che sceglie fra gli ingredienti già in
anagrafica e scrive subito una voce **disponibile, sfusa, senza scadenza**. Non scansiona,
non crea un ingrediente (quel che non c'è lo rimanda alla lista: «scrivilo in lista e
sistemalo da lì»), e non porta la data.

Mattia l'ha chiesto due volte, la seconda (2026-09-27) con un accento: deve essere
**veloce**. I casi sono due:

- torno a casa con una cosa che non avevo scritto, e la confezione è in mano;
- censisco la dispensa la prima volta, o dopo un periodo senza usare l'app: tante
  confezioni di fila.

La spec madre (§8.3) diceva «stesso schermo di 8.2, punto di ingresso diverso, senza voci
di lista da consumare». La lettera non regge alla richiesta di velocità (vedi §3.3), ma lo
spirito sì: **le stesse strade e le stesse guardie**.

## 2. Le due strade: parità subito, o aspettare lo scontrino

### 2.1 Cosa sarebbe lo scontrino

È la fase 2 della spec madre («scansione dello scontrino con riconoscimento testo e
interpretazione AI») e non esiste niente: né la foto, né l'OCR, né il modello che legge le
righe. Uno scontrino italiano scrive righe abbreviate e senza codice a barre
(«YOG.GRECO 0% 170G», «BANANE KG»), spesso troncate a 20-24 caratteri e diverse da catena
a catena. Per farne voci di dispensa servono: una foto leggibile, un OCR (o un modello
visivo su OpenRouter, sotto il tetto di 1 $/giorno), un'interpretazione riga per riga verso
ingrediente e, se possibile, prodotto — con la stessa verifica contro l'anagrafica vera e
lo stesso undo delle altre decisioni dell'AI — e una revisione a mano delle righe incerte.
È un lavoro della taglia dell'import delle ricette, con la sua spec.

E serve a un caso diverso: lo scontrino è **un ingresso in blocco dopo la spesa**, cioè
il caso che «Sistema la spesa» già copre partendo dalla lista. Non è veloce per una
confezione sola: fotografare uno scontrino per un vasetto di yogurt è più lento che
scansionarne il codice.

### 2.2 Confronto

| | A. Parità subito, senza scontrino | B. Aspettare lo scontrino |
|---|---|---|
| Risponde a «veloce» | Sì: scansione e mano dalla Dispensa | No, per mesi: lo scontrino è il pezzo più lungo |
| Costo | Medio: estrazione da `StockingScreen.tsx` più una rotta (§5) | Alto: OCR, AI, revisione, spec nuova, costo per chiamata |
| Rischio | Basso: pezzi che esistono e sono provati | Alto: dati nuovi (righe di scontrino) e una decisione dell'AI in più |
| Lavoro buttato quando arriva lo scontrino | Nessuno, se l'estrazione è fatta bene: le righe dello scontrino diventano voci da risolvere con gli stessi pannelli (§7) | — |
| Dipendenze | Nessuna | Un modello visivo, il suo costo, una revisione |

### 2.3 Raccomandazione: A

**Parità subito, senza scontrino.** È dove la voce pendeva già, ed è l'unica che risponde
alla richiesta così com'è stata fatta. Lo scontrino resta la sua voce (fase 2) e si
progetta sopra i pezzi estratti qui; questa bozza dice in §7 come ci si aggancerà, per non
chiudere la porta. **[da confermare]**, ma la raccomandazione è netta.

## 3. Cosa comporta estrarre scanner, catalogo e modulo

### 3.1 Cosa c'è già, e cosa è già estratto

La buona notizia è che i pannelli **sono già componenti a sé**, in
`frontend/src/features/stocking/`:

| Pezzo | Dipende dalla voce di lista? | Note |
|---|---|---|
| `BarcodeScanner` | No | La fotocamera e il suo ripiego. |
| `ScannerPanel` | **Sì, poco**: prende `item: ShoppingItem` e ne usa solo `raw_text` (titolo e messaggio) | Vive qui, e solo qui, la guardia del codice: il prodotto di un altro ingrediente (S20/409), la cifra di controllo (S20), il codice che segue la voce (S8). **Presuppone l'ingrediente noto** (`ingredientId` obbligatorio). |
| `CatalogSearchPanel` | No: `itemLabel` e `ingredientId` | Cerca solo fra i prodotti di quell'ingrediente. |
| `CustomProductForm` | No: `ingredientId`, `itemLabel`, `barcode`, `suggestion`, `isNonFood` | |
| `OffSuggestionQuestion` | No | La domanda «è davvero …?» prima del modulo (S20). |
| `MatchPanel` | **Sì, poco**: `item.raw_text` | Contiene la creazione dell'ingrediente (S6, S19: il 409 che porta l'ingrediente esistente). |

Quel che **non** è estratto, e che una seconda schermata finirebbe per copiare, è la
**regia** dentro `StockingScreen` (righe 102-561): il tipo `Panel` e le sue transizioni
(`proceedWithNewCode`, `openProductForm`, il passaggio dalla domanda al modulo), il codice
rimasto senza prodotto (`unlinkedCode`, S8) che segue il catalogo e il modulo, la regola
«un esito vale solo se il suo pannello è ancora aperto» (`openPanel`, `isOpen`), la `key`
del modulo che impedisce di salvare il prodotto sbagliato sotto l'ingrediente sbagliato.
Sono le guardie che la prima lezione di `CLAUDE.md` dice di non duplicare: copiate, una
delle due copie resterebbe indietro al primo difetto corretto.

Nel backend lo stesso: `stock_items` (`backend/app/repositories/shopping.py:159`) fa, per
ogni voce, `add_pantry_item` e **dopo** `give_barcode_if_missing` — l'ordine è la guardia
di S8 («il codice va solo a un prodotto che quel controllo ha già riconosciuto»). La rotta
diretta `POST /api/v1/pantry` non accetta né `expires_on` (che `add_pantry_item` già
prende) né `barcode`. Aggiungerli copiando le due righe di `stock_items` sarebbe la
stessa duplicazione, lato server.

### 3.2 L'estrazione proposta

**Frontend**

1. **`ProductResolver`** (nuovo, in `features/stocking/`, nome libero): la regia dei
   pannelli per **un** bersaglio. Riceve `{ key, label, ingredient: {id, name, kind} }` e
   il pannello di partenza (`scanner` | `catalog`), restituisce una `Resolution`
   (`product` col suo eventuale `barcode`) o l'annullamento. Dentro: `Panel`, `unlinkedCode`,
   la domanda di Open Food Facts, il modulo con la sua `key`, la regola dell'esito
   tardivo. `StockingScreen` lo usa per la voce col pannello aperto e tiene per sé ciò che
   è della lista: `resolved` e `expiry` per voce, l'abbinamento salvato sulla voce (S19),
   la sistemazione tutto-o-niente e il suo errore. La Dispensa lo usa per un bersaglio
   solo.
2. **`ScannerPanel`** prende `label: string` al posto di `item`, e `expected` diventa
   facoltativo: `{ ingredientId } | null`. Con l'ingrediente atteso, tutto come oggi. Senza
   (la scansione che parte dalla Dispensa, §4.2) la guardia del 409 non ha niente con cui
   confrontare, e non serve: **il prodotto trovato porta il suo ingrediente**, ed è
   quello che entra. Cifra di controllo e codice nuovo restano identici. Una sola guardia,
   due modi, nello stesso file: è la forma che tiene la lezione.
3. **`IngredientChooser`** (nuovo, estratto da `MatchPanel`): `IngredientPicker` con
   `onCreate` e `createWhen="always"`, più `NewIngredientFields` e la creazione col 409 che
   porta l'esistente. `MatchPanel` diventa titolo + `IngredientChooser` + «Annulla». La
   Dispensa lo usa al posto del picker che oggi rimanda alla lista.
4. `stockingView.ts` e `wording.ts` non cambiano; `CatalogSearchPanel`,
   `CustomProductForm`, `OffSuggestionQuestion`, `BarcodeScanner` nemmeno.

Le prove di schermo che oggi esercitano la regia passando da `StockingScreen.test.tsx`
restano dove sono e devono restare verdi **senza essere toccate**: è la prova che
l'estrazione non ha cambiato niente. `ProductResolver` ne riceve di sue solo per ciò che
la Dispensa aggiunge (il modo senza ingrediente atteso).

**Backend**

5. **`stock_one`** (nome libero), estratta da `stock_items`: `add_pantry_item` più
   `give_barcode_if_missing`, nell'ordine di oggi. `stock_items` la chiama per ogni voce e
   in più chiude la voce di lista; la rotta diretta la chiama una volta.
6. **`PantryItemCreate`** prende `expires_on: date | None` e `barcode: str | None` (senza
   `max_length`, per la stessa ragione di `StockEntryIn`: un codice che non entra in
   colonna non si lega e basta). La rotta `POST /api/v1/pantry` passa da `stock_one`; il
   409 e il 404 restano quelli di oggi.

### 3.3 Perché non «lo stesso schermo» di §8.2

Si potrebbe fare della sistemazione uno schermo con due sorgenti di voci (la lista
spuntata, oppure voci locali scritte o scansionate) e un solo «Metti in dispensa N». È
la lettera della spec madre e il massimo del riuso. Ma è il contrario di veloce: per una
confezione sola sono cinque gesti (apri lo schermo, scrivi o scansiona, scegli la strada,
conferma la voce, metti in dispensa) contro i due di §4.2, e la sistemazione è
tutto-o-niente, che per un ingresso singolo non serve a nessuno. In più la rotta della
sistemazione vuole `shopping_item_id` per ogni voce. Questa forma torna utile con lo
scontrino (§7), che è davvero un ingresso in blocco; per l'ingresso diretto no.

## 4. L'ingresso diretto

### 4.1 Dove

Nella Dispensa, dove c'è già: la barra «Cerca o aggiungi» col +. Accanto al + compare un
secondo pulsante, **«Scansiona»** (icona `barcode`, la stessa di «Sistema la spesa», spec
T3 §3.3), da 44 px. Il pannello dell'ingresso si apre **sotto la barra**, nello stesso
posto dell'aggiunta di oggi, e mentre è aperto le righe della dispensa restano a video (a
differenza della sistemazione, qui non c'è una voce di cui perdere il posto: il pannello è
già in cima).

Due porte, una per caso:

### 4.2 «Scansiona»: la confezione in mano

1. Si apre `ScannerPanel` **senza ingrediente atteso**, titolo «Codice a barre».
2. Il codice trova un prodotto del catalogo → **scheda di conferma** (§4.4) con prodotto,
   marca e ingrediente.
3. Il codice è nuovo e Open Food Facts lo conosce → la scheda chiede prima
   **l'ingrediente** (`IngredientChooser`, che può crearlo), mostrando nome, marca e foto
   del suggerimento perché si sappia di cosa si sta parlando; poi
   `OffSuggestionQuestion` non serve (la domanda «è davvero yogurt greco?» ha senso solo
   quando l'ingrediente c'era prima del codice) e si va dritti al `CustomProductForm`
   precompilato col suggerimento. Creato il prodotto → scheda di conferma.
4. Il codice è nuovo e nessuno lo conosce, o il lookup fallisce → ingrediente, poi il
   modulo vuoto col codice. «Mai un vicolo cieco»: dal modulo si può sempre «Metti in
   dispensa sfuso» con l'ingrediente scelto.
5. Cifra di controllo che non torna: identico a oggi («Usa questo codice lo stesso»).

### 4.3 «+»: il nome, per lo sfuso o quando il codice non c'è

1. Il + apre `IngredientChooser` col testo della barra, come oggi l'aggiunta. A
   differenza di oggi **può creare l'ingrediente** (reparto con `CategorySelect`): il
   rimando alla lista sparisce.
2. Scelto l'ingrediente → scheda di conferma, sfusa. Da lì, **«Codice»** apre
   `ProductResolver` sullo scanner **con** l'ingrediente atteso (guardia del 409 accesa,
   come in sistemazione) e **«Catalogo»** su `CatalogSearchPanel`: sono le tre strade
   della sistemazione, nello stesso ordine e con le stesse icone.

### 4.4 La scheda di conferma

Una scheda sola per le due porte, sotto la barra:

```
┌──────────────────────────────────────────┐
│ [foto] Fage Total 0%            Cambia   │
│        Fage · yogurt greco               │
│ + scadenza                               │
│ [ Metti in dispensa ]   Annulla          │
└──────────────────────────────────────────┘
```

- dice **cosa entra**: prodotto e marca, o «sfuso» e l'ingrediente; la foto se il
  prodotto ce l'ha (`image_url`, vedi anche S12);
- **«+ scadenza»** come in sistemazione (S7): un campo data nativo, facoltativo, con la ✕;
- «Metti in dispensa» è il pulsante primario e prende il fuoco; entra **disponibile**;
- dopo: l'avviso «In dispensa: Fage Total 0%» con **«Annulla»** (archivia la voce
  appena creata, come la ✕ di una riga), la riga nuova portata in vista (`revealId`, come
  oggi), e la barra vuota.

**Perché una scheda e non la scrittura immediata dopo la scansione** **[da confermare]**:
è un tocco in più, ma un codice letto male o un prodotto del catalogo agganciato
all'ingrediente sbagliato finirebbero in dispensa in silenzio — è il «dato sbagliato
scritto in silenzio» di S13. E la scheda è il solo posto dove la scadenza si scrive con la
confezione in mano, che è il senso di D5. Alternativa: scrivere subito e mettere
«Annulla» e «+ scadenza» nell'avviso; più veloce di un tocco, ma l'avviso sparisce da solo
e la data finisce a dopo, sulla riga.

### 4.5 In serie, per il censimento

Dopo «Metti in dispensa» da una scansione, il pannello **non si chiude**: torna allo
scanner pronto per il codice successivo, con l'avviso della voce appena entrata sopra.
Si chiude con la ✕ del pannello. Dal + invece si chiude, come oggi. **[da confermare]** —
raccomandato: il censimento è il secondo caso della richiesta, e riaprire lo scanner a
ogni confezione è il gesto che lo rende lento. La fotocamera resta accesa fra un codice e
l'altro? Oggi no: `BarcodeScanner` rilascia la fotocamera al primo codice letto
(`release`, «l'unica uscita: smontaggio, codice letto, Annulla»). In serie lo scanner va
quindi rimontato a ogni giro (una `key` nuova), che richiede di nuovo il flusso video: il
permesso resta, ma l'accensione costa un attimo. È la scelta conservativa e non tocca
`BarcodeScanner`; da provare sul telefono se l'attesa si sente. Fra un codice e il successivo c'è il tocco su «Metti in dispensa», quindi di solito la
confezione appena letta è già fuori inquadratura quando la fotocamera riparte; se sul
telefono si rilegge lo stesso codice, la scheda lo dice («l'hai appena messo») invece di
scriverlo due volte in silenzio.

## 5. Rotte e dati

- Nessuna tabella nuova, nessuna migrazione.
- `POST /api/v1/pantry`: `PantryItemCreate` + `expires_on` e `barcode` (§3.2.6), via
  `stock_one`. Il 409 «il prodotto appartiene a un altro ingrediente» resta: con lo
  scanner senza ingrediente atteso non è raggiungibile dall'interfaccia (l'ingrediente è
  quello del prodotto), con quello atteso lo ferma la guardia di `ScannerPanel` come in
  sistemazione.
- Prodotto e ingrediente si creano con le rotte di oggi (`createIngredient`,
  `createProduct` dentro `CustomProductForm`).
- Il frontend non decide niente di dominio: il `kind` dell'ingrediente creato lo deriva il
  server dal reparto, come sempre.

## 6. Criteri di accettazione (per il piano)

- Dalla Dispensa, una confezione già a catalogo entra con **due tocchi** dopo aver aperto
  lo scanner: il codice letto e «Metti in dispensa».
- Una confezione con un codice nuovo entra senza passare dalla lista, creando ingrediente
  e prodotto se mancano.
- Uno sfuso entra dal + con l'ingrediente creato al volo se manca; il rimando «scrivilo in
  lista» non esiste più.
- La scadenza si scrive prima di entrare, in entrambe le porte.
- `StockingScreen.test.tsx`, `ScannerPanel.test.tsx`, `MatchPanel.test.tsx` passano senza
  modifiche alle asserzioni (cambiano al più le props con cui si monta `ScannerPanel`).
- Le guardie esistono in un posto solo: `grep` di `valid_checksum`, `unlinkedCode` e
  `give_barcode_if_missing` trova un solo luogo d'uso ciascuno (più i test).
- `e2e/style.spec.ts` misura la Dispensa con lo scanner aperto e con la scheda di
  conferma, nei due temi, a 375 px.
- Typecheck con `npm run typecheck` (non `tsc --noEmit`, vedi `CLAUDE.md`).
- Sul telefono (Mattia): la fotocamera vera in serie, la fotocamera negata, la tastiera
  numerica del codice a mano, la scheda col pollice.

## 7. Come si aggancerà lo scontrino

Lo scontrino produce **righe da risolvere**, ciascuna con un testo e, dopo l'AI, un
ingrediente proposto ed eventualmente un prodotto. È la forma di una voce di lista
spuntata: uno schermo che le mostra per reparto, ognuna con «Codice / Catalogo / Sfuso»
via `ProductResolver`, e un «Metti in dispensa N» tutto-o-niente. Cioè la sistemazione
con una sorgente diversa — la forma scartata in §3.3 per l'ingresso singolo, giusta per
l'ingresso in blocco. Con l'estrazione di §3.2 quella sorgente diversa costa una
rotta e lo stato delle righe, non una seconda copia dei pannelli. In più, in
sistemazione lo scontrino può **spuntare** le voci di lista che riconosce, che è il
pezzo più utile e non tocca l'ingresso diretto.

## 8. Decisioni per Mattia

1. **Strada A (parità subito, scontrino dopo)** — raccomandata, §2.3.
2. **Scheda di conferma prima di scrivere** (un tocco in più) o scrittura immediata con
   «Annulla» nell'avviso — raccomandata la scheda, §4.4.
3. **Scansione in serie** dopo una conferma — raccomandata sì, §4.5.
4. **Una voce già in lista** (in attesa o spuntata) che entra dall'ingresso diretto: la
   lista continua a chiederla. Raccomandato **fuori da questa voce**: l'ingresso diretto
   serve per quel che non era scritto, e la sistemazione resta la strada per la lista. Se
   capita spesso, una voce a sé: la scheda di conferma direbbe «è anche in lista» con
   «Toglila».
5. **Nomi**: «Scansiona» accanto al +, e «Metti in dispensa» anche qui (lo stesso verbo
   della sistemazione). Raccomandati.

## 9. Fuori scope

- Lo scontrino (fase 2, voce a sé).
- La foto dell'etichetta per i nutrienti (fase 2).
- Lo stato all'ingresso diverso da «disponibile» (si corregge con le tacche della riga).
- Distinguere due confezioni dello stesso prodotto (idea già nel backlog).
- La quantità: la dispensa non ne ha, per la decisione fondante 1.
- Desktop.
