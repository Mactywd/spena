# La scadenza in dispensa — disegno

**2026-09-21.** Questa spec costruisce S7, la metà pratica di **D5**
(`docs/prossimi-passi.md`), decisa il 2026-09-20. D5 è la decisione; qui c'è la
forma.

## 1. Cosa si costruisce

Quando un prodotto entra in dispensa si può scrivere anche la sua data di scadenza.
La dispensa la mostra sulla riga, e **quando mancano sette giorni o meno la pastiglia
cambia colore**; dal giorno dopo la scadenza lo dice più forte. La data è sempre
facoltativa, si può scrivere dopo, e si può correggere.

Tre pezzi: una colonna annullabile, un campo data in due schermate, una pastiglia con
un colore suo.

## 2. Da dove viene, e cosa è già deciso

La decisione fondante 1 di `CLAUDE.md` dice che la dispensa non conosce «quantità,
unità **o date di scadenza**». Non è una dimenticanza: è un no scritto apposta, per
togliere la manutenzione giornaliera che fa abbandonare le app come questa. D1
(2026-09-20) ha ristretto quel no *alle ricette*, lasciando la dispensa intera. D5 lo
riapre dal lato della dispensa, e per una ragione precisa: **una quantità va
mantenuta, una scadenza no.** Una quantità è sbagliata ogni volta che usi la cosa,
finché non la correggi; una data di scadenza si scrive una volta sola, con il
barattolo in mano, e non si tocca mai più. E se la lasci vuota non succede niente.

D5 ha già chiuso le due domande che decidevano la forma, e questa spec le eredita
senza riaprirle:

- **Lo stato resta la sola verità.** La scadenza non entra in `status_for_fill`, non
  è un quarto stato, e una cosa scaduta resta dov'è: disponibile, contata dalle
  ricette come il giorno prima. Niente diventa non cucinabile di notte senza che
  nessuno abbia toccato niente. La riga lo dice, e chi cucina sceglie qualcos'altro.
- **Il colore non è il giallo.** La zona gialla del cursore vuol già dire «comincia a
  mancare» (`LOW_MAX_FILL = 30`), e due fatti diversi sullo stesso colore non ne
  dicono più nessuno.

## 3. Il dato

`pantry_items.expires_on`, una `DATE` **annullabile**, migrazione `0009`.

- **Sull'elemento di dispensa**, non sull'ingrediente e non sul prodotto: scade
  *quel* barattolo, non «lo yogurt greco» e nemmeno «Fage Total 0%». Vale per le mele
  sfuse come per il barattolo di marca, ed è quel che rende la colonna vera al secondo
  barattolo dello stesso prodotto.
- **`DATE` e non un timestamp.** La scadenza è un giorno, non un istante; trattarla
  come un istante introduce un fuso orario in un dato che non ne ha.
- **Nessun `CHECK`, nessun default.** Una data già passata è legittima: capita di
  mettere in dispensa qualcosa che scade domani, o di scrivere la data il giorno dopo
  guardando il barattolo. Il vincolo che avrebbe senso — «non nel passato» — sarebbe
  falso metà delle volte in cui viene scritto.
- Il modello segue `fill_percent`, che è il precedente esatto: un dato annullabile
  che *non* è una quantità, con il commento che spiega perché non lo è.

## 4. La regola, e il giorno di calendario

In `backend/app/domain/rules.py`, accanto a `status_for_fill`, perché è lo stesso
genere di cosa — un fatto di dominio che il client chiede e non calcola:

```python
EXPIRY_SOON_DAYS = 7


class ExpiryState(StrEnum):
    SOON = "soon"
    EXPIRED = "expired"


def expiry_state(expires_on: date | None, today: date) -> ExpiryState | None:
    """Nessuna data → nessun segnale. È il caso normale e non costa niente."""
    if expires_on is None:
        return None
    if expires_on < today:
        return ExpiryState.EXPIRED
    if (expires_on - today).days <= EXPIRY_SOON_DAYS:
        return ExpiryState.SOON
    return None
```

