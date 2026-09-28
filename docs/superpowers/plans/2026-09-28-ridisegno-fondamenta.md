# T3 Consegna 0 — Le fondamenta del ridisegno: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Portare in produzione il linguaggio visivo nuovo: colori chiari e scuri, il carattere Inter, le icone Tabler, il cesto come marchio unico, la barra delle schede con le icone, la pagina «Non trovata», e le primitive su cui le Consegne 1–6 rifaranno le schermate. Nessuna schermata cambia disposizione.

**Architecture:** Tutto è nel frontend. I colori restano variabili del blocco `@theme` di `frontend/src/index.css`; il tema scuro ridefinisce le stesse variabili sotto `@media (prefers-color-scheme: dark)`, così le classi di Tailwind (`bg-page`, `text-brand`…) cambiano da sole. Il testo su un fondo pieno usa i token `on-*`, mai `text-white`. Le primitive nuove stanno in `frontend/src/components/ui/`, ciascuna con il suo test in Vitest; ciò che jsdom non vede (colori, carattere, contrasto in scuro) lo misura `frontend/e2e/style.spec.ts` nel browser.

**Tech Stack:** React 19, TypeScript, Tailwind 4, Vitest + Testing Library, Playwright; dipendenze nuove `@tabler/icons-react` (3.x) e `@fontsource-variable/inter` (5.x).

**Spec:** `docs/superpowers/specs/2026-09-28-ridisegno-design.md` (§3 è questa consegna). Leggi anche `CLAUDE.md` alla radice: le sue sette lezioni valgono qui, soprattutto la quarta (un selettore CSS non è una superficie di test) e la settima (`npm run typecheck`, non `tsc --noEmit`).

## Global Constraints

- **Tutti i colori stanno nel blocco `@theme` di `frontend/src/index.css`**, e il tema scuro li ridefinisce nello stesso file. Nessuna schermata nomina un colore grezzo: `grep -rn "emerald\|neutral-\|text-white\|bg-white\|bg-black" frontend/src --include=*.tsx --include=*.ts` deve restituire solo `BarcodeScanner.tsx` (`bg-black` dietro il video della fotocamera, che resta nero in entrambi i temi).
- **Ogni coppia testo su fondo sta sopra 4,5:1**, in chiaro e in scuro. Il testo su un fondo pieno (`bg-brand`, `bg-low`, `bg-finished`, `bg-expiry`) usa `text-on-brand`, `text-on-low`, `text-on-finished`, `text-on-expiry`.
- **Il tema scuro segue il telefono** (`prefers-color-scheme`). Nessun interruttore nell'app.
- **Ogni bersaglio tocca almeno 44×44 px** (`min-h-11` / `size-11`), anche quando il disegno è più piccolo.
- **I campi di testo restano a 16 px** (`text-base`): sotto, iOS ingrandisce la pagina.
- **Regola delle icone** (spec §2): più pulsanti in gruppo → solo icone, con il nome completo in `aria-label`; un pulsante da solo → icona e testo. Un pulsante di sola icona senza `label` non deve compilare.
- **Le icone si importano una per una** da `@tabler/icons-react`, e solo attraverso `frontend/src/components/ui/icons.ts`: nessun altro file importa da `@tabler/icons-react`.
- **Il vocabolario degli stati è uno**: `STATUS_LABELS` di `frontend/src/features/pantry/statusLabels.ts` («Disponibile», «Quasi finito», «Finito»). Nessun componente nuovo inventa altre parole per gli stessi tre stati.
- **Le schermate non cambiano disposizione in questa consegna.** Le primitive nuove esistono e sono provate; le schermate le adotteranno nelle Consegne 1–6. Fanno eccezione solo ciò che la spec §3.6 porta in produzione adesso: token, carattere, cesto nell'intestazione, barra delle schede con le icone, rotta `*`.
- Commenti e testi a video in italiano; identificatori in inglese. Commenti nello stile del file che si tocca: spiegano il perché, non il cosa.
- Comandi (dalla cartella `frontend/`): `npx vitest run <file>` per un test (non esiste `npm test`), `npm run lint`, `npm run typecheck`, `npm run build`. Mai `npx tsc --noEmit`.

## Rulings presi scrivendo il piano

- **Il verde chiaro diventa `#0f7a4a`** (da `#14804f`): `#14804f` come testo sulla pagina misura 4,48:1 e su `brand-tint` 4,21:1, sotto soglia. `#0f7a4a` misura 4,86:1 e 4,56:1. Cambiano con lui la favicon e le due icone PNG della PWA.
- **`ink` resta `#16281f`**: la bozza usava `#101512`, ma `#16281f` passa già tutto e non c'è motivo di cambiarlo.
- **Le tacche usano le parole di `STATUS_LABELS`**, non «c'è / sta finendo» delle bozze: la spec §4.4 le citava a titolo d'esempio, ma due vocabolari per gli stessi tre stati sono proprio l'incoerenza che il giro ha segnalato.
- **`buttonClasses` resta**: serve ai `<Link>` con l'aspetto di un pulsante. `Button` lo usa al suo interno.
- **`StatusChip` ed `ExpiryChip` restano come nomi**, ma diventano due involucri di `Chip`: chi li usa oggi non cambia, e la forma della pastiglia sta in un posto solo.

---

## File

| File | Cosa |
|---|---|
| `frontend/src/index.css` | token chiari, blocco scuro, `color-scheme`, `--font-sans`, animazione dell'avviso |
| `frontend/src/theme.test.ts` (nuovo) | contrasto di ogni coppia in chiaro e in scuro, ogni token chiaro ha il suo scuro |
| `frontend/src/components/ui/buttonClasses.ts` | `text-on-*`, forma `icon`, tipi esportati |
| `frontend/src/features/pantry/statusLabels.ts`, `expiryLabels.ts` | toni con `finished` e `on-*` |
| `frontend/src/features/recipe-form/RecipeForm.tsx` | `text-white` → `text-on-brand` |
| `frontend/src/components/AppHeader.tsx` | velo con `bg-scrim`, cesto, icone Tabler |
| `frontend/index.html`, `frontend/vite.config.ts`, `frontend/public/favicon.svg`, `icon-192.png`, `icon-512.png` | colori della barra di stato e marchio |
| `frontend/scripts/render-icons.mjs` (nuovo) | rigenera le PNG dal SVG con Playwright |
| `frontend/src/main.tsx` | importa Inter |
| `frontend/src/components/ui/icons.ts` (nuovo) | l'unico punto d'ingresso delle icone |
| `frontend/src/components/ui/departments.ts` (+ test) | reparto → icona e tinta |
| `frontend/src/components/ui/BrandMark.tsx` (nuovo) | il cesto, usato da intestazione e accesso |
| `frontend/src/components/TabBar.tsx` (+ test) | icone Tabler, «Lista» attiva anche su `/sistema` |
| `frontend/src/components/ui/Button.tsx`, `IconToolbar.tsx` (+ test) | pulsanti |
| `frontend/src/components/ui/ActionBar.tsx`, `Section.tsx` (+ test) | barra con il +, sezione di reparto |
| `frontend/src/components/ui/StockGauge.tsx`, `StatusDot.tsx`, `Chip.tsx` (+ test) | tacche, pallino, pastiglia |
| `frontend/src/components/ui/noticeContext.ts`, `NoticeProvider.tsx` (+ test) | l'avviso di conferma unico |
| `frontend/src/components/ui/ErrorState.tsx`, `EmptyState.tsx` (+ test) | errore e vuoto |
| `frontend/src/features/not-found/NotFoundScreen.tsx`, `frontend/src/App.tsx` | rotta `*` e `NoticeProvider` |
| `frontend/src/components/ui/OptionList.tsx`, `frontend/src/components/IngredientPicker.tsx` (+ test) | ARIA valido, «Aggiungi «…»» |
| `frontend/e2e/style.spec.ts` | tema scuro, contrasto su ogni schermata, carattere, nomi dei pulsanti |
| `CLAUDE.md`, `docs/prossimi-passi.md` | la regola dei colori col tema scuro; stato di T3 |

---

### Task 1: I token del colore, chiari e scuri

**Files:**
- Modify: `frontend/src/index.css` (blocco `@theme` e seguenti)
- Create: `frontend/src/theme.test.ts`
- Modify: `frontend/src/components/ui/buttonClasses.ts`, `frontend/src/features/pantry/statusLabels.ts`, `frontend/src/features/pantry/expiryLabels.ts`, `frontend/src/features/recipe-form/RecipeForm.tsx:168`, `frontend/src/components/AppHeader.tsx` (il velo, `bg-ink/40`)
- Modify: `frontend/index.html`, `frontend/vite.config.ts`, `frontend/public/favicon.svg`, `frontend/public/icon-192.png`, `frontend/public/icon-512.png`
- Create: `frontend/scripts/render-icons.mjs`
- Modify: `frontend/e2e/style.spec.ts` (il primo test, che oggi confronta con `rgb(238, 241, 238)`)

**Interfaces:**
- Produces: le classi Tailwind `bg-/text-` di `page card ink ink-soft ink-faint ink-ghost line scrim brand brand-tint on-brand low low-tint on-low finished finished-tint on-finished danger expiry expiry-tint on-expiry` e delle tinte di reparto `dept-peach dept-peach-ink dept-pink dept-pink-ink dept-blue dept-blue-ink dept-sand dept-sand-ink dept-slate dept-slate-ink`. Il Task 2 (reparti), il 6 (tacche, pallino, pastiglia) e il 7 (avviso) le usano.

- [ ] **Step 1: Scrivi il test del contrasto, che fallisce**

`frontend/src/theme.test.ts`:

```ts
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

// Il contrasto dei token si controlla sui valori scritti in index.css, in chiaro e in
// scuro, senza aspettare un browser: è aritmetica. Che quei valori arrivino davvero a
// video lo misura e2e/style.spec.ts; qui si impedisce che un token nuovo, o un ritocco,
// scenda sotto 4,5:1 senza che nessuno se ne accorga.
const css = readFileSync(fileURLToPath(new URL("./index.css", import.meta.url)), "utf8");

function tokens(block: string): Record<string, string> {
  const out: Record<string, string> = {};
  for (const [, name, hex] of block.matchAll(/--color-([a-z-]+):\s*(#[0-9a-fA-F]{6})\s*;/g)) {
    out[name] = hex;
  }
  return out;
}

const light = tokens(css.match(/@theme\s*\{([\s\S]*?)\n\}/)?.[1] ?? "");
const dark = tokens(
  css.match(/@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{([\s\S]*?)\}\s*\}/)?.[1] ?? ""
);

function luminance(hex: string): number {
  const [r, g, b] = [1, 3, 5].map((i) => {
    const s = parseInt(hex.slice(i, i + 2), 16) / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function ratio(a: string, b: string): number {
  const [x, y] = [luminance(a), luminance(b)];
  return (Math.max(x, y) + 0.05) / (Math.min(x, y) + 0.05);
}

// [testo, fondo]: ogni coppia che l'app mette a video. Chi aggiunge un token che porta
// testo aggiunge qui la sua coppia.
const PAIRS: [string, string][] = [
  ["ink", "page"], ["ink", "card"],
  ["ink-soft", "page"], ["ink-soft", "card"],
  ["ink-faint", "page"], ["ink-faint", "card"],
  ["brand", "page"], ["brand", "card"], ["brand", "brand-tint"], ["on-brand", "brand"],
  ["low", "page"], ["low", "card"], ["low", "low-tint"], ["on-low", "low"],
  ["finished", "page"], ["finished", "card"], ["finished", "finished-tint"], ["on-finished", "finished"],
  ["danger", "page"], ["danger", "card"],
  ["expiry", "page"], ["expiry", "card"], ["expiry", "expiry-tint"], ["on-expiry", "expiry"],
  // l'avviso di conferma è rovesciato: fondo `ink`, testo `page`, azione `brand-tint`
  ["page", "ink"], ["brand-tint", "ink"],
  ["dept-peach-ink", "dept-peach"], ["dept-pink-ink", "dept-pink"], ["dept-blue-ink", "dept-blue"],
  ["dept-sand-ink", "dept-sand"], ["dept-slate-ink", "dept-slate"],
];

describe("i token del colore", () => {
  it("ogni token chiaro ha il suo valore scuro, e viceversa", () => {
    expect(Object.keys(dark).sort()).toEqual(Object.keys(light).sort());
  });

  for (const [mode, palette] of [["chiaro", light], ["scuro", dark]] as const) {
    it.each(PAIRS)(`in ${mode}, %s su %s sta sopra 4,5:1`, (text, background) => {
      expect(palette[text], `--color-${text} manca in ${mode}`).toBeDefined();
      expect(palette[background], `--color-${background} manca in ${mode}`).toBeDefined();
      expect(ratio(palette[text], palette[background])).toBeGreaterThanOrEqual(4.5);
    });
  }
});
```

