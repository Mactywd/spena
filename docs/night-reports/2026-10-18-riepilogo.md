# Report notte 2026-10-18 — riepilogo

Venti piani `pronto`, venti fatti. La notte è partita il 2026-10-18 alle 10:24 da `master`
e543ff9 ed è finita il 2026-10-19 alle 07:39. Ogni piano ha il suo ramo `night/<slug>` e la sua
sezione nel report della notte sul ramo; questo file li riassume tutti ed è il primo da leggere.
Niente merge, niente push, niente deploy: `master` resta a e543ff9.

## In breve

Niente di quello che segue è ancora nell'app che si usa ogni giorno: è tutto pronto, e arriva
quando Mattia lo rivede e lo pubblica.

**Dispensa**
- Una confezione si mette in dispensa direttamente da qui: si legge il codice a barre, si conferma con un tocco, e lo scanner è subito pronto per la confezione dopo.
- Con il + si crea al volo un ingrediente che non c'è, e la scadenza si scrive prima di confermare. L'avviso permette di annullare.
- Ogni riga ha un piccolo disegno dell'ingrediente (🍅 per i pomodori, 🧀 per i formaggi); dove non c'è, l'icona grigia del reparto. Un disegno sbagliato si cambia a mano. I disegni li sceglie l'AI una volta sola, dopo la pubblicazione.
- Tre pulsanti, «Tutto», «Cibo» e «Casa», mostrano un mondo alla volta. Il riepilogo delle scadenze conta solo il mondo scelto.
- I reparti si chiudono e si riaprono toccando il titolo. Da chiusi dicono quante cose contengono, quante sono finite e quante stanno per scadere, e il telefono si ricorda quali erano chiusi.
- Anche le cose quasi finite hanno «In lista», come quelle finite.

**Lista e spesa**
- In «Sistema la spesa» si aggiunge una cosa comprata che non era in lista, e più confezioni dello stesso prodotto, ognuna con la sua data.
- Cucinando, una confezione già quasi finita si rimette in lista con una casella, e in lista la nota dice perché è tornata.
- Mentre si scrive un ingrediente, i suggerimenti mostrano solo quelli che contengono la parola: sul catalogo di prova, in media meno di due righe invece di cinque, senza perdere quello giusto. Il prezzo: un errore nelle prime lettere spesso dà una lista vuota finché la parola non è finita.

**Ricette**
- Si tocca la dose di un ingrediente («180 g» di pasta), si scrive quanta se ne vuole, e tutte le altre dosi si ricalcolano da lì. In alto si vede a quante porzioni corrisponde.
- «Modifica con AI»: si scrive cosa cambiare («senza zucchero») e l'AI propone una ricetta nuova, già compilata. Salvata, dice «Variante di …» con il collegamento all'originale, che resta com'era.
- Accanto a ogni ingrediente c'è «Sostituisci»: cosa usare al suo posto, se si può omettere, e se il sostituto c'è in dispensa.
- Le ricette importate da GialloZafferano mostrano dosi pulite: «50 g» e non più «36 mesi 50 g». Le parole in più vanno in piccolo sotto il nome, e anche «½ cucchiaino» e «50 g + q.b.» ora si adattano alle porzioni.
- In fondo a ogni ricetta, a richiesta, calorie e nutrienti a porzione, con l'elenco onesto di quello che resta fuori dal conto (per esempio il sale «q.b.»). I numeri si completano dopo la pubblicazione, quando l'AI ha pesato le dosi.
- Nel modulo della ricetta la nota di ogni ingrediente («da grattugiare») si legge, si corregge e si toglie. Se si scrive il nome di un prodotto per la casa, il modulo lo dice subito, prima di salvare.
- Fra gli ingredienti da abbinare compare «Scartate»: le ricette scaricate rimaste fuori dal ricettario, ognuna col perché e cosa fare. Con «Rimetti in coda» riprova a entrare, e ritrova le cotture già segnate.

**Anagrafica e nutrienti**
- Ogni ingrediente alimentare ha «Valori nutrizionali» per 100 g (energia, proteine, grassi, zuccheri, sale, vitamine e minerali), presi dalla tabella ufficiale francese degli alimenti. L'AI sceglie l'alimento giusto, e Mattia può cambiarlo o annullarlo. Si vedono dopo che Mattia ha caricato la tabella.
- Ogni ingrediente dice quanto pesa una sua dose, come «1 spicchio» o «2 cucchiai», e il peso si corregge a mano.
- Una sezione «Sostituti» per rivedere, confermare o scrivere a mano le proposte dell'AI.

**AI e spese**
- Nel menu ☰ c'è «Spese dell'AI»: quanto è costato l'assistente nel mese, negli ultimi 30 giorni o da sempre, diviso per parte dell'app e per giorno. Le chiamate di cui non si sa il costo non passano per gratuite.
- Stanotte l'AI vera non è mai stata chiamata: tutte le prove usavano risposte finte. Le varianti e i sostituti vanno provati con l'AI vera.

**Attività**
- Spena può ricevere dal telefono i passi, gli allenamenti e le pesate di Samsung Health, anche dall'orologio, senza contarli due volte. Una pagina nuova, «Attività», li mostra; un'altra spiega in dieci passi come collegare il telefono.

**Ritocchi e pulizie**
- I pulsanti, le caselle e le tacche spenti non sono più sbiaditi: sono grigi, con la scritta leggibile anche al sole e col tema scuro.
- Col tema scuro, il menu ☰ scurisce davvero la pagina sotto.
- Le caselle della Lista e del foglio della cottura sono grandi come le altre, facili da toccare col pollice.
- Il cestino e le altre icone mostrano una rotellina mentre lavorano, e chi usa la tastiera non perde più il punto in cui si trova.
- Parole sistemate: «È «zucchina»?» senza l'articolo sbagliato, i nomi con la maiuscola in Lista e in cucina, «non è un alimento» per la carta forno.
- Nel modulo della ricetta, scegliere dai suggerimenti un ingrediente appena aggiunto non crea più una seconda riga che bloccava il salvataggio; e se due righe finiscono sullo stesso ingrediente, il messaggio dice quale.

**Prove fatte**
- Ogni novità è stata provata in un browser vero, con i dati di prova, nei due temi e alla larghezza di un telefono: alla fine tutto passava, in ogni pacchetto.
- Niente è stato provato sul telefono vero, né con l'AI vera, né sui dati veri.

**Da decidere**
- **Prima di pubblicare i suggerimenti più corti:** in «Sistema la spesa», con una voce lunga come «pasta barilla integrale», «Pasta» non viene più suggerita. In Anagrafica, cercando un nome, non si vedono più i doppioni scritti male. Va bene così, o si cambia?
- Durante la scansione in serie, con una dispensa lunga, la pagina scorre fino alla riga nuova e lo scanner esce dallo schermo.
- Quando il riquadro delle scadenze si spegne da solo, i reparti che aveva aperto si richiudono sotto il dito.
- Le dosi spezzate su più righe delle ricette importate («1 ½ cucchiai»): la regola è stata scelta di notte. E le cinque unità che nessuna riga usa più: si tolgono?
- I pulsanti senza sfondo, come il cestino, mentre aspettano cambiano solo un po' colore: si capisce che sono spenti?

**Da fare a mano dopo la pubblicazione (solo Mattia)**
- Far lavorare l'AI sui dati veri, con i comandi già pronti:
  - i disegni della dispensa (circa nove richieste);
  - i sostituti (prima venti, circa un centesimo, poi il resto, meno di 0,80 $);
  - i valori nutrizionali: prima scaricare la tabella francese e aggiungerla al progetto (meno di 0,10 $);
  - i pesi delle dosi (meno di 0,05 $).
- Pulire le dosi delle ricette già importate: prima la prova che non salva niente, poi una copia del database, poi la pulizia. Va fatta prima dei pesi delle dosi.
- Collegare il telefono: Samsung Health, Health Connect, l'app HC Webhook e la chiave, seguendo i dieci passi della pagina nuova.
- Misurare i suggerimenti sull'anagrafica vera (solo lettura), e confrontare «Spese dell'AI» con il conto di OpenRouter.
- Le prove sul telefono: fotocamera e tastiera vere, il pollice sui pulsanti nuovi, l'app installata chiusa e riaperta, il grigio dei pulsanti al sole.

## Dettagli tecnici

### I venti rami

Partenza di tutti i conti: `master` e543ff9, con vitest 938 (69 file), pytest 959, e2e 52.
Un asterisco vuol dire che il conto di vitest è stato preso con `--maxWorkers` ridotto per il
carico (vedi «Instabilità viste»). Ogni ramo ha avuto la revisione finale su opus e il suo giro
di correzioni; il database dei test di ogni piano (`spena_test_<slug>`) è stato tolto alla fine.

