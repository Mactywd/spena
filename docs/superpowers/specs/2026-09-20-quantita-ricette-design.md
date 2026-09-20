# Le quantità strutturate nelle ricette — design

**Data:** 2026-09-20
**Voci dei prossimi passi:** D1 (la decisione, presa il 2026-09-17) e la metà per
porzioni di R2
**Documenti d'origine:** `docs/prossimi-passi.md` (D1, R2), `CLAUDE.md` (decisione
fondante 1), `docs/superpowers/specs/2026-09-11-spena-design.md` §2

---

## 1. Il problema

La decisione fondante numero 1 dice «niente quantità, da nessuna parte», e che
`recipe_ingredients.quantity_text` è testo libero che **non deve mai entrare in un
calcolo**. Quella regola è stata scritta per la dispensa, dove ha comprato quel che
doveva comprare: nessuna conversione di unità, nessuna manutenzione giornaliera,
nessuna scadenza da aggiornare — cioè le cose che fanno abbandonare le app come
questa.

Ma tre voci della lista chiedono esattamente un calcolo su quel campo: *riporziona*,
*stima nutrienti di una ricetta*, *NutriScore*. Senza una decisione esplicita, quelle
tre fanno deragliare l'app per inerzia, un pezzo alla volta — ciascuna con la sua
piccola eccezione, nessuna delle quali guarda le altre.

Il lavoro non è «aggiungere le quantità»: è **restringere la decisione fondante a dove
serviva davvero, e dare alle ricette una struttura accanto al testo senza toccare una
riga della dispensa**.

## 2. Le decisioni prese

D1 è stata decisa il 2026-09-17 in `docs/prossimi-passi.md`. Il brainstorming del
2026-09-20 ne ha aggiunte cinque, e sono vincolanti per quel che segue.

1. **Le quantità stanno solo nelle ricette.** `quantity_text` resta la verità da
   mostrare e non viene mai riscritto né perso; `quantity_value` e `quantity_unit_id`
   gli si affiancano, entrambi annullabili. **La dispensa non cambia di una riga**:
   niente quantità, niente unità, niente scadenze.
2. **Il perimetro arriva fino al riporziona per porzioni**, e si ferma lì. Un fondo
   dati che nessuno legge può essere sbagliato per mesi senza che niente lo dica — è
   la prima lezione di `CLAUDE.md` allargata — quindi il fondo nasce con il suo primo
   consumatore vero. L'ancoraggio su un ingrediente («la ricetta è per 400 g di pasta,
   io ne faccio 150») e la domanda se il riporziona si salvi restano a R2.
3. **Il registro delle unità è aperto e lo popola l'AI.** Non un enum chiuso nel
   codice: una tabella che cresce quando una ricetta porta una parola nuova. L'AI
   decide singolare e plurale, la decisione porta `decided_by = "ai"` ed è
   correggibile. È la stessa forma di `import_terms`.
4. **I grammi fra parentesi sono di S4, non di questa spec.** «3 spicchi (15 g)» è la
   forma a video voluta, ma il peso **non è una proprietà dell'unità**: è una proprietà
   della coppia *ingrediente × unità* — una fetta di pane pesa 35 g e una di prosciutto
   8, un cucchiaio di olio 11 g e uno di sale 18, e anche `ml → g` dipende da cosa c'è
   dentro. Questa spec costruisce l'attacco e riempie solo quel che si riempie da sé
   (g, kg); S4 riempirà il resto con la sua provenienza marcata, senza migrazioni.
5. **Nessuna chiamata di rete dentro una scrittura.** Il parser è puro e offline;
   un'unità sconosciuta si deposita nel registro come «da decidere» e l'AI la decide
   dopo, in un passo separato. La via degradata diventa così la via normale: una strada
   sola invece di due, che è la prima lezione di `CLAUDE.md`.

## 3. Il modello

### 3.1 Il registro delle unità

Tabella nuova `units`, con la convenzione di casa — `UUIDMixin` più una chiave unica,
come `ingredient_aliases`:

```python
class Unit(UUIDMixin, TimestampMixin, Base):
    """Il vocabolario delle dosi, che cresce da sé.

    Non è un enum nel codice perché la fonte è un ricettario vero: ogni catalogo
    nuovo porta parole che non avevamo previsto, e una parola non prevista non deve
    poter bloccare una ricetta. Una riga senza `singular` è una parola incontrata e
    non ancora decisa: si mostra così com'è arrivata, e il riporziona la scala lo
    stesso.
    """

    __tablename__ = "units"

    key: Mapped[str] = mapped_column(String(30), unique=True)
    singular: Mapped[str | None] = mapped_column(String(30), nullable=True)
    plural: Mapped[str | None] = mapped_column(String(30), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(20), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    canonical_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("units.id", ondelete="RESTRICT"), nullable=True
    )
```

