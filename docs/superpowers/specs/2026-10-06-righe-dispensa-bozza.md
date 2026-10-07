# S12 — Righe della dispensa riconoscibili (bozza di brainstorming)

_Bozza del 2026-10-06, scritta in una fase giorno senza Mattia: tre direzioni, una
raccomandazione e le decisioni che restano sue. La voce resta `tbd`._

_2026-10-07: Mattia ha deciso tutte e cinque le voci del §5 (le raccomandate). Non resta
niente da confermare; manca il piano._

Voce del backlog: «S12, righe della dispensa riconoscibili: icona per reparto, emoji per
ingrediente, foto del prodotto» [S12 in `docs/prossimi-passi.md`].
Mockup: `docs/mockups/2026-10-06-righe-dispensa.html` (oggi e le tre direzioni, chiaro e
scuro affiancati, a 375 px, coi valori veri dei token di `index.css`).

## 1. Il problema, e cosa c'è già

Le righe della dispensa (`PantryRow.tsx`) sono tutte uguali: nome dell'ingrediente come
link, sotto il prodotto o «sfuso», a destra le tre tacche di `StockGauge` e la ✕. Per
trovare il sale bisogna leggere. Mattia ha proposto una foto per tipo, un'icona o
un'emoji per reparto o per ingrediente, un fondo, un SVG.

Tre fatti del codice di oggi restringono il campo:

1. **Il reparto è già detto, e una volta sola.** Dal T3 ogni sezione della dispensa ha nel
   titolo l'icona del reparto su un quadratino con la sua tinta (`Section.tsx`,
   `departments.ts`: 14 reparti, 5 tinte). Le righe sono raggruppate per reparto, quindi
   **un'icona di reparto su ogni riga ripeterebbe la stessa figura su tutte le righe di
   una sezione**: dentro «Latticini» sarebbero tutte formaggi. Riconoscere una riga vuol
   dire distinguerla dalle vicine, che sono dello stesso reparto. L'icona di reparto
   serve solo come ripiego, dove non c'è niente di meglio.
2. **Le tinte dei reparti stanno solo nel titolo, mai sulle righe** (spec T3 §3.3, e il
   commento in `index.css`): un fondo colorato sulla riga si confonderebbe coi colori che
   vogliono già dire qualcosa (verde, ambra, rosso delle tacche; viola della scadenza). La
   strada «un fondo» è chiusa da quella decisione; il ripiego, se c'è, è monocromo.
3. **Lo spazio.** A 375 px, accanto alle tacche e alla ✕ restano 135 px per il nome (il
   commento in `PantryRow.tsx`). Una figura da 28 px più il suo spazio ne prende 36: il nome
   scende a 99 px, e «Yogurt greco» va a capo (si vede nel mockup). Il nome va già a capo
   oggi con i nomi lunghi; il prodotto resta su una riga, coi puntini.

## 2. Quante figure giuste esistono

