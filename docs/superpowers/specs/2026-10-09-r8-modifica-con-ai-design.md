# R8 — Modifica con AI: una ricetta nuova che nasce da una aperta

_Spec del 2026-10-09 (fase giorno), aggiornata il 2026-10-13 con la decisione di Mattia
sulla foto e i tempi. Voce [R8] di `docs/prossimi-passi.md`. Piano:
`docs/superpowers/plans/2026-10-09-r8-modifica-con-ai.md`._

## 1. Contesto

Oggi l'AI scrive una ricetta solo da zero («Scrivi una ricetta», `AiDraftScreen`, R6/R10).
Chi ha davanti una ricetta che gli va quasi bene — la torta di mele, ma senza zucchero — deve
o correggerla a mano, cambiando l'originale, o riscriverla da capo. R8 chiede la terza strada:
dentro la ricetta aperta, un prompt libero («sostituisci lo zucchero con dolcificante»), e
l'AI riscrive la ricetta **intera**, ribilanciando il resto (le dosi, i liquidi, la cottura).
**Il salvataggio crea una ricetta nuova e non tocca l'originale.**

Tutti i pezzi ci sono già, tranne il legame: il modulo della ricetta (`RecipeForm`, R10/R12)
con la bozza dell'AI (`applyDraft`), il client unico dell'LLM (`services/llm.py`, modello
`google/gemma-4-26b-a4b-it` via OpenRouter) con la spesa in `llm_calls`, la creazione di una
ricetta (`POST /recipes`, che fa passare ogni riga dall'imbuto `write_recipe_ingredients`).

## 2. Decisioni prese

**Da Mattia, il 2026-10-09** (non si rimettono in discussione):

1. **La nuova ricetta tiene un legame con l'originale, e si vede.** Nella nuova, sotto il
   titolo, «Variante di «<titolo>»», che porta all'originale. **Nell'originale niente in
   più.** Se l'originale è eliminata (archiviata) lo si mostra seguendo R10: un'eliminata si
   apre dalla lapide.
2. **Dopo il prompt, la proposta dell'AI apre il modulo della ricetta già compilato**, come la
   bozza AI di oggi: si corregge, e «Salva» crea la ricetta nuova col legame. **Se l'AI non
   risponde, si resta sull'originale con un avviso**: mai un vicolo cieco, e il guasto dell'AI
   è «ambra» (`Alert tone="degraded"`), come nel resto dell'app.

**Da Mattia, il 2026-10-13** (era il «da confermare» di questa spec): **«Sì, copiali».** La
variante parte con la foto e i tempi dell'originale (`image_url`, `prep_minutes`,
`cook_minutes`). Dove avviene la copia e come si corregge sono nel §3.2 e nel §3.4.

**Vincoli dati con le decisioni:** il legame è una colonna, `recipes.derived_from_id`, FK
annullabile verso `recipes`, migrazione `0014` con `down_revision = "0013"` (la `0013` è di
S12). Le righe passano dall'imbuto `write_recipe_ingredients` (niente non alimentari: l'AI non
deve poterli introdurre, e l'imbuto li rifiuta comunque). Una ricetta nata così è dell'utente:
non è importata, non ha pagina d'import. La chiamata all'AI si registra in `llm_calls` con una
sezione `LlmCallSite` nuova. I test usano i finti registrati (`llm_fakes.py`), senza rete.

**Scelte delegate, decise da Claude** (dove sta il tasto, le parole, il prompt di sistema, e
le scelte tecniche interne): sono nel §3 e nel §4, segnate «(Claude)».

## 3. Comportamento

### 3.1 Il tasto e il pannello, nel dettaglio dell'originale

- Nel dettaglio di una ricetta **non eliminata**, il gruppo di icone accanto al titolo («Azioni
  della ricetta», T3 Consegna 5) ha un terzo pulsante di sola icona, **«Modifica con AI»**
  (`IconSparkles`, `ghost`), fra «Modifica» ed «Elimina». *(Claude: le due azioni rare di oggi
  stanno lì; è una modifica, e la scintilla è già l'icona di «scrivi con l'AI», spec T3 §3.3.)*
