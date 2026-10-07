# Suggerimenti degli ingredienti: dove tagliare la lista — bozza

**Data:** 2026-10-06, fase di ricerca notturna, senza Mattia. **Voce:** «I suggerimenti
degli ingredienti sono sempre dieci righe, anche quando non somigliano più: una soglia o un
salto di punteggio nel backend — TBD: quale criterio» di `next-steps.md` ([T3, esito del
giro]). È una bozza: niente è deciso. Le domande stanno nelle «Decisioni per Mattia» in
fondo, ognuna con la sua raccomandazione.

I numeri vengono da script rimasti nello scratchpad della notte. Il metodo, le regole con
cui sono costruiti i dati e l'SQL della misura sono al §3 e in appendice, così chiunque può
rifarli.

## 1. Contesto

Dal giro di T3 (`docs/prossimi-passi.md`, «I suggerimenti sono rumorosi», riga 2371): sono
sempre dieci righe, anche quando dopo la terza non somigliano più («zucch» → Zucchero prima
di Zucchina). Un tocco sbagliato lega la voce all'ingrediente sbagliato, e poi tocca a S9
correggere. La nota chiede di sistemarlo lato server, con una soglia o con un salto di
punteggio.

La misura dice che i due esempi del giro sono due problemi diversi:

- **La coda** (le righe dalla quarta in giù) è rumore vero. Oggi, sui prefissi digitati, una
  lista ha in media 4,7 righe che non contengono il testo digitato, e le hanno il 90 % delle
  liste. Un criterio di taglio la toglie quasi tutta, senza perdere il bersaglio (§5).
- **Zucchero prima di Zucchina** non è rumore. Tutti e due cominciano con «zucch», hanno
  la stessa somiglianza trigram (0,500 e 0,500: stessi cinque trigrammi in comune, stessa
  lunghezza), e oggi li separa solo l'ordine alfabetico, o in produzione il numero di
  acquisti. Nessuna soglia e nessun salto li può separare, perché il testo digitato non li
  distingue. Basta una lettera in più: con «zucchi» resta solo Zucchina (§5.4).

## 2. La query di oggi

**Il percorso.** I suggerimenti di `IngredientPicker`
(`frontend/src/components/IngredientPicker.tsx`) arrivano da
`GET /api/v1/ingredients/search?q=…[&kind=food]` (`frontend/src/features/shopping-list/api.ts:28-33`).
La stessa chiamata alimenta il campo della lista (`AddItemField.tsx:32-36`) e la ricerca
dell'Anagrafica (`RegistryScreen.tsx:65-69`). Il frontend chiede solo da 2 caratteri in su
(`IngredientPicker.tsx:76`), con 180 ms di attesa (riga 10), e non passa `limit`: vale il
default dell'endpoint, 10 (`backend/app/api/ingredients.py:47-53`, massimo 50).

**La funzione.** `search_ingredients` in `backend/app/repositories/ingredients.py:14-85`:

- il testo viene solo ripulito e messo in minuscolo (`query.strip().lower()`, riga 31).
  Niente `unaccent`: «caffe» non è un prefisso di «caffè»;
- per ogni ingrediente, `best = greatest(similarity(name, q), max(similarity(alias, q)))`
  (righe 42-44): `similarity` di pg_trgm su tutta la stringa. Non usa `word_similarity`, né
  l'operatore `%`, né gli embeddings;
- `is_prefix = name LIKE 'q%' OR bool_or(alias LIKE 'q%')` (righe 46-48), sensibile alle
  maiuscole su nomi e alias già minuscoli. Il testo non viene protetto: un `%` o un `_`
  digitati fanno da caratteri jolly;
- `purchase_count`: quante righe di lista hanno quell'ingrediente (righe 35-40 e 50);
- `HAVING best >= 0.15 OR is_prefix` (riga 68, `SIMILARITY_FLOOR = 0.15` alla riga 11);
- `ORDER BY` (righe 69-81): prima i prefissi; fra i prefissi, gli acquisti; poi `best`;
  poi gli acquisti come spareggio; infine il nome in ordine alfabetico;
- `LIMIT 10` (riga 82).

Quindi la lista è fatta così: prima tutti i prefissi, poi tutti gli sfumati fino a dieci,
purché abbiano almeno 0,15. Sopra lo 0,15 non c'è nessun taglio.

**Gli altri chiamanti.** `search_ingredients` non serve solo ai suggerimenti:
`services/ingredient_match.py:111` la chiama con `limit=1` per proporre (marcato incerto)
l'ingrediente di un nome che non coincide con niente, e
`services/recipe_import/decide.py:345` con `limit=3` (`NEIGHBOURS_PER_NAME`, riga 302) per
dare all'AI i vicini di un ingrediente da creare. Lì gli sfumati sono il punto: un taglio
non deve arrivarci (decisione 3).

## 3. Metodo

### 3.1 I dati

Il database di sviluppo non ha dati: `spena` non ha nessuna tabella (le migrazioni non sono
state applicate), e `spena_test` ha le tabelle vuote. Per questo la misura non legge nessuna
tabella. L'anagrafica viaggia dentro la query come JSON, e la query riproduce
`search_ingredients` sopra quel JSON (appendice A). Gira su `spena_test`, che ha pg_trgm,
dentro una transazione `READ ONLY`, con Postgres 16.15 e la stessa collation `en_US.utf8`.
Il controllo di fedeltà: `similarity('pomodoro','pomodorr')` = 0,636 e
`similarity('pomodorini','pomodorr')` = 0,538, gli stessi numeri del docstring di
`test_fuzzy_match_ranks_by_similarity_not_frequency`.