`key` è la parola come è arrivata dal testo, minuscola e ripulita: è quel che si è
visto, non quel che si vorrebbe aver visto.

`canonical_id` esiste per un caso solo e concreto: la fonte scrive sia «cucchiaio» sia
«cucchiai», e finiscono come due righe. Quando l'AI risponde che il singolare di
«cucchiai» è «cucchiaio» e quella chiave esiste già, la riga ci punta invece di
duplicarla. Senza questo, S4 dovrebbe riempire il peso due volte per la stessa unità,
e la seconda volta prima o poi divergerebbe dalla prima.

### 3.2 Le due colonne sulla riga di ricetta

```python
quantity_value: Mapped[Decimal | None] = mapped_column(Numeric(8, 3), nullable=True)
quantity_unit_id: Mapped[uuid.UUID | None] = mapped_column(
    UUID(as_uuid=True), ForeignKey("units.id", ondelete="RESTRICT"), nullable=True
)
```

più un vincolo, perché la quarta combinazione non ha senso:

```python
CheckConstraint(
    "quantity_unit_id IS NULL OR quantity_value IS NOT NULL",
    name="ck_recipe_ingredient_unit_needs_value",
)
```

`Numeric` e non `Float`: `0.1 + 0.2` deve fare `0.3` anche quando un giorno queste
righe si sommeranno per la nutrizione. Tre decimali bastano a `1/3`.

### 3.3 I tre stati di una riga, misurati sui dati veri

Il seme ha 26 ricette, 148 righe, 52 dosi distinte. Non è un campione teorico: è quel
che c'è.

| stato | esempi reali | quante | cosa ne fa il riporziona |
|---|---|---|---|
| `(NULL, NULL)` non parsata | `q.b.` (19), `abbondante`, `facoltativo` | ~22 | resta identica, ed è la risposta giusta |
| `(valore, NULL)` numero nudo | `1` (15), `2` (5), `1/2` (6), `4`, `10` | ~33 | scala e si ridisegna senza unità |
| `(valore, unità)` dose piena | `300 g`, `3 cucchiai`, `1 spicchio`, `80 ml` | ~93 | scala e si ridisegna al plurale |

Il numero nudo è la terza combinazione, non un caso degenere del secondo: «1» detto di
una cipolla vuol dire *una cipolla*, e a ×2 si scrive «2», non «2 pezzi». Inventare
un'unità che la fonte non ha scritto sarebbe una bugia piccola e permanente.

### 3.4 Perché memorizzare invece di parsare a ogni lettura

Parsare al volo eviterebbe la migrazione e il riparsare. Non si fa per due ragioni:
il ricettario intero di GialloZafferano renderebbe il parsing un costo per ogni
lettura di ogni schermata, e soprattutto **un campo derivato al volo non si può
interrogare in SQL** — la nutrizione e il motore di suggerimento dovranno filtrare e
sommare su queste colonne, e la sesta lezione di `CLAUDE.md` racconta cosa succede
quando un conto sul risultato finisce dietro a un limite.

La contropartita è che il parser migliorerà e i dati andranno rifatti: è il §7.2.

## 4. Il parser

### 4.1 Il contratto

`backend/app/domain/quantities.py`, accanto a `rules.py`, e con la stessa disciplina:
funzioni pure, nessun accesso al database, nessuna rete, provate a tavola.

```python
def parse_quantity(text: str | None) -> tuple[Decimal | None, str | None]:
    """Il numero e la parola dell'unità dentro una dose scritta a mano.

    Torna `(None, None)` per tutto ciò che non comincia con un numero: «q.b.»,
    «abbondante», «facoltativo». Non solleva mai: una dose che non si capisce non è
    un errore, è una dose che non si scala.
    """
```

Le regole, nell'ordine:

1. **il numero in testa**, e solo in testa: intero (`300`), decimale con virgola o
   punto (`1,5`), o frazione (`1/2` → `0.5`);
2. **la parola subito dopo** è l'unità, se c'è;
3. **tutto il resto è prosa e si ignora**: `1 litro di brodo` → `(1, "litro")`,
   `500 ml per la besciamella` → `(500, "ml")`,
   `1 confezione di sfoglie per lasagne` → `(1, "confezione")`. La prosa non si perde:
   sta in `quantity_text`, che resta intatto;
