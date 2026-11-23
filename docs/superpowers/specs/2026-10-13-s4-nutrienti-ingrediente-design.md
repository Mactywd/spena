# S4 — I nutrienti dell'ingrediente generico: CIQUAL, i grammi delle dosi, i nutrienti di una ricetta

_2026-11-21: i candidati e i lotti dei pesi cambiano dopo il pilota sulla tabella vera; §4.10 e §4.23 aggiornati, vedi `docs/superpowers/plans/2026-11-21-s4-candidati.md`._

_2026-10-13. Voce di `next-steps.md`: «S4, resto: nutrienti sull'ingrediente generico… e il tasto
«Stima» con l'AI» [S4]. Il ragionamento d'archivio è in `docs/prossimi-passi.md`, «## S4.», e in
P1 e P2. La prima metà di S4 (il livello prodotto, il vocabolario dell'Allegato XIII) è nella spec
`docs/superpowers/specs/2026-09-24-nutrienti-ampi-design.md`. Piani:
`docs/superpowers/plans/2026-10-13-s4-ciqual.md` (fetta 1) e
`docs/superpowers/plans/2026-10-13-s4-grammi.md` (fetta 2)._

## 1. Contesto

Le ricette puntano agli ingredienti, non ai prodotti (decisione fondante 2). I nutrienti che ci
sono oggi stanno solo sui prodotti (`products.nutrients`, da Open Food Facts): una ricetta non ne
sa niente, e P1 (il pasto), P2 (il NutriScore), P3 (più giorni) e M1 (il motore) aspettano tutti
questo. Servono due cose che non ci sono:

1. **i nutrienti dell'ingrediente generico**, medi, per 100 g — `pomodoro`, non «Pelati Cirio»;
2. **quanti grammi pesa una dose**: «1 spicchio» d'aglio, «2 cucchiai» d'olio, «2» uova. Il
   registro delle unità esiste già (D1) e `units.canonical_id` fa puntare «cucchiai» a
   «cucchiaio» proprio perché il peso si scriva una volta per unità canonica.

I numeri della produzione (2026-10-13, misurati di giorno, nessun piano li rilegge): 8.454
ricette, 83.343 righe d'ingrediente, 884 ingredienti dopo la revisione del 2026-09-27 (più quelli
nati dopo), 101 unità; `quantity_value` vuoto su 32.067 righe, circa 16.000 delle quali «q.b.».

## 2. Le decisioni di Mattia (2026-10-13)

1. **La fonte dell'ingrediente generico è CIQUAL 2025** (Anses).
2. **Le righe «q.b.» restano fuori dal conto** dei nutrienti di una ricetta, e la copertura lo
   **dichiara**: quali righe mancano. Una stima per porzione dei grassi «q.b.» si deciderà nella
   spec di P2.
3. **Il modello è Gemma, dopo un pilota** di circa 50 casi con le risposte note (abbinamenti e
   pesi decisi a mano), che costa centesimi. Il pilota è un comando che la notte costruisce e
   prova coi finti, e che Mattia lancia dopo il deploy. Se il pilota non basta si passerà a un
   modello più forte solo dove serve (fuori da questi piani; §9 dice cosa servirebbe).
4. **Si portano a piano le fette 1 e 2**: (1) i nutrienti sull'ingrediente da CIQUAL, con
   provenienza e riferimento; (2) i grammi per ingrediente × unità e la funzione pura «nutrienti
   di una ricetta» con la copertura dichiarata — è ciò che darà dati a P1 e P2. **La fetta 3**, il
   tasto «Stima» sul prodotto, è **decisa e rinviata** (§8): resta in `next-steps.md` come `tbd`
   «serve il piano».

## 3. Quel che la ricerca ha trovato (2026-10-13)