Due anagrafiche, tutte e due dai file pubblici del repository:

| Anagrafica | Da dove viene | Ingredienti | Alias |
|---|---|---|---|
| **seme** | `data/ingredients_seed.json`, com'è: è quello che `python -m app.cli.seed` carica in sviluppo | 187 | 299 |
| **corretta** | il seme più `data/fixes/2026-09-27-anagrafica.json` applicato a mano: un `merge` sposta gli alias e fa del nome perdente un alias del vincitore (come `services/registry.py:594`); `remap` e `decide` aggiungono il termine come alias del suo ingrediente, e creano l'ingrediente se serve; `move_alias` sposta; `rename` col nuovo nome rinomina | 276 | 476 |

La produzione ha 884 ingredienti dopo la revisione dell'anagrafica di R4 (erano 935 dopo l'import completo, poi 952, poi 884: `prossimi-passi.md`, righe 29 e 1430), e circa 1.830 termini decisi
dall'AI, da sé o a mano, che sono quasi tutti alias, più i 299 del seme
(`prossimi-passi.md`, righe 1386-1393; il numero esatto degli alias non è scritto). Le due anagrafiche sono più piccole, e la differenza va in una
direzione sola: passando da 187 a 276 ingredienti, le liste da dieci righe salgono dal
16 % al 36 % dei prefissi digitati (§4). Con 884 ingredienti la coda di oggi sarà più
lunga e più rumorosa di quanto misurato qui, mentre le righe che il criterio raccomandato
tiene restano quelle che contengono il testo, e crescono solo quanto crescono gli
ingredienti che lo contengono davvero.

`purchase_count` vale 0 per tutti, perché in sviluppo la lista è vuota. Conta solo per
l'ordine fra i prefissi, e nessun criterio provato qui dipende dall'ordine fra i prefissi.

### 3.2 L'insieme di prove

Il seed del campionamento è fisso, `20261006`. Le prove sono generate per ciascuna
anagrafica (seme: 2.416, corretta: 3.413):

- **prefissi** (famiglia «digitazione»): per ogni ingrediente (tutti: sono meno di 300), i
  prefissi di 3, 4, 5 e 6 caratteri e il nome intero. Il bersaglio è l'ingrediente da cui
  viene il prefisso;
- **alias** (anche loro in «digitazione»): un campione di alias (fino a 150), con i
  prefissi di 4 e 6 caratteri e l'alias intero. Il bersaglio è l'ingrediente dell'alias
  (chi scrive «pelati» vuole il pomodoro);
- **casi a mano** (in «digitazione»): 43 prove come «zucch» → zucchina, «latt» → latte,
  «pomod» → pomodoro, «olio» → olio di oliva, «uov» → uova, «parmig» → parmigiano,
  «caffe» → caffè, «pollo» → petto di pollo, «pelati» → pomodoro (tabella al §5.4);
- **2 caratteri**: i prefissi di 2 caratteri, tenuti a parte perché il frontend chiede da
  2 caratteri e la somiglianza trigram lì non dice quasi niente;
- **refusi**: sul nome intero (se ha almeno 5 lettere) e sui suoi primi 6 caratteri, tre
  refusi per parola: una lettera mancante, due lettere vicine scambiate, una lettera
  sostituita. Il bersaglio resta l'ingrediente di partenza;
- **assenti**: i 90 ingredienti dell'anagrafica corretta che il seme non ha, né come nome né
  come alias (cibi veri, come «barbabietola»), cercati nell'anagrafica del seme, interi e
  con il prefisso di 5 caratteri (175 prove). Qui un bersaglio non c'è: la cosa giusta è una
  lista corta o vuota, che lascia vedere «Aggiungi «…»» o la nota del chiamante.

### 3.3 Il criterio di pertinenza

Una riga è **pertinente** se è il bersaglio, oppure se, senza accenti, **il nome contiene
il testo all'inizio di una parola** (inizio, dopo uno spazio, un apostrofo o un trattino),
oppure **un suo alias comincia con il testo**. Per i refusi il «testo» è quello giusto, da
cui è nato il refuso. Il criterio è stretto di proposito: «olio» non trova pertinente
«Tonno in scatola», anche se ha l'alias «tonno sott'olio», perché la riga mostra «Tonno in
scatola» e a chi legge sembra rumore. Le tabelle danno anche il conteggio largo, che accetta
il testo all'inizio di una parola in un alias qualunque.

Una cautela: per le prove di digitazione la pertinenza coincide con il segnale che usa il
criterio raccomandato, quindi lì «0 non pertinenti» vale per costruzione. La misura
indipendente è il **richiamo**: quante volte il bersaglio resta in lista.

## 4. Come sono i punteggi oggi

Anagrafica corretta, lista di oggi, prove di digitazione (1.736). `best` è il punteggio
della funzione, «salto» è quanto cala `best` rispetto alla riga di sopra:

| pos | liste che ci arrivano | best p25 | p50 | p75 | prefissi % | pertinenti % | salto p50 | salto p90 |
|---|---|---|---|---|---|---|---|---|
| 1 | 1.736 | 0,40 | 0,55 | 1,00 | 100 | 100 | – | – |
| 2 | 1.629 | 0,22 | 0,29 | 0,38 | 38 | 42 | 0,24 | 0,73 |
| 3 | 1.493 | 0,20 | 0,24 | 0,30 | 24 | 29 | 0,04 | 0,16 |
| 4 | 1.339 | 0,18 | 0,21 | 0,27 | 19 | 24 | 0,02 | 0,09 |
| 5 | 1.204 | 0,17 | 0,20 | 0,25 | 11 | 16 | 0,02 | 0,06 |
| 6 | 1.049 | 0,18 | 0,20 | 0,25 | 6 | 15 | 0,01 | 0,06 |
| 7 | 925 | 0,17 | 0,19 | 0,22 | 4 | 12 | 0,01 | 0,05 |
| 8 | 851 | 0,17 | 0,18 | 0,21 | 1 | 10 | 0,01 | 0,04 |
| 9 | 741 | 0,17 | 0,18 | 0,20 | 1 | 9 | 0,01 | 0,03 |
| 10 | 628 | 0,17 | 0,17 | 0,19 | 1 | 7 | 0,01 | 0,03 |

- Il bersaglio è primo nell'80,8 % delle prove, secondo nel 10,8 %, fra il terzo e il
  decimo nell'8,4 %; il suo `best` ha mediana 0,50, e il 10 % sta sotto 0,25.
- Righe pertinenti per lista: media 2,2, mediana 1. Non pertinenti: media 4,5.
- Liste da dieci righe: 36 % (nel seme: 16 %). Mediana delle righe: 7 (nel seme: 5).
- Dalla terza riga in giù gli sfumati hanno tutti `best` fra 0,17 e 0,30, e cambiano di
  0,01-0,02 da una riga all'altra: **non c'è un salto da trovare**. Il solo salto netto è
  fra la prima e la seconda riga, cioè proprio dove spesso c'è un secondo prefisso giusto
  («latte» → «lattuga»).
- Il rumore non si distingue dal giusto per il punteggio. Un prefisso lungo ha `best`
  basso perché `similarity` misura tutta la stringa: «zucch» contro «zucchero a velo» fa
  0,29, meno di «zucca» (0,50), che non c'entra.

Sui refusi (1.402 prove) il bersaglio è primo nel 75,6 % dei casi e fuori dai dieci
nell'8,1 %. Il suo `best` ha mediana 0,44, ma il 10 % sta sotto 0,20: proprio dove sta il
rumore delle altre liste.

## 5. I criteri a confronto

Ogni criterio riceve la lista nell'ordine di oggi (fino a 30 candidati) e restituisce le
righe da mostrare, al massimo 10. «Richiamo»: il bersaglio resta in lista. «Non pertinenti»
è la media per lista, criterio stretto (fra parentesi quello largo). Anagrafica corretta;
nel seme i rapporti fra i criteri sono gli stessi, con liste più corte.

I criteri provati:

- **soglia assoluta** `t`: tiene chi ha `best ≥ t`;
- **soglia relativa** `r`: tiene chi ha `best ≥ r × best del primo`;
- **salto** `X`: si ferma alla prima riga che cala di più di `X` rispetto a quella sopra;
- **prefisso sempre + altri ≥ t**: i prefissi di oggi passano sempre, gli sfumati solo con
  `best ≥ t`;
- **solo riordino**: chi contiene il testo a inizio parola va in cima, senza tagliare
  niente;
- **A**: chi contiene il testo a inizio parola, nel nome o in un alias qualunque, passa
  sempre; se nessuno lo contiene, gli sfumati con `best ≥ 0,8 × primo`;
- **B**: come A, ma conta l'inizio di parola solo nel nome, più l'alias che comincia col
  testo (il criterio stretto del §3.3). Se c'è anche un solo riscontro, gli sfumati restano
  fuori; se non ce n'è nessuno, passano gli sfumati con `best ≥ max(pavimento, r × primo)`.

### 5.1 Digitazione (1.736 prove)

| criterio | richiamo % | bersaglio 1º % | righe media | righe mediana | non pertinenti | liste con non pertinenti % | liste vuote % |
|---|---|---|---|---|---|---|---|
| **oggi** | 99,9 | 80,8 | 6,7 | 7 | 4,70 (4,48) | 90,3 | 0,0 |
| soglia assoluta 0,20 | 96,0 | 79,8 | 4,5 | 4 | 2,70 | 77,2 | 0,6 |
| soglia assoluta 0,25 | 90,8 | 77,5 | 2,9 | 2 | 1,29 | 55,5 | 2,9 |
| soglia assoluta 0,30 | 84,2 | 74,3 | 2,0 | 1 | 0,60 | 30,8 | 7,4 |
| soglia assoluta 0,35 | 74,7 | 68,2 | 1,5 | 1 | 0,37 | 20,3 | 17,2 |
| relativa ≥ 0,5 × primo | 94,8 | 80,6 | 2,9 | 2 | 1,28 | 42,9 | 0,0 |
| relativa ≥ 0,6 × primo | 91,3 | 80,2 | 2,2 | 1 | 0,76 | 30,2 | 0,0 |
| relativa ≥ 0,7 × primo | 88,3 | 79,3 | 1,7 | 1 | 0,41 | 21,1 | 0,0 |
| relativa ≥ 0,8 × primo | 84,1 | 78,5 | 1,4 | 1 | 0,23 | 15,0 | 0,0 |
| salto > 0,10 | 89,9 | 80,8 | 2,2 | 1 | 0,73 | 18,4 | 0,0 |
| salto > 0,15 | 93,3 | 80,8 | 2,9 | 1 | 1,32 | 28,6 | 0,0 |
| salto > 0,20 | 95,1 | 80,8 | 3,6 | 1 | 1,86 | 38,8 | 0,0 |
| prefisso sempre + altri ≥ 0,3 | 99,9 | 80,7 | 2,5 | 2 | 0,60 | 30,8 | 0,1 |
| prefisso sempre + altri ≥ 0,4 | 99,9 | 80,7 | 2,1 | 1 | 0,23 | 13,9 | 0,1 |
| solo riordino | 99,9 | 80,8 | 6,7 | 7 | 4,68 | 90,3 | 0,0 |
| A (0,8) | 99,9 | 80,8 | 2,2 | 1 | 0,24 (0,00) | 15,1 | 0,0 |
| B (0,8, nessun pavimento) | 99,9 | 80,8 | 2,0 | 1 | 0,00 | 0,0 | 0,0 |
| **B (0,8, pavimento 0,3, senza accenti)** | 99,9 | 80,8 | 2,0 | 1 | 0,00 | 0,0 | 0,0 |

