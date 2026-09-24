# R4 — Runbook dell'import completo di GialloZafferano

Scritto il 2026-09-24, nella sessione che ha costruito R4 senza eseguirlo, **per la
sessione che lo eseguirà**. Contiene tutto quel che serve sapere e fare, in ordine.
Nessun passo qui sotto è stato ancora fatto in produzione.

Spec: `docs/superpowers/specs/2026-09-24-import-completo-design.md`.
Piano: `docs/superpowers/plans/2026-09-24-import-completo.md`.

---

## 0. Cosa c'è da sapere prima di toccare qualunque cosa

**Dove sta il codice.** In `master` e su `origin` dal 2026-09-24 (fuso in avanti dal
ramo `r4-import-completo`, poi cancellato), **non ancora in produzione**. Contiene: il seme che carica le ricette solo con
`--con-ricette`, il comando `drop_seed_recipes`, `import_gz --tutto`, la soglia dei
mancanti calcolata in SQL e «Mostra altre» nel ricettario. **Nessuna migrazione**:
dopo il deploy `alembic current` deve dire ancora `0010 (head)`.

**Il server.** `hetznerserver` (alias SSH), repo in `~/sites/spena`. 75 GB di disco, 31
liberi il 2026-09-24 (più 17,6 GB di immagini Docker e 7,2 GB di cache di build
recuperabili), 7,6 GB di RAM, 4 CPU. Gli embedding sono spenti
(`INSTALL_EMBEDDINGS=0`): la ricerca è solo testuale, e va bene così.

**Tre regole che hanno già fatto danni** (da `CLAUDE.md`):

- `docker compose` **sempre** con `-f docker-compose.prod.yml` sul server. Senza,
  parte lo stack di sviluppo al posto di quello di produzione, e il dominio smette di
  rispondere senza che nessun log lo dica.
- Un `git pull` da solo non distribuisce niente: il frontend è compilato
  nell'immagine. La prova che il codice nuovo gira è il nome del pacchetto servito,
  non i container «healthy».
- Il `.env` (locale e del server) non si modifica senza chiedere a Mattia.

**I numeri da cui si parte** (misurati il 2026-09-24):

| cosa | valore |
|---|---|
| ricette nella sitemap `https://ricette.giallozafferano.it/sitemap/ricette.xml` | 8.469 |
| ricette in produzione | 66 = 40 importate + 26 di semina, più 1 scritta con l'AI |
| pagine d'import in produzione | 40, tutte `imported` |
| termini d'import | 170, tutti decisi (69 AI, 77 automatici, 24 a mano) |
| ingredienti in anagrafica | 223 |
| storage per ricetta importata, pagina d'import compresa | ~17 KB → ~150 MB per tutto il catalogo |
| pausa fra due pagine (`DELAY_SECONDS`) | 1,2 s → ~2 h 50 di sole pause, 3-4 ore in tutto |
| costo AI stimato | 0,0002–0,0003 $ a termine, 1–3 $ in tutto (**non misurato**) |
| ricerca su 8.500 ricette sintetiche | 73–143 ms in ogni caso (prima: errore o 1 s) |

**Come si interroga il database di produzione** (lo stesso schema per tutti i
comandi SQL di questo file):

```bash
ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T db sh -c 'psql -U \"\$POSTGRES_USER\" -d \"\$POSTGRES_DB\"'" < query.sql
```

I warning `The "argon2id" variable is not set` sono cosmetici e preesistenti: non
inseguirli.

---

## 1. In produzione

Il codice è già in `master`. Prima di tutto si controlla che `master` su `origin` sia
quello atteso, cioè che contenga il commit del runbook (`R4: il runbook dell'import
completo`) e che nel frattempo non sia arrivato altro da distribuire senza saperlo:

```bash
git fetch origin && git log --oneline -5 origin/master
```

Sul server:

```bash
ssh hetznerserver "cd ~/sites/spena && git pull --ff-only origin master && docker compose -f docker-compose.prod.yml up -d --build --wait --wait-timeout 120"
ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T backend alembic current"
```

`alembic current` deve dire `0010 (head)`. Poi la prova che il pacchetto è nuovo:

```bash
ssh hetznerserver "docker exec spena-frontend-1 ls /usr/share/nginx/html/assets"
curl -s https://spena.mattiagirellini.com/ | grep -oE 'assets/index-[A-Za-z0-9_-]+\.(js|css)'
```

