# H2, l'attività da Health Connect via HC Webhook — design

_2026-10-13. Voce `[H2]` di `docs/prossimi-passi.md` («## H2. Connettore Samsung Health»),
legata a P2 (il fabbisogno) e H3 (il Profilo). Piano:
`docs/superpowers/plans/2026-10-13-h2-health-connect.md`._

## 1. Contesto

P2 vuole un fabbisogno calorico che tenga conto dell'attività, e inserirla a mano non si fa.
La via ufficiale di Samsung (l'SDK di Samsung Health) chiede di diventare partner. La ricerca
del 2026-10-13 ha trovato una strada praticabile:

- **Samsung Health scrive in Health Connect** (Impostazioni › Health Connect): i passi
  (`StepsRecord`), gli allenamenti (`ExerciseSessionRecord`, con le calorie per allenamento
  scritte a parte come record di calorie), il peso, la massa grassa, il metabolismo basale,
  l'altezza. **Non** scrive il riepilogo giornaliero delle calorie attive.
- **HC Webhook** (https://github.com/mcnaveen/health-connect-webhook, AGPL, su Google Play
  e come APK) legge Health Connect sul telefono e manda i dati a un indirizzo con un
  `POST` JSON, con le intestazioni che si configurano per ogni webhook.

Cosa manda HC Webhook, letto il 2026-10-13 nei suoi `docs/webhook.md`, `docs/api-reference.md`,
`docs/features.md` e nel sorgente (`SyncManager.kt`, `HealthConnectManager.kt`,
`DataResolution.kt`, `MockPayloadBuilder.kt`, `WebhookManager.kt`):

- **Il corpo** è un oggetto JSON con `timestamp` (quando è stato costruito, ISO-8601 UTC con
  `Z`) e `app_version` sempre, poi un elenco per ogni tipo che ha almeno un record nuovo:
  la chiave manca se non c'è niente, un elenco non è mai vuoto. Gli istanti sono
  `Instant.toString()` (`2026-05-09T12:34:56.789Z`, fino a nove decimali).
- **`steps`**: `count` (intero), `start_time`, `end_time`. Tre forme, scelte nell'app alla
  voce «Risoluzione passi»: **«Giornaliero» (quella di default)** manda un totale per giorno
  di calendario del telefono, calcolato con la lettura *aggregata* di Health Connect, senza
  `metadata`; il primo giorno della finestra parte dall'inizio della finestra e non dalla
  mezzanotte, e il giorno in corso finisce adesso. «Completo» manda ogni intervallo grezzo,
  con un oggetto `metadata` (`data_origin`, `recording_method`, `device`). «1 / 5 / 15 min»
  somma gli intervalli grezzi in finestre allineate al minuto, senza `metadata`.
- **`exercise`**: `type` (la costante intera di Health Connect **scritta come stringa**,
  `"56"` è la corsa), `title` facoltativo, `start_time`, `end_time`, `duration_seconds`,
  e se ci sono `distance_meters`, `steps`, le cadenze; più `metadata`. **Nessuna caloria**:
  il corpo non porta il dispendio dell'allenamento.
- **`weight`**: `kilograms`, `time`, `metadata`.
- Gli altri tipi (`heart_rate`, `sleep`, `active_calories`, `body_fat`,
  `basal_metabolic_rate`, `height`…: 31 in tutto) hanno forme loro; nuovi tipi e campi
  possono arrivare a ogni versione.
- **Quando**: a intervallo (default 60 minuti, minimo 15) o a orari fissi, più la
  «Sincronizzazione manuale». Si legge una finestra di **48 ore**, e per ogni tipo solo i
  record nuovi o aggiornati dall'ultima sincronizzazione riuscita di quel tipo (la prima
  volta, tutta la finestra). La manuale può chiedere «Ultimi 30 giorni», e allora manda
  tutto il periodo, senza filtro.
- **Consegna**: riuscita per qualunque 2xx; tre tentativi con attesa crescente, poi si
  riprova alla sincronizzazione dopo. Il registro dell'app mostra stato e corpo della
  risposta.
- **«Testa Webhook»** manda un corpo finto, con `"test": true` in cima, dati inventati
  e `metadata` di un Pixel Watch.
- Ogni webhook ha un filtro dei tipi («Tipi di dati»); le intestazioni si scrivono a mano
  («Modulo») o incollando un oggetto JSON («JSON» › «Applica JSON»).

## 2. Le decisioni di Mattia (2026-10-13)

1. **La via è HC Webhook, subito**, con la PWA di oggi. Più avanti, col wrapper Capacitor,
   la lettura di Health Connect passerà dentro l'app (fuori scope); il backend resta lo
   stesso.
2. **Spena legge passi, allenamenti e peso.** Il dispendio lo calcolerà Spena (passi e
   allenamenti col metodo a MET, più il metabolismo di base dal Profilo), ma **il calcolo
   del fabbisogno è di P2 e H3**: questa voce riceve, salva e mostra i dati (§9 dice cosa
   resta a P2).
3. **I dati arrivano da telefono e Galaxy Watch**: va deciso come evitare i doppioni (§3.2).

Il resto è delegato: le scelte tecniche ed estetiche le prende Claude.

## 3. Le decisioni di Claude (su delega di Mattia)

### 3.1 La rotta e la chiave

1. **La rotta del webhook** è `POST /api/v1/activity/hc-webhook`, **fuori dalla sessione**
   dell'app: HC Webhook non ha il cookie. La autentica una **chiave dedicata** nell'intestazione
   **`X-Spena-Token`** (un nome solo da incollare, senza il «Bearer » da scrivere a mano sul
   telefono).
2. **La chiave** è `secrets.token_urlsafe(32)`: 43 caratteri, 256 bit. Il database ne tiene
   **solo l'impronta** (SHA-256: con 256 bit casuali non serve un hash lento) in una tabella a
   riga unica, con quando è stata creata e quando è stata usata l'ultima volta. **Si vede
   una volta sola**, quando la si crea; persa, si **rigenera**, e la vecchia smette subito di
   funzionare. Crearla e rigenerarla vuole la sessione (`POST /api/v1/activity/token`).
3. **Il rifiuto è silenzioso**: intestazione mancante, di forma sbagliata, chiave sbagliata,
   nessuna chiave configurata danno tutti lo **stesso `401` senza corpo**, prima di leggere il
   corpo e senza scrivere niente. Una forma sbagliata (lunghezza o caratteri) si rifiuta
   senza toccare il database; il confronto è `hmac.compare_digest` fra le impronte, e senza
   chiave configurata si confronta comunque con un'impronta finta, così il tempo non dice
   se una chiave c'è.
4. **Limiti**: il corpo si legge a pezzi e si ferma oltre **2 MB** (`413`). Nginx, che davanti
   ha 1 MB di default, per questa sola rotta ne accetta 4: oltre i 2 MB il rifiuto lo dà il
   backend, che lo **registra** e lo fa vedere in «Attività», invece di un 413 di Nginx che
   nessuno vede. Al massimo 5.000 voci per tipo per corpo. Spena con solo i suoi tre tipi
   manda pochi kB; i 2 MB servono a chi lascia attivi tutti e 31 i tipi.
5. **Mai un 500 su un corpo inatteso.** Un corpo che non è JSON (anche annidato a fondo, che
   in Python solleva `RecursionError`), o che è JSON ma non un oggetto → `400`, registrato.
   Dentro un oggetto, ogni voce si legge da sola: una voce illeggibile si scarta e si conta,
   le altre si salvano; un tipo che non è un elenco si salta; numeri non finiti, booleani
   dove va un numero, istanti senza fuso o fuori dagli anni 2000–2100 sono illeggibili.
   Le chiavi che Spena non usa si **registrano per nome** (mai il contenuto). Risposta
   `200` con quel che si è salvato, scartato e ignorato (HC Webhook la mostra nel registro).
6. **Il registro delle sincronizzazioni** tiene, per ogni corpo autenticato: quando, esito
   (`ok`, `test`, `rejected`), versione dell'app, istante di costruzione del corpo, peso in
   byte, quante voci salvate per tipo, i nomi delle chiavi ignorate, i problemi in italiano.
   **Il corpo non si conserva**: ci sarebbero dati di salute che Spena non ha chiesto.
   Restano le ultime 200 righe.
7. **La prova** (`"test": true`) non salva niente: si registra come `test` e si risponde 200.
8. Le richieste del webhook passano una alla volta (`pg_advisory_xact_lock`): due invii che
   si sovrappongono (un tentativo ripetuto) non si contendono la stessa riga dei passi.

### 3.2 I doppioni fra telefono e orologio

Health Connect toglie i doppioni **solo nelle letture aggregate**: quando più app scrivono
passi sugli stessi minuti, l'aggregato conta una volta sola, secondo la priorità delle app
(Health Connect › Dati e accesso › priorità). Le letture grezze no: due record di due
origini sullo stesso intervallo si sommerebbero. Samsung Health, da parte sua, unisce
telefono e Galaxy Watch prima di scrivere, con un'origine sola
(`com.sec.android.app.shealth`).

9. **I passi si accettano solo nella forma «Giornaliero»** di HC Webhook, che è quella di
   default ed è l'unica calcolata con la lettura aggregata. Un record dei passi con
   `metadata` («Completo») o che dura al più 60 minuti con inizio e fine al minuto tondo
   (le finestre «1 / 5 / 15 min») **non si salva**: si registra il problema, che dice di
   scegliere «Giornaliero». Il totale giornaliero vero finisce adesso (con i millisecondi)
   o dura un giorno intero: non si confonde con una finestra.
10. **Un giorno ha un totale solo, mai una somma.** Il giorno è quello di Roma dell'inizio
    del record (il telefono di Mattia è sullo stesso fuso). Per ogni giorno Spena tiene il
    totale con l'intervallo che copre, e un record nuovo dello stesso giorno:
    - copre almeno lo stesso intervallo (stesso inizio e fine uguale o dopo, o di più) → lo
      **sostituisce**, anche se più basso (è una correzione);
    - sta dentro l'intervallo già tenuto → **si ignora** (è un pezzo già contato);
    - si sovrappone in parte o sta accanto (solo dopo un buco di più di un giorno fra due
      sincronizzazioni) → resta **il più alto** dei due: sommarli conterebbe due volte le
      ore in comune.
11. **Gli allenamenti** sono una riga per `(origine, inizio)`: lo stesso allenamento rimandato
    aggiorna la sua riga (la fine, il titolo, la distanza), non ne crea un'altra. Due
    allenamenti di due app diverse che si sovrappongono restano due righe, ognuna con la sua
    origine scritta a video; contare una volta sola il tempo in comune è del calcolo di P2
    (§9).
12. **Le pesate** sono una riga per `(origine, istante)`, aggiornata se torna.

### 3.3 Cosa si salva

13. Migrazione `0018` (riservata a H2 dall'orchestrazione; `down_revision = "0012"`, da
    ripuntare al merge sulla testa di `master` di quel momento). Cinque tabelle:
    `activity_tokens` (riga unica, `id = 1`), `activity_steps_days` (`day` chiave,
    `steps`, `covered_from`, `covered_to`), `activity_exercises` (`source`, `started_at`,
    `ended_at`, `day`, `exercise_type` intero o nullo, `title`, `distance_m`, `steps`),
    `activity_weights` (`source`, `measured_at`, `day`, `kilograms`), `activity_syncs`.
    I giorni sono di Roma come la scadenza (`PANTRY_TZ`).
14. **Il tipo dell'allenamento** si tiene come la costante intera di Health Connect, non
    tradotta: è la chiave su cui P2 metterà i MET. Un tipo illeggibile resta nullo, e
    l'allenamento si salva lo stesso. Il nome a video è una tabella del backend
    (`EXERCISE_LABELS`, 60 tipi in italiano); uno sconosciuto si chiama «Allenamento».
15. Le calorie per allenamento di Samsung Health non arrivano nel corpo (§1), e non si
    chiedono: il dispendio lo calcola Spena (decisione 2).

### 3.4 A video

16. **Dove: il ☰, voce «Attività»**, percorso `/attivita`; il collegamento è una sottosezione,
    `/attivita/collega`, col tasto indietro. Non dentro il Profilo: il Profilo non esiste
    (H3 è bloccato su P2), e i dati arrivano prima.
17. **«Attività»** mostra: l'ultima sincronizzazione (quando, a Roma; se era la prova o un
    rifiuto; i problemi; i tipi arrivati e non usati; un avviso se da più di 24 ore non
    arriva niente); **i passi degli ultimi 7 giorni** (oggi per primo, «nessun dato» dove
    manca); **gli allenamenti degli ultimi 7 giorni** (il più recente per primo, al più 20);
    **le ultime 5 pesate**; un collegamento a «Collegamento con HC Webhook». Mai
    sincronizzato: uno stato vuoto che dice cosa manca e porta al collegamento.
