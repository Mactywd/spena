# R2, secondo modo: riporzionare da un ingrediente — design

_2026-10-09. Voce `[R2]` di `docs/prossimi-passi.md` («## R2. Riporziona»), la metà che manca.
Piano: `docs/superpowers/plans/2026-10-09-r2-riporziona-ingrediente.md`._

## 1. Contesto

Il riporziona ha due modi. Il primo, **per porzioni**, è in produzione dal 2026-09-20 (dentro
D1, spec `2026-09-20-quantita-ricette-design.md` §5): `GET /api/v1/recipes/{id}?servings=N`
(intero 1–50) riscala le righe che hanno una dose strutturata (`quantity_value`,
`quantity_unit_id`) con `scale_quantity` e le riscrive con `render_quantity`
(`backend/app/domain/quantities.py`); `_to_out` in `backend/app/api/recipes.py` lo fa riga per
riga, e conta quante dosi non si riscalano (`unscalable_lines` su `dose_lines`). A video c'è
`ServingsStepper` (`frontend/src/features/cooking/ServingsStepper.tsx`); su una ricetta senza
porzioni lo stepper resta, spento, col perché («Porzioni non indicate: si cambiano da
«Modifica».»). La cottura (`cook` in `backend/app/services/cooking.py`) registra in
`cooking_events` le porzioni per cui si è scalato (`servings`, intero o null) e uno `snapshot`
JSONB.

Il secondo modo è quello che manca a tutte le app: **riscalare dalla dose assoluta di un
ingrediente** — «la ricetta è per 400 g di pasta, io ne faccio 150 g» — indipendentemente dalle
porzioni.

Vale la decisione fondante 1 di `CLAUDE.md`: le quantità stanno solo nelle ricette;
`quantity_text` è la verità a 1× e non si riscrive mai; una riga che il parser non ha capito non
si riscala, e lo si dichiara.

## 2. Le decisioni di Mattia (2026-10-09)

1. **Solo vista**, come lo stepper: niente si salva sulla ricetta, né come ricetta nuova. Uscire
   dalla ricetta se ne dimentica.
2. **Il gesto parte da un tocco sulla dose della riga.** Ogni dose riscalabile è toccabile e apre
   sotto la riga un campo per dire quanto se ne fa, con l'unità della riga. Le righe senza dose
   strutturata non lo offrono.
3. **Un modo alla volta.** Con un ingrediente fissato, lo stepper delle porzioni dice le porzioni
   equivalenti («≈ 1,5 porzioni»); toccare − o + torna al modo per porzioni intere.

## 3. Le decisioni di Claude (tecniche o estetiche, su delega di Mattia)

4. **Il contratto.** `GET /api/v1/recipes/{id}` accetta, accanto a `servings`, la coppia
   `anchor` (l'`ingredient_id` della riga, uuid) e `amount` (la dose scritta, decimale con il
   punto). Il calcolo è tutto nel backend, come per le porzioni: il frontend chiede e mostra.
   - `anchor` senza `amount`, o `amount` senza `anchor` → 422. `anchor` con `servings` → 422
     («un modo alla volta»). Il frontend non li manda mai: sono contratti, non frasi a video.
   - `amount`: più di zero, sotto 10 000 000, al massimo tre decimali (come `Numeric(8, 3)` della
     colonna); fuori → 422 di validazione.
   - Il fattore è `amount / quantity_value` della riga d'ancora. La riga d'ancora mostra
     **esattamente** la dose scritta (`render_quantity(amount)`), non il suo ricalcolo.
   - Un'ancora che la ricetta non ha (più) — l'ingrediente non è nella ricetta, o la sua riga
     non ha una dose strutturata maggiore di zero — **si ignora**: la risposta è quella senza
     parametri, con `anchor: null`. È lo stesso trattamento di `servings` su una ricetta senza
     porzioni, ed è la strada che non diventa un vicolo cieco quando la ricetta è stata
     modificata in un'altra scheda.
   - Un fattore 1 (la dose della ricetta) è come non chiedere niente: le righe mostrano
     `quantity_text`, la copertura non compare; l'ancora resta nella risposta.
   - La risposta guadagna, per riga, `anchorable` (la riga ha `quantity_value > 0`) e
     `anchor_unit` (la parola dell'unità da scrivere accanto al campo: il plurale deciso, se no
     la chiave com'è arrivata; `null` per un numero nudo come «1» cipolla); e per la ricetta
     `anchor: {ingredient_id, amount, equivalent_servings} | null`. `scaled_to` resta del modo
     per porzioni e in questo modo è `null`; `unscalable_lines` e `dose_lines` valgono come
     nel primo modo.
5. **Il limite: 50 volte in su o in giù.** Una dose che porta la ricetta oltre 50 volte la sua (o
   sotto un cinquantesimo) → 422 con una frase che dice dove stare, con l'unità della riga:
   **«Così la ricetta cambierebbe più di 50 volte: scrivi un numero fra 6 g e 15000 g.»**
   Cinquanta è quanto lo stepper permette già al massimo (da 1 a 50 porzioni, su ricette che ne
   dicono da 1 a 50): una regola sola per i due modi. Oltre, è quasi sempre uno zero di troppo, e
   le dosi delle altre righe diventerebbero numeri che non si pesano. Gli estremi si confrontano
   già arrotondati come si mostrano, così la frase non promette un numero che poi si rifiuta.
6. **Le porzioni equivalenti** sono `servings × fattore`, arrotondate a metà in su: a un decimale
   da una porzione in su («≈ 1,5»), a due sotto («≈ 0,75»). Le calcola il backend
   (`equivalent_servings`); il frontend le scrive con la virgola. Senza porzioni nella ricetta
   sono `null`.
7. **Lo stepper con un ingrediente fissato** mostra «≈ 1,5» al posto del numero. − va all'intero
   più grande **sotto** le porzioni equivalenti (da ≈ 1,5 a 1; da ≈ 2 a 1), + all'intero più
   piccolo **sopra** (da ≈ 1,5 a 2; da ≈ 2 a 3), dentro 1–50: − si spegne sotto una porzione,
   + sopra 50 (e − da ≈ 200 va a 50). Il passo è quello dello stepper di oggi, solo partendo da
   un numero non intero.
8. **Ricette senza porzioni.** Il fattore vale lo stesso: le dosi seguono l'ancora. Lo stepper
   resta com'è oggi su queste ricette — «—», spento, col suo perché — perché non c'è una base da
   cui contare porzioni.
9. **Come si torna indietro.** Con un ingrediente fissato, sotto lo stepper una riga dice
   **«Riscalata da pasta: 150 g.»** (il nome com'è, in minuscolo dentro la frase) con accanto un
   pulsante leggero **«Torna alle dosi della ricetta»**, che toglie l'ancora. Serve soprattutto
   alle ricette senza porzioni, dove − e + sono spenti e altrimenti l'unica uscita sarebbe
   lasciare la ricetta; c'è anche nelle altre, per una regola sola.
10. **Il campo.** Il tocco sulla dose la apre (e un altro tocco la chiude); un campo aperto alla
    volta. Sotto la riga: «Quanto ne fai?», la casella (`inputMode="decimal"`, il fuoco ci va
    da sé), l'unità della riga subito dopo, **«Riscala»** (secondario, `submit`) e
    **«Annulla»** (leggero). Si accetta la virgola o il punto, fino a sette cifre intere e tre
    decimali. «Riscala» non ancora pronto (`unavailableReason`) dice perché:
    «Scrivi quanto ne fai.» a campo vuoto, «Scrivi un numero, come 150 o 1,5.» per tutto ciò
    che non è un numero così, «Scrivi un numero più grande di zero.» per lo zero.
    Si riscala al tocco di «Riscala» (o all'Invio), non a ogni cifra: ogni cifra sarebbe una
    rilettura della ricetta e un salto delle dosi mentre si scrive.
    Prima di cambiare la vista, il frontend chiede la ricetta riscalata; se il server rifiuta
    (il 422 del limite) la frase del server compare sotto il campo, e la ricetta resta com'era;
    se non risponde, «Non sono riuscito a riscalare. Riprova.». Riuscito, il campo si chiude e
    il fuoco torna sulla dose, che adesso dice la dose scritta, in grassetto.
    Il campo di una riga già fissata parte dalla sua dose.
11. **La dose toccabile** è un pulsante leggero (`Button variant="ghost"`) col testo della dose,
    sottolineato a puntini (il segno che si tocca), alto 44 px senza alzare la riga. Il suo nome
    per chi ascolta comincia col testo in vista: **«180 g: riscala da pasta»**. Le dosi che non
    si riscalano («q.b.») restano testo.
12. **Cosa registra la cottura.** In questo modo il foglio della cottura manda `anchor` e
    `amount` al posto di `servings`; `POST /recipes/{id}/cook` accetta la coppia con le stesse
    regole del dettaglio (insieme o niente, mai con `servings`). `cooking_events.servings` resta
    **null**, e lo `snapshot` guadagna una chiave `anchor`:
    `{"ingredient_id", "amount", "unit", "factor", "equivalent_servings"}` (stringhe decimali col
    punto, o null). **Nessuna migrazione.** *Perché:* `servings` è un intero che dice quante
    porzioni sono uscite dalla pentola, ed è un fatto solo quando lo si è scelto; «1,5» non è un
    numero di porzioni che qualcuno ha deciso, è un derivato, e scriverlo arrotondato (2) sarebbe
    falso per sempre — è il motivo per cui la cottura per porzioni registra `scaled_to`
    (commento in `CookSheet.tsx`). Il fatto vero di questa cottura è la dose dell'ancora: va nello
    `snapshot`, che è già lo storico di dettaglio di ogni cottura e non ha consumatori; la fase 3
    ci troverà ancora, dose, unità e fattore, e le porzioni equivalenti se la ricetta le diceva.
    Cambiare il tipo della colonna per un dato che nessuno legge sarebbe una migrazione senza
    consumatore. Il fattore si ricalcola nel backend con la stessa funzione del dettaglio
    (`resolve_anchor`): un'ancora che al momento della cottura non vale più (riga tolta, fuori
    scala) non blocca la cottura — si cucina lo stesso, e lo `snapshot` la registra con
    `factor: null`.
13. **«Metti in lista ciò che manca»** non cambia: la lista non ha quantità (decisione 1), e
    quel che manca lo decide `satisfied`, che non dipende dalla scala. **Il foglio della
    cottura** non cambia a video: le confezioni non hanno quantità; cambia solo cosa registra.
14. **Il 422 non si ritenta.** Il predicato dei tentativi delle query
    (`frontend/src/lib/queryRetry.ts`) aggiunge 422 a 401 e 404: una domanda sbagliata, rifatta
    uguale, resta sbagliata, e il «Riprova» arriverebbe dopo tre secondi. Se una vista riscalata
    già accettata smette di valere (la ricetta è stata modificata altrove e la rilettura torna
    422), il dettaglio dice «Non riesco più a riscalare da quella dose: la ricetta è cambiata.»
    con «Torna alle dosi della ricetta».

## 4. Le parole a video

| Dove | Testo |
|---|---|
| nome della dose toccabile | «{dose}: riscala da {nome}» (es. «180 g: riscala da pasta») |
| etichetta del campo | «Quanto ne fai?» (sotto) |
| accanto alla casella | l'unità della riga («g», «cucchiai»), niente per un numero nudo |
| pulsanti del campo | «Riscala», «Annulla» |
| «Riscala» non pronto | «Scrivi quanto ne fai.» · «Scrivi un numero, come 150 o 1,5.» · «Scrivi un numero più grande di zero.» |
| oltre il limite (dal server) | «Così la ricetta cambierebbe più di 50 volte: scrivi un numero fra {minimo} e {massimo}.» |
| server che non risponde | «Non sono riuscito a riscalare. Riprova.» |
| stepper con un ingrediente fissato | «≈ 1,5» |
| sotto lo stepper | «Riscalata da {nome}: {dose}.» e «Torna alle dosi della ricetta» |
| vista che non vale più | «Non riesco più a riscalare da quella dose: la ricetta è cambiata.» e «Torna alle dosi della ricetta» |

**L'etichetta, decisa da Mattia il 2026-10-13: «Quanto ne fai?».** Mattia aveva scritto «Quanti g ne fai?». Con l'unità dentro la
domanda l'accordo dipende dall'unità, e il registro delle unità non sa il genere: nel seme ci sono
«fette», «scatole», «coste», «tazzine», «bustina», «medie» («Quanti fette ne fai?»), e i numeri
nudi («1» cipolla) non hanno unità. Si scrive **«Quanto ne fai?»** con l'unità accanto alla
casella («Quanto ne fai? [150] g»), che è giusta per ogni riga. Le alternative scartate: la domanda
letterale «Quanti {unità} ne fai?», sbagliata con le unità femminili; oppure il genere nel
registro delle unità (una colonna, una migrazione, l'AI che lo decide), fuori da questa voce.

## 5. Fuori scope

- Salvare una riporzionatura, sulla ricetta o come ricetta nuova (decisione 1).
- Riscalare da una riga senza dose strutturata, o correggere da qui una dose che il parser non ha
  capito: si corregge da «Modifica».
- Le conversioni fra unità («ne faccio 1 kg» su una riga in grammi): la dose si scrive nell'unità
  della riga. I grammi della coppia ingrediente × unità sono di S4.
- Ricordare la vista uscendo dalla ricetta, o fra le schede.
- Il genere delle unità nel registro (vedi §4).
- Il «−» dello stepper spento con `disabled` a 1 porzione: è già un'idea a sé in `next-steps.md`,
  e questa voce non la cambia.