| # | Ramo `night/…` | Parte da | Testa | vitest / pytest / e2e | Esito |
|---|---|---|---|---|---|
| 1 | `s3-ingresso-diretto` | `master` e543ff9 | 17ccaa9 | 990 / 966 / 55 | **fatto con riserve** (una `[tbd] P2`) |
| 2 | `s12-righe-dispensa` | `s3-ingresso-diretto` 17ccaa9 | f8bb645 | 1006 / 1013 / 57 | fatto |
| 3 | `tema-scuro-spenti` | `s12-righe-dispensa` f8bb645 | 4dd49a1 | 1021 / — (backend intatto) / 63 | fatto |
| 4 | `s14-cibo-casa` | `tema-scuro-spenti` 4dd49a1 | 32ccc2e | 1067 / 1015 / 64 | fatto |
| 5 | `s15-reparti-collassabili` | `s14-cibo-casa` 32ccc2e | ebda0a5 | 1102* (4) / 1015 / 65 | fatto (una `[tbd] P2` nuova) |
| 6 | `rimetti-in-lista` | `s15-reparti-collassabili` ebda0a5 | b056811 | 1115 / 1019 / 66 | fatto |
| 7 | `r8-modifica-con-ai` | `rimetti-in-lista` b056811 | 6974368 | 1138* (4) / 1038 / 69 | fatto |
| 8 | `pulizie-controlli` | `r8-modifica-con-ai` 6974368 | c3f1e06 | 1166 / 1038 / 75 | fatto |
| 9 | `suggerimenti-soglia` | `master` e543ff9 | 0434cef | 944 / 992 / 57 | **fatto con riserve** (`[tbd] P2` da decidere prima del merge) |
| 10 | `scartate-in-coda` | `master` e543ff9 | 0b10c4c | 974 / 987 / 54 | fatto |
| 11 | `pulizia-dosi` | `master` e543ff9 | 827b25e | 939 / 1027 / 54 | fatto |
| 12 | `pulizie-test` | `master` e543ff9 | d2a180b | 947 / 962 / 55 | fatto |
| 13 | `r5-sostituti` | `master` e543ff9 | 5276734 | 978* (4) / 1073 / 54 | fatto |
| 14 | `h2-health-connect` | `master` e543ff9 | 4a81f1c | 983* (4) / 1063 / 56 | fatto |
| 15 | `r2-riporziona-ingrediente` | `master` e543ff9 | f60f6d7 | 986 / 1009 / 55 | fatto |
| 16 | `h1-spese-ai` | `master` e543ff9 | 8b72a77 | 987 / 992 / 55 | fatto |
| 17 | `pulizie-parole` | `master` e543ff9 | 924f941 | 949 / 961 / 53 | fatto |
| 18 | `s4-ciqual` | `master` e543ff9 | 65a5646 | 964 / 1069 / 56 | fatto |
| 19 | `s4-grammi` | `s4-ciqual` 65a5646 | 5ee7939 | 983* (2) / 1137 / 60 | fatto |
| 20 | `modulo-nota-nome` | `master` e543ff9 | ea6a361 | 952 / 981 / 55 | fatto |

Typecheck (`npm run typecheck`, `npx tsc -b --force`), lint e build puliti su tutti i rami.
Nessun ramo bloccato. I comandi da lanciare in produzione (`decide_emoji`, `clean_doses`,
`decide_substitutes`, `load_ciqual`, `s4_pilot`, `decide_ciqual`, `decide_grams`) sono stati
provati sullo stack e2e senza chiave: nessuna chiamata a pagamento, uscite come attese.

Dove sono i report dei rami: tutti in `docs/night-reports/2026-10-18.md`, **tranne R5 e H2**,
che l'hanno scritto in `docs/night-reports/2026-10-19.md`. I file risultati del controller
stanno in `.superpowers/night-2026-10-18/results/<slug>.md` (cartella ignorata da git); quello
di `suggerimenti-soglia` è andato perso, e fa fede il report sul ramo.

### Ordine di merge e migrazioni

**La catena** si unisce in quest'ordine, ogni ramo dopo quello da cui parte:
S3 → S12 → tema scuro → S14 → S15 → «Rimetti in lista» → R8 → pulizie dei controlli. Il ramo
`night/pulizie-controlli` contiene tutti e otto: basta fondere lui per portarli tutti, ma la
revisione va fatta ramo per ramo.

**I rami da `master`** sono indipendenti fra loro, con tre vincoli:
- `s4-grammi` dopo `s4-ciqual` (ne parte);
- `suggerimenti-soglia` solo dopo la decisione della sua `[tbd] P2`;
- R6 (`bloccato`) si sblocca col merge di R5.

Una scelta da fare: `pulizie-test` aggiunge una prova (`noLocalQueryClient.test.ts`) che elenca
ogni `new QueryClient(` nei test. Se si unisce presto, ogni ramo dopo di lui va convertito a
`createTestQueryClient()` al suo merge; se si unisce per ultimo, la conversione è un giro solo.

**Migrazioni.** I numeri sono riservati e ognuna parte dalla `0012`, salvo quelle in catena:

| Migrazione | Ramo | `down_revision` sul ramo | Al merge |
|---|---|---|---|
| `0013_figura_ingrediente` | S12 (catena) | `0012` | resta |
| `0014_varianti_ricette` | R8 (catena) | `0013` | resta |
| `0015_sostituti` | R5 | `0012` | ripuntare sulla testa di `master` di quel momento |
| `0016_ciqual` | S4 fetta 1 | `0012` | ripuntare sulla testa di `master` di quel momento |
| `0017_grammi_unita` | S4 fetta 2 | `0016` | resta, si unisce con la fetta 1 o dopo |
| `0018_attivita_health_connect` | H2 | `0012` | ripuntare, **e** la riga `alembic(scratch_url, "downgrade", "0012")` di `backend/tests/db/test_migration_0018.py` |

Unite nell'ordine dei numeri, le `down_revision` diventano `0015 → 0014`, `0016 → 0015`,
`0018 → 0017`. Dopo ogni merge `alembic heads` deve dire una riga sola. Il test della migrazione
di R5 scende di `-1` e regge comunque. Tutte si applicano da sole all'avvio del backend.

**Le etichette delle spese (H1).** `CALL_SITE_LABELS` in `backend/app/domain/spending.py` ha già
`ingredient_emoji` (S12) e `recipe_variant` (R8). Se uno di questi rami arriva su `master`
prima di H1, al merge di H1 va aggiunta la sua etichetta; se arriva dopo, va aggiunta al suo
merge. Il test `test_ogni_sezione_del_client_llm_ha_un_nome_a_video` fallisce e nomina quella
che manca.
- `"ingredient_substitutes": "Sostituti degli ingredienti"` (R5)
- `"ciqual_terms": "Cercare gli alimenti CIQUAL"` e `"ciqual_match": "Abbinare gli ingredienti a CIQUAL"` (S4 fetta 1)
- `"unit_grams": "Pesare le dosi delle ricette"` (S4 fetta 2)

**I file che più rami toccano** (conteggio sui diff di ogni ramo contro la sua base):