- [ ] **Step 2: Verifica che fallisca**

Run: `cd frontend && npx vitest run src/theme.test.ts`
Expected: FAIL. Il blocco scuro non esiste, quindi il primo test trova `[]` contro l'elenco dei token chiari; mancano anche `on-brand`, `finished` e le tinte di reparto.

- [ ] **Step 3: Riscrivi il blocco `@theme` e aggiungi quello scuro**

In `frontend/src/index.css` sostituisci il blocco `@theme { … }` (oggi alle righe 14–50) con questo. Tieni il commento in testa al file, ma cambia la sua ultima frase del primo paragrafo in: «e il tema scuro ridefinisce le stesse variabili qui sotto, sotto `prefers-color-scheme`: nessuna schermata sa in che tema è.»

```css
@theme {
  --color-page: #f1f4f2;
  --color-card: #ffffff;

  --color-ink: #16281f;
  --color-ink-soft: #4e5a52;
  --color-ink-faint: #636e66;
  /* I gradini spenti del costo di una ricetta (R9): `€€€··` si legge come «tre su
     cinque» solo se i due spenti si vedono e insieme non si confondono con i tre
     accesi. Non porta testo da leggere — il gradino sta nell'etichetta accessibile —
     quindi non ha il vincolo di contrasto del testo: deve solo stare lontano da
     `ink` e restare visibile sul bianco e sul grigio della pagina alla luce del
     giorno. */
  --color-ink-ghost: #b3bcb5;

  --color-line: #dce1dc;
  /* il velo dietro un pannello: scuro in entrambi i temi, perché deve spegnere la
     pagina, non schiarirla */
  --color-scrim: #0b0f0d;

  /* 4,86:1 sulla pagina e 4,56:1 sulla sua tinta: il verde di prima, #14804f, come
     testo stava a 4,48:1 e 4,21:1, sotto la soglia */
  --color-brand: #0f7a4a;
  --color-brand-tint: #e4efe8;
  /* il testo sopra un fondo pieno ha un token suo, e non è `text-white`: in scuro il
     verde si schiarisce, e il bianco sopra non si leggerebbe più */
  --color-on-brand: #ffffff;

  /* `low` ha un colore suo e non una sfumatura del verde: è l'unico stato che
     cambia la risposta alla domanda «questa ricetta si può cucinare?» (la regola
     primario/secondario in backend/app/domain/rules.py), e due stati che si
     somigliano rendono invisibile la sola regola che fa guadagnare qualcosa al
     tenere aggiornata la dispensa. */
  --color-low: #9a5f0c;
  --color-low-tint: #fbefdc;
  --color-on-low: #ffffff;

  /* «finito» ha un colore solo in tutta l'app (dal giro di T3: ne aveva tre). È lo
     stesso rosso degli errori perché la ✕ non è più rossa: il rosso vuol dire «manca»
     o «non è andata», e basta. */
  --color-finished: #b3261e;
  --color-finished-tint: #fbe7e5;
  --color-on-finished: #ffffff;
  --color-danger: #b3261e;

  /* La scadenza ha un colore suo, e non è il giallo: la zona gialla vuol già dire
     «comincia a mancare», e due fatti diversi sullo stesso colore non ne dicono più
     nessuno. Due intensità e non due colori: «sta per scadere» e «scaduto» sono lo
     stesso fatto a due distanze. */
  --color-expiry: #5b45a8;
  --color-expiry-tint: #efeaf9;
  --color-on-expiry: #ffffff;

  /* Le tinte dei reparti (spec T3 §3.3): cinque, una per famiglia, lontane da verde,
     giallo, rosso e viola, che vogliono già dire «c'è», «sta finendo», «finito» e
     «scade». Stanno solo nel quadratino del titolo di una sezione, mai sulle righe. */
  --color-dept-peach: #fde7dc;
  --color-dept-peach-ink: #8a3b17;
  --color-dept-pink: #fbe3ee;
  --color-dept-pink-ink: #8a2651;
  --color-dept-blue: #dcecff;
  --color-dept-blue-ink: #1a4f8f;
  --color-dept-sand: #f1e8d8;
  --color-dept-sand-ink: #6b4d1f;
  --color-dept-slate: #e6e9ee;
  --color-dept-slate-ink: #3d4756;

  --radius-card: 14px;
}

/* Il tema scuro: le stesse variabili, altri valori. Tailwind scrive ogni classe come
   `var(--color-…)`, quindi ridefinire la variabile qui cambia `bg-page` e `text-brand`
   dappertutto senza che una schermata lo sappia. I valori non sono il chiaro rovesciato:
   ogni coppia di theme.test.ts sta sopra 4,5:1 anche qui. */
@media (prefers-color-scheme: dark) {
  :root {
    --color-page: #0e1210;
    --color-card: #181e1a;
    --color-ink: #e7ece9;
    --color-ink-soft: #b4beb8;
    --color-ink-faint: #939e98;
    --color-ink-ghost: #4a544e;
    --color-line: #2c342f;
    --color-scrim: #000000;
    --color-brand: #3cb878;
    --color-brand-tint: #16301f;
    --color-on-brand: #06170e;
    --color-low: #e0a63a;
    --color-low-tint: #33260d;
    --color-on-low: #1f1503;
    --color-finished: #ff8a80;
    --color-finished-tint: #3a1714;
    --color-on-finished: #2b0805;
    --color-danger: #ff8a80;
    --color-expiry: #b9a6ff;
    --color-expiry-tint: #261f3d;
    --color-on-expiry: #150d33;
    --color-dept-peach: #3d2317;
    --color-dept-peach-ink: #f5b99c;
    --color-dept-pink: #3f1a2c;
    --color-dept-pink-ink: #f5b3cf;
    --color-dept-blue: #16304d;
    --color-dept-blue-ink: #a8cdf5;
    --color-dept-sand: #352b1b;
    --color-dept-sand-ink: #e3cfa6;
    --color-dept-slate: #262b33;
    --color-dept-slate-ink: #c3cad6;
  }
}
```

Poi, nel blocco `:root { --safe-bottom: … }` che segue, aggiungi `color-scheme: light dark;` con il commento: «i controlli nativi (il selettore della data, le barre di scorrimento) seguono il tema anche loro».

- [ ] **Step 4: Verifica che il test passi**

Run: `cd frontend && npx vitest run src/theme.test.ts`
Expected: PASS, 1 + 2×31 casi.

- [ ] **Step 5: Togli `text-white` e il velo di `ink`**

- `frontend/src/components/ui/buttonClasses.ts`: `primary: "bg-brand text-on-brand"`, `warn: "bg-low text-on-low"`.
- `frontend/src/features/pantry/statusLabels.ts`:

```ts
export const STATUS_TONE: Record<PantryStatus, StatusTone> = {
  available: { fill: "bg-brand text-on-brand", tint: "bg-brand-tint text-brand" },
  low: { fill: "bg-low text-on-low", tint: "bg-low-tint text-low" },
  finished: { fill: "bg-finished text-on-finished", tint: "bg-finished-tint text-finished" },
};
```

  e aggiorna il commento sopra: «finito» non è più `ink` ma il rosso di `--color-finished`, l'unico colore di quello stato in tutta l'app.
- `frontend/src/features/pantry/expiryLabels.ts`: `expired: "bg-expiry text-on-expiry"`.
- `frontend/src/features/recipe-form/RecipeForm.tsx:168`: `"bg-brand text-white"` → `"bg-brand text-on-brand"`.
- `frontend/src/components/AppHeader.tsx`: il velo `bg-ink/40` → `bg-scrim/40` (in scuro `ink` è chiaro, e il velo schiarirebbe la pagina).

Se un test di `StatusChip.test.tsx` o di `CookSheet.test.tsx` controlla le classi di `finished`, aggiornalo ai valori nuovi.

- [ ] **Step 6: Barra di stato, manifesto, favicon e icone PNG**

`frontend/index.html`: sostituisci la riga `<meta name="theme-color" content="#eef1ee" />` con due righe, e tieni il commento sopra:

```html
    <meta name="theme-color" content="#f1f4f2" media="(prefers-color-scheme: light)" />
    <meta name="theme-color" content="#0e1210" media="(prefers-color-scheme: dark)" />
```

`frontend/vite.config.ts`: `background_color` e `theme_color` → `"#f1f4f2"` (il manifesto ha un colore solo; la barra di stato la governano i due `meta`).

`frontend/public/favicon.svg`: `fill="#14804f"` → `fill="#0f7a4a"`.

`frontend/scripts/render-icons.mjs`:

```js
// Rigenera le icone PNG della PWA dal favicon SVG, così il verde del marchio è uno
// solo. Si lancia a mano quando cambia il marchio: `node scripts/render-icons.mjs`.
// Usa il Chromium di Playwright, che il progetto ha già: nessuna dipendenza nuova.
import { readFileSync } from "node:fs";
import { chromium } from "@playwright/test";

const svg = readFileSync(new URL("../public/favicon.svg", import.meta.url), "utf8");
const browser = await chromium.launch();
for (const size of [192, 512]) {
  const page = await browser.newPage({ viewport: { width: size, height: size } });
  await page.setContent(
    `<html><body style="margin:0">${svg.replace(/width="512" height="512"/, `width="${size}" height="${size}"`)}</body></html>`
  );
  await page.screenshot({
    path: new URL(`../public/icon-${size}.png`, import.meta.url).pathname,
    omitBackground: true,
  });
  await page.close();
}
await browser.close();
```

Run: `cd frontend && node scripts/render-icons.mjs && file public/icon-192.png public/icon-512.png`
Expected: `PNG image data, 192 x 192` e `512 x 512`. Aprile con il Read tool per guardarle: un cesto bianco su un quadrato verde arrotondato.

- [ ] **Step 7: Il primo test di `style.spec.ts` legge il token, non un numero**

In `frontend/e2e/style.spec.ts`, il test «i token del colore arrivano davvero alla pagina» diventa:

```ts
test("i token del colore arrivano davvero alla pagina", async ({ page }) => {
  // se il blocco @theme non venisse compilato, il fondo resterebbe il bianco di
  // default e tutto il resto sarebbe da rifare
  await expect(page.locator("body")).toHaveCSS("background-color", tokenDelTema("page"));
});
```

- [ ] **Step 8: Controlli**

Run: `cd frontend && npx vitest run && npm run lint && npm run typecheck && npm run build`
Expected: tutto verde.

Run: `cd frontend && grep -rn "emerald\|neutral-\|text-white\|bg-white\|bg-black" src --include=*.tsx --include=*.ts | grep -v "\.test\."`
Expected: solo `src/features/stocking/BarcodeScanner.tsx` (`bg-black`).

- [ ] **Step 9: Commit**

```bash
git add frontend/src/index.css frontend/src/theme.test.ts frontend/src/components/ui/buttonClasses.ts frontend/src/features/pantry/statusLabels.ts frontend/src/features/pantry/expiryLabels.ts frontend/src/features/recipe-form/RecipeForm.tsx frontend/src/components/AppHeader.tsx frontend/index.html frontend/vite.config.ts frontend/public frontend/scripts/render-icons.mjs frontend/e2e/style.spec.ts
git commit -m "ridisegno: i token del colore, chiari e scuri, e il testo sui fondi pieni"
```

