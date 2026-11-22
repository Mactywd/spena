# L'LLM dell'import su Claude Haiku, con l'API di Anthropic — design

_2026-11-21. Voce del backlog «L'LLM passa da OpenRouter (Gemma) all'API di Anthropic con
Claude Haiku 5.5» (decisa da Mattia il 2026-10-20). Piano:
`docs/superpowers/plans/2026-11-21-llm-haiku.md`. Parte dalla catena dei Pasti con la chiave
API (`docs/superpowers/plans/2026-11-18-pasti-chiave-api.md`, che introduce
`ANTHROPIC_API_KEY`) e dalle sue correzioni (`2026-11-18-pasti-correzioni.md`)._

## 1. Perché

Oggi ogni lavoro dell'AI fuori dai Pasti — i termini dell'import (`term_decision`,
`term_collapse`), la bozza e la variante delle ricette, le forme delle unità, le figure, i
sostituti, gli abbinamenti CIQUAL e i pesi di S4 — passa da OpenRouter con
`google/gemma-4-26b-a4b-it`. Mattia ha deciso di portarli sull'API di Anthropic con Claude
Haiku 5.5, sui suoi crediti API: un fornitore solo per tutta l'AI dell'app, una chiave sola,
e un modello che segue le istruzioni meglio di un MoE da 3,8 miliardi di parametri attivi.

Tre cose cambiano insieme e non si possono separare:

- **il client**: `services/llm.py` parla con l'SDK ufficiale `anthropic` invece che con
  OpenRouter via `httpx`;
- **il costo**: OpenRouter lo dichiarava in `usage.cost`; Anthropic dà solo i token, quindi
  il costo lo calcola spena dai token e dal listino;
- **la regola «one provider» di `CLAUDE.md`**: le due strade verso un modello sono ora tutte e
  due di Anthropic, con la stessa chiave.

## 2. Le decisioni

### Di Mattia (2026-10-20 e 2026-11-21)

1. **Il modello è `claude-haiku-5-5` per ogni lavoro che oggi gira su Gemma.** Nessuno resta
   su OpenRouter.
2. **Un client solo al posto di quello di OpenRouter**, non due fornitori dietro un
   interruttore.
3. **La stessa `ANTHROPIC_API_KEY` dei Pasti**, con un limite di spesa nella console di
   Anthropic. Il rischio è scritto qui sotto (§8): un import grosso può consumare il credito
   che servirebbe alla chat dei Pasti.
4. **§9 della spec S4 è superato e non si costruisce** («modello più forte solo dove serve»,
   `OPENROUTER_MODEL_STRONG`, `--modello-forte`): Haiku è già il modello forte rispetto a
   Gemma.
5. **I piloti di S4 (`s4_pilot`) si rilanciano una volta sul server dopo il deploy**, da
   Mattia, per confrontare con le misure fatte su Gemma.
6. **Il motivo del guasto si vede a video** (2026-11-21). Il backend scrive una frase per
   tipo di guasto (§5), in un posto solo, come `failure_notice` dei Pasti, e la manda nel
   corpo del 503 con la stessa forma dei Pasti, `{"code": "llm_<tipo>", "detail": <frase>}`;
   «Sostituisci», che non risponde mai 503, la manda nel campo `ai_notice` della risposta. La
   coda dell'import, la bozza, la variante e «Sostituisci» mostrano quella frase al posto
   della loro frase generica, seguita dalla strada a mano di oggi; il frontend non calcola
   niente, e se il corpo non porta una frase mostra quella generica di oggi. La strada a mano
   resta com'è: mai un vicolo cieco.
7. **`httpx2` è una dipendenza dichiarata, fra le `dev`** (2026-11-21): arriva comunque con
   l'SDK, e i finti dei test lo importano.

### Tecniche, delegate a Claude (Mattia le rivede nel report)

8. **Il costo = token × listino nel codice**, per modello, in `app/domain/llm_pricing.py`
   (§4), scritto in `llm_calls.cost_usd`. Il commento di `llm_call.py` che spiegava perché il
   costo non si stimava si riscrive: valeva per OpenRouter, che instradava fra provider con
   prezzi diversi. Il precedente è dei Pasti, dove il costo è quello che Claude Code calcola
   dai token col suo listino.