Le soglie che guardano solo il punteggio (assoluta, relativa, salto) **perdono bersagli
che contengono il testo**: un prefisso lungo ha `best` basso per come è fatta
`similarity`. A 0,30 di soglia assoluta si perde un bersaglio su sei. Il salto non trova il
punto giusto, perché il salto netto è fra la prima e la seconda riga (§4). I criteri che
fanno passare sempre chi contiene il testo tengono il richiamo di oggi.

### 5.2 Refusi (1.402 prove)

| criterio | richiamo % | bersaglio 1º % | righe media | non pertinenti | liste con non pertinenti % | liste vuote % |
|---|---|---|---|---|---|---|
| **oggi** | 91,9 | 75,6 | 5,6 | 4,37 | 85,7 | 2,1 |
| soglia assoluta 0,25 | 73,0 | 67,5 | 1,8 | 1,00 | 43,2 | 18,2 |
| soglia assoluta 0,30 | 62,1 | 60,1 | 1,2 | 0,55 | 29,3 | 29,7 |
| relativa ≥ 0,7 × primo | 85,6 | 75,7 | 1,9 | 0,85 | 36,7 | 2,1 |
| relativa ≥ 0,8 × primo | 83,5 | 75,7 | 1,5 | 0,54 | 29,1 | 2,1 |
| salto > 0,15 | 89,8 | 75,6 | 3,0 | 1,82 | 41,7 | 2,1 |
| prefisso sempre + altri ≥ 0,3 | 62,5 | 60,0 | 1,2 | 0,56 | 29,4 | 29,6 |
| B (0,7, nessun pavimento) | 85,4 | 75,6 | 1,9 | 0,85 | 36,6 | 2,1 |
| B (0,8, nessun pavimento) | 83,5 | 75,6 | 1,5 | 0,54 | 29,2 | 2,1 |
| B (0,8, pavimento 0,25) | 70,8 | 67,5 | 1,0 | 0,19 | 15,8 | 18,2 |
| **B (0,8, pavimento 0,3)** | 61,6 | 60,0 | 0,8 | 0,14 | 12,0 | 29,6 |

Il richiamo complessivo sui refusi nasconde due casi molto diversi:

| criterio | refuso nel nome intero (760) | refuso nei primi 6 caratteri (642) |
|---|---|---|
| oggi | 100,0 % · 6,0 righe | 82,2 % · 5,2 righe |
| B (0,8, nessun pavimento) | 99,1 % · 1,1 righe | 65,1 % · 2,0 righe |
| B (0,8, pavimento 0,25) | 98,2 % · 1,1 righe | 38,3 % · 0,8 righe |
| **B (0,8, pavimento 0,3)** | 96,4 % · 1,1 righe | 20,4 % · 0,5 righe |

Un refuso nella parola intera si ritrova quasi sempre: la parola ha abbastanza trigrammi
giusti. Un refuso nei primi caratteri, a metà della parola, no: «aeto» contro «aceto
balsamico» ha troppo poco in comune. È però un caso che passa da solo: chi continua a
scrivere arriva alla parola intera, e lì il 96 % dei refusi torna in lista.

### 5.3 Ingredienti assenti (175 prove, contro il seme)

| criterio | righe media | righe mediana | non pertinenti | liste con non pertinenti % | liste vuote % |
|---|---|---|---|---|---|
| **oggi** | 4,8 | 4 | 4,46 | 90,3 | 6,9 |
| soglia assoluta 0,30 | 0,8 | 0 | 0,58 | 31,4 | 58,9 |
| relativa ≥ 0,8 × primo | 1,8 | 1 | 1,62 | 77,7 | 6,9 |
| salto > 0,15 | 3,6 | 2 | 3,40 | 80,6 | 6,9 |
| B (0,8, nessun pavimento) | 1,9 | 2 | 1,61 | 77,1 | 6,9 |
| B (0,8, pavimento 0,25) | 0,9 | 1 | 0,57 | 41,7 | 42,3 |
| **B (0,8, pavimento 0,3)** | 0,7 | 0 | 0,37 | 26,9 | 57,1 |