`today` **entra come argomento**: è quel che rende la funzione pura e provabile per
tabella su date scritte a mano, che è la prima cosa da scrivere. Il confine è
dichiarato: `expires_on == today` è `SOON` e non `EXPIRED` — quel che scade oggi si
può ancora mangiare oggi, e «scaduto» comincia il giorno dopo.

**Il fuso, che oggi nel backend non esiste.** In `backend/app/` non c'è un solo
`ZoneInfo`: ogni cosa è `datetime.now(UTC)`, e per gli *istanti* è giusto così. Per un
*giorno di calendario* no. Fra mezzanotte e le due, d'estate, la data UTC è ancora
ieri: la pastiglia cambierebbe colore con un giorno di ritardo per due ore al giorno.
È lo stesso difetto del browser che sottrae date, spostato sul server — e la ragione
per cui D5 aveva messo il conto sul server non era «il server è più bravo», era «il
conto si fa in un posto solo, dichiarato».

Quindi accanto alla funzione pura:

```python
PANTRY_TZ = ZoneInfo("Europe/Rome")


def today_in_pantry() -> date:
    """Che giorno è, dove sta la dispensa. Non UTC: vedi §4 della spec."""
    return datetime.now(PANTRY_TZ).date()
```

**E una cosa che qui non serve.** `backend/tests/test_frontend_fill_zones.py` esiste
perché il cursore *deve* conoscere `LOW_MAX_FILL` per dipingere le sue zone, e due
linguaggi che portano lo stesso numero divergono. Qui il numero sette **non
attraversa il confine**: il server manda il verdetto già preso, il TypeScript non
conosce la soglia, e non c'è niente da tenere allineato. È il modo più solido di
passare quel test: non averne bisogno.

## 5. L'API

**In uscita.** `PantryItemOut` (`backend/app/schemas/pantry.py`) prende due campi:

```python
expires_on: date | None
expiry: ExpiryState | None   # "soon" | "expired" | null
```

Due e non uno: la **data** serve per mostrarla e per riaprirla in correzione, il
**verdetto** serve per colorare. Mandare solo la data costringerebbe il browser a
rifare il conto — cioè il difetto che §4 evita. Mandare solo il verdetto perderebbe
quel che l'utente ha scritto. Si riempiono in `_to_out` (`backend/app/api/pantry.py`),
il posto unico da cui esce ogni voce di dispensa.

**All'ingresso dalla spesa.** `StockEntryIn` (`backend/app/schemas/shopping.py`) e la
dataclass `StockEntry` (`backend/app/repositories/shopping.py`) prendono
`expires_on: date | None = None`, che `stock_items` passa ad `add_pantry_item` —
anch'esso con un parametro nuovo annullabile. Resta tutto dentro la stessa
transazione: la sistemazione della spesa è tutto-o-niente, e una data non cambia
questa proprietà.

**In correzione**, ed è l'unico punto con un intoppo vero. `PATCH /api/v1/pantry/{id}`
oggi distingue le richieste con `is not None`, e il commento su `archived` spiega
perché il campo è annullabile: «non l'ho detto» e «mettilo a falso» sono due richieste
diverse. **Per una data quel trucco non funziona**, perché `null` *è* la richiesta —
«cancella la scadenza» — e non l'assenza di richiesta. Si risolve chiedendo a Pydantic
quali campi sono arrivati davvero:

```python
elif "expires_on" in payload.model_fields_set:
    item = await set_expiry(session, item_id, payload.expires_on)
```

`model_fields_set` non è usato da nessuna parte in questo progetto: è un meccanismo
nuovo, di una riga, e va commentato sul posto. Il ramo **deve** stare nella catena
`if/elif` con questa forma e non con `is not None`, altrimenti un corpo
`{"expires_on": null}` cade nell'`else` e torna «niente da modificare» — cioè la
cancellazione fallisce dicendo che non c'era niente da fare. È il caso che il test
deve coprire per primo.

Lato repository, `set_expiry` sta in `backend/app/repositories/pantry.py` accanto a
`set_fill` e `set_status`, e **non tocca `status_changed_at`**: la scadenza non è un
cambio di stato, ed è esattamente quel che D5 ha deciso.

## 6. Le tre superfici