| File | Rami | Cosa fare |
|---|---|---|
| `next-steps.md` | tutti e 20 | Testata, «Pronti per la notte» (ogni ramo toglie la sua voce senza rinumerare: restano buchi, e il preambolo «Il 4, l'8, il 9, …» va riscritto), «Fatti (recenti)», «Da fare a mano». Le date delle voci `fatto` sono 2026-10-18 o 2026-10-19 secondo il ramo. |
| `frontend/e2e/style.spec.ts` | tutti e 20 | Le prove nuove stanno in fondo e in `SCHERMATE`: si tengono tutte. Con `pulizie-test` si tiene `giornoDiRoma`; la data `fraDueGiorni` di S15, scritta con `toISOString()`, diventa `giornoDiRoma(2)`. |
| `docs/night-reports/2026-10-18.md` | 18 | I rami da `master` creano ognuno lo stesso file: conflitto add/add, si uniscono le sezioni. |
| `docs/night-reports/2026-10-19.md` | R5, H2 | Stesso conflitto add/add fra i due. |
| `docs/prossimi-passi.md` | 16 | Righe di sezioni diverse: si tengono tutte. |
| `RecipeDetailScreen.tsx` (+ test) | R2, pulizia-dosi, R5, R8, pulizie-controlli, S4 fetta 2 | R5: «Sostituisci» in fondo al `<div>` della riga dopo la dose di R2, `SubstitutePanel` dopo `AnchorField`. S4 fetta 2: un import e una riga dopo il procedimento. |
| `CookSheet.tsx` (+ test) | R2, «Rimetti in lista», pulizie-parole, pulizie-controlli | R2 incontra «Rimetti in lista» anche in `services/cooking.py` (la riga `snapshot=` e l'import) e in `api/cooking.py`. |
| `icons.ts` | S12, S15, scartate, R5, H2, pulizie-controlli | Scartate e S15 aggiungono le stesse due righe dei chevron: una copia sola dell'export. |
| `backend/app/services/llm.py` (`LlmCallSite`) | S12, R8, R5, S4 fette 1 e 2 | Valori uno sotto l'altro: si tengono tutti. |
| `backend/app/main.py`, `models/__init__.py` | H1, H2, R5, S4 fette 1 e 2 | Si tengono tutti i router e i modelli. |
| `App.tsx`, `AppHeader.tsx` | S3, R8, scartate, H1, H2, pulizie-test; tema scuro | Con H1 e H2, `INDEX` = `…, «Anagrafica», «Spese dell'AI», «Attività»`; l'ultima voce del test del fuoco è «Attività». Il tema scuro tocca il portale, non `INDEX`. |
| `frontend/src/domain/types.ts` | S12, S14, R2, R8, scartate, pulizie-parole | Campi aggiunti: si tengono tutti. |
| `RecipeForm.tsx`, `formModel.ts` | modulo-nota-nome, pulizie-controlli, pulizie-parole | Righe vicine: tenere tutte e due le versioni; gli import delle icone diventano `import { IconPlus, IconX } from "../../components/ui/icons";`, il blocco della nota sotto dose e ruoli. |

**I conflitti che i file risultati segnalano in particolare:**
- **`quantities.py` (pulizia-dosi con R2):** la riga d'ancora di R2 deve passare anche lei da `with_qb_tail`. Si incontrano anche nell'import di `test_quantities.py`, in `_to_out` e in `IngredientRow`.
- **`ServingsStepper.tsx` (R2 con pulizie-controlli):** si tiene la versione intera di R2 e ci si portano i due `ref` e `step`; nei suoi `onClick`, `onChange(below)` diventa `step(below, minusRef, plusRef)` e `onChange(above)` diventa `step(above, plusRef, minusRef)`.
- **`ImportQueueScreen.tsx` (+ test) (scartate con pulizie-controlli):** lo stato `arriving` e due prop sulle `TermCard`; `IconLoader2` in `icons.ts`.
- **`materialize.py`:** pulizia-dosi, scartate e R8.
- **`repositories/imports.py`:** `pulizie-test` con scartate; **`IngredientScreen.test.tsx`:** `pulizie-test` con S12 (e quindi col tema scuro).
- **`_resolve_lines` in `api/recipes.py`:** il `seen`/`_RepeatedIngredient` di `pulizie-test` contro le tre righe di `ingredient_for_new_name` di modulo-nota-nome. La fabbrica del client dei test di `pulizie-test` deve lasciare acceso `refetchOnWindowFocus`.
- **`pulizie-test` contro i rami che aggiungono `status.HTTP_422_UNPROCESSABLE_ENTITY`:** R2 ne aggiunge tre, da rinominare in `_CONTENT`, altrimenti `tests/test_no_deprecated_status.py` e il filtro fanno fallire la suite (è voluto). Ogni prova di guasto con un'asserzione negativa deve prima aspettare lo stato d'errore della query.
- **`pulizie-parole` con R8:** `_draft_from` deve passare `non_food=non_food and match.certain`; il §18 del piano di R8 e la docstring di `test_la_variante_non_introduce_un_non_alimentare` passano da «non in anagrafica» a «non è un alimento».
- **`pulizie-parole` con S3:** `describeSuggestion` va in `wording.ts`; si uniscono a mano il `<h2>` «È «…»?» e le due prove; nel `StockingRow.tsx` riscritto, `capitalizeFirst(name)` su `<p className="font-medium">`. Le prove nuove di S3, S14, S15 e «Rimetti in lista» che cercano il testo di una voce in minuscolo prendono la maiuscola.
- **Le etichette di sezione di H1** con S12, R8, R5 e le due fette di S4: vedi sopra.
- **S4 fetta 1 con S12:** se S12 ha reso obbligatorio `emoji` in `IngredientDetail`, va aggiunto all'oggetto di prova di `NutritionSection.test.tsx`.
- **`suggerimenti-soglia`:** `IngredientPicker.tsx` (anche pulizie-controlli), `api/ingredients.py`. Dopo il suo merge si può togliere la prop `emptyNote` di `IngredientPicker`, rimasta senza chiamanti con S3 (idea di S3).
- **`CLAUDE.md`:** lo toccano modulo-nota-nome (la guardia nuova nel riquadro dei non alimentari) e pulizia-dosi, in punti diversi. Al merge vanno aggiunte due righe proposte: l'annullamento dell'import tiene anche `variant_recipe_ids` accanto a `cooking_event_ids` (R8), e la rotta del webhook scrive senza sessione, con la chiave in `X-Spena-Token`, da esentare da un eventuale middleware globale di autenticazione (H2).
- **Trailer dei commit:** alcuni commit firmano «Claude Haiku 5.5», il modello che li ha scritti (S14 7a2edee e 4ef8edd, scartate c934054, a83788a e 296f5f4, S4 fetta 2 28a6561, il primo commit di suggerimenti, alcuni di H1). Nessuna storia riscritta.

Dopo ogni unione: vitest, typecheck, pytest e l'e2e intera (con `-p spena-e2e` e
`-f docker-compose.e2e.yml` in ogni comando).

### Domande per Mattia

Bloccanti per il merge:
1. **`suggerimenti-soglia`, `[tbd] P2` in «Voci decise, da portare a spec e piano».** «Sistema la spesa» precompila la ricerca con tutto il testo della voce: «pasta barilla integrale» contro pasta fa 0,250, «pane in cassetta grande» contro pane 0,208, sotto il pavimento di 0,30, quindi l'elenco è vuoto accanto ad «Aggiungi «…»». L'Anagrafica nasconde i quasi-doppioni appena c'è un riscontro («zuchina» a 0,700 sparisce cercando «zucchina»). Le strade: **(a)** contare come riscontro anche il testo che contiene un nome o un alias intero, ai confini di parola (risolve solo la prima); **(b)** un elenco non tagliato per questi due chiamanti (risolve tutte e due, ma il taglio non è più «solo l'endpoint» per tutti); **(c)** accettare e provare sul telefono.

