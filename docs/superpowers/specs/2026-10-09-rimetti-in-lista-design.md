# «Rimetti in lista» anche per quasi finito — design

_2026-10-09, fase giorno. Voce di `next-steps.md`: «"Rimetti in lista" nel foglio della
cottura è pre-spuntata solo per "finito", in dispensa la domanda arriva anche nel giallo…»
[Parte X]. Piano: `docs/superpowers/plans/2026-10-09-rimetti-in-lista.md`._

## 1. Contesto

La stessa domanda — «questa confezione va ricomprata?» — oggi ha tre risposte diverse a
seconda di dove la si fa.

- **In Dispensa** (`frontend/src/features/pantry/PantryRow.tsx`) il pulsante «In lista» (o
  la scritta «Già in lista», se l'ingrediente ha già una voce aperta in lista) compare
  **solo sulle righe `finished`**, e chiama `POST /api/v1/pantry/{id}/restock`. Il
  2026-09-17 (S2) la domanda era stata estesa al giallo; il ridisegno di T3 (Consegna 1,
  2026-09-28) l'ha rifatta come pulsante e l'ha lasciata sul solo rosso.
- **Nel foglio della cottura** (`frontend/src/features/cooking/CookSheet.tsx`, funzione
  `choose`) la casella «Rimetti in lista della spesa» appare solo se lo stato **scelto** è
  `low` o `finished`, pre-spuntata solo per `finished`.
- **Dalla Consegna 5** le tacche del foglio partono dallo stato della confezione, e toccare
  lo stato di partenza vuol dire «invariato»: le scelte invariate non si mandano, e `cook`
  (`backend/app/services/cooking.py`) lavora per transizioni. Così una confezione che era
  già gialla prima di cucinare **non si può più rimettere in lista dal foglio**: non c'è
  una transizione da mandare, e la casella non compare.

La nota in `docs/prossimi-passi.md` (Parte X, «Nel foglio della cottura la casella
«Rimetti in lista» è pre-spuntata solo per «finito»…») chiedeva di decidere una volta.

## 2. Decisioni prese da Mattia il 2026-10-09

1. **«Anche quasi finito, ovunque».** La Dispensa offre «In lista» / «Già in lista» anche
   sulle righe `low`, non più solo sulle `finished`. Nel foglio della cottura la casella
   resta per `low` (vuota) e per `finished` (spuntata).
2. **Nel foglio, una confezione che dopo la cottura è `low` o `finished` ha la casella
   anche se lo stato non è cambiato** (era già gialla prima): vuota; spuntata, la rimette
   in lista **senza toccarne lo stato**. Il motivo del rientro (`ShoppingReason`) di una
   voce gialla è quello del giallo (`low_while_cooking`). La forma tecnica la sceglie
   Claude (§4).
3. **Le scelte estetiche** (dove sta il pulsante nella riga gialla, tono, parole) le prende
   Claude su delega, coi vincoli di sempre: bersagli da 44 px, solo token, nessuno
   scorrimento laterale a 375 px — tenendo conto che S12 aggiunge alla riga la figura e
   S15 i reparti che si chiudono.

## 3. Comportamento esatto

### 3.1 Dispensa

| Stato della riga | Sotto la scadenza, una riga sua |
|---|---|
| `available` | niente (com'è oggi) |
| `low` | «Quasi finito» a sinistra, in `text-low`; a destra «In lista», o «Già in lista» |
| `finished` | «Finito» a sinistra, in `text-finished`; a destra «In lista», o «Già in lista» (com'è oggi) |

- «Già in lista» vale come oggi: l'ingrediente ha una voce `pending` o `checked` in lista
  (`listedIngredients` in `PantryScreen`).
- Il tocco su «In lista» è la rotta di oggi, `POST /api/v1/pantry/{id}/restock`, che **non
  cambia lo stato** della voce e scrive in lista con il motivo `manual`, come per una finita.
  Gli avvisi restano quelli di oggi: «Rimesso in lista: <ingrediente>» e «Era già in
  lista.»; un guasto lo dice la riga («Non sono riuscito a salvare la modifica. Riprova.»)
  e «In lista» resta per riprovare.
- La riga del rientro è la stessa per giallo e rosso: una parola dello stato e il
  pulsante. Così la riga gialla si legge come la rossa, e il pulsante sta sempre nello
  stesso posto. Il backend non cambia per la Dispensa (la rotta accetta già ogni stato):
  cambia solo dove la riga offre il pulsante.

### 3.2 Foglio della cottura

Lo stato **dopo la cottura** di una confezione è quello scelto con le tacche, o quello di
partenza se non si è toccato niente. La casella «Rimetti in lista della spesa» c'è quando
quello stato è `low` o `finished`:

| Partenza | Scelta | Dopo | Casella | Si manda |
|---|---|---|---|---|
| `available` | niente | `available` | no | niente |
| `available` | Quasi finito | `low` | sì, vuota | `{to_status: "low", restock: <casella>}` |
| `available` / `low` | Finito | `finished` | sì, spuntata | `{to_status: "finished", restock: <casella>}` |
| `low` | niente | `low` | **sì, vuota** (nuovo) | niente se vuota; `{to_status: "low", restock: true}` se spuntata |
| `low` | Disponibile | `available` | no | `{to_status: "available", restock: false}` |
| `low` | Finito, poi di nuovo Quasi finito | `low` | sì, vuota (tornare allo stato di partenza annulla la scelta, compresa la spunta) | niente |

- Una confezione invariata e con la casella spuntata si manda come **transizione allo
  stesso stato** (`to_status` uguale allo stato attuale, `restock: true`).
- Una casella spuntata vale solo se la casella è a video: se a foglio aperto la confezione
  cambia da un'altra parte e lo stato dopo la cottura non è più giallo né rosso, la spunta
  non si manda (niente rientri che nessuno vede).
- Le voci `finished` restano fuori dal foglio, com'è oggi.
- Il conto dell'avviso dopo «Ho cucinato» («Segnato. Una cosa è tornata in lista della
  spesa.») conta anche questi rientri: viene da `restocked`, che li conta già.

### 3.3 Backend: la transizione allo stesso stato

`cook` accetta già una transizione con `to_status` uguale allo stato attuale, ma la tratta
come un cambio: riscrive `status_changed_at`, azzera `fill_percent`, e la conta in
`updated`. Diventa:

- **se `to_status` è lo stato attuale, la voce non si tocca**: né `status`, né
  `fill_percent`, né `status_changed_at`. Si fa solo il rientro, se chiesto, con il motivo
  dello stato (`_RESTOCK_REASON`: `low` → `low_while_cooking`, `finished` →
  `finished_while_cooking`, il resto `manual`).
- l'istantanea della cottura (`cooking_events.snapshot`) registra la transizione com'è
  (`from` uguale a `to`, `restocked`): è la storia vera di quella sera.
- `updated` nella risposta conta **solo le confezioni il cui stato è cambiato**.

Nessuna rotta nuova, nessun campo nuovo nello schema, nessuna migrazione.

## 4. La forma tecnica (deciso da Claude su delega di Mattia)

Due strade per «rimetti in lista senza transizione»:

- **A. La transizione allo stesso stato** (scelta): il foglio manda
  `{pantry_item_id, to_status: <stato attuale>, restock: true}`.
- B. Un campo nuovo in `CookRequest`, per esempio `restocks: [pantry_item_id]`, accanto a
  `transitions`.

Si sceglie A perché:

1. il contratto della rotta resta quello di oggi, e `cook` già lo accetta: cambia solo che
   una transizione che non cambia niente **non tocca** la voce, che è la cosa vera da dire;
2. il modello del foglio è già «com'è la confezione dopo la cottura, e la rimetto in
   lista?»: una riga, una risposta. Con B la stessa domanda andrebbe in due posti a
   seconda che lo stato sia cambiato o no, e una voce potrebbe finire in tutti e due;
3. il motivo del rientro esce da solo dalla tabella `_RESTOCK_REASON` sullo stato
   (`low` → `low_while_cooking`), senza una seconda regola;
4. l'istantanea registra comunque la confezione, con `from` uguale a `to`: la fase 3 (il
   diario) ci trova «non è cambiata, ma l'ho rimessa in lista».

Il prezzo: il nome «transizione» per una cosa che non transita. Lo dice un commento in
`cook`.

## 5. Parole a video

- Dispensa, riga gialla: «Quasi finito» (la parola di `STATUS_LABELS.low`), «In lista»,
  «Già in lista». Riga rossa invariata: «Finito», «In lista», «Già in lista».
- Avvisi invariati: «Rimesso in lista: <ingrediente>», «Era già in lista.».
- Foglio della cottura: «Rimetti in lista della spesa», nome accessibile
  «Rimetti in lista <confezione>», invariati.
- In Lista, la nota di un rientro dal foglio di una confezione gialla resta quella del
  motivo `low_while_cooking`: «rientrata perché quasi finita cucinando». Per una confezione
  già gialla prima di cucinare è un'approssimazione accettata (era quasi finita, ed è
  rientrata cucinando).