**All'ingresso — «Sistema la spesa».** Ogni riga mostra un «+ scadenza» piccolo;
toccandolo compare il campo data di quella riga. Chi la scadenza non la usa vede una
schermata quasi identica a oggi, che è quel che D5 chiede: il vuoto non deve costare
niente. È la scelta giusta anche per il peso — `StockingScreen.tsx` è già lo schermo
più denso dell'app (609 righe, con abbinamento ingrediente, scanner, catalogo e il
ramo del mismatch), e dieci campi vuoti a video sarebbero rumore permanente.

Il controllo è un `<input type="date">` nativo, che sul telefono apre il calendario di
sistema. Nessun selettore scritto a mano: una data è il caso in cui il controllo
nativo è migliore di qualunque cosa si possa costruire, e non costa manutenzione.

**Nella riga di dispensa — la pastiglia.** Accanto a `StatusChip`, una pastiglia sua
che porta la data. Due pastiglie affiancate dicono due fatti diversi senza
contendersi niente, e lo sfondo della riga resta libero — il cursore verde sotto una
riga tinta manderebbe due messaggi a colpo d'occhio.

Il testo, e non è un dettaglio: **«Scade il 28/09/2026»** prima, **«Scadeva il
20/09/2026»** dopo. Il tempo verbale porta la differenza e **nessuna delle due forme
ha un genere**: «scaduto» e «scaduta» costringerebbero a scegliere fra «Fage Total
0%» e «passata di pomodoro», e una delle due sarebbe sempre sbagliata. La data si
formatta con `toLocaleDateString("it-IT")`, che nel progetto ha già un precedente in
`CookSheet.tsx`.

**In correzione — la stessa pastiglia.** Toccandola si riapre il campo data, e si può
anche svuotare. Questa è la strada che rende vera la scelta del campo facoltativo: chi
ha saltato il momento dell'ingresso, o ha battuto male, non è in un vicolo cieco.

**L'unico punto in cui il vuoto costa qualcosa.** Se la data non c'è, la riga mostra un
«+ scadenza» discreto dove starebbe la pastiglia. Senza, la correzione non avrebbe da
dove cominciare e l'unica strada resterebbe l'ingresso — cioè il vicolo cieco appena
evitato. È un elemento piccolo e permanente su ogni riga, ed è un costo dichiarato,
non una svista.

**S3** (ingresso diretto in dispensa) oggi non c'è: `addPantryItem` crea la voce con
il solo ingrediente. Quando S3 si farà, avrà lo stesso campo — `add_pantry_item` lo
accetta già dopo questo lavoro, quindi resta solo da mostrarlo. Non è lavoro di questa
spec.

## 7. Il colore

Un token nuovo nel blocco `@theme` di `frontend/src/index.css`, **a due intensità**,
sulla falsariga di `StatusTone` (`fill` e `tint`): tinta leggera mentre la scadenza si
avvicina, piena da scaduta. È lo stesso fatto a due distanze, e un terzo colore in una
riga che ne porta già due smetterebbe di dirne nessuno.

Vincoli sul colore, tutti e tre da rispettare insieme:

- **distinto** dai tre già presi — il verde `--color-brand`, l'ambra di `low`
  (`--color-low`, `#9a5f0c`) e il rosso `--color-danger` — a colpo d'occhio e non solo
  da vicino;
- **sopra 4.5:1** su quel che gli sta dietro, come ogni altro: questa app si legge in
  corsia alla luce del giorno;
- dichiarato **solo** nel blocco `@theme`. Nessuna schermata nomina un colore grezzo:
  grepare `src/` per `amber` o `violet` deve continuare a non trovare niente.

Le parole e i toni stanno in un file loro, `expiryLabels.ts`, per la ragione scritta
in `statusLabels.ts`: accanto a un componente un export costante rompe il fast
refresh, e una seconda mappa dei colori è il modo di farle divergere.

