# T3 Consegna 6b — Il modulo della ricetta (R12), la coda d'import, le parole: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** chiudere il ridisegno di T3 con la sua ultima consegna: nel modulo della ricetta «Proponi» secondario e «Salva» principale col motivo sotto, caselle da 44 px, e il selettore unico che aggiunge un ingrediente che non c'è (R12); un campo «Reparto» solo per tutta l'app (`CategorySelect`); la coda d'import senza il rosso e senza il nome della variabile quando l'AI non c'è, col suggerimento testuale della misura del resto e l'esito dell'annullamento nell'avviso unico; il guasto dell'AI di un colore solo; le parole tecniche fuori dallo schermo, «ad astice», e i nomi degli ingredienti con la maiuscola, solo a video.

**Architecture:** nessuna rotta nuova, nessuna migrazione, nessuna modifica al codice del backend: R12 si appoggia a `_resolve_lines` (`backend/app/api/recipes.py`), che crea già l'ingrediente nominato da una riga `{name, category}` alla creazione e alla modifica, nella transazione della ricetta; due test del backend fissano quel contratto. Nel frontend nascono quattro pezzi piccoli — `lib/text.ts` (`capitalizeFirst`, `withPrepositionA`), il tono `degraded` di `Alert`, la primitiva `Checkbox`, il campo `CategorySelect` — e le schermate li adottano: `RecipeForm` (con `formModel.addNewLine` per R12, e `NewIngredientFields` riusato per il passo «Come si chiama in generale?»), `AiDraftScreen`, `ImportQueueScreen`/`TermCard`/`DecidedTermRow`, `CategoryForm`, `NewIngredientFields`, e per le parole `StockingScreen`, `AddItemField`, `PantryRow` e il dettaglio della ricetta.

**Tech Stack:** React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5, react-router 7, Vitest + Testing Library (jsdom), Playwright; pytest su Postgres vero (solo due test, Task 4).

**Spec:** `docs/superpowers/specs/2026-09-28-ridisegno-design.md`, §2 (regola delle icone), §3.1 (un colore per significato: il rosso vuol dire «manca» o «non è andata»), §3.5 (le primitive: `Button`, `Notice`, `IngredientPicker` con «Aggiungi «…»») e **§4.7**; in `docs/prossimi-passi.md` **R12** e, nella voce T3, «Esito del giro» → «**In tutto il sito**», «**Scrivi una ricetta**», «**Ingredienti da abbinare**»; in Parte X la voce «**«Ingrediente» invece di «voce» in due schermate.**». Le decisioni della fase giorno del 2026-09-29 (seconda) sono riportate sotto, in «Decisioni prese».

## Global Constraints

