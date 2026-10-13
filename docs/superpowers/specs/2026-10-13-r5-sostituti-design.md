# R5, «Sostituisci» un ingrediente: design

_2026-10-13, fase giorno. Voce [R5] di `docs/prossimi-passi.md` («## R5. Sostituisci
ingrediente»); leggi anche R6 e M1. Piano: `docs/superpowers/plans/2026-10-13-r5-sostituti.md`._

## 1. Contesto

Dentro una ricetta, accanto a ogni ingrediente, un tasto «Sostituisci». Tre esiti, e sono
tre cose diverse: **uno o più sostituti** (pollo → tacchino), **si può omettere** (una
spezia che non rompe il piatto), **insostituibile** (la farina nel pane). La risposta è
**precalcolata e salvata**, non chiesta all'AI a ogni tocco.

I numeri della ricerca del 2026-10-13: ~884 ingredienti, 8.454 ricette, 83.343 righe. Una
chiamata `term_decision` (l'anagrafica intera nel prompt, `_question` in
`backend/app/services/recipe_import/decide.py`) costa ~0,00042 $ misurati; Gemma via
Darkbloom 0,042 / 0,22 $ per milione di token. Il ruolo primary/secondary di ogni riga c'è
già. Il contesto dolce/salato di una ricetta si ricava senza AI da `recipes.category`, che
l'import riempie da `recipeCategory` di GialloZafferano: i valori nel codice e nelle prove
sono «Dolci e Desserts», «Primi piatti», «Secondi piatti», «Antipasti», «Dolci»; le
ricette scritte a mano e quelle del seme non hanno categoria.

## 2. Decisioni di Mattia (2026-10-13)

1. **Granularità: ingrediente × {dolce, salato}**, con la doppia voce solo dove serve, più
   la **correzione a mano per singola ricetta**. Forma e parole della correzione: Claude.
2. **Un sostituto è solo un ingrediente alimentare dell'anagrafica**, con una nota breve
   facoltativa («metà dose»). Una risposta dell'AI che nomina qualcosa fuori anagrafica,
   non alimentare, l'ingrediente stesso o un doppione **si scarta**: mai applicata una
   risposta non verificabile, come per l'import.
3. **«Si può omettere» soddisfa qualunque riga** (anche primary) ai fini di R6; la ricetta
   dirà «senza X». R6 resta una voce a sé, bloccata da R5: qui **non** si costruisce il
   filtro «cucinabili con sostituti», ma il dato lo permette e la regola è scritta (§8).
4. **Le risposte dell'AI si vedono subito**, segnate «decise dall'AI» (`decided_by`), e si
   rivedono dopo in Anagrafica, nella scheda dell'ingrediente, in una sezione «Sostituti»
   sul modello delle decisioni della coda. **Una correzione umana non viene mai
   sovrascritta da un ricalcolo.**

Vincoli dati con le decisioni: il calcolo è un comando `python -m app.cli.<nome>` sul
modello di `decide_emoji` (piano S12) — a lotti, commit per lotto, riprende solo quel che è
scoperto, `--limit` / `--dry-run`, una `LlmCallSite` nuova; un ingrediente senza risposta,
toccando «Sostituisci», si calcola sul momento e si salva; se l'AI non risponde, «Nessun
suggerimento ancora» e una strada a mano; la fusione di due ingredienti sposta i sostituti
sul vincitore; test coi finti registrati dell'LLM, nessuna rete; il lancio vero in
produzione è di Mattia, prima con `--limit 20`.

## 3. Decisioni di Claude, su delega di Mattia

Tecniche o estetiche, reversibili.

1. **La regola del contesto** (`recipe_context`, `backend/app/domain/substitutions.py`): una
   ricetta è **dolce se la prima parola della sua categoria è «dolci»** (senza maiuscole né
   spazi ai lati) — «Dolci e Desserts», «Dolci» —, **salata in ogni altro caso**,
   categoria assente compresa. «Lievitati» (pane e pizza, ma anche brioche), «Bevande»,
   «Marmellate» vanno fra le salate: sono pochi, e dove la voce generale sbaglia c'è la
   correzione della ricetta. La prima parola e non l'inizio della stringa, perché
   «Dolcificanti» non è un dolce.