9. **Due colonne nuove, `llm_calls.cache_read_tokens` e `llm_calls.cache_write_tokens`**
   (migrazione `0025`), così ogni costo si ricontrolla dalla sua riga. `prompt_tokens` resta
   «tutti i token del prompt», come con OpenRouter: quelli non in cache più quelli letti e
   scritti in cache.
10. **Il client è l'SDK ufficiale** (`AsyncAnthropic`), costruito in un posto solo
   (`client_options`) con la chiave dalle impostazioni e l'indirizzo
   `https://api.anthropic.com` scritto nel codice. Né l'indirizzo né la credenziale si
   prendono dall'ambiente: l'SDK altrimenti leggerebbe `ANTHROPIC_BASE_URL` e
   `ANTHROPIC_AUTH_TOKEN`, e la shell di un agente ha `ANTHROPIC_BASE_URL`. Per lo stesso
   motivo l'indirizzo non è un'impostazione: un campo `anthropic_base_url` di pydantic
   leggerebbe proprio `ANTHROPIC_BASE_URL`.
11. **I test sostituiscono solo il trasporto HTTP** (`httpx2.MockTransport` dentro
   `DefaultAsyncHttpxClient`), con le stesse opzioni del client di produzione: l'SDK vero
   costruisce la richiesta e legge la risposta anche sotto prova (prima lezione di
   `CLAUDE.md`). I finti di oggi, che rispondono con corpi di OpenRouter, si riscrivono con
   corpi dell'API Messages.
12. **Risposta strutturata con `output_config.format`** (`json_schema`) e gli schemi di oggi.
    Le unioni `{"type": ["string", "null"]}` diventano `anyOf` (`{"anyOf": [{"type":
    "string"}, {"type": "null"}]}`), che la documentazione delle structured outputs elenca
    fra le forme accettate; le liste di tipi non le elenca, e un 400 qui sarebbe ogni
    chiamata persa. `schema_name` non serve più e sparisce.
13. **Pensiero e sforzo per profilo.** Le domande di classificazione e decisione (termini,
    collasso, sostituti, unità, figure, CIQUAL, pesi) vanno con `thinking: {"type":
    "disabled"}` e `effort: "low"` (Haiku 5.5 accetta il pensiero spento fino a `high`): i
    loro `max_tokens` restano quelli di oggi e il pensiero non può consumarli. La bozza e la
    variante vanno con il pensiero adattivo a `effort: "low"` e un `max_tokens` più alto
    (6000 e 8000), così il pensiero non tronca la ricetta. Lo sforzo `low` di bozza e
    variante, con il tentativo solo del punto 20, resta una scelta tecnica di Claude: Mattia
    l'ha lasciata delegata il 2026-11-21, e nei primi usi veri guarda in «Spese dell'AI» se
    bozze e varianti si troncano o scadono (§9).
14. **Si legge il blocco di testo**, non il primo blocco (con il pensiero acceso la risposta
    può cominciare con un blocco `thinking`). `stop_reason` `max_tokens` e `refusal`
    diventano un guasto con il suo tipo (§5).
15. **La cache del prompt sulla decisione dei termini.** Oggi il termine viene per primo
    nella domanda e l'anagrafica dopo. Si rovescia: il prompt di sistema e l'anagrafica con
    le categorie formano il prefisso fisso, segnato `cache_control: {"type": "ephemeral"}`,
    e il messaggio porta solo il termine. Il primo termine di un lotto parte da solo e gli
    altri dopo: richieste parallele con lo stesso prefisso non leggono la cache che le altre
    stanno ancora scrivendo, e otto scritture al primo giro costerebbero otto volte.
    L'anagrafica vera supera di molto il prefisso minimo di Haiku 5.5 (512 token).
16. **Una chiamata per termine**, sotto il semaforo di oggi (`LLM_MAX_CONCURRENCY=8`). I lotti
    su Haiku e le Message Batches non sono in questa voce: due `idea` nuove nel backlog.