---

### Task 2: Il carattere, le icone e i reparti

**Files:**
- Modify: `frontend/package.json` (con `npm install`), `frontend/src/main.tsx`, `frontend/src/index.css`
- Create: `frontend/src/components/ui/icons.ts`, `frontend/src/components/ui/departments.ts`, `frontend/src/components/ui/departments.test.ts`

**Interfaces:**
- Consumes: le classi `bg-dept-*` / `text-dept-*-ink` del Task 1.
- Produces:
  - `icons.ts`: `export type IconComponent`, e un'esportazione per ogni icona della spec §3.3 con il nome di Tabler (`IconMenu2`, `IconChevronLeft`, `IconX`, `IconSearch`, `IconPlus`, `IconArrowBackUp`, `IconRefresh`, `IconBasketCheck`, `IconClearAll`, `IconBarcode`, `IconListSearch`, `IconScale`, `IconPencilPlus`, `IconReplace`, `IconCalendarPlus`, `IconPackageImport`, `IconShoppingCartPlus`, `IconCalendarEvent`, `IconAdjustmentsHorizontal`, `IconSparkles`, `IconLink`, `IconChefHat`, `IconCircleCheck`, `IconPencil`, `IconTrash`, `IconRestore`, `IconExternalLink`, `IconCursorText`, `IconCategory`, `IconArrowsTransferDown`, `IconArrowsJoin2`, `IconBarcodeOff`, `IconListCheck`, `IconBox`, `IconToolsKitchen2`, `IconAlertCircle`, `IconEye`, `IconEyeOff`, `IconMinus`) più quelle dei reparti.
  - `departments.ts`: `export type DepartmentTint = "peach" | "pink" | "blue" | "sand" | "slate"`, `export const TINT_CLASSES: Record<DepartmentTint, string>`, `export function departmentStyle(category: string | null): { icon: IconComponent; tint: DepartmentTint }`.

- [ ] **Step 1: Misura il pacchetto di oggi, poi installa le due dipendenze**

Run: `cd frontend && npm run build && du -sb dist/assets/*.js | sort -n | tail -3`
Annota le dimensioni nel rapporto: allo Step 8 si confrontano (spec §7: una libreria di icone importata male pesa tutta).

Run: `cd frontend && npm install @tabler/icons-react@^3.48.0 @fontsource-variable/inter@^5.3.0`
Expected: `package.json` e `package-lock.json` le portano in `dependencies`.

- [ ] **Step 2: Scrivi il test dei reparti, che fallisce**

`frontend/src/components/ui/departments.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { FOOD_CATEGORIES, NON_FOOD_CATEGORIES } from "../../domain/categories";
import { departmentStyle, TINT_CLASSES } from "./departments";
import { IconPackage } from "./icons";

describe("departmentStyle", () => {
  // come test_frontend_categories.py per l'elenco: un reparto nuovo senza icona non
  // deve arrivare a video con il segnaposto senza che nessuno lo abbia deciso
  it.each([...FOOD_CATEGORIES, ...NON_FOOD_CATEGORIES])("«%s» ha la sua icona e una tinta", (category) => {
    const style = departmentStyle(category);
    expect(Object.keys(TINT_CLASSES)).toContain(style.tint);
    if (category !== "altro") expect(style.icon).not.toBe(IconPackage);
  });

  it("senza reparto, o con uno sconosciuto, usa la scatola in ardesia", () => {
    expect(departmentStyle(null)).toEqual({ icon: IconPackage, tint: "slate" });
    expect(departmentStyle("inventato")).toEqual({ icon: IconPackage, tint: "slate" });
  });

  it("i non alimentari stanno nell'ardesia, lontani dalle tinte del cibo", () => {
    for (const category of NON_FOOD_CATEGORIES) expect(departmentStyle(category).tint).toBe("slate");
  });
});
```

- [ ] **Step 3: Verifica che fallisca**

Run: `cd frontend && npx vitest run src/components/ui/departments.test.ts`
Expected: FAIL, `Cannot find module './departments'`.

- [ ] **Step 4: Scrivi `icons.ts`**

```ts
// L'unico punto da cui l'app prende le icone. Due ragioni: `@tabler/icons-react`
// importato icona per icona pesa solo quel che si usa, e un import sbagliato in un
// posto solo si vede; e la tavola delle azioni della spec T3 §3.3 — quale icona vuol
// dire cosa — resta leggibile qui, invece di spargersi per le schermate.
import type { ComponentType } from "react";

export type IconComponent = ComponentType<{
  size?: number | string;
  stroke?: number | string;
  className?: string;
  "aria-hidden"?: boolean | "true" | "false";
}>;

// ovunque
export {
  IconMenu2,
  IconChevronLeft,
  IconX,
  IconSearch,
  IconPlus,
  IconMinus,
  IconArrowBackUp,
  IconRefresh,
  IconAlertCircle,
  IconEye,
  IconEyeOff,
} from "@tabler/icons-react";
// barra delle schede
export { IconListCheck, IconBox, IconToolsKitchen2 } from "@tabler/icons-react";
// lista e sistemazione
export {
  IconBasketCheck,
  IconClearAll,
  IconBarcode,
  IconListSearch,
  IconScale,
  IconPencilPlus,
  IconReplace,
  IconCalendarPlus,
  IconPackageImport,
} from "@tabler/icons-react";
// dispensa. Il carrello con il + vuol dire «va in lista» ovunque compaia
export { IconShoppingCartPlus, IconCalendarEvent } from "@tabler/icons-react";
// ricette
export {
  IconAdjustmentsHorizontal,
  IconSparkles,
  IconLink,
  IconChefHat,
  IconCircleCheck,
  IconPencil,
  IconTrash,
  IconRestore,
  IconExternalLink,
} from "@tabler/icons-react";
// anagrafica
export {
  IconCursorText,
  IconCategory,
  IconArrowsTransferDown,
  IconArrowsJoin2,
  IconBarcodeOff,
} from "@tabler/icons-react";
// reparti
export {
  IconCarrot,
  IconApple,
  IconMeat,
  IconFish,
  IconCheese,
  IconWheat,
  IconSeedling,
  IconBottle,
  IconPepper,
  IconGlassFull,
  IconCookie,
  IconPackage,
  IconSpray,
  IconBath,
} from "@tabler/icons-react";
```

- [ ] **Step 5: Scrivi `departments.ts`**

```ts
import {
  IconApple,
  IconBath,
  IconBottle,
  IconCarrot,
  IconCheese,
  IconCookie,
  IconFish,
  IconGlassFull,
  IconMeat,
  IconPackage,
  IconPepper,
  IconSeedling,
  IconSpray,
  IconWheat,
  type IconComponent,
} from "./icons";

export type DepartmentTint = "peach" | "pink" | "blue" | "sand" | "slate";

// Le classi per intero, non costruite con `bg-dept-${tint}`: Tailwind trova le classi
// leggendo il sorgente, e una classe composta a runtime non la genera mai.
export const TINT_CLASSES: Record<DepartmentTint, string> = {
  peach: "bg-dept-peach text-dept-peach-ink",
  pink: "bg-dept-pink text-dept-pink-ink",
  blue: "bg-dept-blue text-dept-blue-ink",
  sand: "bg-dept-sand text-dept-sand-ink",
  slate: "bg-dept-slate text-dept-slate-ink",
};

// Spec T3 §3.3. Cinque tinte per famiglia, non quattordici colori: quattordici non si
// imparano, e finirebbero addosso ai colori degli stati.
const DEPARTMENTS: Record<string, { icon: IconComponent; tint: DepartmentTint }> = {
  verdura: { icon: IconCarrot, tint: "peach" },
  frutta: { icon: IconApple, tint: "peach" },
  carne: { icon: IconMeat, tint: "pink" },
  dolci: { icon: IconCookie, tint: "pink" },
  pesce: { icon: IconFish, tint: "blue" },
  latticini: { icon: IconCheese, tint: "blue" },
  bevande: { icon: IconGlassFull, tint: "blue" },
  cereali: { icon: IconWheat, tint: "sand" },
  // Tabler non ha un fagiolo: il germoglio è il ripiego più vicino (spec §3.3)
  legumi: { icon: IconSeedling, tint: "sand" },
  condimenti: { icon: IconBottle, tint: "sand" },
  spezie: { icon: IconPepper, tint: "sand" },
  altro: { icon: IconPackage, tint: "slate" },
  casa: { icon: IconSpray, tint: "slate" },
  igiene: { icon: IconBath, tint: "slate" },
};

const UNKNOWN = { icon: IconPackage, tint: "slate" as const };

/** Icona e tinta di un reparto. `null` è «Senza reparto», la sezione delle voci
 * libere della lista: stessa veste di «altro», perché è lo stesso non-sapere. */
export function departmentStyle(category: string | null): { icon: IconComponent; tint: DepartmentTint } {
  return (category && DEPARTMENTS[category]) || UNKNOWN;
}
```

- [ ] **Step 6: Verifica che il test passi**

Run: `cd frontend && npx vitest run src/components/ui/departments.test.ts`
Expected: PASS.

- [ ] **Step 7: Il carattere**

`frontend/src/main.tsx`: in cima agli import, prima di `./index.css`:

```ts
// Inter servito dall'app e non da Google: la PWA deve aprirsi anche offline, e un
// carattere preso da un terzo a ogni avvio è una chiamata che nessuno ha chiesto
import "@fontsource-variable/inter";
```

`frontend/src/index.css`, dentro `@theme`, dopo `--radius-card`:

```css
  --font-sans: "Inter Variable", ui-sans-serif, system-ui, sans-serif;
```

- [ ] **Step 8: Controlli**

Run: `cd frontend && npx vitest run && npm run lint && npm run typecheck && npm run build`
Expected: verde. Nella build, `dist/assets/` contiene i file `inter-*.woff2`.

Run: `cd frontend && du -sb dist/assets/*.js | sort -n | tail -3`
Expected: il JavaScript cresce di poche decine di kB al più (le icone usate più `react` di Tabler). Se cresce di centinaia di kB, un import prende tutta la libreria: trovalo e correggilo.

Run: `cd frontend && grep -rln "@tabler/icons-react" src | grep -v "components/ui/icons.ts"`
Expected: nessuna riga.