- Toccarlo apre, subito sotto il titolo, un **pannello** (una `Card`) e porta il fuoco nel suo
  campo; toccarlo di nuovo lo chiude. Il pulsante dice `aria-expanded` e `aria-controls`.
- Il pannello: l'etichetta **«Cosa vuoi cambiare?»**, un campo di testo libero (fino a 1000
  caratteri, segnaposto «Sostituisci lo zucchero con il dolcificante»), la riga **«L'AI scrive
  una ricetta nuova, che correggi prima di salvare. Questa resta com'è.»**, il pulsante
  **«Proponi la variante»** (secondario, `IconSparkles`, a tutta larghezza) e **«Annulla»**.
  - Con meno di tre lettere, «Proponi la variante» non parte e dice sotto di sé **«Scrivi cosa
    cambiare: bastano tre lettere.»** (`unavailableReason`); in volo dice «Propongo…» (`busy`).
  - «Annulla» chiude il pannello e riporta il fuoco su «Modifica con AI». Una proposta già in
    volo, arrivata dopo «Annulla», non apre niente.
- **L'AI non risponde** (qualunque errore della rotta): il pannello resta aperto, col testo
  scritto, e sotto compare in ambra **«L'AI non ha risposto: questa ricetta resta com'è.
  Riprova fra poco.»** Si è ancora sull'originale, che funziona com'era.
- Una ricetta **eliminata** (la lapide con «Ripristina», R10 §6.1) non ha il tasto, come non
  ha «Modifica»; il server rifiuta comunque la proposta con il 409 di R10.

### 3.2 Il modulo della variante

- Arrivata la proposta, si passa al modulo, su `/ricette/<id dell'originale>/variante`: titolo
  **«Nuova variante»**, sottotitolo **«Variante di «<titolo>»»**, il ritorno «‹ Ricetta» che
  porta all'originale, e sopra il modulo la riga **«Hai chiesto: «<richiesta>». Correggi quel
  che serve: salvando nasce una ricetta nuova, e l'originale resta com'è.»**
- Il modulo è `RecipeForm`, compilato come oggi da `applyDraft`: titolo, descrizione,
  procedimento, porzioni, costo e righe vengono dalla proposta (le righe agganciate,
  incerte da confermare, o «da creare salvando» come nella bozza AI); **la categoria parte da
  quella dell'originale** *(Claude: la proposta non ne ha, e una variante della torta resta un
  dolce; si cambia dal campo)*. Il pulsante è **«Salva la variante»**.