17. **Via OpenRouter**: ogni impostazione `OPENROUTER_*`, l'attribuzione (`HTTP-Referer`,
    `X-Title`), le preferenze di instradamento, `cli/llm_prices.py` e il suo test.
    L'impostazione del modello diventa `LLM_MODEL=claude-haiku-5-5`. Le parole a video che
    nominano OpenRouter («Spese dell'AI») si riscrivono (§6).
18. **Le righe vecchie di `llm_calls` restano come sono**, con il loro modello e il costo di
    OpenRouter. La stima del `--dry-run` dei sostituti (`measured_cost`) conta solo le
    chiamate del modello di adesso.
19. **Il guasto ha un tipo** (§5). I tipi terminali fermano il fan-out e i lotti al primo; gli
    altri lasciano la voce in coda. Una chiamata fallita registra l'uso che la risposta
    aveva (una risposta tagliata o rifiutata ha token e costo), non un uso vuoto.
20. **Tentativi**: quelli dell'SDK (2, su 408/409/429/5xx/529 e rete), con un tempo per
    tentativo di 45 s (`LLM_TIMEOUT_SECONDS`, oggi 60 su un tentativo solo). La bozza e la
    variante, che passano da Nginx con il suo tempo di lettura di 60 s, hanno un tentativo
    solo da 50 s: tre da 45 diventerebbero un 504. Scelta tecnica di Claude, lasciata
    delegata da Mattia il 2026-11-21 (vedi il punto 13 e §9).
21. **Il controllo «c'è la chiave?»** che oggi fa `build_headers()` prima di aprire il client
    (`decide.py`, `substitutions.py`, `llm_prices.py`) diventa `ensure_llm_configured()`, che
    guarda solo le impostazioni.
22. **H4, la regola degli utensili per la bozza e la variante.** Finisce con «se senza quello
    strumento il piatto non si fa, dillo nella descrizione.», perché quelle due rispondono con
    uno schema stretto e possono dirlo solo lì. La chat dei Pasti tiene la frase di oggi (la
    sua formulazione è di un altro piano).
23. **Un comando di controllo, `python -m app.cli.check_llm [--prova]`**, al posto di
    `llm_prices`: stampa il modello, se il listino lo conosce e se la chiave c'è (mai il
    valore); con `--prova` fa una chiamata minima vera.

`decide_grams` di S4 ha una correzione di robustezza in un altro piano (s4-candidati, figlio
di questo): qui il suo ciclo cambia solo dove la chiamata cambia.

## 3. La richiesta

Ogni chiamata è `client.messages.create` con:

- `model` = `LLM_MODEL`; `max_tokens` del chiamante;
- `system` = un blocco di testo, con `cache_control: {"type": "ephemeral"}` solo dove il
  chiamante lo chiede (oggi solo `term_decision`);
- `messages` = un messaggio `user`, il testo del chiamante. Niente prefill, niente
  `temperature`, `top_p`, `top_k` (Haiku 5.5 rifiuta i valori non di default);
- `thinking` = `{"type": "disabled"}` o `{"type": "adaptive"}` secondo il profilo;
- `output_config` = `{"effort": <profilo>, "format": {"type": "json_schema", "schema": <schema>}}`.

## 4. Il costo

Per una risposta con `input_tokens` = I (non in cache), `cache_creation_input_tokens` = W,
`cache_read_input_tokens` = R e `output_tokens` = O (che comprende il pensiero), con P = I + W + R:

```
se P ≤ 100.000:  ingresso = 0,10 $/M, uscita = 0,50 $/M
altrimenti:      ingresso = 0,50 $/M, uscita = 2,50 $/M
costo = (I × ingresso + W × ingresso × 1,25 + R × ingresso × 0,10 + O × uscita) / 1.000.000
```

