# La pulizia delle dosi dell'import — design

_2026-10-13. Voce di `next-steps.md`: «Dosi dell'import con l'aggettivo davanti… più le unità
spurie in `units`» [Parte X]. Piano: `docs/superpowers/plans/2026-10-13-pulizia-dosi.md`._

## 1. Contesto

GialloZafferano scrive la dose di un ingrediente dentro uno `<span>` pieno di a capo e
tabulazioni, e l'import (`parse_ingredients` in `giallozafferano.py`) la conserva così com'è:
`"fredda\n\t\t\t330\n\t\t\tg"`. Il parser delle dosi (`parse_quantity`, D1) vuole il numero in
testa, quindi:

- **le parole davanti alla dose** («fredda», «da grattugiare», «(da pulire)») fanno perdere la
  dose: la riga non si riscala (Parte X, «Circa settanta dosi…», che oggi sono molte di più);
- **un numero nel nome** («36 mesi ⏎ 50 ⏎ g», un Parmigiano stagionato) diventa la dose:
  36 `mesi`, e al doppio delle porzioni la riga dice «72 mesi» (Parte X, «36 mesi»);
- quelle parole sono finite nel registro `units` come se fossero unità: `mesi`, `da`, `per`,
  `già`, `di`, `w`, `grande`, `intere`…;
- il parser non legge le frazioni scritte con un carattere solo («½ cucchiaino»), né una dose
  con accanto «+ q.b.» («10 g + q.b.»).

**Misure sulla produzione del 2026-10-13** (sola lettura, fatte da Claude col via di Mattia):
8.454 ricette, 83.343 righe in `recipe_ingredients`, `quantity_value` vuoto su 32.067 (circa
16.000 sono `q.b.`).

| Forma | Righe |
|---|---|
| a capo o tabulazioni nel testo (il più comune: `"100\n\t\t\tg"`, 2.947) | 61.137 |
| «parole ⏎ numero ⏎ unità» (`'^[^0-9\n]+\n\s*[0-9]'`), tutte senza valore | 9.767 |
| — «da grattugiare» 510, «a temperatura ambiente» 461, «(da pulire)» 447, «(da grattugiare)» 392, «medie» 360, «freddo» 230, «denocciolate» 165… | |
| «numero nel nome ⏎ dose» (`'^[0-9][^\n]*\n\s*[0-9]'`), es. «36 mesi ⏎ 50 ⏎ g» | 202 |
| frazioni ½ ¼ ¾ («½» 471, «½ ⏎ cucchiaino» 156, «½ + ½» 52, «1 + ½» 26…), senza valore | ~1.042 |
| «+ q.b.» («10 ⏎ g + q.b.» 93, «1 ⏎ pizzico + q.b.» 92…), molte senza valore | ~3.547 |
| «parole ⏎⏎ q.b.» («secco» 77, «da grattugiare» 54, «per friggere» 26…) | qualche centinaio |

`units` ha 101 righe, 5 non usate; fra le usate, parole che unità non sono: `mesi` 56, `da` 4,
`per` 2, `intere` 2, `già`, `di`, `w`, `grande`, `lunghi`, `sodi` 1… La colonna
`recipe_ingredients.note` (varchar 300) è **vuota su tutte le righe**: l'import non l'ha mai
usata, e nessuna schermata la mostra (il dettaglio no; il foglio della cottura mostra la nota
della *confezione*, non della riga; il modulo la porta con sé senza mostrarla).

## 2. Decisioni di Mattia (2026-10-13)

1. **Le parole davanti alla dose vanno nella nota della riga** (`note`); `quantity_text` diventa
   la dose pulita («50 g») e si riscala. Lo stesso per «parole ⏎⏎ q.b.» (nota + «q.b.») e per il
   numero nel nome («36 mesi ⏎ 50 g» → nota «36 mesi», dose «50 g»).
2. **Entrano nella pulizia anche:** le frazioni ½ ¼ ¾, che il parser impara a leggere
   («½ cucchiaino» = 0,5 cucchiaini; «1 + ½» = 1,5); «50 g + q.b.», dove i 50 g si riscalano e
   «+ q.b.» resta scritto accanto; le unità spurie, tolte dal registro `units` dopo la rilettura
   se nessuna riga le usa più.
3. **La pulizia tocca anche le ricette adottate** (modificate da Mattia, R10), ma solo nelle righe
   che hanno ancora la forma dell'import: una riga scritta a mano senza quella forma non cambia.
4. **Gli spazi bianchi dell'import** (a capo, tabulazioni) diventano uno spazio nel testo pulito.

