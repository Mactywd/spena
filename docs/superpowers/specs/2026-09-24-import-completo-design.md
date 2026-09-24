# R4 — Via le ricette di semina, e l'import completo di GialloZafferano

Data: 2026-09-24. Voce di `docs/prossimi-passi.md`: **R4**. Brainstorming nella
conversazione dello stesso giorno. Tre risposte di Mattia: le 26 ricette di semina
vanno **via tutte**; il tetto di 1$/giorno resta **un limite di credito su
OpenRouter**, non codice; il ricettario si sfoglia con un **«Mostra altre»** in fondo.
La strada scelta per l'import è la A: un comando che svuota la sitemap.

**Questa spec si costruisce ma non si esegue nella sessione che la scrive.** Il deploy,
la cancellazione delle ricette di semina in produzione e il lancio dell'import stanno
in `docs/import-gz-runbook.md`, per una sessione dedicata.

## 1. I fatti da cui parte (misurati il 2026-09-24)

- La sitemap che `import_gz` legge già,
  `https://ricette.giallozafferano.it/sitemap/ricette.xml`, elenca **8.469 ricette**.
  In produzione ce ne sono 40 importate più 26 di semina.
- Con `DELAY_SECONDS = 1.2` sono almeno **tre ore** di sole pause. Il comando di oggi
  prende 50 pagine per lancio: sarebbero circa 170 lanci a mano.
- Lo storage non è un problema: circa 17 KB per ricetta importata, pagina d'import
  compresa, quindi circa 150 MB per tutto il catalogo, su un server con 31 GB liberi.
- Ogni termine sconosciuto costa una chiamata all'LLM, e la domanda contiene l'intera
  anagrafica (223 ingredienti oggi, circa 3.500 token, e cresce). Ai prezzi di
  `llm_prices` è circa 0,0002–0,0003 $ a termine. Per qualche migliaio di termini la
  stima è **1–3 $ in tutto**, ma non è misurata: le 69 decisioni dell'AI già prese
  precedono la registrazione delle spese in `llm_calls`.
- Un 402 di OpenRouter (credito finito) diventa `LlmUnavailable` in `services/llm.py`,
  e `decide_terms` lo tratta termine per termine: il termine resta in coda. Il limite
  di credito sulla chiave quindi degrada già come serve.
- **Il ricettario non regge 8.500 ricette.** Misurato su 8.500 ricette sintetiche con
  80.893 righe:

  | caso | oggi |
  |---|---|
  | senza soglia (le 100 più recenti) | 129 ms |
  | soglia «Ora» o «+3» su tutto il ricettario | **errore**: `availability_map` riceve un id per riga, duplicati compresi, e asyncpg accetta al massimo 32.767 parametri |
  | soglia «+3» dentro una categoria (~2.100 ricette) | **1,1 s** di mediana, 2,2 s di massimo |
  | ricerca testuale | 50 ms |

  L'errore scatta già intorno alle 3.300 ricette: l'import in produzione avrebbe rotto
  i filtri a metà strada. È la sesta lezione di `CLAUDE.md`, e il commento in
  `recipe_search.py` lo prevedeva («oltre qualche migliaio va misurata di nuovo, e se
  non regge la regola scende in SQL»).
- Senza parole cercate, il ricettario mostra le 30 più recenti fra le 100 più recenti,
  **senza paginazione**. Con 8.469 ricette, le altre si raggiungerebbero solo
  cercando.
- Le 26 ricette di semina hanno `source = 'dataset'` e `source_ref = 'seme iniziale'`.
  **Una è stata cucinata**: `cooking_events.recipe_id` è `ON DELETE SET NULL`, quindi
  l'evento resta, con il suo `snapshot`, senza ricetta collegata.

## 2. Le decisioni

1. **Le ricette di semina escono dalla produzione, non dal repo.** Sviluppo locale ed
   e2e le usano: `seed` senza flag le carica, e `style.spec.ts` e compagni ci contano.
   Quindi si **inverte il flag**: `python -m app.cli.seed` carica solo l'anagrafica, e
   `--con-ricette` carica anche le ricette. `--solo-ingredienti` resta accettato come
   sinonimo del default, perché è scritto nel README e nelle abitudini; un flag
   sconosciuto ora esce con codice 1 (era 0, voce di Parte X). In produzione, un seme
   rilanciato senza pensarci non le fa più tornare.
2. **Un comando le toglie, e prima dice cosa toglierebbe.**
   `python -m app.cli.drop_seed_recipes` elenca le ricette con
   `source = 'dataset' AND source_ref = 'seme iniziale'` e le cotture che perderanno il
   collegamento. Cancella solo con `--conferma`. È rieseguibile: la seconda volta non
   trova niente.
3. **`import_gz --tutto` svuota la sitemap.** Legge la sitemap **una volta**, poi va a
   lotti di `DEFAULT_LIMIT` (50) pagine. Dopo ogni lotto allinea i termini, fa decidere
   all'AI fino a `MAX_TERMS_PER_RUN` (60) termini in coda, e materializza le ricette
   pronte: il ricettario cresce mentre il comando gira. Finite le pagine, continua a
   decidere i termini rimasti a giri di 60, finché la coda è vuota o un giro non ne
   decide nessuno (credito finito, modello giù, risposte non verificabili). Si ferma
   come oggi quando la fonte rifiuta due volte di fila. Ogni lotto scrive una riga di
   avanzamento con l'ora, così il log in background si legge. Rilanciarlo riprende da
   dove era: le pagine prese non si riscaricano, e i termini in coda restano in coda.
   `--limit` resta com'è, e `--tutto` e `--limit` insieme sono un errore.