4. **le somme unite si sommano se l'unità è la stessa**: `merge_quantities` produce
   `500 g + 50 g` quando due righe della fonte collassano sullo stesso ingrediente
   (§«collasso per ingrediente» in `materialize.py`), e quella dose vale `(550, "g")`.
   **Unità miste** — `500 g + 2 cucchiai` — restano **non parsate**: la somma di due
   cose diverse non è un numero, e fingere che lo sia darebbe un riporziona sbagliato
   in silenzio;
5. **niente numero in testa** → `(None, None)`.

Una conseguenza che val la pena dire ad alta voce, perché sta nei dati veri: in
`2 medie` — due zucchine medie — la parola dopo il numero è un aggettivo, e diventa
un'unità. Non è un difetto da riparare: `2 medie` a ×2 si ridisegna `4 medie`, che è
giusto, e distinguere un aggettivo da un'unità vorrebbe dire analisi grammaticale
dentro un parser di numeri. L'unica cosa che conta è che la parola torni a video come
era, ed è quel che fa il registro.

La parola dell'unità si normalizza — minuscola, spazi e punti tolti — ma **non si
traduce e non si corregge**: «cucchiai» resta «cucchiai» finché l'AI non dice che il
suo singolare è «cucchiaio». Correggere qui sarebbe regole di lingua dentro un parser
di numeri.

### 4.2 Dove si chiama, e perché in un posto solo

In `create_recipe` (`backend/app/repositories/recipes.py`), che è **già l'unico punto
che scrive `recipe_ingredients`**: ci passano l'import (`materialize_ready`), il seme
(`app.cli.seed`), l'API (`POST /api/v1/recipes`) e la stesura AI, che finisce nella
stessa rotta. È lo stesso imbuto che solleva `NonFoodInRecipe`.

`create_recipe` prende oggi una lista di `(ingredient_id, role, quantity_text, note)`.
La firma non cambia: il parser gira dentro, e le colonne si riempiono da sé. Chi chiama
non deve ricordarsi niente, che è l'unico modo perché il quinto chiamante — quello che
non abbiamo ancora scritto — non se ne dimentichi.

Le unità sconosciute si depositano nella stessa transazione: `ensure_unit(session, key)`
torna la riga esistente o ne crea una con `singular`, `plural` e `decided_by` a `NULL`.

### 4.3 Due cose che non cambiano, e lo dico perché la tentazione c'è

**`default_role` continua a leggersi `q.b.` dalla stringa.** Ora che esiste
`quantity_value IS NULL` sembra naturale dedurre il ruolo da lì. Sono due domande
diverse: «è una dose che si aggiusta a piacere» e «non sono riuscito a parsare». Le
separa `abbondante`, che è la seconda ma non la prima. La regola primario/secondario
di `domain/rules.py` non si tocca.

**La dispensa non guadagna niente.** Nessuna colonna, nessuna unità, nessuna scadenza.
`pantry_items.fill_percent` resta quel che è: la posizione di un cursore, non una
quantità.

## 5. Il riporziona

### 5.1 Il ridisegno

`render_quantity(value: Decimal, unit: Unit | None) -> str`, pura, accanto al parser:

| | |
|---|---|
| numero | virgola decimale, zeri di coda tolti: `6`, `1,5`, `0,5` |
| plurale | singolare solo quando il valore è esattamente `1`; plurale altrimenti |
| unità non decisa | si usa `key` così com'è: degradazione visibile, mai un errore |
| unità assente | solo il numero: `1` → `2` |

A scala 1× **non si ridisegna niente**: si mostra `quantity_text`. Così `1/2 bicchiere`
resta `1/2 bicchiere` finché non tocchi il selettore, e diventa `1 bicchiere` a ×2.
Il ridisegno esiste per dire quel che il testo originale non può più dire, non per
riscriverlo quando dice già la verità.

### 5.2 L'API

`GET /api/v1/recipes/{id}` guadagna un parametro annullabile `servings`. Il fattore è
`servings / recipe.servings`, e il parametro si ignora quando `recipe.servings` è nulla.

`RecipeIngredientOut` guadagna due campi:

```python
quantity_display: str | None   # quel che va mostrato, già scalato e già al plurale
quantity_scaled: bool          # questa riga ha davvero seguito la scala?
```

`quantity_text` resta nel corpo: è la verità, e altre schermate la leggono.
Senza il parametro, `quantity_display == quantity_text` e `quantity_scaled` è `False`
ovunque — cioè la schermata di oggi non cambia di un pixel.

`RecipeOut` guadagna `scaled_to: int | None` (le porzioni chieste, se applicate) e
`unscalable_lines: int`.

