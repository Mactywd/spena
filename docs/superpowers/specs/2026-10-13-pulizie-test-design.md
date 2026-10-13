# Pulizie: i test instabili e i piccoli difetti del backend — design

_2026-10-13, fase giorno. Raccoglie sette voci `[idea]` di `next-steps.md` («### Idee») sui
test e sul backend. Mattia ha chiesto il 2026-10-13 di farne un piano, con le scelte
estetiche e tecniche delegate a Claude. Piano:
`docs/superpowers/plans/2026-10-13-pulizie-test.md`, ramo `night/pulizie-test` da `master`
(piano 14 della notte, indipendente dalla catena)._

## 1. Le voci, verificate su `master` (b9be6bf) e sui piani 1–12

| # | Voce di `next-steps.md` (inizio del testo) | Stato | Dove va |
|---|---|---|---|
| 1 | «`ShoppingListScreen.test.tsx` è fallito in alcune corse della suite intera sotto carico…» | c'è | §2.1 |
| 2 | «Oltre a `ShoppingListScreen.test.tsx`, anche `IngredientScreen.test.tsx` è fallito una volta…» | c'è | §2.1 |
| 3 | «Una prova e2e di `style.spec.ts` («il campo data si vede…») calcola la data con `toISOString()`…» | c'è, e non in una prova sola: tre (`fraDueGiorni`, `fraTreGiorni`, `fraCinqueGiorni`) | §2.3 |
| 4 | «I test di schermata si costruiscono il client react-query con `retry: false`…» | c'è: 22 file di test costruiscono 34 `QueryClient` a mano; 17 file hanno almeno un `retry: false`, 5 usano il predicato vero ma con l'attesa vera fra i tentativi (fino a 8 s per prova), e un client solo, in `ImportQueueScreen.test.tsx`, ha `retryDelay: 0` | §2.2 |
| 5 | «La suite del backend stampa 8 `StarletteDeprecationWarning` per `HTTP_422_UNPROCESSABLE_ENTITY`…» | c'è: tre usi in `app/api/imports.py` e `app/api/recipes.py` | §2.4 |
| 6 | «L'annullamento riconta `occurrences` caricando tutte le pagine in attesa col loro JSONB intero…» | c'è (`undo_decision` in `services/recipe_import/undo.py`) | §2.5 |
| 7 | «Il 409 «Due righe puntano allo stesso ingrediente» non dice quale…» | c'è (`_writing_recipe` in `app/api/recipes.py`, dal vincolo d'unicità) | §2.6 |
| 8 | «Nella coda d'import nessun test di schermo prova i pulsanti di una voce mentre una decisione è in volo» | c'è | §2.7 |

**Spostata**: «Nel modulo della ricetta, dopo «Aggiungi «pasta»» scegliere anche «Pasta» dai
suggerimenti fa due righe…» va nel piano 15 (`pulizie-parole`): è un difetto del frontend in
`formModel.ts`/`RecipeForm.tsx`, che il piano 15 tocca comunque per la nota delle righe nuove;
qui avrebbe solo moltiplicato i conflitti fra due rami che partono entrambi da `master`. Il 409
che nomina l'ingrediente (voce 7) resta qui, ed è la rete di sicurezza di quella stessa
situazione.

Nessuna voce è già risolta da un altro piano. R2 (piano 8, da `master`) aggiunge **tre nuovi
usi** di `HTTP_422_UNPROCESSABLE_ENTITY` in `app/api/recipes.py`: al merge li fa fallire la
regola del §2.4 (vedi il piano, «Dipendenze»). S15 (piano 6) aggiunge in `style.spec.ts` una
quarta data con `toISOString()`: al merge la sistema l'aiuto del §2.3.

## 2. Comportamento esatto

### 2.1 Le attese troppo corte

Le due prove falliscono «sotto carico, ogni volta su un'asserzione diversa»: è la firma
dell'attesa di Testing Library (`findBy…`, `waitFor`), che per default rinuncia dopo 1 s.
Sotto il carico dell'e2e che gira accanto, una schermata con due o tre letture finte e un
`useDebounced` da 180 ms può metterci di più. **La cura è globale** (deciso da Claude): attesa
di Testing Library a 4 s (`configure({ asyncUtilTimeout: 4000 })` in `vitest.setup.ts`) e tempo
di una prova a 15 s (`testTimeout` in `vite.config.ts`). Un'attesa più lunga non nasconde
niente: una prova che passa la passa al primo disegno buono, e una che fallisce fallisce lo
stesso, solo più tardi. Il piano prima **misura** (le due prove sei volte in parallelo, tre
giri), poi cura, poi rimisura; un'asserzione che resta instabile è un `getBy…` sincrono dopo
un gesto asincrono, e diventa un `findBy…`.

### 2.2 Un client react-query solo, per l'app e per i test

La prima lezione di `CLAUDE.md`: un test che si costruisce il suo oggetto non prova quello che
gira. Il client dell'app nasce oggi dentro `App.tsx`; i test di schermata se ne fanno uno a
mano. **Decisione (Claude):**

- `frontend/src/lib/queryClient.ts` esporta `createAppQueryClient(onUnauthorized)`: il client di
  `App.tsx`, tale e quale (le due cache che riportano all'accesso su un 401, il predicato
  `defaultQueryRetryPredicate`). `App.tsx` lo usa.
- `frontend/src/test/queryClient.ts` esporta `createTestQueryClient(onUnauthorized?)`: lo stesso
  client, con una sola differenza dichiarata, `retryDelay: 0` — i tentativi sono quelli veri,
  senza l'attesa vera fra l'uno e l'altro (1 s, 2 s), che renderebbe ogni ramo d'errore lungo
  tre secondi.