Il database di sviluppo locale è vuoto (nessuna tabella), quindi la stima è fatta sul seme
`data/ingredients_seed.json`: 187 ingredienti in 14 reparti. In produzione gli ingredienti
sono 884 (dopo l'import), più fini del seme — più spezie, tagli e formaggi — quindi le
percentuali vere saranno peggiori di queste, non migliori. Ogni ingrediente è stato
classificato a mano in tre classi:

- **giusta**: la figura è proprio quella cosa (🥕 per carota);
- **di famiglia**: una figura vicina ma condivisa (🧀 per mozzarella, parmigiano, ricotta…);
- **nessuna**: si torna all'icona del reparto.

| Figure | giusta | di famiglia | nessuna |
|---|---|---|---|
| **Emoji** (Unicode, fino a Emoji 15) | 58 (31%) | 88 (47%) | 41 (22%) |
| **Icone di Tabler** (monocrome, il set dell'app: ~45 alimenti su 5166 icone) | 29 (16%) | 57 (30%) | 101 (54%) |

Per reparto, le emoji (giusta / famiglia / nessuna):

| Reparto | | Reparto | |
|---|---|---|---|
| frutta | 15 / 3 / 0 | latticini | 3 / 11 / 2 |
| verdura | 13 / 12 / 4 | carne | 3 / 12 / 0 |
| bevande | 5 / 5 / 0 | pesce | 2 / 9 / 0 |
| dolci | 4 / 5 / 3 | spezie | 2 / 7 / 7 |
| cereali | 4 / 8 / 3 | condimenti | 2 / 2 / 10 |
| legumi | 2 / 5 / 1 | casa | 1 / 2 / 8 |
| igiene | 2 / 5 / 0 | altro | 0 / 2 / 3 |

**La lettura che conta**: le emoji distinguono davvero le righe in frutta, verdura e
bevande; in latticini, carne e pesce danno quasi solo figure di famiglia (🧀, 🥩, 🐟), cioè
righe vicine con la stessa figura; in condimenti, spezie e casa quasi niente. Nessuna
figura risolve da sola i reparti dove le cose si somigliano: lì resta il nome.

Senza emoji, nel seme: sedano, finocchio, asparago, carciofo, mascarpone, panna, le
spezie in polvere (curcuma, cannella, cumino…), le salse (senape, maionese, ketchup,
salsa di soia), aceti, dadi, lieviti, i detersivi, pellicola, stagnola e carta forno.
Lo script della stima è nello scratchpad della sessione; le due tabelle di classificazione
sono a mano e discutibili caso per caso, l'ordine di grandezza no.

## 3. Le tre direzioni

### A. Emoji dell'ingrediente, ripiego sull'icona del reparto — **raccomandata; decisa da Mattia il 2026-10-07**

- **Cosa si vede**: un quadratino da 28 px a sinistra del nome, fondo `page`, con l'emoji
  dell'ingrediente a 18 px; dove non c'è, l'icona Tabler del reparto in `ink-faint`
  (monocroma: niente tinte sulle righe).
- **Contrasto**: il ripiego `ink-faint` sul quadratino `page` sta a 4,80:1 in chiaro e
  6,82:1 in scuro (un segno chiede 3:1, WCAG 1.4.11). Il quadratino `page` sul fondo `card`
  sta a 1,11:1 nei due temi, di proposito: è un appoggio, non un bordo che dice qualcosa.
  Le emoji sono multicolori e non hanno un rapporto misurabile; non portano testo.
- **Dati**: una colonna `ingredients.emoji`, testo nullabile. **La decide l'AI una volta**
  per gli ingredienti che non ce l'hanno: un comando come `decide_units`
  (`app.cli.decide_emoji`), a lotti di un centinaio di nomi, scrive solo dove la colonna è
  vuota e solo un'emoji di un **elenco chiuso** (le emoji di cibo, bevande e casa fino alla
  versione decisa in §5, in `backend/app/domain/`): una risposta fuori elenco lascia la
  colonna vuota, cioè il ripiego, come «una risposta che non si può verificare non si
  applica». Costo: ~900 nomi brevi, qualche migliaio di token in tutto, molto sotto il
  tetto di 1 $/giorno. **Si corregge in Anagrafica** (S9): un selettore dell'elenco chiuso
  nella scheda dell'ingrediente, e «nessuna». Una scelta a mano non viene mai riscritta
  dall'AI, perché l'AI scrive solo sulle colonne vuote.
- **Perché niente `decided_by` e niente undo come nelle decisioni dell'import**: l'emoji
  non lega niente a niente, non cambia una disponibilità né una ricetta. Sbagliata, è una
  figurina sbagliata, e si corregge in un tocco dove si corregge il resto. Le decisioni
  dell'import hanno l'undo perché toccano alias e ricette.
- **API**: `PantryItemOut` prende `ingredient_emoji: str | None`. Il reparto c'è già
  (`ingredient_category`), quindi il ripiego si decide nel client con `departmentStyle`,
  come fa `Section`. Nessuna logica di dominio nel client: l'emoji è un dato, non un
  calcolo.
- **Accessibilità**: la figura è `aria-hidden`. Senza, uno screen reader leggerebbe
  «formaggio Mozzarella».
- **Il rischio vero**: le emoji hanno l'aspetto del telefono, non dell'app (Samsung, Google
  e Apple le disegnano diverse), e quelle recenti su un sistema vecchio diventano un
  quadratino vuoto. Si contiene con l'elenco chiuso fermo a una versione (§5).

### B. Foto del prodotto, poi emoji, poi icona

- **Cosa si vede**: la foto di Open Food Facts (`products.image_url`) quando la voce ha un
  prodotto che ce l'ha; per le altre la A.
- **Pro**: per le confezioni di marca è il segno più immediato — si riconosce il colore
  della confezione prima ancora del nome.
- **Contro**:
  - è **una parte delle righe**: gli sfusi non hanno prodotto, i prodotti creati a mano non
    hanno foto. Tre linguaggi nella stessa colonna (foto, emoji, icona grigia);
  - **in scuro** le foto, quasi tutte su fondo bianco, sono le macchie più chiare della
    pagina: il bianco sul `card` scuro sta a 16,94:1, più della scritta `ink`;
  - **rete**: ogni dispensa aperta chiede N immagini a un server di terzi, che vede quali
    prodotti si hanno in casa; senza rete le foto non ci sono, a meno di farle passare dal
    service worker o di copiarle sul nostro server (lavoro in più, e spazio);
  - a 28 px una foto si riconosce per il colore, non per il contenuto.
- **Dove invece sta bene**: nella scheda di conferma dell'ingresso diretto (S3,
  `docs/superpowers/specs/2026-10-06-ingresso-diretto-bozza.md` §4.4) e nella scheda del
  prodotto, dove la foto è grande e una sola. Non sulle righe.