- **Dove si lavora.** Worktree `/home/mactyws/coding/ais/spena/.worktrees/c6b-modulo-coda-parole` (`.worktrees/` è già in `.gitignore`), ramo `night/c6b-modulo-coda-parole`, creato da **`night/c5-dettaglio`** (il ramo del Piano 3, che parte da quello del Piano 2, che parte da quello del Piano 1). Nel piano `<worktree>` è quel percorso. Ogni comando parte da lì (o dalle sue `backend/` e `frontend/`), mai dalla radice del checkout principale. Il checkout principale non si tocca: se vi trovi modifiche non committate, sono dell'utente. **Nessun push, nessun merge, nessun deploy. Mai `git stash`.**
- **I file che anche i piani prima di questo toccano** (`AiDraftScreen.tsx`, `RecipeEditScreen.tsx`, `RecipeCard.tsx`, `IngredientPicker.tsx`, `NewIngredientFields.tsx`, `StockingScreen.tsx`, `CategoryForm.tsx`, il dettaglio della ricetta in `frontend/src/features/cooking/`): **leggili com'è sul ramo prima di cambiarli**. Il piano descrive ogni modifica contro un'ancora riconoscibile — una funzione o un elemento JSX per nome, o un testo esatto — e non contro numeri di riga. Dove il piano dà un file intero (`TermCard.tsx`, `DecidedTermRow.tsx`), è perché nessun piano precedente lo tocca: la Preparazione lo verifica.
- **`Button` dal Piano 1.** `frontend/src/components/ui/Button.tsx` sul ramo ha, oltre a `variant`, `shape`, `icon`, `label`, `disabled`, `busy`, `aria-describedby`: `unavailableReason?: string` («non si può ancora», col perché: `aria-disabled="true"`, click e submit ignorati, il fuoco resta, e sotto di sé un `<p>` col testo collegato con `aria-describedby`) e `accessibleName?: string` (diventa `aria-label` di un pulsante con testo visibile; il testo visibile sta all'inizio del nome). **La regola (di Mattia):** in volo → `busy`; «non ancora» → `unavailableReason`; `disabled` nativo solo dove nessuno dei due vale. In questo piano ogni `<button>` scritto a mano dei file che si ricostruiscono (`RecipeForm.tsx`, `AiDraftScreen.tsx` per «Proponi», `ImportQueueScreen.tsx`, `TermCard.tsx`, `DecidedTermRow.tsx`) passa a `Button` con quella regola. `CategoryForm.tsx` e `NewIngredientFields.tsx` cambiano solo nel campo del reparto: i loro pulsanti restano come il Piano 1 li ha lasciati.
- Tutto il colore passa dai token di `frontend/src/index.css`. Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto. Il testo su un fondo pieno usa il suo `on-*`. Ogni testo sta sopra 4,5:1, in chiaro e in scuro, e lo misura `frontend/e2e/style.spec.ts`. **Nessun token nuovo.**
- Le icone si importano solo da `frontend/src/components/ui/icons.ts` (quelle che servono ci sono già: `IconSparkles`).
- Ogni bersaglio nuovo è almeno 44×44 px. A 375 px nessuna schermata scorre di lato.
- **Un controllo che si spegne mentre ha il fuoco usa `aria-disabled`**, mai `disabled`: è quel che fanno `busy` e `unavailableReason` di `Button`.
- **Mai un vicolo cieco.** L'AI che non risponde lascia il modulo a mano e la coda a mano; un nome nuovo nel modulo che al salvataggio risulta un non alimentare torna come 422 con la frase del backend («… non è un alimento: una ricetta non può averlo fra gli ingredienti. Toglilo dalla riga, poi salva.»), che il modulo mostra com'è accanto a «Salva», con la riga lì da togliere con la sua ✕.
- **Una ricetta non nomina un non alimentare** (`CLAUDE.md`, decisione 2): `write_recipe_ingredients` lo rifiuta. Per questo ogni campo del reparto del mondo ricette — la riga da creare del modulo, il passo di R12, la scheda della coda d'import — offre solo i reparti del cibo (`CategorySelect foodOnly`), e il selettore del modulo cerca solo cibo (`kind="food"`, com'è oggi).
- **Il frontend non calcola logica di dominio.** Nessun nome si riscrive: la maiuscola è solo a video; il corpo mandato al backend resta quello di oggi (`name` in minuscolo per una riga da creare).
- Le parole a video sono in italiano e **si copiano esattamente come sono scritte qui**; gli identificatori in inglese; i commenti in italiano come nel resto del codice.
- **Il type check è `npm run typecheck`** (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0 (settima lezione di `CLAUDE.md`).
- Controlli del frontend, da `<worktree>/frontend`: `npx vitest run` (non esiste `npm test`), `npm run typecheck`, `npm run lint`, `npm run build`.
- **Backend su Postgres vero.** Il database dei test è il container `spena-db-1` (porta 5433), da usare solo come database dei test: se `docker ps --format '{{.Names}}'` non lo mostra, `docker start spena-db-1`. **Mai `docker compose up` dal worktree** (il nome del progetto Compose viene dalla cartella: nascerebbe un secondo Postgres che litiga sulla 5433), mai `-f docker-compose.prod.yml`. Nel worktree non c'è un `.venv`: si usa quello del checkout principale; `python -m` mette la cartella corrente in testa a `sys.path`, quindi si prova l'`app` del worktree. Il comando, sempre da `<worktree>/backend`:
  ```bash
  PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
  ```
  Se un test sembra ignorare una modifica, `python -c 'import app; print(app.__file__)'` da `<worktree>/backend` (con lo stesso `PATH`) deve stampare un percorso dentro il worktree. Nessuna chiamata di rete nella suite.
- **e2e** sullo stack `spena-e2e`, dalla radice di `<worktree>`. Serve un `.env`: **si copia da `.env.example`, che non ha segreti, solo per la prova, e si cancella alla fine. Mai leggere né copiare il `.env` del checkout principale.** Prima di alzarlo, `docker ps --format '{{.Names}}' | grep spena-e2e`: se c'è e non l'hai alzato tu (un altro piano della notte), non fare `down`, aspetta che sparisca.
  ```bash
  cp .env.example .env
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
  (cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
  docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
  rm .env
  ```
  Il `-p spena-e2e` e il `-f docker-compose.e2e.yml` vanno in ogni comando: un `down -v` sul progetto di default cancellerebbe la dispensa vera. Una prova fallita lascia dati nello stack: prima di rieseguire, `down -v`, poi `up`, seme e prova.
- Nessuna dipendenza nuova, nessuna migrazione, nessun cambio di configurazione globale.

### Preparazione (una volta, prima del Task 1)

- [ ] Il ramo di partenza c'è, e porta quel che questo piano consuma:
  ```bash
  cd /home/mactyws/coding/ais/spena
  git rev-parse --verify night/c5-dettaglio
  git log --oneline master..night/c5-dettaglio | tail -n 3
  git show night/c5-dettaglio:frontend/src/components/ui/Button.tsx | grep -c "unavailableReason\|accessibleName"
  ```
  Expected: un hash; i commit dei Piani 1–3; un numero **maggiore di zero**. Se `night/c5-dettaglio` non c'è, o `Button` non ha `unavailableReason` e `accessibleName`, **fermati**: la catena della notte si è interrotta prima di questo piano, e nessun task di questo piano parte. Il checkout principale non si tocca: la causa va nel report della notte (`docs/night-reports/<data>.md`), sull'ultimo ramo della catena che esiste, con la riga della Consegna 6b segnata `bloccato` in quel ramo, e la domanda per Mattia.
- [ ] Dal checkout principale, allinea `node_modules` al lockfile (non aggiunge dipendenze, installa quelle di `package-lock.json`; fino al 2026-09-29 era vecchio e 24 file di test non partivano):
  ```bash
  cd /home/mactyws/coding/ais/spena/frontend && npm install --no-audit --no-fund
  ```
- [ ] Crea il worktree dal ramo del Piano 3 e collega `node_modules` (e solo quello: **niente `.env`**):
  ```bash
  cd /home/mactyws/coding/ais/spena
  git worktree add .worktrees/c6b-modulo-coda-parole -b night/c6b-modulo-coda-parole night/c5-dettaglio
  ln -s /home/mactyws/coding/ais/spena/frontend/node_modules .worktrees/c6b-modulo-coda-parole/frontend/node_modules
  ```
- [ ] Cosa hanno già cambiato i piani prima di questo nei file di questo piano:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/c6b-modulo-coda-parole
  git diff --stat master -- \
    frontend/src/features/recipe-form/RecipeForm.tsx \
    frontend/src/features/recipe-form/formModel.ts \
    frontend/src/features/recipe-import/ \
    frontend/src/components/ui/Alert.tsx \
    frontend/src/components/ui/Section.tsx \
    frontend/src/features/shopping-list/AddItemField.tsx \
    frontend/src/features/pantry/PantryRow.tsx
  ```
  Expected: **vuoto**. Questi file sono sul ramo come su `master`, e il piano li dà come li vede lì (`TermCard.tsx` e `DecidedTermRow.tsx` interi, gli altri con blocchi «sostituisci questo con questo» esatti). Se uno di loro è cambiato, applica le modifiche di questo piano sopra la versione del ramo, blocco per blocco, invece di sovrascriverlo, e scrivilo nel report. I file cambiati dai Piani 1–3 (`AiDraftScreen.tsx`, `NewIngredientFields.tsx`, `StockingScreen.tsx`, `CategoryForm.tsx`, il dettaglio della ricetta) si leggono comunque prima di toccarli.
- [ ] La linea di partenza, dal worktree:
  ```bash
  cd /home/mactyws/coding/ais/spena/.worktrees/c6b-modulo-coda-parole/frontend && npx vitest run 2>&1 | grep -E "Test Files|Tests "
  cd ../backend && PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q 2>&1 | tail -n 1
  ```
  Expected: tutto verde. **Annota i due numeri** (file e test di vitest, test di pytest): sono `N_file`, `N_vitest`, `N_pytest` del Task 10, e dipendono da quel che i Piani 1–3 hanno aggiunto. Se una delle due linee non è verde, fermati: non è un difetto di questo piano, e va scritto nel report.

---

## Obiettivo e contesto

T3 ha portato una schermata alla volta sulle primitive della Consegna 0: Dispensa, Lista, Sistema la spesa, e stanotte, prima di questo piano, i pulsanti con Accesso e Anagrafica (6a), il ricettario (4) e il dettaglio della ricetta (5). Resta la metà della Consegna 6 che non è una schermata sola: il modulo con cui si scrive e si corregge una ricetta, la coda «Ingredienti da abbinare», e le parole a video sparse. Qui il giro del 2026-09-27 aveva trovato cose piccole ma che insieme fanno sembrare l'app un prototipo — due pulsanti primari uno sopra l'altro, caselle da 20 px, un messaggio rosso che cita `OPENROUTER_API_KEY` anche a coda vuota, «dataset» su ogni ricetta, «collegato a astice», nomi degli ingredienti ora in maiuscolo ora no — e un vicolo cieco vero, R12: scrivendo una ricetta a mano non si aggiunge un ingrediente che l'anagrafica non ha. La spec lo chiude dentro il selettore unico (§3.5), che «Aggiungi «…»» lo sa già offrire; il backend sa già creare l'ingrediente salvando. Manca il pezzo in mezzo, ed è questo piano. È l'ultima consegna del ridisegno.

## Decisioni prese

Dalla fase giorno del 2026-09-29 (seconda), per questo piano:

1. **Modulo della ricetta.** «Proponi» secondario, «Salva» principale, tutti e due con `Button`. «Salva» non ancora pronto → `unavailableReason` col motivo che oggi sta **sopra** il pulsante (`validationProblem`), spostato **sotto** (lo disegna `Button`); in volo → `busy`. Caselle da 44 px, anche «Di solito è secondario» in `TermCard`. Un colore solo per il guasto dell'AI in tutta l'app, deciso qui guardando i token (sotto, scelta 13).
2. **R12.** Nel modulo il selettore unico offre «Aggiungi «…»» (`onCreate`); ne nasce una riga non agganciata passando dal passo «Come si chiama in generale?» (`NewIngredientFields`, con `CategorySelect foodOnly`, perché una ricetta non può nominare un non alimentare) e con la nota «lo creo io salvando». Il backend crea già l'ingrediente salvando (`_resolve_lines`): nessuna modifica al backend. Due righe nuove con lo stesso nome non si duplicano.
3. **`CategorySelect`** estratto, con un'opzione `foodOnly`, usato da `registry/CategoryForm.tsx`, `stocking/NewIngredientFields.tsx`, `recipe-import/TermCard.tsx` e il modulo della ricetta.
4. **Coda d'import.** L'AI non configurata non è rossa, non cita `OPENROUTER_API_KEY` (testo riscritto nel frontend, nessuna modifica al backend) e non compare a coda vuota; il suggerimento «Forse «…»» non è più grande del resto; l'annullamento passa dall'avviso unico.
5. **Parole a video.** «backend» → «il server»; «autocomplete» → «i suggerimenti»; «dataset» non compare più da nessuna parte; «collegato a astice» → «collegato ad astice» (un helper: «ad» davanti a parola che comincia per «a»); maiuscole degli ingredienti uniformi solo a video, con un helper condiviso (prima lettera maiuscola; `Section.tsx` ne ha già uno, che si sposta), nessun dato si riscrive; «Ingrediente» invece di «voce» dove si collega una voce di testo libero (idea di Parte X) — rivista caso per caso (scelta 22).

Scelte di questo piano, dove la fase giorno non arrivava (reversibili; Mattia le rivede):

6. **Gli helper di testo stanno in `frontend/src/lib/text.ts`**: `capitalizeFirst(text)` (quello di `Section.tsx`, spostato) e `withPrepositionA(word)` → «ad astice» / «a pasta». La «d» eufonica solo davanti a «a»/«à»: è l'uso di oggi («a erba cipollina», «a olio»).
7. **`CategorySelect` sta in `frontend/src/components/`**, accanto a `IngredientPicker`: è un campo del dominio, non una primitiva di stile. L'etichetta in vista è **«Reparto» dappertutto** — la parola dell'app per `Ingredient.category` — e il nome accessibile di una riga dice quale: **«Reparto per «…»»** al posto di «Categoria per «…»» nel modulo e nella coda. *Perché:* nel modulo c'è già «Categoria» della ricetta (Primi piatti, Dolci), e due «Categoria» per due cose diverse nella stessa schermata erano un'ambiguità. Le voci si leggono con la maiuscola («Verdura»), come i titoli delle sezioni; il valore resta quello del backend, in minuscolo.
8. **`Checkbox`** (`frontend/src/components/ui/Checkbox.tsx`): il quadratino si vede da 24 px (era 20) dentro un quadrato da 44×44 che è il bersaglio; va dentro una `<label>`, che rende cliccabile il quadrato intero. Una primitiva e non due classi ripetute: le caselle da 44 sono due oggi (modulo e coda) e la Lista ne ha una terza che un giorno la userà.
9. **R12 offre «Aggiungi «…»» sempre**, appena la ricerca ha risposto (`createWhen="always"`), non solo a ricerca vuota: è la scelta di «Sistema la spesa» (S6) per lo stesso motivo — «zucch» pesca «Zucchero», e la porta per «zucchine» non deve sparire dietro di lui.
10. **Il passo di R12 è `NewIngredientFields`** sotto il selettore, in un riquadro `card`, col pulsante **«Aggiungi alla ricetta»** (`submitLabel`): lì l'ingrediente non nasce subito, nasce salvando la ricetta, e «Crea l'ingrediente» direbbe il falso. Aggiunta la riga, **il fuoco va sulla sua «Quantità»** (è la prossima cosa da scrivere); «Annulla» lo riporta al campo «Aggiungi un ingrediente».
11. **«Lo stesso nome» vale anche contro le righe che ci sono già**: un nome nuovo uguale (senza maiuscole né spazi ai lati) al testo di una riga da creare, o all'ingrediente di una riga agganciata, non aggiunge niente — include quella riga, come fa oggi la scelta di un ingrediente già in elenco. E una riga dell'AI «non in anagrafica, sarà esclusa» (senza reparto proposto) ripresa così prende il reparto scelto nel passo, e parte salvando: è la sua uscita.
12. **«Proponi»** porta l'icona `IconSparkles` (spec §3.3, «scrivi con l'AI»: un pulsante da solo → icona e testo); con meno di tre lettere nella richiesta, `unavailableReason` «Scrivi cosa vuoi cucinare: bastano tre lettere.».
13. **Il colore del guasto dell'AI è l'ambra di `low`**, in un tono nuovo di `Alert`: `tone="degraded"` → `text-low`, `role="alert"` come gli altri toni. *Perché:* la spec §3.1 dà al rosso due soli significati, «manca» e «non è andata», e §4.7 vuole che l'AI non configurata non sia rossa; il grigio di `tone="note"` direbbe «niente di importante», mentre un aiuto è davvero mancato. L'ambra nell'app vuol già dire «funziona, ma non del tutto» — `IngredientPicker` e la barra della Lista la usano per la ricerca che non risponde, con la strada a mano che resta — ed è esattamente il caso dell'AI: la stesura manca, il modulo c'è; il giro manca, la coda si decide a mano. `low` regge 4,5:1 su `page` e su `card` nei due temi (`theme.test.ts`). Lo usano i due messaggi della coda (503 e ogni altro errore del giro dell'AI) e quello della stesura.
14. **Il 503 della coda** dice «L'AI non è disponibile: decidi a mano qui sotto, la coda funziona.»; ogni altro errore resta «Non sono riuscito a chiedere all'AI. Decidi a mano: la coda funziona.». Tutti e due solo con la coda non vuota. Il `detail` del backend resta nella risposta (e nei log): non si mostra.
15. **L'esito dell'annullamento è un avviso senza azione.** Non c'è un «Annulla» dell'annullamento: rifare la decisione vorrebbe dire ricrearne l'ingrediente e le ricette, cioè decidere di nuovo — e il termine è appena tornato in coda, dove la sua scheda è la strada per farlo. L'errore dell'annullamento resta un `Alert` nella pagina, come oggi.
16. **«Forse «…»» diventa un `Button` `ghost` della forma di default** (pastiglia, `text-sm`), allineato a sinistra: non più `block` a tutta larghezza in `text-base`, che lo rendeva il pulsante più grosso della scheda anche quando la somiglianza è assurda.
17. **«Collega a …» e «collegato a …» usano `withPrepositionA`** in `TermCard` e `DecidedTermRow`: sono gli unici due posti del frontend con «a» davanti a un nome variabile (cercati).
18. **In `TermCard`, «Crea e collega» senza nome** → `unavailableReason` «Scrivi il nome per crearlo.» (la frase di `NewIngredientFields`); gli altri pulsanti della scheda, di `DecidedTermRow` e della coda → `busy` in volo. «Crea un ingrediente nuovo» e «Annulla» di una decisione tengono il loro nome accessibile con `accessibleName`.
19. **«Ingredienti» nel modulo diventa un `SectionHeading`** (dal giro: «INGREDIENTI» nella bozza non era un `SectionHeading`).
20. **Le maiuscole si mettono dove un nome dell'anagrafica apre una riga**: il nome della riga in Dispensa (`PantryRow`), il nome di una riga del modulo, il nome di una riga d'ingrediente nel dettaglio della ricetta. **Non** dentro una frase («Manca: pasta, uova», «Rimesso in lista: mela», «collegato ad astice»), **non** nei nomi accessibili che mettono il nome in mezzo a una frase («Togli pasta», «Quantità per pasta»), **non** nel testo che una persona ha scritto in Lista e in Sistema la spesa (`raw_text` è suo, com'è: la stessa ragione per cui `quantity_text` non si riscrive), **non** nel titolo del foglio della cottura (quasi sempre un prodotto, col suo nome di marca; il Piano 3 l'ha appena rifatto). Le ultime due restano idee in `next-steps.md`.
21. **«il server»**: «Il server ha rifiutato la ricetta: …» nel modulo; «Se insiste, è il server che non risponde: …» in Sistema la spesa. **«i suggerimenti»**: la barra della Lista dice «I suggerimenti non rispondono. Puoi aggiungere la voce così com'è, e abbinarla dopo in «Sistema la spesa».» — senza «l'ingrediente», e con la strada.
22. **«Ingrediente» o «voce», rivisti caso per caso**: cambia solo la frase della barra della Lista (21), dove «l'ingrediente si abbina dopo» parlava della voce. Restano «Abbina un ingrediente», «Scegli a quale ingrediente corrisponde», «Crea l'ingrediente»: lì si nomina proprio la voce dell'anagrafica, che nell'app si chiama ingrediente anche quando è un detersivo (l'Anagrafica dice «Cerca un ingrediente o un prodotto»); rinominare la parola dell'anagrafica è un'altra cosa.
23. **«dataset»**: il Piano 2 toglie la provenienza dalle righe del ricettario, l'unico posto dove si leggeva. Qui lo si verifica (grep) e lo si fissa con l'e2e sulle parole; se sul ramo fosse ancora a video, lo si toglie (Task 7).
24. **Due test del backend e nessun codice**: fissano che una modifica (`PUT`) con una riga `{name, category}` crea l'ingrediente, e che un nome nuovo che è un non alimentare torna 422 con la frase. È il contratto su cui R12 conta nella modifica, dove oggi c'è solo il caso dell'alias.

## Criteri di accettazione

- [ ] Nel modulo della ricetta (scrivere e modificare) «Salva» è l'unico primario; non pronto ha `aria-disabled="true"`, il motivo sotto di sé come sua descrizione, e il tocco non salva; in volo è `busy` e tiene il fuoco. «Proponi» è secondario, con `IconSparkles`, e con meno di tre lettere dice perché e non parte.
- [ ] La casella di un aggancio incerto (modulo) e «Di solito è secondario» (coda) hanno un bersaglio di almeno 44×44 px, e un tocco nell'angolo del bersaglio le spunta (e2e).
- [ ] Nel modulo, scritto un nome che l'anagrafica non ha, «Aggiungi «…»» c'è (anche se la ricerca trova altro); apre «Come si chiama in generale?» col nome e un «Reparto» senza «Casa» e «Igiene»; «Aggiungi alla ricetta» mette una riga con «Non è in anagrafica: lo creo io salvando.» e «Reparto per «…»», porta il fuoco sulla sua quantità, e salvando manda `{name, category, role, quantity_text}`. Lo stesso nome due volte, o il nome di una riga che c'è, non aggiunge righe. «Annulla» chiude il passo e torna al campo. A 375 px niente scorre di lato (e2e).
- [ ] `PUT /api/v1/recipes/{id}` con una riga `{name, category}` nuova crea l'ingrediente (`display_name` con la maiuscola, il reparto mandato); con il nome di un non alimentare risponde 422 con «non è un alimento» e lascia la ricetta com'era.
- [ ] `CategorySelect` è l'unico importatore di `domain/categories` nel codice (oltre a `departments.test.ts`); «Reparto» in Anagrafica, Sistema la spesa, coda e modulo; `foodOnly` nei tre posti del mondo ricette.
- [ ] Il guasto dell'AI è `text-low` (`Alert tone="degraded"`) nella stesura e nella coda; nella coda il 503 dice «L'AI non è disponibile: decidi a mano qui sotto, la coda funziona.», nessun testo contiene `OPENROUTER_API_KEY`, e a coda vuota il messaggio non c'è.
- [ ] «Forse «…»» è in `text-sm` (14 px a video) e non a tutta larghezza; l'esito di un annullamento compare dentro la regione `status` dell'avviso unico, e non più come riga della pagina.
- [ ] «collegato ad astice», «Collega ad aglio»; «collegato a pasta» resta.
- [ ] Nessuna di queste parole a video: «backend», «dataset», «autocomplete», `OPENROUTER_API_KEY` (e2e su ogni schermata fissa e sul dettaglio di una ricetta).
- [ ] Il nome della riga in Dispensa, di una riga del modulo e di una riga d'ingrediente del dettaglio si legge con la maiuscola; i nomi accessibili e i corpi mandati no.
- [ ] Tutti i test di oggi passano, migrati solo dove un controllo o un testo è cambiato (elencati nei task), mai indeboliti.
- [ ] vitest, typecheck, lint, build, pytest e l'e2e intera verdi; `style.spec.ts` ha cinque prove nuove.
- [ ] `docs/prossimi-passi.md` e `next-steps.md` aggiornati (Task 9).

## Comandi di verifica

Da `<worktree>/frontend`:

```bash
npx vitest run
npm run typecheck
npm run lint
npm run build
```

Da `<worktree>/backend`:

```bash
PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Dalla radice di `<worktree>`:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "Il backend ha rifiutato\|è il backend che\|L'autocomplete\|Categoria per «" frontend/src frontend/e2e
grep -rln "domain/categories" frontend/src | sort
```

Expected: i primi due `grep` non stampano niente; il terzo stampa solo `frontend/src/components/CategorySelect.tsx` e `frontend/src/components/ui/departments.test.ts`. E l'e2e intera con i comandi delle Global Constraints.

## Fuori scope

- Tutto quel che fanno i Piani 1–3: `Button` stesso, Accesso, Anagrafica (le azioni come `IconToolbar`, «Cerca un ingrediente o un prodotto»), `IngredientPicker` oltre al suo uso nel modulo, il ricettario, il dettaglio della ricetta oltre alla maiuscola del nome di riga, il foglio della cottura, «Salvata.».
- Qualunque modifica al codice del backend: il 503 della coda resta com'è (col nome della variabile nel `detail`), `_resolve_lines` resta com'è.
- La formula «non in anagrafica, sarà escluso» per una riga non alimentare della bozza (Parte X): resta un'idea; con R12 quella riga ha però una strada (scelta 11).
- Il fuoco dopo un annullamento nella coda (la riga sparisce, il fuoco cade sulla pagina), la ricerca fra le decisioni, il filtro per termine oltre le 50: idee.
- La casella della Lista (`ListRow.tsx`, 20 px dentro una label alta 44): la Lista non si tocca in questa consegna.
- Le maiuscole in Lista, in Sistema la spesa e nel foglio della cottura (scelta 20).
- Il pulsante primario spento in scuro e il velo del ☰ (voce `tbd` a parte).

## Margine di autonomia

- **Liberi:** i nomi di variabili locali, helper di test e funzioni interne non fissati qui; l'ordine dei test dentro un file; l'ordine delle classi Tailwind; la formulazione dei commenti, purché dicano il perché.
- **Fissi:** le parole a video, esattamente come sono scritte nel piano («Aggiungi alla ricetta», «Reparto», «Reparto per «…»», «Scrivi cosa vuoi cucinare: bastano tre lettere.», «L'AI non è disponibile: decidi a mano qui sotto, la coda funziona.», «Scrivi il nome per crearlo.», «I suggerimenti non rispondono. Puoi aggiungere la voce così com'è, e abbinarla dopo in «Sistema la spesa».», «Il server ha rifiutato la ricetta: …», «è il server che non risponde»); i nomi pubblici che altri task usano (`capitalizeFirst`, `withPrepositionA`, `CategorySelect` e le sue prop, `Checkbox`, `tone="degraded"`, `lineFromNewName`, `addNewLine`, le prop `foodOnly` e `submitLabel` di `NewIngredientFields`); i nomi accessibili di oggi dove il piano non li cambia.
- **Nessuna dipendenza nuova**, nessuna migrazione, nessun token di colore nuovo.
- **Un test di oggi si cambia solo per seguire un controllo che ha cambiato forma o un testo riscritto** — `toBeDisabled` → `aria-disabled` di `busy`/`unavailableReason` (con la prova che il tocco non fa niente), «Categoria per» → «Reparto per», il 503 riscritto, un nome che ora si legge con la maiuscola — mai per indebolirlo: un'asserzione d'assenza (`queryBy… toBeNull`) su un nome che ora ha la maiuscola si migra alla maiuscola, o passerebbe a vuoto. Le migrazioni ammesse sono elencate nei task; se ne serve un'altra, scrivila nel report con il perché.
- **Una decisione non coperta e non reversibile** → si ferma quel task, si fa commit del lavoro parziale sul ramo, lo si segna `bloccato` in `next-steps.md` del ramo con la domanda precisa per Mattia, e si passa al task successivo. Una scelta reversibile e a basso impatto → la più conservativa, annotata nel report della notte.
- Se un test fallisce e non si risolve in modo ragionevole: niente test disattivati, niente asserzioni indebolite; `bloccato` con la diagnosi.

## Dipendenze

**Parte da `night/c5-dettaglio`** (Piano 3, `docs/superpowers/plans/2026-09-30-ridisegno-dettaglio-ricetta.md`), che a sua volta parte da `night/c4-ricette` (Piano 2) e da `night/c6a-pulsanti` (Piano 1): quattro rami a catena, così al merge non ci sono conflitti. Da loro questo piano consuma:

- **Piano 1:** `Button` con `unavailableReason` e `accessibleName` (Global Constraints); `NewIngredientFields` col suo «Crea l'ingrediente» già passato a `Button` (`busy` in volo, `unavailableReason` «Scrivi il nome per crearlo.» a nome vuoto); `IngredientPicker` col suo «Aggiungi «…»» in `busy`.
- **Piano 2:** il ricettario senza la provenienza («dataset») sulle righe.
- **Piano 3:** il dettaglio della ricetta rifatto (le righe d'ingrediente divise in Principali e Secondari), e `AiDraftScreen`/`RecipeEditScreen` che dopo il salvataggio alzano «Salvata.» con l'avviso unico: questo piano non tocca quel pezzo.

Se la Preparazione trova il ramo di partenza mancante o `Button` senza le due prop, il piano non parte (vedi la Preparazione).

---

## File toccati

| File | Task | Cosa |
|---|---|---|
| `frontend/src/lib/text.ts` (nuovo), `text.test.ts` (nuovo) | 1 | `capitalizeFirst`, `withPrepositionA` |
| `frontend/src/components/ui/Section.tsx` | 1 | usa `capitalizeFirst` |
| `frontend/src/components/ui/Alert.tsx`, `Alert.test.tsx` (nuovo) | 1 | `tone="degraded"` |
| `frontend/src/components/ui/Checkbox.tsx` (nuovo), `Checkbox.test.tsx` (nuovo) | 1 | la casella da 44 |
| `frontend/src/components/CategorySelect.tsx` (nuovo), `CategorySelect.test.tsx` (nuovo) | 1 | il campo «Reparto» |
| `frontend/src/features/registry/CategoryForm.tsx` | 2 | `CategorySelect` |
| `frontend/src/features/stocking/NewIngredientFields.tsx`, `.test.tsx` | 2 | `CategorySelect`, `foodOnly`, `submitLabel` |
| `frontend/src/features/recipe-form/RecipeForm.tsx` | 3, 4 | «Salva», caselle, reparto, maiuscola, `SectionHeading`, «il server»; R12 |
| `frontend/src/features/recipe-form/RecipeForm.test.tsx` | 3, 4 | tre test, due migrazioni; cinque test |
| `frontend/src/features/ai-draft/AiDraftScreen.test.tsx` | 3, 5 | migrazioni di «Salva» e «Reparto per»; due test |
| `frontend/e2e/ai-draft.spec.ts` | 3 | «Reparto per» |
| `frontend/src/features/recipe-form/formModel.ts`, `formModel.test.ts` | 4 | `lineFromNewName`, `addNewLine`; quattro test |
| `backend/tests/api/test_recipes_edit.py` | 4 | due test |
| `frontend/src/features/ai-draft/AiDraftScreen.tsx` | 5 | «Proponi», il guasto ambra |
| `frontend/src/features/recipe-import/ImportQueueScreen.tsx`, `.test.tsx` | 6 | l'AI, l'annullamento nell'avviso, `Button` |
| `frontend/src/features/recipe-import/TermCard.tsx` | 6 | riscritto |
| `frontend/src/features/recipe-import/DecidedTermRow.tsx`, `.test.tsx` | 6 | «ad», `Button` |
| `frontend/src/features/stocking/StockingScreen.tsx`, `.test.tsx` | 7 | «il server» |
| `frontend/src/features/shopping-list/AddItemField.tsx`, `.test.tsx` | 7 | «i suggerimenti» |
| `frontend/src/features/pantry/PantryRow.tsx`, `PantryRow.test.tsx`, `PantryScreen.test.tsx` | 7 | la maiuscola |
| il dettaglio della ricetta in `frontend/src/features/cooking/` e il suo test | 7 | la maiuscola |
| `frontend/e2e/style.spec.ts` | 8 | cinque prove |
| `docs/prossimi-passi.md`, `next-steps.md` | 9 | i documenti |

---

### Task 1: Le primitive — le parole, il tono ambra, la casella da 44, il campo «Reparto»

**Files:**
- Create: `frontend/src/lib/text.ts`, `frontend/src/lib/text.test.ts`
- Modify: `frontend/src/components/ui/Section.tsx`
- Modify: `frontend/src/components/ui/Alert.tsx`; Create: `frontend/src/components/ui/Alert.test.tsx`
- Create: `frontend/src/components/ui/Checkbox.tsx`, `frontend/src/components/ui/Checkbox.test.tsx`
- Create: `frontend/src/components/CategorySelect.tsx`, `frontend/src/components/CategorySelect.test.tsx`

**Interfaces:**
- Produces: `capitalizeFirst(text: string): string` e `withPrepositionA(word: string): string` in `frontend/src/lib/text.ts`; `Alert` con `tone?: "error" | "note" | "degraded"`; `Checkbox(props)` con le prop di un `<input>` tranne `type` e `className`; `CategorySelect({ value, onChange, foodOnly?, label?, accessibleLabel?, disabled? })`. I Task 2–8 li usano.

- [ ] **Step 1: I test che falliscono**

Crea `frontend/src/lib/text.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { capitalizeFirst, withPrepositionA } from "./text";

describe("capitalizeFirst", () => {
  it.each([
    ["pasta", "Pasta"],
    ["yogurt greco", "Yogurt greco"],
    ["Rigatoni", "Rigatoni"],
    ["", ""],
    ["élite", "Élite"],
  ])("«%s» si legge «%s»", (testo, atteso) => {
    expect(capitalizeFirst(testo)).toBe(atteso);
  });
});

describe("withPrepositionA", () => {
  it.each([
    ["astice", "ad astice"],
    ["Aglio", "ad Aglio"],
    ["àncora", "ad àncora"],
    ["pasta", "a pasta"],
    ["erba cipollina", "a erba cipollina"],
    ["un ingrediente", "a un ingrediente"],
  ])("davanti a «%s» dice «%s»", (parola, atteso) => {
    expect(withPrepositionA(parola)).toBe(atteso);
  });
});
```

Crea `frontend/src/components/ui/Alert.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Alert } from "./Alert";

describe("Alert", () => {
  it.each([
    ["error", "text-danger"],
    ["note", "text-ink-soft"],
    ["degraded", "text-low"],
  ] as const)("il tono %s è un alert in %s", (tone, classe) => {
    render(<Alert tone={tone}>Qualcosa</Alert>);
    expect(screen.getByRole("alert")).toHaveClass(classe);
  });
});
```

Crea `frontend/src/components/ui/Checkbox.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Checkbox } from "./Checkbox";

describe("Checkbox", () => {
  it("dentro una label, un tocco sul quadrato intorno alla casella la spunta", async () => {
    const onChange = vi.fn();
    render(
      <label>
        <Checkbox aria-label="Includi basilico" checked={false} onChange={onChange} />
        Basilico
      </label>
    );
    const casella = screen.getByRole("checkbox", { name: "Includi basilico" });
    // il quadrato da 44 px è il genitore della casella: il tocco lì, non sul quadratino
    await userEvent.click(casella.parentElement!);
    expect(onChange).toHaveBeenCalledOnce();
  });

  it("è una casella vera, con i suoi attributi", () => {
    render(
      <label>
        <Checkbox aria-label="Di solito è secondario" defaultChecked aria-disabled="true" />
      </label>
    );
    const casella = screen.getByRole("checkbox", { name: "Di solito è secondario" });
    expect(casella).toBeChecked();
    expect(casella).toHaveAttribute("aria-disabled", "true");
  });
});
```

Crea `frontend/src/components/CategorySelect.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CategorySelect } from "./CategorySelect";

