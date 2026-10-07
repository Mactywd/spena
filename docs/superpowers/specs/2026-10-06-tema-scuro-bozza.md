# Tema scuro: il pulsante spento e il velo del ☰ — bozza

**Data:** 2026-10-06, fase di ricerca notturna, senza Mattia. **Voce:** «Tema scuro: il
pulsante primario spento diventa un verde torbido; il velo del ☰ scurisce poco» di
`next-steps.md` ([T3 Consegna 1]). È una bozza: niente è deciso, le domande stanno nelle
«Decisioni per Mattia» in fondo, ognuna con la raccomandazione.

_2026-10-07: decise tutte e sei le voci del §7, le raccomandate. Le prime due da Mattia; le
altre quattro da Claude, perché Mattia ha delegato le scelte estetiche e non funzionali
(«è un'app per me»). Non resta niente da confermare; manca il piano._

Mockup: `docs/mockups/2026-10-06-tema-scuro.html` (le due colonne, chiaro e scuro, con i
valori veri dei token). I numeri vengono da uno script rimasto nello scratchpad della
notte; il metodo e tutti i valori usati sono al §3, così chiunque li rifà.

## 1. Contesto

Dal giro a occhio a 375 px della Consegna 1 (`docs/prossimi-passi.md`, «Tre punti di
disegno del tema scuro per la Consegna 1», sotto T3) erano rimasti aperti due punti su
tre: il pulsante primario spento, fatto con `opacity`, in scuro diventa un verde torbido
con la scritta scura; il velo del ☰ su una pagina già scura scurisce poco, e il pannello si
stacca dalla pagina solo per il fondo `card`. Nessuno dei due è un difetto per WCAG (i
controlli spenti sono esenti, e il bordo di un pannello non è un controllo): sono difetti
per la regola di casa, ogni testo sopra 4,5:1 perché l'app si legge in corsia.

## 2. Come sono fatti oggi

- **Pulsante spento.** `frontend/src/components/ui/buttonClasses.ts`, nella `BASE` comune a
  tutte le varianti: `disabled:opacity-40 aria-disabled:opacity-40`. Vale per i tre modi di
  spegnere un `Button` (`disabled`, `busy`, `unavailableReason`, che dal 6a scrive il perché
  sotto in `ink-faint`) e per tutte e cinque le varianti. L'`opacity` compone il pulsante
  intero, fondo e scritta, sopra quel che ha dietro.
- **Il ☰.** `frontend/src/components/AppHeader.tsx`: un portale con il velo
  `bg-scrim/40` (`--color-scrim` è `#0b0f0d` in chiaro e `#000000` in scuro, «scuro in
  entrambi i temi») e il pannello `bg-card`, largo `w-72`, attaccato a destra, senza bordo né
  ombra. Sotto il velo ci sono l'intestazione (`bg-card`), la pagina (`page`) e le schede di
  reparto (`card`): il pannello confina con tutte e due le superfici.
- **Cosa misurano i test.** `theme.test.ts` controlla coppie di token pieni, nessuna
  composizione. `testiIlleggibili` in `e2e/style.spec.ts` salta ogni testo dentro
  `[disabled]`, `[aria-disabled=true]` o sotto un'opacità minore di 1: la scritta di un
  pulsante spento oggi non la misura nessuno.

## 3. Metodo di calcolo

- **Luminanza** WCAG 2.x, come in `theme.test.ts`: per ogni canale `s = v/255`,
  `s ≤ 0,03928 ? s/12,92 : ((s+0,055)/1,055)^2,4`; `L = 0,2126 R + 0,7152 G + 0,0722 B`.
  **Rapporto** `(L_chiaro + 0,05) / (L_scuro + 0,05)`.
- **Composizione alfa** in sRGB non lineare, come fanno i browser per `opacity` e per un
  colore con alfa: `c = a·sopra + (1−a)·sotto`, canale per canale, arrotondato a 8 bit.
  - pulsante con `opacity: 0,4`: fondo a video `mix(brand, dietro, 0,4)`, scritta a video
    `mix(on-brand, dietro, 0,4)`, con `dietro` = `page` o `card`;
  - velo `bg-scrim/40` (Tailwind v4: `color-mix(in oklab, scrim 40%, transparent)`, cioè
    `scrim` con alfa 0,4): superficie velata `mix(scrim, sotto, 0,4)`; un testo sotto il velo
    `mix(scrim, testo, 0,4)`, misurato contro la sua superficie velata.
- **Valori** di `frontend/src/index.css` al 2026-10-06:

| Token | Chiaro | Scuro |
|---|---|---|
| `page` / `card` | `#f1f4f2` / `#ffffff` | `#0e1210` / `#181e1a` |
| `ink` / `ink-soft` / `ink-faint` | `#16281f` / `#4e5a52` / `#636e66` | `#e7ece9` / `#b4beb8` / `#939e98` |
| `line` / `notch-off` | `#dce1dc` / `#848e87` | `#2c342f` / `#69736d` |
| `scrim` | `#0b0f0d` | `#000000` |
| `brand` / `on-brand` | `#0f7a4a` / `#ffffff` | `#3cb878` / `#06170e` |
| `low` / `on-low` / `danger` | `#9a5f0c` / `#ffffff` / `#b3261e` | `#e0a63a` / `#1f1503` / `#ff8a80` |

## 4. Misure di oggi

### 4.1 Il pulsante spento

| | Chiaro, su `page` | Chiaro, su `card` | Scuro, su `page` | Scuro, su `card` |
|---|---|---|---|---|
| primario acceso: scritta su fondo | 5,38:1 | 5,38:1 | 7,32:1 | 7,32:1 |
| primario spento: fondo a video | `#97c3af` | `#9fcab7` | `#20543a` | `#265c40` |
| primario spento: scritta a video | `#f7f8f7` | `#ffffff` | `#0b140f` | `#111b15` |
| **primario spento: scritta su fondo** | **1,84:1** | **1,81:1** | **2,13:1** | **2,26:1** |
| primario spento: fondo contro dietro | 1,77:1 | 1,81:1 | 2,15:1 | 2,17:1 |
| `warn` spento: scritta su fondo | 1,81:1 | 1,77:1 | 2,30:1 | 2,40:1 |
| `secondary` spento: scritta | 2,46:1 | 2,40:1 | 3,25:1 | 3,36:1 |
| `ghost` spento: scritta | 1,86:1 | 1,90:1 | 2,54:1 | 2,53:1 |
| `danger` spento: scritta | 1,98:1 | 2,03:1 | 2,26:1 | 2,24:1 |

Due cose che il giro a occhio non diceva. **In chiaro va peggio che in scuro**: 1,8:1
contro 2,1–2,3:1. In chiaro il pulsante spento è un verde pallido con la scritta bianca, e
sembra «spento» perché lo è davvero, fino a non leggersi; in scuro la scritta è quasi nera
su un verde scuro, ed è il «torbido» del giro: il colore resta saturo, solo più buio, e
non si capisce se è spento o sbagliato. E **tutte le varianti** spente stanno sotto 4,5:1 in
tutti e due i temi, perché la regola è una sola, nella `BASE`.

### 4.2 Il velo del ☰

| | Chiaro | Scuro |
|---|---|---|
| `page` velata | `#959896` | `#080b0a` |
| `card` velata | `#9d9f9e` | `#0e1210` |
| pagina velata contro pagina scoperta | 2,63:1 | **1,05:1** |
| scheda velata contro scheda scoperta | 2,66:1 | **1,11:1** |
| `ink` sotto il velo, su pagina (scoperto) | 5,89:1 (13,97:1) | 5,97:1 (15,79:1) |
| pannello `card` contro pagina velata | 2,91:1 | **1,17:1** |
| pannello `card` contro scheda velata | 2,66:1 | **1,11:1** |

Il velo spegne il **testo** della pagina nello stesso modo nei due temi (5,9:1 e 6,0:1): non
è lì la differenza. In chiaro la pagina passa dal bianco al grigio (2,6:1), e quel salto è
lo «spegnersi» che l'occhio vede; in scuro il fondo è già quasi nero e non ha dove
scendere (1,05:1). Il pannello poi confina con delle schede velate che hanno quasi il suo
stesso colore: `card` velata in scuro è `#0e1210`, cioè `page`, e il pannello `card` ci sta
sopra a 1,11:1.

**Il limite di fondo**, che vale per ogni opzione: in scuro la sola luminosità non può
staccare il pannello. `card` contro il nero pieno sta a 1,24:1; per arrivare a 3:1 contro il
nero serve una superficie con L ≥ 0,10, cioè un grigio `#5a5a5a`, che come fondo di un
pannello non è più un tema scuro. Un'ombra nera in scuro non si vede: al 50% sopra la
pagina velata misura 1,02:1. In scuro il pannello si stacca con un **segno** (un bordo),
non con una superficie.

## 5. Opzioni per il pulsante spento

Le soglie: la scritta ≥ 4,5:1 sul suo fondo anche da spenta (soglia del progetto, non di
WCAG); il fondo non deve sparire contro pagina e scheda, ma nemmeno arrivare a 3:1, che è
quanto basta a un segno per dire «qui si tocca».

### A. Un fondo pieno dedicato, senza `opacity` (raccomandata; decisa da Mattia il 2026-10-07)

Due token nuovi nel blocco `@theme` e nel blocco scuro:

| Token | Chiaro | Scuro |
|---|---|---|
| `--color-disabled` | `#d8dfdb` | `#2a332d` |
| `--color-on-disabled` | `#4e5a52` (= `ink-soft`) | `#b4beb8` (= `ink-soft`) |

| Misura | Chiaro | Scuro |
|---|---|---|
| scritta su fondo | **5,33:1** | **6,83:1** |
| fondo contro `page` | 1,22:1 | 1,45:1 |
| fondo contro `card` | 1,36:1 | 1,30:1 |

Grigio e non un verde più spento: grigio vuol dire «spento» in ogni app, e un verde
attenuato dice ancora «azione principale» (lo stesso argomento di `notch-off`, che è grigia
perché una tacca spenta colorata direbbe uno stato che non c'è). Accanto a un secondario
acceso (bianco con l'anello `line`) si distingue: pieno, senza anello, scritta più tenue.
Nel mockup c'è il confronto.

Il nome: la richiesta della notte diceva `brand-off`, ma lo stesso fondo serve a `warn`
spento (oggi 1,8:1 e 2,3:1, stesso difetto), quindi un nome neutro. `on-disabled` ha lo
stesso valore di `ink-soft` ma un nome suo, per la regola «testo su fondo pieno usa il
token `on-*`»: se un giorno il fondo cambia, la scritta lo segue senza toccare `ink-soft`.

- **Codice.** `index.css`: i due token nei due blocchi. `buttonClasses.ts`: via
  `disabled:opacity-40 aria-disabled:opacity-40` dalla `BASE`; ogni variante dice come si
  spegne — `primary` e `warn` con `bg-disabled text-on-disabled`, `secondary` con
  `text-ink-faint` (resta l'anello `line`), `ghost` e `danger` con `text-ink-faint` — sotto i
  prefissi `disabled:` e `aria-disabled:`. `Button.tsx` non cambia.
- **Test.** `theme.test.ts`: la coppia `["on-disabled", "disabled"]` in `PAIRS`; e una
  soglia bassa per la forma, `disabled` contro `page` e `card` ≥ 1,2:1, perché il pulsante
  non svanisca (oggi 1,22–1,45). `e2e/style.spec.ts`: «Entra» a campo vuoto
  (`aria-disabled`, raggiungibile senza semina) ha opacità calcolata 1, fondo uguale al token
  `disabled` del tema e scritta ≥ 4,5:1, nei due temi — è la prova che `aria-disabled:bg-…`
  vince su `bg-brand` nel CSS compilato, cosa che jsdom non vede (quarta lezione di
  `CLAUDE.md`). E `testiIlleggibili` smette di saltare `[disabled]` e
  `[aria-disabled=true]`: da qui in poi ogni pulsante spento in ogni luogo è misurato come
  ogni altro testo (il salto per opacità resta, e copre i controlli fuori da `Button`).

Per le altre varianti, già senza fondo, `ink-faint` regge: 4,80:1 su `page` e 5,31:1 su
`card` in chiaro, 6,82:1 e 6,12:1 in scuro. Il limite: in chiaro `ghost` acceso
(`ink-soft`, 6,52:1) e spento (`ink-faint`, 4,80:1) sono vicini; a dire «spento» ci pensa
anche il perché scritto sotto, che `unavailableReason` aggiunge sempre.

### B. Il pulsante spento come «fantasma»: bordo e scritta, fondo trasparente

Token esistenti: bordo 1 px `notch-off`, scritta `ink-faint`.

| Misura | Chiaro `page` | Chiaro `card` | Scuro `page` | Scuro `card` |
|---|---|---|---|---|
| scritta | 4,80:1 | 5,31:1 | 6,82:1 | 6,12:1 |
| bordo | 3,06:1 | 3,39:1 | 3,84:1 | 3,45:1 |

Regge tutte le soglie senza token nuovi, ma rovescia la gerarchia: il pulsante spento ha un
bordo più marcato del secondario acceso, il cui anello `line` sta a 1,33:1 in chiaro e
1,32:1 in scuro. Nel mockup si vede: lo spento sembra il più toccabile dei due. E prendere
un bordo dai bordi del secondario, per abbassarlo, lo farebbe sparire (`line` a 1,2–1,5:1).

- **Codice.** Solo `buttonClasses.ts`: per ogni variante, da spenta,
  `bg-transparent text-ink-faint ring-1 ring-inset ring-notch-off`.
- **Test.** `MARK_PAIRS` già ha `["notch-off", "card"]`; si aggiunge `["notch-off", "page"]`
  (3,06:1 in chiaro, il margine più stretto). L'e2e come per A.

### C. `opacity` solo in chiaro, il fondo dedicato solo in scuro

Tiene il chiaro com'è e corregge il solo difetto visto a occhio. Ma il chiaro com'è sta a
1,84:1 e 1,81:1: lascia in chiaro proprio il difetto più grosso. Alzare l'opacità non basta
a nessuna soglia ragionevole: 0,5 → 2,18:1, 0,6 → 2,59:1, 0,7 → 3,09:1 in chiaro, e anche
in scuro 0,7 si ferma a 4,13:1. E un'`opacity` diversa per tema vuol dire una variabile in
`index.css` letta da una classe (`aria-disabled:opacity-(--off-opacity)`) accanto a un fondo
che vale solo in scuro: due meccanismi per lo stesso stato. Scartata.

### Raccomandazione

**A.** È la sola opzione che porta la scritta spenta sopra 4,5:1 in tutti e due i temi
senza rovesciare la gerarchia fra spento e acceso, e lo fa con il meccanismo che il progetto
usa già per tutto il resto: un token pieno per tema, una coppia in `theme.test.ts`, nessuna
composizione da calcolare. Toglie anche il guaio invisibile del §4.1: l'`opacity` rendeva
illeggibile, in chiaro, ogni pulsante spento dell'app.

## 6. Opzioni per il velo del ☰

Le soglie: il pannello contro ciò che il velo copre ≥ 3:1, col pannello o con il suo
bordo; la pagina sotto il velo visibilmente spenta. Per quest'ultima la misura è il testo
`ink` sotto il velo, perché in scuro è lui che si spegne, non il fondo (§4.2).

### V1. Un velo per tema

Una variabile `--scrim-alpha`: **45%** in chiaro, **60%** in scuro. `--color-scrim` non cambia.

| Misura | Chiaro 45% | Scuro 60% | (Scuro 70%) |
|---|---|---|---|
| pannello `card` contro pagina velata | 3,35:1 | 1,19:1 | 1,20:1 |
| pannello `card` contro scheda velata | 3,09:1 | 1,16:1 | 1,18:1 |
| `ink` sotto il velo (oggi 5,89 / 5,97) | 5,17:1 | 3,09:1 | 2,18:1 |
| `brand` sotto il velo (oggi 3,30 / 3,20) | — | 1,98:1 | 1,55:1 |

In chiaro porta il pannello sopra 3:1 (oggi 2,91 e 2,66). In scuro spegne davvero la
pagina — il testo passa da 6:1 a 3:1, la differenza che il giro chiedeva — ma il pannello
resta a 1,2:1: il velo non può fare di più (§4.2, il limite).

- **Codice.** `index.css`: `--scrim-alpha: 45%` nel blocco `:root` semplice (quello di
  `--safe-bottom`) e `--scrim-alpha: 60%` nel blocco scuro. Fuori da `@theme` perché Tailwind
  v4 scrive solo le variabili di tema che trova usate, e un uso dentro un modificatore
  potrebbe non contare: da verificare nel CSS compilato. `AppHeader.tsx`: `bg-scrim/40` →
  `bg-scrim/(--scrim-alpha)`, la sintassi di Tailwind v4 per un'opacità letta da una
  variabile. Se non compilasse come atteso, il ripiego è un valore arbitrario
  (`bg-[color-mix(in_srgb,var(--color-scrim)_var(--scrim-alpha),transparent)]`).
- **Test.** `theme.test.ts` impara la composizione: legge `--scrim-alpha` nei due blocchi e
  controlla `card` contro `mix(scrim, page, alfa)` e `mix(scrim, card, alfa)` (la soglia
  completa sta sotto, con V2). `e2e/style.spec.ts`, nel giro del ☰ che c'è già: il
  `background-color` calcolato di `[data-menu-backdrop]` ha l'alfa del tema, 0,45 e 0,6 —
  la prova che la sintassi è arrivata a video. Il test legge l'alfa e non confronta la
  stringa: un `color-mix(in oklab, …)` Chromium può restituirlo come `oklab(… / 0.6)` e non
  come `rgba(…)` (lo dice già il commento di `testiIlleggibili`).

### V2. Un bordo sul lato del pannello

Un token `--color-panel-edge` e un `border-l` di 1 px sul pannello.

| `panel-edge` scuro | contro pagina velata (40%) | contro scheda velata (40%) | contro il pannello |
|---|---|---|---|
| `#3a443e` | 1,95:1 | 1,87:1 | 1,68:1 |
| `#4a544e` | 2,51:1 | 2,40:1 | 2,15:1 |
| **`#5a645e`** | **3,22:1** | **3,07:1** | 2,76:1 |
| (`#69736d`, = `notch-off`) | 4,02:1 | 3,84:1 | — |

`#5a645e` è il più scuro sopra 3:1: sta fra `ink-ghost` (`#4a544e`) e `notch-off`
(`#69736d`), e non riusa `notch-off` perché quello vuol dire «tacca spenta». In chiaro il
token vale `#ffffff` come `card`: il bordo non si vede, e a staccare il pannello è il suo
bianco (V1 lo porta sopra 3:1). Da solo, V2 stacca il pannello ma lascia la pagina accesa
(`ink` sotto il velo 5,97:1).

- **Codice.** `index.css`: il token nei due blocchi. `AppHeader.tsx`: `border-l
  border-panel-edge` sul pannello.
- **Test.** In `theme.test.ts`, per ogni tema e per `page` e `card` velate:
  `max(ratio(card, velata), ratio(panel-edge, velata)) ≥ 3` — in chiaro vince il pannello,
  in scuro il bordo. In e2e: `border-left-color` del dialogo uguale al token del tema, largo
  1 px.

### V3. Il pannello un gradino sopra `card`

L'elevazione per luminosità del tema scuro di Material: un token `--color-raised`,
`#ffffff` in chiaro (uguale a `card`) e più chiaro di `card` in scuro.

| `raised` scuro | contro pagina velata | contro scheda velata | `ink-faint` sopra | `line` sopra |
|---|---|---|---|---|
| `#202722` | 1,29:1 | 1,24:1 | 5,52:1 | 1,19:1 |
| `#232b26` | 1,36:1 | 1,30:1 | 5,25:1 | 1,13:1 |
| `#262e29` | 1,42:1 | 1,35:1 | 5,04:1 | 1,09:1 |

Tutti i testi ci stanno sopra (`ink` 12,2:1, `ink-soft` 7,6:1, `brand` 5,8:1 sul
`#232b26`), ma il guadagno è piccolo, per il limite del §4.2: da 1,17 a 1,36:1. In cambio
nasce una superficie nuova su cui ogni coppia di `theme.test.ts` va rifatta, e i divisori
`line` del menu scendono da 1,32 a 1,13:1, quasi invisibili. Ha senso il giorno in cui
l'app avrà più pannelli sovrapposti (oggi il ☰ è il solo `role="dialog"`); per un pannello
solo, no.

- **Codice.** `index.css`: il token nei due blocchi. `AppHeader.tsx`: `bg-card` → `bg-raised`
  sul pannello.
- **Test.** `PAIRS` con ogni testo del pannello su `raised` (`ink`, `ink-soft`, `brand`
  almeno); la soglia del velo come in V2, col pannello `raised`.

### Raccomandazione

**V1 + V2**: velo 45% in chiaro e 60% in scuro, e il bordo `panel-edge` (`#ffffff` /
`#5a645e`). Sono i due mezzi che lavorano su due difetti diversi: il velo più scuro spegne
la pagina, il bordo stacca il pannello, e nessuno dei due da solo fa tutt'e due le cose. In
scuro:

| Misura (scuro, 60%, bordo `#5a645e`) | |
|---|---|
| bordo contro pagina velata | **3,29:1** |
| bordo contro scheda velata | **3,20:1** |
| `ink` sotto il velo | 3,09:1 (oggi 5,97:1) |
| pannello contro pagina velata | 1,19:1 (il bordo fa il suo lavoro) |

In chiaro: pannello contro pagina velata **3,35:1**, contro scheda velata **3,09:1**, `ink`
sotto il velo 5,17:1. Cambia anche il chiaro, di poco (dal 40 al 45%), perché oggi il
pannello ci sta sotto 3:1 (2,91 e 2,66). V3 resta un'aggiunta possibile, non necessaria.

## 7. Decisioni per Mattia

1. **Il pulsante spento diventa grigio pieno** (opzione A: fondo `disabled`, scritta
   `on-disabled`, niente più `opacity`)? Raccomandato: **sì**. In alternativa B (fantasma), che
   però fa sembrare lo spento più toccabile del secondario acceso. **Deciso da Mattia il
   2026-10-07: A.**
2. **La regola vale per tutte le varianti**, nella stessa consegna (`primary` e `warn` col
   fondo grigio, `secondary`, `ghost` e `danger` con la scritta `ink-faint`)? Raccomandato:
   **sì** — oggi stanno tutte sotto 4,5:1, e due regole per «spento» nello stesso componente
   sono quel che il ridisegno ha tolto. **Deciso da Mattia il 2026-10-07: tutte.**
3. **`busy` resta uguale a spento** (anche il pulsante in volo diventa grigio per la durata
   della richiesta)? Raccomandato: **sì**, è già la regola scritta in `buttonClasses.ts`
   («deve sembrare spento come uno spento davvero»). L'alternativa, un aspetto suo per
   `busy` (per esempio il colore pieno con un'icona che gira), è un lavoro a parte.
   **Deciso da Claude il 2026-10-07, su delega di Mattia per le scelte estetiche: sì.**
4. **I nomi** `disabled` / `on-disabled` invece di `brand-off`? Raccomandato: **sì**, perché
   lo stesso fondo serve anche a `warn`. **Deciso da Claude il 2026-10-07, su delega di Mattia per le scelte estetiche: sì.**
5. **Il velo: 45% in chiaro e 60% in scuro, più un bordo `#5a645e` sul pannello in scuro**
   (V1 + V2)? Raccomandato: **sì**. In alternativa 70% in scuro, che spegne di più la pagina
   (`ink` sotto il velo 2,18:1) ma rende quasi illeggibile quel che si sta lasciando.
   **Deciso da Claude il 2026-10-07, su delega di Mattia per le scelte estetiche: V1 + V2.**
6. **L'e2e smette di saltare i pulsanti spenti** nel controllo «ogni testo sopra 4,5:1»?
   Raccomandato: **sì**: con A diventano misurabili, e lasciarli fuori vuol dire che il
   prossimo `opacity` torna senza che nessun test lo veda. **Deciso da Claude il 2026-10-07, su delega di Mattia per le scelte estetiche: sì.**

## 8. Fuori scope

- **Gli altri controlli spenti con `opacity`**, fuori da `Button`: `Checkbox` e la casella
  di `ListRow` (`aria-disabled:opacity-40`), le tacche di `StockGauge` e il nome in
  `PantryRow` (`aria-disabled:opacity-40`), `CostPicker` (`disabled:opacity-60`),
  `IngredientPicker` e `OptionList` (`disabled:opacity-50`). Hanno lo stesso difetto, misure
  da fare una per una; voce a parte.
- Un aspetto proprio per `busy` (decisione 3).
- L'elevazione per luminosità come sistema (V3) e ogni altra superficie sovrapposta.
- Il `background_color` del manifesto e la schermata d'avvio in scuro (in «Da provare sul
  telefono» della Consegna 1).
- L'avviso di conferma rovesciato: deciso da Mattia il 2026-09-29, spec T3 §3.5.

## 9. Mockup e script

- **Mockup:** `docs/mockups/2026-10-06-tema-scuro.html`, autonomo (CSS in linea, Inter da
  Google Fonts). Due colonne da 375 px, chiaro e scuro forzati coi valori del §3 e i token
  proposti; per ogni variante, il pulsante acceso, spento oggi e nelle opzioni A, B e C, e il
  ☰ aperto sopra una pagina finta (oggi, V1, V2, V3, raccomandata), con i rapporti scritti
  sotto. La composizione la fa il browser (`opacity`, velo `rgba`), come nell'app.
- **Script:** `contrasti.py`, nello scratchpad della notte, non nel repo. Fa esattamente il
  §3: luminanza, rapporto e `mix(sopra, sotto, a)` sui valori della tabella, per ogni riga
  delle tabelle dei §4–6. Chi deve rifarlo ha qui tutto quel che serve; il posto naturale
  delle stesse formule, se A e V1+V2 passano, è `theme.test.ts` (che ha già luminanza e
  rapporto, e imparerebbe `mix`).
