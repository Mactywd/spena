# Modificare ed eliminare una ricetta salvata — disegno

**2026-09-27.** Questa spec costruisce **R10** (`docs/prossimi-passi.md`). Le scelte
di forma sono state prese con Mattia nel brainstorming dello stesso giorno, insieme
a quelle di S9. La gemella è `2026-09-27-anagrafica-design.md`, che si costruisce
**prima**: questa ne usa il ri-legamento delle cotture (§5.2 di quella) e la
fusione che corregge le righe in loco.

## 1. Cosa si costruisce

Una ricetta salvata oggi resta com'è per sempre: un refuso nel titolo, un
ingrediente dimenticato, una ricetta di prova. Dopo questa spec:

- **ogni ricetta si modifica**, anche quelle importate, con lo stesso modulo di
  «Scrivi una ricetta»;
- **ogni ricetta si elimina**, con la lapide e «Annulla» come in dispensa;
- **l'import non riscrive mai quel che hai toccato.**

## 2. Da dove viene, e cosa è già deciso

R10 viene dal giro di T3. Le due cose che la rendevano una decisione e non solo
codice sono queste:
- in produzione le ricette importate sono 8.136, quelle scritte qui qualche decina;
- l'import **rifà** le sue ricette: annullare una decisione della coda, rimapparla o
  fondere due ingredienti cancella le ricette delle pagine toccate e le ricostruisce
  dal `payload`. Di una modifica a mano oggi sopravviverebbe solo il costo, che
  `undo_decision` copia apposta nel `payload` (R9).

Deciso nel brainstorming del 2026-09-27:

- **Modificare rende la ricetta tua (A).** Il primo salvataggio di una modifica
  stacca la ricetta dall'import: la sua pagina passa allo stato `adopted`, e
  l'import non la rifà più. Niente copia, niente doppione. «Apri l'originale»
  resta.
- **Eliminare archivia, con la lapide (A).** Nessuna pagina «Ricette eliminate».

## 3. Il dato

Una migrazione, la `0011`:

- `recipes.archived_at`, `TIMESTAMPTZ` annullabile. Come `pantry_items.archived_at`:
  presente vuol dire eliminata.
- il `CHECK` `ck_recipe_import_state` accetta anche `'adopted'`, e `ImportState`
  guadagna `ADOPTED`.

Nient'altro cambia nello schema. `recipes.source` resta quel che era: una ricetta
importata e poi modificata resta `dataset`, con il suo `source_ref`. «Tua» non è la
provenienza, è lo stato della pagina.

## 4. La regola della presa in carico

Una pagina di import passa da `imported` ad `adopted` **nella stessa transazione**
di:
- il primo salvataggio di una modifica della sua ricetta;
- l'eliminazione della sua ricetta.

Non torna mai indietro, nemmeno ripristinando la ricetta.

Cosa vuol dire, punto per punto, nel codice che esiste:

- **`undo_decision`** seleziona già solo le pagine `imported`
  (`services/recipe_import/undo.py`): una pagina `adopted` non si cancella e non
  torna in coda. **Nel risultato** dell'annullamento si aggiunge quante pagine
  `adopted` contengono il termine, e la coda lo dice: «1 ricetta tua non è stata
  toccata». Se il termine aveva creato un ingrediente e una ricetta tua lo usa ancora,
  `delete_ingredient_if_unused` lo lascia, e la coda dice anche questo.
- **`materialize_ready`** lavora solo le pagine `pending`: non cambia.
- **La fusione** (`merge_ingredients`, spec gemella §5) sposta in loco le righe delle
  ricette che non si rifanno. Oggi sono quelle scritte a mano o con l'AI; da adesso
  anche quelle `adopted`, **senza codice nuovo**, perché il ciclo guarda le righe
  rimaste dopo le ricostruzioni.
- **Una risincronizzazione** (`_new_urls`) salta gli URL già noti: una pagina
  `adopted` resta com'è.

## 5. L'API

**`PUT /recipes/{id}`** — la ricetta intera, con gli stessi campi di `RecipeCreate`
tranne `source` e `source_ref`, che non si cambiano: titolo, descrizione,
categoria, porzioni, procedimento, costo, righe.

- **Le righe passano dalla stessa strada di `create_recipe`**: stessa risoluzione dei
  nomi con `match_name`, stesso imbuto `NonFoodInRecipe`, stessa lettura delle
  quantità con `parse_quantity`. La scrittura di `recipe_ingredients` si estrae da
  `create_recipe` in una funzione che usano tutte e due. Resta *l'unico punto che
  scrive le righe*, come dice il suo commento.
- Sostituisce le righe: quelle che non ci sono più si cancellano, le altre si
  riscrivono.
- **Se cambiano titolo o descrizione**, l'embedding si ricalcola. Se il modello
  manca, va a `NULL`, e `reindex` lo ritrova (riempie solo i `NULL`).
- Se la ricetta è importata e la pagina è `imported`, la pagina passa ad `adopted`.
- Una ricetta archiviata non si modifica: 409, con «Ripristinala prima».
- Errori come nella creazione: ingrediente sparito 404, riga doppia 409, non
  alimentare 422.

**`PATCH /recipes/{id}`** accetta, accanto a `cost`, **`archived: bool`**, come la
dispensa. `true` scrive `archived_at` e prende in carico la pagina; `false` lo
toglie. Non c'è una `DELETE`.

**`GET /recipes/{id}`** risponde anche per una ricetta archiviata, con `archived_at`,
così un collegamento vecchio non finisce in un 404.

