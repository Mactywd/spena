# L'anagrafica: correggere quel che è stato registrato male — disegno

**2026-09-27.** Questa spec costruisce **S9** (`docs/prossimi-passi.md`). Le scelte
di forma sono state prese con Mattia nel brainstorming dello stesso giorno, e qui
non si riaprono. La gemella è `2026-09-27-modifica-ricette-design.md` (R10), che
applica lo stesso principio alle ricette e si costruisce dopo questa.

## 1. Cosa si costruisce

Un errore di registrazione oggi resta per sempre. Il parmigiano legato a «burro» si
è sistemato solo a mano sul database, e dall'app non si cambia né un prodotto né un
ingrediente. Dopo questa spec:

- **un prodotto** si rinomina, cambia marca, si sposta sotto un altro ingrediente
  portandosi dietro i suoi elementi di dispensa, perde o cambia il codice a barre,
  si elimina;
- **un ingrediente** si rinomina, cambia reparto (e quindi alimentare / non
  alimentare), cede un alias a un altro ingrediente, si unisce a un suo doppione.

Tre pezzi: un servizio solo per tutte le correzioni, le rotte che lo espongono, e
due pagine («Anagrafica» e le schede di ingrediente e prodotto) raggiunte
dall'hamburger e dalla riga della dispensa.

## 2. Da dove viene, e cosa è già deciso

S9 nasce dal parmigiano, ma il problema è generale: *mai un vicolo cieco* vale
anche per gli errori di chi usa l'app. Il giro di T3 ne ha trovato la stessa classe
in S20 (spaghetti sotto «pomodoro»), che ora è chiusa all'ingresso, ma quel che è
già entrato storto resta da correggere.

Deciso nel brainstorming del 2026-09-27:

- **Dove vive la correzione: B.** Dalla riga della dispensa *e* da una pagina
  «Anagrafica» per ciò che in dispensa non c'è.
- **Come ci si arriva: l'hamburger, adesso.** D3 aveva già deciso che l'hamburger è
  l'indice completo; T1 lo rinviava alla prima sezione secondaria vera. È questa.
- **La fusione sta nell'app, con l'anteprima e senza rifiuti.** Se tocca ricette già
  cucinate lo dice, e procede lo stesso: la storia delle cotture si ri-lega (§5.2).
- **Le operazioni** sono quelle elencate al §1. Nient'altro (§8).

La logica esiste già per la riga di comando, in `app/cli/fix_registry.py`: `merge`,
`recategorize`, `rename`, `move_alias`, con le guardie giuste. **Lo schermo chiama
quella, non una seconda copia** — è la prima lezione di `CLAUDE.md`: una guardia
testata su una copia non protegge l'originale.

## 3. Il servizio unico

Un modulo nuovo, `backend/app/services/registry.py`, con una funzione per
correzione:

| Funzione | Da dove viene | Cosa scrive |
|---|---|---|
| `rename_ingredient` | `rename` della CLI | nome e nome a video; il vecchio nome diventa alias |
| `recategorize_ingredient` | `recategorize` | reparto (e `kind`, derivato dal `@validates`) |
| `merge_ingredients` | `merge` | tutto quel che punta al perdente (§5) |
| `move_alias` | `move_alias` | un alias passa a un altro ingrediente |
| `delete_alias` | nuova | toglie un alias non dell'import |
| `update_product` | nuova | nome e marca |
| `move_product` | nuova | `products.ingredient_id` e quello di **tutti** i suoi `pantry_items`, attivi e archiviati |
| `set_barcode` | nuova | il codice, o nessun codice; con `take=True` lo toglie a chi l'ha |
| `delete_product` | nuova | cancella il prodotto; gli elementi di dispensa restano, sfusi (`SET NULL` c'è già) |

Ogni funzione:

- prende la sessione e argomenti tipizzati, **non** i dizionari dei passi della CLI;
- non fa commit (come `create_recipe`: chi chiama decide);
- solleva un'eccezione di dominio, `RegistryRefusal`, con un codice (`name_taken`,
  `kind_mismatch`, `non_food_in_recipes`, `barcode_taken`, `import_alias`, …), un
  messaggio in italiano da mostrare, e — dove serve — l'oggetto che fa da ostacolo
  (l'ingrediente omonimo, il prodotto che ha il codice, le ricette che lo usano).

**La CLI diventa un guscio.** Le operazioni di `fix_registry.py` traducono il passo
in argomenti, chiamano il servizio e trasformano `RegistryRefusal` in `PlanError`.
`decide` e `remap` restano dove sono: sono decisioni della coda, non anagrafica.
**I test della CLI che esistono devono passare senza essere toccati**: sono la prova
che lo spostamento non ha cambiato niente.

## 4. L'API

| Rotta | Corpo | Risposta |
|---|---|---|
| `GET /ingredients/{id}` | — | nome, reparto, `kind`, alias `[{id, alias, source}]`, prodotti `[{id, name, brand, barcode}]`, uso `{recipes, pantry, shopping}` |
| `PATCH /ingredients/{id}` | `name?`, `category?` | l'ingrediente; 409 `name_taken` con `existing`; 409 `non_food_in_recipes` con le ricette |
| `POST /ingredients/{id}/merge` | `into`, `dry_run` | i conteggi (§5.1); 409 `kind_mismatch` |
| `PATCH /ingredients/{id}/aliases/{alias_id}` | `ingredient_id` | l'alias spostato; 409 `import_alias` |
| `DELETE /ingredients/{id}/aliases/{alias_id}` | — | 204; 409 `import_alias` |
| `GET /products/{id}` | — | nome, marca, codice, ingrediente `{id, name}`, elementi in dispensa attivi |
| `PATCH /products/{id}` | `name?`, `brand?`, `ingredient_id?`, `barcode?` (anche `null`), `take_barcode?` | il prodotto; 409 `barcode_taken` con `existing` |
| `DELETE /products/{id}` | — | 204, con il numero di elementi di dispensa rimasti sfusi |

Il 409 ha sempre la forma già usata da `POST /ingredients` dopo S19: `detail` con il
messaggio, e l'oggetto d'ostacolo accanto, così lo schermo offre il passo dopo
invece di un errore.

**Gli alias dell'import non si toccano da qui.** Un alias con `source = "import"` è
la metà di una decisione in `import_terms`: spostarlo da solo lascerebbe la coda a
dire una cosa e l'anagrafica un'altra. Si corregge dalla coda, dove R11 ora mostra
anche le decisioni prese a mano. Il 409 `import_alias` lo dice e porta il termine.

**Un codice a barre scritto a mano** passa dalla stessa `has_valid_check_digit` di
S20: se non torna, l'avviso e «Usalo lo stesso», mai un rifiuto.

## 5. La fusione

È l'unica correzione che non si annulla, ed è quella che tocca più tabelle:
`import_terms`, `recipe_imports`, `recipes`, `recipe_ingredients`, `pantry_items`,
`shopping_list_items`, `products`, `ingredient_aliases`, `ingredients`. Due cose la
rendono sicura da offrire a un tocco.

### 5.1 L'anteprima è la fusione stessa

`dry_run=true` esegue **la stessa `merge_ingredients`** dentro un SAVEPOINT
(`session.begin_nested()`), raccoglie i conteggi e annulla il SAVEPOINT. Non c'è una
seconda funzione che stima: i numeri dell'anteprima sono quelli dell'operazione, per
costruzione. È la stessa lezione di `recipe_search.py` al contrario — una stima
scritta a parte sarebbe giusta finché i dati sono pochi.

I conteggi: ricette rifatte dall'import, righe di ricetta spostate, elementi di
dispensa, voci di lista, prodotti, alias, cotture ri-legate. Il nome del perdente
che diventa alias del vincitore.

La rimaterializzazione calcola gli embedding anche nell'anteprima. Sono poche
ricette per fusione, e il costo è il prezzo della garanzia sopra.

### 5.2 Le cotture non si perdono

Oggi `undo_decision` rifiuta con `CookedRecipesAffected` se una ricetta da rifare è
già stata cucinata, perché cancellandola `cooking_events.recipe_id` diventa `NULL`
e la cottura perde la ricetta. Questa spec toglie la causa invece del sintomo:

1. prima di cancellare la ricetta di una pagina, `undo_decision` scrive gli id delle
   sue cotture nel `payload` della pagina, alla chiave `cooking_event_ids` —
   **riassegnando** il dizionario, come già fa per `cost`, perché SQLAlchemy non vede
   le mutazioni dentro un JSONB;
2. `materialize_ready`, quando rifà la ricetta di quella pagina, rimette
   `recipe_id` su quelle cotture e toglie la chiave.

Una pagina che resta in coda (il termine torna da decidere e nessuno lo rimappa)
tiene gli id nel `payload` finché non torna ricetta: la cottura è senza ricetta per
quel tempo, e la ritrova dopo.

Con questo, **`CookedRecipesAffected` non ha più ragione d'essere** e si toglie,
insieme a quel che lo aggirava: il `force` di `UndoIn` (`schemas/recipe_import.py`)
e di `undoTerm` (`features/recipe-import/api.ts`), e la conferma «ci sono ricette già
cucinate» della coda in `ImportQueueScreen.tsx`. Un annullamento nella coda smette di
chiedere conferma per le cotture, perché non ne scollega più nessuna. L'anteprima dice comunque
quante cotture vengono ri-legate, perché è un fatto che chi fonde vuole sapere.

### 5.3 Le guardie che restano

- **Stesso ingrediente**: rifiuto, non ha senso.
- **`kind` diverso**: rifiuto `kind_mismatch`, con il messaggio «Prima porta
  «detersivo» nello stesso reparto di «sapone», poi uniscili» e il link al cambio
  di reparto. Non è un vicolo cieco: dice il passo.

## 6. Le schermate

### 6.1 L'hamburger

Un ☰ in alto a destra in `AppHeader.tsx` apre un pannello laterale: un `dialog`
accessibile, il fuoco intrappolato dentro, Esc e il tocco fuori lo chiudono, il
fuoco torna al ☰. Dentro, per ora:

- «Sistema la spesa» → `/sistema`
- «Ingredienti da abbinare» → `/ricette/importa`
- «Anagrafica» → `/anagrafica`

Pasti, Spese, Profilo e Connettori si aggiungeranno qui. T1 si chiude.

### 6.2 «Anagrafica» (`/anagrafica`)

Un campo di ricerca, che interroga le due ricerche che esistono già,
`GET /ingredients/search` e `GET /products/search`, e mostra due gruppi:
«Ingredienti» e «Prodotti». Ogni risultato apre la sua scheda. Senza testo, una riga
che spiega cosa si trova qui.

### 6.3 La scheda dell'ingrediente (`/anagrafica/ingrediente/:id`)

- **Cos'è**: nome, reparto, e dove è usato — «in 42 ricette · 1 in dispensa · in
  lista». Così il peso di una correzione si vede prima di farla.
- **Alias**, uno per riga. Quelli non dell'import hanno «Sposta» (scelta
  dell'ingrediente) e «Togli». Quelli dell'import dicono «Deciso nella coda» con il
  link.
- **Prodotti** sotto questo ingrediente, ciascuno col link alla sua scheda.
- **Azioni**:
  - «Rinomina»: il campo in loco; un nome già preso risponde «C'è già «pomodoro».
    Uniscili?» e porta alla fusione con quel vincitore già scelto.
  - «Cambia reparto»: la scelta del reparto; il rifiuto per le ricette le elenca.
  - «Unisci a un altro…»: la scelta del vincitore, poi l'anteprima: «Si spostano 3
    ricette, 1 elemento di dispensa, 2 alias. «pomodori» diventa un alias di
    «pomodoro». Non si annulla.» e il pulsante «Unisci». Dopo, si arriva alla scheda
    del vincitore con l'esito in vista.

### 6.4 La scheda del prodotto (`/anagrafica/prodotto/:id`)

- Nome, marca e codice modificabili in loco, con «Salva» per campo.
- L'ingrediente, come link alla sua scheda, e «È sotto l'ingrediente sbagliato?
  Spostalo» → scelta → «Spostato sotto «parmigiano», con 1 elemento di dispensa».
- «Togli il codice».
- Un codice già di un altro prodotto: «Il codice è di «Grana Padano 200 g».
  Spostalo qui?».
- «Elimina il prodotto», con conferma: «Gli elementi in dispensa restano, come
  «burro» sfuso».

La scelta dell'ingrediente, in entrambe le schede, è la `IngredientPicker` che
esiste, senza filtro `kind`: in anagrafica si corregge anche il non alimentare.

### 6.5 Dalla dispensa

In `PantryRow.tsx` il nome diventa un link: alla scheda del prodotto se l'elemento
ne ha uno, a quella dell'ingrediente se è sfuso. **Nessuna terza schermata**: la
scheda dell'elemento è la scheda del prodotto, e l'ingrediente sta lì come link. Il
caso del parmigiano sono due tocchi e una scelta.

Il tocco è sul nome, non sulla riga: il cursore della dispensa resta dove è, e S13
resta chiusa. Il link ha un bersaglio di almeno 44 px.

Il tasto indietro di `Screen` vuole una destinazione dichiarata (T1). Le schede si
raggiungono da due posti, quindi chi le apre lo dice nell'indirizzo: `?da=dispensa`
torna a `/dispensa`, senza parametro si torna a `/anagrafica`.

## 7. Mai un vicolo cieco

| Rifiuto | Cosa offre |
|---|---|
| nome già preso | «Uniscili», con il vincitore già scelto |
| non alimentare con ricette | le ricette, ciascuna col suo link |
| `kind` diverso nella fusione | il cambio di reparto |
| alias dell'import | il termine nella coda |
| codice già usato | «Sposta il codice qui» |
| codice che non torna | l'avviso, e «Usalo lo stesso» |
| salvataggio fallito | il campo com'era scritto, e l'errore accanto |

## 8. Cosa non fa

- **Annullare una fusione.** L'anteprima lo dice prima.
- **Eliminare un ingrediente.** Un ingrediente inutile non fa danno, e un doppione
  si unisce. Se servirà, `delete_ingredient_if_unused` c'è già.
- **Modificare i nutrienti** di un prodotto: vengono da Open Food Facts e S4 ha la
  sua strada.
- **Correggere le decisioni della coda** da qui: stanno nella coda (R11).
- **Uno storico delle correzioni.** Nessun registro di chi ha cambiato cosa: l'app
  ha un utente solo.

## 9. Le prove, e in che ordine

Si costruisce in due consegne, ognuna distribuita da sola.

**Prima: il backend.**
1. Test del servizio, uno per funzione e uno per rifiuto, su Postgres vero.
2. Lo spostamento della CLI sul servizio, con **i test di `test_fix_registry_cli.py`
   invariati e verdi**.
3. Le cotture ri-legate: una ricetta importata cucinata, una fusione che la rifà, la
   cottura che punta alla ricetta nuova. E la pagina lasciata in coda che ritrova la
   ricetta quando torna.
4. L'anteprima: dopo un `dry_run`, il database è identico a prima (conteggi di tutte
   le tabelle toccate), e i conteggi dell'anteprima sono uguali a quelli della
   fusione vera fatta subito dopo.