18. **«Collega HC Webhook»**: la chiave (crea, o rigenera con una conferma), poi i passi da
    fare in HC Webhook uno per uno, con l'indirizzo e le intestazioni da copiare con un
    tocco (un campo di sola lettura e «Copia»; se il telefono non lascia copiare, il testo
    si seleziona e si copia a mano). Le intestazioni in JSON (`{"X-Spena-Token": "…"}`) si
    vedono solo insieme alla chiave appena creata.
19. Il backend decide tutto quel che è dominio: i giorni di Roma, l'ora a Roma (`"18:05"`),
    i 7 giorni coi buchi, i minuti, i chilometri, i nomi degli allenamenti, delle app e dei
    tipi ignorati, se la sincronizzazione è vecchia. Il frontend scrive «Oggi» / «Ieri» /
    «lun 12 ott», i numeri all'italiana, e disegna.
20. Nessuna dipendenza nuova, nessun grafico (sette numeri si leggono meglio così), nessun
    token di colore nuovo. Un'icona nuova da `@tabler/icons-react`, che c'è già: `IconCopy`.

## 4. Le parole a video

**Nel ☰:** «Attività».

**«Attività»** (`/attivita`): titolo «Attività», sotto «Passi, allenamenti e peso da Health
Connect.»

- Caricando: «Carico l'attività…». Guasto: «Non sono riuscito a leggere l'attività.» con
  «Riprova».
