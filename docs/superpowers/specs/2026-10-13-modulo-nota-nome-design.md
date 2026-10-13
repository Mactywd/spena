# Modulo della ricetta: la nota modificabile e l'avviso sul nome non alimentare

_Spec, 2026-10-13. Piano: `docs/superpowers/plans/2026-10-13-modulo-nota-nome.md` (piano 20
della notte, ramo `night/modulo-nota-nome` da `master`)._

## 1. Contesto

Due difetti del modulo della ricetta (`frontend/src/features/recipe-form/`), lo stesso che
usano «Scrivi una ricetta», la modifica (R10) e — dopo R8 — la variante.

**La nota della riga non si vede.** `recipe_ingredients.note` (varchar 300) esiste da v1, il
modulo la conserva (`FormLine.note` in `formModel.ts`: «il modulo non la mostra e non la
cambia, ma una modifica non deve perderla») e la rimanda com'era. Finché era vuota quasi
ovunque, andava bene. Il piano 12 (`pulizia-dosi`) sposta nella nota circa 10.000 frammenti
dell'import («da grattugiare», «a temperatura ambiente», «36 mesi») e la mostra nel dettaglio
sotto il nome: chi trova una nota sbagliata deve poterla correggere o togliere, e oggi non può.

**Un nome nuovo non alimentare si scopre al salvataggio.** Il passo del nome di R12 («Come si
chiama in generale?», `NewIngredientFields`) manda nome e reparto dentro la ricetta, e
l'ingrediente nasce salvando (`_resolve_lines` in `backend/app/api/recipes.py`). Ma
`_resolve_lines` prima chiede a `match_name`: se il nome coincide con certezza (nome canonico
o alias) con un ingrediente che c'è, si collega a quello — e se quello è un non alimentare
l'imbuto `write_recipe_ingredients` rifiuta tutta la ricetta col 422 ««Sapone per le mani» non
è un alimento…». Il selettore del modulo cerca solo `kind=food`, quindi prima non lo mostra.
Non è un vicolo cieco (la frase dice cosa fare), ma arriva tardi, dopo aver scritto tutto il
resto. È la voce `idea` di `next-steps.md` «Nel modulo, un nome nuovo che coincide con un non
alimentare dell'anagrafica si scopre solo salvando…» e la domanda 2 della spec delle pulizie delle
parole (`2026-10-13-pulizie-parole-design.md` §4.2).

## 2. Decisioni prese da Mattia (2026-10-13)

1. **La nota della riga diventa un campo modificabile del modulo, come la dose.** Lunghezza
   massima 300 (la colonna). Una nota vuota si salva come `null`. Forma, parole e posizione
   delegate a Claude.
2. **Un nome nuovo che coincide con un non alimentare dell'anagrafica lo dice già il passo del
   nome, appena scritto, invece del 422 al salvataggio** (opzione B di
   `2026-10-13-pulizie-parole-design.md` §4.2, come voce a sé). Serve una rotta di sola
   lettura sopra `match_name`, o il modo più semplice che dia la risposta esatta **senza
   logica di dominio nel frontend**. Mai un vicolo cieco: dire cosa fare — scegliere un altro
   nome, o correggere l'ingrediente in Anagrafica se è classificato male, con il collegamento.
   Forma e parole delegate a Claude.

## 3. Scelte di Claude su delega di Mattia

1. **Una funzione sola decide dove va un nome nuovo:** `ingredient_for_new_name(session,
   raw_name) -> Ingredient | None` in `backend/app/services/ingredient_match.py`, accanto a
   `match_name`: l'ingrediente a cui il nome si collega salvando (coincidenza **certa** di
   `match_name`), o `None` se salvando nasce. La chiamano `_resolve_lines` (al posto delle due
   righe che oggi rifanno la stessa condizione) e la rotta nuova. Così l'avviso dice
   esattamente quel che il salvataggio farà: due copie della condizione si scollerebbero
   (prima lezione di `CLAUDE.md`).