**`servings` uguale a quelle della ricetta è come non averlo passato**: fattore 1,
`quantity_display == quantity_text`, `quantity_scaled` falso ovunque. Il ridisegno
entra in scena solo quando il fattore è diverso da 1, perché a 1× il testo originale
dice già la verità meglio di qualunque cosa sappiamo riscrivere.

**Il conto sta nel backend**, non nel client, ed è la riga di `CLAUDE.md` che tiene in
piedi la porta a Capacitor: *il frontend chiede se una ricetta è cucinabile, non se lo
calcola*. In TypeScript vorrebbe dire spedire il registro delle unità al client e
tenere le stesse regole di plurale in due lingue, dove a scollarsi per prima sarebbe
quella che nessun test guarda.

### 5.3 Il comando a video

In `RecipeDetailScreen`: un selettore «Per *N* porzioni» che parte da `recipe.servings`,
con due bersagli da pollice da 44px. Cambiarlo rilegge la ricetta con `?servings=N`; il
client mostra `quantity_display` e non fa aritmetica.

È **una vista**: esci dalla ricetta e se ne dimentica. Se il riporziona si salvi è un
TBD di R2, e questa metà non ne ha bisogno.

Quando `recipe.servings` è nulla il selettore **non compare** e la ricetta si legge come
oggi. Non è un vicolo cieco: non toglie niente a nessuno, e dare un valore alle porzioni
è una modifica di ricetta, che non esiste ancora in nessuna forma.

### 5.4 La copertura si dichiara

Quando la scala è diversa da 1 e almeno una riga non si è scalata, sotto l'elenco una
riga sommessa: **«3 dosi su 14 non si riscalano: restano come sono.»**

Nessuna percentuale a effetto, e nessuna riga riscritta a caso per far tornare il
conto. È la stessa onestà di «i nutrienti mancanti restano mancanti»: l'assenza si
dichiara, non si riempie.

## 6. Le forme delle unità: il lavoro dell'AI

`backend/app/services/unit_forms.py`, più il comando `python -m app.cli.decide_units`.

- prende tutte le `units` con `decided_by IS NULL` e le chiede **in una sola chiamata**:
  sono una manciata di parole, e sul tetto di 1$/giorno non si sentono;
- `LlmCallSite.UNIT_FORMS`, membro nuovo dell'enum in `services/llm.py`. L'enum non ha
  default di proposito — una sezione che si dimenticasse di dichiararsi finirebbe in un
  secchio muto — quindi la torta delle spese di H1 continua a tornare;
- schema stretto, come ogni altra chiamata di questo progetto: una lista di
  `{key, singular, plural}`, ogni proprietà in `required`, `additionalProperties: false`.

**Si applica solo quel che si può verificare**, che è la regola già scritta per i
termini dell'import: la `key` tornata dev'essere una di quelle chieste, `singular` e
`plural` non vuoti e entro i 30 caratteri. Quel che non passa non si scrive: la parola
resta non decisa e si continua a mostrarla grezza. Se il `singular` coincide con una
`key` che esiste già, si riempie `canonical_id` invece di duplicare.

**AI irraggiungibile:** `LlmUnavailable` è già la forma di casa. Non si scrive niente,
le unità restano non decise, il riporziona continua a scalare mostrando la parola come
è arrivata. Nessuno schermo mostra un errore, perché per l'utente non è successo niente.

**Undo:** `python -m app.cli.decide_units --azzera <key>` riporta una riga a non decisa,
e la chiamata successiva la ridecide.

## 7. La migrazione e i comandi

### 7.1 La migrazione `0008`

Crea `units`, aggiunge le due colonne e il vincolo. **Non riempie niente.**

### 7.2 Il riempimento, che è un comando e non un passo dati

`python -m app.cli.reparse_quantities`, rieseguibile: rilegge `quantity_text` di ogni
riga e riscrive `quantity_value` e `quantity_unit_id`, depositando le unità nuove.

Non sta dentro la migrazione perché **il parser migliorerà**: il primo catalogo vero
porterà forme di dose che 26 ricette non hanno, e migliorare il parser non deve voler
dire scrivere un'altra migrazione. È esattamente la ragione per cui `app.cli.reindex`
esiste già per gli embedding.

Il comando dichiara quel che ha fatto: quante righe parsate, quante no, quante unità
nuove depositate.

## 8. Le prove

- **`test_quantities.py`, a tavola sulle 52 dosi vere del seme**, non su un campione
  inventato: sono l'unico caso di prova che è anche un dato di produzione. Più le somme
  unite (stessa unità e miste) e le malformate.