## 6. Scelte estetiche e di codice (deciso da Claude su delega di Mattia)

- **La riga del rientro diventa un componente suo**, `RestockLine`
  (`frontend/src/features/pantry/RestockLine.tsx`), usato da `PantryRow` per giallo e
  rosso. È il taglio che la nota di Parte X su `PantryRow.tsx` («il file più affollato
  dell'app») indicava come primo; la scadenza resta il secondo candidato.
- **Quali stati offrono il rientro è una regola sola**, `offersRestock(status)` in
  `frontend/src/features/pantry/statusLabels.ts` (accanto alle parole e ai colori degli
  stati), usata dalla Dispensa e dal foglio della cottura: le due sezioni non possono più
  rispondere in modo diverso alla stessa domanda. Non è logica di dominio: dice dove l'app
  fa una domanda, non se una ricetta si può cucinare.
- **La riga gialla ha la stessa forma della rossa**: la parola dello stato in `text-sm
  font-medium` nel colore dello stato (`text-low`, già misurato su `card` in
  `theme.test.ts`), il pulsante a destra. Nessun token nuovo. Non si mette il pulsante
  sulla riga della scadenza: la scadenza ha la sua riga larga quanto la voce (S12 la fa
  rientrare sotto il nome), e un pulsante lì la stringerebbe proprio quando il campo data
  è aperto.

## 7. Fuori scope

- Il titolo chiuso di un reparto (S15) conta «N finito» ma non le quasi finite, che ora
  hanno anche loro «In lista». S15 resta com'è: deciso da Mattia il 2026-10-13 (il giallo
  non è urgente come il rosso, e i titoli chiusi resterebbero rumorosi).
- Un motivo nuovo per il rientro dalla Dispensa (oggi `manual`, per giallo e rosso).
- Estrarre da `PantryRow.tsx` la scadenza.
- La Lista, Sistema la spesa, il resto della Dispensa.
