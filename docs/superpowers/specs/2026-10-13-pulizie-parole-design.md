# Pulizie: le parole a video — design

_2026-10-13, fase giorno. Raccoglie sei voci `[idea]` di `next-steps.md` («### Idee») sulle
parole a video, più una spostata dal piano 14. Mattia ha chiesto il 2026-10-13 di farne un
piano, con le scelte estetiche e tecniche delegate a Claude; le due scelte di comportamento
che restavano sono in fondo, decise da Mattia il 2026-10-13. Piano:
`docs/superpowers/plans/2026-10-13-pulizie-parole.md`, ramo `night/pulizie-parole` da `master`
(piano 15 della notte, indipendente dalla catena)._

## 1. Le voci, verificate su `master` (b9be6bf) e sui piani 1–12

| # | Voce di `next-steps.md` (inizio del testo) | Stato | Dove va |
|---|---|---|---|
| 1 | «La domanda di Open Food Facts in Sistema la spesa dice sempre «È un «…»?»…» | c'è (`OffSuggestionQuestion.tsx`); S3 sposta `describeSuggestion` in `wording.ts` ma non tocca la domanda | §2.1 |
| 2 | «Il titolo del foglio della cottura, per una confezione senza prodotto, è il nome dell'ingrediente in minuscolo…» | c'è (`CookSheet.tsx`, `item.product_name ?? item.ingredient_name`); il piano 7 e R2 toccano il file altrove | §2.2 |
| 3 | «Nella bozza AI, «non in anagrafica» è la formula sbagliata per una riga non alimentare» | c'è: `draft_recipe` stacca l'aggancio di un non alimentare e il modulo non sa perché (`matchNote` in `formModel.ts`) | §2.3 |
| 4 | ««Non è in anagrafica: lo creo io salvando.» può essere falso…» | c'è (`RecipeForm.tsx`) | §2.4 |
| 5 | «Nel modulo della ricetta, dopo «Aggiungi «pasta»» scegliere anche «Pasta» dai suggerimenti fa due righe…» | c'è (`attach` in `RecipeForm.tsx`); **spostata qui dal piano 14**: tocca `formModel.ts` e `RecipeForm.tsx` come le voci 3 e 4 | §2.5 |
| 6 | «Lista e Sistema la spesa mostrano il testo della voce com'è stato scritto, anche in minuscolo…» | c'è; deciso da Mattia il 2026-10-13 (§4.1) | §2.6 |
| 7 | «Nel modulo, un nome nuovo che coincide con un non alimentare dell'anagrafica si scopre solo salvando…» | c'è; deciso da Mattia il 2026-10-13 (§4.2) | piano 20, non qui |

Nessuna voce è già risolta da un altro piano.

## 2. Comportamento esatto

### 2.1 La domanda di Open Food Facts

«È un «zucchina»?» diventa **«È «zucchina»?»**: senza articolo, così vale per ogni genere e
numero, e resta la domanda a cui rispondono «Sì» e «No, è un'altra cosa». Deciso da Claude su
delega (era uno dei due esempi della voce).

### 2.2 Il titolo della confezione nel foglio della cottura

Una confezione senza prodotto si intitola col nome dell'ingrediente **con la maiuscola**
(`capitalizeFirst`), come le righe della Dispensa e del dettaglio (spec T3 §4.7, «la maiuscola
solo a video»). Il nome di un prodotto resta com'è scritto. I nomi accessibili (le tacche, la
casella «Rimetti in lista …») restano in minuscolo: lo mettono in mezzo a una frase.

### 2.3 Una riga della bozza AI che è un non alimentare

Il backend dice perché una riga non è agganciata: `DraftIngredient` e `DraftIngredientOut`
hanno un campo nuovo, **`non_food: bool`**, vero quando `match_name` trova **con certezza** (nome
o alias esatto) un ingrediente non alimentare — la stessa coincidenza che oggi fa staccare
l'aggancio. Una somiglianza incerta con un non alimentare resta `false`: lì la riga è davvero
«non in anagrafica». Il modulo mostra, al posto di «<nome> non in anagrafica, sarà escluso»:

> <nome> non è un alimento, sarà escluso

(le parole del 422 del salvataggio, «non è un alimento»). Il campo è facoltativo nel tipo
TypeScript (`non_food?: boolean`): le bozze finte dei test e di R8 non lo portano, e senza è
`false`. Lo porta anche la proposta di R8 (`/ai-variant`), che usa la stessa lavorazione delle
righe: al merge basta che `_draft_from` passi il campo.

### 2.4 «lo creo io salvando»

La frase sotto una riga non agganciata col suo reparto diventa:

> Salvando lo cerco in anagrafica; se non c'è, lo creo in questo reparto.

È quel che il server fa (`_resolve_lines`: `match_name` certo → collega quello che c'è, e il
reparto scelto non conta; altrimenti crea nel reparto scelto). La vecchia era falsa per un nome
che c'era già.

### 2.5 `attach` riconosce una riga senza aggancio con lo stesso nome