- **CIQUAL 2025**: 3.484 alimenti, 74 costituenti, pubblicata il 19/11/2025. Scheda ufficiale
  sull'entrepôt di recherche.data.gouv.fr, **DOI 10.57745/RDMHWY**
  (<https://doi.org/10.57745/RDMHWY>). La scheda di data.gouv.fr porta ancora la 2020 e rimanda
  a questa. **Licenza verificata sulla scheda: Etalab 2.0** (Licence Ouverte), «peuvent être
  reproduits, obligatoirement avec la référence explicite à la source»; la citazione richiesta è
  «Anses. 2025. Table de composition nutritionnelle des aliments Ciqual». File della scheda:
  `Table Ciqual 2025_FR_2025_11_03.xlsx` (1,5 MB), lo stesso in `.xls` (4,5 MB), e cinque XML —
  fra cui `compo_2025_11_03.xml` da 69 MB. Solo in francese: l'XLSX non ha i nomi inglesi.
- **Il formato del 2025 non l'ha visto nessuno di noi**: il download dall'entrepôt passa da una
  verifica anti-robot, e Claude non l'ha aggirata. Il lettore è scritto sulla forma documentata
  delle edizioni precedenti — una riga d'intestazione con `alim_code`, `alim_nom_fr`,
  `alim_grp_nom_fr`, `alim_ssgrp_nom_fr` e una colonna per costituente col nome e l'unità,
  «Fer (mg/100 g)» — e **si rifiuta di scrivere** se il file non torna (§4, decisione 7). La
  prova a secco lo dice prima di ogni scrittura.
- **La ricerca semantica e5 in produzione è spenta** (`INSTALL_EMBEDDINGS=0`, README): non può
  fare da filtro dei candidati. Il filtro è `pg_trgm`, che c'è già, sui nomi francesi, dopo che
  l'AI ha scritto le parole di ricerca in francese (decisione 12).
- **Le porzioni USDA** (CC0) come ancoraggio dei pesi: non valgono il lavoro adesso. Sono in
  inglese, a misure americane (cup, tbsp), su un catalogo diverso da questo; l'abbinamento
  costerebbe quanto quello di CIQUAL, per dare un'ancora a una parte piccola delle coppie. Il
  pilota (decisione 3 di Mattia) misura lo stesso rischio a costo quasi nullo.
- **Costi attesi**, con Gemma (`google/gemma-4-26b-a4b-it`, ~0,04–0,06 $ al milione di token in
  ingresso): l'abbinamento di ~900 ingredienti è ~36 chiamate di termini e ~90 di scelta, qualche
  centinaio di migliaia di token, **meno di 0,10 $**; i pesi di 800–1.500 coppie sono ~20–40
  chiamate, **meno di 0,05 $**; il pilota, **meno di 0,01 $**. Tutto molto sotto il tetto di
  1 $/giorno.

## 4. Le decisioni di Claude, su delega di Mattia (tecniche o estetiche)

Reversibili; Mattia le rivede.

**Il file**

1. **Il file CIQUAL sta nel repository**, `data/ciqual/ciqual-2025.xlsx` (l'XLSX della scheda,
   rinominato), con l'attribuzione nel README e nella scheda dell'ingrediente. La licenza lo
   consente citando la fonte, 1,5 MB è una misura ragionevole, e `data/` è già montata in
   produzione su `/data` (`docker-compose.prod.yml`): niente da copiare sul server a mano. **La
   notte non scarica niente**: il file lo scarica e lo committa Mattia (§10). I test costruiscono
   al volo un piccolo XLSX con valori inventati (`backend/tests/ciqual_fixture.py`), che lo stack
   e2e carica allo stesso modo.
2. **L'XLSX si legge senza dipendenze nuove**: è un archivio zip di XML, e la libreria standard
   (`zipfile`, `xml.etree`) basta (`backend/app/services/ciqual_file.py`). L'XML ufficiale
   (69 MB) non entra in un repository; l'`.xls` vorrebbe `xlrd`.
3. **Si caricano i 30 nutrienti del vocabolario che CIQUAL ha**: tutti quelli dell'Allegato XIII
   tranne vitamina A (CIQUAL dà retinolo e beta-carotene separati, e la somma in equivalenti è un
   calcolo che non si fa senza dirlo), biotina, fluoruro, cromo e molibdeno (CIQUAL non li ha).
   La vitamina K è la K1. Le colonne si riconoscono **dal nome**, senza accenti né maiuscole
   (`CIQUAL_NAMES` in `backend/app/domain/ciqual.py`), mai dalla posizione.
   *Aggiornato il 2026-11-23 (rifiniture di S4)*: la vitamina A entra dall'«Activité vitaminique A,
   équivalents rétinol» (il calcolo lo fa CIQUAL e lo dice nel nome; dove manca, la A manca), e la
   vitamina E ha il ripiego «Alpha-tocophérol (vitamine E)» dove «Vitamine E» è vuota
   (`CIQUAL_FALLBACKS`): i nutrienti letti sono 31, fuori restano biotina, fluoruro, cromo, molibdeno.
4. **Come si legge un valore** (`parse_teneur`): «10,4» → 10,4; «traces» → 0; «< 0,5» → 0,25
   (la metà del limite, la convenzione «middle bound» dell'EFSA: il valore vero sta fra 0 e il
   limite); «-» o la cella vuota → **assente**, mai zero (CLAUDE.md, «missing nutrients stay
   missing»); qualunque altra cosa → illeggibile, contata, e assente.
5. **Le tabelle** (migrazione `0016`): `ciqual_foods` (`code` testo, chiave; `name_fr`;
   `group_fr`, il sottogruppo o il gruppo; `nutrients` JSONB con le chiavi del vocabolario, per
   100 g di parte edibile; `version` «2025»); `ingredient_nutrition` (`ingredient_id` chiave e FK
   `CASCADE`; `ciqual_code` FK `RESTRICT`, annullabile; `decided_by` `ai`|`human`;
   `decided_at`). **Tre stati**: nessuna riga = non ancora deciso; riga con `ciqual_code` NULL =
   deciso «nessun alimento adatto»; riga con un codice = quell'alimento. I valori **non si
   copiano** sull'ingrediente: si leggono da `ciqual_foods` con una join, così un caricamento più
   nuovo li aggiorna tutti.
6. La colonna `ingredients.composition_ref` (`String(60)`, «popolato in fase 3», mai scritta)
   **resta com'è**: toglierla ora litigherebbe al merge con S12, che ci scrive accanto. Un'`idea`.
7. **Il caricamento è prudente**: se mancano `alim_code` o `alim_nom_fr`, se manca una delle
   quattro colonne d'obbligo (energia, proteine, carboidrati, grassi), o se una colonna
   riconosciuta porta un'unità diversa da quella del vocabolario («Fer (µg/100 g)» contro i mg),
   **non si scrive niente**, e il messaggio dice quale colonna. `--dry-run` legge, conta e
   stampa senza toccare il database (non lo apre nemmeno). Il caricamento vero aggiorna per
   codice (`INSERT … ON CONFLICT DO UPDATE`), non cancella gli alimenti che il file non ha più, e
   li conta.

**L'abbinamento ingrediente → alimento**

8. **L'AI decide, a due passi, solo per gli ingredienti alimentari non ancora decisi**
   (`python -m app.cli.decide_ciqual`). Un ingrediente non alimentare non si chiede mai. Una
   decisione dell'AI non sovrascrive mai una riga che c'è già (`ON CONFLICT DO NOTHING`): una
   scelta fatta a mano nel frattempo vince.
9. **Primo passo, le parole di ricerca**: lotti da 25 nomi italiani, col reparto; l'AI risponde
   per numero e nome (come `decide_emoji` di S12) da una a tre parole in francese, «come le
   scriverebbe CIQUAL» («tomate crue»). Sezione della spesa `ciqual_terms`.
10. **I candidati**: per ogni ingrediente, le parole dell'AI contro `ciqual_foods.name_fr` con
    `word_similarity` di `pg_trgm`; i 15 migliori sopra 0,3. `word_similarity` vale 1 per ogni
    nome che contiene la parola (sulla tabella vera «riz» ne lega 43: amido, bevanda, riso al
    latte), quindi a parità vince il nome che comincia con la prima parola, poi la
    `similarity` di tutto il nome, poi l'alfabeto. Il nome italiano si cerca solo se le parole
    dell'AI non trovano niente: aggiunto sempre portava rumore («sale» → «Salers», «Eau
    minérale Salvetat»). _Cambiato il 2026-11-21, dopo il pilota del 2026-10-20 (20 su 29):
    con l'ordine alfabetico, 12 di 24 gruppi di parole plausibili non avevano l'alimento fra i
    candidati; con questo, nessuno._