**Tutto quel che elenca ricette esclude le archiviate.** È il punto dove è facile
dimenticarne una, e `CLAUDE.md` ricorda il limite di `recipe_search.py` scritto
quando i dati erano pochi. L'elenco da coprire, ognuno con il suo test:
- la ricerca testuale;
- la ricerca semantica;
- lo sfoglio (`_browse`) con tutti i suoi filtri: cucinabili, per ingrediente,
  mancanti al più *n* (R7), costo;
- `GET /recipes/categories`;
- `reindex`.

## 6. Le schermate

### 6.1 Nel dettaglio

In fondo a `RecipeDetailScreen.tsx`, sotto «Cucina», due azioni secondarie:
«Modifica» ed «Elimina».

- **«Elimina»** archivia subito e torna a `/ricette`, con la lapide in cima: «Carbonara
  eliminata · Annulla», per 6 secondi, con lo stesso meccanismo di `PantryScreen`.
  Il segnale passa con lo stato della navigazione. «Annulla» manda
  `archived: false`; se fallisce, la lapide resta con l'errore.
- **Una ricetta archiviata** aperta da un collegamento mostra «Questa ricetta è stata
  eliminata» e «Ripristina», e nient'altro: niente «Cucina», niente «Modifica».

### 6.2 Il modulo condiviso

Il modulo di «Scrivi una ricetta» (`features/ai-draft/AiDraftScreen.tsx`) oggi parte
sempre vuoto. Si estrae in **`RecipeForm`**, che accetta valori iniziali e una
funzione di salvataggio. Due usi:

- **`/ricette/nuova-ai`**: il campo della richiesta e «Proponi» restano sopra, e la
  bozza riempie `RecipeForm`;
- **`/ricette/:id/modifica`**: `RecipeForm` riempito dalla ricetta. Il salvataggio
  chiama `PUT`, e al termine si torna al dettaglio con «Salvata» in vista.

Una ricetta importata, in modifica, ha una riga sopra il modulo: «È una ricetta
importata: salvando diventa tua, e l'import non la riscriverà più.»

L'estrazione chiude anche tre note del giro di T3 sul modulo, perché sono lo stesso
lavoro:
- **Descrizione e categoria.** Oggi mancano, e una ricetta scritta non esce mai
  filtrando per categoria. La categoria si sceglie fra quelle di
  `GET /recipes/categories`, o nessuna: senza testo libero, per non creare «Primi» e
  «primi».
- **Il ruolo si cambia su ogni riga**, anche su quelle proposte dall'AI. È il ruolo
  che decide se la ricetta è cucinabile.
- **Una riga si toglie con una ✕**, e non togliendo la spunta. Il nome si scrive una
  volta sola.

La scelta dell'ingrediente resta quella con `kind=food`: l'imbuto del backend è
l'ultima difesa, non l'unica.

## 7. Cosa non fa

- **Una pagina «Ricette eliminate».** Dopo l'«Annulla» la ricetta è sparita per chi
  usa l'app. Resta nel database: si ripristina da un collegamento vecchio (§6.1), o
  a mano in un'emergenza.
- **Tornare alla versione importata** di una ricetta modificata. «Apri l'originale»
  mostra la fonte.
- **Modificare foto e tempi.** Restano quelli dell'import, o vuoti.
- **«Modifica con AI»** (R8), che viene dopo e userà `RecipeForm`.
- **Il nuovo aspetto del modulo.** Lo decide la spec di T3; qui cambia cosa fa, non
  come appare.

## 8. Le prove, e in che ordine

Si costruisce dopo la spec gemella, e si distribuisce da sola.

1. Migrazione: l'`upgrade` e il `downgrade`, con il `CHECK` che rifiuta uno stato
   inventato.
2. `PUT` su Postgres vero: una ricetta scritta a mano modificata; una importata
   modificata, con la pagina che diventa `adopted`; il non alimentare rifiutato; una
   riga tolta; l'embedding a `NULL` senza modello.
3. La presa in carico contro l'import:
   - un annullamento del termine di una ricetta `adopted` la lascia intatta e la
     conta;
   - una fusione ne sposta la riga in loco;
   - `materialize_ready` non la tocca.
4. L'archivio: la ricetta sparisce da ogni voce dell'elenco del §5, una per test, e
   torna col ripristino. Le cotture restano legate.
5. Vitest: `RecipeForm` in creazione e in modifica, e la schermata di «Scrivi una
   ricetta» che si comporta come prima; la lapide; il dettaglio archiviato.
6. In `e2e/`: si modifica una ricetta togliendo l'unico ingrediente che manca, e
   diventa cucinabile; si elimina, si annulla, torna. E il controllo di `scrollWidth`
   a 375 px sul modulo di modifica.

## 9. Cosa può andare storto

- **L'estrazione di `RecipeForm` rompe «Scrivi una ricetta».** I suoi test esistenti
  devono restare verdi senza essere modificati, salvo i selettori che cambiano per la
  ✕ al posto della spunta.
- **Un elenco dimenticato** mostra una ricetta eliminata. Il punto 4 del §8 ha un test
  per voce proprio per questo.
- **Il controllo dei tipi.** `RecipeSummary` e `RecipeDetail` guadagnano
  `archived_at`: i letterali dei test si rompono, e lo vede solo `npm run typecheck`,
  non `tsc --noEmit` (sesta lezione di `CLAUDE.md`).

## 10. Gli emendamenti, da fare insieme

- `docs/prossimi-passi.md`: R10 passa a **[FATTO]** con il rimando a questa spec.
- `CLAUDE.md`, sezione sull'import: una ricetta importata e poi modificata o
  eliminata è `adopted`, e l'import non la rifà.
- La docstring di `services/recipe_import/undo.py`, che oggi dice che la cosa va
  ripensata «se le ricette importate diventano modificabili»: adesso è ripensata, e va
  scritto come.