**La trappola dello stile, già pagata una volta.** La regola base che veste i campi è
scritta per selettore, con una lista di esclusioni
(`input:not([type="checkbox"], [type="radio"], …)`). Un `input[type="date"]` oggi in
quel foglio non compare mai, e il commento lì sopra racconta com'è andata la prima
volta: un campo che rendeva trasparente e senza bordo mentre 157 test jsdom passavano.
Tailwind genera il CSS alla costruzione e jsdom non lo calcola, **quindi questo va
guardato in un browser vero**: `frontend/e2e/style.spec.ts` è il posto che tiene quel
terreno, e ci va un controllo sul campo data e sulla pastiglia.

## 8. Cosa non fa

Elencato perché ognuna di queste è una cosa che sembra ovvia da aggiungere, e ognuna
riaprirebbe una decisione presa:

- **non entra in `status_for_fill`** e non cambia la disponibilità di nessun
  ingrediente: nessuna ricetta diventa non cucinabile per una data;
- **non chiede «Lo rimetto in lista?»** quando scade. Quella domanda nasce da un gesto
  dell'utente sul cursore; una scadenza arriva da sola, e una domanda che si presenta
  da sé al risveglio è una notifica travestita;
- **non riordina la dispensa** per scadenza più vicina;
- **non manda notifiche**, che sarebbero l'unica forma di manutenzione giornaliera che
  D5 non ha accettato;
- **non arriva da Open Food Facts**, che descrive il prodotto e non la confezione che
  hai comprato: è sempre scrittura umana, il che rende il campo facoltativo non una
  cortesia ma l'unica forma possibile.

## 9. Le prove, e in che ordine

1. **Il dominio per primo, per tabella**: `expiry_state` su nessuna data, lontana,
   sette giorni esatti, oggi, ieri. È la funzione su cui poggia tutto il resto e non
   tocca niente.
2. **La rotta PATCH**, e prima di tutto il caso `{"expires_on": null}`: deve cancellare
   la data e non rispondere «niente da modificare». Poi la scrittura, e che
   `status_changed_at` non si muova.
3. **L'ingresso dalla spesa**: una entry con la data e una senza, nella stessa
   richiesta, e la transazione unica che regge.
4. **Le schermate** con Vitest: la pastiglia che compare e sparisce, il «+ scadenza»,
   la correzione, e il vuoto che non mostra niente di più.
5. **Il browser vero** per lo stile, in `style.spec.ts`.

Due avvertenze che questo progetto ha già pagato:

- `PantryItem` in `domain/types.ts` prende due campi nuovi, quindi **ogni oggetto
  `PantryItem` costruito a mano nei test** smette di compilare. È un bene: è il modo
  in cui si scopre che un fixture è rimasto indietro. Il controllo che lo vede è
  `npm run typecheck` (`tsc -b`) — **non** `tsc --noEmit`, che su questo progetto esce
  0 sempre perché il `tsconfig.json` è solution-style e non trova file da compilare.
- Nessuna chiamata di rete nella suite, come sempre.

## 10. Gli emendamenti, che vanno fatti insieme

Quando il lavoro è in piedi, e **nello stesso commit**:

- **`CLAUDE.md`**, decisione fondante 1: smette di dire «né date di scadenza» e dice
  cosa la dispensa conosce e perché quel dato non contraddice la regola — si scrive una
  volta sola, non si mantiene, e non entra in nessun giudizio di disponibilità.
- **`docs/superpowers/specs/2026-09-11-spena-design.md` §2**, la stessa cosa, perché è
  il documento d'origine e due copie che divergono sono peggio di una sola sbagliata.
- **`docs/prossimi-passi.md`**: S7 da `[D]` a fatto, con quel che si è misurato.

## 11. Cosa può andare storto

- **Il fuso.** Se `today` finisce per essere letto in UTC da qualche parte, il difetto
  è invisibile per ventidue ore al giorno. Il test lo prende solo se qualcuno pensa a
  scriverlo con un `today` esplicito — ed è perché la funzione pura lo prende come
  argomento.
- **Il ramo `model_fields_set`.** Scritto con `is not None` sembra funzionare e non
  cancella mai niente. Il test del `null` è la difesa, e va scritto rosso per primo.
- **Il colore che non si distingue.** Nessun test lo vede: è un giudizio, e si dà in
  un browser vero a 375px, come la volta che ha prodotto la quarta lezione di
  `CLAUDE.md`.