- Mai sincronizzato: titolo «Nessun dato da Health Connect, per ora», testo «Spena riceve
  passi, allenamenti e pesate da HC Webhook, un'app per Android che li legge da Health
  Connect, dove li scrive Samsung Health. Si collega una volta sola.», pulsante «Collega HC
  Webhook».
- L'ultima sincronizzazione: «Ultima sincronizzazione: {quando}.»; la prova: «Ultima
  sincronizzazione: {quando}, la prova di HC Webhook: arrivata, e non salva niente.»; un
  rifiuto: «Ultima sincronizzazione: {quando}, rifiutata.». {quando} è «oggi alle 14:05»,
  «ieri alle 23:50», «12 ottobre alle 09:10».
- Vecchia: «Da più di un giorno non arriva niente. Controlla che HC Webhook non sia
  limitato dall'ottimizzazione della batteria, e prova «Sincronizza ora».»
- I problemi, uno per riga, come li scrive il backend:
  - «Passi non salvati: arrivano a intervalli e non come totale del giorno. In HC Webhook,
    alla voce «Risoluzione passi», scegli «Giornaliero».»
  - «{Passi | Allenamenti | Pesate}: 1 voce illeggibile, scartata.» / «…: {n} voci
    illeggibili, scartate.»
  - «{tipo}: non è un elenco, non letto.» / «{tipo}: {n} voci, lette le prime 5000.»
  - «Rifiutato: il corpo supera i 2 MB. Nel webhook di Spena, in HC Webhook, lascia solo
    Passi, Sessioni di esercizio e Peso.»
  - «Rifiutato: il corpo non è JSON.» / «Rifiutato: il corpo è JSON, ma non un oggetto.»