2. **La rotta:** `GET /api/v1/ingredients/match?name=<nome>` → `{"ingredient": IngredientOut |
   null}`. Sola lettura, dietro la sessione come le altre di `/ingredients`, `name` da 1 a 120
   caratteri (il limite di `RecipeIngredientIn.name`), dichiarata prima di `/{ingredient_id}`.
   Torna l'ingrediente intero e non un sì/no: il frontend legge il `kind` che il server
   manda (come fa già `IngredientPicker`), il `display_name` per la frase e l'`id` per il
   collegamento. Nessuna regola del dominio nel client: confronti, alias e certezza sono del
   server.
3. **Quando si chiede:** mentre si scrive nel campo «Come si chiama in generale?», con
   l'attesa di 180 ms del selettore (`useDebounced`), e alla sua apertura col nome che arriva
   da «Aggiungi «…»». La risposta vale solo per il nome che c'è adesso: appena il nome cambia,
   l'avviso sparisce finché il server non ha risposto sul nome nuovo.
4. **Cosa fa l'avviso:** il passo resta aperto, la frase sta sotto il suggerimento del campo
   e «Aggiungi alla ricetta» non si può usare, col perché sotto di sé (`unavailableReason` di
   `Button`, la regola dei pulsanti spenti). È il senso di «invece del 422»: la riga che il
   salvataggio rifiuterebbe non entra nel modulo. «Annulla» resta.
5. **Mai un vicolo cieco, anche quando il controllo non c'è.** Se la rotta non risponde (rete,
   5xx) o non ha ancora risposto, il passo **non** si ferma: «Aggiungi alla ricetta» resta
   usabile e l'ultima linea resta il 422 di oggi al salvataggio, con la sua frase.
6. **Il collegamento apre la scheda dell'ingrediente in un'altra scheda del browser**
   (`target="_blank"`), perché uscire dal modulo perderebbe la ricetta scritta fin lì (il
   modulo non ha bozze salvate). Tornati al modulo, la domanda si rifà da sola
   (`refetchOnWindowFocus` di react-query): se il reparto è stato corretto, l'avviso sparisce.
   Deciso da Mattia il 2026-10-13 (opzione A, vedi §7).
7. **La nota, nella riga del modulo:** sotto la dose e i ruoli, solo sulle righe che partono
   salvando (dove ci sono dose e ruolo). Una riga **con** nota mostra il campo «Nota»; una
   riga **senza** mostra un pulsante leggero «Aggiungi una nota», che apre il campo col
   fuoco. Dodici campi vuoti su dodici righe allungherebbero il modulo di un telefono intero,
   e una nota è l'eccezione. Il campo aperto e svuotato resta aperto fino al salvataggio
   (chiuderlo mentre lo si cancella porterebbe via il fuoco).