Qui si vede a cosa serve il pavimento. Senza pavimento, un criterio relativo tiene sempre
il primo sfumato, anche quando non somiglia a niente: chi cerca un ingrediente che non c'è
vede una o due righe sbagliate nel 77 % dei casi. Con il pavimento a 0,3 la lista è vuota
in più di metà dei casi.

### 5.4 Due caratteri, e i casi a mano

**2 caratteri** (275 prove): tutti i criteri che fanno passare chi contiene il testo
lasciano il richiamo di oggi (88,7 %; il resto è il bersaglio oltre la decima riga, perché
con due lettere i prefissi sono più di dieci) e tolgono le poche righe non pertinenti (da
0,30 a 0 per lista; righe da 7,0 a 6,7). Le soglie sul punteggio invece li svuotano: a 0,30
di soglia assoluta il 59 % delle liste di due lettere resta vuoto, perché con due lettere
`similarity` non arriva mai in alto. È il caso che il docstring della funzione già
documenta, e il motivo per cui oggi il prefisso scavalca lo 0,15.

**Casi a mano**, anagrafica corretta. «Oggi» dà le righe e, fra parentesi, quante non sono
pertinenti; «pos.» è la posizione del bersaglio oggi. L'ultima colonna è il criterio
raccomandato (§6):

| digitato | bersaglio | oggi | pos. | con il criterio raccomandato |
|---|---|---|---|---|
| «zucch» | zucchina | 9 (4) | 2 | zucchero, zucchina, zuccherino, zucchero a velo, pasta di zucchero |
| «zucchin» | zucchina | 10 (9) | 1 | zucchina |
| «latt» | latte | 9 (4) | 1 | latte, lattuga, latte di soia, latte di mandorle, latte al cioccolato |
| «pomod» | pomodoro | 10 (4) | 1 | pomodoro, pomodorino, polpa di pomodoro, pomodoro secco, pomodoro verde, concentrato di pomodoro |
| «olio» | olio di oliva | 8 (5) | 1 | olio di oliva, olio di semi, olio di cocco |
| «sale» | sale | 10 (9) | 1 | sale |
| «sal» | sale | 10 (3) | 1 | sale, salvia, salmone, salsiccia, ketchup, salsa di soia, polpa di pomodoro |
| «uovo» | uova | 2 (1) | 1 | uova |
| «parmig» | parmigiano | 7 (6) | 1 | parmigiano |
| «farina» | farina | 10 (6) | 1 | farina, farina di ceci, polenta, semola di grano duro rimacinata |
| «panna» | panna fresca | 10 (9) | 1 | panna fresca |
| «burro» | burro | 5 (3) | 1 | burro, olio di cocco |
| «pasta» | pasta | 10 (4) | 1 | pasta, pasta per pizza, pasta sfoglia, mix tandoori, marzapane, pasta di zucchero |
| «caffe» | caffè | 10 (9) | 1 | caffè |
| «te» | tè | 1 (0) | 1 | tè |
| «pollo» | petto di pollo | 10 (8) | 1 | petto di pollo, coscia di pollo |
| «pelati» | (polpa di pomodoro, dopo la correzione) | 10 (9) | 1 | polpa di pomodoro |
| «pepe» | pepe nero | 10 (6) | 1 | pepe nero, pepe verde, peperone, peperoncino |

Le righe che sembrano strane nell'ultima colonna («ketchup» per «sal», «olio di cocco» per
«burro», «mix tandoori» per «pasta») hanno tutte un alias che comincia col testo («salsa
ketchup», «burro di cocco», «pasta tandoori»). Non sono un errore della ricerca: la riga
mostra il nome dell'ingrediente e non dice da quale alias arriva (vedi «Fuori scope»).

**«zucch».** Con il criterio raccomandato la lista passa da 9 righe a 5, e sono le 5 che
contengono «zucch»: via «zucca», «semi misti», «fiori di zucca», «panna fresca». Zucchero
resta prima di Zucchina, per il motivo del §1: lo stesso prefisso, la stessa somiglianza,
lo stesso numero di lettere. Tre modi di riordinare, scartati:

- **prima il più corto**: sono lunghi uguali;
- **prima il nome dell'alias**: tutti e due hanno il prefisso nel nome;
- **prima quel che è in dispensa o in lista**: è un'informazione che c'è (e in produzione
  gli acquisti già fanno da spareggio), ma è un cambio di ordinamento, non di taglio. Va
  deciso a parte, se serve (decisione 5).

Riordinare senza tagliare non risolve niente: «solo riordino» lascia 4,7 righe non
pertinenti per lista (§5.1), perché oggi i prefissi sono già in cima.

## 6. Raccomandazione

**Criterio B: «chi contiene il testo, e gli altri solo se nessuno lo contiene»**, con
`r = 0,8` e pavimento `0,30`, togliendo gli accenti nel confronto:

1. Una riga è un **riscontro** se, tolti gli accenti, il **nome** dell'ingrediente contiene
   il testo digitato all'inizio di una parola (inizio, dopo uno spazio, un apostrofo o un
   trattino), oppure se un suo **alias comincia** con il testo. Il secondo caso è
   l'`is_prefix` di oggi sugli alias.
2. **Se c'è almeno un riscontro, si mostrano solo i riscontri**, al massimo 10, nell'ordine
   di oggi: prefisso, acquisti, somiglianza, nome.
3. **Se non c'è nessun riscontro**, si mostrano gli sfumati con
   `best ≥ max(0,30; 0,8 × best del primo)`, al massimo 10: è il caso del refuso.
