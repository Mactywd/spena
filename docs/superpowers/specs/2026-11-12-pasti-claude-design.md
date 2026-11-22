# Pasti con Claude e Utensili — design

_2026-11-12, fase giorno con Mattia. Sostituisce la «Parte IV — Pasti» di
`docs/prossimi-passi.md` (P1 creazione di un pasto, P3 pianificare più giorni)._

Le decisioni di Mattia sono scritte come tali. Quelle che ho preso io, perché Mattia
le ha delegate (le scelte estetiche e non funzionali, vedi la memoria del progetto) o
perché un costruttore attento le prenderebbe uguali, sono segnate **(scelta di
Claude)**: Mattia le può rivedere leggendo.

## 1. Perché

Oggi i pasti vivono fuori da spena. Mattia scrive pranzo e cena a mano in un planner
sul reMarkable, e la skill `pasti` di Claude Code legge quella pagina e la dispensa di
spena per proporre piatti, dare le ricette e aggiornare dispensa e lista. Funziona, ma
la ricetta di stasera si chiede di nuovo ogni sera, il planner si legge a occhio (il
passo più lento della skill) e niente di quello che si decide resta in spena.

L'obiettivo è portare tutto il giro dentro spena: la settimana dei pasti, la ricetta di
ogni piatto, e una conversazione con Claude simile alla chat di Claude stessa. Il
reMarkable e la skill escono dal giro.

**Esempio guida (2026-11-10).** Martedì sera era pianificata «frittata di spinaci e
parmigiano, piadina come pane, banana come frutta». In futuro Mattia apre spena, vede la
settimana, tocca la cena di martedì e trova la ricetta completa. Sotto la ricetta c'è la
chat: «ho gli spinaci congelati nella busta da 1 kg, quanti ne prendo? Posso metterli in
padella da congelati e poi versare le uova, senza tritarli?». Claude risponde in chat e,
insieme, la ricetta si aggiorna: 150 g di spinaci congelati, padella unica, niente
strizzatura. **Il messaggio resta nella chat e la scheda cambia** (deciso da Mattia).

## 2. Obiettivi, non-obiettivi, anti-obiettivi

**Obiettivi**
- Una sezione Pasti con la vista della settimana: pranzo e cena per giorno.
- Pianificare con Claude dentro spena, nei due modi in cui Mattia usa oggi la skill:
  qualche pasto con quello che c'è in casa, oppure tutta la settimana prima della spesa,
  chiudendo con lista e dispensa aggiornate.
- Per ogni piatto pianificato, una ricetta vera di spena scritta da Claude al momento
  della pianificazione, e una chat per modificarla.
- Ogni campo modificabile anche a mano (deciso da Mattia).
- Una sezione Utensili: le ricette scritte dall'AI usano solo gli strumenti che Mattia ha.

**Non-obiettivi (per ora)**
- Colazione, merenda, spuntini: solo pranzo e cena, come nel planner di oggi
  **(scelta di Claude)**.
- Importare le settimane già scritte sul reMarkable **(scelta di Claude)**.
- NutriScore, budget di costo, scelta automatica dal ricettario: erano la Parte IV, che
  questa sezione sostituisce (deciso da Mattia, §11). L'equilibrio resta uno sguardo
  approssimativo di Claude sui pasti precedenti (§7).
- Calorie e grammi: il giudizio sull'equilibrio resta per gruppi alimentari, come nella
  skill.