8. **Una nota vuota o di soli spazi si salva `null`, e gli spazi ai bordi si tolgono:** lo fa
   il backend (`RecipeIngredientIn`, che è l'autorità), e il modulo non manda la chiave
   `note` per una nota vuota — il corpo che «Scrivi una ricetta» manda da sempre non cambia.
   È così che una nota si toglie: si svuota il campo.
9. **Il limite di 300** sta nel campo (`maxLength`) e in `validationProblem`, come per la
   dose; l'autorità resta il 422 di `RecipeIngredientIn`.

## 4. Comportamento esatto

### 4.1 La nota

- `valuesFromRecipe` porta la nota com'è (già oggi). Una riga con `note` non `null` mostra:
  etichetta «Nota», campo con nome accessibile `Nota per <nome della riga>`, segnaposto
  «da grattugiare», «a temperatura ambiente» (con le virgolette basse), `maxLength` 300.
- Una riga con `note === null` mostra il pulsante «Aggiungi una nota» (`Button` `ghost` con
  l'icona `IconPlus`; nome accessibile `Aggiungi una nota: <nome della riga>`). Toccato, la
  riga prende `note: ""`, il campo compare col fuoco e il pulsante sparisce.
- Le righe nuove di R12 e le righe della bozza AI che partono salvando hanno lo stesso
  campo/pulsante; un aggancio incerto non confermato pure (come la dose).
- Salvando: la nota senza spazi ai bordi, se non è vuota; altrimenti la chiave non c'è e il
  server salva `null`. Una nota oltre 300 caratteri dice sotto «Salva» «La nota di «<nome>» è
  troppo lunga: massimo 300 caratteri.»
- Il backend: `note` di `RecipeIngredientIn` passa per un validatore che toglie gli spazi ai
  bordi e trasforma la stringa vuota in `null`, prima del limite di 300.

### 4.2 Il nome non alimentare

- Nel passo del nome, quando il server dice che il nome scritto si collega a un ingrediente
  con `kind = "non_food"`, sotto il suggerimento del campo compare (in un `role="status"`):
  - «In anagrafica questo nome è «<display_name>», un non alimentare: una ricetta non può
    averlo. Scrivi un altro nome; se invece è l'anagrafica a sbagliare, correggila.»
  - il collegamento «Correggi «<display_name>» in Anagrafica» (icona `IconExternalLink`,
    alto 44 px) verso `/anagrafica/ingrediente/<id>`, in un'altra scheda;
  - «Si apre a parte: la ricetta resta qui com'è.»
- «Aggiungi alla ricetta» è `aria-disabled`, con sotto «Cambia il nome: questo è un non
  alimentare.»; il tocco e l'Invio non aggiungono niente.
- Cambiato il nome in uno che il server non lega a un non alimentare (nessuno, o un cibo),
  l'avviso sparisce e il pulsante torna usabile.
- `GET /ingredients/match` per un nome che coincide per somiglianza ma non con certezza («deter-
  sivo» per «detersivo per i piatti») risponde `null`: il salvataggio creerebbe un ingrediente
  nuovo, e il passo non dice niente.

## 5. Parole a video (esatte)

| Dove | Testo |
|---|---|
| etichetta del campo | Nota |
| nome accessibile del campo | Nota per <nome> |
| segnaposto | «da grattugiare», «a temperatura ambiente» |
| pulsante | Aggiungi una nota (nome accessibile: Aggiungi una nota: <nome>) |
| motivo sotto «Salva» | La nota di «<nome>» è troppo lunga: massimo 300 caratteri. |
| avviso nel passo del nome | In anagrafica questo nome è «<display_name>», un non alimentare: una ricetta non può averlo. Scrivi un altro nome; se invece è l'anagrafica a sbagliare, correggila. |
| collegamento | Correggi «<display_name>» in Anagrafica |
| sotto il collegamento | Si apre a parte: la ricetta resta qui com'è. |
| motivo sotto «Aggiungi alla ricetta» | Cambia il nome: questo è un non alimentare. |

## 6. Fuori scope

- Mostrare la nota nel dettaglio della ricetta: lo fa il piano 12 (`pulizia-dosi`).
- Un nome nuovo che coincide con un **alimento** dell'anagrafica: salvando si collega a lui
  (com'è oggi); la frase sotto la riga la cambia il piano 15 («Salvando lo cerco in
  anagrafica; se non c'è, lo creo in questo reparto.»).
- I non alimentari fra i suggerimenti del selettore (opzione C della spec delle pulizie, non
  scelta).
- Le righe della bozza AI che sono non alimentari: le dice il piano 15 (`non_food`).
- Salvare una bozza del modulo per non perderla uscendo.
- Nessuna migrazione: `recipe_ingredients.note` c'è già. Nessuna dipendenza nuova.

## 7. Il collegamento in un'altra scheda (deciso da Mattia il 2026-10-13)

**Il collegamento all'Anagrafica si apre in un'altra scheda.** Le opzioni erano:

- **A (decisa da Mattia il 2026-10-13):** `target="_blank"`: il modulo e quel che c'è
  scritto restano; tornati, l'avviso si rilegge. Nell'app installata sul telefono la scheda
  si apre nel browser, e si torna all'app col selettore delle app.
- **B:** stessa scheda: più semplice da seguire sul telefono, ma la ricetta non salvata si
  perde.
- **C:** niente collegamento, solo la frase con «Anagrafica dal ☰».

Mattia ha scelto A il 2026-10-13. Il cambio da A a B resterebbe una riga (`target`) e una frase.