- «Salva la variante» crea la ricetta con `POST /recipes`: `source = "ai"`,
  `source_ref = "prompt: <richiesta>"` (accorciato a 500 caratteri, come la bozza AI), e
  `derived_from_id` = l'originale. Riuscito: «Salvata.» dall'avviso unico, e il dettaglio della
  ricetta nuova **al posto** del modulo (indietro si torna all'originale, non al modulo).
- La proposta passa dal pannello al modulo nella cronologia del browser (lo stato della
  navigazione), e regge un ricaricamento. *(Claude.)* Un indirizzo `/variante` aperto senza
  proposta (scritto a mano, un preferito) porta al dettaglio dell'originale: lì c'è il tasto.
- **La variante parte con la foto e i tempi dell'originale** (deciso da Mattia il
  2026-10-13: «Sì, copiali»). Nel modulo non si vedono: il modulo della ricetta non ha
  campi per la foto e per i tempi, né alla creazione né alla modifica (R10, spec del
  2026-09-27 §7: «Restano quelli dell'import, o vuoti»). Li copia quindi **il server**, al
  salvataggio di una ricetta con `derived_from_id` (§3.4). *(Deciso da Claude su delega di
  Mattia: aggiungere al modulo i campi della foto e dei tempi sarebbe una funzione nuova,
  che vale per ogni ricetta e non solo per la variante; e il client non deve né leggere né
  rimandare valori che solo il server conosce — il frontend non fa logica di dominio.)*
  Salvata, la variante mostra la foto dell'originale nel dettaglio e nel ricettario, e il
  suo tempo totale nella riga del ricettario, come ogni ricetta che li ha. **Come si
  correggono:** la modifica della ricetta (R10) li lascia com'erano, come fa per una ricetta
  importata; oggi nessuno schermo li cambia, per nessuna ricetta. Poterli correggere è una
  voce a sé (§5), annotata in `next-steps.md` come idea.

### 3.3 Il legame, a video

- Nel dettaglio di una variante, **subito sotto la riga del titolo**, il collegamento
  **«Variante di «<titolo dell'originale>»»** (testo `brand`, alto 44 px), che apre il
  dettaglio dell'originale. Il titolo è quello di oggi dell'originale, non quello del momento
  in cui la variante è nata.
- **Originale eliminata:** il collegamento dice **«Variante di «<titolo>» (eliminata)»** e
  porta lo stesso al dettaglio dell'originale, cioè alla sua lapide con «Ripristina» (R10). È
  la forma che l'Anagrafica usa già per le ricette eliminate («(eliminata)»). *(Claude.)*
- Nell'originale non compare niente: né l'elenco delle varianti, né un segno.
- Da una variante all'originale lo schermo riparte da capo: le porzioni scelte, il foglio
  della cottura o il pannello aperti sulla ricetta di prima non passano all'altra.
- Il ricettario, gli elenchi e i filtri non cambiano.

### 3.4 Il server

- **Colonna** `recipes.derived_from_id` (UUID annullabile, FK verso `recipes.id`, `ON DELETE
  SET NULL`), migrazione `0014`, nessun passo dati: ogni ricetta di oggi non è una variante.
  *(Claude: `SET NULL` e non `CASCADE` — cancellare l'originale non deve cancellare il lavoro
  di chi ha scritto la variante — né `RESTRICT`, che bloccherebbe l'annullamento di una
  decisione dell'import, l'unica strada che cancella davvero una ricetta.)*
- **`POST /api/v1/recipes/{id}/ai-variant`**, corpo `{"prompt": "…"}` (3–1000 caratteri, come
  la bozza), risposta della stessa forma di `POST /recipes/ai-draft` (`DraftOut`). Propone e
  non salva. 404 se la ricetta non c'è; 409 con la frase di R10 se è eliminata; 503 se l'AI non
  risponde o risponde in modo inutilizzabile.
- **`POST /api/v1/recipes`** accetta `derived_from_id` (facoltativo). Se l'originale nel
  frattempo non esiste più, la variante **si salva lo stesso, senza legame** *(Claude, dalla
  regola «mai un vicolo cieco»: un rifiuto butterebbe il lavoro, e dal modulo non c'è modo di
  togliere il legame)*. Un'originale eliminata tiene il legame.
- **La foto e i tempi della variante** (Mattia, 2026-10-13): quando `derived_from_id`
  punta a un'originale che c'è (anche eliminata), `POST /recipes` copia nella ricetta nuova
  `image_url`, `prep_minutes` e `cook_minutes` dell'originale, letti nella stessa
  transazione del salvataggio. `RecipeCreate` non dichiara quei tre campi: il client non
  li sceglie, e se li mandasse si ignorano. Senza `derived_from_id`, o con un'originale che
  non c'è più, restano vuoti come oggi. Copiati, sono della variante: cambiare o cancellare
  l'originale dopo non li tocca, e `PUT` sulla variante li lascia com'erano.
- **`RecipeOut.derived_from`**: `{id, title, archived}` dell'originale, o `null`. `PUT` e
  `PATCH` non lo toccano: modificare o eliminare una variante lascia il legame com'è.
- **Il prompt della variante** *(Claude)*: lo stesso schema e le stesse regole della bozza
  (`SYSTEM_PROMPT`), più le regole della variante — ricevi la ricetta e la richiesta, rispondi
  con la ricetta modificata intera; applica la richiesta e **ribilancia** dosi, tempi e
  passaggi che ne dipendono; quel che la richiesta non tocca resta uguale (stesso `name` degli
  ingredienti, stessa dose, stesso ruolo, stesse porzioni); il titolo dice in cosa la variante
  è diversa; solo ingredienti alimentari; il costo è quello della variante. La domanda è un
  JSON con `ricetta` (titolo, descrizione, procedimento, porzioni, costo, e le righe col
  **nome canonico** dell'anagrafica, ruolo, dose e reparto) e `richiesta`: col nome canonico le
  righe tenute si riagganciano con certezza. Tetto di 4000 token in uscita (la ricetta intera
  torna indietro; la bozza da zero ne ha 2000).
- **Le righe proposte** passano dalla stessa lavorazione della bozza da zero (`match_name`):
  una riga che somiglia a un non alimentare dell'anagrafica torna **non agganciata e senza
  reparto** («non in anagrafica, sarà escluso»), e un reparto proposto che non è del cibo si
  scarta. Una riga così non parte salvando; se qualcuno la forzasse, l'imbuto
  `write_recipe_ingredients` la rifiuta con il 422 di oggi.
- **La spesa**: ogni chiamata, riuscita o no, va in `llm_calls` con
  `call_site = "recipe_variant"` (`LlmCallSite.RECIPE_VARIANT`), committata subito come per la
  bozza (una variante chiesta e buttata è pagata lo stesso).
- **Una variante non è importata**: nessuna pagina d'import, `owned_by_import` falso.
- **L'import che rifà l'originale non perde il legame** *(Claude)*: annullare una decisione
  della coda cancella e rifà le ricette importate non prese in carico (R10). Come le cotture
  (S9 §5.2), gli id delle varianti di una ricetta che si cancella aspettano nel `payload` della
  sua pagina, alla chiave `variant_recipe_ids`, e `materialize_ready` li rimette sulla ricetta
  rifatta. Nel frattempo la variante è senza legame (la riga non compare), e lo ritrova dopo.
  Creare una variante **non** prende in carico la pagina dell'originale: l'originale resta
  com'era, anche per l'import.

## 4. Parole a video

| Dove | Testo |
|---|---|
| Pulsante di sola icona nel dettaglio | «Modifica con AI» |
| Etichetta del campo | «Cosa vuoi cambiare?» |
| Segnaposto | «Sostituisci lo zucchero con il dolcificante» |
| Riga sotto il campo | «L'AI scrive una ricetta nuova, che correggi prima di salvare. Questa resta com'è.» |
| Pulsante | «Proponi la variante» / in volo «Propongo…» |
| Perché non parte | «Scrivi cosa cambiare: bastano tre lettere.» |
| Chiudere | «Annulla» |
| Guasto dell'AI (ambra) | «L'AI non ha risposto: questa ricetta resta com'è. Riprova fra poco.» |
| Titolo del modulo | «Nuova variante» |
| Sottotitolo del modulo | «Variante di «<titolo>»» |
| Riga sopra il modulo | «Hai chiesto: «<richiesta>». Correggi quel che serve: salvando nasce una ricetta nuova, e l'originale resta com'è.» |
| Pulsante del modulo | «Salva la variante» |
| Ritorno del modulo | «Ricetta» |
| Dopo il salvataggio | «Salvata.» |
| Legame nel dettaglio | «Variante di «<titolo>»», o «Variante di «<titolo>» (eliminata)» |

## 5. Fuori scope

- Nell'originale, l'elenco delle sue varianti (deciso: niente in più).
- Il legame negli elenchi del ricettario, nei filtri, nella ricerca.
- Riproporre dal modulo della variante (si torna all'originale e si riapre il pannello).
- Correggere a mano la foto e i tempi, della variante come di ogni altra ricetta: il modulo
  non li ha (R10 §7). La variante li copia dall'originale (§3.2), e poterli cambiare è una
  voce a sé, da decidere di giorno.
- La pagina delle spese dell'AI (H1): la sezione nuova `recipe_variant` le arriva come le
  altre; il suo nome a video è di H1.
- Correggere la formula «non in anagrafica» per una riga non alimentare della bozza (idea già
  in `next-steps.md`).

## 6. Domande aperte

Nessuna. La sola che c'era — se la variante prende la foto e i tempi dell'originale — è
stata decisa da Mattia il 2026-10-13: «Sì, copiali» (§2, §3.2, §3.4).