2. **Una «voce» è un ingrediente in un contesto in cui compare.** La voce dolce di un
   ingrediente esiste solo se almeno una ricetta dolce non eliminata lo usa (e così per la
   salata): è la «doppia voce solo dove serve». Un ingrediente in nessuna ricetta non ha
   voci, e non si chiede niente all'AI.
3. **I dati** (migrazione `0015`, numero riservato dalla fase giorno): una tabella
   `ingredient_substitutions` per due ambiti — la **voce generale** (`recipe_id` NULL,
   `context` «dolce» o «salato», `decided_by` «ai» o «human») e la **correzione di una
   ricetta** (`recipe_id` presente, `context` NULL, sempre «human») —, con `verdict`
   «substitutes» | «omit» | «irreplaceable»; e `substitution_options`, un sostituto per riga
   (`substitute_id` verso `ingredients`, `note` fino a 60 caratteri, `position`). Due indici
   unici parziali: una voce generale per ingrediente e contesto, una correzione per ricetta
   e ingrediente. Chiavi esterne in `CASCADE`: un ingrediente o una ricetta che spariscono
   si portano via le loro risposte.
4. **Una risposta «sostituti» senza più sostituti visibili vale come nessuna risposta**:
   l'unico sostituto è stato cancellato (un annullamento della coda), o è diventato non
   alimentare. A video «Nessun suggerimento ancora», e il calcolo la richiede. È la regola
   che rende innocue tutte le strade che cancellano un ingrediente, senza che ognuna debba
   sapere dei sostituti. Vale anche per una risposta scritta a mano: non resta niente da
   proteggere.