I due nomi devono coincidere, e il `.js` deve essere diverso da `index-D-4nTk3P.js`
(il pacchetto di prima di R4).

**Controllo a schermo, prima dell'import:** con 66 ricette il ricettario ne mostra 30 e
in fondo c'è «Mostra altre»; toccandolo arrivano le altre 36 e il bottone sparisce.
«Ora» filtra senza errori.

---

## 2. Il limite di credito su OpenRouter

Deciso in brainstorming: il tetto di 1 $/giorno **non** è nel codice, è un limite
sulla chiave. **È un'impostazione dell'account di Mattia e la fa lui**, dal pannello
delle chiavi di OpenRouter: un limite di credito sulla chiave usata dal server, con
reset giornaliero se il pannello lo offre, altrimenti un limite totale di qualche
dollaro da rialzare a mano.

Cosa succede quando il limite scatta: OpenRouter risponde 402, `services/llm.py` lo
trasforma in `LlmUnavailable`, il termine resta in coda. Dopo due giri di fila senza
una decisione `--tutto` smette di chiedere all'AI (`MAX_FRUITLESS_ROUNDS`), finisce le
pagine e esce. Si rilancia il giorno dopo: riprende dai termini.

Prima di partire, la spesa registrata finora, per poter fare la differenza dopo:

```sql
SELECT call_site, count(*), round(sum(cost_usd)::numeric, 5) AS usd
FROM llm_calls GROUP BY 1;
```

(Il 2026-09-24 c'erano solo 4 chiamate `unit_forms`, per 0,00019 $: le decisioni sui
termini precedenti non sono registrate, perché precedono `llm_calls`.)

---

## 3. Un backup, poi via le ricette di semina

Il backup, prima di cancellare qualunque cosa:

```bash
ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T db sh -c 'pg_dump -U \"\$POSTGRES_USER\" \"\$POSTGRES_DB\"' | gzip > ~/spena-prima-di-r4-\$(date +%F).sql.gz && ls -lh ~/spena-prima-di-r4-*"
```

Poi il comando senza conferma, che elenca e basta:

```bash
ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.drop_seed_recipes"
```

Deve elencare **26 ricette** e dire **1 cottura**. Una sola cottura esiste in
produzione, ed è su una ricetta di semina: resterà nello storico, con la sua
fotografia, senza ricetta collegata. Se i numeri sono diversi, ci si ferma e si capisce
perché. Se tornano:

```bash
ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.drop_seed_recipes --conferma"
```

Un seme rilanciato da qui in poi non le rimette: da R4 il default è la sola anagrafica.

---

## 4. Il lancio

```bash
ssh hetznerserver "cd ~/sites/spena && nohup docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.import_gz --tutto > ~/import-gz-\$(date +%F).log 2>&1 &"
```

- `-T` perché sotto `nohup` non c'è un terminale.
- Il processo gira **dentro il container del backend**: un deploy o un riavvio del
  container lo uccide. Niente deploy mentre gira. Se succede, si rilancia lo stesso
  comando: le pagine già prese non si riscaricano, e al massimo si perde il lotto in
  corso.
- `--tutto` e `--limit` insieme sono un errore (codice 2).

---

## 5. Come si segue

```bash
ssh hetznerserver "tail -n 20 ~/import-gz-*.log"
```

Una riga per lotto da 50 pagine, per esempio:

```
14:03 pagine 850/8429 (prese 846, scartate 4) · termini decisi 212, in coda 35 · ricette 802
```

`pagine x/y`: il denominatore sono le pagine **nuove** della sitemap, cioè 8.469 meno
quelle già prese. «in coda» sono i termini ancora da decidere; «ricette» sono tutte
quelle importate. Finite le pagine, le righe dicono `solo termini`.

Dal database:

```sql
SELECT state, count(*) FROM recipe_imports GROUP BY 1;
SELECT decision, decided_by, count(*) FROM import_terms GROUP BY 1, 2;
```

Il ricettario si riempie mentre il comando gira: ogni lotto materializza le ricette
i cui termini sono tutti decisi.

---

## 6. Se si ferma prima della fine

