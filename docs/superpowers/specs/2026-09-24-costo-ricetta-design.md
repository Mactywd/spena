# R9 — Il costo della ricetta

Data: 2026-09-24. Voce di `docs/prossimi-passi.md`: **R9**. Brainstorming nella
conversazione dello stesso giorno, con le cinque decisioni accettate così come sono
scritte qui.

## 1. Cosa e perché

Ogni ricetta può dire quanto costa, su una scala da 1 a 5, disegnata come cinque `€`
di cui i primi *n* in nero e gli altri in grigio chiaro: `€€€··` è una ricetta da 3.

È un **livello**, non una cifra in euro, per la stessa ragione della decisione
fondante 1: un prezzo vero andrebbe tenuto aggiornato e comincerebbe a mentire il
giorno in cui si smette. Il livello si scrive una volta.

Chi lo leggerà davvero è **P3** (la pianificazione su più giorni con un budget medio
per pasto). R9 viene prima perché è piccola, indipendente, e perché ogni ricetta
importata oggi senza costo andrebbe rimessa a posto dopo.

## 2. Le decisioni

1. **Annullabile.** Una ricetta senza costo non è una ricetta da 1: «ciò che manca
   resta mancante» vale anche qui. Sulla scheda del ricettario un costo assente non
   si mostra; nel dettaglio si legge «Costo: non indicato» e si può scegliere.
2. **Si imposta toccando i `€` nel dettaglio della ricetta.** Tocchi il terzo e la
   ricetta diventa da 3; ritocchi quello già scelto e il costo torna non indicato.
   Una rotta nuova, `PATCH /api/v1/recipes/{id}`, che oggi accetta solo `cost`. È
   anche la correzione di un costo sbagliato che arriva dalla fonte.
3. **La bozza AI lo propone**, nella stessa chiamata e quindi senza spesa in più.
   Si vede nel modulo prima di salvare e si cambia come nel dettaglio. Lo stesso
   selettore serve alla ricetta scritta a mano, che vive nello stesso modulo.
4. **L'import legge «Costo» dalla pagina di GialloZafferano**, così R4 lo troverà
   fatto. E un comando, `python -m app.cli.reread_costs`, riscarica le pagine delle
   ricette già importate e scrive **solo** il costo.
5. **Niente filtro né ordinamento per costo**, per ora.

## 3. Il dato

`recipes.cost`: `SMALLINT` annullabile, con
`CHECK (cost IS NULL OR cost BETWEEN 1 AND 5)`. Migrazione `0010_costo_ricette`,
nessun passo dati.

Viaggia in `RecipeCreate` (facoltativo, 1–5), in `RecipeOut` e in
`RecipeSummaryOut` (`int | None`), e in `DraftOut` (proposta dell'AI).

## 4. La fonte

GialloZafferano scrive nella pagina, fuori dal JSON-LD:

```html
<span class="gz-name-featured-data">Costo: <strong>Basso</strong></span>
```

Cinque valori, che diventano i nostri cinque gradini:

| Pagina | Livello |
|---|---|
| Molto basso | 1 |
| Basso | 2 |
| Medio | 3 |
| Elevato | 4 |
| Molto elevato | 5 |

Qualunque altra parola, o l'assenza del blocco, è **nessun costo**, mai un gradino
indovinato. La lettura sta in `parse_recipe` (funzione pura, già il nucleo verificato
dell'import) e finisce nel `payload` come `"cost"`; la materializzazione la copia
sulla ricetta come copia già categoria e tempi.

### `reread_costs`

Per ogni ricetta `source = 'dataset'` con `source_ref` che è un indirizzo e
`cost IS NULL`: una pagina alla volta, con la stessa pausa, lo stesso client e le
stesse regole di fermata dell'import (`SourceUnavailable` due volte di fila → ci si
ferma, il lavoro fatto resta). Scrive `recipes.cost` e anche `payload["cost"]` della
riga di `recipe_imports` corrispondente, perché un annulla e una rimaterializzazione
non lo perdano. Commit a ogni pagina.

Solo le ricette **senza** costo: un costo messo a mano non si sovrascrive, e
rilanciare il comando dopo un'interruzione riprende da dove era.

## 5. La bozza AI

Lo schema della bozza acquista `"cost"`: intero 1–5 o `null`. Il prompt spiega il
gradino in una riga (il costo degli ingredienti per la ricetta intera, da «molto
basso» a «molto elevato»). Un valore fuori scala o non intero diventa `null`: un
campo vuoto è meglio di un gradino inventato. Stessa chiamata, stesso `call_site`.

## 6. Lo schermo

Due componenti in `frontend/src/components/ui/`:

- **`CostMeter`**, sola lettura: cinque `€`, i primi *n* nel colore del testo
  (`text-ink`), gli altri in un grigio chiaro nuovo, `--color-ink-ghost`, nell'unico
  blocco `@theme`. Un'etichetta accessibile, «Costo 3 su 5»: il grigio da solo non
  dice niente a uno screen reader. Se il costo è assente non disegna niente.
- **`CostPicker`**, per scegliere: gli stessi cinque `€` come cinque bottoni con
  bersaglio da pollice (44px), `aria-pressed` su quello scelto, ritocco che azzera.

Dove:

- **scheda del ricettario**: `CostMeter` sulla riga dei minuti;
- **dettaglio**: `CostPicker` sotto la descrizione, con «Costo» accanto e «non
  indicato» quando manca. Un salvataggio fallito lo dice accanto, e il valore
  mostrato resta quello salvato, non quello toccato;
- **modulo «Scrivi una ricetta»**: `CostPicker` sotto le porzioni, precompilato
  dalla bozza.

Che il grigio si distingua dal nero è CSS, quindi la prova sta in
`frontend/e2e/style.spec.ts`, non in jsdom.

## 7. Fuori

- filtro o ordinamento per costo nel ricettario;
- pesi non lineari per gradino (decisi rinviati in P3);
- costo per porzione: il costo è di quel che si cucina (chiuso con P3).