11. **Secondo passo, la scelta**: lotti da 10 ingredienti, ciascuno coi suoi candidati
    (codice, nome, gruppo); l'AI risponde il codice di uno dei **suoi** candidati, oppure `null`
    se nessuno è quell'ingrediente. «Nello stato in cui una ricetta lo pesa»: crudo se si cucina,
    secco se si compra secco. Sezione `ciqual_match`. Un codice che non è fra i candidati di
    quell'ingrediente, un numero non chiesto o già risposto, un nome che non torna: **non si
    applica**, e l'ingrediente resta da decidere.
12. **Perché due passi e non e5**: in produzione e5 non c'è (§3), e i trigrammi da soli fra
    italiano e francese non si incontrano («pomodoro» / «tomate»). Le parole francesi le scrive
    chi sa il francese, cioè l'AI; la scelta la fa fra candidati veri, così non può inventare un
    codice.
13. **«Nessun alimento adatto» dall'AI si scrive** (riga con codice NULL, `ai`): l'ingrediente è
    deciso e il giro dopo non lo richiede. Vale anche quando la ricerca non trova nemmeno un
    candidato. **Deciso da Mattia il 2026-10-13** (§12); lo stesso per «nessun peso» (decisione 23).
14. **La correzione è in Anagrafica**, nella scheda dell'ingrediente: «Cambia alimento» cerca in
    CIQUAL per nome francese o per codice e salva la scelta come `human`; «Nessun alimento adatto»
    la salva vuota; **«Annulla la scelta»** toglie la riga — l'ingrediente torna da decidere, e
    l'AI lo riprenderà al giro dopo. È l'annullamento delle decisioni, come per i termini
    dell'import. Una scelta `human` l'AI non la tocca mai.