- Segnalare le ricette importate che chiedono uno strumento mancante (resta un'idea).

**Anti-obiettivi — sarebbe un fallimento anche se funzionasse**
- Una chat che, quando Claude non risponde (limite del piano raggiunto, token scaduto,
  rete), lascia Mattia senza modo di scrivere il pasto o correggere la ricetta. *Mai un
  vicolo cieco*: tutto quello che fa Claude si deve poter fare a mano.
- Claude che scrive in dispensa o in lista senza che Mattia abbia visto e confermato i
  cambi. La skill di oggi chiede l'ok su una tabella, e quell'ok resta.
- Ricette dei pasti che riempiono il ricettario di frittate fatte una volta sola.
- La dispensa che perde due volte la stessa cosa: una volta alla pianificazione e una
  quando si cucina.

## 3. Vincoli

- **Il modello è Claude Opus (`claude-opus-5-5`) sull'abbonamento di Mattia, non su
  crediti API** (deciso da Mattia il 2026-11-10). Mattia ha valutato che l'uso è
  personale: spena è usato solo da lui e non è un prodotto commerciale.
  Conseguenze da tenere presenti:
  - la strada tecnica è il **Claude Agent SDK** per Python (`claude-agent-sdk`), cioè
    l'harness di Claude Code come libreria, autenticato con il token del suo account
    (`claude setup-token` → `CLAUDE_CODE_OAUTH_TOKEN` nel `.env` del server, mai nel
    repo, che è pubblico). L'API di Anthropic con chiave non va usata per questa
    sezione, e l'SDK `anthropic` non serve;
  - le chat consumano **gli stessi limiti del piano** delle sessioni notturne di Claude
    Code. Quando il limite è raggiunto la chat lo dice e la strada a mano resta (§9);
  - nessun costo in dollari da registrare: in `llm_calls` le chiamate vanno con la loro
    sezione e i token, e `cost_usd` resta `NULL` («l'assenza è la verità», come vuole il
    modello `LlmCall`).
- **Un secondo percorso verso un modello.** La regola «one provider» di `CLAUDE.md` era
  contro due implementazioni dietro un interruttore, di cui una non gira mai in
  produzione. Qui i percorsi sono due ma con due scopi diversi, e girano tutti e due:
  Gemma (o Haiku, quando passerà la voce «L'LLM passa all'API di Anthropic») per import,
  bozze e varianti; Opus via Agent SDK per i Pasti. `CLAUDE.md` va aggiornato insieme,
  spiegando perché questo non è il caso che la regola vieta.
- Le due decisioni fondanti di spena restano intere: nessuna quantità in dispensa, e le
  ricette puntano solo a ingredienti alimentari, attraverso l'imbuto
  `write_recipe_ingredients`.
- Tutta la logica sta nel backend; il frontend mostra e invia.
- Mobile-first, letta in corsia e in cucina: contrasti sopra 4,5:1 nei due temi, colori
  solo dai token di `index.css`, primitive da `components/ui/`. Il controllo visivo
  si fa nel browser e in `e2e/style.spec.ts`, non nei test jsdom.
- I test non usano la rete: il client di Claude ha una versione finta per i test, ma
  (prima lezione di `CLAUDE.md`) l'oggetto di produzione deve essere quello che gira.
  L'immagine del backend deve contenere davvero l'Agent SDK e ciò che gli serve, e un
  test o un controllo all'avvio lo deve dimostrare.

## 4. Il modello dei dati

### 4.1 Pasti

Un **pasto** è un posto nella settimana: una data, `pranzo` o `cena`, e al massimo un
pasto per posto. Ha:

- un **piatto**: il nome che si legge nella settimana («Frittata di spinaci e
  parmigiano», «Fuori», «Pizza»);
- una **ricetta** facoltativa (`recipe_id`): ce l'ha ogni piatto pianificato con
  Claude; un pasto scritto a mano può non averla («Fuori», «dai genitori»);
- gli **accompagnamenti**: testo breve, per pane, frutta e contorni semplici
  («piadina · banana») **(scelta di Claude)**. Se un contorno ha bisogno di una
  ricetta, Claude lo mette nella ricetta del piatto, come oggi la skill dice «come
  completarlo»;
- **fuori casa**: un segno, per i pasti che non si cucinano. Serve a Claude per non
  riempirli e per non contarli nell'equilibrio della settimana come piatti noti.

Un pasto è **in bozza** o **ufficiale** (deciso da Mattia il 2026-11-12, vedi §5.2).
Una bozza è un'intenzione per compilare la lista della spesa: ha il piatto e gli
accompagnamenti, non ha ancora una ricetta e non ha toccato la dispensa. Un pasto
ufficiale ha la sua ricetta e la dispensa è già al netto di lui. I pasti scritti a mano
nascono ufficiali.

Un posto vuoto è «da pianificare». Un pasto con la data passata conta come mangiato:
come nella skill, i pasti pianificati e passati sono quello che Mattia ha mangiato.

### 4.2 Le ricette dei pasti

Ogni ricetta scritta per un pasto è una **ricetta vera di spena** (deciso da Mattia):
righe di ingredienti che passano dall'imbuto, dosi riscalabili, «Metti in lista ciò che
manca». Si apre con il dettaglio di sempre e si corregge con il modulo di sempre
(`/ricette/:id/modifica`, R10).

**Non compare nel ricettario** finché Mattia non sceglie «Salva nel ricettario»
(deciso da Mattia). Serve un segno sulla ricetta: per esempio `recipes.in_book`, falso
per le ricette nate da un pasto e vero per tutte le altre (la migrazione lo mette vero
su quelle esistenti). Ogni elenco e ogni ricerca del ricettario escludono le ricette
fuori dal ricettario **dentro la query che porta il limite**, con la stessa regola delle
archiviate (sesta lezione di `CLAUDE.md`). `source = 'ai'`.

**Ogni pasto ha la sua ricetta, e una ricetta appartiene a un solo pasto** (legame uno
a uno) **(scelta di Claude)**. Così la chat di un piatto non cambia mai, di nascosto, un
altro pasto. Di conseguenza:

- «rifacciamo la frittata di martedì» crea una **copia** della ricetta per il pasto
  nuovo;
- un pasto scritto a mano può ricevere una ricetta anche senza Claude: **«Scrivi la
  ricetta»** apre il modulo di sempre e crea una ricetta fuori dal ricettario, mentre
  **«Scegli dal ricettario»** ne fa una copia fuori dal ricettario. La ricetta del
  ricettario non viene mai toccata dalla chat di un pasto;
- un **avanzo** («pranzo: l'avanzo della cena di ieri») è un pasto senza ricetta propria
  con il segno «avanzo» e il legame al pasto da cui viene: si apre sulla ricetta di quel
  pasto, in sola lettura e senza chat, e non tocca la dispensa
  (era già la regola dell'«Altro» di P3).

Quando la ricetta di un pasto si salva nel ricettario, resta la stessa ricetta: il
pasto continua a puntarla, e la sua chat la modifica come prima, perché è comunque la
ricetta di Mattia. «Togli dal ricettario» la rimette fuori **(scelta di
Claude)**. Eliminare un pasto non elimina la sua ricetta se è nel ricettario; se non lo
è, la archivia (R10), e nessun altro pasto la usa **(scelta di Claude)**.

Le ricette fuori dal ricettario vanno escluse anche dagli altri consumatori che oggi
leggono «tutte le ricette»: la ricerca semantica, il calcolo dei cucinabili e il motore
dei sostituti. I conteggi dell'Anagrafica (`recipes_using`, `ingredient_usage`) invece
le includono e le marcano «(da un pasto)»: è lo stesso motivo per cui includono le
eliminate. Una correzione dell'anagrafica che una riga vieta deve vederle.

### 4.3 Conversazioni

Una **conversazione** ha un tipo:

- **pianificazione**: non legata a un pasto. Nasce da «Pianifica con Claude»;
- **piatto**: legata a un pasto, una sola per pasto, aperta sotto la sua ricetta.

I messaggi si conservano in spena, con ruolo, testo, data e, per le risposte di Claude,
cosa hanno cambiato (§6.3). Per riprendere una conversazione dopo un riavvio del
container, la cronologia deve sopravvivere: o le sessioni dell'Agent SDK stanno su un
volume, o la conversazione si ricostruisce dai messaggi salvati. Scelta del
costruttore, ma un `up -d --build` non deve far dimenticare a Claude cosa si era detto.

### 4.4 Utensili

Un elenco: nome (testo libero) e nota facoltativa («padella antiaderente», nota
«da 24 cm»). Si aggiunge, si corregge, si toglie. Nessun legame con le righe delle
ricette **(scelta di Claude)**.

## 5. Le schermate

Le bozze di struttura sono in `.superpowers/brainstorm/` (fuori dal repo). Mattia le ha
approvate il 2026-11-12 e ha scelto, per il piatto, la versione **A**. L'aspetto è
lasciato al costruttore, dentro il sistema visivo di spena.

### 5.1 La settimana

- Una scheda nuova, **«Pasti»**, nella barra in basso accanto a Lista, Dispensa e
  Ricette **(scelta di Claude)**.
- Settimana da lunedì a domenica, con le frecce per quella prima e quella dopo. Si apre
  sulla settimana di oggi, con oggi evidenziato.
- Per ogni giorno, pranzo e cena: il piatto e, sotto, gli accompagnamenti; i pasti fuori
  hanno il loro segno, e i posti vuoti dicono «+ da pianificare».
- Toccare un pasto apre il piatto (§5.3). Toccare un posto vuoto offre due strade:
  scriverlo a mano (piatto, accompagnamenti, fuori casa) oppure chiederlo a Claude, che
  apre la pianificazione già puntata su quel posto.
- In fondo, **«Pianifica con Claude»**.
- Un pasto si sposta su un altro posto o si cancella a mano **(scelta di Claude: il modo
  è libero, anche un menu della riga)**.

### 5.2 Pianificare con Claude

Una chat a tutta pagina, nello stile della chat di Claude: i messaggi di Mattia a
destra, le risposte di Claude che arrivano un po' alla volta mentre vengono scritte, il
campo di testo in basso.

**I due giri (deciso da Mattia il 2026-11-12).**

- **Con quello che c'è in casa**: si pianifica e i pasti entrano subito ufficiali, con
  le ricette e la scheda dei cambi alla dispensa.
- **Prima della spesa**: si pianifica una **bozza** di pasti, che serve a compilare la
  lista. Claude propone le voci mancanti in lista (la scheda dei cambi, con le sole
  righe della lista) e i pasti entrano nella settimana come bozza, riconoscibili a
  colpo d'occhio. Al ritorno, dopo «Sistema la spesa», si **ufficializza**: Mattia
  dice cosa ha trovato e cosa no («il merluzzo non c'era, ho preso il salmone in
  offerta»), Claude legge la dispensa già aggiornata, rivede la bozza e la propone
  come pasti ufficiali. Solo allora si scrivono le ricette e arriva la scheda dei cambi
  alla dispensa. Così quello che si è comprato per un pasto non resta «libero» in
  dispensa: lo toglie l'ufficializzazione, come oggi lo toglie Mattia quando scrive il
  pasto sul planner.

Una bozza si può anche ufficializzare a mano, pasto per pasto, senza Claude: il pasto
diventa ufficiale senza ricetta (si scrive con «Scrivi la ricetta») e spena propone la
scheda dei cambi vuota, da compilare a mano **(scelta di Claude)**. Una bozza rimasta
tale nel passato si mostra come «non registrata».

Il giro della conversazione è quello della skill (§7). Quando Claude propone dei pasti, la proposta arriva
come una **scheda** nella chat: posto per posto, il piatto e gli accompagnamenti. Mattia
la discute a parole («il salmone no, facciamo merluzzo») e Claude ne manda una nuova.
Con **«Metti nella settimana»** i pasti entrano nei loro posti, ognuno con la sua
ricetta. Se un posto è già occupato la scheda lo dice, e mettere il pasto sostituisce
il vecchio solo con una conferma.

**Quando si scrivono le ricette (scelta di Claude).** La scheda della proposta porta
solo piatti e accompagnamenti: rivedere la proposta non costa ricette scritte e poi
buttate. Le ricette si scrivono quando i pasti diventano ufficiali, una per pasto: i
pasti entrano subito nella settimana con «ricetta in preparazione», e ognuno riceve la
sua appena è pronta. Se una ricetta non arriva (limite del piano, errore), il pasto resta
nella settimana senza ricetta, con «Chiedi la ricetta a Claude» per riprovare e
«Scrivi la ricetta» per farla a mano. Nessun pasto resta bloccato.

Subito dopo, Claude manda la **scheda dei cambi** a dispensa e lista (§6.2).

«Pianifica con Claude» riapre l'ultima conversazione di pianificazione, se non è
conclusa; una conversazione si conclude quando i suoi pasti sono messi nella settimana
e la scheda dei cambi è applicata o scartata. C'è sempre un «Nuova» per ricominciare
**(scelta di Claude)**.

### 5.3 Il piatto (versione A)

- In alto, la ricetta: titolo, porzioni, accompagnamenti, ingredienti, procedimento.
  «Modifica» apre il modulo di sempre, «Salva nel ricettario» la porta nel ricettario.
  Il piatto, gli accompagnamenti e il posto si correggono a mano anche da qui.
- Sotto, la chat del piatto, con il campo in fondo.
- Quando una risposta di Claude cambia la ricetta, nella chat compare, sotto il
  messaggio, una riga del tipo «Ricetta aggiornata: spinaci congelati, padella unica»,
  con **«Annulla»** che rimette la versione di prima **(scelta di Claude)**. Nella
  ricetta, le righe cambiate restano evidenziate fino al messaggio successivo.
- Niente «Cucina» per la ricetta aperta da un pasto: la dispensa è già stata aggiornata
  alla pianificazione (§6.2). Aperta dal ricettario, dopo «Salva nel ricettario», la
  stessa ricetta ha «Cucina» come tutte le altre.

### 5.4 Utensili

Dal ☰, accanto all'Anagrafica **(scelta di Claude)**: l'elenco, un campo per
aggiungere, e su ogni riga la correzione e la rimozione. Vuoto, dice cosa serve:
«Scrivi gli strumenti che hai in cucina: le ricette scritte dall'AI useranno solo
quelli».

## 6. Cosa può fare Claude

Claude lavora solo con strumenti di spena: niente file, niente shell, niente web
(gli strumenti integrati dell'Agent SDK sono spenti), e nessuna istruzione caricata da
`CLAUDE.md` o dalle impostazioni del server.

### 6.1 Leggere

- la dispensa, per reparto, con stati e scadenze (le voci non alimentari si ignorano);
- la lista della spesa attiva;
- i pasti di un intervallo di date, con le loro ricette;
- gli utensili;
- l'anagrafica degli ingredienti (ricerca per nome), per agganciare le righe.

**Il ricettario non si legge**, come nella skill: le ricette le inventa Claude, partendo
da dispensa ed equilibrio **(scelta di Claude, che mantiene la regola della skill)**.
Le ricette dei pasti passati invece si leggono, perché sono la storia («rifacciamo la
frittata di martedì»).

### 6.2 Proporre, mai applicare da solo

- **Pasti**: la scheda della pianificazione (§5.2). Entrano nella settimana solo con il
  tocco di Mattia.
- **Cambi a dispensa e lista**: una scheda con le stesse colonne della tabella della
  skill (voce, ora, diventa), uno stato proposto per ogni voce e le voci finite già
  proposte in lista. Mattia toglie o corregge le righe nella scheda (una casella per
  riga, lo stato modificabile) **(scelta di Claude: nella skill si correggeva a parole,
  qui si tocca)** e preme **«Applica»**. Gli stati passano da `set_status`, le voci in
  lista da `restock`/l'aggiunta di sempre, in una transazione. Nessun duplicato in
  lista.
  - Quando i pasti diventano ufficiali, per le cose che usano. Da quel momento la
    dispensa è «al netto» dei pasti pianificati, come oggi. Per una bozza la scheda ha
    solo le righe della lista (§5.2).
  - In una chat del piatto: quando una modifica cambia cosa si usa («non ho spinaci, uso
    le zucchine»), Claude può proporre la stessa scheda.
  - **Un pasto tolto o sostituito dopo che i suoi cambi sono stati applicati (scelta di
    Claude).** Senza quantità, l'inverso non si ricava dallo stato di oggi. Per questo
    ogni scheda applicata si conserva legata ai suoi pasti, con lo stato di prima di
    ogni voce. Quando un pasto si cancella, si sostituisce o diventa «fuori casa»,
    spena propone la scheda inversa («rimetti in dispensa: spinaci → c'è») anche senza
    Claude, e Mattia la applica o la scarta. Spostare un pasto su un altro posto non
    propone niente.
- Le regole della skill sugli stati restano: una confezione da una porzione diventa
  `finished`, una confezione grande resta com'è, un vasetto di sugo appena aperto
  diventa `low`; un sugo `low` è avviato, non in esaurimento, e non va in lista per
  questo.

### 6.3 Scrivere la ricetta del piatto

Nella chat del piatto, Claude cambia la ricetta direttamente, senza una scheda da
confermare (deciso da Mattia: «il messaggio verrebbe mandato comunque» e la scheda si
aggiorna). La sicurezza sta altrove:

- ogni scrittura passa da `write_recipe_ingredients`: niente righe non alimentari, e
  ogni riga punta a un ingrediente vero. Per un nome che l'anagrafica non conosce si usa
  lo stesso percorso del modulo (`ingredient_for_new_name`), compreso il rifiuto di un
  non alimentare. Se una riga non si riesce ad agganciare, lo strumento lo dice a Claude
  e non scrive niente di parziale;
- ogni modifica salva la versione di prima, e «Annulla» la rimette (§5.3);
- nella stessa modifica Claude può correggere anche il **piatto e gli accompagnamenti**
  del pasto, perché la settimana non dica «Frittata di spinaci» dopo il passaggio alle
  zucchine; «Annulla» rimette anche quelli. Il posto (data e pranzo/cena) Claude non lo
  cambia dalla chat del piatto **(scelta di Claude)**;
- `quantity_text` è la verità mostrata, e i valori strutturati si riempiono con il
  parser delle quantità, come per ogni altra ricetta.

## 7. Come ragiona Claude: la skill `pasti` adattata

Il prompt di sistema è la skill `pasti` riscritta per spena **(il testo esatto è del
costruttore, partendo da `~/.claude/skills/pasti/SKILL.md`)**. Restano:

- **leggere solo quello che serve alla domanda** (la tabella in testa alla skill): una
  domanda di tecnica non legge niente, un piatto deciso legge la dispensa, una
  pianificazione legge pasti recenti, dispensa e lista;
- **la dispensa è già al netto dei pasti pianificati**: non sottrarli di nuovo;
- **i sughi avviati** (`low` su pesto, sughi, ragù) sono da usare presto, non da
  ricomprare;
- **il quadro della settimana** solo quando si pianifica o Mattia chiede
  dell'equilibrio: gruppi (carboidrati, proteine per fonte, verdura, frutta), i piatti
  composti scomposti, gli squilibri detti con i numeri dei pasti, e il sale stimato
  contro i 5 g al giorno, sempre come stima. La tabella del sale della skill passa nel
  prompt;
- **proposte varie**, con precedenza a scadenze, sughi avviati e confezioni aperte, e
  per ognuna perché aiuta l'equilibrio;
- **un piatto già deciso non si sostituisce**: lo si aiuta a venire bene, con i
  sostituti presi da casa;
- **le parole incerte si chiedono**, non si indovinano.

Cambiano:

- **le dosi**: Mattia non ragiona in persone ma in quantità di ingredienti (2026-11-12).
  Claude scrive ogni ricetta con le quantità del pasto così come lo si mangerà, di
  norma per lui solo (`servings = 1`), e le misura su quello che c'è in casa e sulle
  confezioni («150 g dalla busta da 1 kg»). Per cambiare le dosi si cambia
  l'ingrediente: in chat («ho solo 2 uova») o con il riscalamento per ingrediente che
  spena ha già (R2, tocco sulla dose);
- **l'equilibrio resta approssimativo** (deciso da Mattia il 2026-11-12: inserire valori
  nutrizionali precisi è troppo lavoro). Quando pianifica, Claude guarda i pasti delle
  settimane precedenti per bilanciare i gruppi, come fa la skill, e niente di più:
  nessun punteggio, nessun nutriente calcolato;
- i pasti si leggono da spena: non c'è più il planner da trascrivere, né «barrato» o
  «non registrato». Un posto passato vuoto è non registrato, uno futuro vuoto è da
  pianificare;
- **ogni ricetta rispetta gli utensili**: se lo strumento classico manca (la frusta per
  le chiare), Claude propone un'altra tecnica o dice che senza quello il piatto non si
  fa. Con l'elenco vuoto non c'è nessun vincolo **(scelta di Claude)**;
- Claude non scrive più tabelle da copiare: propone con le schede di §6.2.

Lo sforzo (`effort`) e i token massimi li sceglie il costruttore; il punto di partenza è
`medium` per la chat del piatto e `high` per la pianificazione **(scelta di Claude)**.

## 8. Utensili nelle altre ricette dell'AI

L'elenco degli utensili entra anche nei prompt della bozza AI (`draft_recipe`) e della
variante (`draft_variant`, R8), che oggi girano su Gemma **(scelta di Claude: Mattia ha
chiesto che «le ricette non dicano di usare strumenti che non ho»; costa una riga di
prompt)**. Le ricette importate non cambiano.

## 9. Quando Claude non c'è

Il token manca o è scaduto, il limite del piano è raggiunto, la rete cade, la risposta
non arriva entro un tempo massimo. In ogni caso:

- la chat mostra un avviso in parole semplici («Claude non risponde: hai raggiunto il
  limite del piano, riprova dopo le 18:40» quando l'ora si conosce) e il messaggio di
  Mattia resta, pronto da rimandare;
- la settimana, i pasti a mano, la ricetta e il suo modulo funzionano tutti senza
  Claude;
- una risposta interrotta a metà non lascia una ricetta scritta a metà: le scritture
  della ricetta sono atomiche (§6.3).

La sezione nelle spese dell'AI (H1) mostra le chiamate e i token senza costo, con una
nota: «sul piano di Claude, non a consumo».

## 10. Cosa resta al costruttore

- L'integrazione con l'Agent SDK: come girano gli strumenti di spena (server MCP nel
  processo), lo streaming verso il frontend (per esempio SSE), la persistenza delle
  sessioni, i tempi massimi. Va verificato sulla documentazione corrente dell'SDK, non
  a memoria: cosa serve nell'immagine (il binario di Claude Code incluso nel pacchetto o
  Node), come si spengono gli strumenti integrati e il caricamento delle impostazioni.
- Il nome delle tabelle, delle rotte e dei componenti; l'aspetto delle schermate dentro
  il sistema visivo di spena.
- La forma esatta degli strumenti di Claude e del prompt di sistema.
- Come si divide il lavoro in consegne. Un ordine sensato: (1) Utensili, piccola e
  indipendente; (2) pasti e settimana a mano, con le ricette fuori dal ricettario; (3)
  Claude e la chat del piatto; (4) la pianificazione con le schede dei cambi.

## 11. Cosa cambia nel resto del progetto

- In `docs/prossimi-passi.md` la Parte IV punta a questa spec: P1 e P3 sono sostituiti.
  Escono anche P2 (NutriScore), M1 (motore di suggerimento) e H3 (Profilo): il
  NutriScore diventa lo sguardo approssimativo di Claude sui pasti precedenti (§7), e il
  suggerimento è la pianificazione con Claude. Il Profilo serviva solo a P2.
- In `next-steps.md` escono le voci P1, P2, P3, M1 e H3; la voce «Sezione Pasti» e la
  voce «Utensili» diventano piani.
- La skill `pasti` di Claude Code resta finché la sezione non è in produzione e provata;
  poi va ritirata o ridotta.
- `CLAUDE.md`: la sezione su LLM e fornitori (§3), e una riga sulle ricette fuori dal
  ricettario accanto a quella sulle ricette archiviate.
