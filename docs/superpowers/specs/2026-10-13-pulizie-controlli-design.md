# Pulizie: i controlli spenti e il fuoco — design

_2026-10-13, fase giorno. Raccoglie dodici voci `[idea]` di `next-steps.md` («### Idee») sui
controlli spenti e sul fuoco che cade sulla pagina. Mattia ha chiesto il 2026-10-13 di farne
un piano, con le scelte estetiche e tecniche delegate a Claude. Piano:
`docs/superpowers/plans/2026-10-13-pulizie-controlli.md`, ramo `night/pulizie-controlli` da
`night/r8-modifica-con-ai` (la fine della catena della notte, piano 13)._

## 1. Contesto

Il tema scuro (piano 3, `night/tema-scuro-spenti`) ha tolto l'`opacity` dallo spento di
`Button`: un pulsante spento — con `disabled`, `busy` o `unavailableReason` — è un grigio pieno
(`bg-disabled text-on-disabled`) se ha un fondo, `text-ink-faint` se non ce l'ha. I controlli
**fuori** da `Button` sono rimasti com'erano, e la bozza del tema scuro li ha messi fuori scope
(«voce a parte»): si spengono ancora con l'`opacity`, che compone colore e fondo e in chiaro
porta il testo a ~1,8:1. Sono, su `master`:

| Controllo | File | Come si spegne oggi |
|---|---|---|
| la casella di casa | `components/ui/Checkbox.tsx` | `aria-disabled:opacity-40` |
| la casella della Lista (20 px, non `Checkbox`) | `features/shopping-list/ListRow.tsx` | `aria-disabled:opacity-40` |
| le tacche | `components/ui/StockGauge.tsx` | `aria-disabled:opacity-40` sul pulsante |
| la scadenza della riga (la voce dice «il nome»: è il pulsante «+ scadenza» / «scade …») | `features/pantry/PantryRow.tsx` | `aria-disabled:opacity-40` |
| i € del costo | `components/ui/CostPicker.tsx` | `disabled:opacity-60` (nessun chiamante passa `disabled`) |
| il campo del selettore | `components/IngredientPicker.tsx` | `disabled` nativo, `disabled:opacity-50` |
| i suggerimenti | `components/ui/OptionList.tsx` | `disabled` nativo, `disabled:opacity-50` |

Accanto a loro, altri `disabled` nativi che tolgono il fuoco (il browser toglie il fuoco a un
controllo che diventa `disabled`, e chi usa la tastiera lo ritrova sul `body`), e due punti in
cui il fuoco cade sulla pagina perché il controllo che l'aveva sparisce.

## 2. Le voci, verificate su `master` (b9be6bf) e sui piani 1–12

| # | Voce di `next-steps.md` (inizio del testo) | Stato | Dove va |
|---|---|---|---|
| 1 | «Altri controlli spenti fuori da `Button` usano ancora `opacity`…» | c'è; nessun piano lo tocca (il tema scuro lo mette fuori scope) | §3.1 |
| 2 | «La casella della Lista (`ListRow.tsx`) è ancora un quadratino da 20 px…» | c'è | §3.2 |
| 3 | «Lo stepper delle porzioni spegne il «−» con `disabled`…» | c'è; R2 (piano 8, da `master`) riscrive lo stepper **tenendo** il `disabled` e rimanda a questa voce | §3.3 |
| 4 | «`IngredientPicker` spegne campo e suggerimenti con `disabled`…» | c'è; i suggerimenti (piano 4) e S3 non lo toccano (lo dicono) | §3.1 |
| 5 | «`InlineField.tsx` (nome, marca e codice del prodotto) ha ancora `<button disabled>`…» | c'è | §3.4 |
| 6 | «`CustomProductForm.tsx` («Salva prodotto») spegne ancora con `disabled`…» | c'è; S3 non tocca il file | §3.4 |
| 7 | «`Button` con `disabled` e `unavailableReason` insieme non è definito…» | c'è | §3.5 |
| 8 | «In `MergePanel.tsx` «Cambia» è un `Button` dentro un `<p class="flex">`…» | c'è | §3.4 |
| 9 | «In `RecipeForm.tsx` restano due `<button>` scritti a mano…» | c'è | §3.4 |
| 10 | ««Elimina» di sola icona non mostra niente mentre archivia…» | c'è | §3.5 |
| 11 | «Annullando una decisione nella coda la riga sparisce e il fuoco cade sulla pagina…» | c'è; il piano 9 (pagine scartate, da `master`) tocca la stessa schermata ma non questo | §3.6 |
| 12 | «Se il ricaricamento della dispensa dopo «Ho cucinato» fallisce…» | c'è; né il piano 7 né R8 lo toccano | §3.6 |

Trovato in più, e messo qui perché è la stessa voce della 2: la casella «Rimetti in lista della
spesa» del foglio della cottura (`features/cooking/CookSheet.tsx`) è anche lei un
`<input type="checkbox" className="size-5">` scritto a mano, da 20 px. Il piano 7 ne cambia
la condizione e non la casella.

Nessuna voce è già risolta da un altro piano. Nessuna voce si sposta in un altro pacchetto.

## 3. Comportamento esatto

### 3.1 Lo spento senza opacità, fuori da `Button`

La regola del tema scuro, portata ai controlli che non sono `Button` (deciso da Claude su
delega di Mattia): **chi ha un fondo pieno si spegne nel grigio, chi è solo testo scrive in
`ink-faint`; niente `opacity`**, e la forma del controllo non cambia.

- `Checkbox`: spenta (`aria-disabled`), la spunta prende il grigio `ink-faint`
  (`aria-disabled:accent-ink-faint`) invece del verde.
- `StockGauge`: spenta (una scrittura in volo), le tacche accese diventano grigie
  (`bg-on-disabled`); le spente restano `notch-off`. Il livello resta leggibile (2,13:1 in
  chiaro, 2,57:1 in scuro fra accesa e spenta), la forma resta tre tacche.
- `PantryRow`, il pulsante della scadenza spento: `aria-disabled:text-ink-faint` (anche sopra il
  viola di una scadenza vicina).
- `OptionList`: i suggerimenti si spengono con `aria-disabled` e non con `disabled` (il fuoco
  resta), il tocco si ignora dentro il componente, la scritta passa a `ink-faint`.
- `IngredientPicker`: mentre la scelta è in volo il campo è `readOnly` con `aria-disabled` (il
  fuoco resta, non si scrive) e la scritta passa a `ink-faint`; i suggerimenti come sopra.
  Il nome della prop resta `disabled` (la usano TermCard, AliasRow, ProductScreen e
  l'`IngredientChooser` di S3): cambia cosa fa, non come si chiama.
- `CostPicker`: la prop `disabled` non ha chiamanti; si toglie, con la sua classe.

Una prova strutturale (`frontend/src/disabledLook.test.ts`) tiene fuori dal codice ogni
`disabled:opacity-…` e `aria-disabled:opacity-…`; `theme.test.ts` controlla la tacca spenta
accesa contro la scheda (≥ 3:1, è un segno) e contro la tacca spenta (≥ 2:1, il livello).

### 3.2 Le caselle da 20 px diventano `Checkbox`

La casella della Lista e quella del foglio della cottura diventano `Checkbox` (il quadrato da
44 px, il quadratino da 24): stessi nomi accessibili, stesso comportamento. La label della
Lista perde il `py-1.5` e passa a `gap-1`, come le altre label con `Checkbox`.

### 3.3 Lo stepper delle porzioni non perde il fuoco

Il «−» a 1 porzione e il «+» a 50 restano spenti con `disabled` (sono fermi: non c'è un perché
da dire, la regola del `disabled` nativo). **Prima** che il tasto premuto si spenga, se il fuoco
era su di lui, passa all'altro tasto, che a quel punto è acceso. Niente frase in più sotto lo
stepper (la voce temeva proprio quella). Deciso da Claude su delega.

### 3.4 I pulsanti scritti a mano

- **`InlineField`** (nome, marca, codice del prodotto): il «Salva» diventa `Button`.
  - in volo → `busy` (il fuoco resta);
  - campo obbligatorio vuoto → `unavailableReason` «Il campo «<label>» non può restare
    vuoto.» (le parole di oggi), scritto da `Button` sotto il pulsante, a capo;
  - invariato → `disabled` nativo: è lo stato di ogni campo a riposo, e non c'è niente da
    spiegare (la regola);
  - **dopo un salvataggio riuscito il fuoco torna nel campo** appena salvato, se era sul
    «Salva»: prima che il pulsante si spenga perché invariato. Così il pulsante non si spegne
    mai col fuoco addosso.
  - Il campo, mentre salva, è `readOnly` e non `disabled`.
- **`CustomProductForm`**: «Salva prodotto» diventa `Button` `type="submit"` `primary`
  `block`, `busy` mentre crea, `unavailableReason` «Scrivi il nome del prodotto per
  salvarlo.» senza nome (le parole di oggi, ora dette da `Button`); «Annulla» diventa `Button`
  `ghost`.
- **`MergePanel`**: il contenitore di «Resta: «…»» e «Cambia» passa da `<p>` a `<div>`, con le
  stesse classi.
- **`RecipeForm`**: la ✕ di una riga diventa `Button` `ghost` di sola icona (`IconX`, nome
  «Togli <riga>»); i due ruoli diventano `Button` con `aria-pressed`, `primary` quello scelto e
  `secondary` l'altro, nella forma `pill` di sempre (testo `text-sm`). La riga della quantità
  va a capo (`flex-wrap`) se a 375 px non ci stanno.

### 3.5 `Button`

- **`busy` e `unavailableReason` vincono su `disabled`**: se un chiamante passa `disabled`
  insieme a uno dei due, il pulsante non prende il `disabled` nativo; resta `aria-disabled`,
  raggiungibile, e il perché si sente. Scritto anche nel JSDoc della prop.
- **Un pulsante di sola icona in volo mostra un segno d'attesa**: l'icona lascia il posto a
  `IconLoader2` che gira (`motion-safe:animate-spin`: chi ha chiesto meno movimento la vede
  ferma). Il nome accessibile non cambia. I pulsanti con testo non cambiano (i chiamanti
  cambiano già il testo: «Salvo…», «Unisco…»). Vale per «Elimina» del dettaglio e per ogni
  altro pulsante di sola icona in volo (le ✕ della Lista e della Dispensa, «Modifica con AI»
  di R8).

### 3.6 Il fuoco che cade sulla pagina

- **Coda d'import, «Annulla» su una decisione**: la riga sparisce e il termine torna in coda
  come scheda. Il fuoco va al **nome del termine** nella sua scheda (un `<p tabIndex={-1}>`),
  appena la scheda c'è e solo se il fuoco è caduto sulla pagina (chi nel frattempo ha toccato
  altro se lo tiene). Vale anche per il termine messo a fuoco con `?termine=`. Se il termine
  non torna in coda (la coda non si rilegge), il fuoco resta dov'è caduto: non c'è un posto
  migliore da inventare.
- **Dettaglio della ricetta, dopo «Ho cucinato»**: il fuoco torna su «Cucina» come oggi; se la
  dispensa non si ricarica e al posto di «Cucina» compare l'avviso con «Riprova», il fuoco va
  su «Riprova» — anche se l'errore arriva dopo che il fuoco era già tornato su «Cucina». Solo se
  il fuoco è caduto sulla pagina. «Riprova» diventa `Button`, `busy` mentre rilegge.

## 4. Parole a video

Nessuna parola nuova. Le frasi di `InlineField` e `CustomProductForm` restano identiche; cambia
solo chi le scrive (`Button`, in `text-xs text-ink-faint` invece di `text-ink-soft`).

## 5. Scelte estetiche e tecniche (decise da Claude su delega di Mattia)

1. La regola del §3.1 (grigio per i pieni, `ink-faint` per il testo) e i suoi token: nessun
   token nuovo, si usano `on-disabled`, `ink-faint`, `notch-off` del tema scuro.
2. La tacca spenta accesa è `on-disabled` e non `disabled`: con `disabled` le tacche spente
   (`notch-off`) e accese sarebbero a 1,4:1 fra loro, e il livello non si leggerebbe.
3. `CostPicker` perde `disabled` invece di guadagnare uno spento che nessuno usa.
4. Il passaggio del fuoco nello stepper invece del motivo sotto.
5. `InlineField`: invariato resta `disabled` nativo, e il fuoco torna nel campo dopo il
   salvataggio.
6. Il segno d'attesa solo sui pulsanti di sola icona, `IconLoader2` di Tabler (già nel
   pacchetto installato, si esporta da `icons.ts`).
7. Il fuoco dopo l'annullamento va sul nome del termine e non sul primo pulsante della scheda:
   chi ascolta sente quale termine è tornato, e il Tab lo porta alle scelte.
8. I ruoli del modulo nella forma `pill` di `Button` (`text-sm`, `px-4`) e non più `text-xs`.

## 6. Fuori scope

- Il `disabled` nativo di altri campi in volo: `RenameForm` (il campo del nome), il
  `CategorySelect` di `CategoryForm`, il campo data di `PantryRow`. Stessa famiglia, non fra le
  voci: il piano li annota come idea.
- Lo stepper riscritto da R2 (piano 8, da `master`): al merge la revisione porta il passaggio
  del fuoco dentro la versione di R2 (vedi il piano, «Dipendenze»).
- Un aspetto proprio per `busy` sui pulsanti con testo.
- Il backend: nessuna modifica.