4. **Se non resta niente, la lista è vuota**, e il chiamante mostra la sua via d'uscita:
   «Aggiungi «…»», la nota della dispensa, il testo libero della lista (§7).

I numeri, sull'anagrafica corretta (fra parentesi il seme):

| | oggi | raccomandato |
|---|---|---|
| digitazione: richiamo | 99,9 % (100 %) | 99,9 % (100 %) |
| digitazione: bersaglio primo | 80,8 % (86,5 %) | 80,8 % (86,5 %) |
| digitazione: righe, media e mediana | 6,7 e 7 (5,2 e 5) | 2,0 e 1 (1,5 e 1) |
| digitazione: liste con righe non pertinenti | 90 % (87 %) | 0 % (0 %), per costruzione (§3.3) |
| 2 caratteri: richiamo; righe | 88,7 %; 7,0 | 88,7 %; 6,7 |
| refuso nel nome intero: richiamo | 100 % | 96,4 % |
| refuso nei primi 6 caratteri: richiamo | 82,2 % | 20,4 % |
| refusi: liste con righe non pertinenti | 86 % | 12 % |
| assenti: righe; liste vuote | 4,8; 6,9 % | 0,7; 57,1 % |

Perché questo e non una soglia sul punteggio:

- **Il punteggio non separa il giusto dal rumore** (§4): un prefisso lungo ha `best` basso
  per come è fatta `similarity`, e il rumore sta fra 0,17 e 0,30 come una parte dei
  bersagli. Ogni soglia sul solo punteggio che toglie il rumore perde bersagli che
  contengono il testo: un bersaglio su sei a 0,30. E con due lettere svuota le liste.
- **«Contiene il testo» è il segnale che chi digita si aspetta**, e il docstring di
  `search_ingredients` lo dice già per il prefisso. Il criterio lo allarga all'inizio di
  ogni parola del nome («pollo» → «petto di pollo»), e smette di aggiungere sfumati quando
  ci sono riscontri.
- **Il pavimento a 0,30 costa poco dove conta**: un refuso nella parola intera si ritrova
  ancora nel 96 % dei casi. E rende vuota più di metà delle liste di un ingrediente che non
  c'è, che oggi mostrano sempre qualcosa di sbagliato. Perde i refusi a metà parola, che si
  ritrovano appena la parola è finita.
- **Il taglio non cambia l'ordine**: chi oggi è primo resta primo. Il bersaglio in testa
  resta all'80,8 %, e nessun test d'ordinamento esistente cambia verso.

**Il prezzo**, da dire chiaro: chi scrive con un refuso nelle prime lettere vede la lista
vuota finché non finisce la parola. E in «Sistema la spesa» e nel modulo ricetta, dove
«Aggiungi «…»» c'è sempre (`createWhen="always"`), una lista vuota accanto a «Aggiungi
«pomdo»» rende più facile creare un doppione scritto male. Un pavimento a 0,25 riduce
questo prezzo e ne alza un altro (decisione 1).

## 7. Mai un vicolo cieco

Cosa succede quando la lista è vuota, chiamante per chiamante (verificato nel codice):

- **Lista della spesa** (`AddItemField`): il testo libero si aggiunge sempre con
  «Aggiungi». Nessun problema.
- **Sistema la spesa** (`MatchPanel.tsx:70-78`) e **modulo ricetta**
  (`RecipeForm.tsx:338-347`): `createWhen="always"`, «Aggiungi «…»» c'è comunque.
- **Dispensa** (`PantryScreen.tsx:212-230`): `emptyNote` («Non è in anagrafica: scrivilo
  in lista…») compare solo a ricerca vuota. Oggi un ingrediente assente dà una lista vuota
  solo nel 6,9 % dei casi, quindi la nota quasi non si vede e si vedono righe sbagliate.
  Con il criterio la vedrebbe più di metà delle volte. È un miglioramento.
- **Coda dell'import** (`TermCard.tsx:87`), **Anagrafica** (`AliasRow.tsx:84`,
  `MergePanel.tsx:99`, `ProductScreen.tsx:209`) e **filtri del ricettario**
  (`RecipeFiltersPanel.tsx:64`): non passano né `onCreate` né `emptyNote`. A ricerca
  vuota il pannello resta muto sotto il campo pieno, ed è il caso che il commento di
  `emptyNote` in `IngredientPicker` chiama vicolo cieco. Oggi capita di rado, perché la
  lista ha quasi sempre qualcosa; con il taglio capiterebbe spesso. Il piano deve dare a
  `IngredientPicker` una nota di ripiego per quando nessuno la passa, per esempio
  «Nessun ingrediente somiglia a «…»» (decisione 6).

Nessun criterio provato toglie «Aggiungi «…»» dove c'è oggi: tagliare le righe può solo
farlo comparire più spesso, dove dipende dalla ricerca vuota.

## 8. Dove andrebbe nel codice

Una funzione pura in `backend/app/domain/` (accanto a `rules.py`, senza database), per
esempio `trim_suggestions(candidates, limit)`, che riceve i candidati già ordinati, ognuno
con `is_hit` e `best`, e restituisce quelli da mostrare secondo i quattro punti del §6;
testabile table-driven come `rules.py`.

Intorno servono tre ritocchi alla query, che restano da progettare nel piano:

- calcolare `is_hit` in SQL: il nome con il testo a inizio parola, o l'alias che comincia
  col testo. Gli accenti si tolgono con `translate()` sui due lati, che non chiede
  estensioni (decisione 2). Il testo va protetto da `%` e `_`;
- mettere `is_hit` nell'`ORDER BY` subito dopo `is_prefix`, così i riscontri a metà nome
  («petto di pollo» per «pollo») non restano fuori dal `LIMIT`;
- restituire `best` e `is_hit` insieme all'ingrediente, e applicare il taglio solo per
  l'endpoint `/ingredients/search`, non per `match_name` e i vicini dell'AI (decisione 3).

## 9. Test che servirebbero

- **La funzione pura, table-driven**: solo riscontri (tutti tenuti, fino al limite);
  riscontri più uno sfumato a 0,9 (lo sfumato esce); nessun riscontro, sfumati a 0,60,
  0,50 e 0,45 (escono quelli sotto 0,48, cioè 0,8 × 0,60); nessun riscontro e primo
  sfumato a 0,28 (lista vuota, per il pavimento); lista vuota in ingresso; più di 10
  riscontri (taglio a 10).
- **Sul Postgres vero, attraverso l'endpoint** che chiama il frontend, non solo la
  funzione (la prima lezione del `CLAUDE.md`): «zucch» con zucchero, zucchina e zucca (la
  zucca esce); «olio» con un alias «tonno sott'olio» (il tonno esce); «pollo» trova
  «petto di pollo» a metà nome; «te» trova «tè»; «pomodorr» trova ancora «pomodoro»
  (refuso nella parola intera); un ingrediente che non c'è dà `[]`; una query con `%` o
  `_` li tratta come lettere.
- **I test esistenti restano verdi** (`backend/tests/api/test_ingredients.py`: prefisso,
  refuso «yogrut greco», alias «pelati», acquisti a parità di prefisso, somiglianza prima
  degli acquisti sugli sfumati). Due di questi passano dal ramo degli sfumati, ed è bene
  saperlo: «yogrut greco» (0,529) e «pelati», che nel fixture è dentro l'alias «pomodori
  pelati» e non al suo inizio (0,467). Tutti e due stanno sopra il pavimento e sono primi,
  quindi restano.
- **Gli altri chiamanti non cambiano**: `search_ingredients` usata da `decide.py`
  restituisce ancora i vicini sfumati (un test in `test_decide_terms.py` con un vicino
  che non contiene il testo).
- **Frontend**, se passa la decisione 6: `IngredientPicker` senza `emptyNote` né
  `onCreate` mostra la nota di ripiego a ricerca vuota, e non la mostra mentre la ricerca
  è in corso (la stessa regola di S18).

## 10. Decisioni per Mattia

1. **Il pavimento sugli sfumati, quando nessuno contiene il testo.**
   (a) 0,30: refuso nel nome intero 96,4 %, a metà parola 20 %, ingrediente assente con
   lista vuota nel 57 % dei casi; (b) 0,25: 98,2 %, 38 %, 42 %; (c) nessun pavimento,
   solo 0,8 × primo: 99,1 %, 65 %, 7 %, cioè per un ingrediente assente quasi sempre una o
   due righe sbagliate.
   **Raccomandazione: (a).** Il tocco sbagliato è il difetto che ha aperto la voce, e i
   refusi a metà parola tornano da soli a parola finita. **Deciso da Mattia il 2026-10-07:
   (a), il criterio B col pavimento a 0,30.**
2. **Togliere gli accenti nel confronto «contiene il testo».**
   (a) `translate()` sulle vocali accentate, nella query, senza migrazioni; (b)
   l'estensione `unaccent`, con una migrazione; (c) niente. Misurato: senza accenti si
   recupera «te» → tè; «caffe» → caffè passa già come sfumato (0,50).
   **Raccomandazione: (a).** Costa una riga e non cambia nient'altro. **Deciso da Claude il 2026-10-07, su delega di Mattia per le scelte non funzionali: (a).**
3. **Dove si applica il taglio.** (a) solo nell'endpoint `/ingredients/search`; (b) dentro
   `search_ingredients`, per tutti. **Raccomandazione: (a).** `match_name` (`limit=1`) e i
   vicini per l'AI (`limit=3`) vivono degli sfumati. **Deciso da Claude il 2026-10-07, su delega di Mattia per le scelte non funzionali: (a).**