- [ ] **Step 9: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/main.tsx frontend/src/index.css frontend/src/components/ui/icons.ts frontend/src/components/ui/departments.ts frontend/src/components/ui/departments.test.ts
git commit -m "ridisegno: Inter servito dall'app, le icone Tabler da un punto solo, e i reparti"
```

---

### Task 3: Il cesto e la barra delle schede

**Files:**
- Create: `frontend/src/components/ui/BrandMark.tsx`
- Modify: `frontend/src/components/AppHeader.tsx`, `frontend/src/features/auth/LoginScreen.tsx:41-49`, `frontend/src/components/TabBar.tsx`
- Test: `frontend/src/components/TabBar.test.tsx`, `frontend/src/components/AppHeader.test.tsx`

**Interfaces:**
- Consumes: `IconMenu2`, `IconX`, `IconListCheck`, `IconBox`, `IconToolsKitchen2` da `icons.ts` (Task 2).
- Produces: `BrandMark({ className }: { className?: string })`.

- [ ] **Step 1: Scrivi i test che falliscono**

In `frontend/src/components/TabBar.test.tsx` aggiungi (usa lo stesso modo di montare con un router che il file usa già; se monta con `MemoryRouter`, passa `initialEntries`):

```tsx
it("su /sistema segna «Lista»: sistemare la spesa è una parte della lista", () => {
  render(
    <MemoryRouter initialEntries={["/sistema"]}>
      <TabBar />
    </MemoryRouter>
  );
  expect(screen.getByRole("link", { name: "Lista" })).toHaveAttribute("aria-current", "page");
  expect(screen.getByRole("link", { name: "Dispensa" })).not.toHaveAttribute("aria-current");
});
```

In `frontend/src/components/AppHeader.test.tsx` aggiungi:

```tsx
it("porta il cesto, lo stesso segno dell'icona sul telefono", () => {
  renderHeader(); // l'aiutante che il file usa già per montare l'intestazione
  expect(screen.getByRole("banner").querySelector("svg[data-mark='cesto']")).not.toBeNull();
});
```

Se `AppHeader.test.tsx` non ha un aiutante `renderHeader`, monta come fanno i test vicini.

- [ ] **Step 2: Verifica che falliscano**

Run: `cd frontend && npx vitest run src/components/TabBar.test.tsx src/components/AppHeader.test.tsx`
Expected: FAIL. Su `/sistema` nessun link ha `aria-current`, e nell'intestazione c'è la pentola.

- [ ] **Step 3: `BrandMark`**

`frontend/src/components/ui/BrandMark.tsx`:

```tsx
// Il cesto: il marchio dell'app, uno solo (spec T3 §3.4). È lo stesso disegno della
// favicon e delle icone della PWA, così chi apre l'app ritrova il segno che ha toccato
// sulla schermata iniziale. Resta un SVG disegnato a mano: la libreria di icone serve
// alle azioni, non al marchio.
export function BrandMark({ className = "size-7" }: { className?: string }) {
  return (
    <svg viewBox="0 0 512 512" aria-hidden="true" data-mark="cesto" className={className}>
      <rect width="512" height="512" rx="112" fill="var(--color-brand)" />
      <g fill="none" stroke="var(--color-on-brand)" strokeLinecap="round" strokeLinejoin="round">
        <path d="M148 218h216l-42 142H190z" strokeWidth="26" />
        <path d="M194 218a62 62 0 0 1 124 0" strokeWidth="26" />
        <path d="M219 254l9 76M293 254l-9 76" strokeWidth="22" />
      </g>
    </svg>
  );
}
```

- [ ] **Step 4: Intestazione e accesso**

`frontend/src/components/AppHeader.tsx`:
- togli le funzioni `Mark`, `MenuIcon` e `CloseIcon` e il commento che dice che una libreria di icone «peserebbe sul primo avvio»;
- al posto di `<Mark />` metti `<BrandMark className="size-7" />`;
- al posto di `<MenuIcon />` metti `<IconMenu2 aria-hidden="true" className="size-6" stroke={1.8} />`, e al posto di `<CloseIcon />` metti `<IconX aria-hidden="true" className="size-5" stroke={2} />`, importati da `./ui/icons`.

`frontend/src/features/auth/LoginScreen.tsx`: sostituisci l'`<svg>` del cesto (righe 41–49) con `<BrandMark className="inline-block size-16" />`, e tieni il commento sopra.

- [ ] **Step 5: La barra delle schede**

`frontend/src/components/TabBar.tsx`: togli `ICONS` e il commento sulla libreria; ogni scheda porta la sua icona e i percorsi che la accendono:

```tsx
import { NavLink, useLocation } from "react-router-dom";
import { IconBox, IconListCheck, IconToolsKitchen2, type IconComponent } from "./ui/icons";

// `also`: i percorsi che stanno dentro una scheda senza cominciare col suo indirizzo.
// «Sistema la spesa» è una parte della lista (dal giro di T3: su /sistema la barra
// non segnava niente, e non si capiva dove si era).
const TABS: { to: string; label: string; icon: IconComponent; also?: string[] }[] = [
  { to: "/lista", label: "Lista", icon: IconListCheck, also: ["/sistema"] },
  { to: "/dispensa", label: "Dispensa", icon: IconBox },
  { to: "/ricette", label: "Ricette", icon: IconToolsKitchen2 },
];

export function TabBar() {
  const { pathname } = useLocation();
  return (
    <nav
      className="fixed inset-x-0 bottom-0 border-t border-line bg-card"
      style={{ paddingBottom: "var(--safe-bottom)" }}
    >
      {/* la stessa larghezza massima del contenuto: su uno schermo largo una barra
          che attraversa tutto mentre l'app sta in mezzo sembra di un'altra pagina */}
      <div className="mx-auto grid max-w-md grid-cols-3">
        {TABS.map((tab) => {
          const Icon = tab.icon;
          const alsoActive = tab.also?.some((p) => pathname === p || pathname.startsWith(`${p}/`)) ?? false;
          return (
            <NavLink
              key={tab.to}
              to={tab.to}
              // `aria-current` lo mette NavLink quando l'indirizzo combacia; per i percorsi
              // di `also` va messo a mano, o lo screen reader non saprebbe dove si è
              aria-current={alsoActive ? "page" : undefined}
              className={({ isActive }) =>
                `flex min-h-14 flex-col items-center justify-center gap-1 text-xs ${
                  isActive || alsoActive ? "font-semibold text-brand" : "text-ink-faint"
                }`
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={`rounded-full px-3 py-0.5 transition-colors ${
                      isActive || alsoActive ? "bg-brand-tint" : ""
                    }`}
                  >
                    {/* `aria-hidden`: il nome del link resta la parola, o chi usa uno
                        screen reader sentirebbe due volte la stessa scheda */}
                    <Icon aria-hidden="true" className="size-6" stroke={1.6} />
                  </span>
                  {tab.label}
                </>
              )}
            </NavLink>
          );
        })}
      </div>
    </nav>
  );
}
```

- [ ] **Step 6: Verifica che i test passino**

Run: `cd frontend && npx vitest run src/components src/features/auth`
Expected: PASS. Se un test di `TabBar.test.tsx` contava i `path` degli SVG disegnati a mano, riscrivilo sul nome del link e su `aria-current`.

- [ ] **Step 7: Controlli e commit**

Run: `cd frontend && npx vitest run && npm run lint && npm run typecheck`
Expected: verde.

```bash
git add frontend/src/components/ui/BrandMark.tsx frontend/src/components/AppHeader.tsx frontend/src/components/AppHeader.test.tsx frontend/src/features/auth/LoginScreen.tsx frontend/src/components/TabBar.tsx frontend/src/components/TabBar.test.tsx
git commit -m "ridisegno: il cesto anche nell'intestazione, e la barra delle schede con le icone"
```

---

### Task 4: `Button` e `IconToolbar`

**Files:**
- Modify: `frontend/src/components/ui/buttonClasses.ts`
- Create: `frontend/src/components/ui/Button.tsx`, `frontend/src/components/ui/IconToolbar.tsx`, `frontend/src/components/ui/Button.test.tsx`

**Interfaces:**
- Consumes: `IconComponent` (Task 2), `buttonClasses` (Task 1).
- Produces:
  - `buttonClasses(variant?: ButtonVariant, shape?: ButtonShape): string`, con `export type ButtonVariant = "primary" | "secondary" | "ghost" | "danger" | "warn"` ed `export type ButtonShape = "pill" | "block" | "icon"`;
  - `Button(props: ButtonProps)`, dove `ButtonProps` è l'unione di `{ children: ReactNode; icon?: IconComponent; label?: never }` e `{ icon: IconComponent; label: string; children?: never }`, più `variant`, `shape`, `type`, `onClick`, `disabled`, `className`, `aria-describedby`;
  - `IconToolbar({ label, children }: { label: string; children: ReactNode })`.

- [ ] **Step 1: Scrivi il test che fallisce**

`frontend/src/components/ui/Button.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { Button } from "./Button";
import { IconToolbar } from "./IconToolbar";
import { IconPencil, IconTrash } from "./icons";