| nel log | cosa vuol dire | cosa fare |
|---|---|---|
| `fonte dice di fermarsi` o `2 rifiuti di fila: mi fermo` | GialloZafferano ha risposto 429 o 5xx due volte di fila | aspettare qualche ora, poi rilanciare §4 |
| `l'AI non ha deciso niente per 2 giri di fila` | credito finito, modello giù o risposte non verificabili | controllare il credito su OpenRouter; rilanciare §4 più tardi (riprende dai termini) |
| `riconoscimento non disponibile (OPENROUTER_API_KEY non configurata)` | la chiave manca nel `.env` del server | chiedere a Mattia; non si tocca il `.env` da soli |
| il processo sparisce senza riga finale | container riavviato, o un'eccezione | leggere la coda del log; rilanciare §4 |

Rilanciare è sempre sicuro: pagine prese una volta sola, termini decisi una volta sola.

---

## 7. Dopo

1. **Il riepilogo** in fondo al log dice quante pagine, quanti termini e quante unità
   nuove. Se ci sono unità nuove:
   ```bash
   ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T backend python -m app.cli.decide_units"
   ```
   rilanciato finché l'ultima riga dice che non ne restano. Le forme sbagliate si
   correggono con `--imposta` (vedi README, «Le unità di misura delle dosi»).
2. **I termini rimasti in coda** si decidono a mano dall'app: «Ingredienti da
   abbinare» in cima al ricettario. Le decisioni dell'AI si rivedono a campione da
   `/ricette/importa`, «Deciso dall'AI», e ognuna ha il suo annulla.
3. **I conti:**
   ```sql
   SELECT state, count(*) FROM recipe_imports GROUP BY 1;
   SELECT skipped_reason, count(*) FROM recipe_imports WHERE state = 'skipped' GROUP BY 1 ORDER BY 2 DESC;
   SELECT count(*) FROM recipes;
   SELECT count(*) FROM ingredients;
   SELECT call_site, count(*), round(sum(cost_usd)::numeric, 5) AS usd FROM llm_calls GROUP BY 1;
   SELECT pg_size_pretty(pg_database_size(current_database()));
   ```
   e `df -h /` sul server.
4. **La ricerca sui dati veri.** Dentro il container:
   ```bash
   ssh hetznerserver "cd ~/sites/spena && docker compose -f docker-compose.prod.yml exec -T backend python -" <<'EOF'
   import asyncio, time
   from app.core.db import SessionLocal
   from app.services.recipe_search import search_recipes

   async def main():
       for kwargs in ({}, {"offset": 3000}, {"max_missing": 0}, {"max_missing": 3},
                      {"query": "pasta"}, {"query": "pasta", "max_missing": 1}):
           async with SessionLocal() as session:
               start = time.perf_counter()
               found = await search_recipes(session, **kwargs)
               print(kwargs, len(found), f"{(time.perf_counter() - start) * 1000:.0f} ms")

   asyncio.run(main())
   EOF
   ```
   Il riferimento sono i 73–143 ms delle 8.500 ricette sintetiche. Molto oltre i 300 ms
   vuol dire guardare il piano con `EXPLAIN ANALYZE` prima di chiamarlo fatto.
5. **A schermo, sul telefono:** «Mostra altre» più volte, «Ora / +1 / +2 / +3», un
   filtro per categoria, uno per ingrediente, una ricerca per parole.
6. **Aggiornare `docs/prossimi-passi.md`:** R4 diventa FATTO con i numeri veri (pagine,
   scartate e perché, termini decisi dall'AI e a mano, costo, tempo, dimensione del
   database, tempi della ricerca); in «Stato di oggi» una riga; R5 e R6 non aspettano
   più R4. Il backup di §3 si può cancellare dopo qualche giorno senza sorprese.

---

## 8. Cose note che non sono di R4

- Circa settanta dosi importate con un aggettivo davanti al numero non si riscalano
  (Parte X di `prossimi-passi.md`). Con il catalogo intero saranno molte di più: vale
  la pena riprenderla dopo, con `reparse_quantities` che è rieseguibile.
- `skipped_reason` non si vede da nessuna schermata (Parte X): i motivi degli scarti si
  leggono solo con la query di §7.
- Con parole cercate, «Mostra altre» scorre solo fra i primi `CANDIDATE_POOL` (100)
  candidati di ciascuna graduatoria: è una scelta dichiarata in R3, R7 e nella spec di
  R4, non un difetto.