- I tipi non usati: «Arrivati e non usati: frequenza cardiaca, sonno. Nel webhook di Spena,
  in HC Webhook, si possono togliere.»
- Le tre sezioni: «Passi», «Allenamenti», «Peso». Una riga dei passi: «Oggi» / «Ieri» /
  «lun 12 ott» e «8.421» o «nessun dato». Un allenamento: «Corsa · 32 min · 5,1 km» (con
  il titolo: «Corsa («Giro del parco») · 32 min»), sotto «Oggi, 18:05 · Samsung Health».
  Una pesata: «72,4 kg», sotto «Oggi, 07:30». Vuoti: «Nessun allenamento negli ultimi 7
  giorni.», «Nessuna pesata, per ora.»
- In fondo: «Collegamento con HC Webhook».

**«Collega HC Webhook»** (`/attivita/collega`, indietro ad «Attività»): sotto il titolo «Una
volta sola, dal telefono con Samsung Health.»

- «La chiave». Senza: «Spena accetta i dati solo da chi porta la sua chiave. Creala, poi
  incollala in HC Webhook come dicono i passi qui sotto.» e «Crea la chiave». Appena creata:
  «Ecco la chiave. Si vede solo adesso: copiala in HC Webhook prima di uscire da qui.» e il
  campo «Chiave». Già creata: «Chiave creata {quando}. Usata l'ultima volta {quando}.» (o
  «Non ancora usata.»), «La chiave si vede solo quando la crei. Se non l'hai più,
  rigenerala: quella di prima smette di funzionare.» e «Rigenera la chiave»; la conferma:
  «La chiave di adesso smetterà di funzionare, e in HC Webhook andrà incollata quella
  nuova.» con «Rigenera» e «Annulla». Guasto: «Non sono riuscito a creare la chiave.»; lo
  stato della chiave che non si legge: «Non sono riuscito a leggere la chiave.» con «Riprova».