15. **La fusione in Anagrafica** cancella il perdente e, per `CASCADE`, la sua scelta e i suoi
    pesi; il vincitore tiene i suoi, anche se non li ha. **Deciso da Mattia il 2026-10-13** (§12), con un'`idea` per tenerli.
16. **Le scritture** passano da un servizio solo per tabella: `services/ingredient_nutrition.py`
    (le scelte, a mano e dell'AI) e, nella fetta 2, `services/unit_grams.py` (i pesi). Non da
    `registry.py`, che S12 e R5 toccano stanotte: il rifiuto ha la stessa forma di quelli
    dell'anagrafica (409 con `code` e `detail`), così lo schermo lo legge con `registryRefusal`.
17. **Le rotte**: `GET /api/v1/ciqual/foods?q=` (la ricerca della correzione);
    `GET|PUT|DELETE /api/v1/ingredients/{id}/nutrition` (lo stato, la scelta, l'annullamento).
    Una rotta a sé e non un campo nuovo della scheda dell'ingrediente: `IngredientDetailOut` lo
    cambia S12 stanotte, e un campo obbligatorio in più costringerebbe a riscrivere ogni oggetto
    di prova del frontend. Nella fetta 2 la stessa risposta porta anche i pesi (`weights`).

**Il pilota**

18. **`python -m app.cli.s4_pilot`** chiede all'AI i casi di `backend/app/data/s4_pilota.json`
    con gli stessi servizi del lancio vero, **senza scrivere niente** sugli ingredienti (registra
    le chiamate in `llm_calls`, come ogni chiamata). La fetta 1 lo costruisce con **30
    abbinamenti**; la fetta 2 gli aggiunge **20 pesi**. Un abbinamento atteso è un'espressione
    regolare sul nome francese senza accenti né maiuscole (`^tomate, crue`; nella 2025 quel nome
    non c'è: il caso del pomodoro aspetta `^tomate (sans precision|ronde), crue`), perché i codici
    del 2025 non li ha visti nessuno; un caso la cui espressione non trova **nessun** alimento nella
    tabella caricata si segna «da rivedere» e non entra nel conto. Un peso atteso è un intervallo
    in grammi.
19. **Le soglie**: almeno il **90%** degli abbinamenti giusti, almeno l'**80%** dei pesi
    nell'intervallo. Il comando stampa ogni caso sbagliato, il verdetto e la spesa del giro. Non
    blocca niente: decide Mattia.

**I pesi (fetta 2)**

20. **Una tabella**, `ingredient_unit_grams` (migrazione `0017`): `ingredient_id` FK `CASCADE`;
    `unit_id` FK `units` **`CASCADE`** e annullabile (NULL = il «pezzo», la dose senza unità:
    «2» uova); `grams` `Numeric(8, 2)` annullabile (NULL = deciso «nessun peso sensato»), con
    `CHECK grams > 0`; `decided_by`, `decided_at`; **`UNIQUE NULLS NOT DISTINCT (ingredient_id,
    unit_id)`** (Postgres 16), perché due righe «pezzo» dello stesso ingrediente non devono poter
    esistere. `CASCADE` e non `RESTRICT` sull'unità: la pulizia delle dosi (piano 12) toglie le
    unità spurie, e un peso di un'unità che non c'è più non serve a niente.
21. **Sempre sull'unità canonica**: `canonical_id` se c'è, altrimenti l'unità stessa. «pezzo» e
    «pezzi» valgono come la dose senza unità (`unit_id` NULL).
22. **Le unità di massa non chiedono niente**: g, gr, grammo/i ×1; kg, chilo/i, chilogrammo/i
    ×1000; hg, etto/i ×100; mg ×0,001. **Quelle di volume** (ml, millilitro/i ×1; cl,
    centilitro/i ×10; dl, decilitro/i ×100; l, lt, litro/i ×1000) con **densità 1**, dichiarata
    approssimata, salvo quattro eccezioni sul nome dell'ingrediente: `olio…` 0,92, `miele` 1,42,
    `sciroppo…` 1,33, `latte condensato` 1,29. La parola si riconosce sulla chiave o sul
    singolare dell'unità canonica. Tutto in `backend/app/domain/recipe_nutrition.py`.
23. **Le coppie da chiedere** sono quelle che le ricette usano davvero (tutte, eliminate
    comprese: si ripristinano), di un ingrediente alimentare, con una dose letta
    (`quantity_value`), su un'unità che non è di massa né di volume. L'AI le decide a lotti da
    40 (`python -m app.cli.decide_grams`, sezione `unit_grams`): per ciascuna numero,
    ingrediente, unità e un esempio di dose; risponde i grammi **netti della parte che si mangia**
    di una unità, o `null` se una unità di quell'ingrediente non ha un peso sensato. Si applica
    solo una risposta col numero e i nomi giusti e un peso fra 0 e 5.000 g; `null` si scrive come
    «nessun peso» e non si richiede. Un lotto a cui l'AI risponde in modo illeggibile (troncato,
    JSON rotto) si divide a metà e si richiede, fino alla coppia sola; una coppia che non si
    legge nemmeno da sola si salta per quel giro, resta da pesare e il comando la nomina. Se
    nessuna coppia di un lotto di più coppie si legge, il giro si ferma. (2026-11-21: prima si
    fermava al primo lotto rotto, e il lotto era sempre lo stesso.)
24. **La correzione è in Anagrafica**, nella stessa scheda, sotto i valori: «Pesi per unità», una
    riga per coppia («1 spicchio — 5 g · AI»), e per ciascuna «Correggi» che apre il campo dei
    grammi con «Salva il peso», «Annulla il peso» (torna da decidere) e «Lascia com'è». Una scelta
    `human` l'AI non la tocca. Un'unità di massa o di volume si rifiuta: i suoi grammi si contano
    da sé.

**I nutrienti di una ricetta (fetta 2)**

25. **Una funzione pura**, `recipe_nutrition` in `backend/app/domain/recipe_nutrition.py`: per
    ogni riga, la dose letta × i grammi dell'unità (massa, volume × densità, o la coppia) × i
    valori per 100 g dell'alimento CIQUAL. Una riga **si conta** se ha una dose letta, un
    alimento CIQUAL e un peso; altrimenti è **fuori dal conto con il suo perché**: senza dose
    («q.b.», o una dose che il parser non legge), senza alimento CIQUAL (non deciso, o «nessun
    alimento»), senza peso (la coppia non decisa, o «nessun peso»). I totali sommano solo le righe
    contate, e per ogni nutriente si dice **su quante righe** c'è il valore: un nutriente che
    nessuna riga ha resta assente, non zero.
26. **A porzione** quando la ricetta dice le porzioni, altrimenti per tutta la ricetta. Il
    riporziona non cambia una porzione, quindi la vista è una sola.
27. **La rotta** `GET /api/v1/recipes/{id}/nutrition`, a sé: il dettaglio della ricetta lo
    cambiano R2, R8 e la pulizia delle dosi stanotte. È ciò che P1 e P2 leggeranno.
28. **A video, nel dettaglio della ricetta**, in fondo dopo il procedimento: «Valori
    nutrizionali», **chiuso** finché non lo si apre («Mostra i valori nutrizionali»), perché è una
    stima e non deve competere con «Cucina». Aperto: la tabella (a porzione), «Contate N righe su
    M.», le righe fuori dal conto col loro perché e il nome che porta alla scheda in Anagrafica
    (mai un vicolo cieco: è lì che si sceglie l'alimento o si scrive il peso), e «Stima con i
    valori medi di CIQUAL 2025 e i pesi delle dosi: non è un'etichetta.».

## 5. Fetta 1 — cosa fa, esattamente

**Comandi** (con `-f docker-compose.prod.yml` in produzione, come sempre):

```
python -m app.cli.load_ciqual --dry-run      # legge data/ciqual/ciqual-2025.xlsx, conta, non scrive
python -m app.cli.load_ciqual                # carica (o aggiorna) ciqual_foods
python -m app.cli.load_ciqual <percorso>     # un altro file
python -m app.cli.s4_pilot                   # il pilota, senza scrivere sugli ingredienti
python -m app.cli.decide_ciqual --limit 20   # l'AI abbina i primi 20 ingredienti da decidere
python -m app.cli.decide_ciqual              # tutti
```

**Lo schermo** — scheda dell'ingrediente in Anagrafica, **solo per un alimento**, in fondo dopo
«Prodotti». Parole esatte:

| Dove | Testo |
|---|---|
| titolo della sezione | «Valori nutrizionali» |
| in caricamento | «Carico i valori nutrizionali…» |
| guasto | «Non sono riuscito a leggere i valori nutrizionali.» e il pulsante «Riprova a leggerli» |
| non deciso | «Non ancora abbinato a un alimento della tabella CIQUAL: lo farà l'AI al prossimo giro, oppure sceglilo tu.» e «Scegli l'alimento» |
| «nessun alimento» | «Nessun alimento adatto» e sotto «CIQUAL 2025 · scelto dall'AI» (o «scelto a mano»); «Cambia alimento», «Annulla la scelta» |
| un alimento | il nome francese, sotto «CIQUAL 2025 · 20047 · scelto dall'AI» (o «scelto a mano»); la tabella «Per 100 g»; «Cambia alimento», «Annulla la scelta» |
| dopo «Annulla la scelta» | «Scelta annullata: l'AI lo abbinerà al prossimo giro.» |
| guasto dell'annullamento | «Non sono riuscito ad annullare la scelta. Riprova.» |
| in fondo | «Fonte: Anses, Table de composition nutritionnelle des aliments Ciqual 2025.» |
| la ricerca | il campo «Cerca nella tabella CIQUAL», sotto «Scrivi in francese, come la tabella: «tomate», «farine», «beurre».»; i risultati come scelte («Alimenti trovati»), ciascuna col nome e il gruppo; «Nessun alimento trovato: prova un'altra parola, in francese.»; «Non sono riuscito a cercare. Riprova fra poco.» |
| i pulsanti della ricerca | «Salva l'alimento» (non ancora: «Scegli un alimento dall'elenco.», oppure «È già il suo alimento: scegline un altro.»), «Nessun alimento adatto», «Lascia com'è» |
| guasto del salvataggio | «Non sono riuscito a salvare la scelta. Riprova.» |

La tabella: le otto righe principali (Energia, Proteine, Carboidrati, di cui zuccheri, Grassi, di
cui saturi, Fibre, Sale) sempre, con «—» dove CIQUAL non dà il valore (per chi ascolta «non
indicato nella tabella»); sotto, «Vitamine e minerali (N)» che si apre, con quelli presenti. I
numeri all'italiana, kcal senza decimali, il resto con uno (due sotto l'unità).

I rifiuti (409, `code` e `detail`): `non_food` ««Detersivo» non è un alimento: non ha valori
nutrizionali.»; `unknown_food` «Questo alimento non è nella tabella CIQUAL caricata: cercane un
altro.».

## 6. Fetta 2 — cosa fa, esattamente

**Comandi**:

```
python -m app.cli.s4_pilot                   # ora anche i 20 pesi
python -m app.cli.decide_grams --limit 40    # l'AI pesa le prime 40 coppie da decidere
python -m app.cli.decide_grams               # tutte
```

**Lo schermo, in Anagrafica**, sotto i valori: «Pesi per unità»; vuoto: «Nessuna dose da pesare:
le sue ricette lo scrivono in grammi o in litri, oppure non lo usano.»; una riga per coppia:
«1 spicchio» a sinistra, a destra «5 g · AI» (o «· a mano»), «da decidere», «nessun peso · AI»; il
pulsante di sola icona «Correggi il peso di 1 spicchio»; il campo «Grammi in 1 spicchio», «Salva
il peso» (non ancora: «Scrivi un numero di grammi più grande di zero.»), «Annulla il peso» (solo
se deciso), «Lascia com'è»; il guasto «Non sono riuscito a salvare il peso. Riprova.»; il rifiuto
`measured_unit` ««litro» è un'unità di peso o di volume: i grammi si contano da sé.».

**Lo schermo, nel dettaglio della ricetta**, in fondo: «Valori nutrizionali», «Mostra i valori
nutrizionali» / «Nascondi i valori nutrizionali»; «Calcolo i valori nutrizionali…»; «Non sono
riuscito a calcolare i valori nutrizionali.» con «Riprova a calcolarli»; la didascalia «A porzione,
su 2 porzioni» o «Per tutta la ricetta: porzioni non indicate»; sotto un valore parziale «su 3
righe di 4»; «Contate 4 righe su 5.»; «Fuori dal conto:» e per riga «Basilico (q.b.): senza una
dose da pesare», «… : senza un alimento CIQUAL», «… : manca il peso di «spicchio»»; con zero righe
contate, al posto della tabella: «Nessuna riga si può contare ancora: servono gli alimenti CIQUAL
degli ingredienti e i pesi delle loro dosi, in Anagrafica.»; in fondo «Stima con i valori medi di
CIQUAL 2025 e i pesi delle dosi: non è un'etichetta.».

## 7. Cosa non cambia

La dispensa resta senza quantità (decisione fondante 1): i pesi stanno sulle **ricette**, la
stessa porta che D1 ha aperto per le dosi. I nutrienti del prodotto (Open Food Facts) non si
toccano. Nessuna riga d'import, nessun riporziona, nessuna lista cambia.

## 8. La fetta 3, decisa e rinviata: il tasto «Stima» sul prodotto

Su un prodotto senza valori (scritto a mano, o che Open Food Facts non conosce), «Stima» propone
i valori, **in due passi**: prima **la media del suo ingrediente** (i valori CIQUAL della fetta
1, gratis e subito); poi, se si vuole di più, **l'AI con la ricerca web** (su OpenRouter il
plugin `web`, che aggiunge alla chiamata il costo dei risultati: da misurare con un lancio prima
della spec). Ogni valore stimato porta la sua provenienza — una colonna o una chiave accanto a
`products.nutrients`: `off`, `manuale`, `stima CIQUAL`, `stima AI` — e a video **non sembra mai
una lettura d'etichetta**. Serve il piano; la riga in `next-steps.md` resta `tbd` «serve il
piano».