describe("Button", () => {
  it("con il testo, il nome è il testo e l'icona non si legge", () => {
    render(<Button icon={IconPencil}>Modifica</Button>);
    const button = screen.getByRole("button", { name: "Modifica" });
    expect(button.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("di sola icona, il nome è l'etichetta completa", () => {
    const onClick = vi.fn();
    render(<Button icon={IconTrash} label="Elimina la ricetta" onClick={onClick} />);
    fireEvent.click(screen.getByRole("button", { name: "Elimina la ricetta" }));
    expect(onClick).toHaveBeenCalledOnce();
  });

  it("di sola icona è un quadrato da pollice", () => {
    render(<Button icon={IconTrash} label="Elimina" />);
    expect(screen.getByRole("button", { name: "Elimina" }).className).toContain("size-11");
  });

  it("è type=button se non si dice altro: dentro un modulo non deve inviarlo", () => {
    render(<Button>Annulla</Button>);
    expect(screen.getByRole("button", { name: "Annulla" })).toHaveAttribute("type", "button");
  });
});

describe("IconToolbar", () => {
  it("raggruppa i pulsanti sotto un nome", () => {
    render(
      <IconToolbar label="Azioni sulla ricetta">
        <Button icon={IconPencil} label="Modifica" />
        <Button icon={IconTrash} label="Elimina" />
      </IconToolbar>
    );
    const toolbar = screen.getByRole("toolbar", { name: "Azioni sulla ricetta" });
    expect(toolbar.querySelectorAll("button")).toHaveLength(2);
  });
});
```

- [ ] **Step 2: Verifica che fallisca**

Run: `cd frontend && npx vitest run src/components/ui/Button.test.tsx`
Expected: FAIL, `Cannot find module './Button'`.

- [ ] **Step 3: La forma `icon` in `buttonClasses`**

In `frontend/src/components/ui/buttonClasses.ts`: esporta i tipi (`export type ButtonVariant = …`, `export type ButtonShape = "pill" | "block" | "icon"`), e aggiungi a `SHAPES`:

```ts
  // di sola icona (spec T3 §2): un quadrato da 44px, il bersaglio minimo di casa
  icon: "size-11 shrink-0 rounded-full",
```

- [ ] **Step 4: `Button` e `IconToolbar`**

`frontend/src/components/ui/Button.tsx`:

```tsx
import type { ReactNode } from "react";
import { buttonClasses, type ButtonShape, type ButtonVariant } from "./buttonClasses";
import type { IconComponent } from "./icons";

type Common = {
  variant?: ButtonVariant;
  shape?: ButtonShape;
  type?: "button" | "submit";
  onClick?: () => void;
  disabled?: boolean;
  className?: string;
  "aria-describedby"?: string;
};

// Le due forme della regola delle icone (spec T3 §2), e nessuna terza: un pulsante di
// sola icona senza `label` non compila, perché un pulsante muto per uno screen reader
// è un pulsante che non c'è.
type WithText = Common & { children: ReactNode; icon?: IconComponent; label?: never };
type IconOnly = Common & { icon: IconComponent; label: string; children?: never };

export function Button(props: WithText | IconOnly) {
  const { variant = "secondary", type = "button", onClick, disabled, className = "" } = props;
  const Icon = props.icon;
  const iconOnly = props.label !== undefined;
  const shape = props.shape ?? (iconOnly ? "icon" : "pill");
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      aria-label={iconOnly ? props.label : undefined}
      aria-describedby={props["aria-describedby"]}
      className={`${buttonClasses(variant, shape)} ${className}`}
    >
      {Icon && <Icon aria-hidden="true" className={iconOnly ? "size-5" : "size-[1.1em]"} stroke={1.8} />}
      {props.children}
    </button>
  );
}
```

`frontend/src/components/ui/IconToolbar.tsx`:

```tsx
import type { ReactNode } from "react";

/** Più pulsanti in gruppo: la metà «solo icone» della regola (spec T3 §2). Il gruppo
 * ha un nome suo, così chi usa uno screen reader sa di che cosa sono le icone prima
 * di sentirle una per una. */
export function IconToolbar({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div role="toolbar" aria-label={label} className="flex items-center gap-1">
      {children}
    </div>
  );
}
```

- [ ] **Step 5: Verifica che passi, e i controlli**

Run: `cd frontend && npx vitest run src/components/ui/Button.test.tsx && npm run lint && npm run typecheck`
Expected: PASS e verde.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ui/buttonClasses.ts frontend/src/components/ui/Button.tsx frontend/src/components/ui/IconToolbar.tsx frontend/src/components/ui/Button.test.tsx
git commit -m "ridisegno: Button con le due forme della regola delle icone, e IconToolbar"
```

---

### Task 5: `ActionBar` e `Section`

**Files:**
- Create: `frontend/src/components/ui/ActionBar.tsx`, `frontend/src/components/ui/Section.tsx`, `frontend/src/components/ui/ActionBar.test.tsx`, `frontend/src/components/ui/Section.test.tsx`

**Interfaces:**
- Consumes: `Button` (Task 4), `IconPlus`, `IconSearch` e `IconComponent` (Task 2), `departmentStyle` e `TINT_CLASSES` (Task 2).
- Produces:
  - `ActionBar({ inputLabel, placeholder, addLabel, value, onChange, onAdd, leadingIcon? }: { inputLabel: string; placeholder: string; addLabel: string; value: string; onChange: (value: string) => void; onAdd: (text: string) => void; leadingIcon?: IconComponent })`;
  - `Section({ category, title, count, children }: { category: string | null; title?: string; count?: number; children: ReactNode })`.

- [ ] **Step 1: Scrivi i test che falliscono**

`frontend/src/components/ui/ActionBar.test.tsx`:

```tsx
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ActionBar } from "./ActionBar";

function Harness({ onAdd }: { onAdd: (text: string) => void }) {
  const [value, setValue] = useState("");
  return (
    <ActionBar
      inputLabel="Cerca o aggiungi in dispensa"
      placeholder="Cerca o aggiungi"
      addLabel="Aggiungi in dispensa"
      value={value}
      onChange={setValue}
      onAdd={onAdd}
    />
  );
}

describe("ActionBar", () => {
  it("il + e l'Invio aggiungono il testo scritto, senza spazi attorno", () => {
    const onAdd = vi.fn();
    render(<Harness onAdd={onAdd} />);
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "  latte " } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    expect(onAdd).toHaveBeenCalledWith("latte");
  });

  it("a campo vuoto il + non manda niente", () => {
    const onAdd = vi.fn();
    render(<Harness onAdd={onAdd} />);
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    expect(onAdd).not.toHaveBeenCalled();
  });

  it("il campo resta a 16px: sotto, iOS ingrandisce la pagina", () => {
    render(<Harness onAdd={() => {}} />);
    expect(screen.getByLabelText("Cerca o aggiungi in dispensa").className).toContain("text-base");
  });
});
```

`frontend/src/components/ui/Section.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Section } from "./Section";

describe("Section", () => {
  it("è una regione col nome del reparto, e dice quante righe porta", () => {
    render(
      <Section category="latticini" count={3}>
        <p>Latte</p>
      </Section>
    );
    const region = screen.getByRole("region", { name: "Latticini" });
    expect(region).toHaveTextContent("3");
    expect(region).toHaveTextContent("Latte");
  });

  it("il quadratino porta la tinta del reparto", () => {
    render(<Section category="latticini">x</Section>);
    const badge = screen.getByRole("region", { name: "Latticini" }).querySelector("[data-dept-badge]");
    expect(badge?.className).toContain("bg-dept-blue");
  });

  it("senza reparto si chiama «Senza reparto», e un titolo dato vince", () => {
    render(
      <>
        <Section category={null}>a</Section>
        <Section category="altro" title="Da abbinare">b</Section>
      </>
    );
    expect(screen.getByRole("region", { name: "Senza reparto" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Da abbinare" })).toBeInTheDocument();
  });

  it("dentro la sezione le righe non hanno linee di separazione", () => {
    render(<Section category="frutta">x</Section>);
    const region = screen.getByRole("region", { name: "Frutta" });
    expect(region.innerHTML).not.toContain("divide-");
  });
});
```

- [ ] **Step 2: Verifica che falliscano**

Run: `cd frontend && npx vitest run src/components/ui/ActionBar.test.tsx src/components/ui/Section.test.tsx`
Expected: FAIL, moduli mancanti.

- [ ] **Step 3: `ActionBar`**

```tsx
import { useId, type FormEvent } from "react";
import { Button } from "./Button";
import { IconPlus, type IconComponent } from "./icons";

/** La barra in cima a Lista e Dispensa: il campo e il + accanto (spec T3 §2). Il
 * segnaposto del campo fa da etichetta visiva al +, che è di sola icona e porta il
 * suo nome completo per chi non vede. Il valore lo tiene chi la usa: in Dispensa lo
 * stesso testo filtra le righe mentre si scrive. */
export function ActionBar({
  inputLabel,
  placeholder,
  addLabel,
  value,
  onChange,
  onAdd,
  leadingIcon: Leading,
}: {
  inputLabel: string;
  placeholder: string;
  addLabel: string;
  value: string;
  onChange: (value: string) => void;
  onAdd: (text: string) => void;
  leadingIcon?: IconComponent;
}) {
  const id = useId();
  function submit(event: FormEvent) {
    event.preventDefault();
    const text = value.trim();
    if (text) onAdd(text);
  }
  return (
    <form onSubmit={submit} className="flex items-center gap-2">
      <div className="relative min-w-0 flex-1">
        {Leading && (
          <Leading
            aria-hidden="true"
            className="pointer-events-none absolute top-1/2 left-3 size-5 -translate-y-1/2 text-ink-faint"
          />
        )}
        <input
          id={id}
          aria-label={inputLabel}
          value={value}
          onChange={(e) => onChange(e.target.value)}
          placeholder={placeholder}
          className={`text-base ${Leading ? "pl-10" : ""}`}
        />
      </div>
      <Button type="submit" variant="primary" icon={IconPlus} label={addLabel} className="rounded-[10px]" />
    </form>
  );
}
```

- [ ] **Step 4: `Section`**

```tsx
import { useId, type ReactNode } from "react";
import { departmentStyle, TINT_CLASSES } from "./departments";

function capitalize(text: string): string {
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** Un reparto: la scheda bianca con il quadratino colorato, il nome e il conteggio
 * (spec T3 §2, presa dalla direzione «Vivace»). Dentro, le righe non hanno linee fra
 * loro — deciso da Mattia: lo spazio basta a separarle, e la sezione resta un blocco
 * solo. Chi la usa passa righe che portano il proprio spazio verticale. */
export function Section({
  category,
  title,
  count,
  children,
}: {
  category: string | null;
  title?: string;
  count?: number;
  children: ReactNode;
}) {
  const headingId = useId();
  const { icon: Icon, tint } = departmentStyle(category);
  const name = title ?? (category ? capitalize(category) : "Senza reparto");
  return (
    <section aria-labelledby={headingId} className="overflow-hidden rounded-2xl bg-card">
      <div className="flex items-center gap-2.5 px-3 pt-3 pb-1.5">
        <span
          data-dept-badge
          aria-hidden="true"
          className={`flex size-7 shrink-0 items-center justify-center rounded-lg ${TINT_CLASSES[tint]}`}
        >
          <Icon className="size-4" stroke={1.8} />
        </span>
        <h2 id={headingId} className="flex-1 text-sm font-semibold">
          {name}
        </h2>
        {count !== undefined && <span className="text-xs text-ink-faint">{count}</span>}
      </div>
      <div className="px-3 pb-2">{children}</div>
    </section>
  );
}
```

- [ ] **Step 5: Verifica che passino, e i controlli**

Run: `cd frontend && npx vitest run src/components/ui && npm run lint && npm run typecheck`
Expected: PASS e verde.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ui/ActionBar.tsx frontend/src/components/ui/Section.tsx frontend/src/components/ui/ActionBar.test.tsx frontend/src/components/ui/Section.test.tsx
git commit -m "ridisegno: la barra con il + e la sezione di reparto"
```

---

### Task 6: `StockGauge`, `StatusDot` e `Chip`

**Files:**
- Create: `frontend/src/components/ui/StockGauge.tsx`, `frontend/src/components/ui/StatusDot.tsx`, `frontend/src/components/ui/Chip.tsx`, `frontend/src/components/ui/StockGauge.test.tsx`, `frontend/src/components/ui/StatusDot.test.tsx`
- Modify: `frontend/src/components/ui/StatusChip.tsx`, `frontend/src/components/ui/ExpiryChip.tsx`

**Interfaces:**
- Consumes: `STATUS_LABELS` e `STATUS_TONE` (`features/pantry/statusLabels.ts`), `EXPIRY_TONE` e `formatExpiry` (`features/pantry/expiryLabels.ts`), i tipi `PantryStatus` e `Availability` (`domain/types.ts`).
- Produces:
  - `StockGauge({ status, onChange, itemName, disabled? }: { status: PantryStatus; onChange: (status: PantryStatus) => void; itemName: string; disabled?: boolean })`;
  - `StatusDot({ availability }: { availability: Availability })`;
  - `Chip({ tone, children }: { tone: string; children: ReactNode })`.

- [ ] **Step 1: Scrivi i test che falliscono**

`frontend/src/components/ui/StockGauge.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { StockGauge } from "./StockGauge";

describe("StockGauge", () => {
  it("è un gruppo di tre scelte con le parole degli stati", () => {
    render(<StockGauge status="available" onChange={() => {}} itemName="Latte" />);
    const group = screen.getByRole("radiogroup", { name: "Quanto resta di Latte" });
    const names = [...group.querySelectorAll("[role=radio]")].map((r) => r.getAttribute("aria-label"));
    expect(names).toEqual(["Finito", "Quasi finito", "Disponibile"]);
    expect(screen.getByRole("radio", { name: "Disponibile" })).toHaveAttribute("aria-checked", "true");
  });

  it.each([
    ["Finito", "finished"],
    ["Quasi finito", "low"],
    ["Disponibile", "available"],
  ] as const)("toccare «%s» manda %s", (name, status) => {
    const onChange = vi.fn();
    render(<StockGauge status={status === "available" ? "low" : "available"} onChange={onChange} itemName="Latte" />);
    fireEvent.click(screen.getByRole("radio", { name }));
    expect(onChange).toHaveBeenCalledWith(status);
  });

  it("toccare lo stato che c'è già non manda niente", () => {
    const onChange = vi.fn();
    render(<StockGauge status="low" onChange={onChange} itemName="Latte" />);
    fireEvent.click(screen.getByRole("radio", { name: "Quasi finito" }));
    expect(onChange).not.toHaveBeenCalled();
  });

  it("il livello arriva fino alla tacca toccata: quasi finito accende due tacche", () => {
    render(<StockGauge status="low" onChange={() => {}} itemName="Latte" />);
    const lit = screen.getByRole("radiogroup").querySelectorAll("[data-lit=true]");
    expect(lit).toHaveLength(2);
  });

  it("le frecce spostano lo stato di una tacca, e il fuoco lo segue", () => {
    const onChange = vi.fn();
    render(<StockGauge status="low" onChange={onChange} itemName="Latte" />);
    const current = screen.getByRole("radio", { name: "Quasi finito" });
    expect(current).toHaveAttribute("tabindex", "0");
    expect(screen.getByRole("radio", { name: "Finito" })).toHaveAttribute("tabindex", "-1");
    fireEvent.keyDown(current, { key: "ArrowRight" });
    expect(onChange).toHaveBeenLastCalledWith("available");
    expect(screen.getByRole("radio", { name: "Disponibile" })).toHaveFocus();
    fireEvent.keyDown(current, { key: "ArrowLeft" });
    expect(onChange).toHaveBeenLastCalledWith("finished");
  });

  it("ogni tacca è un bersaglio da 44px", () => {
    render(<StockGauge status="low" onChange={() => {}} itemName="Latte" />);
    for (const radio of screen.getAllByRole("radio")) expect(radio.className).toContain("size-11");
  });
});
```

`frontend/src/components/ui/StatusDot.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusDot } from "./StatusDot";

describe("StatusDot", () => {
  it.each([
    ["available", "c'è", "bg-brand"],
    ["low", "sta finendo", "bg-low"],
    ["missing", "manca", "bg-finished"],
  ] as const)("%s si legge «%s» ed è %s", (availability, words, colour) => {
    render(<StatusDot availability={availability} />);
    const dot = screen.getByRole("img", { name: words });
    expect(dot.className).toContain(colour);
  });
});
```

- [ ] **Step 2: Verifica che falliscano**

Run: `cd frontend && npx vitest run src/components/ui/StockGauge.test.tsx src/components/ui/StatusDot.test.tsx`
Expected: FAIL, moduli mancanti.

- [ ] **Step 3: `StockGauge`**

```tsx
import { useRef, type KeyboardEvent } from "react";
import { STATUS_LABELS } from "../../features/pantry/statusLabels";
import type { PantryStatus } from "../../domain/types";

// Da sinistra a destra, dal meno al più. Il livello arriva fino alla tacca toccata
// (spec T3 §4.4): si tocca dove si vuole che arrivi.
const ORDER: PantryStatus[] = ["finished", "low", "available"];
const LIT: Record<PantryStatus, string> = {
  finished: "bg-finished",
  low: "bg-low",
  available: "bg-brand",
};

/** Le tre tacche: quanto resta di una voce, e il controllo che lo cambia (spec T3
 * §4.4, al posto del cursore). Sono tre pulsanti e non un `range`: un tocco che
 * diventa uno scorrimento il browser non lo trasforma in un clic, quindi scorrere
 * partendo da qui non cambia mai uno stato — il difetto di S13 non ha dove nascere.
 * Ogni tacca è un bersaglio da 44px; il disegno è una barretta. */
export function StockGauge({
  status,
  onChange,
  itemName,
  disabled = false,
}: {
  status: PantryStatus;
  onChange: (status: PantryStatus) => void;
  itemName: string;
  disabled?: boolean;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const level = ORDER.indexOf(status);

  function choose(next: PantryStatus) {
    if (next !== status) onChange(next);
  }

  function onKeyDown(event: KeyboardEvent) {
    const step = { ArrowRight: 1, ArrowUp: 1, ArrowLeft: -1, ArrowDown: -1 }[event.key];
    if (step === undefined) return;
    event.preventDefault();
    const index = Math.min(ORDER.length - 1, Math.max(0, level + step));
    choose(ORDER[index]);
    refs.current[index]?.focus();
  }

  return (
    <div role="radiogroup" aria-label={`Quanto resta di ${itemName}`} className="flex shrink-0">
      {ORDER.map((option, index) => {
        const lit = index <= level;
        return (
          <button
            key={option}
            ref={(el) => {
              refs.current[index] = el;
            }}
            type="button"
            role="radio"
            aria-checked={option === status}
            aria-label={STATUS_LABELS[option]}
            tabIndex={option === status ? 0 : -1}
            disabled={disabled}
            data-lit={lit}
            onClick={() => choose(option)}
            onKeyDown={onKeyDown}
            className="flex size-11 items-center justify-center disabled:opacity-40"
          >
            <span className={`h-1.5 w-4 rounded-full ${lit ? LIT[status] : "bg-line"}`} />
          </button>
        );
      })}
    </div>
  );
}
```

- [ ] **Step 4: `StatusDot` e `Chip`**

`frontend/src/components/ui/StatusDot.tsx`:

```tsx
import type { Availability } from "../../domain/types";

// I colori sono quelli degli stati della dispensa (STATUS_TONE): «manca» è il rosso di
// «finito», perché per una ricetta sono la stessa notizia.
const DOT: Record<Availability, { colour: string; words: string }> = {
  available: { colour: "bg-brand", words: "c'è" },
  low: { colour: "bg-low", words: "sta finendo" },
  missing: { colour: "bg-finished", words: "manca" },
};

/** Il pallino accanto a un ingrediente di ricetta (spec T3 §4.6). Il colore da solo
 * non basta a chi non lo distingue: il pallino ha un nome, letto da chi ascolta. */
export function StatusDot({ availability }: { availability: Availability }) {
  const { colour, words } = DOT[availability];
  return <span role="img" aria-label={words} className={`inline-block size-2 shrink-0 rounded-full ${colour}`} />;
}
```

`frontend/src/components/ui/Chip.tsx`:

```tsx
import type { ReactNode } from "react";

/** La pastiglia: la forma una volta, il colore da chi la usa (un tono di STATUS_TONE o
 * di EXPIRY_TONE). */
export function Chip({ tone, children }: { tone: string; children: ReactNode }) {
  return <span className={`inline-block rounded-full px-2.5 py-1 text-xs font-medium ${tone}`}>{children}</span>;
}
```

In `StatusChip.tsx` e `ExpiryChip.tsx` sostituisci lo `<span className=…>` con `<Chip tone={…}>…</Chip>`, tenendo i commenti. `StatusChip.test.tsx` ed `ExpiryChip.test.tsx` devono passare senza modifiche; se uno controlla l'esatta stringa di classi, aggiornalo.

- [ ] **Step 5: Verifica che passino, e i controlli**

Run: `cd frontend && npx vitest run src/components/ui && npm run lint && npm run typecheck`
Expected: PASS e verde.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ui/StockGauge.tsx frontend/src/components/ui/StatusDot.tsx frontend/src/components/ui/Chip.tsx frontend/src/components/ui/StockGauge.test.tsx frontend/src/components/ui/StatusDot.test.tsx frontend/src/components/ui/StatusChip.tsx frontend/src/components/ui/ExpiryChip.tsx
git commit -m "ridisegno: le tre tacche, il pallino dello stato, e una pastiglia sola"
```

---

### Task 7: L'avviso di conferma unico

**Files:**
- Create: `frontend/src/components/ui/noticeContext.ts`, `frontend/src/components/ui/NoticeProvider.tsx`, `frontend/src/components/ui/NoticeProvider.test.tsx`
- Modify: `frontend/src/index.css` (l'animazione), `frontend/src/App.tsx` (monta il provider)

**Interfaces:**
- Produces:
  - `noticeContext.ts`: `export type NoticeInput = { text: string; action?: { label: string; onClick: () => void } }`, `export const NoticeContext`, `export function useNotice(): (notice: NoticeInput) => void`, `export const NOTICE_MS = 6000`;
  - `NoticeProvider({ children }: { children: ReactNode })`.

- [ ] **Step 1: Scrivi il test che fallisce**

`frontend/src/components/ui/NoticeProvider.test.tsx`:

```tsx
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { NoticeProvider } from "./NoticeProvider";
import { NOTICE_MS, useNotice, type NoticeInput } from "./noticeContext";

function Trigger({ notice }: { notice: NoticeInput }) {
  const show = useNotice();
  return <button onClick={() => show(notice)}>mostra</button>;
}

describe("NoticeProvider", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("mostra l'avviso come stato, e se ne va dopo sei secondi", () => {
    render(
      <NoticeProvider>
        <Trigger notice={{ text: "4 in dispensa · 3 restano in lista" }} />
      </NoticeProvider>
    );
    fireEvent.click(screen.getByText("mostra"));
    expect(screen.getByRole("status")).toHaveTextContent("4 in dispensa · 3 restano in lista");
    act(() => vi.advanceTimersByTime(NOTICE_MS));
    expect(screen.queryByText("4 in dispensa · 3 restano in lista")).toBeNull();
  });

  it("l'azione esegue e chiude l'avviso", () => {
    const undo = vi.fn();
    render(
      <NoticeProvider>
        <Trigger notice={{ text: "Tolto: kiwi", action: { label: "Annulla", onClick: undo } }} />
      </NoticeProvider>
    );
    fireEvent.click(screen.getByText("mostra"));
    fireEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(undo).toHaveBeenCalledOnce();
    expect(screen.queryByText("Tolto: kiwi")).toBeNull();
  });

  it("un avviso nuovo prende il posto del vecchio e riparte da sei secondi", () => {
    function Two() {
      const show = useNotice();
      return (
        <>
          <button onClick={() => show({ text: "primo" })}>uno</button>
          <button onClick={() => show({ text: "secondo" })}>due</button>
        </>
      );
    }
    render(
      <NoticeProvider>
        <Two />
      </NoticeProvider>
    );
    fireEvent.click(screen.getByText("uno"));
    act(() => vi.advanceTimersByTime(NOTICE_MS - 1000));
    fireEvent.click(screen.getByText("due"));
    expect(screen.queryByText("primo")).toBeNull();
    act(() => vi.advanceTimersByTime(NOTICE_MS - 1000));
    expect(screen.getByText("secondo")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1000));
    expect(screen.queryByText("secondo")).toBeNull();
  });
});
```

- [ ] **Step 2: Verifica che fallisca**

Run: `cd frontend && npx vitest run src/components/ui/NoticeProvider.test.tsx`
Expected: FAIL, moduli mancanti.

- [ ] **Step 3: Il contesto**

`frontend/src/components/ui/noticeContext.ts`:

```ts
import { createContext, useContext } from "react";

export type NoticeInput = { text: string; action?: { label: string; onClick: () => void } };

/** Quanto resta a video un avviso. Sei secondi, come la lapide di prima: abbastanza
 * per leggere e toccare «Annulla» con una mano sola. */
export const NOTICE_MS = 6000;

// Il contesto e il suo gancio stanno in un file senza componenti: accanto a
// NoticeProvider romperebbero il fast refresh (la stessa regola di statusLabels.ts).
export const NoticeContext = createContext<(notice: NoticeInput) => void>(() => {});

/** Mostra un avviso di conferma: in basso, sopra la barra delle schede, lo stesso in
 * tutta l'app (spec T3 §3.5, il resto di T4). */
export function useNotice(): (notice: NoticeInput) => void {
  return useContext(NoticeContext);
}
```

- [ ] **Step 4: Il provider**

`frontend/src/components/ui/NoticeProvider.tsx`:

```tsx
import { useCallback, useEffect, useState, type ReactNode } from "react";
import { NOTICE_MS, NoticeContext, type NoticeInput } from "./noticeContext";

/** L'avviso di conferma unico (spec T3 §3.5). Uno alla volta: il nuovo prende il posto
 * del vecchio, perché due avvisi impilati sopra la barra coprirebbero la lista.
 *
 * Il fondo è `ink` e il testo `page`: rovesciato rispetto alla pagina in entrambi i
 * temi, così si stacca da qualunque cosa ci sia sotto senza un'ombra. La barra che si
 * accorcia dice quanto dura (dal giro: «la lapide dura 6 secondi e non lo dice»). */
export function NoticeProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<(NoticeInput & { key: number }) | null>(null);

  const show = useCallback((notice: NoticeInput) => {
    setCurrent({ ...notice, key: Date.now() + Math.random() });
  }, []);

  useEffect(() => {
    if (!current) return;
    const timer = setTimeout(() => setCurrent(null), NOTICE_MS);
    return () => clearTimeout(timer);
  }, [current]);

  return (
    <NoticeContext.Provider value={show}>
      {children}
      <div
        className="pointer-events-none fixed inset-x-0 z-20 mx-auto max-w-md px-3"
        style={{ bottom: "calc(3.5rem + var(--safe-bottom) + 0.5rem)" }}
      >
        {/* la regione `status` c'è sempre, anche vuota: uno screen reader annuncia
            ciò che cambia dentro una regione che conosceva già, non una che nasce */}
        <div role="status">
          {current && (
            <div
              key={current.key}
              className="pointer-events-auto overflow-hidden rounded-xl bg-ink text-page"
            >
              <div className="flex min-h-11 items-center gap-3 px-3 py-2 text-sm">
                <span className="flex-1">{current.text}</span>
                {current.action && (
                  <button
                    type="button"
                    onClick={() => {
                      current.action!.onClick();
                      setCurrent(null);
                    }}
                    className="min-h-11 shrink-0 px-2 font-semibold text-brand-tint"
                  >
                    {current.action.label}
                  </button>
                )}
              </div>
              <div
                aria-hidden="true"
                className="notice-timer h-0.5 origin-left bg-brand-tint"
                style={{ animationDuration: `${NOTICE_MS}ms` }}
              />
            </div>
          )}
        </div>
      </div>
    </NoticeContext.Provider>
  );
}
```

`frontend/src/index.css`, in fondo:

```css
/* La barra dell'avviso di conferma che si accorcia (NoticeProvider). Chi ha chiesto al
   sistema meno movimento la vede ferma: la durata resta la stessa, cambia solo che non
   la si vede scorrere. */
@keyframes notice-shrink {
  from {
    transform: scaleX(1);
  }
  to {
    transform: scaleX(0);
  }
}

.notice-timer {
  animation-name: notice-shrink;
  animation-timing-function: linear;
  animation-fill-mode: forwards;
}

@media (prefers-reduced-motion: reduce) {
  .notice-timer {
    animation: none;
  }
}
```

- [ ] **Step 5: Monta il provider**

In `frontend/src/App.tsx`, dentro `<QueryClientProvider>`, avvolgi `<BrowserRouter>…</BrowserRouter>` in `<NoticeProvider>`, importato da `./components/ui/NoticeProvider`. Nessuna schermata lo usa ancora: le lapidi di dispensa e ricettario passano a lui nelle loro consegne.

- [ ] **Step 6: Verifica che passi, e i controlli**

Run: `cd frontend && npx vitest run && npm run lint && npm run typecheck`
Expected: PASS e verde.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ui/noticeContext.ts frontend/src/components/ui/NoticeProvider.tsx frontend/src/components/ui/NoticeProvider.test.tsx frontend/src/index.css frontend/src/App.tsx
git commit -m "ridisegno: l'avviso di conferma unico, sopra la barra delle schede"
```

---

### Task 8: `ErrorState`, `EmptyState` e la pagina «Non trovata»

**Files:**
- Create: `frontend/src/components/ui/ErrorState.tsx`, `frontend/src/components/ui/EmptyState.tsx`, `frontend/src/components/ui/States.test.tsx`, `frontend/src/features/not-found/NotFoundScreen.tsx`
- Modify: `frontend/src/App.tsx` (rotta `*`), `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: `Button` (Task 4), `IconRefresh` e `IconAlertCircle` (Task 2), `Screen`, `buttonClasses`.
- Produces:
  - `ErrorState({ message, onRetry, retrying? }: { message: string; onRetry: () => void; retrying?: boolean })`;
  - `EmptyState({ title, body?, action? }: { title: string; body?: ReactNode; action?: ReactNode })`;
  - `NotFoundScreen()`.

- [ ] **Step 1: Scrivi i test che falliscono**

`frontend/src/components/ui/States.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { EmptyState } from "./EmptyState";
import { ErrorState } from "./ErrorState";

describe("ErrorState", () => {
  it("dice cosa non è andato e offre sempre «Riprova»", () => {
    const onRetry = vi.fn();
    render(<ErrorState message="Non sono riuscito a caricare la dispensa." onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Non sono riuscito a caricare la dispensa.");
    fireEvent.click(screen.getByRole("button", { name: "Riprova" }));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("mentre riprova il pulsante non si ripete", () => {
    render(<ErrorState message="x" onRetry={() => {}} retrying />);
    expect(screen.getByRole("button", { name: "Riprovo…" })).toBeDisabled();
  });
});

describe("EmptyState", () => {
  it("ha un titolo, una riga e un'azione", () => {
    render(<EmptyState title="Niente da sistemare" body="Spunta prima qualcosa in lista." action={<a href="/lista">Vai alla lista</a>} />);
    expect(screen.getByRole("heading", { name: "Niente da sistemare" })).toBeInTheDocument();
    expect(screen.getByText("Spunta prima qualcosa in lista.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Vai alla lista" })).toBeInTheDocument();
  });
});
```

In `frontend/src/App.test.tsx` aggiungi un test che apre un indirizzo inesistente. Segui il modo in cui il file già monta `App` con un indirizzo (se usa `window.history.pushState` prima di `render(<App />)`, fai lo stesso):

```tsx
it("un indirizzo che non esiste dice «Pagina non trovata» e porta alla lista", async () => {
  window.history.pushState({}, "", "/non-esiste");
  render(<App />);
  expect(await screen.findByRole("heading", { name: "Pagina non trovata" })).toBeInTheDocument();
  expect(screen.getByRole("link", { name: "Torna alla lista" })).toHaveAttribute("href", "/lista");
});
```

- [ ] **Step 2: Verifica che falliscano**

Run: `cd frontend && npx vitest run src/components/ui/States.test.tsx src/App.test.tsx`
Expected: FAIL. Mancano i moduli, e la rotta `*` non c'è (oggi la pagina resta vuota).

- [ ] **Step 3: `ErrorState` ed `EmptyState`**

`frontend/src/components/ui/ErrorState.tsx`:

```tsx
import { Button } from "./Button";
import { IconAlertCircle, IconRefresh } from "./icons";

/** L'errore di caricamento, uno per tutta l'app (spec T3 §3.5: il giro ne ha contate
 * cinque forme, due senza un modo di riprovare). Dice cosa non è andato — chi lo usa
 * scrive anche se il dato è ancora lì — e offre sempre «Riprova»: «riprova più tardi»
 * senza un pulsante chiede di ricaricare a mano, ed è un vicolo cieco. */
export function ErrorState({
  message,
  onRetry,
  retrying = false,
}: {
  message: string;
  onRetry: () => void;
  retrying?: boolean;
}) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3 rounded-2xl bg-card p-4">
      <p className="flex items-start gap-2 text-sm text-danger">
        <IconAlertCircle aria-hidden="true" className="mt-0.5 size-5 shrink-0" stroke={1.8} />
        {message}
      </p>
      <Button icon={IconRefresh} onClick={onRetry} disabled={retrying}>
        {retrying ? "Riprovo…" : "Riprova"}
      </Button>
    </div>
  );
}
```

`frontend/src/components/ui/EmptyState.tsx`:

```tsx
import type { ReactNode } from "react";

/** Una schermata vuota che invita invece di scusarsi: cosa manca, perché, e cosa fare. */
export function EmptyState({ title, body, action }: { title: string; body?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-2 rounded-2xl bg-card p-4">
      <h2 className="text-base font-semibold">{title}</h2>
      {body && <p className="text-sm text-ink-soft">{body}</p>}
      {action && <div className="pt-1">{action}</div>}
    </div>
  );
}
```

- [ ] **Step 4: La pagina «Non trovata» e la rotta**

`frontend/src/features/not-found/NotFoundScreen.tsx`:

```tsx
import { Link } from "react-router-dom";
import { Screen } from "../../components/ui/Screen";
import { EmptyState } from "../../components/ui/EmptyState";
import { buttonClasses } from "../../components/ui/buttonClasses";

/** Un indirizzo che non porta a niente — un collegamento vecchio, un refuso. Prima
 * di questa schermata restava una pagina vuota sotto l'intestazione (dal giro di T3),
 * cioè un vicolo cieco. */
export function NotFoundScreen() {
  return (
    <Screen title="Pagina non trovata">
      <EmptyState
        title="Questo indirizzo non porta a niente"
        body="Forse è un collegamento vecchio. Da qui torni dove si comincia."
        action={
          <Link to="/lista" className={buttonClasses("primary")}>
            Torna alla lista
          </Link>
        }
      />
    </Screen>
  );
}
```

Nota: `Screen` usa `<h1>` per il titolo ed `EmptyState` usa `<h2>`; il test cerca il titolo della schermata («Pagina non trovata»), che è unico.

In `frontend/src/App.tsx`, come ultima `<Route>` dentro `<Routes>`:

```tsx
            {/* in fondo: prende solo ciò che nessuna rotta sopra ha preso */}
            <Route path="*" element={<NotFoundScreen />} />
```

- [ ] **Step 5: Verifica che passino, e i controlli**

Run: `cd frontend && npx vitest run && npm run lint && npm run typecheck`
Expected: PASS e verde.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ui/ErrorState.tsx frontend/src/components/ui/EmptyState.tsx frontend/src/components/ui/States.test.tsx frontend/src/features/not-found/NotFoundScreen.tsx frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "ridisegno: un errore solo con Riprova, lo stato vuoto, e la pagina non trovata"
```

---

### Task 9: Il selettore d'ingrediente: ARIA valido e «Aggiungi «…»»

**Files:**
- Modify: `frontend/src/components/ui/OptionList.tsx`, `frontend/src/components/IngredientPicker.tsx`
- Test: `frontend/src/components/IngredientPicker.test.tsx`

**Interfaces:**
- Consumes: `Button` (Task 4), `IconPlus` (Task 2).
- Produces: `IngredientPicker` accetta in più `onCreate?: (name: string) => void`. Senza `onCreate` si comporta come oggi, quindi chi lo usa non cambia. `OptionList` ha la stessa firma di prima.

- [ ] **Step 1: Scrivi i test che falliscono**

In `frontend/src/components/IngredientPicker.test.tsx` aggiungi, usando `stubRoutedFetch` e `renderWithClient` che il file ha già:

```tsx
const LATTE: Ingredient = { id: "i1", name: "latte", display_name: "Latte", category: "latticini", kind: "food" };

it("ogni suggerimento è un'opzione della lista, senza voci d'elenco in mezzo", async () => {
  stubRoutedFetch(() => [[LATTE], 200]);
  renderWithClient(<IngredientPicker label="Contiene ingredienti" failureNote="x" onPick={() => {}} />);
  fireEvent.change(screen.getByLabelText("Contiene ingredienti"), { target: { value: "lat" } });
  const listbox = await screen.findByRole("listbox");
  // ARIA: i figli di un listbox sono opzioni, non `listitem` (dal giro di T3)
  expect(within(listbox).queryAllByRole("listitem")).toHaveLength(0);
  // il nome è l'ingrediente e basta, il reparto è una descrizione: prima si leggeva
  // «Lattelatticini»
  expect(within(listbox).getByRole("option", { name: "Latte" })).toHaveAccessibleDescription("latticini");
});

it("quando non trova niente offre di aggiungerlo, se chi lo usa sa crearlo", async () => {
  stubRoutedFetch(() => [[], 200]);
  const onCreate = vi.fn();
  renderWithClient(
    <IngredientPicker label="Aggiungi un ingrediente" failureNote="x" onPick={() => {}} onCreate={onCreate} />
  );
  fireEvent.change(screen.getByLabelText("Aggiungi un ingrediente"), { target: { value: "zz tre" } });
  fireEvent.click(await screen.findByRole("button", { name: "Aggiungi «zz tre»" }));
  expect(onCreate).toHaveBeenCalledWith("zz tre");
});

it("senza onCreate, a ricerca vuota non offre niente: resta com'era", async () => {
  stubRoutedFetch(() => [[], 200]);
  renderWithClient(<IngredientPicker label="Contiene ingredienti" failureNote="x" onPick={() => {}} />);
  fireEvent.change(screen.getByLabelText("Contiene ingredienti"), { target: { value: "zz tre" } });
  await waitFor(() => expect(screen.queryByRole("listbox")).toBeNull());
  expect(screen.queryByRole("button", { name: /Aggiungi/ })).toBeNull();
});
```

Se `vi`, `within` o `waitFor` non sono già importati nel file, aggiungili all'import.

- [ ] **Step 2: Verifica che falliscano**

Run: `cd frontend && npx vitest run src/components/IngredientPicker.test.tsx`
Expected: FAIL. Oggi ogni opzione sta in un `<li>`, il nome fonde nome e reparto, e `onCreate` non esiste.

- [ ] **Step 3: `OptionList`**

Riscrivi il corpo di `frontend/src/components/ui/OptionList.tsx`, tenendo il commento in testa:

```tsx
import { useId } from "react";
import type { Ingredient } from "../../domain/types";

export function OptionList({
  options,
  onPick,
  disabled = false,
}: {
  options: Ingredient[];
  onPick: (ingredient: Ingredient) => void;
  disabled?: boolean;
}) {
  const baseId = useId();
  return (
    // un listbox contiene opzioni e basta: niente `<ul>/<li>` in mezzo, che uno screen
    // reader leggerebbe come un elenco di voci e non come una scelta (dal giro di T3)
    <div role="listbox" className="flex flex-col overflow-hidden rounded-card bg-card">
      {options.map((ingredient) => {
        const categoryId = `${baseId}-${ingredient.id}`;
        return (
          <button
            key={ingredient.id}
            type="button"
            role="option"
            aria-selected={false}
            aria-label={ingredient.display_name}
            aria-describedby={categoryId}
            disabled={disabled}
            onClick={() => onPick(ingredient)}
            className="flex min-h-12 w-full items-baseline gap-3 px-3 py-2.5 text-left text-sm disabled:opacity-50"
          >
            <span className="truncate">{ingredient.display_name}</span>
            {/* la categoria serve a distinguere due omonimi, non a essere letta
                sempre: in fondo alla riga, e per chi ascolta è una descrizione, non
                un pezzo del nome */}
            <span id={categoryId} className="ml-auto shrink-0 text-xs text-ink-faint">
              {ingredient.category}
            </span>
          </button>
        );
      })}
    </div>
  );
}
```

L'`aria-label` non è ridondante: senza, con il `<span>` della categoria dentro il pulsante, il nome accessibile resterebbe «Lattelatticini».

- [ ] **Step 4: «Aggiungi «…»» in `IngredientPicker`**

In `frontend/src/components/IngredientPicker.tsx`:
- aggiungi alla firma `onCreate?: (name: string) => void;` con il commento «Chi sa creare un ingrediente nuovo lo offre quando la ricerca non trova niente (R12). Senza, la ricerca vuota non propone niente, come prima.»;
- leggi anche `isSuccess` da `useQuery`;
- dopo il blocco `{showOptions && found.length > 0 && …}` aggiungi:

```tsx
      {/* solo a ricerca finita e vuota: mentre la risposta arriva, offrire di creare
          «latt» accanto al latte che sta per comparire sarebbe l'errore di S18 */}
      {onCreate && showOptions && isSuccess && found.length === 0 && (
        <Button
          icon={IconPlus}
          onClick={() => {
            onCreate(term.trim());
            setTerm("");
          }}
          disabled={disabled}
        >
          {`Aggiungi «${term.trim()}»`}
        </Button>
      )}
```

Importa `Button` da `./ui/Button` e `IconPlus` da `./ui/icons`.

- [ ] **Step 5: Verifica che passino, e i controlli**

Run: `cd frontend && npx vitest run && npm run lint && npm run typecheck`
Expected: PASS e verde. Se un test di `AddItemField.test.tsx` o di un'altra schermata cercava le opzioni con `listitem`, o per il nome fuso con il reparto, riscrivilo su `option` e sul nome dell'ingrediente: il comportamento è lo stesso.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/ui/OptionList.tsx frontend/src/components/IngredientPicker.tsx frontend/src/components/IngredientPicker.test.tsx
git commit -m "ridisegno: il selettore d'ingrediente con ARIA valido, e «Aggiungi» quando non trova niente"
```

Aggiungi al commit anche i test di altre schermate che hai dovuto adattare allo Step 5.

---

### Task 10: Il tema scuro su ogni schermata, misurato nel browser; e i documenti

**Files:**
- Modify: `frontend/e2e/style.spec.ts`
- Modify: qualunque schermata in cui il controllo trovi testo sotto 4,5:1 (le correzioni passano dai token, mai da un colore grezzo)
- Modify: `CLAUDE.md` (la convenzione dei colori), `docs/prossimi-passi.md` (T3)

**Interfaces:**
- Consumes: tutto quanto sopra; lo stack e2e (`README.md`, sezione dei test end-to-end).

- [ ] **Step 1: Scrivi i controlli nel browser**

In `frontend/e2e/style.spec.ts`:

1. Accanto a `tokenDelTema`, aggiungi la versione scura, che legge il blocco `@media (prefers-color-scheme: dark)`:

```ts
function tokenDelTemaScuro(nome: string): string {
  const css = readFileSync(fileURLToPath(new URL("../src/index.css", import.meta.url)), "utf8");
  const scuro = css.match(/@media \(prefers-color-scheme: dark\)\s*\{\s*:root\s*\{([\s\S]*?)\}\s*\}/)?.[1] ?? "";
  const esadecimale = scuro.match(new RegExp(`--color-${nome}:\\s*#([0-9a-fA-F]{6})\\s*;`))?.[1];
  expect(esadecimale, `--color-${nome} non è nel blocco scuro di index.css`).toBeDefined();
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(esadecimale!.slice(i, i + 2), 16));
  return `rgb(${r}, ${g}, ${b})`;
}
```

2. Una funzione che scorre tutto il testo visibile di una pagina e raccoglie ciò che sta sotto 4,5:1:

```ts
/** Ogni testo visibile della pagina, col suo contrasto contro il primo fondo dipinto
 * dietro di lui. Salta ciò che è nascosto, i controlli spenti (WCAG li esenta) e il
 * testo dentro un `aria-hidden`. Torna solo i casi sotto 4,5:1, descritti. */
async function testiIlleggibili(page: Page): Promise<string[]> {
  return page.evaluate(() => {
    const canali = (c: string) => (c.match(/[\d.]+/g) ?? []).map(Number);
    const lum = (c: string) => {
      const [r, g, b] = canali(c).map((v) => {
        const s = v / 255;
        return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
      });
      return 0.2126 * r + 0.7152 * g + 0.0722 * b;
    };
    const cattivi: string[] = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const testo = n.textContent?.trim();
      const el = n.parentElement;
      if (!testo || !el) continue;
      if (el.closest("[aria-hidden=true], [disabled], [aria-disabled=true], .sr-only")) continue;
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      let fondo: string | null = null;
      let opacita = 1;
      for (let nodo: Element | null = el; nodo; nodo = nodo.parentElement) {
        const s = getComputedStyle(nodo);
        opacita *= Number(s.opacity);
        if (fondo === null && (canali(s.backgroundColor)[3] ?? 1) > 0) fondo = s.backgroundColor;
      }
      if (opacita < 1) continue;
      const a = lum(getComputedStyle(el).color);
      const b = lum(fondo ?? "rgb(255, 255, 255)");
      const rapporto = (Math.max(a, b) + 0.05) / (Math.min(a, b) + 0.05);
      if (rapporto < 4.5) cattivi.push(`«${testo.slice(0, 40)}» ${rapporto.toFixed(2)}:1 su ${fondo}`);
    }
    return cattivi;
  });
}
```

   (Se il file non importa già `Page` da `@playwright/test`, aggiungilo all'import.)

3. I controlli, in chiaro e in scuro, sulle schermate che si raggiungono dal seme `--con-ricette` senza scrivere niente:

```ts
const SCHERMATE = ["/lista", "/sistema", "/dispensa", "/ricette", "/ricette/importa", "/anagrafica", "/non-esiste"];