- «In HC Webhook», i passi:
  1. «In Samsung Health: Impostazioni › Health Connect. Lascia scrivere a Samsung Health
     passi, esercizio e peso, e tieni attiva la sincronizzazione con Samsung Cloud.»
  2. «Installa HC Webhook (Health Connect to Webhook) da Google Play.»
  3. «Aprila e attiva Passi, Sessioni di esercizio e Peso fra i «Tipi di dati»; concedi i
     permessi di Health Connect, anche quello in background.»
  4. «Alla voce «Risoluzione passi» lascia «Giornaliero»: così Health Connect conta una volta
     sola i passi del telefono e dell'orologio.»
  5. «In «Webhook» aggiungi questo indirizzo:» e il campo «Indirizzo».
  6. «Nel webhook, «Gestisci intestazioni» › «JSON»: incolla questo e tocca «Applica JSON».»
     e il campo «Intestazioni (JSON)»; senza una chiave appena creata: «Le intestazioni da
     incollare compaiono qui quando crei la chiave.»
  7. «Sempre nel webhook, fra i «Tipi di dati» scegli solo Passi, Sessioni di esercizio e
     Peso.»
  8. «Tocca «Testa Webhook»: in «Attività», l'ultima sincronizzazione deve dire che è
     arrivata la prova.»
  9. «Intervallo: 15 minuti o più. E togli HC Webhook dall'ottimizzazione della batteria
     («Ottimizzazione batteria attiva» › «Risolvi ora»), o Android salta le
     sincronizzazioni.»
  10. «Per portare i giorni passati: «Sincronizzazione manuale» › «Ultimi 30 giorni».»
- «Copia» accanto a ogni campo; copiato: «Copiato.»; non riuscito: «Non riesco a copiare:
  tieni premuto sul testo e copialo a mano.»