describe("CategorySelect", () => {
  it("di norma offre tutti i reparti, e i non alimentari a parte", () => {
    render(<CategorySelect value="altro" onChange={vi.fn()} />);
    const reparto = screen.getByRole("combobox", { name: "Reparto" }) as HTMLSelectElement;
    expect(reparto.options).toHaveLength(14);
    const gruppo = reparto.querySelector('optgroup[label="Non alimentari"]');
    expect(gruppo?.querySelector('option[value="casa"]')).not.toBeNull();
    expect(gruppo?.querySelector('option[value="igiene"]')).not.toBeNull();
  });

  it("`foodOnly` offre solo i reparti del cibo: una ricetta non può nominare un non alimentare", () => {
    render(<CategorySelect value="altro" onChange={vi.fn()} foodOnly />);
    const reparto = screen.getByRole("combobox", { name: "Reparto" }) as HTMLSelectElement;
    expect(reparto.options).toHaveLength(12);
    expect(reparto.querySelector("optgroup")).toBeNull();
    expect(within(reparto).queryByRole("option", { name: "Casa" })).toBeNull();
  });

  it("le voci si leggono con la maiuscola, e il valore resta quello del backend", async () => {
    const onChange = vi.fn();
    render(<CategorySelect value="altro" onChange={onChange} />);
    const reparto = screen.getByRole("combobox", { name: "Reparto" });
    expect(within(reparto).getByRole("option", { name: "Latticini" })).toHaveValue("latticini");
    await userEvent.selectOptions(reparto, "latticini");
    expect(onChange).toHaveBeenCalledWith("latticini");
  });

  it("l'etichetta in vista resta «Reparto», e il nome accessibile può dire per quale riga", () => {
    render(
      <CategorySelect value="carne" onChange={vi.fn()} accessibleLabel="Reparto per «speck»" />
    );
    expect(screen.getByRole("combobox", { name: "Reparto per «speck»" })).toHaveValue("carne");
    expect(screen.getByText("Reparto")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Farli fallire**

Run (da `<worktree>/frontend`): `npx vitest run src/lib/text.test.ts src/components/ui/Alert.test.tsx src/components/ui/Checkbox.test.tsx src/components/CategorySelect.test.tsx`
Expected: FAIL — i moduli `./text`, `./Checkbox`, `./CategorySelect` non esistono; `tone="degraded"` non è nel tipo (il test di `Alert` fallisce sul caso `degraded`).

- [ ] **Step 3: Il codice**

Crea `frontend/src/lib/text.ts`:

```ts
/** La prima lettera maiuscola, solo a video (spec T3 §4.7). I nomi dell'anagrafica
 * sono scritti in minuscolo (`Ingredient.name`), e accanto a un `display_name` o al
 * titolo di una sezione si leggevano «a caso» (dal giro). Nessun dato si riscrive: si
 * chiama dove un nome apre una riga, mai dentro una frase («Manca: pasta, uova») e mai
 * in un nome accessibile che lo mette in mezzo a una frase («Togli pasta»). */
export function capitalizeFirst(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** «a» o «ad» davanti a una parola (dal giro di T3: «collegato a astice»). La «d»
 * eufonica solo davanti a una parola che comincia per «a», com'è l'uso di oggi: «ad
 * astice», ma «a erba cipollina», «a olio». */
export function withPrepositionA(word: string): string {
  return /^[aàAÀ]/.test(word) ? `ad ${word}` : `a ${word}`;
}
```

In `frontend/src/components/ui/Section.tsx` togli la funzione locale:

```tsx
function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}
```

aggiungi, sotto `import { departmentStyle, TINT_CLASSES } from "./departments";`:

```tsx
import { capitalizeFirst } from "../../lib/text";
```

e nella riga del nome sostituisci `capitalize(category)` con `capitalizeFirst(category)`:

```tsx
  const name = title ?? (category ? capitalizeFirst(category) : "Senza reparto");
```

Sostituisci tutto `frontend/src/components/ui/Alert.tsx` con:

```tsx
import type { ReactNode } from "react";

// Ogni rifiuto dell'app passa da qui. `role="alert"` non è decorazione: è ciò che fa
// leggere il messaggio a uno screen reader nel momento in cui appare, invece di
// lasciarlo come testo che comparirà sotto le dita di chi scorre.
//
// Il tono è una scelta. `error` dice «è andato male qualcosa», in rosso: il rosso vuol
// dire «manca» o «non è andata», e basta (spec T3 §3.1). `note` dice «non ho potuto»,
// in grigio, per una cosa che si fa comunque. `degraded` è il guasto di un aiuto — l'AI,
// oggi — con la strada a mano che resta: l'ambra di «funziona, ma non del tutto», la
// stessa di «quasi finito» e della ricerca che non risponde. Il guasto dell'AI ha un
// colore solo in tutta l'app (spec T3 §4.7), ed è questo.
const COLOUR = {
  error: "text-danger",
  note: "text-ink-soft",
  degraded: "text-low",
} as const;

export function Alert({
  children,
  className = "",
  tone = "error",
}: {
  children: ReactNode;
  className?: string;
  tone?: keyof typeof COLOUR;
}) {
  return (
    <p role="alert" className={`text-sm ${COLOUR[tone]} ${className}`}>
      {children}
    </p>
  );
}
```

Crea `frontend/src/components/ui/Checkbox.tsx`:

```tsx
import type { InputHTMLAttributes } from "react";

/** La casella di casa (spec T3 §4.7, dal giro: «le caselle sono da 20×20»). Il
 * quadratino si vede da 24 px, ma il bersaglio è il quadrato da 44×44 intorno a lui: la
 * regola dei 44 px vale per l'area di tocco, non per il disegno (spec §3.2).
 *
 * Va messa dentro una `<label>`: è la label che rende cliccabile il quadrato intero,
 * come per ogni casella nativa. Il colore della spunta è il verde dell'app. */
export function Checkbox(props: Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "className">) {
  return (
    <span className="flex size-11 shrink-0 items-center justify-center">
      <input type="checkbox" {...props} className="size-6 accent-brand aria-disabled:opacity-40" />
    </span>
  );
}
```

Crea `frontend/src/components/CategorySelect.tsx`:

```tsx
import { FOOD_CATEGORIES, NON_FOOD_CATEGORIES } from "../domain/categories";
import { capitalizeFirst } from "../lib/text";

/** Il reparto di un ingrediente (spec T3 §4.7): lo stesso campo per Sistema la spesa,
 * l'Anagrafica, la coda d'import e il modulo della ricetta, che ne avevano quattro copie.
 *
 * `foodOnly` nei posti del mondo ricette — la riga da creare del modulo, il passo «Come
 * si chiama in generale?» quando lo apre il modulo (R12), la scheda della coda d'import:
 * una ricetta non può nominare un non alimentare (`write_recipe_ingredients` lo
 * rifiuta), e offrirlo qui sarebbe offrire un rifiuto un istante dopo. Altrove i non
 * alimentari stanno a parte, in un gruppo loro: non sono un reparto in più del
 * supermercato, sono la metà dell'anagrafica che le ricette non vedono.
 *
 * «Reparto» e non «Categoria»: nel modulo della ricetta «Categoria» è già quella della
 * ricetta (Primi piatti, Dolci). Le voci si leggono con la maiuscola, come i titoli delle
 * sezioni; il valore resta quello del backend (`IngredientCategory`), in minuscolo. */
export function CategorySelect({
  value,
  onChange,
  foodOnly = false,
  label = "Reparto",
  accessibleLabel,
  disabled = false,
}: {
  value: string;
  onChange: (category: string) => void;
  foodOnly?: boolean;
  label?: string;
  /** Quando deve dire più dell'etichetta in vista: in un elenco di righe o di schede,
   * per quale. Di norma coincide con `label`. */
  accessibleLabel?: string;
  disabled?: boolean;
}) {
  return (
    <label className="text-sm font-medium text-ink-soft">
      {label}
      <select
        aria-label={accessibleLabel ?? label}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        className="mt-1.5"
      >
        {FOOD_CATEGORIES.map((category) => (
          <option key={category} value={category}>
            {capitalizeFirst(category)}
          </option>
        ))}
        {!foodOnly && (
          <optgroup label="Non alimentari">
            {NON_FOOD_CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {capitalizeFirst(category)}
              </option>
            ))}
          </optgroup>
        )}
      </select>
    </label>
  );
}
```

- [ ] **Step 4: Farli passare, e la suite**

Run: `npx vitest run src/lib/text.test.ts src/components/ui/Alert.test.tsx src/components/ui/Checkbox.test.tsx src/components/CategorySelect.test.tsx src/components/ui/Section.test.tsx`
Expected: PASS (20 test nuovi, e quelli di `Section` come prima).
Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: verde; vitest `N_vitest + 20` in `N_file + 4`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/text.ts frontend/src/lib/text.test.ts frontend/src/components/ui/Section.tsx \
  frontend/src/components/ui/Alert.tsx frontend/src/components/ui/Alert.test.tsx \
  frontend/src/components/ui/Checkbox.tsx frontend/src/components/ui/Checkbox.test.tsx \
  frontend/src/components/CategorySelect.tsx frontend/src/components/CategorySelect.test.tsx
git commit -m "ui: le primitive della Consegna 6b — la maiuscola e «ad», il tono ambra di Alert, la casella da 44, il campo Reparto"
```

---

### Task 2: «Reparto» in Anagrafica e in Sistema la spesa

**Files:**
- Modify: `frontend/src/features/registry/CategoryForm.tsx`
- Modify: `frontend/src/features/stocking/NewIngredientFields.tsx`
- Test: `frontend/src/features/stocking/NewIngredientFields.test.tsx`

**Interfaces:**
- Consumes: `CategorySelect` (Task 1).
- Produces: `NewIngredientFields` con due prop in più, `foodOnly?: boolean` (di norma `false`) e `submitLabel?: string` (di norma «Crea l'ingrediente»). Il Task 4 le usa.

Leggi prima i due file com'è sul ramo: il Piano 1 li ha toccati (il pulsante di `NewIngredientFields` è un `Button`; `CategoryForm` può esserlo). Qui cambia solo il campo del reparto, più il testo del pulsante di `NewIngredientFields`.

- [ ] **Step 1: I test che falliscono**

In `frontend/src/features/stocking/NewIngredientFields.test.tsx` sostituisci `renderFields` con:

```tsx
function renderFields(
  props: { initialName?: string; busy?: boolean; foodOnly?: boolean; submitLabel?: string } = {}
) {
  const onSubmit = vi.fn();
  const onCancel = vi.fn();
  render(
    <NewIngredientFields
      initialName={props.initialName ?? "zucchine tonde di Nizza"}
      busy={props.busy ?? false}
      foodOnly={props.foodOnly}
      submitLabel={props.submitLabel}
      onSubmit={onSubmit}
      onCancel={onCancel}
    />
  );
  return { onSubmit, onCancel };
}
```

e in fondo al `describe` aggiungi:

```tsx
  it("`foodOnly` offre solo i reparti del cibo: nel modulo della ricetta un non alimentare sarebbe rifiutato", () => {
    renderFields({ foodOnly: true });
    const reparto = screen.getByLabelText("Reparto") as HTMLSelectElement;
    expect(reparto.querySelector('option[value="casa"]')).toBeNull();
    expect(reparto.querySelector('option[value="igiene"]')).toBeNull();
    expect(reparto.querySelector('option[value="verdura"]')).not.toBeNull();
  });

  it("il pulsante dice cosa succede dove lo si usa", async () => {
    const { onSubmit } = renderFields({ initialName: "zz tre", submitLabel: "Aggiungi alla ricetta" });
    expect(screen.queryByRole("button", { name: "Crea l'ingrediente" })).toBeNull();
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi alla ricetta" }));
    expect(onSubmit).toHaveBeenCalledWith({ name: "zz tre", category: "altro" });
  });
```

- [ ] **Step 2: Farli fallire**

Run: `npx vitest run src/features/stocking/NewIngredientFields.test.tsx`
Expected: FAIL — vitest non controlla i tipi, quindi le due prop sconosciute arrivano e si ignorano: i due test nuovi falliscono (il non alimentare è offerto; il pulsante si chiama «Crea l'ingrediente»). `npm run typecheck` a questo punto segnala le due prop: è atteso, e sparisce allo Step 3.

- [ ] **Step 3: `NewIngredientFields`**

1. Negli import, togli `import { FOOD_CATEGORIES, NON_FOOD_CATEGORIES } from "../../domain/categories";` e aggiungi `import { CategorySelect } from "../../components/CategorySelect";`.
2. Nei parametri della funzione `NewIngredientFields`, dopo `onCancel,` aggiungi `foodOnly = false,` e `submitLabel = "Crea l'ingrediente",`; nel tipo, dopo `onCancel: () => void;`, aggiungi:
   ```tsx
     /** Solo i reparti del cibo: lo chiede il modulo della ricetta (R12), dove un non
      * alimentare verrebbe rifiutato al salvataggio. */
     foodOnly?: boolean;
     /** Il pulsante che conferma: «Crea l'ingrediente» in «Sistema la spesa», che lo crea
      * subito; «Aggiungi alla ricetta» nel modulo, dove nasce salvando la ricetta. */
     submitLabel?: string;
   ```
3. Sostituisci l'intero blocco del reparto — la `<label className="text-sm">` che contiene `Reparto` e il `<select aria-label="Reparto" …>` con le sue `option` e l'`<optgroup label="Non alimentari">` — con:
   ```tsx
      <CategorySelect value={category} onChange={setCategory} foodOnly={foodOnly} />
   ```
4. Nel pulsante di invio (quello `type="submit"`, oggi con il testo `Crea l'ingrediente`), sostituisci il testo `Crea l'ingrediente` con `{submitLabel}`. Il resto del pulsante (le prop `busy`/`unavailableReason` messe dal Piano 1) non cambia.

- [ ] **Step 4: `CategoryForm`**

1. Negli import, togli `import { FOOD_CATEGORIES, NON_FOOD_CATEGORIES } from "../../domain/categories";` e aggiungi `import { CategorySelect } from "../../components/CategorySelect";`.
2. Sostituisci l'intero blocco `<label className="text-sm font-medium text-ink-soft">` che contiene `Reparto` e il suo `<select value={category} … disabled={save.isPending} …>` (con le `option` e l'`optgroup`) con:
   ```tsx
      {/* tutti i reparti, i non alimentari compresi: in anagrafica si corregge anche il
          detersivo creato in «latticini» */}
      <CategorySelect value={category} onChange={setCategory} disabled={save.isPending} />
   ```

- [ ] **Step 5: Farli passare, e la suite**

Run: `npx vitest run src/features/stocking src/features/registry`
Expected: PASS — i due test nuovi, e quelli di oggi di `NewIngredientFields`, `MatchPanel`, `StockingScreen`, `IngredientScreen` senza modifiche (il campo si chiama ancora «Reparto», i valori sono gli stessi).
Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: verde; `+2`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/stocking/NewIngredientFields.tsx frontend/src/features/stocking/NewIngredientFields.test.tsx \
  frontend/src/features/registry/CategoryForm.tsx
git commit -m "anagrafica, sistemazione: il reparto con CategorySelect; NewIngredientFields impara foodOnly e submitLabel"
```

---

### Task 3: Il modulo della ricetta — «Salva» principale col motivo sotto, caselle da 44, «Reparto per», la maiuscola, «il server»

**Files:**
- Modify: `frontend/src/features/recipe-form/RecipeForm.tsx`
- Test: `frontend/src/features/recipe-form/RecipeForm.test.tsx`
- Test (migrazioni): `frontend/src/features/ai-draft/AiDraftScreen.test.tsx`, `frontend/e2e/ai-draft.spec.ts`

**Interfaces:**
- Consumes: `Button` (`busy`, `unavailableReason`; Piano 1), `Checkbox`, `CategorySelect`, `capitalizeFirst` (Task 1), `SectionHeading` (c'è già).

`RecipeForm.tsx` sul ramo è quello di `master` (la Preparazione lo ha verificato): i blocchi qui sotto sono esatti.

- [ ] **Step 1: I test che falliscono**

In `frontend/src/features/recipe-form/RecipeForm.test.tsx`:

1. Il test «il nome di una riga si legge una volta sola» diventa (migrazione: il nome ora si legge con la maiuscola; la seconda asserzione è nuova):
   ```tsx
     it("il nome di una riga si legge una volta sola, con la maiuscola; i nomi accessibili restano come sono", () => {
       stubCategories([[], 200]);
       renderForm(valuesFromRecipe(DETAIL));
       expect(screen.getAllByText("Pasta")).toHaveLength(1);
       // dentro una frase il nome resta com'è: «Quantità per pasta», non «per Pasta»
       expect(screen.getByLabelText("Quantità per pasta")).toBeInTheDocument();
     });
   ```
2. Nel test «con un elenco di errori di validazione non lo mostra grezzo, e non dice «riprova»», sostituisci `expect(avviso).toHaveTextContent(/rifiutato/);` con:
   ```tsx
       expect(avviso).toHaveTextContent(/Il server ha rifiutato la ricetta/);
       expect(avviso.textContent).not.toMatch(/backend/);
   ```
3. `lineFromDraft`, `within`, `RecipeBody` e `RecipeDetail` sono già importati nel file; aggiungi in fondo:
   ```tsx
   describe("«Salva» e le righe (T3 Consegna 6b)", () => {
     it("«Salva» non ancora pronto dice perché, sotto di sé, e il tocco non salva", async () => {
       stubCategories([[], 200]);
       const { save } = renderForm({ ...valuesFromRecipe(DETAIL), instructions: "" });

       const salvaBtn = screen.getByRole("button", { name: "Salva le modifiche" });
       expect(salvaBtn).toHaveAttribute("aria-disabled", "true");
       expect(salvaBtn).not.toBeDisabled();
       expect(salvaBtn).toHaveAccessibleDescription(
         "Servono un titolo e un procedimento per salvare."
       );
       // una volta sola, e dopo il pulsante: il motivo non sta più anche sopra
       const motivo = screen.getByText("Servono un titolo e un procedimento per salvare.");
       expect(
         salvaBtn.compareDocumentPosition(motivo) & Node.DOCUMENT_POSITION_FOLLOWING
       ).toBeTruthy();

       await salva();
       expect(save).not.toHaveBeenCalled();
     });

     it("in volo «Salva» si spegne tenendo il fuoco, e non salva due volte", async () => {
       stubCategories([[], 200]);
       const save = vi.fn((_body: RecipeBody) => new Promise<RecipeDetail>(() => {}));
       renderForm(valuesFromRecipe(DETAIL), save);

       await salva();

       const inVolo = screen.getByRole("button", { name: "Salvo…" });
       expect(inVolo).toHaveAttribute("aria-disabled", "true");
       expect(inVolo).toHaveFocus();
       await userEvent.click(inVolo);
       expect(save).toHaveBeenCalledTimes(1);
     });

     it("una riga da creare chiede il reparto fra quelli del cibo, col nome della riga", () => {
       stubCategories([[], 200]);
       renderForm({
         ...valuesFromRecipe(DETAIL),
         lines: [
           lineFromDraft(
             { raw_name: "speck", role: "primary", quantity_text: "100 g", ingredient_id: null,
               matched_name: null, confident: false, proposed_category: "carne" },
             0
           ),
         ],
       });

       const reparto = screen.getByRole("combobox", { name: "Reparto per «speck»" });
       expect(reparto).toHaveValue("carne");
       expect(within(reparto).getByRole("option", { name: "Carne" })).toBeInTheDocument();
       expect(within(reparto).queryByRole("option", { name: "Casa" })).toBeNull();
       expect(within(reparto).queryByRole("option", { name: "Igiene" })).toBeNull();
     });
   });
   ```

In `frontend/src/features/ai-draft/AiDraftScreen.test.tsx` (migrazioni, perché «Salva» passa da `disabled` a `unavailableReason`; stesse asserzioni, più strette dove si può):

1. Il test «senza titolo o senza procedimento il salvataggio è spento, e dice cosa manca» diventa:
   ```tsx
     it("senza titolo o senza procedimento il salvataggio non è ancora pronto, e dice cosa manca sotto di sé", async () => {
       vi.stubGlobal("fetch", vi.fn());
       renderScreen();

       expect(screen.getByText(/servono un titolo e un procedimento/i)).toBeDefined();
       expect(saveButton()).toHaveAttribute("aria-disabled", "true");
       expect(saveButton()).toHaveAccessibleDescription(/servono un titolo e un procedimento/i);

       await userEvent.type(screen.getByLabelText("Titolo"), "Cacio e pepe");
       expect(screen.getByText(/servono un titolo e un procedimento/i)).toBeDefined();
       expect(saveButton()).toHaveAttribute("aria-disabled", "true");

       await userEvent.type(screen.getByLabelText("Procedimento"), "1. Lessa.");
       expect(screen.queryByText(/servono un titolo e un procedimento/i)).toBeNull();
       expect(saveButton()).not.toHaveAttribute("aria-disabled");

       await userEvent.clear(screen.getByLabelText("Titolo"));
       expect(screen.getByText(/servono un titolo e un procedimento/i)).toBeDefined();
       expect(saveButton()).toHaveAttribute("aria-disabled", "true");
     });
   ```
2. Nei test «le porzioni fuori scala si correggono qui…» e «una quantità troppo lunga si corregge prima di mandarla», sostituisci `expect(saveButton()).toBeDisabled();` con `expect(saveButton()).toHaveAttribute("aria-disabled", "true");` (una riga per test).
3. Nel test «un ingrediente ignoto si crea salvando, con la categoria modificabile», sostituisci `screen.getByLabelText(/categoria per «speck»/i)` con `screen.getByLabelText(/reparto per «speck»/i)`, e il titolo del test con «un ingrediente ignoto si crea salvando, col reparto modificabile».

In `frontend/e2e/ai-draft.spec.ts` sostituisci:

```ts
  await expect(page.getByLabel(`Categoria per «${NOME_LUNGO}»`)).toHaveValue("carne");
```

con:

```ts
  await expect(page.getByLabel(`Reparto per «${NOME_LUNGO}»`)).toHaveValue("carne");
```

- [ ] **Step 2: Farli fallire**

Run: `npx vitest run src/features/recipe-form/RecipeForm.test.tsx src/features/ai-draft/AiDraftScreen.test.tsx`
Expected: FAIL — «Pasta» non c'è (si legge «pasta»), «Il server» non c'è, il pulsante ha `disabled` e non `aria-disabled`, il motivo sta sopra, «Reparto per «speck»» non esiste.

- [ ] **Step 3: Il codice**

In `frontend/src/features/recipe-form/RecipeForm.tsx`:

1. Sostituisci gli import dall'inizio del file fino a `import { CategoryField } from "./CategoryField";` compreso con:
   ```tsx
   import type { Dispatch, SetStateAction } from "react";
   import { useMutation, useQueryClient } from "@tanstack/react-query";
   import { ApiError } from "../../api/client";
   import { CategorySelect } from "../../components/CategorySelect";
   import { IngredientPicker } from "../../components/IngredientPicker";
   import { Button } from "../../components/ui/Button";
   import { Checkbox } from "../../components/ui/Checkbox";
   import { CostPicker } from "../../components/ui/CostPicker";
   import { SectionHeading } from "../../components/ui/SectionHeading";
   import type { Ingredient, IngredientRole, RecipeBody, RecipeDetail } from "../../domain/types";
   import { capitalizeFirst } from "../../lib/text";
   import { CategoryField } from "./CategoryField";
   ```
2. In `saveProblem` sostituisci:
   ```tsx
       return "Il backend ha rifiutato la ricetta: qualcosa nei campi qui sopra non va. Correggilo — rimandarla identica darà lo stesso esito.";
   ```
   con:
   ```tsx
       return "Il server ha rifiutato la ricetta: qualcosa nei campi qui sopra non va. Correggilo — rimandarla identica darà lo stesso esito.";
   ```
3. In `LineRow` sostituisci la `<label className="flex min-h-11 min-w-0 flex-1 items-center gap-3">` con tutto il suo contenuto (il commento della casella, l'`<input type="checkbox" …>` e lo `<span className="min-w-0 flex-1 break-words">{line.label}</span>`) con:
   ```tsx
           <label className="flex min-h-11 min-w-0 flex-1 items-center gap-1">
             {/* La casella c'è solo dove l'AI ha un'ipotesi da confermare: lì vuol dire
                 «è questo», non «tienila». Le righe si tolgono con la ✕ (R10 §6.2). Il
                 bersaglio è il quadrato da 44 px di `Checkbox` (dal giro: «le caselle sono
                 da 20×20») */}
             {line.uncertain && (
               <Checkbox
                 aria-label={`Includi ${line.label}`}
                 checked={line.included}
                 onChange={() => onUpdate({ included: !line.included })}
               />
             )}
             {/* la maiuscola solo a video (spec T3 §4.7): il nome mandato resta quello
                 scritto, e i nomi accessibili di questa riga lo mettono in mezzo a una frase
                 («Togli pasta», «Quantità per pasta»), dove resta com'è */}
             <span className="min-w-0 flex-1 break-words">{capitalizeFirst(line.label)}</span>
           </label>
   ```
4. In `LineRow` sostituisci il blocco `{line.ingredientId === null && line.proposedCategory !== null && ( … )}` (quello con «Non è in anagrafica: lo creo io salvando.» e la `<label className="text-xs font-medium text-ink-soft">Categoria<select …>`) con:
   ```tsx
         {line.ingredientId === null && line.proposedCategory !== null && (
           <div className="flex flex-col gap-1">
             <p className="text-xs text-ink-soft">Non è in anagrafica: lo creo io salvando.</p>
             {/* solo i reparti del cibo: una ricetta non può nominare un non alimentare, e
                 `write_recipe_ingredients` rifiuterebbe il salvataggio */}
             <CategorySelect
               value={line.proposedCategory}
               onChange={(category) => onUpdate({ proposedCategory: category })}
               foodOnly
               accessibleLabel={`Reparto per «${line.label}»`}
             />
           </div>
         )}
   ```
5. In `RecipeForm` sostituisci:
   ```tsx
           <h2 className="text-xs uppercase tracking-wide text-ink-faint">Ingredienti</h2>
   ```
   con:
   ```tsx
           {/* la stessa intestazione delle sezioni del resto dell'app (dal giro: «INGREDIENTI»
               nella bozza non era un `SectionHeading`) */}
           <SectionHeading>Ingredienti</SectionHeading>
   ```
6. In `RecipeForm` sostituisci il blocco che va dal commento «il motivo sta accanto al pulsante che sta disabilitando…» fino alla chiusura del `<button type="button" onClick={() => submit.mutate()} … </button>` compresi — cioè `{problem && <p className="text-sm text-low">{problem}</p>}` e il `<button>` — con:
   ```tsx
         {/* «Salva» è il solo primario della vista (spec T3 §4.7). Non pronto, dice perché
             sotto di sé (`unavailableReason`: un pulsante spento e muto è un vicolo cieco
             quanto un errore senza spiegazione, dal giro); in volo è `busy`. Tutti e due con
             `aria-disabled`, così il fuoco resta qui */}
         <Button
           variant="primary"
           shape="block"
           onClick={() => submit.mutate()}
           busy={submit.isPending}
           unavailableReason={problem ?? undefined}
         >
           {submit.isPending ? "Salvo…" : submitLabel}
         </Button>
   ```

Se `npm run lint` segnala `FOOD_CATEGORIES` o `buttonClasses` non usati, sono gli import che il punto 1 ha già tolto: controlla di aver sostituito tutto il blocco.

- [ ] **Step 4: Farli passare, e la suite**

Run: `npx vitest run src/features/recipe-form src/features/ai-draft`
Expected: PASS. Se un test di `RecipeEditScreen.test.tsx` cerca il nome di una riga con una stringa esatta in minuscolo, migralo alla maiuscola (solo quello) e scrivilo nel report; oggi non ce ne sono.
Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: verde; `+3` rispetto al Task 2.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/recipe-form/RecipeForm.tsx frontend/src/features/recipe-form/RecipeForm.test.tsx \
  frontend/src/features/ai-draft/AiDraftScreen.test.tsx frontend/e2e/ai-draft.spec.ts
git commit -m "ricette: il modulo con «Salva» principale e il motivo sotto, caselle da 44, «Reparto per», la maiuscola, «il server»"
```

---

### Task 4: R12 — un ingrediente che non c'è si aggiunge dal modulo

**Files:**
- Modify: `frontend/src/features/recipe-form/formModel.ts`
- Test: `frontend/src/features/recipe-form/formModel.test.ts`
- Modify: `frontend/src/features/recipe-form/RecipeForm.tsx`
- Test: `frontend/src/features/recipe-form/RecipeForm.test.tsx`
- Test: `backend/tests/api/test_recipes_edit.py`

**Interfaces:**
- Consumes: `IngredientPicker` (`onCreate`, `createWhen="always"`), `NewIngredientFields` (`foodOnly`, `submitLabel`; Task 2), `_resolve_lines` del backend (invariato).
- Produces: `lineFromNewName(name: string, category: string): FormLine` e `addNewLine(lines: FormLine[], name: string, category: string): { lines: FormLine[]; key: string }` in `formModel.ts`.

- [ ] **Step 1: I test del backend (il contratto)**

In fondo a `backend/tests/api/test_recipes_edit.py` aggiungi:

```python
# --- R12: il modulo aggiunge un ingrediente che non c'è (T3 Consegna 6b) ---
# Il modulo non chiama `POST /ingredients`: manda la riga come nome e reparto, e il
# salvataggio crea l'ingrediente dentro la transazione della ricetta (`_resolve_lines`).
# Per la creazione lo provano `test_recipes_create_ingredient.py`; qui la modifica, che
# è l'altra metà del modulo e che finora aveva solo il caso dell'alias.


async def test_r12_una_riga_nuova_scritta_in_modifica_crea_l_ingrediente(
    logged_client, db_session, cucina
):
    ricetta = await _scritta(logged_client, cucina)

    risposta = await _modifica(logged_client, ricetta["id"], _corpo(cucina, ingredients=[
        _riga(cucina["pasta"], quantity="320 g"),
        {"name": "zz tre", "category": "verdura", "role": "secondary", "quantity_text": "1"},
    ]))

    assert risposta.status_code == 200, risposta.text
    creato = (
        await db_session.execute(select(Ingredient).where(Ingredient.name == "zz tre"))
    ).scalar_one()
    assert (creato.display_name, creato.category) == ("Zz tre", "verdura")
    assert await _nomi(logged_client, ricetta["id"]) == {"pasta", "zz tre"}


async def test_r12_un_nome_nuovo_che_e_un_non_alimentare_si_rifiuta_con_la_frase(
    logged_client, cucina
):
    """Il selettore del modulo cerca solo cibo, quindi «sapone per le mani» non compare
    fra i suggerimenti e il modulo offre di aggiungerlo. Al salvataggio `match_name` lo
    trova, e l'imbuto di `write_recipe_ingredients` lo rifiuta: il 422 porta una frase,
    che il modulo mostra com'è accanto a «Salva», e la ricetta resta com'era."""
    ricetta = await _scritta(logged_client, cucina)

    risposta = await _modifica(logged_client, ricetta["id"], _corpo(cucina, ingredients=[
        _riga(cucina["pasta"]),
        {"name": "sapone per le mani", "category": "altro", "role": "primary"},
    ]))

    assert risposta.status_code == 422
    assert "non è un alimento" in risposta.json()["detail"]
    assert await _nomi(logged_client, ricetta["id"]) == {"pasta", "pomodoro", "aglio"}
```

Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q tests/api/test_recipes_edit.py`
Expected: **PASS da subito**: non sono test di codice nuovo, fissano un comportamento che c'è e su cui questo task conta. Se uno fallisce, **fermati**: la decisione della fase giorno («nessuna modifica al backend») poggia su un fatto falso; segna il task `bloccato` con l'uscita del test.

- [ ] **Step 2: I test del modello che falliscono**

In `frontend/src/features/recipe-form/formModel.test.ts`, aggiungi `addNewLine` e `lineFromNewName` all'import da `./formModel` (lo stesso import che porta già `lineFromDraft` e `recipeBody`; se `lineFromDraft` o `recipeBody` non ci sono, aggiungili), e in fondo al file:

```ts
describe("R12: le righe di un nome nuovo", () => {
  it("una riga nuova è come quelle dell'AI non agganciate, e parte salvando con nome e reparto", () => {
    const riga = lineFromNewName("  Zucchine ", "verdura");
    expect(riga).toMatchObject({
      key: "new:zucchine", label: "Zucchine", ingredientId: null, proposedCategory: "verdura",
      manual: true, included: true, role: "primary", uncertain: false,
    });
    const corpo = recipeBody({
      title: "T", description: "", category: null, servingsText: "", cost: null,
      instructions: "I", lines: [riga],
    });
    expect(corpo.ingredients).toEqual([
      { name: "zucchine", category: "verdura", role: "primary", quantity_text: null },
    ]);
  });

  it("un nome che non c'è si aggiunge in fondo, e torna la sua chiave", () => {
    const { lines, key } = addNewLine([], "zz tre", "verdura");
    expect(lines).toHaveLength(1);
    expect(key).toBe("new:zz tre");
    expect(lines[0].key).toBe(key);
  });

  it("lo stesso nome due volte resta una riga sola, anche con maiuscole e spazi diversi, e torna inclusa", () => {
    const prima = addNewLine([], "zz tre", "verdura").lines;
    const esclusa = [{ ...prima[0], included: false }];
    const { lines, key } = addNewLine(esclusa, " ZZ Tre ", "frutta");
    expect(lines).toHaveLength(1);
    expect(key).toBe("new:zz tre");
    expect(lines[0].included).toBe(true);
    // il reparto scelto la prima volta resta: la riga c'era già
    expect(lines[0].proposedCategory).toBe("verdura");
  });

  it("un nome che è già una riga non ne aggiunge un'altra: include quella, e a una riga dell'AI senza reparto dà il reparto", () => {
    const agganciata = lineFromDraft(
      { raw_name: "basilico fresco", role: "secondary", quantity_text: null, ingredient_id: "i2",
        matched_name: "basilico", confident: false, proposed_category: null },
      0
    );
    const ignota = lineFromDraft(
      { raw_name: "zafferano di Navelli", role: "secondary", quantity_text: null,
        ingredient_id: null, matched_name: null, confident: false, proposed_category: null },
      1
    );

    const conBasilico = addNewLine([agganciata, ignota], "Basilico", "spezie");
    expect(conBasilico.lines).toHaveLength(2);
    expect(conBasilico.key).toBe(agganciata.key);
    expect(conBasilico.lines[0].included).toBe(true);
    expect(conBasilico.lines[0].proposedCategory).toBeNull();

    const conZafferano = addNewLine([agganciata, ignota], "zafferano di navelli", "spezie");
    expect(conZafferano.lines).toHaveLength(2);
    expect(conZafferano.key).toBe(ignota.key);
    // era «non in anagrafica, sarà escluso»: col reparto, parte salvando
    expect(conZafferano.lines[1].proposedCategory).toBe("spezie");
    expect(savableLines(conZafferano.lines).map((line) => line.key)).toContain(ignota.key);
  });
});
```

(aggiungi anche `savableLines` all'import, se non c'è.)

Run (da `<worktree>/frontend`): `npx vitest run src/features/recipe-form/formModel.test.ts`
Expected: FAIL — `lineFromNewName` e `addNewLine` non esistono.

- [ ] **Step 3: Il modello**

In `frontend/src/features/recipe-form/formModel.ts`, subito dopo la funzione `lineFromIngredient`, aggiungi:

```ts
/** R12: una riga per un ingrediente che l'anagrafica non ha, scritta a mano. È fatta
 * come le righe dell'AI non agganciate — nome e reparto, «lo creo io salvando» — e
 * l'ingrediente nasce al salvataggio, dentro la transazione della ricetta
 * (`_resolve_lines` nel backend, per la creazione e per la modifica). `manual`: una
 * bozza nuova dell'AI non la porta via. */
export function lineFromNewName(name: string, category: string): FormLine {
  const label = name.trim();
  return {
    key: `new:${label.toLowerCase()}`,
    label,
    ingredientId: null,
    matchedName: null,
    uncertain: false,
    manual: true,
    role: "primary",
    quantityText: "",
    included: true,
    proposedCategory: category,
    note: null,
  };
}

/** Il nome con cui una riga si confronta con un nome nuovo: l'ingrediente a cui è
 * agganciata, o il testo con cui nascerà. */
function comparableName(line: FormLine): string {
  return (line.matchedName ?? line.label).trim().toLowerCase();
}

/** Aggiunge la riga di un nome nuovo, se non c'è già (R12). Due righe con lo stesso nome
 * diventerebbero lo stesso ingrediente al salvataggio, e il backend rifiuterebbe la
 * ricetta per la riga doppia: la riga che c'è si include e basta, come fa la scelta di
 * un ingrediente già in elenco. Una riga dell'AI che non sapeva il reparto («non in
 * anagrafica, sarà escluso») prende quello scelto, e così parte salvando. Torna anche la
 * chiave della riga, per darle il fuoco. */
export function addNewLine(
  lines: FormLine[],
  name: string,
  category: string
): { lines: FormLine[]; key: string } {
  const wanted = name.trim().toLowerCase();
  const existing = lines.find((line) => comparableName(line) === wanted);
  if (existing) {
    return {
      lines: lines.map((line) =>
        line.key === existing.key
          ? {
              ...line,
              included: true,
              proposedCategory:
                line.ingredientId === null ? line.proposedCategory ?? category : line.proposedCategory,
            }
          : line
      ),
      key: existing.key,
    };
  }
  const line = lineFromNewName(name, category);
  return { lines: [...lines, line], key: line.key };
}
```

Run: `npx vitest run src/features/recipe-form/formModel.test.ts`
Expected: PASS.

- [ ] **Step 4: I test del modulo che falliscono**

In `frontend/src/features/recipe-form/RecipeForm.test.tsx` aggiungi in fondo:

```tsx
describe("R12: un ingrediente che non c'è si aggiunge dal modulo", () => {
  async function offri(testo: string) {
    await userEvent.type(screen.getByLabelText("Aggiungi un ingrediente"), testo);
    return screen.findByRole("button", { name: `Aggiungi «${testo}»` });
  }

  it("«Aggiungi «…»» chiede come si chiama in generale e il reparto, solo del cibo, e la riga si crea salvando", async () => {
    stubCategories([[], 200]);
    const { save } = renderForm(valuesFromRecipe(DETAIL));

    await userEvent.click(await offri("zz tre"));

    const nome = screen.getByLabelText("Come si chiama in generale?");
    expect(nome).toHaveValue("zz tre");
    expect(nome).toHaveFocus();
    const reparto = screen.getByLabelText("Reparto");
    expect(within(reparto).queryByRole("option", { name: "Casa" })).toBeNull();
    expect(within(reparto).queryByRole("option", { name: "Igiene" })).toBeNull();

    await userEvent.clear(nome);
    await userEvent.type(nome, "zucchine");
    await userEvent.selectOptions(reparto, "verdura");
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi alla ricetta" }));

    // il passo si chiude, e la riga è come quelle dell'AI non agganciate
    expect(screen.queryByLabelText("Come si chiama in generale?")).toBeNull();
    const riga = screen.getByRole("button", { name: "Togli zucchine" }).closest("li")!;
    expect(within(riga).getByText("Zucchine")).toBeInTheDocument();
    expect(within(riga).getByText("Non è in anagrafica: lo creo io salvando.")).toBeInTheDocument();
    expect(within(riga).getByRole("combobox", { name: "Reparto per «zucchine»" })).toHaveValue(
      "verdura"
    );

    await salva();
    expect(save).toHaveBeenCalledWith(
      expect.objectContaining({
        ingredients: expect.arrayContaining([
          { name: "zucchine", category: "verdura", role: "primary", quantity_text: null },
        ]),
      })
    );
  });

  it("aggiunta la riga, il fuoco va sulla sua quantità: è la prossima cosa da scrivere", async () => {
    stubCategories([[], 200]);
    renderForm(valuesFromRecipe(DETAIL));

    await userEvent.click(await offri("zz tre"));
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi alla ricetta" }));

    expect(screen.getByLabelText("Quantità per zz tre")).toHaveFocus();
  });

  it("lo stesso nome due volte resta una riga, e il nome di una riga che c'è non ne aggiunge un'altra", async () => {
    stubCategories([[], 200]);
    renderForm(valuesFromRecipe(DETAIL));

    for (let volta = 0; volta < 2; volta++) {
      await userEvent.click(await offri("zz tre"));
      await userEvent.click(screen.getByRole("button", { name: "Aggiungi alla ricetta" }));
    }
    expect(screen.getAllByRole("button", { name: "Togli zz tre" })).toHaveLength(1);

    // «Pasta» è già la riga di «pasta»: una seconda il backend la rifiuterebbe come doppia
    await userEvent.click(await offri("Pasta"));
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi alla ricetta" }));
    expect(screen.getAllByRole("button", { name: /^Togli pasta$/i })).toHaveLength(1);
    expect(screen.getByLabelText("Quantità per pasta")).toHaveFocus();
  });

  it("«Annulla» chiude il passo senza aggiungere niente, e il fuoco torna al campo", async () => {
    stubCategories([[], 200]);
    renderForm(valuesFromRecipe(DETAIL));

    await userEvent.click(await offri("zz tre"));
    await userEvent.click(screen.getByRole("button", { name: "Annulla" }));

    expect(screen.queryByLabelText("Come si chiama in generale?")).toBeNull();
    expect(screen.queryByRole("button", { name: "Togli zz tre" })).toBeNull();
    expect(screen.getByLabelText("Aggiungi un ingrediente")).toHaveFocus();
  });

  it("«Aggiungi «…»» c'è anche quando la ricerca trova qualcosa (S6): «zucch» non è per forza «Zucchero»", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn((url: unknown) =>
        Promise.resolve(
          new Response(
            JSON.stringify(
              String(url).includes("/ingredients/search")
                ? [{ id: "i9", name: "zucchero", display_name: "Zucchero", category: "dolci", kind: "food" }]
                : []
            ),
            { status: 200 }
          )
        )
      )
    );
    renderForm(valuesFromRecipe(DETAIL));

    const offerta = await offri("zucch");
    expect(screen.getByRole("option", { name: /Zucchero/ })).toBeInTheDocument();
    expect(offerta).toBeInTheDocument();
  });
});
```

Run: `npx vitest run src/features/recipe-form/RecipeForm.test.tsx`
Expected: FAIL — il modulo non passa `onCreate`, quindi «Aggiungi «zz tre»» non compare.

- [ ] **Step 5: Il modulo**

In `frontend/src/features/recipe-form/RecipeForm.tsx`:

1. La prima riga degli import diventa:
   ```tsx
   import { useRef, useState, type Dispatch, type SetStateAction } from "react";
   import { flushSync } from "react-dom";
   ```
   e aggiungi, dopo `import { CategoryField } from "./CategoryField";`:
   ```tsx
   import { NewIngredientFields } from "../stocking/NewIngredientFields";
   ```
   Nell'import da `./formModel` aggiungi `addNewLine,` come prima voce dell'elenco.

   `RecipeForm` non sta dentro un `<form>` (né in `AiDraftScreen`, né in `RecipeEditScreen`): `NewIngredientFields` è un `<form>` suo, e dentro un altro `<form>` il browser lo scarterebbe. Controllalo sul ramo: `grep -n "<form" src/features/ai-draft/AiDraftScreen.tsx src/features/recipe-form/*.tsx` deve essere vuoto; se non lo è, fermati e segna il task `bloccato` (un piano precedente ha cambiato la forma della schermata).
2. In `LineRow`, nell'`<input aria-label={`Quantità per ${line.label}`} …>`, aggiungi l'attributo `data-line-key={line.key}` (serve a ritrovare il campo per dargli il fuoco).
3. In `RecipeForm`, dopo la riga `const problem = validationProblem(values);`, aggiungi:
   ```tsx
     // R12: il nome che il selettore ha consegnato con «Aggiungi «…»», mentre il passo
     // «Come si chiama in generale?» è aperto; `null` a passo chiuso
     const [creating, setCreating] = useState<string | null>(null);
     const pickerRef = useRef<HTMLDivElement>(null);
     const linesRef = useRef<HTMLUListElement>(null);
   ```
4. Dopo la funzione `attach`, aggiungi:
   ```tsx
     function addNew(fields: { name: string; category: string }) {
       const added = addNewLine(values.lines, fields.name, fields.category);
       // `flushSync`: la riga deve essere in pagina prima di darle il fuoco, e il passo
       // che l'aveva sparisce nello stesso momento — senza, il fuoco cadrebbe sul `body`
       flushSync(() => {
         onChange({ ...values, lines: added.lines });
         setCreating(null);
       });
       linesRef.current
         ?.querySelectorAll<HTMLInputElement>("input[data-line-key]")
         .forEach((input) => {
           if (input.dataset.lineKey === added.key) input.focus();
         });
     }

     function cancelNew() {
       setCreating(null);
       // il passo sparisce col suo «Annulla»: il fuoco torna al campo da cui si era partiti
       pickerRef.current?.querySelector<HTMLInputElement>("input")?.focus();
     }
   ```
5. Sostituisci `<ul className="divide-y divide-line">` con `<ul ref={linesRef} className="divide-y divide-line">`.
6. Sostituisci il blocco `<IngredientPicker label="Aggiungi un ingrediente" … onPick={attach} />` con:
   ```tsx
           <div ref={pickerRef}>
             <IngredientPicker
               label="Aggiungi un ingrediente"
               failureNote="Puoi salvare la ricetta comunque, anche senza ingredienti agganciati."
               kind="food"
               onPick={attach}
               // R12: «Aggiungi «…»» appena la ricerca ha risposto, anche se trova qualcosa —
               // la scelta di «Sistema la spesa» (S6): «zucch» pesca «Zucchero», e la porta
               // per «zucchine» non deve sparire dietro di lui
               createWhen="always"
               onCreate={setCreating}
             />
           </div>

           {/* Il passo di R12: il nome generico e il reparto, solo del cibo. L'ingrediente
               non nasce qui: nasce salvando la ricetta (`_resolve_lines`), per questo il
               pulsante dice «Aggiungi alla ricetta» e non «Crea l'ingrediente». `key`: un
               secondo «Aggiungi «…»» riparte dal suo nome */}
           {creating !== null && (
             <div className="mt-2 rounded-card bg-card p-3 ring-1 ring-line ring-inset">
               <NewIngredientFields
                 key={creating}
                 initialName={creating}
                 busy={false}
                 foodOnly
                 submitLabel="Aggiungi alla ricetta"
                 onSubmit={addNew}
                 onCancel={cancelNew}
               />
             </div>
           )}
   ```

- [ ] **Step 6: Farli passare, e la suite**

Run: `npx vitest run src/features/recipe-form src/features/ai-draft`
Expected: PASS.
Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: verde; `+9` rispetto al Task 3 (4 del modello, 5 del modulo). Se il lint segnala una regola di `react-hooks` su `addNew` o `cancelNew`, non spegnerla: scrivi la diagnosi nel report e segna il task `bloccato` (i ref si leggono solo nei gestori, mai durante il disegno).
Run (da `<worktree>/backend`): `PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q`
Expected: verde, `N_pytest + 2`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/recipe-form/formModel.ts frontend/src/features/recipe-form/formModel.test.ts \
  frontend/src/features/recipe-form/RecipeForm.tsx frontend/src/features/recipe-form/RecipeForm.test.tsx \
  backend/tests/api/test_recipes_edit.py
git commit -m "ricette: R12, dal modulo si aggiunge un ingrediente che non c'è — nasce salvando, e lo stesso nome non si duplica"
```

---

### Task 5: «Proponi» secondario, e il guasto dell'AI ambra

**Files:**
- Modify: `frontend/src/features/ai-draft/AiDraftScreen.tsx`
- Test: `frontend/src/features/ai-draft/AiDraftScreen.test.tsx`

**Interfaces:**
- Consumes: `Button` (`busy`, `unavailableReason`, `icon`), `IconSparkles`, `Alert tone="degraded"` (Task 1).

Leggi prima `AiDraftScreen.tsx` com'è sul ramo: il Piano 3 ne ha cambiato `onSaved` (l'avviso «Salvata.»). Qui cambiano solo il pulsante «Proponi» e il messaggio del guasto.

- [ ] **Step 1: I test che falliscono**

In fondo al `describe("AiDraftScreen", …)` di `frontend/src/features/ai-draft/AiDraftScreen.test.tsx` aggiungi:

```tsx
  it("«Proponi» è un pulsante secondario, e a richiesta troppo corta dice perché senza partire", async () => {
    const spy = vi.fn();
    vi.stubGlobal("fetch", spy);
    renderScreen();

    const proponi = screen.getByRole("button", { name: "Proponi" });
    // «Salva» è il solo primario della vista (spec T3 §4.7)
    expect(proponi).not.toHaveClass("bg-brand");
    expect(saveButton()).toHaveClass("bg-brand");
    expect(proponi).toHaveAttribute("aria-disabled", "true");
    expect(proponi).toHaveAccessibleDescription("Scrivi cosa vuoi cucinare: bastano tre lettere.");

    await userEvent.click(proponi);
    expect(spy).not.toHaveBeenCalled();

    await userEvent.type(screen.getByLabelText("Cosa vuoi cucinare"), "zuppa");
    expect(proponi).not.toHaveAttribute("aria-disabled");
  });

  it("il guasto dell'AI ha l'ambra di «funziona, ma non del tutto», non il rosso degli errori", async () => {
    vi.stubGlobal("fetch", aiDown());
    renderScreen();
    await proposeDraft();

    const avviso = await screen.findByRole("alert");
    expect(avviso).toHaveTextContent(/La stesura AI non è disponibile/);
    expect(avviso).toHaveClass("text-low");
    expect(avviso).not.toHaveClass("text-danger");
  });
```

Run: `npx vitest run src/features/ai-draft/AiDraftScreen.test.tsx`
Expected: il primo FAIL («Proponi» è `bg-brand` e `disabled`, senza descrizione); il secondo PASS già oggi — la stesura usava l'ambra a mano — e da qui in poi fissa che il colore resti quello, ora che viene da `Alert tone="degraded"`.

- [ ] **Step 2: Il codice**

In `frontend/src/features/ai-draft/AiDraftScreen.tsx`:

1. Aggiungi gli import (accanto a quelli che ci sono):
   ```tsx
   import { Alert } from "../../components/ui/Alert";
   import { Button } from "../../components/ui/Button";
   import { IconSparkles } from "../../components/ui/icons";
   ```
2. Sostituisci il `<button type="button" onClick={() => propose.mutate()} disabled={prompt.trim().length < 3 || propose.isPending} className={buttonClasses("primary", "block")}>` con il suo contenuto (`{propose.isPending ? "Propongo…" : "Proponi"}`) e la sua chiusura con:
   ```tsx
           {/* secondario: il primario della vista è «Salva» (spec T3 §4.7). Da solo, quindi
               icona e testo (spec §2); «non ancora» col perché sotto, `busy` in volo */}
           <Button
             variant="secondary"
             shape="block"
             icon={IconSparkles}
             onClick={() => propose.mutate()}
             busy={propose.isPending}
             unavailableReason={
               prompt.trim().length < 3 ? "Scrivi cosa vuoi cucinare: bastano tre lettere." : undefined
             }
           >
             {propose.isPending ? "Propongo…" : "Proponi"}
           </Button>
   ```
3. Sostituisci il blocco del guasto:
   ```tsx
           {propose.isError && (
             <p role="alert" className="text-sm text-low">
               La stesura AI non è disponibile. Il modulo qui sotto resta tuo: scrivi la ricetta a
               mano e salvala.
             </p>
           )}
   ```
   con:
   ```tsx
           {/* il guasto dell'AI ha un colore solo in tutta l'app (spec T3 §4.7): l'ambra di
               `Alert tone="degraded"`, lo stesso della coda d'import */}
           {propose.isError && (
             <Alert tone="degraded">
               La stesura AI non è disponibile. Il modulo qui sotto resta tuo: scrivi la ricetta a
               mano e salvala.
             </Alert>
           )}
   ```
4. Se `buttonClasses` non ha più usi nel file (`grep -n buttonClasses src/features/ai-draft/AiDraftScreen.tsx`), togline l'import.

- [ ] **Step 3: Farli passare, e la suite**

Run: `npx vitest run src/features/ai-draft`
Expected: PASS, compresi i test di oggi che premono «Proponi» dopo aver scritto la richiesta.
Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: verde; `+2` rispetto al Task 4.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/ai-draft/AiDraftScreen.tsx frontend/src/features/ai-draft/AiDraftScreen.test.tsx
git commit -m "ricette: «Proponi» secondario con l'icona, e il guasto dell'AI in ambra come nella coda"
```

---

### Task 6: La coda d'import — l'AI senza rosso e senza variabili, «Forse» della misura del resto, l'annullamento nell'avviso, «ad»

**Files:**
- Modify: `frontend/src/features/recipe-import/ImportQueueScreen.tsx`
- Modify (riscritto): `frontend/src/features/recipe-import/TermCard.tsx`
- Modify (riscritto): `frontend/src/features/recipe-import/DecidedTermRow.tsx`
- Test: `frontend/src/features/recipe-import/ImportQueueScreen.test.tsx`, `frontend/src/features/recipe-import/DecidedTermRow.test.tsx`

**Interfaces:**
- Consumes: `Button` (`busy`, `unavailableReason`, `accessibleName`), `Alert tone="degraded"`, `Checkbox`, `CategorySelect`, `withPrepositionA` (Task 1), `useNotice`.

La Preparazione ha verificato che `frontend/src/features/recipe-import/` è sul ramo come su `master`: `TermCard.tsx` e `DecidedTermRow.tsx` si sostituiscono interi.

- [ ] **Step 1: I test che falliscono**

In `frontend/src/features/recipe-import/ImportQueueScreen.test.tsx`:

1. Aggiungi l'import `import { NoticeProvider } from "../../components/ui/NoticeProvider";` e in `renderScreen` metti la schermata dentro l'avviso unico, come in `App.tsx` (è dove va a finire l'esito dell'annullamento):
   ```tsx
         <MemoryRouter initialEntries={[path]}>
           <NoticeProvider>
             <ImportQueueScreen />
           </NoticeProvider>
         </MemoryRouter>
   ```
2. Nel test «i controlli di ogni scheda portano il termine nel nome accessibile» sostituisci:
   ```tsx
       expect(
         screen.getByRole("combobox", { name: /Categoria per «Rigatoni»/i })
       ).toBeInTheDocument();
   ```
   con:
   ```tsx
       const reparto = screen.getByRole("combobox", { name: /Reparto per «Rigatoni»/i });
       expect(reparto).toBeInTheDocument();
       // la coda decide i termini delle ricette: niente reparti non alimentari
       expect(within(reparto).queryByRole("option", { name: "Casa" })).toBeNull();
   ```
3. Il test «un 503 dell'AI lo dice col messaggio del backend, e la coda resta usabile a mano» diventa (migrazione: il testo è riscritto nel frontend, decisione 4; la prova del ramo sul 503 resta, ed è più stretta):
   ```tsx
     it("un 503 dell'AI lo dice con parole sue, senza il nome della variabile, e la coda resta usabile a mano", async () => {
       // Mai un vicolo cieco: il modello irraggiungibile non deve impedire di decidere a
       // mano. Il `detail` è quello vero del backend, col nome della variabile: a video
       // non deve arrivare (dal giro di T3). Il testo del 503 (non quello generico) è la
       // prova che il ramo sullo status è ancora lì.
       renderQueue({
         askAiResult: [
           {
             detail:
               "il riconoscimento non è disponibile (OPENROUTER_API_KEY non configurata): decidi a mano, la coda funziona.",
           },
           503,
         ],
       });

       await userEvent.click(await screen.findByRole("button", { name: /Riprova con l'AI/i }));

       expect(
         await screen.findByText("L'AI non è disponibile: decidi a mano qui sotto, la coda funziona.")
       ).toBeInTheDocument();
       expect(screen.queryByText(/OPENROUTER_API_KEY/)).not.toBeInTheDocument();
       expect(screen.queryByText(/Non sono riuscito a chiedere all'AI/i)).not.toBeInTheDocument();
       // i controlli a mano restano lì, invariati dal fallimento dell'AI
       expect(screen.getByRole("button", { name: /Forse «pasta»/i })).toBeEnabled();
     });
   ```
4. Aggiungi in fondo al `describe("coda di revisione dell'import", …)`:
   ```tsx
     it("il guasto dell'AI è ambra, come nella stesura, e non rosso", async () => {
       renderQueue({ askAiResult: [{ detail: "giù" }, 503] });

       await userEvent.click(await screen.findByRole("button", { name: /Riprova con l'AI/i }));

       const avviso = await screen.findByText(/L'AI non è disponibile/);
       expect(avviso).toHaveAttribute("role", "alert");
       expect(avviso).toHaveClass("text-low");
       expect(avviso).not.toHaveClass("text-danger");
     });

     it("a coda svuotata il guasto dell'AI non si mostra più: non c'è niente da chiederle", async () => {
       let inCoda: ImportTerm[] = [TERMINI[1]];
       stubFetch((path, method) => {
         if (path.includes("/imports/terms/decide") && method === "POST") return [{ detail: "giù" }, 503];
         if (path.includes("/decision") && method === "POST") {
           inCoda = [];
           return [{ unlocked: 0, remaining_terms: 0 }, 200];
         }
         if (path.includes("decided_by=")) return [[], 200];
         if (path.includes("/imports/terms")) return [inCoda, 200];
         if (path.includes("/imports/status")) return [STATO_NORMALE, 200];
         return [{}, 404];
       });
       renderScreen();

       await userEvent.click(await screen.findByRole("button", { name: /Riprova con l'AI/i }));
       expect(await screen.findByText(/L'AI non è disponibile/)).toBeInTheDocument();

       await userEvent.click(screen.getByRole("button", { name: /^Ignora «Acqua»$/ }));

       expect(await screen.findByText(/Niente da abbinare/)).toBeInTheDocument();
       expect(screen.queryByText(/L'AI non è disponibile/)).not.toBeInTheDocument();
     });

     it("l'esito di un annullamento passa dall'avviso unico, non da una riga della pagina", async () => {
       renderQueue({
         pending: [],
         decided: [
           {
             id: "t9", display_name: "Rigatoni", occurrences: 3, suggestion: null,
             waiting_titles: [], decided_by: "ai", decided_action: "map",
             decided_name: "pasta", decided_at: "2026-09-20T10:00:00Z",
           },
         ],
         undoStatus: 200,
       });

       await userEvent.click(
         await screen.findByRole("button", { name: /annulla la decisione su «Rigatoni»/i })
       );

       const esito = await screen.findByText("Nessuna ricetta è tornata in coda.");
       expect(esito.closest('[role="status"]')).not.toBeNull();
     });

     it("il suggerimento testuale non è più grande del resto della scheda", async () => {
       renderQueue();

       const forse = await screen.findByRole("button", { name: /Forse «pasta»/i });
       // era un `block` in `text-base` a tutta larghezza: il pulsante più grosso della
       // scheda anche quando la somiglianza è assurda («Aragosta» → «lonza di maiale»)
       expect(forse).toHaveClass("text-sm");
       expect(forse).not.toHaveClass("text-base");
       expect(forse).not.toHaveClass("w-full");
     });

     it("una scorciatoia certa verso un nome che comincia per «a» dice «Collega ad …»", async () => {
       renderQueue({
         pending: [
           {
             ...TERMINI[0], id: "t4", display_name: "Aglio rosso",
             suggestion: { ingredient_id: "i4", name: "aglio", certain: true },
           },
         ],
       });

       expect(await screen.findByRole("button", { name: "Collega ad aglio" })).toBeInTheDocument();
     });

     it("«Crea e collega» senza nome non decide, e dice perché sotto di sé", async () => {
       const spy = renderQueue();

       await userEvent.click(
         await screen.findByRole("button", { name: /Crea un ingrediente nuovo per «Acqua»/i })
       );
       await userEvent.clear(screen.getByRole("textbox", { name: /Nome dell'ingrediente per «Acqua»/i }));
       const crea = screen.getByRole("button", { name: "Crea e collega" });
       expect(crea).toHaveAttribute("aria-disabled", "true");
       expect(crea).toHaveAccessibleDescription("Scrivi il nome per crearlo.");

       await userEvent.click(crea);
       expect(spy.mock.calls.some(([url]) => String(url).includes("/decision"))).toBe(false);
     });
   ```

In `frontend/src/features/recipe-import/DecidedTermRow.test.tsx`:

1. Il test «mentre una decisione è in corso il pulsante è disabilitato» diventa (migrazione: `disabled` → `busy`, con la prova che il tocco non fa niente):
   ```tsx
     it("mentre una decisione è in corso il pulsante si spegne tenendo il fuoco, e il tocco non annulla", async () => {
       const onUndo = vi.fn();
       render(<DecidedTermRow term={term()} pending={true} onUndo={onUndo} />);
       const annulla = screen.getByRole("button", { name: /annulla la decisione su «Rigatoni»/i });
       expect(annulla).toHaveAttribute("aria-disabled", "true");
       expect(annulla).not.toBeDisabled();
       await userEvent.click(annulla);
       expect(onUndo).not.toHaveBeenCalled();
     });
   ```
2. Aggiungi:
   ```tsx
     it("davanti a un nome che comincia per «a» dice «ad»: «collegato ad astice»", () => {
       render(
         <DecidedTermRow
           term={term({ display_name: "Astice blu", decided_name: "astice", created_ingredient: false })}
           pending={false}
           onUndo={vi.fn()}
         />
       );
       expect(screen.getByText("collegato ad astice")).toBeInTheDocument();
     });
   ```

Run: `npx vitest run src/features/recipe-import`
Expected: FAIL — il 503 mostra il `detail` del backend, il guasto è rosso e resta a coda vuota, l'esito dell'annullamento è una riga della pagina, «Forse» è `text-base w-full`, «Collega a aglio», «Crea e collega» è `disabled`, il pulsante di `DecidedTermRow` è `disabled`, «collegato a astice».

- [ ] **Step 2: `DecidedTermRow.tsx`**

Sostituisci tutto il file con:

```tsx
import { Button } from "../../components/ui/Button";
import type { ImportTerm } from "../../domain/types";
import { withPrepositionA } from "../../lib/text";

/** Chi ha deciso, in una parola: «AI» o «tu».
 *
 * Le decisioni dell'AI e quelle a mano stanno nello stesso elenco (R11), e sbagliano
 * per motivi diversi: senza l'etichetta, un collegamento sbagliato fatto a mano si
 * leggerebbe come un errore del modello. La parola visibile è corta per stare sulla
 * riga di un telefono; chi ascolta sente la frase intera, perché «tu» da solo, letto
 * accanto al nome del termine, non dice niente.
 */
function DecidedByLabel({ decidedBy }: { decidedBy: string | null }) {
  const human = decidedBy === "human";
  return (
    <>
      <span
        data-testid="decided-by"
        aria-hidden="true"
        className="shrink-0 rounded-full border border-line bg-card px-2 py-0.5 text-xs font-medium text-ink-soft"
      >
        {human ? "tu" : "AI"}
      </span>
      <span className="sr-only">{human ? "deciso da te" : "deciso dall'AI"}</span>
    </>
  );
}

/** Cosa è stato fatto di questo termine, in una frase.
 *
 * «Rigatoni → pasta» e non «mappato con successo»: il nome dell'ingrediente è la sola
 * informazione su cui si può giudicare se la decisione è giusta, e nasconderla dietro
 * un verbo tecnico renderebbe la revisione una lista di caselle da spuntare.
 *
 * Un termine accorpato dal collasso non ha niente di speciale: è un aggancio, e si
 * mostra come un aggancio, perché è quello che è.
 */
function decisionSummary(term: ImportTerm): string {
  if (term.decided_action === "ignored") return "ignorato: non si tiene in dispensa";
  // «creato dall'import» e non «creato»: il `true` può essere passato a questo termine da
  // quello che l'ha creato davvero, poi annullato, e la frase deve restare vera anche lì.
  // Le decisioni di prima non lo sanno, e «collegato» non promette niente in più.
  if (term.created_ingredient === true)
    return `creato dall'import: ${term.decided_name ?? "un ingrediente"}`;
  // «ad astice», non «a astice» (dal giro di T3): la preposizione la sceglie il nome
  return `collegato ${withPrepositionA(term.decided_name ?? "un ingrediente")}`;
}

export function DecidedTermRow({
  term,
  pending,
  onUndo,
}: {
  term: ImportTerm;
  pending: boolean;
  onUndo: () => void;
}) {
  return (
    <li className="flex items-center justify-between gap-3 border-b border-line py-3 last:border-b-0">
      <div className="min-w-0">
        <div className="flex min-w-0 items-center gap-2">
          <p className="truncate font-medium">{term.display_name}</p>
          <DecidedByLabel decidedBy={term.decided_by} />
        </div>
        <p className="truncate text-xs text-ink-soft">{decisionSummary(term)}</p>
      </div>
      {/* il nome accessibile porta il termine: una riga per termine, e senza il nome chi
          ascolta sente N pulsanti «Annulla» indistinguibili. `busy` e non `disabled`:
          mentre un annullamento è in volo il fuoco resta qui */}
      <Button
        variant="ghost"
        busy={pending}
        onClick={onUndo}
        accessibleName={`Annulla la decisione su «${term.display_name}»`}
      >
        Annulla
      </Button>
    </li>
  );
}
```

- [ ] **Step 3: `TermCard.tsx`**

Sostituisci tutto il file con:

```tsx
import { useState } from "react";
import { CategorySelect } from "../../components/CategorySelect";
import { IngredientPicker } from "../../components/IngredientPicker";
import { Button } from "../../components/ui/Button";
import { Card } from "../../components/ui/Card";
import { Checkbox } from "../../components/ui/Checkbox";
import type { ImportTerm } from "../../domain/types";
import { withPrepositionA } from "../../lib/text";

export type Decision = {
  action: "map" | "create" | "ignore";
  ingredient_id?: string;
  name?: string;
  display_name?: string;
  category?: string;
  role_override?: "primary" | "secondary";
};

export function TermCard({
  term,
  suggestionName,
  pending,
  onDecide,
}: {
  term: ImportTerm;
  /** Il nome dell'aggancio testuale: è la proposta di riserva, e c'è anche senza AI. */
  suggestionName: string | null;
  pending: boolean;
  onDecide: (decision: Decision) => void;
}) {
  const [alsoSecondary, setAlsoSecondary] = useState(false);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState(term.display_name.toLowerCase());
  const [newCategory, setNewCategory] = useState<string>("altro");

  const role = alsoSecondary ? ("secondary" as const) : undefined;

  // l'aggancio testuale, che è sempre meglio di nessun pulsante: un termine senza
  // scorciatoia costa tre tocchi. Non ci sono più proposte dell'AI da confermare
  // qui: quelle si rivedono, già applicate, dall'elenco «Decisioni recenti».
  const shortcut: { ingredient_id: string; name: string } | null =
    suggestionName !== null && term.suggestion !== null
      ? { ingredient_id: term.suggestion.ingredient_id, name: suggestionName }
      : null;

  // L'aggancio testuale eredita `certain` da `match_name`
  // (backend/app/services/ingredient_match.py): certo è una coincidenza esatta su
  // nome o alias, un fatto che non ha bisogno di conferma; incerto è il risultato
  // migliore di una ricerca per somiglianza, un'ipotesi come tante altre. Questo è
  // il difetto critico: "Pinoli" diventava alias permanente di "pisello" con un
  // tocco sul pulsante primario, perché qui `certain` non veniva mai letto.
  const shortcutIsCertain = shortcut !== null && term.suggestion?.certain === true;

  // In volo ogni pulsante della scheda è `busy` e non `disabled`: il fuoco resta dov'è
  // (regola di T3). «Crea e collega» senza nome è «non ancora», col perché sotto.
  return (
    <Card as="li" className="flex flex-col gap-3">
      <div>
        <p className="font-medium">{term.display_name}</p>
        <p className="text-xs text-ink-faint">
          {term.occurrences === 1 ? "1 ricetta in attesa" : `${term.occurrences} ricette in attesa`}
        </p>
        {term.waiting_titles.length > 0 && (
          // i titoli non sono decorazione: «Scorza di limone» si giudica
          // diversamente in una torta e in un arrosto
          <p className="pt-1 text-xs text-ink-soft">{term.waiting_titles.join(" · ")}</p>
        )}
      </div>

      {shortcut && shortcutIsCertain && (
        <Button
          variant="primary"
          shape="block"
          busy={pending}
          onClick={() =>
            onDecide({ action: "map", ingredient_id: shortcut.ingredient_id, role_override: role })
          }
        >
          {`Collega ${withPrepositionA(shortcut.name)}`}
        </Button>
      )}

      {/* il nome accessibile porta il termine: la schermata mette una scheda per
          ogni termine in attesa, e senza il nome qui dentro uno screen reader
          sente N controlli identici — "Collega a un altro ingrediente" non dice a
          chi lo ascolta quale dei tanti termini stia per agganciare */}
      <IngredientPicker
        label="Collega a un altro ingrediente"
        accessibleLabel={`Collega «${term.display_name}» a un altro ingrediente`}
        failureNote="Puoi crearne uno nuovo qui sotto, o ignorare il termine."
        disabled={pending}
        kind="food"
        onPick={(ingredient) =>
          onDecide({ action: "map", ingredient_id: ingredient.id, role_override: role })
        }
      />

      {!creating ? (
        <Button
          shape="block"
          busy={pending}
          onClick={() => setCreating(true)}
          accessibleName={`Crea un ingrediente nuovo per «${term.display_name}»`}
        >
          Crea un ingrediente nuovo
        </Button>
      ) : (
        <div className="flex flex-col gap-2">
          <label className="text-sm font-medium text-ink-soft">
            Nome dell'ingrediente
            <input
              aria-label={`Nome dell'ingrediente per «${term.display_name}»`}
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              className="mt-1.5"
            />
          </label>
          {/* solo i reparti del cibo: il termine viene da una ricetta, e una ricetta non
              può nominare un non alimentare */}
          <CategorySelect
            value={newCategory}
            onChange={setNewCategory}
            foodOnly
            accessibleLabel={`Reparto per «${term.display_name}»`}
          />
          <Button
            variant="primary"
            shape="block"
            busy={pending}
            unavailableReason={newName.trim() === "" ? "Scrivi il nome per crearlo." : undefined}
            onClick={() =>
              onDecide({
                action: "create", name: newName.trim().toLowerCase(),
                display_name: term.display_name, category: newCategory,
                role_override: role,
              })
            }
          >
            Crea e collega
          </Button>
        </div>
      )}

      {/* l'aggancio testuale incerto: una somiglianza di nome, non un fatto verificato
          (vedi `shortcutIsCertain` sopra). Sta sotto ai controlli a mano, e ha la misura
          del resto della scheda — un `ghost` in `text-sm`, non a tutta larghezza (dal
          giro: «è enorme anche quando è assurdo», «Aragosta» → «lonza di maiale»). Non lo
          togliamo — un termine senza scorciatoia costa tre tocchi — lo retrocediamo. */}
      {shortcut && !shortcutIsCertain && (
        <div className="flex flex-col items-start gap-1">
          <Button
            variant="ghost"
            busy={pending}
            onClick={() =>
              onDecide({ action: "map", ingredient_id: shortcut.ingredient_id, role_override: role })
            }
          >
            {`Forse «${shortcut.name}» — tocca per confermare`}
          </Button>
          <p className="text-xs text-ink-faint">
            È solo una somiglianza tra i nomi: verificala prima di confermarla, oppure scegli
            un altro ingrediente con i controlli qui sopra.
          </p>
        </div>
      )}

      {/* la correzione dell'aglio: un tocco in più, solo per le eccezioni. Il nome
          accessibile porta il termine per lo stesso motivo del picker qui sopra: una
          scheda per termine. Il bersaglio è il quadrato da 44 px di `Checkbox` */}
      <label className="flex min-h-11 items-center gap-1 text-sm text-ink-soft">
        <Checkbox
          aria-label={`Di solito «${term.display_name}» è un ingrediente secondario`}
          checked={alsoSecondary}
          onChange={(e) => setAlsoSecondary(e.target.checked)}
        />
        Di solito è secondario
      </label>

      {/* sempre presente: è la via d'uscita che non lascia mai un termine senza
          decisione possibile. Quando la scorciatoia sopra è già certa questo resta
          comunque un pulsante distinto, perché la scorciatoia certa collega, non
          ignora: non c'è mai un doppione con lo stesso testo in scheda */}
      <Button
        variant="ghost"
        shape="block"
        busy={pending}
        onClick={() => onDecide({ action: "ignore" })}
      >
        {`Ignora «${term.display_name}»`}
      </Button>
    </Card>
  );
}
```

- [ ] **Step 4: `ImportQueueScreen.tsx`**

1. Negli import togli `import { buttonClasses } from "../../components/ui/buttonClasses";` e aggiungi:
   ```tsx
   import { Button } from "../../components/ui/Button";
   import { useNotice } from "../../components/ui/noticeContext";
   ```
2. Subito dopo la funzione `aiRunMessage`, aggiungi:
   ```tsx
   /** Cosa dire quando chiedere all'AI non riesce. Il 503 porta nel `detail` il motivo per
    * chi amministra il server — il nome della variabile che manca — che a video era una
    * parola tecnica (dal giro di T3): qui si dice cosa resta possibile, con le parole
    * dell'app. Il `detail` resta nella risposta, e nei log. */
   function aiFailureMessage(error: unknown): string {
     if (error instanceof ApiError && error.status === 503)
       return "L'AI non è disponibile: decidi a mano qui sotto, la coda funziona.";
     return "Non sono riuscito a chiedere all'AI. Decidi a mano: la coda funziona.";
   }
   ```
3. In `ImportQueueScreen`, togli la riga `const [lastUndo, setLastUndo] = useState<UndoSummary | null>(null);` e aggiungi, subito dopo `const queryClient = useQueryClient();`:
   ```tsx
     const notice = useNotice();
   ```
4. In `askAi.onSuccess` togli il commento «un giro nuovo scavalca l'esito di un annullamento precedente…» e la riga `setLastUndo(null);`. In `decide.onSuccess` togli la riga `setLastUndo(null);`.
5. In `undo.onSuccess` sostituisci il blocco `setLastUndo({ … });` (con i suoi commenti su `?? 0` e `?? false`) con:
   ```tsx
         // l'esito passa dall'avviso unico (spec T3 §4.7, dal giro: «Annulla parte senza
         // lapide»): la riga annullata sparisce dall'elenco, e la frase che dice cosa ha
         // disfatto sta dove stanno tutte le conferme. Senza azione: rifare la decisione è
         // decidere di nuovo, dalla scheda del termine appena tornato in coda.
         // `?? 0` e `?? false`: una risposta di un backend di prima di R10 non li porta, e
         // un `undefined` finirebbe scritto nella frase
         notice({
           text: undoResultMessage({
             recipesRequeued: result.recipes_requeued,
             ingredientDeleted: result.ingredient_deleted,
             adoptedUntouched: result.adopted_untouched ?? 0,
             ingredientKeptForAdopted: result.ingredient_kept_for_adopted ?? false,
           }),
         });
   ```
6. Nel JSX togli il blocco:
   ```tsx
         {lastUndo && (
           <p className="pt-2 text-sm font-medium text-brand">{undoResultMessage(lastUndo)}</p>
         )}
   ```
7. Nel ramo d'errore del termine a fuoco sostituisci il `<button type="button" disabled={focus.isFetching} onClick={() => void focus.refetch()} className={buttonClasses("secondary")}>Riprova</button>` con:
   ```tsx
               <Button busy={focus.isFetching} onClick={() => void focus.refetch()}>
                 Riprova
               </Button>
   ```
8. Sostituisci il blocco di «Riprova con l'AI» (`{queue.length > 0 && ( <button … disabled={askAi.isPending} …> … </button> )}`) con:
   ```tsx
         {queue.length > 0 && (
           <Button shape="block" busy={askAi.isPending} onClick={() => askAi.mutate()}>
             {askAi.isPending ? "Sto chiedendo…" : "Riprova con l'AI"}
           </Button>
         )}
   ```
9. Sostituisci il blocco del guasto dell'AI (`{askAi.isError && ( <Alert className="pt-2"> {askAi.error instanceof ApiError && askAi.error.status === 503 ? askAi.error.message : "…"} </Alert> )}`) con:
   ```tsx
         {/* Il guasto dell'AI ha un colore solo in tutta l'app, l'ambra di `degraded`: la
             coda si decide a mano comunque (spec T3 §4.7). E a coda vuota non c'è niente da
             chiedere all'AI, quindi niente da dire: dal giro, il messaggio restava lì dopo
             aver deciso a mano l'ultimo termine */}
         {askAi.isError && queue.length > 0 && (
           <Alert tone="degraded" className="pt-2">
             {aiFailureMessage(askAi.error)}
           </Alert>
         )}
   ```

`UndoSummary` e `undoResultMessage` restano (li usa il punto 5).

- [ ] **Step 5: Farli passare, e la suite**

Run: `npx vitest run src/features/recipe-import`
Expected: PASS — i test nuovi, e quelli di oggi (l'esito dell'annullamento si trova per testo come prima, ora dentro l'avviso; «Forse «pasta»», «Collega a pinolo» col `bg-brand`, «Ignora «Acqua»» invariati).
Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: verde; `+7` rispetto al Task 5 (6 in `ImportQueueScreen.test.tsx`, 1 in `DecidedTermRow.test.tsx`).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/recipe-import/
git commit -m "coda d'import: l'AI assente in ambra e senza variabili, niente a coda vuota; «Forse» della misura del resto; l'annullamento nell'avviso; «ad astice»"
```

---

### Task 7: Le parole e le maiuscole altrove — «il server», «i suggerimenti», «dataset», la Dispensa, il dettaglio

**Files:**
- Modify: `frontend/src/features/stocking/StockingScreen.tsx`; Test: `StockingScreen.test.tsx`
- Modify: `frontend/src/features/shopping-list/AddItemField.tsx`; Test: `AddItemField.test.tsx`
- Modify: `frontend/src/features/pantry/PantryRow.tsx`; Test: `PantryRow.test.tsx`, `PantryScreen.test.tsx`
- Modify: il componente del dettaglio della ricetta che scrive il nome di una riga d'ingrediente (in `frontend/src/features/cooking/`); Test: `RecipeDetailScreen.test.tsx` (o il test di quel componente)
- Verifica (e solo se serve, modifica): `frontend/src/features/recipes/RecipeCard.tsx`

**Interfaces:**
- Consumes: `capitalizeFirst` (Task 1).

Leggi prima `StockingScreen.tsx` (Piano 1) e il dettaglio della ricetta (Piano 3) com'è sul ramo.

- [ ] **Step 1: I test che falliscono**

In `frontend/src/features/stocking/StockingScreen.test.tsx`, subito dopo il test che finisce con `expect(screen.getByRole("button", { name: /Rileggi la spesa/ })).toBeDefined();` (quello del 404 di `/shopping-list/stock`), aggiungi:

```tsx
  it("un guasto del server nel mettere in dispensa lo dice con «server», non con «backend»", async () => {
    stubRoutedFetch((path) =>
      path.includes("/shopping-list/stock") ? [{ detail: "giù" }, 500] : [CHECKED]
    );

    renderScreen();
    await userEvent.click(await screen.findByRole("button", { name: /Sfuso.*mele/i }));
    await userEvent.click(screen.getByRole("button", { name: "Metti in dispensa 1" }));

    const avviso = await screen.findByRole("alert");
    expect(avviso).toHaveTextContent(/è il server che non risponde/);
    expect(avviso.textContent).not.toMatch(/backend/);
  });
```

(se sul ramo il test del 404 usa un nome diverso per il pulsante di «Metti in dispensa», usa quello: è lo stesso pulsante.)

In `frontend/src/features/shopping-list/AddItemField.test.tsx`, nel test «una ricerca che non risponde non blocca il testo libero, e lo dice», sostituisci `expect(await screen.findByText(/autocomplete non risponde/i)).toBeDefined();` con (migrazione del testo riscritto, più stretta):

```tsx
    expect(
      await screen.findByText(
        "I suggerimenti non rispondono. Puoi aggiungere la voce così com'è, e abbinarla dopo in «Sistema la spesa»."
      )
    ).toBeDefined();
    expect(screen.queryByText(/autocomplete/i)).toBeNull();
```

In `frontend/src/features/pantry/PantryRow.test.tsx`:

1. Migrazioni (il nome si legge con la maiuscola): nelle righe `screen.getByRole("link", { name: "yogurt greco" })` (tre, nei primi quattro test) scrivi `"Yogurt greco"`.
2. Aggiungi, dopo il test «il nome di una voce sfusa porta alla scheda dell'ingrediente…»:
   ```tsx
     it("il nome si legge con la maiuscola, e i nomi dei controlli lo tengono com'è dentro la frase", () => {
       renderRow({ product_id: null, product_name: null, product_brand: null });
       expect(screen.getByRole("link", { name: "Yogurt greco" })).toBeDefined();
       expect(screen.getByRole("button", { name: "Togli yogurt greco dalla dispensa" })).toBeDefined();
     });
   ```

In `frontend/src/features/pantry/PantryScreen.test.tsx`, migra alla maiuscola ogni ricerca **esatta** del nome della riga (link o testo): su `master` sono `findByText("mela")` (due), `getByRole("link", { name: "mela" })` (quattro), `queryByRole("link", { name: "mela" })` (una, un'asserzione d'assenza: va migrata, o passerebbe a vuoto) e `getAllByRole("link", { name: "yogurt greco" })` (una). Trovali con:

```bash
grep -n '"mela"\|"yogurt greco"' src/features/pantry/PantryScreen.test.tsx
```

e cambia solo quelli che cercano il nome della riga (`findByText`, `getByText`, `queryByText`, `getByRole("link"…)`, `queryByRole("link"…)`, `getAllByRole("link"…)`) — `"mela"` → `"Mela"`, `"yogurt greco"` → `"Yogurt greco"`; non i dati di prova (`ingredient_name: "mela"`, `raw_text: "mela"`), non i nomi accessibili dei controlli («Togli mela dalla dispensa»), non i testi dell'avviso («Rimesso in lista: mela»).

Nel test del dettaglio della ricetta (`frontend/src/features/cooking/RecipeDetailScreen.test.tsx` sul ramo, o il file di test del componente che il Piano 3 ha creato per le righe d'ingrediente), aggiungi — con l'apparato che il file usa per rendere il dettaglio di `DETAIL` (su `master`: `stubFetch({})` e `renderScreen()`):

```tsx
  it("il nome di una riga d'ingrediente si legge con la maiuscola, solo a video (T3 Consegna 6b)", async () => {
    stubFetch({});
    renderScreen();
    expect(await screen.findByText("Pomodoro")).toBeInTheDocument();
    expect(screen.queryByText("pomodoro")).toBeNull();
  });
```

e migra alla maiuscola le ricerche esatte del nome di una riga che il file fa già (su `master`: `findByText("pomodoro")`, `findByText("aglio")`, `findByText("basilico")`, `getByText("pasta")`, tutte seguite da `.closest("li")`); il Piano 3 può averle cambiate: `grep -n 'ByText("\(pasta\|pomodoro\|aglio\|basilico\|olio\)")' <file>`.

Run: `npx vitest run src/features/stocking/StockingScreen.test.tsx src/features/shopping-list/AddItemField.test.tsx src/features/pantry src/features/cooking`
Expected: FAIL — «backend», «autocomplete», i nomi in minuscolo.

- [ ] **Step 2: Il codice**

1. `frontend/src/features/stocking/StockingScreen.tsx`, in `stockFailureMessage`: sostituisci
   ```tsx
       "Se insiste, è il backend che non risponde: le conferme restano su questo schermo."
   ```
   con
   ```tsx
       "Se insiste, è il server che non risponde: le conferme restano su questo schermo."
   ```
2. `frontend/src/features/shopping-list/AddItemField.tsx`: sostituisci
   ```tsx
             L'autocomplete non risponde. Puoi aggiungere la voce così com'è: l'ingrediente
             si abbina dopo.
   ```
   con
   ```tsx
             I suggerimenti non rispondono. Puoi aggiungere la voce così com'è, e abbinarla
             dopo in «Sistema la spesa».
   ```
   e nel commento sopra il `<p>` aggiungi in fondo la riga: `«la voce», non «l'ingrediente»: qui è una voce di testo libero, che si abbina dopo (Parte X).`
3. `frontend/src/features/pantry/PantryRow.tsx`: aggiungi `import { capitalizeFirst } from "../../lib/text";` e nel `<Link to={registryPath(item)} …>` sostituisci `{item.ingredient_name}` con `{capitalizeFirst(item.ingredient_name)}`. Aggiungi sopra il `<Link>`, dentro il commento che c'è o in uno nuovo: `la maiuscola solo a video (spec T3 §4.7): i nomi accessibili dei controlli della riga usano \`label\`, in mezzo a una frase, e restano com'è`.
4. Il dettaglio della ricetta: trova dove il nome di una riga d'ingrediente si scrive a video, da solo:
   ```bash
   grep -rn "ingredient_name" src/features/cooking --include=*.tsx | grep -v "\.test\."
   ```
   Nel punto (o nei punti) in cui `line.ingredient_name` (o il nome che il Piano 3 ha dato alla riga) è **testo a video che apre la riga** — non dentro una frase, non in un `aria-label`, non in `CookSheet.tsx` — scrivi `capitalizeFirst(…)`, con l'import `import { capitalizeFirst } from "../../lib/text";`. Nient'altro nel dettaglio.
5. «dataset»: verifica che non si legga più da nessuna parte:
   ```bash
   grep -rn '"dataset"' src --include=*.tsx | grep -v "\.test\."
   ```
   Expected: vuoto (il Piano 2 ha tolto la provenienza dalle righe). Se stampa `RecipeCard.tsx` con `SOURCE_LABEL`, il Piano 2 non l'ha tolta: togli dalla riga lo `<span>` che scrive `{SOURCE_LABEL[recipe.source] ?? recipe.source}` e la costante `SOURCE_LABEL`, migra i test che cercavano «dataset», «AI» o «scritta da te» su quella riga (`grep -rn 'ByText("dataset")\|ByText("AI")\|scritta da te' src/features/recipes`) togliendo solo quelle asserzioni sulla provenienza, e scrivilo nel report.

- [ ] **Step 3: Farli passare, e la suite**

Run: `npx vitest run src/features/stocking src/features/shopping-list src/features/pantry src/features/cooking src/features/recipes`
Expected: PASS.
Run: `npx vitest run && npm run typecheck && npm run lint`
Expected: verde; `+3` rispetto al Task 6.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/features/stocking/StockingScreen.tsx frontend/src/features/stocking/StockingScreen.test.tsx \
  frontend/src/features/shopping-list/AddItemField.tsx frontend/src/features/shopping-list/AddItemField.test.tsx \
  frontend/src/features/pantry/ frontend/src/features/cooking/ frontend/src/features/recipes/
git commit -m "parole: «il server», «i suggerimenti», niente «dataset»; il nome con la maiuscola in Dispensa e nel dettaglio della ricetta"
```

---

### Task 8: L'e2e — il modulo, la coda e le parole nel browser vero, a 375×812

jsdom non calcola il CSS (quarta lezione di `CLAUDE.md`): che il passo di R12 e la riga nuova non facciano scorrere la pagina di lato, che le caselle abbiano davvero un bersaglio da 44 px, che l'avviso dell'AI sia davvero ambra nei due temi e che «Forse» sia davvero a 14 px, lo dice solo un browser. Il seme e2e non ha termini in coda e non ha l'AI: la coda e la bozza si servono con `page.route`, come fa già `ai-draft.spec.ts` — prove che si costruiscono le risposte da sé (prima lezione di `CLAUDE.md`), dette tali nei commenti, valide per schermata, componenti e CSS veri. **Nessuna prova scrive**: nessuna ricetta si salva, nessuna decisione arriva al backend.

**Files:**
- Modify: `frontend/e2e/style.spec.ts` (due aiuti e cinque `test(...)` in fondo, in blocchi propri)

- [ ] **Step 1: I test**

1. In cima a `frontend/e2e/style.spec.ts`, nell'import dei tipi, aggiungi `ImportTerm`:
   ```ts
   import type { ImportTerm, Ingredient, RecipeDraft } from "../src/domain/types.ts";
   ```
2. In fondo al file aggiungi (il `beforeEach` del file ha già fatto l'accesso; `fermo`, `testiIlleggibili`, `contrastoAVideo`, `tokenDelTema`, `tokenDelTemaScuro` e `SCHERMATE` sono già definiti più sopra nel file):

```ts
// --- T3 Consegna 6b: il modulo della ricetta, la coda d'import, le parole ---

/** Una coda d'import finta, servita da `page.route`. Il seme e2e non ha termini in coda,
 * e «Riprova con l'AI» compare solo con la coda piena: come `ai-draft.spec.ts`, questa è
 * una prova che si costruisce le risposte da sé (prima lezione di `CLAUDE.md`), e vale per
 * la schermata, i componenti e il CSS veri, non per quel che il backend manda. Il 503 porta
 * il `detail` vero di `backend/app/api/imports.py`, col nome della variabile: è quello che
 * la schermata non deve mostrare. Una decisione a mano svuota la coda, e non arriva al
 * backend. */
async function codaFinta(page: Page) {
  let inCoda: ImportTerm[] = [
    {
      id: "e2e-t1",
      display_name: "Rigatoni",
      occurrences: 3,
      suggestion: { ingredient_id: "e2e-i1", name: "pasta", certain: false },
      waiting_titles: ["Pasta alla norma"],
      decided_by: null,
      decided_action: null,
      decided_name: null,
      decided_at: null,
    },
  ];
  await page.route("**/api/v1/imports/**", (route) => {
    const richiesta = route.request();
    const url = new URL(richiesta.url());
    if (url.pathname.endsWith("/imports/terms/decide") && richiesta.method() === "POST")
      return route.fulfill({
        status: 503,
        json: {
          detail:
            "il riconoscimento non è disponibile (OPENROUTER_API_KEY non configurata): decidi a mano, la coda funziona.",
        },
      });
    if (url.pathname.endsWith("/decision") && richiesta.method() === "POST") {
      inCoda = [];
      return route.fulfill({ json: { unlocked: 0, remaining_terms: 0 } });
    }
    if (url.pathname.endsWith("/imports/terms"))
      return route.fulfill({ json: url.searchParams.has("decided_by") ? [] : inCoda });
    if (url.pathname.endsWith("/imports/status"))
      return route.fulfill({
        json: {
          fetched: 3,
          pending_recipes: inCoda.length > 0 ? 3 : 0,
          imported: 0,
          skipped: 0,
          pending_terms: inCoda.length,
        },
      });
    return route.continue();
  });
}

/** Una bozza finta con un aggancio incerto: la sola riga del modulo che ha una casella.
 * L'`ingredient_id` non esiste nel seme, e non importa: la prova non salva. */
async function bozzaFinta(page: Page) {
  await page.route("**/api/v1/recipes/ai-draft", (route) =>
    route.fulfill({
      json: {
        title: "Minestra",
        description: null,
        instructions: "Cuoci.",
        servings: 2,
        cost: null,
        ingredients: [
          {
            raw_name: "basilico fresco",
            role: "secondary",
            quantity_text: "q.b.",
            ingredient_id: "00000000-0000-4000-8000-000000000001",
            matched_name: "basilico",
            confident: false,
            proposed_category: null,
          },
        ],
      } satisfies RecipeDraft,
    })
  );
}

test("R12 a 375px: «Aggiungi «…»» nel modulo, il passo del nome e la riga nuova stanno nello schermo", async ({
  page,
}) => {
  // il `beforeEach` tocca «Entra» ma non aspetta la risposta
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  const nomeLungo = "zz prova r12 cavolo nero di Toscana a foglia lunga del mercato rionale";
  const scorre = async () => ({
    scrollWidth: await page.evaluate<number>("document.documentElement.scrollWidth"),
    clientWidth: await page.evaluate<number>("document.documentElement.clientWidth"),
  });

  await page.goto("/ricette/nuova-ai");
  // la ricerca vera non trova il nome: «Aggiungi «…»» compare appena ha risposto
  await page.getByLabel("Aggiungi un ingrediente").fill(nomeLungo);
  await page.getByRole("button", { name: `Aggiungi «${nomeLungo}»` }).click();

  const nome = page.getByLabel("Come si chiama in generale?");
  await expect(nome).toHaveValue(nomeLungo);
  await expect(nome).toBeFocused();
  const reparto = page.getByLabel("Reparto", { exact: true });
  await expect(reparto.locator('option[value="casa"]')).toHaveCount(0);
  await expect(reparto.locator('option[value="igiene"]')).toHaveCount(0);
  let misura = await scorre();
  expect(misura.scrollWidth, "il passo del nome fa scorrere di lato").toBeLessThanOrEqual(
    misura.clientWidth
  );

  await reparto.selectOption("verdura");
  await page.getByRole("button", { name: "Aggiungi alla ricetta", exact: true }).click();

  const togli = page.getByRole("button", { name: `Togli ${nomeLungo}` });
  const riga = page.getByRole("listitem").filter({ has: togli });
  await expect(riga.getByText("Non è in anagrafica: lo creo io salvando.")).toBeVisible();
  await expect(page.getByLabel(`Reparto per «${nomeLungo}»`)).toHaveValue("verdura");
  await expect(page.getByLabel(`Quantità per ${nomeLungo}`)).toBeFocused();
  await page.waitForLoadState("networkidle");
  misura = await scorre();
  expect(misura.scrollWidth, "la riga nuova fa scorrere di lato").toBeLessThanOrEqual(
    misura.clientWidth
  );
  // la ✕ della riga resta intera dentro lo schermo, accanto al nome lungo
  await togli.scrollIntoViewIfNeeded();
  await expect(togli).toBeInViewport({ ratio: 1 });
  // niente si salva: la riga vive nel modulo, e l'ingrediente nascerebbe solo salvando
});

test("le caselle del modulo della ricetta e della coda d'import sono bersagli da 44 px", async ({
  page,
}) => {
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  await bozzaFinta(page);
  await codaFinta(page);

  /** Il quadrato intorno alla casella: almeno 44×44, e un tocco nel suo angolo — fuori dal
   * quadratino da 24 — la spunta. */
  async function bersaglio(casella: Locator) {
    await casella.scrollIntoViewIfNeeded();
    const quadrato = await casella.locator("xpath=..").boundingBox();
    expect(quadrato, "la casella non ha il suo quadrato").not.toBeNull();
    expect(quadrato!.width).toBeGreaterThanOrEqual(44);
    expect(quadrato!.height).toBeGreaterThanOrEqual(44);
    const prima = await casella.isChecked();
    await page.mouse.click(quadrato!.x + 3, quadrato!.y + 3);
    await expect(casella).toBeChecked({ checked: !prima });
  }

  await page.goto("/ricette/nuova-ai");
  await page.getByLabel("Cosa vuoi cucinare").fill("una minestra");
  await page.getByRole("button", { name: "Proponi", exact: true }).click();
  await bersaglio(page.getByRole("checkbox", { name: "Includi basilico fresco" }));

  await page.goto("/ricette/importa");
  await bersaglio(
    page.getByRole("checkbox", { name: "Di solito «Rigatoni» è un ingrediente secondario" })
  );
});

test("la coda d'import: il guasto dell'AI è ambra e senza nomi di variabili, e a coda vuota non c'è", async ({
  page,
}) => {
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  await codaFinta(page);
  await page.goto("/ricette/importa");

  // «Forse «…»» non è più grande del resto della scheda: `text-sm`, 14 px a video. `el`
  // è `any`: questo file non ha la libreria DOM (vedi `testiIlleggibili`)
  const forse = page.getByRole("button", { name: /^Forse «pasta»/ });
  await expect(forse).toBeVisible();
  const corpo = await forse.evaluate(
    (el) => el.ownerDocument.defaultView.getComputedStyle(el).fontSize as string
  );
  expect(corpo).toBe("14px");

  await page.getByRole("button", { name: "Riprova con l'AI", exact: true }).click();
  const guasto = page.getByText(
    "L'AI non è disponibile: decidi a mano qui sotto, la coda funziona.",
    { exact: true }
  );
  await expect(guasto).toBeVisible();
  await expect(page.getByText(/OPENROUTER/)).toHaveCount(0);
  for (const tema of ["light", "dark"] as const) {
    await page.emulateMedia({ colorScheme: tema });
    await fermo(page);
    const misura = await contrastoAVideo(guasto);
    expect(misura.colore, `il guasto dell'AI non è ambra, tema ${tema}`).toBe(
      tema === "light" ? tokenDelTema("low") : tokenDelTemaScuro("low")
    );
  }
  await page.emulateMedia({ colorScheme: "light" });

  // deciso a mano l'ultimo termine, la coda è vuota: niente da chiedere all'AI, niente da dire
  await page.getByRole("button", { name: "Ignora «Rigatoni»", exact: true }).click();
  await expect(page.getByText(/Niente da abbinare/)).toBeVisible();
  await expect(guasto).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Riprova con l'AI" })).toHaveCount(0);
});

test("il modulo della ricetta e la coda d'import si leggono nei due temi, negli stati che solo questa prova apre", async ({
  page,
}) => {
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  await page.setViewportSize({ width: 375, height: 812 });
  await page.route("**/api/v1/recipes/ai-draft", (route) =>
    route.fulfill({
      status: 503,
      json: { detail: "stesura AI non disponibile (OPENROUTER_API_KEY non configurata)" },
    })
  );
  await codaFinta(page);

  async function leggibile(dove: string) {
    for (const tema of ["light", "dark"] as const) {
      await page.emulateMedia({ colorScheme: tema });
      await fermo(page);
      expect(await testiIlleggibili(page), `${dove}, tema ${tema}`).toEqual([]);
    }
    await page.emulateMedia({ colorScheme: "light" });
  }

  // il modulo: i motivi sotto «Proponi» e «Salva», il guasto dell'AI, il passo di R12
  await page.goto("/ricette/nuova-ai");
  await page.getByLabel("Cosa vuoi cucinare").fill("zz");
  await expect(page.getByText("Scrivi cosa vuoi cucinare: bastano tre lettere.")).toBeVisible();
  await page.getByLabel("Cosa vuoi cucinare").fill("una zuppa");
  await page.getByRole("button", { name: "Proponi", exact: true }).click();
  await expect(page.getByText(/La stesura AI non è disponibile/)).toBeVisible();
  await expect(page.getByText("Servono un titolo e un procedimento per salvare.")).toBeVisible();
  await page.getByLabel("Aggiungi un ingrediente").fill("zz prova contrasto");
  await page.getByRole("button", { name: "Aggiungi «zz prova contrasto»" }).click();
  await expect(page.getByLabel("Come si chiama in generale?")).toBeVisible();
  await leggibile("modulo col passo del nome");

  await page.getByRole("button", { name: "Aggiungi alla ricetta", exact: true }).click();
  await expect(page.getByText("Non è in anagrafica: lo creo io salvando.")).toBeVisible();
  await leggibile("modulo con la riga nuova");

  // la coda: la scheda con «Forse» e la casella, e il guasto dell'AI
  await page.goto("/ricette/importa");
  await page.getByRole("button", { name: "Riprova con l'AI", exact: true }).click();
  await expect(page.getByText(/L'AI non è disponibile/)).toBeVisible();
  await leggibile("coda col guasto dell'AI");
});

test("nessuna parola tecnica a video: né «backend», né «dataset», né «autocomplete», né il nome di una variabile", async ({
  page,
}) => {
  await expect(page.getByRole("link", { name: "Dispensa" })).toBeVisible();
  const tecniche = /\bbackend\b|\bdataset\b|autocomplete|OPENROUTER_API_KEY/i;
  for (const luogo of SCHERMATE) {
    await page.goto(luogo);
    await page.waitForLoadState("networkidle");
    expect(await page.locator("body").innerText(), luogo).not.toMatch(tecniche);
  }
  // il dettaglio di una ricetta del seme, che viene dall'import
  await page.goto("/ricette");
  await page.getByRole("link", { name: /Pasta al pomodoro/ }).first().click();
  await page.waitForLoadState("networkidle");
  expect(await page.locator("body").innerText(), "dettaglio").not.toMatch(tecniche);
});
```

Se una delle prove del contrasto segnala un testo di questa consegna sotto 4,5:1, **non cambiare token**: scrivi nel report quale testo, su quale fondo, in quale tema e con quale rapporto, e segna il task `bloccato` — un colore si decide di giorno.

- [ ] **Step 2: Il tipo del file**

Run (da `frontend/`): `npm run typecheck && npm run lint`
Expected: puliti. `tsc -b` compila anche gli e2e (`tsconfig.node.json`, senza la libreria DOM: per questo dentro `evaluate` l'elemento è `any` e si passa da `el.ownerDocument`).

- [ ] **Step 3: Lo stack e2e, e l'e2e intera**

Dalla radice di `<worktree>`, con i comandi delle Global Constraints: `cp .env.example .env`, `up -d --build --wait`, il seme `--con-ricette`, poi `(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)`.
Expected: tutti verdi, **cinque più del conto e2e del Piano 3** (nel suo report della notte; se non lo trovi, conta le prove di `frontend/e2e/` con `npx playwright test --list | tail -n 1` su `night/c5-dettaglio` e aggiungi cinque). Annota il numero (`N_e2e`). Le prove che il piano ha già migrato (`ai-draft.spec.ts` con «Reparto per») passano; `import-review.spec.ts` trova l'esito dell'annullamento per testo nella pagina, ora dentro l'avviso, e «collegato a pasta …» (il suo ingrediente comincia per «p»). Se una prova di altri file fallisce **solo** perché cerca con `exact: true` il nome di una riga di Dispensa o del dettaglio in minuscolo, migra quella ricerca alla maiuscola (solo il caso della lettera) e scrivilo nel report; ogni altro fallimento si diagnostica, non si migra.

Se una prova fallisce e lascia dati nello stack, prima di rieseguire ricrea lo stack da zero (`down -v`, `up`, seme). Alla fine, sempre:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/
git commit -m "e2e: la Consegna 6b a 375px — R12 senza scorrere di lato, caselle da 44, il guasto dell'AI ambra e assente a coda vuota, i due temi, nessuna parola tecnica"
```

---

### Task 9: I documenti

**Files:**
- Modify: `docs/prossimi-passi.md`
- Modify: `next-steps.md`

Leggi prima i due file com'è sul ramo: i Piani 1–3 li hanno aggiornati (paragrafi delle loro consegne, righe di `next-steps.md`).

- [ ] **Step 1: Il paragrafo della consegna**

In `docs/prossimi-passi.md`, nella voce T3, dopo l'ultimo paragrafo di consegna scritto stanotte dai piani prima di questo (cerca `grep -n "^\*\*Consegna" docs/prossimi-passi.md`: il più in basso fra «Consegna 6a», «Consegna 4», «Consegna 5» e i loro paragrafi «Da provare sul telefono») e **prima** del paragrafo che comincia con «Dei tre punti di disegno del tema scuro», aggiungi:

```markdown
**Consegna 6b (il modulo della ricetta, la coda d'import, le parole) fatta il <data di
oggi>, sul ramo `night/c6b-modulo-coda-parole`, non ancora in produzione. È l'ultima
consegna del ridisegno**: con lei ogni schermata della spec è sulle primitive, e restano le
prove sul telefono e il via di Mattia per le Consegne 4, 5, 6a e 6b. Cosa è cambiato: nel
modulo della ricetta «Salva» è il solo primario, e quando non è ancora pronto dice perché
**sotto** di sé (`unavailableReason`); «Proponi» è secondario, con la sua icona, e con meno
di tre lettere dice perché; le caselle hanno un bersaglio da 44 px (`Checkbox`, anche «Di
solito è secondario» nella coda); «Ingredienti» è un `SectionHeading`; **R12**: il selettore
unico offre «Aggiungi «…»» anche quando trova altro, e ne nasce il passo «Come si chiama in
generale?» con un reparto solo del cibo, poi una riga «lo creo io salvando» col fuoco sulla
sua quantità — l'ingrediente nasce salvando, nessuna modifica al backend, e lo stesso nome
non fa due righe. Un campo «Reparto» solo (`CategorySelect`, con `foodOnly` nel mondo
ricette) per Anagrafica, Sistema la spesa, coda e modulo; «Reparto per «…»» al posto di
«Categoria per «…»», che nel modulo si confondeva con la categoria della ricetta. Il guasto
dell'AI ha un colore solo, l'ambra di «funziona, ma non del tutto» (`Alert tone="degraded"`),
nella stesura e nella coda: il rosso resta a «manca» e «non è andata». Nella coda l'AI
assente dice «L'AI non è disponibile: decidi a mano qui sotto, la coda funziona.», senza il
nome della variabile, e a coda vuota non c'è; «Forse «…»» ha la misura del resto della
scheda; l'esito di un annullamento passa dall'avviso unico. Parole: «il server» al posto di
«backend», «I suggerimenti non rispondono…» al posto dell'autocomplete, niente «dataset»,
«collegato ad astice» e «Collega ad aglio» (`withPrepositionA`); i nomi degli ingredienti
con la maiuscola dove aprono una riga — Dispensa, modulo, dettaglio della ricetta — solo a
video (`capitalizeFirst`, spostato da `Section.tsx`).

**Le scelte del piano che Mattia può voler rivedere:** l'ambra come colore del guasto
dell'AI (e non il grigio di una nota); «Reparto» ovunque al posto di «Categoria» per il
reparto di un ingrediente; il bersaglio da 44 intorno a un quadratino da 24; «Aggiungi alla
ricetta» come pulsante del passo di R12; un nome nuovo uguale a una riga che c'è non ne
aggiunge un'altra ma include quella (e a una riga dell'AI «non in anagrafica» dà il reparto
scelto); l'annullamento nella coda come avviso senza «Annulla»; le maiuscole solo dove un
nome apre una riga, non in Lista né in Sistema la spesa (lì si legge il testo che una
persona ha scritto, com'è) né nel titolo del foglio della cottura.

**Da provare sul telefono:** R12 con la tastiera aperta (il passo del nome, il reparto
nativo, il fuoco che salta alla quantità); il tocco sulle caselle nuove, anche nell'angolo;
la coda con un termine vero e l'AI non configurata; l'avviso dopo un annullamento.
```

Sostituisci `<data di oggi>` con la data vera.

- [ ] **Step 2: R12, e le osservazioni del giro**

1. Il titolo `## R12. Scrivendo una ricetta a mano non si aggiunge un ingrediente che non c'è **[D — trovato da Mattia il 2026-09-28]**` diventa `## R12. Scrivendo una ricetta a mano non si aggiunge un ingrediente che non c'è **[FATTO <data di oggi> — T3 Consegna 6b, non ancora in produzione]**`. In fondo alla voce, dopo la riga in corsivo sulla spec di T3, aggiungi:
   ```markdown
   **Fatto** con la Consegna 6b di T3: nel modulo (scrivere e modificare) il selettore unico
   offre «Aggiungi «…»» appena la ricerca ha risposto, anche quando trova altro
   (`createWhen="always"`, come in Sistema la spesa per S6); il passo «Come si chiama in
   generale?» (`NewIngredientFields`, reparto solo del cibo) mette una riga «lo creo io
   salvando», e l'ingrediente nasce al salvataggio con `_resolve_lines`, nella transazione
   della ricetta, alla creazione e alla modifica — nessuna modifica al backend, due test in
   `test_recipes_edit.py` ne fissano il contratto. Un nome uguale a una riga che c'è la
   include invece di duplicarla. Un nome che al salvataggio risulta un non alimentare torna
   come 422 con la frase, accanto a «Salva», e la riga si toglie con la sua ✕.
   ```
2. Nella sezione del giro (voce T3, «Esito del giro»), segna in fondo alla voce, fra parentesi in corsivo:
   - in «**In tutto il sito**»: «**Ci sono parole tecniche a video**» → *(T3 Consegna 6b; «Cerca in anagrafica» con la 6a)*; «**Maiuscole a caso**» → *(T3 Consegna 6b, per le maiuscole)*; «**Accordi sbagliati**» → *(T3 Consegne 1 e 6b)*; «**Titoli e intestazioni di sezione hanno stili diversi**» → *(«Ingredienti» nel modulo: T3 Consegna 6b)*;
   - in «**Scrivi una ricetta**»: «**«Proponi» e «Salva» sono due pulsanti primari.**», «**Le caselle sono da 20×20.**», «**Lo stesso guasto dell'AI**» → *(T3 Consegna 6b)* ciascuna;
   - in «**Ingredienti da abbinare** (oltre a R11)»: «**Il messaggio dell'AI non configurata**», «**Il suggerimento testuale è enorme anche quando è assurdo**», «**«Annulla» parte senza lapide.**» → *(T3 Consegna 6b)* ciascuna.
3. In Parte X, in fondo alla voce «**«Ingrediente» invece di «voce» in due schermate.**», aggiungi:
   ```markdown
   *(Rivista caso per caso il <data di oggi>, T3 Consegna 6b: cambia la frase della barra
   della Lista quando i suggerimenti non rispondono — «Puoi aggiungere la voce così com'è, e
   abbinarla dopo in «Sistema la spesa».» — dove «l'ingrediente si abbina dopo» parlava della
   voce. Restano «Abbina un ingrediente», «Scegli a quale ingrediente corrisponde», «Crea
   l'ingrediente»: lì si nomina la voce dell'anagrafica, che nell'app si chiama ingrediente
   anche quando è un detersivo; rinominarla è un'altra cosa, non una frase.)*
   ```

- [ ] **Step 3: `next-steps.md`**

1. La riga in testa: `_Ultimo aggiornamento: <data di oggi> (fase notte)_`.
2. Togli la riga della Consegna 6 (`grep -n "Consegna 6" next-steps.md`): se ce n'è una per la 6b, toglila; se c'è ancora la riga unica «Consegna 6, il resto», toglila anche lei — con questa consegna la 6 è finita tutta (la 6a l'ha segnata il Piano 1, se l'ha fatto, in «Fatti»).
3. Togli le idee chiuse qui: quella che comincia con `- [idea] P3 · \`NewIngredientFields\` copia il \`<select>\` del reparto` e quella che comincia con `- [idea] P3 · «Ingrediente» invece di «voce»`.
4. In cima a «Fatti (recenti)» aggiungi:
   ```markdown
   - [fatto] <data di oggi> · T3 Consegna 6b, l'ultima del ridisegno: il modulo della ricetta con «Salva» principale e il motivo sotto, caselle da 44, R12 («Aggiungi «…»» e il passo del nome, l'ingrediente nasce salvando); `CategorySelect` unico; la coda d'import senza rosso né variabili e senza messaggio a coda vuota, «Forse» della misura del resto, l'annullamento nell'avviso; il guasto dell'AI ambra ovunque; «il server», niente «dataset», «ad astice», le maiuscole solo a video [T3, R12, Parte X] → branch night/c6b-modulo-coda-parole (da revisionare)
   - [fatto] <data di oggi> · `CategorySelect` sostituisce i quattro `<select>` del reparto (anche quello copiato da `NewIngredientFields`) [T3] → branch night/c6b-modulo-coda-parole (da revisionare)
   - [fatto] <data di oggi> · «Ingrediente» o «voce», rivisti caso per caso: cambia la frase della barra della Lista [Parte X] → branch night/c6b-modulo-coda-parole (da revisionare)
   ```
5. In cima a «Da fare a mano (solo Mattia)» aggiungi:
   ```markdown
   - [tbd] P1 · Prove sul telefono della Consegna 6b: R12 con la tastiera aperta (il passo del nome, il reparto, il fuoco sulla quantità), il tocco sulle caselle nuove, la coda con un termine vero e l'AI non configurata, l'avviso dopo un annullamento
   ```
6. In «Idee» aggiungi:
   ```markdown
   - [idea] P3 · Annullando una decisione nella coda la riga sparisce e il fuoco cade sulla pagina: portarlo alla scheda del termine tornato in coda [T3 Consegna 6b]
   - [idea] P3 · Il titolo del foglio della cottura, per una confezione senza prodotto, è il nome dell'ingrediente in minuscolo: `capitalizeFirst` come nelle righe [T3 Consegna 6b]
   - [idea] P3 · Lista e Sistema la spesa mostrano il testo della voce com'è stato scritto, anche in minuscolo (di proposito: è il testo di chi l'ha scritto) — da confermare con Mattia [T3 Consegna 6b]
   - [idea] P3 · Nel modulo, un nome nuovo che coincide con un non alimentare dell'anagrafica si scopre solo salvando (422 con la frase): il selettore cerca solo cibo, quindi non lo mostra prima [T3 Consegna 6b, R12]
   - [idea] P3 · La casella della Lista (`ListRow.tsx`) è ancora un quadratino da 20 px: `Checkbox` è pronta [T3 Consegna 6b]
   ```
7. Se nella notte sono emerse altre cose da fare fuori da questo piano, aggiungile come `idea` o `tbd` nella sezione giusta, con la voce di `docs/prossimi-passi.md` fra parentesi quadre.

- [ ] **Step 4: Commit**

```bash
git add docs/prossimi-passi.md next-steps.md
git commit -m "docs: T3 Consegna 6b, l'ultima del ridisegno; R12 fatto, e le parole di Parte X riviste"
```

---

### Task 10: La verifica finale

Niente di nuovo da scrivere: si prova tutto, dal worktree, com'è sul ramo.

- [ ] **Step 1: Il frontend**

Da `<worktree>/frontend`:

```bash
npx vitest run
npm run typecheck
npx tsc -b --force
npm run lint
npm run build
```

Expected: vitest tutto verde — **`N_vitest` della Preparazione più 46**, cioè 20 (Task 1) + 2 (Task 2) + 3 (Task 3) + 9 (Task 4) + 2 (Task 5) + 7 (Task 6) + 3 (Task 7), in **`N_file` + 4** file (`text.test.ts`, `Alert.test.tsx`, `Checkbox.test.tsx`, `CategorySelect.test.tsx`); se il numero differisce, scrivi nel report da dove viene la differenza. Typecheck, lint e build puliti. `npx tsc -b --force` perché `node_modules` è condiviso col checkout principale, e con lui il `tsbuildinfo`: `--force` compila davvero tutto.

- [ ] **Step 2: Il backend**

Da `<worktree>/backend`:

```bash
PATH="/home/mactyws/coding/ais/spena/backend/.venv/bin:$PATH" python -m pytest -q
```

Expected: tutto verde, **`N_pytest` + 2**. `git diff night/c5-dettaglio -- backend/app` vuoto: nessuna riga del codice del backend è cambiata.

- [ ] **Step 3: I grep**

Dalla radice del worktree:

```bash
grep -rn "emerald\|neutral-" frontend/src
grep -rn "Il backend ha rifiutato\|è il backend che\|L'autocomplete\|Categoria per «" frontend/src frontend/e2e
grep -rn '"dataset"' frontend/src --include=*.tsx | grep -v "\.test\."
grep -rln "domain/categories" frontend/src | sort
git diff night/c5-dettaglio -- backend/app
```

Expected: vuoto, vuoto, vuoto; poi solo `frontend/src/components/CategorySelect.tsx` e `frontend/src/components/ui/departments.test.ts`; poi vuoto.

- [ ] **Step 4: L'e2e intera**

Con i comandi delle Global Constraints, su uno stack ricreato da zero (`down -v` prima dell'`up`, se ne era rimasto uno di questo ramo). Expected: tutti verdi, `N_e2e` del Task 8. Poi `down -v` e `rm .env`, sempre.

- [ ] **Step 5: Il report**

Nel report della notte (`docs/night-reports/<data>.md`, sul ramo), per questo piano: il ramo e da dove parte, i conti veri (vitest, pytest, e2e) contro quelli della Preparazione, le migrazioni di test fatte oltre a quelle elencate nei task (dovrebbero essere zero, salvo i nomi con la maiuscola trovati dai grep dei Task 7 e 8), cosa hanno trovato i grep sui file già toccati dai Piani 1–3, e le decisioni prese in autonomia. Niente push, niente merge, niente deploy.