5. Le rotte, con i 409 e i loro oggetti d'ostacolo.

**Poi: le schermate.**
6. Vitest per ogni schermata e ogni rifiuto del §7.
7. In `e2e/`, il caso del parmigiano per intero: un prodotto sotto «burro» in
   dispensa → tocco sul nome → «Spostalo» → «parmigiano» → la dispensa lo mostra
   sotto «parmigiano». E il controllo di `scrollWidth` a 375 px sulle tre pagine
   nuove e sul pannello dell'hamburger.

**Prima di distribuire la fusione**, una prova su una copia dei dati di produzione,
sullo stack `spena-e2e` come per il giro di T3: una fusione vera su dati veri (8.136
ricette), anteprima e poi esecuzione, con i conteggi confrontati. Poi `down -v` e il
dump cancellato. Il repo è pubblico: niente di quella prova entra in git.

## 10. Cosa può andare storto

- **Lo spostamento tocca codice che ha già corretto la produzione.** La difesa è il
  punto 2 del §9: i test della CLI non si modificano per farli passare.
- **Il `payload` mutato invece che riassegnato** perde gli id delle cotture in
  silenzio. Il test del punto 3 lo vede solo se rilegge la pagina da una sessione
  nuova: va scritto così.
- **Un SAVEPOINT che non annulla tutto.** Se qualcosa nella fusione facesse commit
  o toccasse fuori dalla sessione, l'anteprima scriverebbe davvero. Il test del
  punto 4 confronta il database prima e dopo, non il valore di ritorno.

## 11. Gli emendamenti, da fare insieme

- `docs/prossimi-passi.md`: S9 passa a **[FATTO]** con il rimando a questa spec, e il
  TBD sulla forma si chiude; T1 dice che l'hamburger c'è.
- `CLAUDE.md`, nella sezione sull'import: «a wrong decision is corrected from the
  ingredient registry» ora ha un posto nell'app; e l'annullamento non rifiuta più le
  ricette cucinate, perché le cotture si ri-legano.
- La docstring di `services/recipe_import/undo.py` che spiega `CookedRecipesAffected`.