for (const tema of ["light", "dark"] as const) {
  test.describe(`tema ${tema === "light" ? "chiaro" : "scuro"}`, () => {
    test.use({ colorScheme: tema });

    test("il fondo della pagina è il token del tema", async ({ page }) => {
      const atteso = tema === "light" ? tokenDelTema("page") : tokenDelTemaScuro("page");
      await expect(page.locator("body")).toHaveCSS("background-color", atteso);
    });

    test("su ogni schermata ogni testo sta sopra 4,5:1", async ({ page }) => {
      const tutti: string[] = [];
      for (const indirizzo of SCHERMATE) {
        await page.goto(indirizzo);
        await page.waitForLoadState("networkidle");
        tutti.push(...(await testiIlleggibili(page)).map((t) => `${indirizzo}: ${t}`));
      }
      // anche il dettaglio di una ricetta: la prima del ricettario
      await page.goto("/ricette");
      await page.getByRole("link").filter({ has: page.locator("h2, h3") }).first().click();
      await page.waitForLoadState("networkidle");
      tutti.push(...(await testiIlleggibili(page)).map((t) => `dettaglio: ${t}`));
      expect(tutti).toEqual([]);
    });

    test("ogni pulsante ha un nome, anche quelli di sola icona", async ({ page }) => {
      const muti: string[] = [];
      for (const indirizzo of SCHERMATE) {
        await page.goto(indirizzo);
        await page.waitForLoadState("networkidle");
        const qui = await page.evaluate(() =>
          [...document.querySelectorAll("button")]
            .filter((b) => !(b.getAttribute("aria-label") || b.textContent?.trim() || b.getAttribute("aria-labelledby")))
            .map((b) => b.outerHTML.slice(0, 80))
        );
        muti.push(...qui.map((b) => `${indirizzo}: ${b}`));
      }
      expect(muti).toEqual([]);
    });
  });
}