Scegliere un ingrediente dal selettore del modulo (`attach`, ora `attachIngredient` in
`formModel.ts`):

1. se una riga lo indica già → la si include (com'è oggi);
2. **se una riga senza aggancio ha lo stesso nome** — una riga nuova di «Aggiungi «…»», o una
   dell'AI «non in anagrafica» — confrontato come fa già `addNewLine` (minuscolo, senza spazi ai
   bordi, col `name` o il `display_name` dell'ingrediente) → **si aggancia quella riga**: prende
   l'id, perde il reparto proposto, tiene dose e ruolo, è inclusa. Al salvataggio il server
   l'avrebbe collegata a lui comunque, e due righe davano il 409;
3. altrimenti → una riga nuova (com'è oggi).

### 2.6 Il testo delle voci della Lista e di Sistema la spesa

Deciso da Mattia il 2026-10-13 (§4.1, opzione B): il testo di una voce prende la maiuscola
**solo a video**, dove apre la riga — `capitalizeFirst(item.raw_text)` nel testo della riga
della Lista (`ListRow.tsx`) e nel nome della riga di Sistema la spesa (`StockingRow.tsx`).
«cosa verde» si legge «Cosa verde», «Total 0%» resta «Total 0%». Il testo salvato non cambia,
e nemmeno ciò che si cerca o si manda al server; i nomi accessibili (la casella, la ✕, le
icone, la scadenza) restano com'è scritto, perché lo mettono in mezzo a una frase. È la
regola della Dispensa, delle ricette e del foglio della cottura (§2.2).

## 3. Scelte estetiche e tecniche (decise da Claude su delega di Mattia)

1. «È «…»?» fra le due forme della voce.
2. «<nome> non è un alimento, sarà escluso», con le parole del 422.
3. «Salvando lo cerco in anagrafica; se non c'è, lo creo in questo reparto.»
4. `non_food` solo sulla coincidenza certa; facoltativo nel tipo TypeScript.
5. `attachIngredient` come funzione pura in `formModel.ts`, accanto ad `addNewLine`, con lo
   stesso confronto dei nomi.

## 4. Le scelte di comportamento (decise da Mattia il 2026-10-13)

### 4.1 Il testo delle voci della Lista e di Sistema la spesa in minuscolo

Oggi la riga mostra `raw_text` com'è stato scritto («yogurt greco», «Total 0%»), di proposito:
è il testo di chi l'ha scritto. Il resto dell'app mette la maiuscola solo a video ai nomi che
aprono una riga.

- **A (com'era).** Nessun cambiamento: la voce resta aperta.
- **B. La maiuscola solo a video**: `capitalizeFirst(item.raw_text)` nella riga della Lista
  (`ListRow.tsx`) e nella riga di Sistema la spesa (`StockingRow.tsx`); il dato e i nomi
  accessibili restano come scritti. Una riga per file, più un test ciascuno.
- **C. La maiuscola nel dato**, all'inserimento: cambia ciò che si salva e ciò che si cerca; no.

**Deciso da Mattia il 2026-10-13: B** — coerente con Dispensa, ricette e foglio della cottura
(§2.2), e non tocca il testo salvato. Il comportamento è al §2.6; il piano lo fa nel Task 7.

### 4.2 Un nome nuovo che coincide con un non alimentare, nel modulo

Il selettore del modulo cerca solo cibo (`kind="food"`), quindi «sapone» non compare fra i
suggerimenti; «Aggiungi «sapone»» crea una riga nuova, e solo al salvataggio arriva il 422
««Sapone per le mani» non è un alimento: una ricetta non può averlo fra gli ingredienti.
Toglilo dalla riga, poi salva.» Non è un vicolo cieco (la frase dice cosa fare, la riga si
toglie), ma si scopre tardi.

- **A (com'è oggi, e resta così in queste pulizie).** Il 422 al salvataggio, con la frase.
- **B. Lo dice il passo del nome**: premendo «Aggiungi alla ricetta», il modulo chiede al server
  se quel nome è già in anagrafica (una rotta nuova di sola lettura sopra `match_name`, perché il
  confronto con alias e accenti è del server); se è un non alimentare, il passo resta aperto con
  «In anagrafica «Sapone per le mani» è un non alimentare: una ricetta non può averlo.» e la riga
  non si aggiunge.
- **C. Lo mostra il selettore**: i non alimentari compaiono fra i suggerimenti, spenti, col
  perché. Cambia il selettore in tutti i posti del mondo ricette.

**Deciso da Mattia il 2026-10-13: B, come voce a sé** — lo dice nel momento in cui si sceglie
il nome, senza rumore nel selettore. La fa il piano 20 (`modulo-nota-nome`), non queste
pulizie: qui non cambia niente, e la voce di `next-steps.md` la chiude il piano 20.

## 5. Fuori scope

- Le altre parole dell'app.
- L'avviso su un nome nuovo che coincide con un non alimentare (§4.2): piano 20.
- `addNewLine` che dà il reparto a una riga dell'AI riconosciuta come non alimentare (rientra
  nella §4.2, piano 20).
