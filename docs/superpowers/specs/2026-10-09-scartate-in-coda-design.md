# Le pagine scartate dell'import, a video e rimesse in coda — disegno

_Scritto il 2026-10-09, fase giorno. Voci di `next-steps.md`: «Una pagina `SKIPPED` non
torna mai in coda, anche dopo aver corretto la causa» (`tbd`) e «`skipped_reason` non
affiora da nessuna rotta né schermata» (`idea`), entrambe [Parte X]. Piano:
`docs/superpowers/plans/2026-10-09-scartate-in-coda.md`._

## 1. Il problema

Una pagina scaricata da GialloZafferano diventa ricetta quando tutti i suoi termini sono
decisi (`materialize_ready`, `backend/app/services/recipe_import/materialize.py`). Se non
può diventarlo, finisce `skipped` con un motivo in `recipe_imports.skipped_reason`, e da
lì non esce più:

- **nessuna strada dell'app la rimette `pending`**: `undo_decision` riprende solo le
  pagine `imported` con la loro ricetta, e né la coda né `fix_registry` né un comando
  toccano le scartate (Parte X, verificato sul codice e con i test del 2026-09-28 in
  `backend/tests/services/test_undo.py`);
- **il motivo non si vede**: `/api/v1/imports/status` ne dà solo il numero (`skipped`).
  Chi vuole sapere perché deve aprire il database.

Così una ricetta scartata per una «riga non alimentare» resta fuori anche dopo che
l'ingrediente è tornato cibo, o che il termine è stato rideciso; e le cotture che
aspettavano nel suo `payload` (`cooking_event_ids`, lasciati lì da un annullamento:
nota della revisione del Task 3 di S9) restano senza ricetta.

Le scartate oggi sono di tre tipi, riconoscibili dai dati che la pagina conserva:

| Tipo | Chi la scarta | `payload` | `skipped_reason` |
|---|---|---|---|
| **illeggibile** | `store_unparsable` (`backend/app/repositories/imports.py`), allo scarico | `{}`: niente titolo, niente righe | il perché del lettore della pagina, per esempio «nessuna riga dd.gz-ingredient nella pagina», «la fonte ha risposto 404» |
| **tutte ignorate** | `materialize_ready` | la pagina intera | `EMPTY_REASON` |
| **riga non alimentare** | `materialize_ready`, quando `create_recipe` solleva `NonFoodInRecipe` | la pagina intera | «riga non alimentare: «…»», col nome della voce |

Una pagina illeggibile non ha niente da materializzare: il `payload` è vuoto, e
l'indirizzo non si riscarica mai (`known_urls`).

## 2. Decisioni prese

**Da Mattia, il 2026-10-09:**

1. **Una sezione «Scartate» nella coda d'import** («Ingredienti da abbinare»,
   `/ricette/importa`), **chiusa di partenza**, col numero: **«Scartate (N)»**.
2. Per ogni pagina: il **titolo** (o l'**indirizzo**, se il titolo non c'è), il **motivo
   dello scarto in parole da persona** (non il nome della variabile né il testo tecnico
   del motivo), e **«Rimetti in coda»**.
3. Rimessa in coda, la pagina torna `pending` e segue la **strada normale**,
   `materialize_ready`: se la causa è corretta diventa ricetta, rilegando le cotture che
   aspettano nel `payload`; se no torna scartata col suo motivo. **Lo si dice all'utente:
   mai un vicolo cieco.**
4. La voce chiude anche l'idea su `skipped_reason`.

**Da Claude, su delega di Mattia (tecniche ed estetiche; reversibili):**

5. **Le rotte.** `GET /api/v1/imports/pages/skipped?limit=&offset=` — l'elenco
   paginato (`limit` da 1 a 100, 50 di default; `offset` da 0), con il totale — e
   `POST /api/v1/imports/pages/{id}/requeue`. Sotto `/imports`, dietro la sessione come
   le altre.