test("il carattere è Inter, servito dall'app", async ({ page }) => {
  await page.waitForLoadState("networkidle");
  expect(await page.evaluate(() => document.fonts.check('16px "Inter Variable"'))).toBe(true);
  await expect(page.locator("body")).toHaveCSS("font-family", /Inter Variable/);
});
```

   Il selettore del dettaglio deve prendere una scheda di ricetta del ricettario di oggi. Se non trova niente, guarda `RecipeCard.tsx` e usa il suo ruolo e il suo titolo veri: il punto è aprire un dettaglio qualunque.

- [ ] **Step 2: Fai girare l'e2e e correggi quel che trova**

Run (dalla radice del repo; lo stack è quello del `README.md`):

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e
```

Expected, la prima volta: il controllo del contrasto può trovare dei testi sotto 4,5:1, in scuro più facilmente. Per ognuno:
- se il testo usa un token giusto su un fondo sbagliato, o `opacity` per schiarire (per esempio `text-ink/60`), passa a un token (`text-ink-faint`);
- se nessun token regge quella coppia, correggi il valore nel blocco di `index.css`, aggiungi la coppia a `PAIRS` di `theme.test.ts`, e rifai girare quel test;
- mai un colore grezzo in una schermata.

Rifai girare finché tutto è verde, poi `docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v`.