**I nomi** (backend): gli allenamenti secondo `EXERCISE_LABELS` (56 «Corsa», 79
«Camminata», 8 «Bicicletta», 70 «Allenamento di forza», 74 «Nuoto in piscina», …; gli
altri «Allenamento»); le app: «Samsung Health», «Google Fit», «Health Connect», «Strava»,
«Fitbit», l'origine vuota «origine non indicata», le altre col nome del pacchetto; i tipi
ignorati: «frequenza cardiaca», «sonno», «calorie attive», «calorie totali», «distanza»,
«altezza», «massa grassa», «metabolismo basale», … e gli sconosciuti col nome com'è.

## 5. Sicurezza ed esposizione

L'app è già su internet dietro Traefik; questa è la prima rotta fuori dalla sessione che
scrive. Oltre al §3.1: nessun dato nell'indirizzo (la chiave sta nell'intestazione, e i
registri di accesso scrivono solo il percorso); nessuna scrittura senza la chiave giusta;
il registro tiene solo nomi e conteggi. Un limite di frequenza non serve alla chiave (256
bit non si indovinano) e una richiesta senza chiave costa al più una lettura di una riga:
niente limitatore nell'app, che senza un IP affidabile dietro due proxy potrebbe solo
bloccare anche il telefono di Mattia.

## 6. Dopo il deploy (solo Mattia)

La migrazione `0018` la fa il backend all'avvio. Poi, sul telefono: installare HC Webhook;
in Samsung Health › Impostazioni › Health Connect lasciar scrivere passi, esercizio e peso,
con la sincronizzazione di Samsung Cloud attiva; togliere HC Webhook dall'ottimizzazione
della batteria; la **prova dei 10 minuti** in Health Connect › Dati e accesso (Samsung Health
scrive passi, esercizio, calorie, peso; i dati di ieri ci sono); poi in Spena crea la chiave,
configura indirizzo e intestazioni come dicono i passi, «Testa Webhook», e controlla
«Attività». Il piano ha i comandi esatti.

## 7. Fuori scope

- La lettura di Health Connect dentro l'app col wrapper Capacitor (decisione 1).
- Il calcolo del dispendio e del fabbisogno (P2, H3: §9).
- Gli altri tipi di Health Connect (sonno, frequenza cardiaca, calorie, massa grassa,
  metabolismo basale, altezza): arrivano, si registrano per nome, non si salvano.
- Cancellare i dati arrivati, scollegare senza rigenerare, più di una chiave, un grafico
  dei passi, una vista oltre i 7 giorni.
- Il formato Protobuf/gRPC di HC Webhook, e il suo server HTTP locale.

## 8. Domande aperte

Nessuna.

## 9. Per P2 e H3 (rinviato, non si costruisce qui)

Il dispendio del giorno lo calcolerà P2 con una funzione pura in `backend/app/domain/`,
sopra le tabelle di questa voce. Quel che questa voce lascia pronto e quel che P2 dovrà
decidere:

- `activity_energy_kcal(day) = Σ allenamenti MET(tipo) × peso × ore + passi fuori dagli
  allenamenti × kcal per passo`, più il metabolismo di base del Profilo (H3; per esempio
  Mifflin-St Jeor da peso, altezza, età e sesso).
- I MET per tipo vanno su `exercise_type` (la costante di Health Connect), da una tabella
  del Compendium of Physical Activities; un tipo sconosciuto o nullo prende un MET di
  ripiego da decidere.
- I passi fuori dagli allenamenti: il totale del giorno meno i `steps` degli allenamenti di
  quel giorno, dove ci sono; da decidere la stima dove mancano.
- Il tempo in comune fra due allenamenti di due app (§3.2, 11) si conta una volta sola.
- Il peso è l'ultima pesata fino a quel giorno; senza una pesata il dispendio è **assente**,
  non zero («l'assenza resta assenza», come i nutrienti).
- H3 dovrà decidere se il peso del Profilo è l'ultima pesata di Health Connect o un numero
  scritto a mano, e quale vince.