Da costruire: la funzione pura di pulizia, test-first e tabellare sui casi misurati; l'import che
pulisce all'ingresso; un comando idempotente con `--dry-run` che pulisce le righe esistenti,
rilegge le dosi e toglie le unità spurie. Il lancio in produzione lo fa Mattia.

## 3. Decisioni di Claude, su delega (tecniche o estetiche)

5. **«La forma dell'import» è un testo con almeno un a capo o una tabulazione.** È quel che
   distingue senza ambiguità una dose arrivata da GialloZafferano da una scritta a mano (il campo
   del modulo è una riga sola). Una dose senza a capo né tabulazioni non si tocca mai, da
   nessuna strada: è la decisione 3 resa misurabile.
6. **Come si separa la nota dalla dose.** Il testo si divide sugli a capo in righe (vuote
   escluse, spazi interni ridotti a uno). La dose comincia dall'**ultima** riga che comincia con
   una cifra, con ½ ¼ ¾, o con «q.b.»; quel che sta prima è la nota. Se quel che sta prima non ha
   nemmeno una lettera («2 ⏎ 1/2 ⏎ cucchiai») è tutto dose: non si inventa una nota fatta di
   numeri. Una nota chiusa per intero fra parentesi perde le parentesi («(da pulire)» → «da
   pulire»). Le dosi unite con « + » (`merge_quantities`) si puliscono pezzo per pezzo, e le note
   dei pezzi si uniscono.
7. **Più note sulla stessa riga** (due righe dell'import collassate sullo stesso ingrediente, una
   nota già scritta a mano più quella nuova) si uniscono con «; », senza ripetere la stessa nota,
   tagliate ai 300 caratteri della colonna (`merge_notes`). Una nota già scritta resta davanti.
8. **«½ + ½» vale 1.** Viene da due righe dello stesso ingrediente unite (½ limone per la frolla,
   ½ per la crema): la somma è la verità, come «500 g + 50 g». **«1 ½» e «1½» valgono 1,5.**
   «2 1/2», scritto con la barra, resta non letto come oggi.
9. **«50 g + q.b.» riscalato si legge «100 g + q.b.»**: il numero si riscala e i pezzi «q.b.»
   del testo tornano scritti accanto, com'erano (`with_qb_tail`). A 1× si mostra
   `quantity_text`, come sempre. Un testo fatto solo di «q.b.» resta non letto.
10. **L'import pulisce dove il `payload` diventa ricetta** (`materialize_ready`), non dove la
    pagina si scarica: il `payload` in `recipe_imports` resta la copia di quel che è arrivato, e
    ogni ricetta rifatta da lì (annulla, unione nell'anagrafica, rimessa in coda) nasce pulita
    come le nuove. Il **ruolo** si deduce dal testo come è arrivato, come prima: la pulizia non
    cambia ruoli né all'import né sulle righe esistenti («da grattugiare ⏎⏎ q.b.» resta
    principale se lo era).
11. **Il comando è `python -m app.cli.clean_doses`**: legge tutte le righe (archiviate comprese:
    una ricetta archiviata si può ripristinare), pulisce quelle nella forma dell'import, rilegge
    **tutte** le dosi con il parser nuovo (la stessa lettura di `reparse_quantities`:
    `parse_quantity` più `ensure_unit`, in una passata sola e a tuple, perché 83.000 oggetti ORM
    con due join non servono), e toglie le unità rimaste orfane. `--dry-run` fa esattamente lo
    stesso lavoro e alla fine annulla la transazione: i numeri che stampa sono quelli della
    scrittura vera, e un errore della scrittura vera esce già nella prova. Senza `--dry-run`, una
    transazione sola. Rilanciato, non cambia niente.
12. **Quali unità si tolgono:** quelle che prima della pulizia avevano righe e dopo non ne hanno
    più — le parole che la pulizia ha spostato nella nota. Una di loro resta se è il canonico
    (`canonical_id`, FK `RESTRICT`) di un'unità che resta; fra quelle tolte, i puntatori si
    azzerano prima della cancellazione. Le unità **già senza righe prima** (5 in produzione) non
    si toccano: il comando le elenca, e Mattia decide al dry-run in produzione se toglierle
    (deciso da Mattia il 2026-10-13, §7).
13. **La nota nel dettaglio della ricetta:** sotto il nome dell'ingrediente, piccola
    (`text-xs text-ink-soft`), così com'è scritta. Dice com'è l'ingrediente («da grattugiare»,
    «36 mesi»); la dose resta a destra, dov'è.

## 4. Comportamento esatto

### 4.1 La pulizia di una dose (`clean_dose`, funzione pura)