4. **Un termine chiesto in questo giro non si richiede in questo giro.**
   `pending_terms` accetta un `exclude`: senza, se i primi 60 termini per frequenza
   avessero risposte non verificabili, ogni giro rifarebbe le stesse 60 domande e il
   resto della coda non verrebbe mai chiesto. Con l'esclusione, un giro che non ha più
   niente di nuovo da chiedere chiude la fase dei termini.
5. **La soglia dei mancanti scende in SQL, la regola no.** Python decide, con
   `is_satisfied` di `domain/rules.py`, per ciascun ruolo quali ingredienti della
   dispensa lo soddisfano: al massimo qualche centinaio di id. SQL conta, per ogni
   ricetta, le righe il cui ingrediente non sta nell'insieme del proprio ruolo, e su
   quel numero filtra, ordina e pagina. Nessuna tabella di verità ricopiata in SQL:
   solo l'appartenenza a un insieme che la regola ha già deciso. Un test a tabella
   confronta il conteggio SQL con `missing_count` su ogni combinazione di ruolo e
   stato, così i due non possono divergere in silenzio.
6. **Senza parole cercate, il ricettario è sempre intero.** Il ramo senza ricerca non
   usa più la piscina delle 100 più recenti. Ordina tutto il ricettario per
   `(mancanti, titolo, id)`, cioè lo stesso ordine che la pagina già mostrava dentro la
   piscina («prima ciò che puoi davvero cucinare»), filtra per categoria, ingredienti e
   soglia in SQL, e restituisce una pagina con `OFFSET`/`LIMIT`. Per le sole ricette
   della pagina si caricano i requisiti in Python, e mancanti, cucinabilità e nomi dei
   mancanti li dà `rules.py`, come oggi.
7. **Con parole cercate non cambia niente**, salvo l'offset. I candidati restano i
   primi `CANDIDATE_POOL` di ciascuna graduatoria (una scelta già dichiarata in R3 e
   R7), e «Mostra altre» scorre dentro quei candidati: finisce prima di 8.469, e va
   bene così. Il limite resta scritto nel commento dove esiste.
8. **Offset, non cursore.** L'ordine per mancanti e titolo non ha un cursore naturale,
   e l'offset vale uguale per tutti i rami. Il difetto dell'offset è che un
   inserimento sopra la pagina (l'import che gira) sposta tutto in giù di uno. Si
   vedono doppioni, mai buchi, e il frontend scarta i doppioni per `id`. In
   brainstorming avevo proposto il cursore; questa è la correzione, con il motivo.
9. **`availability_map` riceve id distinti.** È la causa dell'errore misurato, e costa
   una riga. Con la decisione 5 il ramo senza ricerca non la chiama più su tutto il
   ricettario, ma la ricerca testuale sì, su un massimo di 200 candidati: meglio che
   non possa più fallire per numero di righe.

## 3. Le interfacce

- `GET /api/v1/recipes/search` accetta `offset` (intero ≥ 0, default 0). La risposta
  resta una lista: un frontend vecchio, servito dalla cache del service worker, non
  manda `offset` e continua a vedere la prima pagina.
- `search_recipes(..., offset: int = 0)`.
- `pending_terms(session, source, limit, exclude=())`.
- `import_gz`: `--tutto`. `run_import` resta com'è per `--limit`, e i due modi
  condividono le stesse funzioni interne (prendere un elenco di pagine; allineare,
  decidere e materializzare), così le regole di cortesia e di fermata stanno in un
  posto solo.
- `app.cli.drop_seed_recipes`: nuovo, `--conferma`.
- `app.cli.seed`: default solo anagrafica, `--con-ricette`, `--solo-ingredienti`
  sinonimo del default, flag sconosciuto → codice 1.

## 4. Lo schermo

`RecipeBookScreen` passa da `useQuery` a `useInfiniteQuery`, con la stessa chiave
`["recipes", …]`: gli `invalidateQueries({ queryKey: ["recipes"] })` sparsi nell'app
continuano a funzionare. Pagine da 30. La pagina successiva si chiede con
`offset = numero di ricette ricevute finora`, e c'è finché l'ultima pagina era piena.
L'elenco mostrato è la concatenazione senza doppioni per `id`.

In fondo all'elenco, un bottone **«Mostra altre»** (`buttonClasses("secondary")`,
bersaglio da 44px). Mentre carica diventa «Carico…» ed è disabilitato. Se la pagina
successiva fallisce, compare una riga «Non sono riuscito a caricarne altre.» e il
bottone resta lì per riprovare: mai un vicolo cieco. Le ricette già a video restano.
Quando non ce ne sono altre il bottone sparisce, senza frasi.

## 5. Fuori

- Il lancio dell'import, la cancellazione in produzione e la verifica dopo: sono il
  runbook.
- Un tetto di spesa nel codice (deciso: basta il limite di credito su OpenRouter).
- Scaricare le immagini: resta l'URL.
- La ricerca semantica in produzione (`INSTALL_EMBEDDINGS=0`): la questione vera lì è
  la RAM del modello di embedding su un server da 7,6 GB, non il vector store. È una
  decisione sua, non di R4.
- La revisione umana delle migliaia di decisioni dell'AI: la coda e l'annulla ci
  sono già, e la revisione resta a campione.
- R5 e R6, che R4 sblocca.