4. **Gli alias che contengono il testo a metà** («olio» → «Tonno in scatola» per «tonno
   sott'olio»). (a) fuori, criterio B; (b) dentro, criterio A: 0,24 righe in più per lista
   che a chi legge sembrano rumore. **Raccomandazione: (a).**
5. **«zucch».** (a) nessuna regola nuova: il taglio lascia 5 righe che contengono tutte
   «zucch», con Zucchina seconda; (b) uno spareggio nuovo fra prefissi a pari punteggio,
   per esempio prima quel che è in dispensa o in lista. **Raccomandazione: (a)** in questa
   voce. Se il giro dopo il taglio dice ancora che sbaglia, (b) diventa una voce sua.
6. **La nota di ripiego in `IngredientPicker`** per i cinque schermi che non passano né
   `emptyNote` né `onCreate` (§7). (a) dentro questa voce; (b) voce a parte.
   **Raccomandazione: (a).** Senza la nota, il taglio crea muti dove oggi c'è rumore.
   **Deciso da Claude il 2026-10-07, su delega di Mattia per le scelte non funzionali: (a).**

## 11. Fuori scope

- **L'ordine fra i prefissi** (acquisti, poi somiglianza, poi nome) resta com'è; vedi la
  decisione 5.
- **Mostrare da quale alias arriva una riga** («Ketchup · salsa ketchup»): spiegherebbe le
  righe giuste che sembrano rumore. È un cambio di interfaccia, da proporre come `idea`.
- **Gli alias discutibili** («pasta tandoori» su «mix tandoori», «burro di cocco» su
  «olio di cocco»): si correggono dall'Anagrafica (S9), non con la ricerca.
- **La somiglianza senza accenti** (`unaccent` dentro `similarity`) e la ricerca
  semantica con gli embeddings: nessun caso misurato li chiede.
- **Le prestazioni**: oggi la query calcola `similarity` per ogni coppia ingrediente-alias,
  senza usare gli indici GIN trigram. Con 884 ingredienti va bene così.
- **Il `limit` chiesto dal frontend**: resta 10.

## Appendice A: l'SQL della misura

La query riproduce `search_ingredients` (righe 31-82) con `purchase_count = 0`, sopra
un'anagrafica e un elenco di prove passati come JSON (`$J$…$J$`). Il JSON ha la forma
`{"ingredients": [{"name": "…", "aliases": ["…"]}], "queries": [{"q": "…"}]}`. Gira dentro
una transazione di sola lettura e non legge nessuna tabella. `word_sim` è una colonna in
più, che la funzione di oggi non calcola, servita a provare un criterio su
`word_similarity`. Quel criterio è stato scartato: sui refusi teneva il bersaglio solo nel
40 % dei casi.

```sql
BEGIN TRANSACTION READ ONLY;
WITH data AS (SELECT $J$ { …anagrafica e prove… } $J$::jsonb AS j),
ingredients AS (
  SELECT o AS id, x->>'name' AS name
  FROM data, jsonb_array_elements(j->'ingredients') WITH ORDINALITY AS t(x, o)
),
ingredient_aliases AS (
  SELECT o AS ingredient_id, a AS alias
  FROM data, jsonb_array_elements(j->'ingredients') WITH ORDINALITY AS t(x, o),
       jsonb_array_elements_text(x->'aliases') AS a
),
queries AS (
  SELECT o AS qid, lower(btrim(x->>'q')) AS cleaned
  FROM data, jsonb_array_elements(j->'queries') WITH ORDINALITY AS t(x, o)
),
scored AS (
  SELECT q.qid, c.*
  FROM queries q
  CROSS JOIN LATERAL (
    SELECT i.name,
           similarity(i.name, q.cleaned) AS name_sim,
           coalesce(max(similarity(a.alias, q.cleaned)), 0.0) AS alias_sim,
           greatest(similarity(i.name, q.cleaned),
                    coalesce(max(similarity(a.alias, q.cleaned)), 0.0)) AS best,
           (i.name LIKE q.cleaned || '%')
             OR coalesce(bool_or(a.alias LIKE q.cleaned || '%'), false) AS is_prefix,
           greatest(word_similarity(q.cleaned, i.name),
                    coalesce(max(word_similarity(q.cleaned, a.alias)), 0.0)) AS word_sim
    FROM ingredients i
    LEFT JOIN ingredient_aliases a ON a.ingredient_id = i.id
    GROUP BY i.id, i.name
    HAVING greatest(similarity(i.name, q.cleaned),
                    coalesce(max(similarity(a.alias, q.cleaned)), 0.0)) >= 0.15
        OR (i.name LIKE q.cleaned || '%')
        OR coalesce(bool_or(a.alias LIKE q.cleaned || '%'), false)
  ) c
),
ranked AS (
  SELECT *,
         row_number() OVER (PARTITION BY qid
                            ORDER BY is_prefix DESC, best DESC, name ASC) AS rk,
         count(*) OVER (PARTITION BY qid) AS pool
  FROM scored
)
SELECT qid, rk, pool, name, name_sim, alias_sim, best, is_prefix, word_sim
FROM ranked
WHERE rk <= 30
ORDER BY qid, rk;
ROLLBACK;
```

Con `purchase_count = 0` i due termini sugli acquisti dell'`ORDER BY` di oggi valgono zero
per tutti, e l'ordine si riduce a `is_prefix DESC, best DESC, name ASC`.

## Appendice B: le regole del resto della misura

Il resto è in Python, sopra il risultato della query:

- **riscontro** (criterio B): `re.search(r"(^|[\s'’\-])" + re.escape(testo), nome)` sul
  nome, oppure `alias.startswith(testo)` su un alias; nella variante «senza accenti», tutti
  e due i lati passano per una normalizzazione NFD senza i segni diacritici;
- **pertinenza**: la stessa regola, applicata al testo giusto (per i refusi, quello prima
  del refuso), più il bersaglio stesso (§3.3); quella «larga» accetta l'inizio di parola in
  un alias qualunque;
- **refusi**: con `random.Random(20261006)`, una posizione interna a caso per la lettera
  mancante, una per lo scambio con la lettera dopo (saltato se le due lettere sono uguali),
  una per la sostituzione con una lettera di `abcdefghilmnoprstuvz`;
- **campioni**: tutti gli ingredienti (sono meno di 300), e fino a 150 alias con
  `rng.sample` sull'elenco ordinato delle coppie (alias, ingrediente).