- [ ] **Step 3: Un giro a occhio, a 375 px, in chiaro e in scuro**

Con lo stack ancora su, apri nel browser `http://localhost:5174` a 375×812, prima in chiaro poi con `prefers-color-scheme: dark`, e passa da Lista, Sistema la spesa, Dispensa, Ricette, un dettaglio, il ☰, Anagrafica, la coda, e un indirizzo inesistente. Cerca ciò che il contrasto non misura: un bordo che sparisce, un'icona illeggibile, un selettore data ancora chiaro, il cursore della dispensa (resta fino alla Consegna 1: deve vedersi anche in scuro). Scrivi nel rapporto cosa hai visto e cosa hai corretto.

- [ ] **Step 4: I documenti**

`CLAUDE.md`, nel punto «**All colour lives in one `@theme` block**»: aggiungi, dopo la prima frase, «The dark theme redefines the same variables under `@media (prefers-color-scheme: dark)` in the same file, so no screen knows which theme it is in. Text on a solid fill uses the matching `on-*` token (`text-on-brand`), never `text-white`: in the dark theme the fills get lighter. `src/theme.test.ts` checks every text/background pair in both themes; `e2e/style.spec.ts` measures every visible text on every screen.»

`docs/prossimi-passi.md`, sotto la voce T3: aggiungi un paragrafo «**Consegna 0 (fondamenta) fatta il <data>**, sul ramo `<ramo>`, non ancora in produzione: token chiari e scuri, Inter, icone Tabler, il cesto nell'intestazione, la barra delle schede con le icone e «Lista» accesa su `/sistema`, la pagina «Non trovata», e le primitive (`Button`, `IconToolbar`, `ActionBar`, `Section`, `StockGauge`, `StatusDot`, `Chip`, l'avviso unico, `ErrorState`, `EmptyState`, `IngredientPicker` con «Aggiungi»). Le schermate le adottano dalla Consegna 1. Da provare sul telefono: il tema scuro vero, la barra di stato nei due temi, l'icona dell'app reinstallata.» Metti i numeri veri dei test.

- [ ] **Step 5: Controlli finali**

Run: `cd frontend && npx vitest run && npm run lint && npm run typecheck && npm run build`
Expected: verde.

- [ ] **Step 6: Commit**

```bash
git add frontend/e2e/style.spec.ts CLAUDE.md docs/prossimi-passi.md
git add -u frontend/src
git commit -m "ridisegno: il tema scuro misurato su ogni schermata, e la regola dei colori nei documenti"
```