6. **Il motivo si legge in un posto solo.** Accanto a chi lo scrive, in
   `materialize.py`, una funzione pura, `explain_skip(payload, skipped_reason)`, dà la
   causa in un codice — `unreadable`, `all_ignored`, `non_food`, `other` — col nome della
   voce non alimentare e se la pagina si può rimettere in coda. Lo scarto non alimentare
   si scrive con la stessa costante che la funzione legge (`NON_FOOD_PREFIX`): la stringa
   scritta e quella letta non possono scollarsi. Le parole da persona le scrive il
   frontend (le parole a video stanno lì in tutta l'app); il frontend non decide niente,
   traduce un codice.
7. **«Rimetti in coda» materializza subito**, nella stessa richiesta. `materialize_ready`
   oggi gira solo quando si decide un termine (a mano o con l'AI) e allo scarico:
   lasciata al ciclo normale, una pagina rimessa resterebbe `pending` senza esito
   visibile fino alla prossima decisione qualunque. La rotta rimette la pagina
   `pending`, riallinea i termini (`sync_terms`), materializza, riallinea di nuovo, e
   risponde **com'è finita quella pagina**: entrata nel ricettario (con quante cotture
   ha ritrovato), di nuovo scartata (con la causa), oppure in coda ad aspettare dei
   termini ancora da decidere (con i loro nomi) — il terzo caso c'è quando, nel
   frattempo, una decisione della pagina è stata annullata. Il primo `sync_terms` serve
   a un termine sparito dal dizionario: senza, la pagina aspetterebbe un termine che la
   coda non mostra, il vicolo cieco; il secondo rifà il conto delle `occurrences` sulle
   pagine davvero in attesa.
8. **L'esito va nell'avviso unico** (`useNotice`), come l'annullamento. Se la pagina è
   entrata, l'avviso ha l'azione **«Apri»**, che porta alla ricetta. Il rifiuto
   (pagina non più scartata, pagina illeggibile, guasto) è un `Alert` nella sezione.
9. **Ogni riga dice anche la strada**, non solo la causa: per una riga non alimentare
   «rendilo un alimento in Anagrafica, o annulla la decisione che lo ha scelto»; per le
   righe tutte ignorate «annulla la decisione su uno di loro». Così l'avviso dopo una
   rimessa che non riesce può restare corto (la causa), e la strada resta scritta nella
   riga, che non sparisce.
10. **Le cotture che aspettano si dicono nella riga** («2 cotture registrate aspettano
    questa ricetta»): è il motivo per cui conviene rimetterla, e l'unico posto dove lo si
    viene a sapere.
11. **La sezione sta in fondo alla coda**, dopo «Decisioni recenti», e non c'è quando N è
    0. Il numero è `skipped` di `/imports/status`, che la schermata legge già; l'elenco
    si chiede solo aprendo la sezione, a pagine da 50 con «Mostra altre». La chiave della
    query sta sotto `["import-status", …]`: ogni decisione, giro dell'AI o annullamento
    della coda — che possono scartare pagine — la rilegge senza toccare il loro codice.
12. **L'ordine dell'elenco**: dalla pagina scaricata per ultima (`fetched_at`
    decrescente), a parità per indirizzo.
13. **Il titolo della sezione è un pulsante dentro l'`h2`** («Scartate (N)», con
    `aria-expanded` e `aria-controls`, chevron giù aperta e a destra chiusa, alto almeno
    44 px), come l'intestazione dei reparti di S15; il contenuto chiuso ha `hidden`.
    Nessun token nuovo, nessuna animazione.

**La pagina illeggibile: opzione A, decisa da Mattia il 2026-10-13.** Rimetterla in coda non
serve: il `payload` è vuoto e l'indirizzo non si riscarica, quindi tornerebbe subito
scartata — e per giunta col motivo sbagliato, «ogni ingrediente è stato ignorato», perché
`materialize_ready` vede zero righe. Quindi **si mostra
nell'elenco col suo perché, senza «Rimetti in coda», e con «Apri la pagina»** (il
collegamento all'indirizzo originale, in una scheda nuova), così chi vuole quella ricetta
la legge sul sito e la scrive a mano; la rotta la rifiuta con un 409 se qualcuno ci prova
lo stesso. Le alternative scartate: (B) offrire comunque «Rimetti in coda», che però non può
riuscire; (C) non mostrarla affatto, e allora «Scartate (N)» non torna con il numero di
`/imports/status`; (D) un «Riscarica» che rilegge la pagina dal sito, che è una funzione
nuova (rete, sito che risponde 404) fuori da questa voce.

## 3. Comportamento esatto

### 3.1 La causa (`explain_skip`)

In quest'ordine:

1. `payload` senza righe (`payload.get("ingredients")` vuoto o assente) → `unreadable`,
   **non** si rimette;
2. `skipped_reason == EMPTY_REASON[:200]` → `all_ignored`, si rimette;
3. `skipped_reason` che comincia con `NON_FOOD_PREFIX` («riga non alimentare: ») →
   `non_food`, si rimette; il nome è quel che segue, senza le virgolette basse (se il
   taglio a 200 caratteri ha mangiato la chiusa, il resto; se non resta niente, nessun
   nome);
4. qualunque altro motivo con le righe → `other`, si rimette.

### 3.2 L'elenco