- Ogni test di schermata lo usa al posto di `new QueryClient(...)`. Una prova strutturale
  (`frontend/src/test/noLocalQueryClient.test.ts`) tiene fuori da ogni `*.test.ts(x)` un
  `new QueryClient(`.
- Dove un test passava solo perché `retry: false` mostrava l'errore al primo tentativo, il test
  si corregge **verso la produzione**: il guasto si finge permanente (ogni lettura fallisce),
  non solo la prima. Un test che contava le chiamate dopo un guasto conta quelle che l'app fa
  davvero (tre). Nessun test torna a `retry: false`.

### 2.3 Le date dell'e2e nel giorno di Roma

Il backend giudica le scadenze nel giorno di `Europe/Rome` (`PANTRY_TZ`). Le prove di
`style.spec.ts` calcolano «fra N giorni» con `toISOString()`, cioè nel giorno di UTC: fra
mezzanotte e le 2 ora italiana mandano il giorno sbagliato. Un aiuto `giornoDiRoma(fraGiorni,
adesso?)` in `frontend/e2e/giornoDiRoma.ts` prende il giorno di Roma di adesso e ci somma i
giorni nel calendario (non 24 ore: un cambio d'ora non sposta il giorno). Le tre date di
`style.spec.ts` lo usano. Una prova di Playwright senza pagina fissa l'aiuto su tre istanti
(mezzanotte e mezza a Roma, il pomeriggio, la notte del cambio d'ora del 2026-10-25).

### 2.4 Le costanti di stato deprecate di Starlette

I tre usi di `status.HTTP_422_UNPROCESSABLE_ENTITY` diventano
`status.HTTP_422_UNPROCESSABLE_CONTENT` (stesso numero, 422). Perché non tornino: in
`pyproject.toml` `filterwarnings` fa di `StarletteDeprecationWarning` un errore, e una prova
del backend cerca in `app/` ogni nome deprecato che Starlette elenca (`status.__deprecated__`):
la prima vede gli usi che i test attraversano, la seconda anche quelli che non attraversano.

### 2.5 L'annullamento riconta `occurrences` con una query

`undo_decision` legge tutte le pagine in attesa, con il loro `payload` intero, per contare una
chiave sola; e la fusione dell'anagrafica lo fa una volta per termine. **Decisione (Claude):**
`count_pending_recipes_with_key(session, source, key)` in `app/repositories/imports.py`, una
`COUNT(*)` sulle pagine `pending` della fonte il cui `payload->'ingredients'` contiene un
elemento con quella `key` (`@>`). Conta le **ricette**, come `count_pending_keys`: una pagina
che nomina la chiave in due righe conta una volta. Una prova confronta i due conti su un
insieme di pagine scelto apposta (due righe con la stessa chiave, righe senza chiave, pagine di
un'altra fonte, pagine non in attesa, pagine senza ingredienti). `sync_terms` resta com'è: lì
servono tutte le chiavi, e una lettura sola le dà tutte.

### 2.6 Il 409 delle due righe nomina l'ingrediente

Oggi il 409 nasce dal vincolo d'unicità della tabella delle righe, che non sa dire quale.
**Decisione (Claude):** `_resolve_lines` (la strada di creazione e modifica) riconosce da sé due
righe che, risolte, puntano allo stesso ingrediente — anche due nomi diversi che `match_name`
porta allo stesso, o un nome nuovo uguale a una riga agganciata — e le rifiuta prima di
scrivere, con la frase:

> Due righe puntano allo stesso ingrediente, «<nome a video dell'ingrediente>»: togline una, poi salva.

Il rifiuto passa da `_writing_recipe`, che fa il `rollback` (un ingrediente creato da una riga
precedente non resta orfano). Il 409 del vincolo resta come ripiego, con la frase di oggi, per
una corsa fra due salvataggi. Il modulo mostra il `detail` di un 4xx così com'è: nessun
cambiamento nel frontend.

### 2.7 I pulsanti della coda con una decisione in volo

Solo test, in `ImportQueueScreen.test.tsx`: con una decisione in volo, ogni pulsante di ogni
scheda è `aria-disabled` e non `disabled`, quello premuto tiene il fuoco, e un secondo tocco (lo
stesso o un altro) non manda una seconda decisione; lo stesso per «Annulla» con un annullamento
in volo. Il campo del selettore non si guarda: lo cambia il piano 13.

## 3. Parole a video

Una sola frase cambia, quella del §2.6. Le altre voci non toccano lo schermo.

## 4. Scelte tecniche (decise da Claude su delega di Mattia)

1. Le attese globali (4 s, 15 s) invece di ritoccare prova per prova.
2. La fabbrica dei test sopra la fabbrica dell'app, con `retryDelay: 0` come sola differenza;
   la prova strutturale contro i client fatti a mano.
3. `giornoDiRoma` in un file suo sotto `e2e/`, provato da Playwright stesso (vitest esclude
   `e2e/`).
4. `filterwarnings` più una prova statica, per le costanti deprecate.
5. Il conto con `@>` sul JSONB, senza indice (l'annullamento è raro; la tabella è di qualche
   migliaio di pagine).
6. Il controllo delle righe doppie in `_resolve_lines`, non nell'imbuto
   `write_recipe_ingredients`, che l'import usa anche lui e che deve continuare a rifiutare
   con l'`IntegrityError` che la materializzazione si aspetta.

## 5. Fuori scope

- `attach` nel modulo della ricetta (spostata nel piano 15).
- Le altre prove e2e o di vitest instabili che la misura del §2.1 non trova.
- I test dei rami della notte che partono dalla catena o da altri piani: si costruiscono il
  client a mano come oggi, e al merge passano alla fabbrica (la prova strutturale li trova).