## 9. Se il pilota non basta: cosa servirebbe (fuori da questi piani)

_Superato il 2026-11-21 (deciso da Mattia): con il passaggio a Claude Haiku il modello di tutte le chiamate è già quello forte rispetto a Gemma, e questo non si costruisce. Il pilota si rilancia una volta su Haiku dopo il deploy (spec `2026-11-21-llm-haiku-design.md` §9)._

`complete_json` oggi usa un modello solo (`OPENROUTER_MODEL`). Servirebbe: un argomento
`model` facoltativo di `complete_json` (il default resta quello di oggi); un'impostazione
`OPENROUTER_MODEL_STRONG`; e nei due comandi un'opzione `--modello-forte` che rilancia **solo**
le decisioni deboli — gli ingredienti che l'AI ha lasciato «nessun alimento», le risposte
rifiutate, le coppie «nessun peso» — dopo averle riportate a «da decidere». Il pilota si
rilancia con lo stesso interruttore, per confrontare. Una spec di mezza pagina e un piano
piccolo; il costo dipende dal modello (un Claude o un GPT medi costano 50–100 volte Gemma: su
qualche centinaio di casi, ancora centesimi).

## 10. Dopo il deploy (solo Mattia)

I comandi esatti, coi numeri attesi, sono nei due piani. In ordine:

1. **Il file**: scaricare `Table Ciqual 2025_FR_2025_11_03.xlsx` da
   <https://doi.org/10.57745/RDMHWY>, metterlo in `data/ciqual/ciqual-2025.xlsx`, provarlo
   (`load_ciqual --dry-run`), committarlo. Meglio **prima della notte**, nel checkout principale:
   allora la notte fa la prova a secco sul file vero e la scrive nel report.
2. Le migrazioni `0016` (e `0017`) si applicano da sé al deploy.
3. `load_ciqual --dry-run`, poi `load_ciqual`.
4. `s4_pilot`: se passa, avanti; se no, §9.
5. `decide_ciqual --limit 20`, uno sguardo in Anagrafica, poi `decide_ciqual` finché l'ultima
   riga dice «nessun ingrediente alimentare in attesa».
6. (fetta 2) `decide_grams --limit 40`, uno sguardo, poi `decide_grams` fino in fondo; poi
   qualche ricetta vera aperta su «Valori nutrizionali».

## 11. Al merge (solo Mattia)

La fetta 1 parte da `master` con la `0016` appesa alla `0012`, perché la catena della notte non
si allunghi; altri piani della notte aggiungono `0013`, `0014`, `0015`, `0018`. Al merge, la
`down_revision` della `0016` va ripuntata sulla testa di `master` di quel momento (una riga), e
`alembic heads` deve dire una testa sola. La `0017` resta appesa alla `0016`.

## 12. Le due domande, decise da Mattia il 2026-10-13

- **«Nessun alimento adatto» dell'AI si scrive, e il giro dopo non lo richiede** (decisione 13),
  anche quando la ricerca non ha trovato candidati; **lo stesso per «nessun peso»** (decisione
  23). L'Anagrafica lo dice («scelto dall'AI»), e «Annulla la scelta» / «Annulla il peso» lo
  rimettono da decidere.
- **La fusione perde la scelta e i pesi del perdente** (decisione 15), anche quando il vincitore
  non ne ha; il giro dopo dell'AI li ridecide sul vincitore. Un'`idea` in `next-steps.md`: farli
  ereditare al vincitore dove non ha niente.