| Testo | Dose pulita | Nota | Forma |
|---|---|---|---|
| `None`, «300 g», «freddo 50 g», «q.b.» | invariato | — | `unchanged` |
| `"100\n\t\t\tg"` | «100 g» | — | `spaces` |
| `"fredda\n\t\t\t330\n\t\t\tg"` | «330 g» | «fredda» | `words_before` |
| `"(da pulire)\n\t\t\t2\n\t\t\tcespi"` | «2 cespi» | «da pulire» | `words_before` |
| `"(circa 2 medie)\n\t\t\t110\n\t\t\tg"` | «110 g» | «circa 2 medie» | `words_before` |
| `"36 mesi\n\t\t\t50\n\t\t\tg"` | «50 g» | «36 mesi» | `number_in_name` |
| `"secco\n\n\t\t\tq.b."` | «q.b.» | «secco» | `note_qb` |
| `"½\n\t\t\tcucchiaino"` | «½ cucchiaino» | — | `spaces` |
| `"10\n\t\t\tg + q.b."` | «10 g + q.b.» | — | `spaces` |
| `"freddo\n\t\t\t100\n\t\t\tg + freddo\n\t\t\t50\n\t\t\tg"` | «100 g + 50 g» | «freddo» | `words_before` |
| `"2\n\t\t\t1/2\n\t\t\tcucchiai"` | «2 1/2 cucchiai» | — | `spaces` |

### 4.2 La lettura (`parse_quantity`)

| Testo | Valore, unità |
|---|---|
| «½», «½ cucchiaino», «¾ tazza» | 0,5; 0,5 `cucchiaino`; 0,75 `tazza` |
| «1 ½ cucchiai», «1½», «1 + ½», «½ + ½» | 1,5 `cucchiai`; 1,5; 1,5; 1 |
| «50 g + q.b.», «1 pizzico + q.b.» | 50 `g`; 1 `pizzico` |
| «q.b.», «q.b. + q.b.», «abbondante + q.b.» | non letto |

Il resto è come oggi (D1, spec `2026-09-20-quantita-ricette-design.md` §4.1).

### 4.3 Il comando

```
python -m app.cli.clean_doses --dry-run   # fa tutto, stampa, annulla
python -m app.cli.clean_doses             # fa tutto e salva
```

Stampa le righe lette e quelle ripulite per forma, le dosi lette prima e dopo e quante hanno
cambiato valore, le unità nuove, tolte, tenute perché canoniche, già senza righe, e un campione
di cinque righe per forma (`prima → dopo`, con la nota). Senza `--dry-run`, se ci sono unità nuove
ricorda `python -m app.cli.decide_units`.

### 4.4 A video

Nel dettaglio della ricetta, sotto il nome di una riga con la nota: la nota, piccola. La dose
pulita si riscala con lo stepper come le altre; «+ q.b.» resta accanto alla dose riscalata.
Nessuna parola nuova a video oltre alle note stesse.

## 5. Fuori scope

- Mostrare o modificare la nota nel modulo di modifica (oggi la porta con sé senza mostrarla):
  sarà un campo modificabile, in una voce a sé, il piano 20 `modulo-nota-nome` (deciso da
  Mattia il 2026-10-13, §7).
- Le dosi scritte a mano senza la forma dell'import, anche se hanno un aggettivo davanti
  («freddo 50 g»): non si toccano (decisione 3).
- Il `payload` delle pagine dell'import, gli `snapshot` delle cotture passate: restano come sono.
- Le frazioni oltre ½ ¼ ¾ (⅓, ⅛…), «2 1/2» con la barra: restano non lette.
- Il genere e le forme delle unità nuove: le decide `decide_units`, come sempre.
- Il ruolo delle righe (decisione 10).

## 6. Dopo il deploy (solo Mattia)

Dry-run, backup del database come nel runbook `docs/import-gz-runbook.md` §3, scrittura, e
`decide_units` se il comando ha depositato unità nuove. I comandi esatti e i numeri attesi sono
nel piano, sezione «Dopo il deploy (solo Mattia)».

## 7. Decise da Mattia il 2026-10-13

- **Le unità già senza righe prima della pulizia** (5 in produzione): il comando le elenca e
  non le toglie; quali siano lo dice il dry-run in produzione, e lì Mattia decide se toglierle.
- **La nota nel modulo di modifica**: oggi invisibile e conservata; con ~10.000 note nuove, chi
  modifica una ricetta deve poterne correggere una. Diventa un campo modificabile, in una voce a
  sé: il piano 20 (`modulo-nota-nome`). Questo piano non cambia il modulo e non aggiunge voci
  al backlog per questo.