5. **Da 1 a 3 sostituti**, nell'ordine in cui l'AI (o la persona) li dà, dal migliore.
6. **Una chiamata per voce**, con l'anagrafica alimentare intera nel prompt (solo i nomi,
   tolto l'ingrediente stesso) e lo schema JSON stretto: `{"esito": "sostituti" | "omettere"
   | "insostituibile", "sostituti": [{"nome", "nota"}]}`. Una per voce e non un lotto per
   chiamata per la ragione scritta in testa a `decide.py`: un modello piccolo che deve
   riecheggiare venti nomi si sfalda, e il degrado non si vede. La verifica: l'esito
   conosciuto; per «omettere» e «insostituibile» la lista vuota; per «sostituti» da 1 a 3
   nomi, ognuno uguale (senza maiuscole né spazi ai lati) al nome canonico di un ingrediente
   alimentare, mai l'ingrediente stesso, mai due volte, con la nota fino a 60 caratteri.
   **Un solo difetto scarta tutta la risposta** di quella voce (decisione 2).
7. **L'AI scrive solo dove non c'è una risposta**, e lo controlla nella stessa scrittura
   (`INSERT … ON CONFLICT DO NOTHING` sull'indice parziale): una correzione fatta mentre
   il modello risponde vince.
8. **Il comando** è `python -m app.cli.decide_substitutes`, con la sezione della spesa
   `LlmCallSite.INGREDIENT_SUBSTITUTES = "ingredient_substitutes"`. Chiede le voci scoperte
   dalle più usate (più ricette prima), a lotti da 20 (`SUBSTITUTE_BATCH`) con le chiamate
   del lotto in parallelo sotto `LLM_MAX_CONCURRENCY`, commit dopo ogni lotto; al primo
   lotto con un guasto dell'AI si ferma. `--limit N` chiede al massimo N voci; `--dry-run`
   non chiama nessuno e non scrive: dice quante voci sono scoperte, quali chiederebbe e,
   se ci sono già chiamate misurate, il costo stimato. Stampa una riga per voce decisa
   («pollo (salato): tacchino (metà dose), coniglio»), la spesa del lancio e, per ultima,
   quante voci restano.
9. **Sul momento**: il pannello legge la risposta (`GET`); se non c'è, chiede al server di
   calcolarla (`POST …/ask`), che chiama l'AI per quella voce, la verifica, la salva e la
   rende. Senza chiave non si chiama nessuno e non si registra niente.
10. **La correzione della ricetta si scrive dalla ricetta, la voce generale da
    Anagrafica.** Dalla ricetta, «Non va bene qui» (e «Scrivi tu», quando non c'è un
    suggerimento) scrive una correzione **solo per questa ricetta**; «Torna al suggerimento
    generale» la toglie. In Anagrafica si corregge la voce generale («Correggi», «Scrivi
    tu») e si conferma quella dell'AI («Va bene così», che la fa diventare «scelta a mano»).
    Una regola sola, e nessuna scelta di ambito dentro un modulo stretto.
11. **Nel dettaglio**: in fondo a ogni riga d'ingrediente un pulsante di sola icona
    (`IconArrowsExchange`), nome «Sostituisci {nome}», 44 × 44 px; apre il pannello sotto la
    riga, rientrato sotto il nome, e un secondo tocco lo chiude. Ogni riga ha il suo, e due
    pannelli aperti insieme non si danno fastidio. Accanto a ogni sostituto il pallino della
    dispensa e «ce l'hai» quando in dispensa soddisfa la riga (la regola di §8, per riga),
    «non basta» quando è quasi finito e la riga è principale.
12. **In Anagrafica**: la sezione «Sostituti» in fondo alla scheda di un ingrediente
    alimentare, una scheda per contesto («Nei piatti salati · in 120 ricette», «Nei dolci ·
    in 3 ricette»), la voce dell'AI segnata «Deciso dall'AI: da rivedere.» in ambra (il
    colore di «funziona, ma non del tutto»), e sotto «Corretto a mano in N ricette.» se ci
    sono correzioni di ricette. Un non alimentare non ha la sezione.
13. **La fusione** (`merge_ingredients`, `move_substitutions`): dove il perdente è un
    sostituto, al suo posto va il vincitore, mai due volte nella stessa risposta e mai come
    sostituto di sé stesso; le voci generali del perdente passano al vincitore, e dove ne
    hanno una tutti e due vince quella con una risposta, poi quella scritta a mano, poi
    quella del vincitore; le correzioni di ricetta seguono la riga della ricetta, e se la
    ricetta ne ha una per tutti e due resta quella del vincitore; una risposta «sostituti»
    rimasta senza sostituti si toglie.

## 4. Comportamento, passo per passo

**Nella ricetta.** Tocco su «Sostituisci pasta»:

1. il pannello si apre e dice «Cerco cosa usare al posto di pasta…»;
2. `GET /api/v1/recipes/{id}/substitutes/{ingredient_id}` risponde la risposta che vale per
   questa riga: la correzione della ricetta se c'è, altrimenti la voce generale del
   contesto della ricetta, altrimenti nessuna;
3. se non ce n'è nessuna, `POST …/ask`: il server chiede all'AI la voce generale, la
   verifica e la salva; risponde la riga com'è dopo, con `ai_failed` vero se l'AI non ha
   risposto o ha risposto qualcosa che non si applica;
4. il pannello mostra la risposta, o «Nessun suggerimento ancora.» con «Riprova» (che rifà
   i passi 2–3) e «Scrivi tu».

Con una risposta: «Al posto di pasta:» e i sostituti, o la frase dell'omettere o
dell'insostituibile; sotto, da dove viene; sotto ancora «Non va bene qui» (voce generale)
oppure «Cambia» e «Torna al suggerimento generale» (correzione della ricetta). «Non va bene
qui», «Cambia» e «Scrivi tu» aprono lo stesso modulo: i tre esiti come pastiglie, per
«Un altro ingrediente» il selettore dell'anagrafica alimentare (fino a tre) con una nota per
ciascuno e la ✕ per toglierlo, «Salva per questa ricetta» e «Annulla». Salvato o annullato,
il modulo si chiude e il fuoco torna sul pulsante che l'ha aperto.

**In Anagrafica.** La sezione legge `GET /api/v1/ingredients/{id}/substitutes`; «Correggi»,
«Scrivi tu» e «Va bene così» scrivono con `PUT /api/v1/ingredients/{id}/substitutes/{contesto}`
(«Va bene così» manda la risposta com'è: la voce diventa `human`). Dopo una scrittura i
pannelli delle ricette rileggono.

**Le API.**

| Rotta | Cosa |
|---|---|
| `GET /api/v1/recipes/{recipe_id}/substitutes/{ingredient_id}` | la risposta della riga; 404 se la ricetta o la riga non c'è |
| `POST …/ask` | calcola la voce generale se manca, poi come la `GET`; mai 503: `ai_failed` |
| `PUT …` corpo `{verdict, substitutes: [{ingredient_id, note}]}` | la correzione della ricetta; 422 con la frase |
| `DELETE …` | toglie la correzione; 204 anche se non c'era |
| `GET /api/v1/ingredients/{id}/substitutes` | i contesti dell'ingrediente con la voce, le ricette, le correzioni |
| `PUT /api/v1/ingredients/{id}/substitutes/{dolce\|salato}` | la voce generale, scritta a mano; 422 con la frase |

La risposta di una riga: `ingredient_id`, `ingredient_name`, `context`, `scope`
(`"recipe"` | `"general"` | null), `verdict` | null, `decided_by` | null, `substitutes`
(`ingredient_id`, `name`, `note`, `availability`, `satisfied`), `ai_failed`.

I rifiuti di una risposta scritta a mano (422, `detail`), esatti:

- «Scegli almeno un ingrediente da usare al suo posto.»
- «Chi si omette o è insostituibile non ha sostituti: toglili, poi salva.»
- «Al massimo tre sostituti: togline uno, poi salva.»
- «Uno dei sostituti scelti non è più in anagrafica: toglilo e scegline un altro.»
- ««Pasta» non può sostituire sé stesso: scegli un altro ingrediente.»
- ««Detersivo» non è un alimento: non può sostituire un ingrediente.»
- ««Tacchino» è scelto due volte: tienilo una volta sola.»
- «La nota per «Tacchino» è troppo lunga: bastano poche parole, al massimo 60 caratteri.»
- (solo in Anagrafica) ««Detersivo» non è un alimento: non ha sostituti.»

## 5. Parole a video

Esatte. Il nome dell'ingrediente dentro una frase o un nome accessibile resta minuscolo; a
inizio riga prende la maiuscola, solo a video.

Nella ricetta: «Sostituisci {nome}» (nome del pulsante); «Cerco cosa usare al posto di
{nome}…»; «Al posto di {nome}:»; «ce l'hai»; «non basta»; «Si può omettere: il piatto riesce
anche senza {nome}.»; «Insostituibile: senza {nome} il piatto non si fa.»; «Suggerito
dall'AI per i piatti salati.» / «… per i dolci.»; «Scelto a mano per i piatti salati.» /
«… per i dolci.»; «Scelto a mano per questa ricetta.»; «Non va bene qui»; «Cambia»; «Torna
al suggerimento generale»; «Non sono riuscito a tornare al suggerimento generale. Riprova.»;
«Nessun suggerimento ancora.»; «Riprova»; «Scrivi tu»; «Non sono riuscito a leggere i
sostituti.»; «Questo ingrediente non è più nella ricetta: ricarica la pagina.».

Il modulo: «Al posto di {nome}, in questa ricetta:» (in Anagrafica «Al posto di {nome}, nei
piatti salati:» / «…, nei dolci:»); le pastiglie «Un altro ingrediente», «Si può omettere»,
«Insostituibile»; il selettore «Cosa usare al suo posto», poi «Aggiungine un altro»; sotto
di lui, se la ricerca non risponde, «Puoi scegliere «Si può omettere» o «Insostituibile».»,
e se non trova niente «Non è in anagrafica: un sostituto si sceglie fra gli ingredienti che
ci sono.»; la nota «Nota per {nome}» col segnaposto «Nota, per esempio: metà dose»; «Togli
{nome}»; «Salva per questa ricetta» (in Anagrafica «Salva»), che non ancora pronto dice
«Scegli almeno un ingrediente.»; «Annulla»; il rifiuto del server com'è, ogni altro guasto
«Non sono riuscito a salvare. Riprova.».

In Anagrafica: «Sostituti»; «Nei piatti salati» / «Nei dolci» con «· in 1 ricetta», «· in N
ricette», «· in nessuna ricetta»; «Deciso dall'AI: da rivedere.»; «Scelto a mano.»; «Va bene
così», «Correggi», «Scrivi tu» (nomi accessibili «Va bene così: nei piatti salati» e simili,
perché le schede sono due); «Nessun suggerimento ancora: lo chiedo all'AI la prima volta che
lo sostituisci in una ricetta.»; «Non è in nessuna ricetta: i sostituti servono dentro una
ricetta.»; «Corretto a mano in 1 ricetta.» / «Corretto a mano in N ricette.»; «Carico…»;
«Non sono riuscito a leggere i sostituti.» con «Riprova» (nome accessibile «Riprova a
leggere i sostituti»).

## 6. Il costo

Una chiamata per voce, con ~850 nomi alimentari nel prompt: ~0,0004 $, come
`term_decision`. Le voci sono gli ingredienti per i contesti in cui compaiono: fra 900 e
1.800, stimate ~1.250 (i dolci sono una parte del ricettario). In tutto **~0,5 $**, sotto il
tetto di 1 $ al giorno; `--dry-run` dopo un `--limit 20` dà la stima misurata, e se supera
0,8 $ il lancio si divide in due giorni con `--limit`. Ogni «Sostituisci» su una voce
scoperta costa una chiamata.

## 7. La fusione e le cancellazioni

Vedi §3.13 per la fusione. Le altre strade che cancellano un ingrediente (l'annullamento di
una decisione della coda, `delete_ingredient_if_unused`) o una ricetta (l'import che la
rifà) non sanno niente dei sostituti: le chiavi esterne in `CASCADE` tolgono le righe, e la
regola di §3.4 fa il resto. **Una correzione di ricetta vive con la ricetta**: se l'import
la rifà da capo (l'annullamento o la fusione di un suo termine), la correzione se ne va con
la ricetta vecchia (deciso da Mattia il 2026-10-13, §10).

## 8. La regola per R6 (non costruita qui)

R6 dirà «cucinabile con sostituti». Con i dati di R5 la regola è, per ogni riga della
ricetta:

- la riga è **soddisfatta** come oggi (`is_satisfied(role, availability)`) → conta;
- altrimenti si guarda la risposta che vale per quella riga (la correzione della ricetta,
  se c'è, altrimenti la voce generale del contesto della ricetta, e solo se «risponde», §3.4):
  - **«si può omettere»** → la riga conta come soddisfatta, qualunque sia il ruolo (anche
    primary), e la ricetta dirà «senza X»;
  - **«sostituti»** → la riga conta se **almeno un sostituto** in dispensa soddisfa la stessa
    regola della riga: per una primary `available`, per una secondary `available` o `low`
    (`is_satisfied(role, disponibilità del sostituto)`);
  - **«insostituibile»**, o nessuna risposta → la riga resta mancante.
- **Un passo solo**: i sostituti di un sostituto non contano.

R5 calcola già `satisfied` per ogni sostituto nella risposta di una riga (la seconda metà
della regola); R6 dovrà farlo in SQL o in blocco, sul ricettario intero, e la forma della
scala («cucinabile» come gradino) resta la sua domanda.

## 9. Fuori scope

- Il filtro «cucinabili con sostituti» (R6); il motore di suggerimento (M1).
- Un elenco di tutte le voci dell'AI da rivedere, fuori dalla scheda dell'ingrediente.
- Chiedere all'AI da Anagrafica («Chiedi all'AI»): la voce si chiede dalla ricetta, o col
  comando.
- Sostituti che non sono nell'anagrafica, o che si creano dal modulo.
- Le quantità dei sostituti oltre la nota («metà dose» è testo, non si riscala).
- Rifare con l'AI una voce già decisa (si corregge a mano).

## 10. La correzione di una ricetta che l'import rifà (deciso da Mattia il 2026-10-13)

Se un termine di una ricetta importata si annulla nella coda o si fonde in Anagrafica,
l'import cancella la ricetta e la ricrea dal `payload` con un id nuovo: le cotture le
ritrova (`cooking_event_ids`), le correzioni dei sostituti no. Le opzioni erano tre: (a) la
correzione **si perde** — è raro, e si rifà in due tocchi; (b) correggere i sostituti
prende in carico la ricetta (`adopted`, R10); (c) le correzioni viaggiano nel `payload`
come le cotture e `materialize_ready` le rimette. **Mattia ha scelto (a) il 2026-10-13**:
il piano costruisce (a), e (c) resta un'`idea` in `next-steps.md`, da riprendere se
succede davvero.

## 11. Al merge e dopo il deploy (solo Mattia)

**Al merge.** La migrazione è la `0015` con `down_revision = "0012"`: va ripuntata sulla
testa di `master` di quel momento (una riga), e `alembic heads` deve dire una testa sola.
Se H1 è già su `master`, `CALL_SITE_LABELS` (`backend/app/domain/spending.py`) prende
`"ingredient_substitutes": "Sostituti degli ingredienti"`, o il suo test fallisce.

**Dopo il deploy.** In produzione, sul server: prima `--dry-run`, poi `--limit 20` e uno
sguardo alle venti righe stampate (e in Anagrafica) e alla spesa del lancio; poi di nuovo
`--dry-run` per la stima misurata; poi il resto, in uno o due giorni. I comandi esatti
sono nel piano.