Di comportamento, non bloccano il merge:
2. **S3, `[tbd] P2` (ramo `s3-ingresso-diretto` e i successivi).** Nella serie della scansione ogni «Metti in dispensa» porta in vista la riga nuova (`revealId`, decisione 2 di Mattia) e lo scanner esce dallo schermo con una dispensa lunga. Proposta: saltare `revealId` finché il pannello resta aperto e portare in vista l'ultima riga alla ✕. Va decisa con S14 e S15, che si agganciano ad `afterEntry`. S14 aggiunge un caso: in serie su «Casa», il codice di un cibo porta il selettore a «Tutto».
3. **S15, `[tbd] P2` in «Da approfondire».** Il riepilogo delle scadenze che si spegne da solo (l'ultimo yogurt segnato «Finito») richiude i reparti che aveva aperto, portandosi via la riga col suo «In lista». Quando è lo schermo a spegnere il filtro, i reparti restano aperti a video finché non si tocca qualcosa, senza salvarli?
4. **Pulizia delle dosi (`pulizia-dosi`).**
   - Va bene la decisione 6 raffinata (ruling 3 qui sotto: «fredda⏎1⏎½⏎cucchiai» → «1 ½ cucchiai»)?
   - Prima della scrittura in produzione: le due SELECT in sola lettura del «Dopo il deploy» («+» nelle note, percentuali in testa) e, al dry-run, le 5 «numero nel nome» del campione.
   - Le 5 unità già senza righe in produzione: toglierle, controllando prima `canonical_id`?
   - Da rivedere, scelte del piano: il ruolo dedotto dal testo arrivato, «½ + ½» = 1, «; » fra le note.
5. **Pulizie dei test (`pulizie-test`).** Si aggiunge `httpx2`, dipendenza nuova, per togliere l'ultimo avviso di Starlette, o lo si lascia (idea P3 sul ramo)? Da rivedere: le attese globali (4 s per Testing Library, 15 s per ogni prova) e la frase del 409, «Due righe puntano allo stesso ingrediente, «<nome>»: togline una, poi salva.».
6. **H2 (`h2-health-connect`).** La riga proposta per `CLAUDE.md` sulla rotta senza sessione; un nome italiano per il tipo nuovo `mindfulness` di HC Webhook 1.9.24.
7. **Tema scuro (`tema-scuro-spenti`).** Il ghost in volo (il cestino della ricetta, la ✕ della riga della lista) cambia solo il colore della scritta (`ink-soft` → `ink-faint`, 1,36:1 in chiaro e 1,45:1 in scuro fra i due): è la conseguenza della decisione 2 di Mattia, e si può volerla rivedere.
8. **S12 (`s12-righe-dispensa`).** `EMOJI_MAX_TOKENS` a 8000 invece dei 4000 del piano; `wrap-anywhere` sul nome della riga, che spezza una parola lunga senza trattino.
9. **Modulo della ricetta (`modulo-nota-nome`).** Un'idea nel backlog per l'annuncio dell'avviso ai lettori di schermo (ruling 6)? Le parole nuove della spec §5.

Scelte delegate o del piano, da rivedere se si vuole:
- **R5:** la regola del contesto (solo «Dolci…» è dolce), un solo difetto che scarta l'intera risposta dell'AI, da 1 a 3 sostituti, l'ambra di «Deciso dall'AI: da rivedere.», le regole della fusione.
- **S4 fetta 1:** «< x» = x/2 e «traces» = 0; i 30 casi del pilota e le soglie (0,3 candidati, 0,4 ricerca, 90%); la sezione in fondo alla scheda; la ricerca in francese; la colonna in kJ tollerata accanto a quella in kcal (ruling 4).
- **S4 fetta 2:** le quattro densità; i 20 pesi del pilota e la soglia dell'80%; il pannello chiuso in fondo al dettaglio; «Contate N righe su M». Le righe `bloccato` di P3 e M1 («attende: … S4») si possono rivedere, meglio dopo il deploy.
- **R2:** il limite delle 50 volte; «Torna alle dosi della ricetta» anche con le porzioni; la riscala al tocco di «Riscala» o Invio e non a ogni cifra; la dose sottolineata a puntini; la cottura con `servings` null e la dose nello `snapshot`; i 4 px della dose.
- **Scartate:** la rimessa che materializza subito coi due `sync_terms`; la strada scritta in ogni riga; «Apri» nell'avviso; le più recenti prima; tutti i pulsanti spenti durante una rimessa.
- **Pulizie dei controlli:** il grigio di tacche e casella mentre salvano; l'icona che gira sui pulsanti di sola icona; «Salva» dei campi del prodotto, `disabled` a riposo, che riporta il fuoco nel campo; il fuoco sul nome del termine dopo un annullamento; i ruoli del modulo in `text-sm`.
- **Pulizie delle parole:** «È «<nome>»?», «<nome> non è un alimento, sarà escluso», «Salvando lo cerco in anagrafica; se non c'è, lo creo in questo reparto.».
- **Suggerimenti:** il prefisso senza accenti nell'ordine («caffe» dà «Caffè» prima di «Caffelatte»); la nota di ripiego nei cinque `IngredientPicker` senza `onCreate`; le liste di due lettere più lunghe (5,60 → 6,54 righe).

Senza domande: «Rimetti in lista», R8, H1, S14.

### Dopo il deploy (solo Mattia)

In ordine, dove l'ordine conta. Sempre con `-f docker-compose.prod.yml`. I comandi esatti sono
nella sezione «Dopo il deploy» di ogni piano.

1. **`alembic current`** sul server: deve dire la testa con tutte le migrazioni unite.
2. **S12, le figure:** `decide_emoji` (circa 900 ingredienti, nove chiamate), rilanciato finché il numero scende; se smette di scendere, ci si ferma.
3. **Pulizia delle dosi:** `clean_doses --dry-run` e il confronto coi numeri attesi e con le regole di arresto («numero nel nome» oltre circa 220, o «lette diverse» molto sopra l'atteso, vuol dire niente scrittura); le due SELECT in sola lettura; il backup; la scrittura; `decide_units` se servono unità nuove. **Prima di `decide_grams`**, perché S4 fetta 2 mette `ON DELETE CASCADE` su `ingredient_unit_grams.unit_id`.
4. **S4 fetta 1:** scaricare `Table Ciqual 2025_FR_2025_11_03.xlsx` da https://doi.org/10.57745/RDMHWY in `data/ciqual/ciqual-2025.xlsx`, provarlo con `load_ciqual --dry-run` dal checkout (se dice «Il file non va», fermarsi: il messaggio dice la colonna) e committarlo; poi sul server `load_ciqual --dry-run`, `load_ciqual`, `s4_pilot` (< 0,01 $; se non passa, spec §9), `decide_ciqual --limit 20`, uno sguardo in Anagrafica, `decide_ciqual` fino a «nessun ingrediente alimentare in attesa.» (< 0,10 $).
5. **S4 fetta 2:** `s4_pilot` di nuovo (ora con i pesi, < 0,01 $), `decide_grams --limit 40` (< 0,002 $), uno sguardo a «Pesi per unità», `decide_grams` fino a «nessuna coppia in attesa di un peso.» (< 0,05 $ in tutto).
6. **R5:** `decide_substitutes --dry-run` (attese 900–1.800 voci), `--limit 20` (~0,01 $) e uno sguardo alle venti righe, di nuovo `--dry-run` per la stima; sotto 0,80 $ il resto in un lancio, altrimenti in due giorni.
7. **Suggerimenti:** `measure_suggestions` sull'anagrafica vera (sola lettura, qualche minuto; è una lettura della produzione), da confrontare col §6 della bozza; se la famiglia «digitazione» ha persi, sono il caso da guardare.
8. **H2:** un `curl -X POST` senza chiave sul webhook deve dare `401`. Poi sul telefono: Samsung Health › Health Connect (passi, esercizio, peso), la prova dei 10 minuti, HC Webhook installato e fuori dall'ottimizzazione della batteria, «Crea la chiave» e i dieci passi, «Testa Webhook». «Attività» deve dire la prova e **non** «Arrivati e non usati: timezone»; i passi di ieri uguali a Samsung Health.
9. **H1:** «Spese dell'AI» › «Da sempre» parte dal 17 settembre 2026; il totale torna con l'attività su OpenRouter, dove compariranno anche le righe nuove (`recipe_variant`, `ingredient_substitutes`, `ciqual_*`, `unit_grams`).
10. **R8 col modello vero:** una variante su una ricetta importata lunga (regge il tetto di 4000 token?), «sostituisci lo zucchero con dolcificante» (ribilancia?), la riga `recipe_variant` in `llm_calls` col suo costo, la foto dell'originale sulla variante.
11. **Scartate:** aprire «Scartate (N)», correggere in Anagrafica le pagine con un ingrediente non alimentare, «Rimetti in coda», e controllare che la ricetta rientri con le sue cotture.
12. **Prove sul telefono**, una riga `[tbd]` per piano in «Da fare a mano» sui rami: la fotocamera vera in serie, la fotocamera negata, la tastiera numerica (S3, R2); le emoji vere e «Cambia figura» (S12); il grigio al sole e il ☰ in scuro (tema scuro, pulizie dei controlli); i tre mondi e l'app reinstallata che riparte da «Tutto» (S14); i titoli dei reparti col pollice e i reparti chiusi dopo il riavvio (S15); «In lista» sulla riga gialla (rimetti); il pannello con la tastiera aperta (R8, R5); la tastiera che non si apre dopo «Salva» di un campo del prodotto (pulizie dei controlli); i tre periodi di H1 col pollice; «Valori nutrizionali», la ricerca e «Annulla la scelta» (S4).

### Instabilità viste

**vitest sotto il carico di tre corsie.** Con i worker di default (load average fino a 30–45,
anche per altri progetti in prova) cadevano a turno i primi test di alcuni file, sempre in file
che il ramo non toccava, con il `findBy` da 1000 ms scaduto e la schermata ancora su «Carico…».
Tutti verdi da soli e con meno worker; nessun test toccato o indebolito. I più frequenti:
- `registry/IngredientScreen.test.tsx`, «dice cos'è e dove è usato, prima di ogni correzione»: visto da quasi tutti i rami, e da `pulizie-controlli` anche su una macchina non carica (2 corse intere su 5, a circa 1,4 s contro l'attesa di 1 s);
- `shopping-list/ShoppingListScreen.test.tsx`, «una sezione per reparto, con il conteggio; quello ignoto in fondo»;
- `recipes/useArchiveRecipe.test.tsx`;
- più di rado: `RecipeForm` (i due test R12), `AiDraftScreen`, `ProductScreen`, `RecipeEditScreen`, `StockingScreen`, `IngredientSubstitutes`, `UnitWeights`.

Conti finali presi con `--maxWorkers` ridotto: **4** per S15, R8, R5 e H2 (anche nella
Preparazione); **2** per S4 fetta 2. Con `--maxWorkers=3` sono state verificate le suite del
tema scuro e di S14; con `--maxWorkers=2` il giro dei fix di S4 fetta 1; con `--maxWorkers=4`
la Preparazione e i task di «Rimetti in lista» (verifica finale senza opzioni) e la
Preparazione di modulo-nota-nome. La cura scritta è `pulizie-test` (`asyncUtilTimeout` a 4 s),
ma la sua misura «prima» (0 cadute su 18 corse) non ha mai riprodotto l'instabilità: mostra che
non c'è regressione, non prova la cura.

**e2e fra mezzanotte e le 2.** `style.spec.ts:727` («il campo data si vede…», «scade tra 5 gg»)
calcola la data in UTC mentre il server la calcola in Europe/Rome, e fra le 00:00 e le 02:00
fallisce. È un difetto noto di `master`, già nel backlog come idea, e `pulizie-test` lo
corregge con `giornoDiRoma`. L'hanno visto S14, R5 e S4 fetta 1, che hanno rifatto l'e2e dopo
le 02:00 (tutto verde). Nessun'altra e2e instabile.

### Nuove voci aggiunte ai `next-steps.md` dei rami

Oltre alla voce `fatto … (da revisionare)` di ogni piano. Tutte `idea` P3 salvo dove è scritto.

- **S3:** `[tbd] P2` la serie della scansione e la riga portata in vista; `[tbd] P1` prove sul telefono; idee: fotocamera che si riaccende a ogni codice; togliere `emptyNote` dopo i suggerimenti; estrarre il pezzo comune di `PackageRow` e `StockingRow`; la nota «L'hai appena messo in dispensa…» dopo «Annulla»; la ✕ con «Metti in dispensa» in volo che nasconde un errore; una confezione in più senza scelta che non entra in silenzio; il fuoco dopo la serie; un codice non trovato ricordato dopo «Annulla». (L'idea su `IngredientChooser` e `aria-disabled` l'ha chiusa `pulizie-controlli`.)
- **S12:** `[tbd] P2` `decide_emoji` in produzione; idee: l'emoji anche in Lista, Sistema la spesa e cottura; `import_gz` che nomina `decide_emoji`; una fusione che eredita la figura del perdente.
- **Tema scuro:** `[tbd] P3` prova sul telefono.
- **S14:** `[tbd] P3` prove sul telefono; l'idea «una riga nascosta non spegne `revealId`», chiusa poi da S15.
- **S15:** `[tbd] P2` i reparti richiusi dal riepilogo; `[tbd] P3` prove sul telefono; idee: «chiudi tutto / apri tutto»; l'errore di una riga in un reparto chiuso.
- **«Rimetti in lista»:** `[tbd] P3` prova sul telefono; idee: la corsa fra due dispositivi con dati vecchi (`from_status`); l'estrazione da `PantryRow.tsx` riscritta (resta la scadenza).
- **R8:** `[tbd] P3` prove col modello vero e al telefono; idee: le etichette di H1 da controllare al merge; riproporre dal modulo della variante; correggere foto e tempi di una ricetta; le note delle righe perse in una variante; un indice su `derived_from_id`; `variant_recipe_ids` in `CLAUDE.md`.
- **Pulizie dei controlli:** chiude 13 idee; `[tbd] P3` prova sul telefono; idee: altri campi che si spengono con `disabled` nativo (`RenameForm`, `CategoryForm`, la data di `PantryRow`); l'attesa del fuoco in sospeso nella coda.
- **Suggerimenti:** `[tbd] P2` da decidere prima del merge; `[tbd] P3` dopo il deploy (la misura e il telefono); un'idea con le code della revisione finale; chiusa l'idea su `%` e `_` nel `LIKE`.
- **Scartate:** `[tbd] P3` prova al telefono; idea: il collegamento dalla riga al termine (`?termine=<id>`); chiusa l'idea su `skipped_reason`.
- **Pulizia delle dosi:** `[tbd] P2` la corsa in produzione.
- **Pulizie dei test:** chiude 8 idee; idea: l'avviso di Starlette che vorrebbe `httpx2`.
- **R5:** `[tbd] P3` dopo il deploy; R6 resta `bloccato`, ora «attende: il merge di R5»; idee: le correzioni dei sostituti nel `payload` dell'import; un elenco delle voci AI da rivedere; «Chiedi all'AI» in Anagrafica.
- **H2:** `[tbd] P2` il telefono dopo il deploy; idee: il dispendio per P2, con l'avviso sui giorni parziali al bordo della finestra; applicare le cancellazioni (`deleted`) di Health Connect.
- **R2:** `[tbd] P2` prove sul telefono; idee: la conversione g/kg e ml/l; i 4 px della dose; l'attesa della vista nuova nelle prove e2e future.
- **H1:** `[tbd] P3` prove coi dati veri e al telefono; idea: il dettaglio di un giorno per sezione.
- **Pulizie delle parole:** chiude sei idee.
- **S4 fetta 1:** `[tbd] P2` dopo il deploy; idee: la fusione che eredita la scelta CIQUAL; togliere `ingredients.composition_ref`; la ricerca CIQUAL senza accenti; «< 0,01» invece di «0».
- **S4 fetta 2:** `[tbd] P2` dopo il deploy; idea: il peso orfano su un'unità poi resa canonica.
- **Modulo della ricetta:** chiude l'idea del non alimentare scoperto solo salvando.

### Come è andata la notte

**Tre corsie in parallelo**, su 16 core e 15 GB, ognuna con un controller SDD per piano e la
revisione finale su opus:
- **A, la catena:** S3 → S12 → tema scuro → S14 → S15 → «Rimetti in lista» → R8 → pulizie dei controlli. Finita alle 07:39.
- **B, da `master`:** suggerimenti → scartate → pulizia delle dosi → pulizie dei test → R5 → H2. Finita alle 04:35.
- **C, da `master`:** R2 → H1 → pulizie delle parole → S4 fetta 1 → S4 fetta 2 → modulo della ricetta. Finita alle 05:40.

**Tre interruzioni per il limite di sessione:**
1. Verso le 11:40, con il reset alle 14:50; la notte è ripresa alle 17:33. Alla ripresa erano finiti suggerimenti e R2; S3, scartate e H1 sono stati ripresi da controller nuovi. Le sveglie sono state rifatte per le 22:36, 03:36, 08:36 e 13:36 (la finestra di 5 ore era ripartita alle 17:32).
2. Verso le 20:20 si sono fermati i controller del tema scuro, delle pulizie dei test e di S4 fetta 1; ripresi via SendMessage alle 22:35.
3. Verso le 03:00 si sono fermati quelli di S15, H2 e S4 fetta 2; ripresi alle 03:36. S4 fetta 2 è stato consegnato parziale alle 03:07 e finito da un controller nuovo alle 04:33.

**La scratchpad persa al primo reset.** Il primo registro dell'orchestratore e il brief comune
stavano nella scratchpad di sessione, cancellata al reset: si sono persi il registro, il brief
(i controller di H1 e delle scartate hanno ricostruito le convenzioni da altri piani finché non
è stato indicato il nuovo) e il file risultati di suggerimenti. Alle 17:44 brief e registro sono
passati in `.superpowers/night-2026-10-18/`, ignorata da git, che sopravvive ai reset. Il
controller di H1 ha consegnato due volte un lavoro parziale (T1–4 committati senza revisioni,
con un implementer orfano in volo): la causa probabile erano i sottoagenti lanciati in
sottofondo, e da lì il brief li vuole in primo piano.

**Le scelte dell'orchestratore**, ognuna con il costo se sbagliata:
- **Tre corsie in parallelo**, perché i piani da `master` non dipendono l'uno dall'altro. Costo: vitest instabile sotto carico; i controller hanno rieseguito e annotato (vedi sopra).
- **Un database dei test per piano** (`spena_test_<slug>`), perché tre corsie si sarebbero pestate su `spena_test`, e i piani della catena lo avrebbero portato alla `0013`. Costo: nessuno; tutti tolti alla fine.
- **Uno stack e2e solo (`spena-e2e`) col lucchetto** `mkdir .worktrees/e2e.lock`, per evitare `down` incrociati. Costo: attese; alcuni piani hanno committato il codice e lanciato l'e2e quando il lucchetto si è liberato.
- **`npm install` una volta sola, alle 10:24.** Costo: nessuno (nessuna dipendenza nuova era permessa).
- **I file della notte in `.superpowers/night-2026-10-18/`** e non nella scratchpad. Costo: nessuno.
- **I sottoagenti in primo piano**, uno alla volta. Costo: controller un po' più lenti.

Alla fine restano i 20 worktree in `.worktrees/` e i rami `night/*`: da togliere dopo la
revisione. Nessuno stack `spena-e2e`, nessun lucchetto, nessun database dei test rimasto.

### Da fare nella fase giorno

1. Decidere la `[tbd] P2` dei suggerimenti, e se si vuole quelle di S3 e S15.
2. Rispondere alle domande sopra e rileggere i rulings qui sotto, per rifare quelli sbagliati.
3. Revisionare e unire la catena, poi i rami da `master`, ripuntando le migrazioni.
4. Deploy, poi i passi di «Dopo il deploy».

## Appendice: «Rulings I made»

Tutte le decisioni prese in autonomia, piano per piano, dai file risultati (per suggerimenti,
dal report sul ramo). Ognuna con il costo se sbagliata.

### S3, ingresso diretto in dispensa (`night/s3-ingresso-diretto`)
1. **PF1.** «Passa senza modifiche» per `StockingRow.test.tsx` e `StockingScreen.test.tsx` vuol dire che nessun test esistente cambia; aggiungere in fondo i test nuovi del piano è permesso. Costo: nessuno.
2. **PF2a.** `PackageRow` ripete la barra delle tre icone e «Cambia» di `StockingRow`, come la scrive il piano; un'idea P3 per estrarre un pezzo comune. Costo: un piccolo refactoring più avanti.
3. **PF2b.** Il Task 8 poteva unire `undoEntry` e `undoRemove` in un helper locale; non l'ha fatto. Costo: nessuno.
4. **PF3.** Il Task 8 ha migrato un test in più di `PantryScreen` («con l'aggiunta aperta, il vuoto non offre un secondo «Aggiungi»»), tenendo l'asserzione sincrona e aggiungendone una dopo il debounce. Costo: un test da ripristinare.
5. **PF4.** Mentre `IngredientChooser` crea l'ingrediente, il campo usa `disabled` nativo (viene da `IngredientPicker`, che il piano vietava di toccare); idea P3. Costo: un difetto di accessibilità per il tempo di una richiesta. (Poi corretto da `pulizie-controlli`.)
6. **PF5.** In `prossimi-passi`, A, B e C sono «decise da Mattia il 2026-10-09», non «da confermare». Costo: una frase.
7. **PF6.** Al passo 2 del Task 4 fallisce tutto `ScannerPanel.test.tsx`, non solo i due test nuovi: atteso. Costo: nessuno.
8. **PF7.** Dopo «Annulla» nell'avviso, rileggere lo stesso codice dice ancora «L'hai appena messo in dispensa…»: è il codice del piano; prova sul telefono e idea P3. Costo: una nota fuorviante dopo un annullamento.
9. **T1.** Nel test del 409 il prodotto è salvato con `commit()` invece di `flush()`, perché il `rollback` della rotta scarterebbe una riga in sospeso. Costo: una riga di fixture.
10. **T8.** Una Minor trattata come difetto: il test migrato non era più forte in ogni caso («mai asserzioni indebolite»). Costo: un giro di correzione in più.
11. **F-I1, la riserva.** La revisione finale ha trovato lo scanner che esce dallo schermo nella serie; non corretto (decisione 2 di Mattia, e `afterEntry` è l'aggancio di S14 e S15), registrato come `[tbd] P2`. Costo: con una dispensa lunga si risale a ogni codice, finché non arriva una piccola modifica in `PantryScreen`/`DirectEntry`.
12. **F-M.** L'ultimo giro ha toccato solo documenti e commenti; lasciati in nota: l'e2e non apre il campo della data sulla scheda sfusa, e verifica il testo esatto «Metti in dispensa 1» (lo chiede il piano). Costo: piccoli seguiti.

### S12, righe della dispensa riconoscibili (`night/s12-righe-dispensa`)
1. **PF1.** Il commento dell'e2e diceva che «melanzana» non la usa nessun altro file: falso (la usa la prova S3 del +, che non scrive). Tenuta «melanzana», corretto il commento. Costo: una frase.
2. **PF2.** Usati gli aiuti già nel file (`senzaScorrimentoLaterale`, `leggibileNeiDueTemi`) invece di ricopiarli. Costo: nessuno.
3. **PF3.** Il commento del blocco S12 dice che l'unica traccia è «melanzana» decisa «Nessuna». Costo: una frase.
4. **PF4.** In `MARK_PAIRS` resta `ink-faint`/`page` a 3:1, anche se `PAIRS` la misura a 4,5:1 (la chiede la spec §7). Costo: un test ridondante.
5. **PF5.** Previsto di restringere le query dei 149 radio a `within(gruppo)` in caso di timeout; non è servito. Costo: nessuno.
6. **PF6.** `ingredient_emoji: null` aggiunto anche dove il piano non lo elencava (`CookSheet.test.tsx`, `CREATED` in `DirectEntry.test.tsx`). Costo: nessuno.
7. **PF7.** Tenuto il nome `inDispensa` dell'e2e, che ombreggia due variabili omonime. Costo: un lettore confuso.
8. **PF8.** I blocchi del Task 3 stanno sopra il codice di S3, che non è toccato. Costo: nessuno.
9. **PF9.** Una risposta verificata che trova la colonna già scritta non entra nei conti: la scelta a mano vince. Costo: un riassunto che conta meno risposte.
10. **T7a.** L'e2e del Task 7 l'ha lanciata il controller quando il lucchetto si è liberato, insieme alla prova del comando del Task 9. Costo: nessuno.
11. **T7b.** Lo scorrimento laterale della griglia aperta si misura solo in chiaro (la larghezza non dipende dal tema); la leggibilità nei due. Costo: un caso visibile solo in scuro non verrebbe visto.
12. **FR1 (Important della revisione finale).** A 375 px, con la figura, «Bagnoschiuma» e «Ammorbidente» sbordavano sulla prima tacca: `wrap-anywhere` e un'asserzione e2e. Costo: una parola lunga si spezza senza trattino.
13. **FR2.** `EMOJI_MAX_TOKENS` da 4000 a 8000: una risposta di cento voci può superare 4000 token, e una troncata fermerebbe ogni rilancio. Costo: nessuno (si pagano solo i token generati).
14. **FR3.** Nei documenti: se il numero da decidere non scende fra due lanci ci si ferma; dopo un guasto i lotti di prima restano scritti. Costo: qualche frase.
15. **FR4.** Una risposta dell'AI che non è un oggetto conta come rifiutata invece di far cadere il comando; con un test. Costo: nessuno.
16. **FR5.** Sistemati quattro minori: i commenti delle famiglie nell'elenco del frontend, il commento della prova S3, `expect.soft` sulla `PATCH` di pulizia, il commento sulle figure 15.0. Costo: nessuno.
17. **FR6.** Il falso positivo del terzo grep (`EmojiForm.tsx`, un commento) resta, scritto nel report. Costo: nessuno.
18. **Parcheggiati:** la POST di «bagnoschiuma» fuori dal `try` (se fallisse, su uno stack di prova resterebbe una voce); l'ultima riga del comando dice sempre «rilancia» (righe fissate dal piano). Costo: minimo.

### Tema scuro: pulsanti spenti e velo del ☰ (`night/tema-scuro-spenti`)
1. Il commento con `emerald-700` in `index.css:6` resta: è su `master` e fuori dal piano. Costo: un commento da riformulare al merge.
2. Nel Task 4 il codice dell'e2e è stato committato prima di alzare lo stack, per tenerlo al sicuro durante l'attesa del lucchetto. Costo: nessuno.
3. Revisione finale prima del Task 6 (verifica e report), così la verifica copre il ramo corretto. Costo: nessuno.
4. Il giro finale ha preso due Minor: il ghost in volo fra le prove sul telefono, e nell'e2e il fondo `card`/`page` delle varianti spente. Costo: poche righe da togliere.
5. Il grep `opacity` su `buttonClasses.ts` trova il commento voluto dal piano; non riformulato. Costo: una discrepanza estetica nel grep.
6. **Parcheggiato:** nei browser senza `color-mix` il velo del ☰ diventa opaco (prima al 40%), solo sotto i minimi di Tailwind 4 (Safari 16.4, Chrome 111, Firefox 128). Costo: su un browser molto vecchio il ☰ oscura del tutto la pagina.
7. **Parcheggiato:** nell'e2e `VARIANTI` non obbliga a elencare ogni `ButtonVariant`. Costo: una sesta variante non sarebbe misurata dall'e2e (la vedrebbe `Button.test.tsx`).

### S14, «Tutto / Cibo / Casa» (`night/s14-cibo-casa`)
1. I due test d'aggiunta del Task 5 usano il gesto di S3 («Mela», poi «Metti in dispensa»), come prescrive il piano. Costo: nessuno.
2. L'e2e passa per il lucchetto della notte. Costo: attesa.
3. Task 3 e 4 a un solo implementer (haiku), due commit, una revisione. Costo: nessuno.
4. Il trailer di 7a2edee e 4ef8edd dice «Claude Haiku 5.5»; storia non riscritta. Costo: un trailer da correggere al merge.
5. Il difetto UTC/Roma dell'e2e non corretto qui (lo corregge `pulizie-test`); e2e finale dopo le 02:05. Costo: nessuno.
6. Revisione finale dopo il Task 6, prima di documenti e verifica. Costo: nessuno.
7. **Minor 1 corretto:** un tocco sul selettore o su «Cerca in tutto» spegne il `revealId` in sospeso prima di cambiare mondo (`chooseWorld`), con un test; prima ogni tocco su «Casa» o «Cibo» poteva rimbalzare a «Tutto». Costo: toccato un mondo, la riga appena aggiunta non viene più portata in vista.
8. **Minor 2 corretto:** il commento di `afterEntry` rimanda a `settleWorld`. Costo: nessuno.
9. **Parcheggiato il Minor 3:** dopo «Cerca in tutto» il fuoco si perde (stesso schema di «Mostra tutto»). Costo: chi usa la tastiera perde il fuoco.
10. Nota per S15 (report e idea): una riga nascosta non spegne `revealId`. Costo: nessuno.
11. La sezione sta in fondo a `2026-10-18.md`; le date dei documenti sono `2026-10-19`, la data vera. Costo: una data da ritoccare.
12. I rilievi della review del Task 7 (conti provvisori) corretti nel Task 8 e ri-verificati. Costo: nessuno.

### S15, reparti collassabili (`night/s15-reparti-collassabili`)
1. Il test della voce aggiunta usa il gesto di S3. Costo: nessuno.
2. Il test del mondo tocca il selettore con l'aiuto `mondo(...)`, così non scambia il mondo «Casa» col reparto «Casa». Costo: nessuno.
3. Task 1+2 a un implementer (haiku), Task 4+5 a uno (sonnet), un commit per task e una revisione per coppia. Costo: nessuno.
4. L'e2e passa per il lucchetto. Costo: attesa.
5. Revisione finale dopo il Task 6, prima di documenti e verifica. Costo: nessuno.
6. **L'Important della revisione finale non corretto: è la `[tbd] P2`** (il riepilogo che si spegne da solo richiude i reparti). Costo: una piccola modifica dopo la decisione.
7. Corretti tre Minor (8f5a3a2): `Section` con un solo `useId`; la pulizia dell'e2e una voce alla volta; un'asserzione sul titolo chiuso senza nota. Costo: nessuno.
8. **Parcheggiato:** `closedNote` controllato per verità (uno `0` o una stringa vuota non si vedrebbero; oggi nessuno li passa). Costo: nessuno oggi.

### «Rimetti in lista» (`night/rimetti-in-lista`)
1. Il diff dei documenti del Task 5 (25 righe di testo del piano) l'ha riletto il controller; la revisione finale l'ha ricontrollato. Costo: una svista di parole.
2. Revisione finale prima della verifica del Task 6. Costo: nessuno.
3. **Minor 1 non corretto, idea P3:** con due dispositivi, una spunta «Rimetti in lista» su una confezione non toccata la riporta allo stato mostrato a video; chiuderlo vuole `from_status`, un cambio di contratto escluso dal piano. Costo: raro, una confezione può tornare «quasi finita».
4. Minor 2 corretto (`fill_percent` nella nota chiusa di `prossimi-passi`). Costo: nessuno.
5. La re-review del giro di fix (solo documenti, dd950ba) l'ha fatta il controller. Costo: una svista nei documenti.

### R8, modifica con AI (`night/r8-modifica-con-ai`)
1. Revisione finale prima della verifica del Task 10. Costo: nessuno.
2. Task 9: l'idea su H1 scritta con quel che si sa già (H1 nomina già `recipe_variant` e `ingredient_emoji`). Costo: una riga di backlog da riscrivere.
3. Corretti l'Important (il test «una proposta arrivata dopo «Annulla» non apre niente») e i Minor dei test 404 e 409 e una frase di `prossimi-passi`; tre Minor diventati idee (note delle righe, indice su `derived_from_id`, `CLAUDE.md`). `CLAUDE.md` non toccato perché fuori dai file del piano. Costo: una riga di `CLAUDE.md` da scrivere al merge.
4. **Parcheggiato:** la corsa fra `variant_copy` e l'INSERT, se l'originale viene cancellata in quei millisecondi (solo da un annullamento dell'import a mano), dà un 404 con una frase sugli ingredienti; un secondo «Salva» salva senza legame. Il lock `FOR KEY SHARE` era fuori dal piano. Costo: un messaggio fuorviante in un caso quasi impossibile.
5. **Parcheggiato:** un'originale archiviata mentre si corregge la variante, se era l'unica della sua categoria, fa rispondere 422 sulla categoria; il modulo lo dice. Costo: un tocco in più in un caso raro.

### Pulizie: controlli spenti e fuoco (`night/pulizie-controlli`)
1. «`grep opacity` vuoto» vale per le classi: il commento in `buttonClasses.ts:15` resta, fa fede `disabledLook.test.ts`. Costo: una riga di commento.
2. Tolto il test «spento, non accetta tocchi» di `Cost.test.tsx`: provava la prop `disabled` di `CostPicker`, che il piano toglie. Costo: rimettere prop e test (nessun chiamante li usa).
3. «il campo è spento» di `IngredientChooser.test.tsx` (di S3) passa a `aria-disabled` + `readonly` + `not.toBeDisabled()`, un controllo più stretto. Costo: nessuno.
4. Dopo un salvataggio, `InlineField` sposta il fuoco da «Salva» al campo prima che il pulsante si spenga, solo se il fuoco era su «Salva» (decisione 9). Costo: su Android la tastiera potrebbe aprirsi dopo ogni «Salva» toccato; rimedio: spostare il fuoco solo da tastiera (`:focus-visible`).
5. Nel giro finale, oltre al fix chiesto: il fuoco torna su «Cucina» anche dopo un «Riprova» riuscito (e l'idea relativa è tolta); due cose in più nella prova sul telefono. Costo: una riga e un test da togliere.
6. Restano senza correzione: il test della coda non forza l'ordine delle letture; la regex di `disabledLook` non vede le varianti composte (`hover:disabled:`); una ventina di minori. Costo: una regressione futura non vista dai test.

### Suggerimenti tagliati (`night/suggerimenti-soglia`, dal report sul ramo)
1. Revisione finale prima del Task 7, così conti e report descrivono il codice finale. Costo: nessuno.
2. Database dei test `spena_test_suggerimenti`, anche per le misure di somiglianza in sola lettura. Costo: nessuno.
3. Stack e2e sotto il lucchetto della notte. Costo: attesa.
4. La numerazione di «Pronti per la notte» resta con un buco (voce 4 tolta). Costo: estetico, si rinumera al merge.
5. «Il 4» resta nel preambolo di «Pronti per la notte». Costo: estetico, da sistemare al merge.
6. Le due domande della revisione finale non risolte in codice: scelte funzionali fuori dal piano; esito «fatto con riserve». Costo: un giorno in più prima del merge.
7. Priorità P2 per la `[tbd]`: blocca il merge e tocca il flusso della spesa. Costo: solo l'ordine.
8. Le code minori non corrette di notte, in un'idea P3: cambierebbero numeri misurati o comportamento. Costo: un po' di lavoro dopo.
9. La correzione della revisione aveva cancellato per sbaglio l'idea «Il database di sviluppo locale non ha tabelle»: ripristinata byte per byte (e0a9fe5). Costo: nessuno.
10. Gli esempi non rimisurati nella `[tbd]` (pane 0,208, «gelati» → gelatina, Olive 0,500) restano, dalle misure della revisione finale. Costo: un numero sbagliato in un testo di voce.

### Le pagine scartate (`night/scartate-in-coda`)
1. Database `spena_test_scartate`. Costo: nessuno.
2. Stack e2e sotto il lucchetto. Costo: attesa.
3. c934054, a83788a e 296f5f4 firmano «Claude Haiku 5.5»; storia non riscritta. Costo: una riga cosmetica.
4. Task 6 diviso: passi 1–5 committati prima dell'e2e, l'e2e sul codice completo appena libero il lucchetto (superato dal 9). Costo: nessuno.
5. I numeri dei «Pronti per la notte» restano con un buco al 9. Costo: estetico.
6. Il brief comune non era nella scratchpad: il secondo controller è partito dalle convenzioni del piano e dei risultati di R2, poi ha seguito il brief nuovo. Costo: nessuno.
7. Dei quattro Minor della revisione finale, corretto il n. 1 (un 409 sulla rimessa lasciava a video l'elenco vecchio). Costo: una riga e due test da togliere.
8. Minor 2 (il fuoco sul `<body>` quando la riga rimessa sparisce) annotato nel report e non nella voce 13 (`pronto` di un altro piano); Minor 3 (le cotture contate per id, come la spec §3.2) e 4 (reparti del ricettario non invalidati) lasciati. Costo: una riga da spostare in next-steps al merge; un conto di cotture sbagliato di una cottura cancellata; un filtro dei reparti vecchio fino al ricaricamento.
9. L'e2e rigirata sul codice finale (af6130b). Costo: due minuti di stack.

### Pulizia delle dosi dell'import (`night/pulizia-dosi`)
1. Database `spena_test_dosi`. Costo: nessuno.
2. Task 1 e 2 in un solo dispatch, due commit e una revisione. Costo: una revisione più grande.
3. **Decisione 6 raffinata:** l'inizio della dose risale dall'ultima riga che comincia con una cifra, passando sulle righe senza lettere. «fredda⏎1⏎½⏎cucchiai» dà «1 ½ cucchiai» = 1,5 con nota «fredda» (la regola letterale dava 0,5); «da grattugiare⏎2⏎1/2⏎cucchiai» dà «2 1/2 cucchiai». Spec emendata. Costo: Mattia voleva un'altra lettura; si cambia prima della corsa in produzione.
4. **Important 1 corretto solo nei documenti:** se dopo la dose vera c'è un'altra riga numerica, la dose va nella nota («1⏎bustina⏎7 g» → «7 g», nota «1 bustina»). Il dry-run ha ora le attese corrette e regole di arresto; le righe del comando non cambiano. Costo: una checklist più lunga.
5. Minor 2 e 3 non corretti: un «+» nella nota rovina il testo; una percentuale prima della dose («70%⏎200⏎g») resta letta 70, com'era. Due SELECT da far girare a Mattia nel «Dopo il deploy». Costo: poche righe col testo rovinato, un errore di prima che resta.
6. Minor 4 non corretto: «Unità già senza righe prima» non segna le canoniche; il «Dopo il deploy» dice di controllare `canonical_id`. Costo: un controllo a mano.
7. Minor 5: S4 fetta 2 mette `ON DELETE CASCADE` su `ingredient_unit_grams.unit_id`; scritto di lanciare `clean_doses` prima di `decide_grams`. Costo: nessuno.

### Pulizie: test instabili e backend (`night/pulizie-test`)
1. Il giro e2e intero del Task 4 confluito in quello del Task 10 (lucchetto occupato); il Task 4 ha fatto girare `giornoDiRoma.spec.ts` e `--list`. Costo: un difetto sarebbe emerso al Task 10.
2. L'e2e l'ha fatta girare il controller, non un implementer. Costo: nessuno.
3. Il test del Task 2 passava `retry: false` a una `fetchQuery` mentre il Task 3 vuole il grep vuoto: diventato `retryDelay: 0`. Costo: una riga di test.
4. «pytest senza avvisi di Starlette» rispettato solo per il nostro codice; resta l'avviso di `starlette.testclient` che chiede `httpx2` (dipendenza nuova, idea per Mattia); filtro ristretto a `:app`. Costo: un avviso visibile finché Mattia non decide.
5. Il Task 9 (solo `next-steps.md`) rivisto dal controller. Costo: una correzione di parole.
6. Il Task 10 (il report) senza revisione a sé, letto dalla revisione finale. Costo: una correzione di parole.
7. **Parcheggiato il Minor 7:** nessuna prova forza il 409 di ripiego dell'`IntegrityError` in `_writing_recipe`. Costo: la frase di ripiego potrebbe rompersi in silenzio.
8. Il report sul ramo elenca ancora fra le «Cose minori rinviate» i commenti del Task 3, poi sistemati. Costo: una riga vecchia nel report.
- **Deviazione prevista dal piano:** `configure({ asyncUtilTimeout: 4000 })` in `frontend/src/test/setup.ts` e non in `vitest.setup.ts` (lì il typecheck dava 32 TS2339 negli `e2e/*.spec.ts`).
- **Important della revisione finale, corretto:** tre prove di guasto secondario erano diventate vuote con i tentativi veri; ora aspettano lo stato `error` della query, e cadono se si inserisce il difetto.

### R5, sostituisci un ingrediente (`night/r5-sostituti`)
1. `substitutionKey` senza `export`: la regola `react-refresh/only-export-components` rendeva rosso il lint, e nessuno lo importa. Costo: nessuno.
2. Lo spazio fuori dallo `<span>` nel titolo della scheda per contesto: dentro, jsdom lo perdeva dal nome accessibile. Stesso testo a video. Costo: nessuno.
3. «Corretto a mano in N ricette» conta anche le ricette eliminate, coerente con l'Anagrafica. Costo: un numero più alto, corretto con una riga in `ingredient_view`.
4. La prova `style.spec.ts:727` non si tocca qui; e2e rifatta dopo le 02:00. Costo: nessuno.
5. Nel giro di fix anche due minori economici: il modulo aperto vince su un errore di rilettura; `confirm.reset()` in Anagrafica. Costo: due righe da togliere.
6. Gli altri minori lasciati; in particolare le rotte di scrittura e `/ask` accettano una ricetta eliminata, ma l'app non ci arriva. Costo: una chiamata AI possibile solo da un client fuori dall'app.
7. Conto di vitest preso con `--maxWorkers=4`, nessuna asserzione o timeout toccati. Costo: un difetto vero nascosto dal carico (ma ogni file da solo è sempre verde).
- **Corretto dalla revisione finale:** il pannello non richiama più l'AI da solo (prima la rilettura chiedeva all'AI a ogni ritorno sulla finestra, riconnessione e tentativo: chiamate a pagamento senza un tocco).

### H2, l'attività da Health Connect (`night/h2-health-connect`)
1. Il test della migrazione passava `:fine` come stringa a una colonna `timestamptz`: oggetti `datetime` UTC. Costo: nessuno.
2. «Mai un 500»: `\u0000` o un surrogato solitario in versione, titolo, origine o nome di chiave valgono come assenti e la chiave non si registra; 5 test. Costo: un testo strano sparisce invece di comparire storpiato.
3. La prova nuova di `style.spec.ts` attende il link «Dispensa» prima di chiamare l'API. Costo: nessuno.
4. Il grep dei colori crudi non può essere vuoto (commento di `master`). Costo: nessuno.
5. La prova di `style.spec.ts` lascia dati di attività nello stack: aggiunta alle eccezioni dichiarate. Costo: nessuno.
6. `senzaScorrimentoLaterale` copiato in `attivita.spec.ts` con un rimando all'originale. Costo: poche righe doppie.
7. `HTTP_413_CONTENT_TOO_LARGE` invece del deprecato `HTTP_413_REQUEST_ENTITY_TOO_LARGE`. Costo: nessuno.
8. `Content-Length` con `isascii() and isdigit()` (superato dal 13). Costo: nessuno.
9. Il Task 9 (testo del piano in due documenti) rivisto dal controller. Costo: un refuso.
10. **Important della revisione finale:** HC Webhook 1.9.23/1.9.24, usciti il 2026-10-18, mandano sempre `timezone` e a volte `deleted`, che sarebbero apparsi in «Arrivati e non usati… si possono togliere» da «Testa Webhook» in poi: ora sono chiavi d'involucro, con un test. Costo: nessuno.
11. Nessuna etichetta italiana per `mindfulness`. Costo: una parola inglese fra i tipi non usati.
12. Una distanza che arrotondata fa 0,0 km non si mostra. Costo: un allenamento sotto i 50 m non dice la distanza.
13. `Content-Length` letto da un solo aiutante, fino a 10 cifre (oltre 4300 era un 500 dopo l'autenticazione, irraggiungibile dietro Nginx). Costo: nessuno.
14. «Annulla» sulla conferma di rigenerazione toglie anche l'avviso dell'errore precedente. Costo: nessuno.
15. La riga in `CLAUDE.md` sulla rotta senza sessione è proposta nel report, non scritta. Costo: nessuno.
16. I giorni parziali al bordo della finestra di HC Webhook e le cancellazioni (`deleted`): due idee. Costo: nessuno.

### R2, riporzionare da un ingrediente (`night/r2-riporziona-ingrediente`)
1. Il Task 4 cambia anche l'unico chiamante di `fetchRecipe` in `RecipeDetailScreen.tsx`, per un typecheck pulito fino al Task 6. Costo: nullo (riga riscritta dal Task 6).
2. e2e col lucchetto al posto del solo `docker ps`. Costo: attesa.
3. **Una riscala in volo annullata o superata non cambia più la vista** (Annulla, un'altra riga, lo stepper, «Torna alle dosi della ricetta», «Cucina», l'uscita da una vista non più valida): guardia a contatore in `anchorOn`, fuoco sulla dose solo se applicata, casella `readOnly` in volo; 6 test, fuori dal codice del piano. Costo: un ref e un tipo da togliere.
4. La seconda prova di `riporziona.spec.ts` aspetta «Riscalata da farro: 80 g.» prima di guardare le righe (alla prima corsa 54/55). Costo: nessuno.
5. `-mr-3` lasciato sulla dose che si tocca, 4 px più a sinistra delle dosi fisse; `-mr-4` farebbe sporgere il pulsante; idea. Costo: 4 px di disallineamento.
6. Un giro sui minori della revisione finale: il 3 anche per «Cucina» e l'uscita 422, la casella ferma in volo, due commenti vecchi, il commento di `FACTOR_PRECISION`, `assert` → `KeyError` (→ 404). Costo: poche righe.
- Il Task 3 ha usato il ripiego `get_recipe` previsto dal piano per `MissingGreenlet` (una SELECT in più, solo con l'ancora).

### H1, spese dell'AI (`night/h1-spese-ai`)
1. Il primo controller non ha trovato il brief (scratchpad cancellata): convenzioni ricostruite da un altro piano; dal Task 5 il brief c'era. Costo: qualche regola non seguita nei primi task (nessun effetto sul codice).
2. Niente `npm install`. Costo: nullo.
3. Task 1+2 e 3+4 a un implementer per coppia, una review per coppia. Costo: diff di review più grandi.
4. I primi dispatch senza i file brief/report degli script SDD. Costo: nessuno sul codice.
5. e2e col lucchetto. Costo: attesa.
6. ` ` nelle tre regex dei test al posto dello spazio crudo (`no-irregular-whitespace`). Costo: nessuno.
7. Trailer «Claude Opus 5.5»/«Haiku 5.5» secondo la sessione, anche con implementer sonnet. Costo: cosmetico.
8. Revisione finale prima del Task 8; il `DROP DATABASE` dopo l'ultimo pytest. Costo: nessuno.
9. **Una quota piccola ma non nulla vale 0,0001, non 0** (`share()`): la decisione 8 della spec («< 1%») vince sul `round` del piano. Costo: quella sezione mostra «< 1%» e una barra minima invece di niente.
10. Tolta da `next-steps.md` la clausola «decidere se tenere la riga delle chiamate senza costo»: Mattia l'ha decisa il 2026-10-13. Costo: nessuno.
11. Le due note di merge della revisione finale nel report, senza codice. Costo: nessuno.

### Pulizie: parole a video (`night/pulizie-parole`)
1. I due commenti prescritti dal piano contenevano «È un «» e sporcavano il grep d'accettazione: riformulati. Costo: due righe di commento diverse dal piano.
2. `matchNote` guarda `proposedCategory` prima di `nonFood`; irrilevante perché il backend manda `proposed_category=None` quando c'è un id di corrispondenza. Costo: una riga non alimentare con reparto direbbe «da creare».
3. Accettato un commento cambiato in `formModel.ts`, fuori dai file elencati, perché il grep copre tutto `frontend`. Costo: una riga fuori elenco.
4. La re-review dell'a capo di un commento (752db5f) l'ha fatta il controller. Costo: un a capo non rivisto.
- Preparazione: `spena_test` era alla `0012`; usato comunque `spena_test_parole`.

### S4 fetta 1, nutrienti da CIQUAL (`night/s4-ciqual`)
1. Il test `NutritionSection.test.tsx` del piano dava 9 errori di typecheck: corretti solo i tipi. Costo: nessuno.
2. Il grep `emerald\|neutral-` non è vuoto già su `master`: attesa «nessuna riga nuova». Costo: nessuno.
3. La tabella «File toccati» del piano diverge dal testo del Task 8: vale il testo. Costo: nessuno.
4. **`map_columns`:** il piano rifiutava il file se un costituente compariva in due unità, ma CIQUAL ha l'energia in kJ e in kcal: ora una colonna d'unità sbagliata va fra le «non usate» se c'è la gemella giusta; altrimenti il rifiuto resta. Costo: una colonna ignorata invece del rifiuto, solo con la gemella.
5. `read_ciqual`: un archivio rovinato dava un traceback; ora «Il file non va: …» e niente scritto. Costo: nessuno.
6. Il Task 11 dopo la revisione finale e il suo giro di fix. Costo: nessuno.
7. Giro di fix: la scelta vale solo se è fra i risultati mostrati; un salvataggio alla volta; il rifiuto vecchio sparisce al cambio di scelta; torna il triangolo di «Vitamine e minerali (N)»; `apply_ai_choice` non scrive su un ingrediente sparito o diventato non alimentare durante `decide_ciqual`. Costo: piccolo, interno.
8. La lista «Declined to judge» della revisione finale resta a Mattia (soglie, x/2 e traces, «nessun alimento adatto», passi del merge, le cose misurabili solo col file vero). Costo: nessuno nel ramo.
9. La rossa e2e delle 00:5x (data in UTC) non corretta qui; e2e rifatta alle 02:25. Costo: un'ora d'attesa.

### S4 fetta 2, grammi e nutrienti della ricetta (`night/s4-grammi`)
1. `recipe_nutrition_out(result, source)` come nel codice del piano (la riga «Interfaces» aveva un argomento solo). Costo: nessuno.
2. Il Task 11 dopo la revisione finale e il suo giro di fix. Costo: nessuno.
3. Il brief vince sul piano: niente `npm install`, e2e sotto il lucchetto. Costo: nessuno.
4. `set_grams` arrotonda a 0,01 prima di controllare e rifiuta (`bad_grams`) un peso non finito o fuori da (0, 5000]: il piano lasciava passare 0,001 g fino al CHECK (un 500). Costo: nessuno.
5. `_read_grams` rifiuta numeri enormi dall'AI (1e30, un intero di 401 cifre), che fermavano `decide_grams` perdendo la registrazione della chiamata pagata. Costo: nessuno.
6. `--limit ²` esce con 2 invece di un traceback (solo `decide_grams`). Costo: nessuno.
7. Due `eslint-disable-next-line react-refresh/only-export-components` (i primi in `frontend/src`) su `parseGrams`/`weightText`, che il piano fissa in `UnitWeights.tsx`; un parametro rinominato `_path` per `tsc -b`. Costo: spostare due funzioni in `nutrition.ts`.
8. Due correzioni di soli tipi nel test del Task 8 (TS2493). Costo: nessuno.
9. «Data di oggi» nei documenti = 2026-10-18, anche dopo mezzanotte. Costo: una data in tre righe.
10. Lasciata la firma «Claude Haiku 5.5» in 28a6561. Costo: nessuno.
11. I 5 minori della revisione finale in un solo giro (il pannello che perdeva i numeri se un ricalcolo falliva, `busy` su «Riprova a calcolarli», il campo del peso dopo «Annulla il peso», un avviso vecchio, un import inutile) più un'idea. Costo: una decina di righe da togliere.
12. Accettate come fuori dal piano le voci «Declined to judge»: densità approssimata detta solo nei documenti; stesso link in Anagrafica anche per una dose non letta; «senza nutrienti» che nasconde «senza peso»; `decide_grams` che può dire «rilancia» per sempre; un solo testo d'errore per l'annullamento; pesi che restano su un ingrediente reso non alimentare; numeri vecchi per un attimo alla riapertura; in `RecipeDetailScreen.tsx` un import, un commento e il componente invece di «una riga sola». Costo: piccoli seguiti da pianificare.
13. Tenuto `busy={query.isFetching}` su «Riprova a calcolarli», oggi inerte (TanStack Query v5 rimette in «pending» una lettura fallita senza dati). Costo: una proprietà inerte.

### Modulo della ricetta: nota e nome (`night/modulo-nota-nome`)
1. La verifica `grep -n "match_name" backend/app/api/recipes.py` trova il commento che il piano prescrive: letta come «nessuna chiamata a `match_name(`». Costo: una parola di commento.
2. «Data di oggi» = 2026-10-18 anche se l'orologio diceva 19. Costo: una data nel backlog e nel report.
3. Il Task 8 (solo documenti) verificato dal controller. Costo: un'imprecisione di parole.
4. Dopo la revisione finale, un giro solo sulle lacune economiche: la prova dell'Invio col nome non alimentare, il limite della nota con gli spazi ai bordi, «archiviata» nel commento dell'e2e. Costo: due prove da togliere.
5. La prova dell'Invio non isola la guardia `|| nameProblem` di `submit` (`Button` ferma già il clic implicito su un pulsante `aria-disabled`): tenuta come prova di comportamento. Costo: una riga ridondante.
6. **Parcheggiato:** l'avviso ha `role="status"` ma nasce già pieno (alcuni lettori di schermo potrebbero non annunciarlo) e il campo non lo cita in `aria-describedby`. Markup del piano. Costo: un annuncio mancato per chi usa un lettore di schermo.
7. **Parcheggiato:** `match_name` senza coincidenza fa anche una ricerca pg_trgm che `ingredient_for_new_name` scarta. Costo: una query in più per nome scritto.
8. **Parcheggiato** (già su `master`): il commento in `NewIngredientFields.submit` sull'Invio col pulsante spento non corrisponde a come si comporta `Button`. Costo: un commento sbagliato.