Fonte: il listino di Claude Haiku 5.5 della skill `claude-api` (aggiornato al 2026-11-03):
due listini secondo la lunghezza del prompt, letture della cache a 0,1× l'ingresso,
scritture a 5 minuti a 1,25×. Che la soglia dei 100.000 si misuri su P (cache compresa) è
un'assunzione: in spena nessun prompt ci arriva vicino (il più lungo, la decisione di un
termine con l'anagrafica intera, è di qualche migliaio di token). Un modello che il listino
non conosce ha costo `NULL`: l'assenza è la verità, come per i nutrienti. Il costo registrato
è una stima nostra e Mattia lo confronta una volta con la console (§9): è lì che si vede
anche se l'assunzione sulla soglia regge. L'assunzione resta scritta nel codice, nel
docstring di `llm_pricing.py`.

## 5. I guasti e le loro frasi

`LlmUnavailable` porta un tipo (`LlmFailureKind`), l'uso della risposta se c'era, e una frase
in italiano (`notice`), scritta una volta sola in `LLM_FAILURE_NOTICES`. È una frase da
schermo (deciso da Mattia, §2.6), nel tono degli avvisi dei Pasti: dove il senso è lo stesso
le parole sono le loro, con «L'AI» al posto di «Claude». Va nel corpo dei 503 della stesura,
della variante e della coda dell'import, nella forma dei Pasti (`{"code": "llm_<tipo>",
"detail": <frase>}`), nel campo `ai_notice` di «Sostituisci» e nel `stopped_notice` di un
giro della coda fermato a metà; con il dettaglio tecnico fra parentesi, nelle righe dei
comandi.

| Tipo | Quando | Terminale | Frase |
|---|---|---|---|
| `not_configured` | `ANTHROPIC_API_KEY` vuota o assente | sì | «L'AI non è collegata: manca la chiave API sul server.» |
| `auth` | 401, 403 | sì | «L'AI non risponde: la chiave API non vale più (sbagliata o revocata). Va sostituita nel .env del server.» |
| `credit` | 402, `billing_error`, o un 400 che parla di «credit balance» | sì | «L'AI non risponde: il credito della chiave API è finito. Va ricaricato nella console di Anthropic.» |
| `rate_limit` | 429 dopo i tentativi | sì | «L'AI non risponde: hai raggiunto il limite di frequenza della chiave API, riprova fra poco.» |
| `rejected` | gli altri 4xx (schema, modello, richiesta) | sì | «L'AI non risponde: Anthropic ha rifiutato la richiesta (modello o schema non accettati). Il dettaglio è nei log del backend.» |
| `transient` | 5xx, 529, rete, tempo scaduto, dopo i tentativi | no | «L'AI non risponde in questo momento: riprova fra poco.» |
| `truncated` | `stop_reason` `max_tokens` | no | «La risposta dell'AI si è interrotta prima della fine: riprova.» |
| `refusal` | `stop_reason` `refusal` | no | «L'AI ha rifiutato di rispondere a questa richiesta.» |
| `invalid` | nessun blocco di testo, JSON rotto, non un oggetto | no | «La risposta dell'AI non si può usare: riprova.» |

Il testo dell'eccezione (`str`) è `ANTHROPIC_API_KEY non configurata` per il primo tipo, e
«‹frase› (‹dettaglio tecnico›)» per gli altri (per esempio `HTTP 402 billing_error`,
`stop_reason max_tokens`, `ReadTimeout`): va nei log e nei comandi, mai a video. Nessuna
frase nomina una variabile o un codice HTTP. Un «credit balance» dentro un 400 è riconosciuto
perché, a memoria di chi usa l'API, il credito finito arriva anche così e non solo come 402.

**Terminale** vuol dire che rifare la domanda subito darebbe lo stesso esito per ogni voce.
Nel fan-out dei termini le domande non ancora partite non partono, il collasso si salta, e i
termini restano in coda; se il guasto arriva alla prima domanda, la rotta della coda risponde
503 con la frase (dopo aver salvato la riga di spesa). Nei sostituti, le domande dello stesso
lotto non ancora partite non partono, e il lancio si ferma dopo il lotto come oggi. I lotti
di S4 e delle figure si fermano già al primo guasto di qualunque tipo, e così restano.

### Dove si vede la frase

Lo schermo mostra la frase che riceve, seguita dalla sua strada a mano, che è fissa e
quella di oggi; senza frase (un corpo senza `code` che cominci per `llm_`, un errore di
rete, un 500), la frase generica di oggi. Il colore è quello di ogni guasto dell'AI,
l'ambra di `Alert tone="degraded"`: nessun colore nuovo.

| Dove | Con la frase | Senza (oggi, invariata) |
|---|---|---|
| Coda dell'import, «Riprova con l'AI» (503) | «‹frase› Decidi a mano qui sotto: la coda funziona.» | «L'AI non è disponibile: decidi a mano qui sotto, la coda funziona.» |
| Coda dell'import, giro fermato a metà (200 con `stopped_notice`) | il messaggio del giro di oggi, e sotto la frase | il messaggio del giro di oggi |
| Bozza AI (503) | «‹frase› Il modulo qui sotto resta tuo: scrivi la ricetta a mano e salvala.» | «La stesura AI non è disponibile. Il modulo qui sotto resta tuo: scrivi la ricetta a mano e salvala.» |
| Variante (503) | «‹frase› Questa ricetta resta com'è.» | «L'AI non ha risposto: questa ricetta resta com'è. Riprova fra poco.» |
| «Sostituisci» (200 con `ai_failed` e `ai_notice`) | la frase, sopra «Nessun suggerimento ancora.» con «Riprova» e «Scrivi tu» | «Nessun suggerimento ancora.» con «Riprova» e «Scrivi tu» |

In «Sostituisci» una risposta dell'AI che non si verifica contro l'anagrafica (oggi
`failed` senza un guasto) porta la frase di `invalid`.

## 6. Cosa sparisce, cosa cambia nome

- `OPENROUTER_API_KEY`, `OPENROUTER_MODEL`, `OPENROUTER_BASE_URL`, `OPENROUTER_APP_TITLE`,
  `OPENROUTER_APP_URL`, `OPENROUTER_PROVIDER_ONLY`: via da `config.py`, `.env.example`,
  `.env.e2e`, `README.md`. Al loro posto `ANTHROPIC_API_KEY` (già dei Pasti) e
  `LLM_MODEL=claude-haiku-5-5`; restano `LLM_TIMEOUT_SECONDS` (45) e `LLM_MAX_CONCURRENCY`
  (8), e nasce `LLM_MAX_RETRIES` (2).
- `build_headers`, `build_provider_preferences`, `schema_name`: via.
- `app/cli/llm_prices.py` e `tests/test_llm_prices_cli.py`: via; al loro posto `check_llm`.
- `anthropic` torna nel `pyproject.toml`, ma come **dipendenza di base fissata**
  (`anthropic==<versione>`), mai come extra: il deploy in cui mancava dall'immagine è la
  storia che `test_image_dependencies.py` ricorda, e il test ora difende il contrario di
  prima.
- «Spese dell'AI»: il sottotitolo «Quanto ha speso l'AI su OpenRouter, e per cosa.» diventa
  «Quanto ha speso l'AI con la chiave API di Anthropic, e per cosa.»; «‹n› senza un costo
  dichiarato da OpenRouter (…)» diventa «1 senza un costo (di solito, una chiamata fallita):
  non è nel totale.» e «‹n› senza un costo (di solito, chiamate fallite): non sono nel
  totale.».
- I 503 dell'AI perdono i prefissi di oggi («stesura AI non disponibile: …», «il
  riconoscimento non è disponibile (…): decidi a mano, la coda funziona.»): il corpo è
  `{"code", "detail"}` come nei Pasti. Nel frontend nasce un solo lettore di quel corpo, e i
  quattro schermi di §5 lo usano.

## 7. Cosa cambia in `CLAUDE.md`

- Il paragrafo sull'LLM («An LLM (`google/gemma-4-26b-a4b-it`, reached through OpenRouter…»)
  dice Haiku via l'API Messages con l'SDK `anthropic`, il client costruito in un posto solo e
  provato sostituendo solo il trasporto, e il costo calcolato da spena con le colonne della
  cache.
- Il paragrafo «A second path to a model, on purpose» dice che le due strade sono tutte e due
  di Anthropic, sulla stessa chiave: l'API Messages con Haiku per l'import, le bozze e le
  varianti; l'Agent SDK con Opus per i Pasti. Restano due strade con due lavori, non due
  implementazioni dello stesso lavoro, e tutte e due girano in produzione.

Il testo esatto è nel Task 9 del piano.

## 8. Rischi

- **Il credito condiviso.** La chat dei Pasti e l'import pagano dalla stessa chiave. Un
  import di migliaia di termini, o un `decide_*` lanciato senza `--limit`, può finire il
  credito a metà settimana, e allora anche la chat dice «credito finito». Il limite di spesa
  nella console protegge il portafoglio, non la chat. Sui consumi misurati (quasi tutto
  `term_decision`) un import intero costa pochi dollari, meno con la cache; il `--dry-run`
  dei sostituti stima prima di spendere.
- **Il costo è una stima nostra**, da un listino scritto nel codice: se Anthropic cambia
  prezzo, il listino va aggiornato a mano. La console resta la verità.
- **Il modello cambia le risposte.** Le decisioni di Haiku non sono quelle di Gemma; la coda
  resta la revisione, e il pilota di S4 dice se la qualità è salita.
- **Il tempo di una richiesta alla coda dell'import** (`POST /imports/terms/decide`) passa da
  Nginx con 60 s: con Anthropic degradato, tre tentativi per domanda possono superarli e il
  telefono vede un errore generico. La coda resta usabile a mano.
- **`httpx2` arriva con l'SDK**, e Mattia l'ha voluto dichiarato fra le `dev` (§2.7). Fino a
  oggi non era installato, e Starlette ne parla all'import del suo client di test
  (`pyproject.toml`, `filterwarnings`; l'idea del backlog «La suite del backend stampa ancora
  un avviso di Starlette…»): la suite intera, dopo l'installazione, dice se l'avviso sparisce
  o se resta qualcosa da fare, e il backlog lo registra.

## 9. Dopo il deploy (solo Mattia)

1. **La chiave.** La stessa `ANTHROPIC_API_KEY` dei Pasti, già nel `.env` del server, con il
   limite di spesa nella console. `OPENROUTER_*` nel `.env` non servono più: si possono
   togliere, e la chiave di OpenRouter si revoca dal loro sito quando le spese vecchie non
   servono più.
2. **Il deploy di sempre**, con `-f docker-compose.prod.yml`. La `0025` gira all'avvio.
3. **Il controllo**: `docker compose -f docker-compose.prod.yml exec backend python -m
   app.cli.check_llm --prova`. Expected: `modello: claude-haiku-5-5`, `listino: noto`,
   `chiave API: presente`, `prova: ok` con i token e il costo (una frazione di centesimo).
4. **Qualche decisione vera**: «Riprova con l'AI» sulla coda dell'import con una manciata di
   termini, poi «Decisioni recenti»: le decisioni hanno senso, e in «Spese dell'AI» la
   sezione dei termini ha un costo. Dal secondo termine del lotto in poi, `llm_calls` ha
   `cache_read_tokens` valorizzato.
5. **La bozza e la variante nei primi usi veri.** Lo sforzo `low` e il tentativo solo da
   50 s sono una scelta tecnica di Claude (§2.13, §2.20): nelle prime bozze e varianti dal
   telefono Mattia guarda se arrivano entro il minuto, e in «Spese dell'AI» le chiamate
   fallite delle due sezioni. Un troncamento («La risposta dell'AI si è interrotta…») o un
   tempo scaduto («L'AI non risponde in questo momento…») ripetuti vanno detti alla prossima
   fase giorno, che alza `max_tokens` o cambia profilo.
6. **I piloti di S4**: `s4_pilot` una volta, da confrontare con le misure su Gemma.
7. **Il costo**: dopo qualche giorno, il totale di «Spese dell'AI» per le sezioni dell'import
   confrontato con la console di Anthropic. È anche il controllo dell'assunzione di §4 (la
   soglia dei 100.000 token che conta la cache): se i due totali differiscono di molto, il
   listino o l'assunzione vanno corretti.