### C. Icona di Tabler per ingrediente, monocroma

- **Cosa si vede**: lo stesso set di icone dell'app, una per ingrediente dove Tabler ce
  l'ha, l'icona del reparto altrove. Tutto in `ink-faint`, coerente coi due temi.
- **Pro**: nessuna dipendenza dal telefono, nessuna colonna (una mappa fissa nel client,
  decisa a mano una volta), i token valgono come per ogni altra icona.
- **Contro**: copre poco (16% giusta, 54% ripiego sul seme), e senza colore una figura
  monocroma da 18 px si legge poco più del testo che le sta accanto. Dentro una sezione,
  più di metà delle righe ripete l'icona del titolo. Non risolve il problema che S12
  pone. Una mappa fissa nel client per ingredienti che nascono ogni giorno (import,
  anagrafica) andrebbe anche tenuta, mentre la colonna di A si riempie da sé.

### Confronto

| | A. Emoji | B. Foto | C. Tabler |
|---|---|---|---|
| Righe con una figura propria (seme) | 31% giusta, 47% di famiglia | solo le voci con prodotto e foto, più A | 16% giusta, 30% di famiglia |
| Riconoscibile senza leggere | sì in frutta, verdura, bevande | sì per le marche | poco |
| Due temi | invariata | foto bianche in scuro | perfetta |
| Dati | una colonna, l'AI una volta, Anagrafica | `image_url` c'è già | nessuno |
| Rete e privacy | niente | richieste a terzi | niente |
| Costo | medio | medio-alto (cache delle foto) | basso |

## 4. Raccomandazione

**A**, con l'icona monocroma del reparto come ripiego, sulle righe della Dispensa. B per le
schede grandi (S3, il prodotto), non per le righe. C no.

È una raccomandazione con un limite dichiarato: A rende riconoscibili soprattutto frutta,
verdura e bevande, e poco latticini, carne e pesce. Se sul telefono quel limite si sente,
la mossa successiva non è un'altra figura ma S15 (reparti collassabili) e la ricerca che
c'è già (S11).

## 5. Decisioni per Mattia

1. **Direzione A** (emoji con ripiego) — raccomandata. **Deciso da Mattia il 2026-10-07: A.**
2. **Fino a quale versione di emoji**: raccomandato **Emoji 14.0** (2021): esclude 🫚
   zenzero e 🫛 baccello (15.0) e il fungo marrone (15.1), ma si vede sui telefoni
   aggiornati dal 2022 in poi. Se il telefono è recente, 15.0. **Deciso da Mattia il
   2026-10-07: Emoji 14.0.**
3. **Solo la Dispensa, o anche Lista, Sistema la spesa e il foglio della cottura**:
   raccomandato **solo la Dispensa** per cominciare; l'emoji arriva in `PantryItemOut` e
   basta. Allargarla dopo è aggiungere un campo a tre risposte. **Deciso da Mattia il
   2026-10-07: solo la Dispensa.**
4. **Chi decide l'emoji di un ingrediente nuovo** (creato a mano, dall'import, dalla
   coda): raccomandato **nessuno al momento della creazione** — nasce senza, mostra il
   ripiego, e il comando dell'AI la riempie quando si lancia (come `decide_units`).
   L'alternativa, chiederla nel modulo del nuovo ingrediente, aggiunge un campo a R12 e a
   S6 per una figurina. **Deciso da Mattia il 2026-10-07: nessuno alla creazione.**
5. **Una foto nella scheda del prodotto e nella scheda di conferma di S3** (la parte buona
   di B): raccomandata, ma come voce a sé, perché porta con sé la domanda delle immagini di
   terzi. **Deciso da Mattia il 2026-10-07: voce a sé** (l'`idea` P3 già nel backlog).

## 6. Fuori scope

- Le foto sulle righe (B), e copiare le immagini di Open Food Facts sul server.
- Fondi colorati sulle righe (chiusi dalla spec T3 §3.3).
- Un'emoji per prodotto: la figura è dell'ingrediente, come la disponibilità.
- Un font di emoji incluso nell'app (Noto Color Emoji pesa megabyte; anche ritagliato è
  un peso per una figurina).
- Il layout da desktop.

## 7. Se si fa: cosa deve provare il piano

- `theme.test.ts`: `ink-faint` su `page` ≥3:1 nei due temi (il ripiego è un segno).
- `e2e/style.spec.ts`: la Dispensa a 375 px senza scorrimento orizzontale con la figura, in
  chiaro e in scuro; il nome più lungo del seme va a capo e non spinge le tacche fuori.
- Backend: l'elenco chiuso rifiuta un'emoji fuori elenco (test a tabella), il comando
  scrive solo sulle colonne vuote, la correzione dall'Anagrafica passa dal servizio unico
  `registry.py`.
- Sul telefono (Mattia): le emoji del proprio telefono, a colpo d'occhio, in una dispensa
  vera di una trentina di voci.