`GET /api/v1/imports/pages/skipped` → `{"total": N, "pages": [...]}`; ogni pagina:
`id`, `url`, `title` (il titolo del `payload`, o `null`), `cause`, `non_food_name`,
`requeueable`, `waiting_cooking_events` (quanti id aspettano in `cooking_event_ids`).

### 3.3 La rimessa

`POST /api/v1/imports/pages/{id}/requeue`:

- pagina che non c'è → 404 «pagina inesistente»;
- pagina che non è `skipped` → 409 «Questa pagina non è più scartata: l'elenco era
  vecchio.»;
- pagina illeggibile → 409 «La pagina non aveva una ricetta leggibile: rimetterla in coda
  non cambierebbe niente.»;
- altrimenti 200 con `outcome` (`imported` | `skipped` | `waiting`), `title`, `url`,
  `recipe_id` (solo `imported`), `cooking_relinked` (le cotture ora sulla ricetta),
  `cause` e `non_food_name` (solo `skipped`), `waiting_terms` (solo `waiting`: i nomi dei
  termini della pagina ancora in coda, nell'ordine delle righe, senza doppioni).

## 4. Parole a video

Si copiano esattamente. «…» è il valore.

- Titolo della sezione: **«Scartate (N)»**.
- Sotto, aperta: «Le pagine scaricate che non sono diventate ricette, ciascuna col suo
  perché. Rimessa in coda, una pagina entra nel ricettario se la causa è stata corretta;
  se no torna qui.»
- Il nome della riga: il titolo, o l'indirizzo.
- Il motivo:
  - `non_food` col nome: «Fra gli ingredienti c'è «…», che non è un alimento. Rendilo un
    alimento in Anagrafica, o annulla la decisione che lo ha scelto; poi rimettila in
    coda.»
  - `non_food` senza nome: «Uno degli ingredienti non è un alimento. Rendilo un alimento
    in Anagrafica, o annulla la decisione che lo ha scelto; poi rimettila in coda.»
  - `all_ignored`: «Tutti i suoi ingredienti sono ignorati, e una ricetta senza
    ingredienti non entra nel ricettario. Annulla la decisione su uno di loro; poi
    rimettila in coda.»
  - `unreadable`: «Sul sito la pagina non aveva una ricetta leggibile: rimetterla in coda
    non cambierebbe niente.»
  - `other`: «Non è entrata nel ricettario durante l'import.»
- Le cotture: «1 cottura registrata aspetta questa ricetta.» / «N cotture registrate
  aspettano questa ricetta.»
- I pulsanti: **«Rimetti in coda»** (nome accessibile «Rimetti in coda «…»»), **«Apri la
  pagina»** (collegamento, nome accessibile «Apri la pagina «…»»), «Mostra altre».
- Mentre carica: «Carico le pagine scartate…»; se non riesce: «Non sono riuscito a
  leggere le pagine scartate.» con «Riprova».
- L'avviso dopo la rimessa (`«…»` è il titolo, o l'indirizzo):
  - entrata: ««…» è entrata nel ricettario.», più « Ha ritrovato 1 cottura.» / « Ha
    ritrovato N cotture.» se ce ne sono; azione «Apri»;
  - in coda: ««…» è tornata in coda: aspetta la decisione su «A».» / «… aspetta le
    decisioni su «A» e «B».» / «… su «A», «B» e «C».» / con più di tre, «… su «A», «B»,
    «C» e altri N.» (con uno solo in più, «e un altro»); senza nomi, «… aspetta che i suoi
    ingredienti siano decisi.»;
  - di nuovo scartata: ««…» è ancora scartata: «X» non è un alimento.» / «… : un
    ingrediente non è un alimento.» / «… : tutti i suoi ingredienti sono ignorati.» /
    ««…» è ancora scartata.» (causa `other`).
- Il rifiuto della rimessa: il `detail` del 4xx così com'è; per ogni altro guasto «Non
  sono riuscito a rimetterla in coda. Niente è andato perso: riprova.»

## 5. Fuori scope

- Riscaricare una pagina illeggibile (alternativa D sopra).
- Un collegamento dalla riga al termine che blocca la pagina (`?termine=<id>`, per
  annullarlo senza cercarlo fra le «Decisioni recenti», che ne mostrano 50): resta
  un'idea; la riga dice la strada a parole.
- Rimettere in coda più pagine in un tocco, filtrare l'elenco per causa, cercarci dentro.
- Le pagine `adopted` e `imported`: non sono scartate, e restano come sono.
- Qualunque migrazione: `skipped_reason` e `payload` bastano.
- Toccare le scartate della produzione: lo fa Mattia dall'app, dopo il deploy.