- **`render_quantity`**, a tavola: singolare a 1, plurale altrove, virgola decimale,
  unità non decisa, unità assente.
- **Un test che passa da `create_recipe` vero** e verifica che le colonne si riempiano
  e che l'unità nuova compaia in `units`. Costruire a mano la riga proverebbe una copia
  che non gira — prima lezione di `CLAUDE.md`.
- **L'API**: con `?servings=N` scala e lascia intatte le non parsate; senza parametro il
  corpo è identico a oggi; con `recipe.servings` nulla il parametro si ignora.
- **`unit_forms`** su risposta registrata, compreso il rifiuto di una risposta non
  verificabile (chiave non chiesta, forma vuota) e il ramo `LlmUnavailable`.
- **Frontend**: il selettore compare solo quando `servings` c'è, rilegge al cambio, e
  mostra `quantity_display` senza calcolare niente.
- **Nel browser vero**, a 375px: i due bersagli del selettore sopra i 44px, come già la
  X delle pastiglie del filtro e il cursore della dispensa in `frontend/e2e/style.spec.ts`.
  Il peso visivo non lo vede jsdom — quarta lezione di `CLAUDE.md`.

## 9. La messa in produzione

1. `git pull --ff-only` e `docker compose -f docker-compose.prod.yml up -d --build --wait`
   — **il `-f` non è opzionale**, terza lezione di `CLAUDE.md`;
2. la migrazione `0008` si applica all'avvio, come la `0007`;
3. `python -m app.cli.reparse_quantities` nel container del backend: 148 righe, istantaneo;
4. `python -m app.cli.decide_units`: una chiamata, una ventina di parole;
5. verifica a mano su una ricetta con dosi miste — «Pasta al pomodoro» ha `180 g`,
   `400 g`, `1 spicchio`, `2 cucchiai` e `q.b.`: cinque dosi, ma solo due dei tre
   stati del §3.3, `(valore, unità)` dose piena e `(NULL, NULL)` non parsata. Per il
   terzo stato, il numero nudo, serve un'altra ricetta — «Frittata di patate» o
   «Minestrone di verdure» ne hanno.

Fra il passo 2 e il passo 3 le ricette hanno le colonne vuote: il selettore c'è e
scala **zero righe**, dichiarando «14 dosi su 14 non si riscalano». È brutto e non è
rotto, e dura il tempo di un comando.

Fra il passo 3 e il passo 4 le dosi sono parsate ma le unità non hanno ancora
singolare e plurale decisi: a una porzione lo schermo mostra la parola grezza così
com'è arrivata dal testo, non quella corretta — misurato, non immaginato: «Pasta al
pomodoro» a una porzione legge «1 cucchiai», perché `cucchiai` è la parola che la
fonte ha scritto e nessuno ne ha ancora deciso il singolare. È brutto e non è rotto,
e dura il tempo di un comando.

## 10. Fuori ambito, e perché

- **I grammi della coppia ingrediente × unità**: è S4, §2 decisione 4.
- **Il riporziona ancorato a un ingrediente** e **il salvataggio di una riporzionatura**:
  restano a R2, con i loro TBD.
- **Una schermata per correggere un plurale sbagliato.** Il registro è una ventina di
  righe, un errore si vede nella ricetta stessa, e si corregge dal comando. Va in
  `prossimi-passi.md` come voce aperta: dichiarata, non nascosta.
- **Modificare le porzioni di una ricetta**: non esiste una modifica di ricetta, e
  inventarla qui sarebbe un'altra spec dentro questa.
- **La nutrizione di una ricetta**: ha bisogno dei grammi, cioè di S4.

## 11. Cosa va emendato quando questo lavora

Insieme, nello stesso lavoro, perché una delle due lasciata indietro diventa la
documentazione che mente:

- **`CLAUDE.md`, decisione fondante 1**: il paragrafo che dice che `quantity_text` non
  deve **mai** entrare in un calcolo, e il riquadro che annuncia questo lavoro come
  «deciso ma non ancora costruito»;
- **`docs/superpowers/specs/2026-09-11-spena-design.md` §2**: la stessa affermazione;
- **`docs/prossimi-passi.md`**: D1 fatta, R2 dimezzata, e la voce nuova sulla correzione
  dei plurali.

In entrambi i testi la forma dell'emendamento è la stessa: **la dispensa tiene la regola
intera** — niente quantità, niente unità, niente scadenze — e sono le ricette, e solo
loro, a guadagnare una struttura accanto al testo.
