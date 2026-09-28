# T3 Consegna 1 — La Dispensa ridisegnata: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** portare la schermata Dispensa sulle primitive della Consegna 0: barra «Cerca o aggiungi» con il +, riepilogo delle scadenze, sezioni per reparto, righe con le tre tacche al posto del cursore, «In lista» sulle voci finite e la ✕ con l'avviso «Annulla».

**Architecture:** tutto nel frontend, nessuna rotta nuova e nessuna migrazione. La logica che decide cosa si vede (filtro, riepilogo, ordine delle righe, testo della scadenza) va in funzioni pure testate a tabella (`pantryView.ts`, `expiryLabels.ts`). `PantryRow` diventa una riga compatta con `StockGauge`. `PantryScreen` compone `ActionBar`, `Section`, `EmptyState`, `ErrorState` e l'avviso unico (`useNotice`). Il cursore (`FillSlider`, `fillZones`), la lapide e le pastiglie `StatusChip`/`ExpiryChip` escono.

**Tech Stack:** React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5, react-router 7, Vitest + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-09-28-ridisegno-design.md`, §2, §4.1 e §4.4. Si legge insieme a questo piano.

## Global Constraints

- Tutto il colore passa dai token di `frontend/src/index.css`. Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto.
- Le icone si importano solo da `frontend/src/components/ui/icons.ts`. Un'icona che manca si aggiunge lì, re-esportata da `@tabler/icons-react`.
- Regola delle icone (spec §2): **più pulsanti in gruppo → solo icone; un pulsante da solo → icona e testo.** Ogni pulsante di sola icona ha il nome completo come `aria-label`: `Button` con `icon` e `label`.
- Ogni bersaglio nuovo è almeno 44×44 px. Ogni testo sta sopra 4,5:1, in chiaro e in scuro.
- **Il 7 dei giorni di scadenza non entra nel TypeScript.** Quale voce è «in scadenza» lo dice `item.expiry` (`"soon"` / `"expired"` / `null`), deciso dal backend.
- **Nessuna percentuale.** Nessun client scrive più `fill_percent`: le tacche mandano `status`. Il backend non si tocca (spec §4.1: «Nessuna migrazione»).
- **Mai un vicolo cieco.** Ogni scrittura fallita lascia un modo di riprovare, accanto alla voce o nell'avviso.
- Le parole a video sono in italiano, gli identificatori in inglese, i commenti in italiano come nel resto del codice.
- **Accordi**: niente participi che concordano con il nome della voce («Tolta dalla dispensa» sbaglia su «kiwi»). Si scrive «Tolto dalla dispensa: kiwi», «scadeva ieri», «Rimesso in lista: kiwi».
- Il type check è `npm run typecheck` (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0.
- Controlli del frontend, da `frontend/`: `npx vitest run`, `npm run lint`, `npm run typecheck`, `npm run build`.
- e2e: stack `spena-e2e` (comandi nel Task 5). Serve un `.env` nella radice del worktree: si copia da `.env.example`, che non ha segreti, e si cancella a fine prova. **Mai copiare il `.env` del checkout principale.**

---

## File toccati

| File | Cosa |
|---|---|
| `frontend/src/features/pantry/pantryView.ts` (nuovo) | `itemLabel`, `matchesQuery`, `isExpiring`, `expiryCounts`, `expirySummary`, `groupForDisplay` |
| `frontend/src/features/pantry/pantryView.test.ts` (nuovo) | test a tabella |
| `frontend/src/features/pantry/expiryLabels.ts` | `expiryText` al posto di `formatExpiry` ed `EXPIRY_TONE` |
| `frontend/src/features/pantry/expiryLabels.test.ts` | test di `expiryText` |
| `frontend/src/components/IngredientPicker.tsx` | `initialTerm`, `autoFocus` |
| `frontend/src/components/ui/ActionBar.tsx` (+ test) | a campo vuoto il + porta il fuoco nel campo |
| `frontend/src/features/pantry/PantryRow.tsx` | riscritta |
| `frontend/src/features/pantry/PantryRow.test.tsx` (nuovo) | test della riga |
| `frontend/src/features/pantry/PantryScreen.tsx` | riscritta |
| `frontend/src/features/pantry/PantryScreen.test.tsx` | riscritta per il comportamento nuovo |
| `frontend/src/features/pantry/api.ts` | `patchPantryItem` senza `fill_percent` |
| `frontend/src/domain/types.ts` | commento di `fill_percent` |
| cancellati | `FillSlider.tsx`, `FillSlider.test.tsx`, `fillZones.ts`, `fillZones.test.ts`, `components/ui/StatusChip.tsx`, `StatusChip.test.tsx`, `components/ui/ExpiryChip.tsx`, `ExpiryChip.test.tsx` |
| `frontend/e2e/*.spec.ts` | cooking, non-alimentari, anagrafica, style |
| `CLAUDE.md`, `docs/prossimi-passi.md` | `fill_percent`, S11, T4, T3 Consegna 1 |

---

### Task 1: Le funzioni pure: filtro, riepilogo, ordine, testo della scadenza

**Files:**
- Create: `frontend/src/features/pantry/pantryView.ts`
- Create: `frontend/src/features/pantry/pantryView.test.ts`
- Modify: `frontend/src/features/pantry/expiryLabels.ts` (aggiungere `expiryText`; `formatExpiry` ed `EXPIRY_TONE` restano per ora, li usa ancora `ExpiryChip` e li toglie il Task 3)
- Modify: `frontend/src/features/pantry/expiryLabels.test.ts`

**Interfaces:**
- Consumes: `PantryItem`, `ExpiryState` da `frontend/src/domain/types.ts`.
- Produces:
  - `itemLabel(item: PantryItem): string`
  - `matchesQuery(item: PantryItem, query: string): boolean`
  - `isExpiring(item: PantryItem): boolean`
  - `expiryCounts(items: PantryItem[]): { soon: number; expired: number }`
  - `expirySummary(counts: { soon: number; expired: number }): string | null`
  - `groupForDisplay(items: PantryItem[]): [string, PantryItem[]][]`
  - `expiryText(expiresOn: string, expiry: ExpiryState | null, today?: Date): string`

- [ ] **Step 1: Scrivere i test di `pantryView`**

`frontend/src/features/pantry/pantryView.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { PantryItem } from "../../domain/types";
import {
  expiryCounts,
  expirySummary,
  groupForDisplay,
  isExpiring,
  itemLabel,
  matchesQuery,
} from "./pantryView";

function item(over: Partial<PantryItem>): PantryItem {
  return {
    id: "x",
    ingredient_id: "i",
    product_id: null,
    ingredient_name: "mela",
    ingredient_category: "frutta",
    product_name: null,
    product_brand: null,
    status: "available",
    fill_percent: null,
    note: null,
    added_at: "2026-09-11T10:00:00Z",
    expires_on: null,
    expiry: null,
    ...over,
  };
}

describe("itemLabel", () => {
  it("usa il prodotto se c'è, l'ingrediente altrimenti", () => {
    expect(itemLabel(item({ product_name: "Total 0%" }))).toBe("Total 0%");
    expect(itemLabel(item({}))).toBe("mela");
  });
});

describe("matchesQuery", () => {
  const yogurt = item({ ingredient_name: "yogurt greco", product_name: "Total 0%", product_brand: "Fage" });
  it.each([
    ["", true],
    ["   ", true],
    ["yog", true],
    ["GRECO", true],
    ["total", true],
    ["fage", true],
    ["latte", false],
  ])("«%s» → %s", (query, expected) => {
    expect(matchesQuery(yogurt, query)).toBe(expected);
  });

  it("non guarda gli accenti: «caffe» trova «caffè»", () => {
    expect(matchesQuery(item({ ingredient_name: "caffè" }), "caffe")).toBe(true);
    expect(matchesQuery(item({ ingredient_name: "caffe" }), "caffè")).toBe(true);
  });
});

describe("isExpiring", () => {
  it.each([
    [{ expiry: "soon" as const }, true],
    [{ expiry: "expired" as const }, true],
    [{ expiry: null }, false],
    // un barattolo finito non allarma: non c'è più niente da consumare in tempo
    [{ expiry: "soon" as const, status: "finished" as const }, false],
    [{ expiry: "expired" as const, status: "low" as const }, true],
  ])("%o → %s", (over, expected) => {
    expect(isExpiring(item(over))).toBe(expected);
  });
});

describe("expiryCounts ed expirySummary", () => {
  it("conta le voci per verdetto, senza le finite", () => {
    const items = [
      item({ id: "a", expiry: "soon" }),
      item({ id: "b", expiry: "soon" }),
      item({ id: "c", expiry: "expired" }),
      item({ id: "d", expiry: "soon", status: "finished" }),
      item({ id: "e" }),
    ];
    expect(expiryCounts(items)).toEqual({ soon: 2, expired: 1 });
  });

  it.each([
    [{ soon: 0, expired: 0 }, null],
    [{ soon: 1, expired: 0 }, "1 in scadenza questa settimana"],
    [{ soon: 3, expired: 0 }, "3 in scadenza questa settimana"],
    [{ soon: 0, expired: 2 }, "2 oltre la scadenza"],
    [{ soon: 2, expired: 1 }, "2 in scadenza questa settimana · 1 oltre la scadenza"],
  ])("%o → %s", (counts, expected) => {
    expect(expirySummary(counts)).toBe(expected);
  });
});

describe("groupForDisplay", () => {
  it("reparti in ordine alfabetico, e dentro l'ordine del server", () => {
    const groups = groupForDisplay([
      item({ id: "1", ingredient_category: "verdura" }),
      item({ id: "2", ingredient_category: "frutta" }),
      item({ id: "3", ingredient_category: "verdura" }),
    ]);
    expect(groups.map(([category, rows]) => [category, rows.map((r) => r.id)])).toEqual([
      ["frutta", ["2"]],
      ["verdura", ["1", "3"]],
    ]);
  });

  it("le finite vanno in fondo alla loro sezione, ciascun gruppo nel suo ordine", () => {
    const [[, rows]] = groupForDisplay([
      item({ id: "a", status: "finished" }),
      item({ id: "b" }),
      item({ id: "c", status: "finished" }),
      item({ id: "d", status: "low" }),
    ]);
    expect(rows.map((r) => r.id)).toEqual(["b", "d", "a", "c"]);
  });
});
```

- [ ] **Step 2: Scrivere i test di `expiryText`**

Aggiungere in fondo a `frontend/src/features/pantry/expiryLabels.test.ts` (l'import di `expiryText` si aggiunge a quello già presente dal modulo `./expiryLabels`):

```ts
describe("expiryText", () => {
  // «oggi» è il 28 settembre 2026, a mezzogiorno ora locale
  const today = new Date(2026, 8, 28, 12, 0);

  it.each([
    // il verdetto «soon» viene dal backend: qui si sceglie solo come dirlo
    ["2026-09-28", "soon", "scade oggi"],
    ["2026-09-29", "soon", "scade domani"],
    ["2026-10-01", "soon", "scade tra 3 gg"],
    // il fuso del telefono può non essere quello di Roma: un «soon» già passato si
    // dice «oggi», non «tra -1 gg»
    ["2026-09-27", "soon", "scade oggi"],
    ["2026-09-27", "expired", "scadeva ieri"],
    ["2026-09-20", "expired", "scadeva il 20 set"],
    // «expired» con la data di oggi è un disaccordo di fuso: si dice ieri
    ["2026-09-28", "expired", "scadeva ieri"],
    ["2026-11-15", null, "scade il 15 nov"],
    ["2027-01-10", null, "scade il 10 gen 2027"],
    ["2025-12-31", "expired", "scadeva il 31 dic 2025"],
  ] as const)("%s (%s) → %s", (expiresOn, expiry, expected) => {
    expect(expiryText(expiresOn, expiry, today)).toBe(expected);
  });

  it("non sbaglia giorno al cambio dell'ora legale", () => {
    // il 25 ottobre 2026 l'Italia torna all'ora solare: quel giorno dura 25 ore
    const sabato = new Date(2026, 9, 24, 23, 30);
    expect(expiryText("2026-10-26", "soon", sabato)).toBe("scade tra 2 gg");
  });
});
```

- [ ] **Step 3: Far girare i test e vederli fallire**

Run (da `frontend/`): `npx vitest run src/features/pantry/pantryView.test.ts src/features/pantry/expiryLabels.test.ts`
Expected: FAIL. `pantryView` non esiste ed `expiryText` non è esportata.

- [ ] **Step 4: Scrivere `pantryView.ts`**

```ts
import type { PantryItem } from "../../domain/types";

/** Il nome con cui l'utente chiama questa voce: il prodotto se c'è, l'ingrediente
 * altrimenti. Entra nei nomi accessibili dei controlli della riga («Togli Total 0%
 * dalla dispensa»), perché due barattoli dello stesso ingrediente vanno distinti. */
export function itemLabel(item: PantryItem): string {
  return item.product_name ?? item.ingredient_name;
}

// minuscole e senza accenti: chi cerca «caffe» vuole il caffè
function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim();
}

/** Se la voce risponde a quel che è scritto nella barra (S11). Guarda ingrediente,
 * prodotto e marca: si cerca «fage» come si cerca «yogurt». */
export function matchesQuery(item: PantryItem, query: string): boolean {
  const wanted = fold(query);
  if (!wanted) return true;
  return [item.ingredient_name, item.product_name, item.product_brand].some(
    (field) => field !== null && fold(field).includes(wanted)
  );
}

/** Se la voce entra nel riepilogo delle scadenze. Il verdetto è del backend
 * (`expiry`); qui si toglie solo ciò che è finito, perché un barattolo vuoto non ha
 * più niente da consumare in tempo. */
export function isExpiring(item: PantryItem): boolean {
  return item.expiry !== null && item.status !== "finished";
}

export function expiryCounts(items: PantryItem[]): { soon: number; expired: number } {
  let soon = 0;
  let expired = 0;
  for (const item of items) {
    if (!isExpiring(item)) continue;
    if (item.expiry === "soon") soon += 1;
    else expired += 1;
  }
  return { soon, expired };
}

/** Il testo del riepilogo in cima alla dispensa, `null` se non c'è niente da dire:
 * il riepilogo compare solo quando serve (spec T3 §4.1). «Oltre la scadenza» e non
 * «scaduti»: il participio sbaglierebbe l'accordo su metà delle voci. */
export function expirySummary(counts: { soon: number; expired: number }): string | null {
  const parts: string[] = [];
  if (counts.soon > 0) parts.push(`${counts.soon} in scadenza questa settimana`);
  if (counts.expired > 0) parts.push(`${counts.expired} oltre la scadenza`);
  return parts.length > 0 ? parts.join(" · ") : null;
}

/** Le sezioni a video: reparti in ordine alfabetico; dentro, l'ordine del server
 * (stabile da S21) con le voci finite in fondo (spec T3 §4.1). Il filtro è stabile:
 * le finite restano fra loro nell'ordine in cui arrivano. */
export function groupForDisplay(items: PantryItem[]): [string, PantryItem[]][] {
  const groups = new Map<string, PantryItem[]>();
  for (const item of items) {
    groups.set(item.ingredient_category, [...(groups.get(item.ingredient_category) ?? []), item]);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([category, rows]) => [
      category,
      [...rows.filter((r) => r.status !== "finished"), ...rows.filter((r) => r.status === "finished")],
    ]);
}
```

- [ ] **Step 5: Aggiungere `expiryText` a `expiryLabels.ts`**

Aggiungere in fondo al file, lasciando per ora `formatExpiry` ed `EXPIRY_TONE`:

```ts
const DAY_MS = 86_400_000;

// La data-senza-ora letta in ora locale, con la stessa cautela di `formatExpiry`:
// tre numeri al costruttore posizionale, e l'anno rimesso a mano.
function localDate(expiresOn: string): Date {
  const [anno, mese, giorno] = expiresOn.split("-").map(Number);
  const data = new Date(anno, mese - 1, giorno);
  data.setFullYear(anno);
  return data;
}

// Giorni di calendario fra due date. Si contano sulle date UTC costruite con i
// numeri del calendario, non sui millisecondi locali: il giorno del cambio d'ora
// dura 23 o 25 ore, e una divisione per 24 sbaglierebbe di uno.
function daysBetween(from: Date, to: Date): number {
  const a = Date.UTC(from.getFullYear(), from.getMonth(), from.getDate());
  const b = Date.UTC(to.getFullYear(), to.getMonth(), to.getDate());
  return Math.round((b - a) / DAY_MS);
}

// «15 nov», e l'anno solo se non è quello di oggi (dal giro: le date avevano
// sempre l'anno, anche quando non diceva niente)
function shortDate(date: Date, today: Date): string {
  const options: Intl.DateTimeFormatOptions = { day: "numeric", month: "short" };
  if (date.getFullYear() !== today.getFullYear()) options.year = "numeric";
  return date.toLocaleDateString("it-IT", options);
}

/** La scadenza come si legge sulla riga (spec T3 §4.1): relativa quando il backend
 * dice che è vicina o passata da un giorno, assoluta altrimenti. Quale voce è «in
 * scadenza» lo decide `expiry`: qui non c'è nessuna soglia di giorni. «Scadeva» e
 * non «scaduto», per non sbagliare l'accordo col nome della voce. */
export function expiryText(expiresOn: string, expiry: ExpiryState | null, today: Date = new Date()): string {
  const date = localDate(expiresOn);
  const days = daysBetween(today, date);
  if (expiry === "soon") {
    if (days <= 0) return "scade oggi";
    if (days === 1) return "scade domani";
    return `scade tra ${days} gg`;
  }
  if (expiry === "expired") {
    if (days >= -1) return "scadeva ieri";
    return `scadeva il ${shortDate(date, today)}`;
  }
  return `scade il ${shortDate(date, today)}`;
}
```

- [ ] **Step 6: Far girare i test e vederli passare**

Run: `npx vitest run src/features/pantry/pantryView.test.ts src/features/pantry/expiryLabels.test.ts`
Expected: PASS. Se il mese abbreviato di Node esce diverso da «set», «nov», «gen», «dic» (ICU ridotto), fermarsi e riportarlo: non si cambia l'atteso a occhio.

- [ ] **Step 7: Lint, typecheck e commit**

Run: `npm run lint && npm run typecheck`

```bash
git add frontend/src/features/pantry/pantryView.ts frontend/src/features/pantry/pantryView.test.ts frontend/src/features/pantry/expiryLabels.ts frontend/src/features/pantry/expiryLabels.test.ts
git commit -m "dispensa: filtro, riepilogo delle scadenze e ordine delle righe, come funzioni pure"
```

---

### Task 2: `IngredientPicker` parte da un testo, e il + a campo vuoto non è muto

**Files:**
- Modify: `frontend/src/components/IngredientPicker.tsx`
- Modify: `frontend/src/components/ui/ActionBar.tsx`
- Modify: `frontend/src/components/ui/ActionBar.test.tsx`
- Test: il file di test esistente di `IngredientPicker`. Lo si trova con `grep -rl "IngredientPicker" frontend/src --include=*.test.tsx`. Se non ce n'è uno dedicato, si crea `frontend/src/components/IngredientPicker.test.tsx`.

**Interfaces:**
- Produces:
  - `IngredientPicker` prende due prop nuove e facoltative: `initialTerm?: string` (il testo con cui il campo nasce) e `autoFocus?: boolean`.
  - `ActionBar`: il + con il campo vuoto (o di soli spazi) non chiama `onAdd` e porta il fuoco nel campo.

- [ ] **Step 1: Scrivere i test**

In `ActionBar.test.tsx`, sostituire il test «a campo vuoto il + non manda niente» con:

```tsx
  it("a campo vuoto il + non manda niente e porta il fuoco nel campo", () => {
    const onAdd = vi.fn();
    render(<Harness onAdd={onAdd} />);
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    expect(onAdd).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(screen.getByLabelText("Cerca o aggiungi in dispensa"));
  });
```

Per `IngredientPicker`, usare l'harness del file di test esistente (`QueryClientProvider` e `fetch` finto). Se il file si crea da zero, l'harness è:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { IngredientPicker } from "./IngredientPicker";

function renderPicker(props: Partial<Parameters<typeof IngredientPicker>[0]> = {}) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <IngredientPicker label="Quale ingrediente?" failureNote="Riprova." onPick={() => {}} {...props} />
    </QueryClientProvider>
  );
}
```

I due test:

```tsx
  it("parte dal testo che gli si passa, e cerca subito quello", async () => {
    const fetchSpy = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([{ id: "i1", name: "sale", display_name: "Sale", category: "condimenti", kind: "food" }]), { status: 200 })
    );
    vi.stubGlobal("fetch", fetchSpy);
    renderPicker({ initialTerm: "sale" });
    expect(screen.getByLabelText("Quale ingrediente?")).toHaveProperty("value", "sale");
    expect(await screen.findByRole("option", { name: "Sale" })).toBeDefined();
  });

  it("con autoFocus il campo prende il fuoco appena compare", () => {
    vi.stubGlobal("fetch", vi.fn());
    renderPicker({ autoFocus: true });
    expect(document.activeElement).toBe(screen.getByLabelText("Quale ingrediente?"));
  });
```

- [ ] **Step 2: Far girare i test e vederli fallire**

Run: `npx vitest run src/components/ui/ActionBar.test.tsx src/components/IngredientPicker.test.tsx` (o il file di test trovato allo Step 0).
Expected: FAIL.

- [ ] **Step 3: Implementare**

In `IngredientPicker.tsx`:
- aggiungere al tipo delle prop:

  ```ts
  /** Il testo con cui il campo nasce: la Dispensa apre l'aggiunta con quel che era
   * scritto nella barra. Vale solo alla nascita — chi vuole ripartire da un altro
   * testo cambia la `key`. */
  initialTerm?: string;
  /** Il campo prende il fuoco appena compare: l'aggiunta si è aperta con un tocco. */
  autoFocus?: boolean;
  ```

- destrutturarle come `initialTerm = ""` e `autoFocus = false`;
- scrivere `useState(initialTerm)` al posto di `useState("")`;
- aggiungere `autoFocus={autoFocus}` all'`<input>`.

`useDebounced` nasce già con il valore iniziale, quindi la ricerca parte subito senza aspettare il ritardo.

In `ActionBar.tsx`:
- aggiungere `useRef` all'import da `react` e `const inputRef = useRef<HTMLInputElement>(null);`;
- mettere `ref={inputRef}` sull'`<input>`;
- riscrivere `submit`:

```tsx
  function submit(event: FormEvent) {
    event.preventDefault();
    const text = value.trim();
    // un + che non fa niente è un controllo morto: a campo vuoto porta dove si scrive
    if (text) onAdd(text);
    else inputRef.current?.focus();
  }
```

- [ ] **Step 4: Far girare i test e vederli passare**

Run: `npx vitest run src/components`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components
git commit -m "ui: il selettore d'ingrediente parte da un testo, e il + a campo vuoto porta al campo"
```

---

### Task 3: La riga nuova — tacche, «In lista», ✕ con l'avviso

**Files:**
- Modify: `frontend/src/features/pantry/PantryRow.tsx` (riscritto)
- Create: `frontend/src/features/pantry/PantryRow.test.tsx`
- Modify: `frontend/src/features/pantry/PantryScreen.tsx`: solo il cablaggio della riga. La disposizione dello schermo cambia nel Task 4.
- Modify: `frontend/src/features/pantry/PantryScreen.test.tsx`
- Modify: `frontend/src/features/pantry/api.ts`
- Modify: `frontend/src/features/pantry/expiryLabels.ts` e `expiryLabels.test.ts`: via `formatExpiry` ed `EXPIRY_TONE` con i loro test.
- Modify: `frontend/src/domain/types.ts`: il commento di `fill_percent`.
- Modify: `frontend/src/features/cooking/CookSheet.test.tsx`: solo il commento alla riga ~270 che cita `FillSlider`.
- Delete: `frontend/src/features/pantry/FillSlider.tsx`, `FillSlider.test.tsx`, `fillZones.ts`, `fillZones.test.ts`, `frontend/src/components/ui/StatusChip.tsx`, `StatusChip.test.tsx`, `frontend/src/components/ui/ExpiryChip.tsx`, `ExpiryChip.test.tsx`

**Interfaces:**
- Consumes: `itemLabel` ed `expiryText` (Task 1); `StockGauge({ status, onChange, itemName, disabled })`, `Button`, `useNotice()` che restituisce `(notice: { text: string; action?: { label: string; onClick: () => void } }) => void`, e `NoticeProvider` (Consegna 0); `revealAtTop(element)` da `frontend/src/lib/revealAtTop.ts`.
- Produces: il componente `PantryRow`, con queste prop:

```ts
{
  item: PantryItem;
  busy: boolean;
  failed: boolean;
  /** l'ingrediente ha già una voce aperta in lista: «In lista» non serve */
  listed: boolean;
  /** portare la riga in vista (dopo un'aggiunta); il Task 4 la accende */
  reveal: boolean;
  onStatus: (status: PantryStatus) => void;
  onRemove: () => void;
  onRestock: () => void;
  onExpiry: (expiresOn: string | null) => Promise<unknown>;
  onRevealed: () => void;
}
```

**La geometria della riga.** Il nome e la riga sotto sono due bersagli da 44 px, uno sopra l'altro, e **non si sovrappongono**:
- il nome è un link `flex min-h-11 items-end pb-0.5`: alto 44 px, con il testo in basso;
- la riga sotto è `flex min-h-11 items-start pt-0.5`, con il testo in alto; la scadenza lì dentro è un pulsante `min-h-11`.

Il testo si legge così come un blocco unito al centro della riga, e fra una riga e l'altra resta lo spazio vuoto dei bersagli: niente linee (spec §2). A destra, centrati in verticale, stanno `StockGauge` (3×44 px) e la ✕ (44 px). Col testo a 375 px la colonna del nome è larga circa 130 px, e i nomi lunghi vanno a capo: va bene così, non si tronca.

- [ ] **Step 1: Scrivere i test della riga**

`frontend/src/features/pantry/PantryRow.test.tsx`:

```tsx
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { PantryRow } from "./PantryRow";
import type { PantryItem } from "../../domain/types";

const BASE: PantryItem = {
  id: "p1", ingredient_id: "i1", product_id: "pr1", ingredient_name: "yogurt greco",
  ingredient_category: "latticini", product_name: "Total 0%", product_brand: "Fage",
  status: "available", fill_percent: null, note: null, added_at: "2026-09-11T10:00:00Z",
  expires_on: null, expiry: null,
};

function renderRow(over: Partial<PantryItem> = {}, props: Partial<Parameters<typeof PantryRow>[0]> = {}) {
  const handlers = {
    onStatus: vi.fn(),
    onRemove: vi.fn(),
    onRestock: vi.fn(),
    onExpiry: vi.fn().mockResolvedValue(undefined),
    onRevealed: vi.fn(),
  };
  render(
    <MemoryRouter>
      <ul>
        <PantryRow item={{ ...BASE, ...over }} busy={false} failed={false} listed={false} reveal={false} {...handlers} {...props} />
      </ul>
    </MemoryRouter>
  );
  return handlers;
}

describe("PantryRow", () => {
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ["Date"] });
    vi.setSystemTime(new Date(2026, 8, 28, 12, 0));
  });
  afterEach(() => vi.useRealTimers());

  it("il nome è l'ingrediente, e sotto c'è il prodotto: un aggancio sbagliato si vede", () => {
    renderRow();
    expect(screen.getByRole("link", { name: "yogurt greco" })).toBeDefined();
    expect(screen.getByText("Total 0%")).toBeDefined();
  });

  it("una voce senza prodotto dice «sfuso»", () => {
    renderRow({ product_id: null, product_name: null, product_brand: null });
    expect(screen.getByText("sfuso")).toBeDefined();
  });

  it("il nome porta alla scheda del prodotto se c'è, dell'ingrediente se è sfuso", () => {
    renderRow();
    expect(screen.getByRole("link", { name: "yogurt greco" }).getAttribute("href")).toContain("/anagrafica/prodotto/pr1");
  });

  it("le tacche mandano lo stato toccato, non una percentuale", () => {
    const { onStatus } = renderRow();
    fireEvent.click(screen.getByRole("radio", { name: "Quasi finito" }));
    expect(onStatus).toHaveBeenCalledWith("low");
  });

  it("la scadenza vicina si legge relativa", () => {
    renderRow({ expires_on: "2026-10-01", expiry: "soon" });
    expect(screen.getByRole("button", { name: "Scadenza di Total 0%: scade tra 3 gg" })).toBeDefined();
  });

  it("senza scadenza offre di scriverla, e il campo manda la data all'uscita", async () => {
    const { onExpiry } = renderRow();
    fireEvent.click(screen.getByRole("button", { name: "+ scadenza per Total 0%" }));
    const field = screen.getByLabelText("Scadenza di Total 0%");
    fireEvent.change(field, { target: { value: "2026-10-05" } });
    fireEvent.blur(field);
    expect(onExpiry).toHaveBeenCalledWith("2026-10-05");
  });

  it("una voce finita dice «Finito» e offre «In lista»", () => {
    const { onRestock } = renderRow({ status: "finished" });
    expect(screen.getByText("Finito")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "In lista" }));
    expect(onRestock).toHaveBeenCalled();
  });

  it("se è già in lista non offre di rimettercela", () => {
    renderRow({ status: "finished" }, { listed: true });
    expect(screen.queryByRole("button", { name: "In lista" })).toBeNull();
    expect(screen.getByText("Già in lista")).toBeDefined();
  });

  it("una voce non finita non offre «In lista»", () => {
    renderRow({ status: "low" });
    expect(screen.queryByRole("button", { name: "In lista" })).toBeNull();
  });

  it("la ✕ è di sola icona e nomina la voce", () => {
    const { onRemove } = renderRow();
    fireEvent.click(screen.getByRole("button", { name: "Togli Total 0% dalla dispensa" }));
    expect(onRemove).toHaveBeenCalled();
  });

  it("mentre una scrittura è in volo i controlli sono spenti", () => {
    renderRow({ status: "finished" }, { busy: true });
    for (const name of ["Disponibile", "Quasi finito", "Finito"]) {
      expect(screen.getByRole("radio", { name }).hasAttribute("disabled")).toBe(true);
    }
    expect(screen.getByRole("button", { name: "In lista" }).hasAttribute("disabled")).toBe(true);
    expect(screen.getByRole("button", { name: "Togli Total 0% dalla dispensa" }).hasAttribute("disabled")).toBe(true);
  });

  it("una scrittura fallita lo dice nella riga", () => {
    renderRow({}, { failed: true });
    expect(screen.getByRole("alert").textContent).toContain("Riprova");
  });

  it("con reveal si porta in vista e lo dice", () => {
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    const { onRevealed } = renderRow({}, { reveal: true });
    expect(scroll).toHaveBeenCalled();
    expect(onRevealed).toHaveBeenCalled();
  });
});
```

Nel file ci sono già i test esistenti di Invio, uscita senza cambiamenti, campo svuotato → `null`, e scrittura rifiutata. Vanno riportati qui dentro, adattati alla riga, e tolti da `PantryScreen.test.tsx`: sono comportamenti della riga.

- [ ] **Step 2: Far girare i test e vederli fallire**

Run: `npx vitest run src/features/pantry/PantryRow.test.tsx`
Expected: FAIL.

- [ ] **Step 3: Riscrivere `PantryRow.tsx`**

```tsx
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { StockGauge } from "../../components/ui/StockGauge";
import { IconListCheck, IconShoppingCartPlus, IconX } from "../../components/ui/icons";
import { EXPIRY_INPUT_MAX, expiryText } from "./expiryLabels";
import { itemLabel } from "./pantryView";
import { ingredientPath, productPath } from "../registry/origin";
import { revealAtTop } from "../../lib/revealAtTop";
import type { PantryItem, PantryStatus } from "../../domain/types";

/** Dove porta il nome: alla scheda del prodotto se la voce ne ha uno, a quella
 * dell'ingrediente se è sfusa (spec S9 §6.5). */
function registryPath(item: PantryItem): string {
  return item.product_id
    ? productPath(item.product_id, "dispensa")
    : ingredientPath(item.ingredient_id, "dispensa");
}

const EXPIRY_TONE_TEXT = {
  soon: "font-medium text-expiry",
  expired: "font-semibold text-expiry",
} as const;

/** Una riga della dispensa (spec T3 §4.1): l'ingrediente, sotto il prodotto e la
 * scadenza, a destra le tacche e la ✕. Il nome è l'ingrediente e non il prodotto
 * (dal giro): così un aggancio sbagliato, il parmigiano sotto «burro», si vede proprio
 * qui, dove si corregge (S9). */
export function PantryRow({
  item,
  busy,
  failed,
  listed,
  reveal,
  onStatus,
  onRemove,
  onRestock,
  onExpiry,
  onRevealed,
}: {
  item: PantryItem;
  busy: boolean;
  failed: boolean;
  listed: boolean;
  reveal: boolean;
  onStatus: (status: PantryStatus) => void;
  onRemove: () => void;
  onRestock: () => void;
  onExpiry: (expiresOn: string | null) => Promise<unknown>;
  onRevealed: () => void;
}) {
  const label = itemLabel(item);
  const [editingExpiry, setEditingExpiry] = useState(false);
  const ref = useRef<HTMLLIElement>(null);

  useEffect(() => {
    if (reveal && ref.current) {
      revealAtTop(ref.current);
      onRevealed();
    }
  }, [reveal, onRevealed]);

  // [qui si riporta com'è il commento lungo che stava sopra `commitExpiry` nella
  // versione precedente: `change` a ogni segmento del campo data, la ragione di
  // `defaultValue`, perché si scrive all'uscita. È la memoria di un difetto misurato]
  async function commitExpiry(value: string) {
    setEditingExpiry(false);
    if (value === (item.expires_on ?? "")) return;
    try {
      await onExpiry(value || null);
    } catch {
      // il guasto lo mostra già l'`Alert` della riga
    }
  }

  const expiry = item.expires_on ? expiryText(item.expires_on, item.expiry) : null;

  return (
    // `scroll-mt-16`: l'intestazione fissa (h-12) più un respiro, come nel dettaglio ricetta
    <li ref={ref} className="scroll-mt-16">
      <div className="flex items-center gap-1">
        <div className="min-w-0 flex-1">
          <Link
            to={registryPath(item)}
            className="flex min-h-11 items-end pb-0.5 font-medium underline decoration-line underline-offset-4"
          >
            {item.ingredient_name}
          </Link>
          <div className="flex min-h-11 flex-wrap items-start gap-x-1.5 pt-0.5 text-xs text-ink-faint">
            <span>{item.product_name ?? "sfuso"}</span>
            <span aria-hidden="true">·</span>
            {editingExpiry ? (
              <span>
                <label htmlFor={`expiry-${item.id}`} className="sr-only">
                  Scadenza di {label}
                </label>
                <input
                  id={`expiry-${item.id}`}
                  type="date"
                  max={EXPIRY_INPUT_MAX}
                  disabled={busy}
                  autoFocus
                  defaultValue={item.expires_on ?? ""}
                  onBlur={(event) => void commitExpiry(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") event.currentTarget.blur();
                  }}
                />
              </span>
            ) : (
              <button
                type="button"
                disabled={busy}
                onClick={() => setEditingExpiry(true)}
                aria-label={expiry ? `Scadenza di ${label}: ${expiry}` : `+ scadenza per ${label}`}
                className={`-mt-0.5 min-h-11 pt-0.5 text-left disabled:opacity-40 ${
                  item.expiry ? EXPIRY_TONE_TEXT[item.expiry] : ""
                }`}
              >
                {expiry ?? "+ scadenza"}
              </button>
            )}
          </div>
        </div>
        <StockGauge status={item.status} itemName={label} disabled={busy} onChange={onStatus} />
        <Button
          variant="ghost"
          icon={IconX}
          label={`Togli ${label} dalla dispensa`}
          onClick={onRemove}
          disabled={busy}
          className="text-ink-faint"
        />
      </div>
      {item.status === "finished" && (
        // «Lo rimetto in lista? Sì / No» aveva bersagli da 35px e non tornava più se
        // ignorato: ora è un pulsante che resta finché serve, e ignorarlo è il «No»
        <div className="flex items-center justify-between gap-2 pb-2">
          <span className="text-sm font-medium text-finished">Finito</span>
          {listed ? (
            <span className="flex items-center gap-1 text-sm text-ink-soft">
              <IconListCheck aria-hidden="true" className="size-4" stroke={1.8} />
              Già in lista
            </span>
          ) : (
            <Button icon={IconShoppingCartPlus} onClick={onRestock} disabled={busy}>
              In lista
            </Button>
          )}
        </div>
      )}
      {failed && <Alert className="pb-2">Non sono riuscito a salvare la modifica. Riprova.</Alert>}
    </li>
  );
}
```

Controllare in `Alert.tsx` che la prop `className` esista (esiste: `className = ""`). Se `Button` non passa `className` al DOM dopo le sue classi, `text-ink-faint` va comunque in coda, come fa già `ActionBar`.

- [ ] **Step 4: Cablare la riga nello schermo**

In `PantryScreen.tsx`, senza toccare ancora la disposizione (Task 4):

1. **Via il cursore.** Sostituire la mutazione `change` con `status`:

```ts
  const status = useMutation({
    mutationFn: ({ id, status }: { id: string; status: PantryStatus }) => patchPantryItem(id, { status }),
    onMutate: ({ id }) => clearFailed(id),
    onSuccess: invalidate,
    onError: (_error, { id }) => markFailed(id),
  });
```

2. **Via la lapide.** Cancellare `withRemoved`, `removed`/`addRemoved`/`clearRemoved`, `undoTimers`, `startUndoTimer`/`stopUndoTimer`, l'effetto di pulizia, la mutazione `undo` e l'import di `UNDO_MS`. `rows` diventa `isError ? [] : items`. L'archiviazione e il suo annulla diventano:

```ts
  const notice = useNotice();

  // L'annulla vive nell'avviso, che è dell'app e non di questo schermo: si può
  // toccare anche dopo essere passati a un'altra scheda. Per questo non è una
  // useMutation (legata al componente) ma una chiamata col queryClient dell'app.
  // Se fallisce, un nuovo avviso lo dice e offre di riprovare: la voce è archiviata
  // davvero, e perderla qui sarebbe il vicolo cieco.
  function undoRemove(item: PantryItem) {
    patchPantryItem(item.id, { archived: false }).then(
      () => queryClient.invalidateQueries({ queryKey: ["pantry"] }),
      () =>
        notice({
          text: `Non sono riuscito a rimettere ${itemLabel(item)} in dispensa.`,
          action: { label: "Riprova", onClick: () => undoRemove(item) },
        })
    );
  }

  const archive = useMutation({
    mutationFn: (item: PantryItem) => patchPantryItem(item.id, { archived: true }),
    onMutate: (item) => clearFailed(item.id),
    onSuccess: (_data, item) => {
      invalidate();
      notice({
        text: `Tolto dalla dispensa: ${itemLabel(item)}`,
        action: { label: "Annulla", onClick: () => undoRemove(item) },
      });
    },
    onError: (_error, item) => markFailed(item.id),
  });
```

3. **Il rientro in lista.** Prende la voce e risponde con l'avviso:

```ts
  const restock = useMutation({
    mutationFn: (item: PantryItem) => restockPantryItem(item.id),
    onMutate: (item) => clearFailed(item.id),
    onSuccess: (result, item) => {
      queryClient.invalidateQueries({ queryKey: ["shopping-list"] });
      notice({ text: result.added ? `Rimesso in lista: ${item.ingredient_name}` : "Era già in lista." });
    },
    onError: (_error, item) => markFailed(item.id),
  });
```

4. **Già in lista.** Dalla query `["shopping-list"]` che lo schermo legge già:

```ts
  // gli ingredienti con una voce aperta in lista: per loro «In lista» non serve
  // (dal giro: «la domanda del rientro compare anche per ciò che è già in lista»)
  const listedIngredients = new Set(
    (shopping ?? [])
      .filter((entry) => entry.status === "pending" || entry.status === "checked")
      .map((entry) => entry.ingredient_id)
  );
```

5. **`busyIds`**: `status.variables.id`, `archive.variables.id`, `restock.variables.id`, `expiry.variables.id`.

6. **La riga nel `map`**:

```tsx
                  <PantryRow
                    key={item.id}
                    item={item}
                    busy={busyIds.has(item.id)}
                    failed={failedIds.has(item.id)}
                    listed={listedIngredients.has(item.ingredient_id)}
                    reveal={false}
                    onStatus={(next) => status.mutate({ id: item.id, status: next })}
                    onRemove={() => archive.mutate(item)}
                    onRestock={() => restock.mutate(item)}
                    onExpiry={(expiresOn) => expiry.mutateAsync({ id: item.id, expiresOn })}
                    onRevealed={() => {}}
                  />
```

   e l'`<ul>` perde `divide-y divide-line`.

7. **Il resto:**
   - in `api.ts`, `patchPantryItem` perde il campo `fill_percent` dal tipo del corpo;
   - in `types.ts`, il commento di `fill_percent` diventa: «La posizione del cursore di prima di T3. Dalla Consegna 1 nessun client la scrive più — le tacche mandano `status`, e `set_status` la azzera — ma la colonna resta, annullabile.»;
   - cancellare i file elencati in **Delete**, e da `expiryLabels.ts` `formatExpiry` ed `EXPIRY_TONE` con i loro test;
   - aggiustare il commento in `CookSheet.test.tsx` che cita `FillSlider`, per esempio «Lo stesso standard da pollice delle tacche della dispensa».

   Prima di cancellare, controllare che niente importi più quei file:

   ```bash
   grep -rn "FillSlider\|fillZones\|StatusChip\|ExpiryChip\|formatExpiry\|EXPIRY_TONE" frontend/src
   ```

   Deve restare solo qualche commento. Se `Chip.tsx` resta senza chi lo usa, **non** si cancella: è una primitiva della spec §3.5, e la usano le consegne dopo.

- [ ] **Step 5: Riscrivere `PantryScreen.test.tsx` per il comportamento nuovo**

- `renderScreen` e `renderScreenConRetryVero` avvolgono lo schermo in `<NoticeProvider>` (da `../../components/ui/NoticeProvider`): senza, gli avvisi non si vedono.
- **Si tolgono** i test di cursore, lapide, «Lo rimetto in lista?» e scadenza. I titoli da togliere, alle righe ~102–130 e ~281–830 di oggi:
  - «spostare il cursore…» e «una voce che non ha mai visto il cursore…»;
  - «la X toglie la voce… lascia un annulla al suo posto», «passati i secondi dell'annulla…», «l'annulla che fallisce lascia una lapide…», «un ricaricamento fallito non si porta via la lapide…», «due rimozioni vicine…», «la lapide sopravvive…»;
  - «portato a zero il cursore chiede…», «anche il giallo chiede…», «finire una voce non scrive in lista da sé…», «se era già in lista lo dice…», «il no chiude la domanda…», «un rientro in lista che fallisce…», «due voci portate a zero…», «annullare un'archiviazione non fa ricomparire…», «mentre il rientro in lista è in volo…», «una mutazione su un'altra riga non sblocca il «Sì»…»;
  - i test della scadenza, che sono passati in `PantryRow.test.tsx`.

  I test di prodotto e marca, di «nome e marca restano due parole» e di «il tocco è sul nome e non sulla riga» si adattano alla riga nuova: il link è il nome dell'ingrediente e il prodotto sta sotto. Oppure si tolgono se `PantryRow.test.tsx` li copre già.
- **Si aggiungono** questi test (scritti per lo schermo, con `stubRoutedFetch`):

```tsx
  it("toccare una tacca manda lo stato, non la posizione", async () => {
    const fetchSpy = stubRoutedFetch((path, init) =>
      init?.method === "PATCH" ? [{ ...ITEMS[0], status: "low" }, 200] : path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]
    );
    renderScreen();
    const gauge = await screen.findByRole("radiogroup", { name: "Quanto resta di Total 0%" });
    fireEvent.click(within(gauge).getByRole("radio", { name: "Quasi finito" }));
    await waitFor(() => {
      const patch = fetchSpy.mock.calls.find(([, init]) => init?.method === "PATCH");
      expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ status: "low" });
    });
  });

  it("la ✕ toglie la voce e l'avviso offre «Annulla», che la disarchivia", async () => {
    const fetchSpy = stubRoutedFetch((path, init) =>
      init?.method === "PATCH" ? [ITEMS[0], 200] : path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]
    );
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli Total 0% dalla dispensa" }));
    expect(await screen.findByText("Tolto dalla dispensa: Total 0%")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Annulla" }));
    await waitFor(() => {
      const bodies = fetchSpy.mock.calls
        .filter(([, init]) => init?.method === "PATCH")
        .map(([, init]) => JSON.parse(String(init?.body)));
      expect(bodies).toEqual([{ archived: true }, { archived: false }]);
    });
  });

  it("un annulla che fallisce lo dice nell'avviso e offre di riprovare", async () => {
    let patches = 0;
    stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") {
        patches += 1;
        return patches === 2 ? [{ detail: "no" }, 500] : [ITEMS[0], 200];
      }
      return path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200];
    });
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli Total 0% dalla dispensa" }));
    fireEvent.click(await screen.findByRole("button", { name: "Annulla" }));
    expect(await screen.findByText("Non sono riuscito a rimettere Total 0% in dispensa.")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Riprova" }));
    await waitFor(() => expect(patches).toBe(3));
  });

  it("una ✕ che fallisce lo dice accanto alla voce, e la voce resta", async () => {
    stubRoutedFetch((path, init) =>
      init?.method === "PATCH" ? [{ detail: "no" }, 500] : path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]
    );
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli Total 0% dalla dispensa" }));
    expect(await screen.findByRole("alert")).toBeDefined();
    // i due barattoli di yogurt greco sono ancora lì tutti e due
    expect(screen.getAllByRole("link", { name: "yogurt greco" })).toHaveLength(2);
  });

  it("«In lista» su una voce finita la rimette in lista e lo dice", async () => {
    const finished = [{ ...ITEMS[2], status: "finished" }];
    const fetchSpy = stubRoutedFetch((path, init) =>
      path.includes("/restock") ? [{ added: true }, 200] : path.includes("/shopping-list") ? [[], 200] : [finished, 200]
    );
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "In lista" }));
    expect(await screen.findByText("Rimesso in lista: mela")).toBeDefined();
    expect(fetchSpy.mock.calls.some(([url, init]) => String(url).includes("/pantry/p3/restock") && init?.method === "POST")).toBe(true);
  });

  it("se era già in lista, l'avviso lo dice", async () => {
    const finished = [{ ...ITEMS[2], status: "finished" }];
    stubRoutedFetch((path) =>
      path.includes("/restock") ? [{ added: false }, 200] : path.includes("/shopping-list") ? [[], 200] : [finished, 200]
    );
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "In lista" }));
    expect(await screen.findByText("Era già in lista.")).toBeDefined();
  });

  it("una voce finita che ha già una voce aperta in lista non offre «In lista»", async () => {
    const finished = [{ ...ITEMS[2], status: "finished" }];
    const list = [{ id: "s1", raw_text: "mela", ingredient_id: "i2", ingredient_name: "mela",
      ingredient_category: "frutta", ingredient_kind: "food", status: "pending", reason: "manual",
      created_at: "2026-09-11T10:00:00Z" }];
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [list, 200] : [finished, 200]));
    renderScreen();
    expect(await screen.findByText("Già in lista")).toBeDefined();
    expect(screen.queryByRole("button", { name: "In lista" })).toBeNull();
  });
```

Il test di «mentre una modifica è in volo i controlli di quella voce sono bloccati» si riscrive sulle tacche: una PATCH che non risponde (una `Promise` mai risolta) lascia spente le tacche e la ✕ di **quella** riga, e accese quelle di un'altra.

Le URL delle rotte vanno controllate in `fetchShoppingList` e `restockPantryItem`: `path.includes("/shopping-list")` deve prendere la GET della lista, e `"/restock"` il POST del rientro. Se `fetchShoppingList` ha una query string, `includes` la regge.

- [ ] **Step 6: Far girare tutto**

Run: `npx vitest run && npm run lint && npm run typecheck`
Expected: tutto verde.

- [ ] **Step 7: Commit**

```bash
git add -A frontend/src
git commit -m "dispensa: le tacche al posto del cursore, «In lista» sulle finite, e la ✕ con l'avviso"
```

---

### Task 4: Lo schermo nuovo — barra, aggiunta, riepilogo, sezioni

**Files:**
- Modify: `frontend/src/features/pantry/PantryScreen.tsx`
- Modify: `frontend/src/features/pantry/PantryScreen.test.tsx`

**Interfaces:**
- Consumes:
  - dal Task 1: `matchesQuery`, `isExpiring`, `expiryCounts`, `expirySummary`, `groupForDisplay`;
  - dal Task 2: `IngredientPicker` con `initialTerm` e `autoFocus`;
  - dal Task 3: `PantryRow` con `reveal` e `onRevealed`;
  - dalla Consegna 0: `ActionBar({ inputLabel, placeholder, addLabel, value, onChange, onAdd, leadingIcon })`, `Section({ category, count, children })`, `EmptyState({ title, body, action })`, `ErrorState({ message, onRetry, retrying })`, `Button`, e le icone `IconSearch`, `IconCalendarEvent`, `IconX` e `IconPlus`.

**Com'è fatto lo schermo, dall'alto:**
1. `SectionEntryCard` «Sistema la spesa»: com'è oggi.
2. **La barra.** `ActionBar` con:
   - `inputLabel="Cerca o aggiungi in dispensa"`, `placeholder="Cerca o aggiungi"`, `addLabel="Aggiungi in dispensa"`;
   - `leadingIcon={IconSearch}`, `value={query}`, `onChange={setQuery}`;
   - `onAdd` che apre l'aggiunta con quel testo.

   Scrivere filtra le righe mentre si scrive (S11).
3. **L'aggiunta**, solo se aperta: una scheda (`rounded-2xl bg-card p-3`) con:
   - il `IngredientPicker`, con `key` = il testo d'apertura, `label="Quale ingrediente?"`, `accessibleLabel="Ingrediente da mettere in dispensa"`, `initialTerm`, `autoFocus` e il `failureNote` di oggi;
   - accanto, la ✕ `Button variant="ghost" icon={IconX} label="Chiudi l'aggiunta"`;
   - sotto, «Entra come disponibile e senza marca.» (`text-xs text-ink-faint`);
   - e, se l'aggiunta fallisce, l'`Alert` di oggi.
4. **Il riepilogo**, solo se `expirySummary(...)` non è `null`:
   - un `<button aria-pressed>` alto almeno 44 px (`min-h-11`), largo quanto la colonna, `rounded-2xl`;
   - `IconCalendarEvent` a sinistra, il testo del riepilogo, e quando è premuto una `IconX` decorativa a destra (`aria-hidden`) che dice che si richiude;
   - spento ha la tinta `bg-expiry-tint text-expiry`, premuto il pieno `bg-expiry text-on-expiry`;
   - premuto, mostra solo le voci `isExpiring`. Il nome accessibile non cambia fra i due stati: lo stato lo dice `aria-pressed`.
5. **Caricamento**: «Carico…» come oggi.
6. **Errore**: `ErrorState` con `message="Non sono riuscito a caricare la dispensa."`, `onRetry={() => void refetch()}` e `retrying={isFetching}`.
7. **Vuoto:**
   - con niente in dispensa e nessun filtro: `EmptyState` con `title="Dispensa vuota"` e `body="Sistema la spesa, oppure scrivi qui sopra quello che hai in casa e tocca +."`;
   - con un testo che non trova niente: `EmptyState` con `title={`Niente in dispensa per «${query.trim()}»`}` e come `action` un `Button icon={IconPlus}` «Aggiungi «…»» che apre l'aggiunta con quel testo. È il «se non c'è mi offre di aggiungerlo» di S11.
8. **Le sezioni**:

```tsx
{groupForDisplay(visible).map(([category, rows]) => (
  <Section key={category} category={category} count={rows.length}>
    <ul>{rows.map((item) => <PantryRow … />)}</ul>
  </Section>
))}
```

Tutto il contenuto sotto il titolo sta in un `<div className="flex flex-col gap-3">`: `Screen` non spazia i figli da sé.

**Lo stato nuovo nello schermo:**

```ts
  const [query, setQuery] = useState("");
  const [expiringOnly, setExpiringOnly] = useState(false);
  // il testo con cui si è aperta l'aggiunta; `null` quando è chiusa
  const [adding, setAdding] = useState<string | null>(null);
  // la voce appena aggiunta, da portare in vista quando arriva nell'elenco
  const [revealId, setRevealId] = useState<string | null>(null);
  const clearReveal = useCallback(() => setRevealId(null), []);
```

`onRevealed={clearReveal}` va passato stabile (`useCallback`), perché la riga lo mette nelle dipendenze del suo effetto. Nella riga: `reveal={item.id === revealId}`.

**L'aggiunta riuscita** (resto di T4: «svuota il campo e basta, e la riga nuova è venti schermate più in basso»):

```ts
  const add = useMutation({
    mutationFn: (ingredient: Ingredient) => addPantryItem(ingredient.id),
    onMutate: () => setAddFailed(false),
    onSuccess: (created, ingredient) => {
      invalidate();
      setAdding(null);
      // la barra torna vuota e il riepilogo si spegne: la riga nuova deve potersi vedere
      setQuery("");
      setExpiringOnly(false);
      setRevealId(created.id);
      notice({ text: `In dispensa: ${ingredient.display_name}` });
    },
    onError: () => setAddFailed(true),
  });
```

**Cosa si vede:**

```ts
  const summary = isError ? null : expirySummary(expiryCounts(items));
  // premuto su un riepilogo che non c'è più (l'ultima voce in scadenza è stata tolta)
  // non filtra: una dispensa vuota per un filtro invisibile sarebbe una bugia
  const showExpiring = expiringOnly && summary !== null;
  const visible = (isError ? [] : items)
    .filter((item) => matchesQuery(item, query))
    .filter((item) => !showExpiring || isExpiring(item));
```

- [ ] **Step 1: Scrivere i test dello schermo**

In `PantryScreen.test.tsx`:
- si tolgono i test dell'aggiunta vecchia («si può aggiungere in dispensa…», «un'aggiunta rifiutata…», «mentre l'aggiunta è in volo…») e i due del vuoto e dell'errore di caricamento;
- si scrivono questi. Il seme dei dati mette `ITEMS[2]` (mela) in scadenza (`expiry: "soon"`).

```tsx
  it("scrivere nella barra filtra le righe, anche per prodotto e marca", async () => {
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "fage" } });
    expect(screen.getByText("Total 0%")).toBeDefined();
    expect(screen.queryByText("Pesca")).toBeNull();
    expect(screen.queryByRole("link", { name: "mela" })).toBeNull();
  });

  it("un testo che non trova niente offre di aggiungerlo", async () => {
    stubRoutedFetch((path) =>
      path.includes("/shopping-list") ? [[], 200] : path.includes("/ingredients") ? [[], 200] : [ITEMS, 200]
    );
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "sale" } });
    expect(screen.getByText("Niente in dispensa per «sale»")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi «sale»" }));
    expect(screen.getByLabelText("Ingrediente da mettere in dispensa")).toHaveProperty("value", "sale");
  });

  it("il + apre l'aggiunta con il testo della barra, e scegliere mette in dispensa", async () => {
    const created = { ...ITEMS[2], id: "p9" };
    const fetchSpy = stubRoutedFetch((path, init) => {
      if (path.includes("/shopping-list")) return [[], 200];
      if (path.includes("/ingredients")) return [[MELA], 200];
      if (init?.method === "POST") return [created, 201];
      return [ITEMS, 200];
    });
    Element.prototype.scrollIntoView = vi.fn();
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "mel" } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    fireEvent.click(await screen.findByRole("option", { name: "Mela" }));
    expect(await screen.findByText("In dispensa: Mela")).toBeDefined();
    const post = fetchSpy.mock.calls.find(([, init]) => init?.method === "POST");
    expect(JSON.parse(String(post?.[1]?.body))).toEqual({ ingredient_id: "i2", status: "available" });
    // l'aggiunta si chiude e la barra torna vuota
    expect(screen.queryByLabelText("Ingrediente da mettere in dispensa")).toBeNull();
    expect(screen.getByLabelText("Cerca o aggiungi in dispensa")).toHaveProperty("value", "");
  });

  it("un'aggiunta rifiutata lo dice nella scheda dell'aggiunta, che resta aperta", async () => {
    stubRoutedFetch((path, init) => {
      if (path.includes("/shopping-list")) return [[], 200];
      if (path.includes("/ingredients")) return [[MELA], 200];
      if (init?.method === "POST") return [{ detail: "no" }, 500];
      return [ITEMS, 200];
    });
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "mel" } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    fireEvent.click(await screen.findByRole("option", { name: "Mela" }));
    expect(await screen.findByText("Non sono riuscito ad aggiungere la voce in dispensa. Riprova.")).toBeDefined();
    expect(screen.getByLabelText("Ingrediente da mettere in dispensa")).toBeDefined();
  });

  it("la ✕ dell'aggiunta la chiude", async () => {
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    fireEvent.change(screen.getByLabelText("Cerca o aggiungi in dispensa"), { target: { value: "x" } });
    fireEvent.click(screen.getByRole("button", { name: "Aggiungi in dispensa" }));
    fireEvent.click(screen.getByRole("button", { name: "Chiudi l'aggiunta" }));
    expect(screen.queryByLabelText("Ingrediente da mettere in dispensa")).toBeNull();
  });

  it("il riepilogo conta le voci in scadenza e, toccato, mostra solo quelle", async () => {
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [ITEMS, 200]));
    renderScreen();
    const summary = await screen.findByRole("button", { name: "1 in scadenza questa settimana" });
    expect(summary.getAttribute("aria-pressed")).toBe("false");
    fireEvent.click(summary);
    expect(summary.getAttribute("aria-pressed")).toBe("true");
    expect(screen.getByRole("link", { name: "mela" })).toBeDefined();
    expect(screen.queryByText("Total 0%")).toBeNull();
    fireEvent.click(summary);
    expect(screen.getByText("Total 0%")).toBeDefined();
  });

  it("senza scadenze vicine il riepilogo non c'è", async () => {
    const quiet = ITEMS.map((item) => ({ ...item, expires_on: null, expiry: null }));
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [quiet, 200]));
    renderScreen();
    await screen.findByText("Total 0%");
    expect(screen.queryByRole("button", { name: /in scadenza/ })).toBeNull();
  });

  it("una sezione per reparto, con il conteggio, e le finite in fondo", async () => {
    const rows = [
      { ...ITEMS[0], status: "finished" },
      ITEMS[1],
      ITEMS[2],
    ];
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [rows, 200]));
    renderScreen();
    const latticini = await screen.findByRole("region", { name: "Latticini" });
    const links = within(latticini).getAllByRole("link").map((link) => link.getAttribute("href"));
    // Pesca (pr2) prima di Total 0% (pr1), che è finito
    expect(links[0]).toContain("pr2");
    expect(links[1]).toContain("pr1");
    expect(within(latticini).getByText("2")).toBeDefined();
    expect(screen.getByRole("region", { name: "Frutta" })).toBeDefined();
  });

  it("dice cosa fare quando la dispensa è vuota", async () => {
    stubRoutedFetch((path) => (path.includes("/shopping-list") ? [[], 200] : [[], 200]));
    renderScreen();
    expect(await screen.findByRole("heading", { name: "Dispensa vuota" })).toBeDefined();
  });

  it("un caricamento fallito non si traveste da dispensa vuota, e offre «Riprova»", async () => {
    let calls = 0;
    stubRoutedFetch((path) => {
      if (path.includes("/shopping-list")) return [[], 200];
      calls += 1;
      return calls === 1 ? [{ detail: "no" }, 500] : [ITEMS, 200];
    });
    renderScreen();
    expect(await screen.findByText("Non sono riuscito a caricare la dispensa.")).toBeDefined();
    expect(screen.queryByRole("heading", { name: "Dispensa vuota" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Riprova" }));
    expect(await screen.findByText("Total 0%")).toBeDefined();
  });
```

Controllare la rotta della ricerca d'ingredienti in `searchIngredients` (`frontend/src/features/shopping-list/api.ts`) e adattare `path.includes("/ingredients")`. Il nome della regione viene da `Section`, che mette la maiuscola al reparto («latticini» → «Latticini»).

- [ ] **Step 2: Far girare i test e vederli fallire**

Run: `npx vitest run src/features/pantry/PantryScreen.test.tsx`
Expected: FAIL sui test nuovi.

- [ ] **Step 3: Riscrivere la disposizione di `PantryScreen.tsx`**

Seguire la descrizione in cima al task:
- togliere `Card`, `SectionHeading` e il vecchio blocco dell'aggiunta;
- togliere il testo «Dispensa vuota. …» e l'`Alert` del caricamento fallito, che diventano `EmptyState` ed `ErrorState`;
- `useQuery` della dispensa ora prende anche `refetch` e `isFetching`;
- i commenti che spiegano un perché (la chiave condivisa della lista, `failedIds` come insieme, i limiti di `busyIds`) restano;
- quelli che parlano di lapide, cursore o «Sì»/«No» si tolgono con il codice che commentavano.

- [ ] **Step 4: Far girare tutto**

Run: `npx vitest run && npm run lint && npm run typecheck && npm run build`
Expected: tutto verde.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/pantry
git commit -m "dispensa: la barra che cerca e aggiunge, il riepilogo delle scadenze, i reparti in sezioni"
```

---

### Task 5: L'e2e — i percorsi che attraversano la dispensa, e le misure nel browser

**Files:**
- Modify: `frontend/e2e/cooking.spec.ts`, `frontend/e2e/non-alimentari.spec.ts`, `frontend/e2e/anagrafica.spec.ts`, `frontend/e2e/style.spec.ts`

Ogni `spec` che tocca la Dispensa si adatta ai controlli nuovi:
- **`cooking.spec.ts`** (~riga 43): la voce «pomodoro» è disponibile se la tacca «Disponibile» della sua riga è scelta. Il controllo diventa `getByRole("radio", { name: "Disponibile" })` con `aria-checked="true"`, al posto del testo della pastiglia. La riga si trova sempre come `li` con il testo «pomodoro». Il commento si aggiorna.
- **`non-alimentari.spec.ts`** (~righe 44–57):
  - la sezione del reparto ora si chiama «Casa», con la maiuscola di `Section`;
  - il cursore diventa la tacca `radio` «Finito» nel `radiogroup` «Quanto resta di detersivo per i piatti»;
  - «Lo rimetto in lista?» / «Sì» diventa il pulsante «In lista» della riga;
  - l'esito è l'avviso «Rimesso in lista: detersivo per i piatti».
  - La pulizia in fondo (~riga 99) si adatta alla ✕ e all'avviso, se usava la lapide.
- **`anagrafica.spec.ts`** (~righe 68–76 e 132–140):
  - il link della riga ora ha come nome l'ingrediente, non il prodotto. Il percorso tocca il link della riga del prodotto di prova, cioè il link dentro l'`li` che contiene il nome del prodotto;
  - «Tolta dalla dispensa» diventa «Tolto dalla dispensa: <nome>».
- **`style.spec.ts`**:
  - l'aggiunta (~righe 112, 501, 584) passa dalla barra: si scrive nel campo «Cerca o aggiungi in dispensa», si tocca il + «Aggiungi in dispensa», e si sceglie l'opzione nel selettore che si apre (il campo si chiama «Ingrediente da mettere in dispensa» ed è già riempito);
  - la pulizia usa «Tolto dalla dispensa: …»;
  - il test «il cursore della dispensa è un bersaglio da pollice, e le zone si vedono» (~riga 95) diventa «le tacche della dispensa sono bersagli da pollice». Misura:
    - che ognuno dei tre `radio` della riga di prova sia almeno 44×44;
    - che la ✕ della riga sia almeno 44×44;
    - che il pulsante della scadenza («+ scadenza per …») sia almeno 44 px di altezza;
    - che il link del nome e il pulsante della scadenza **non si sovrappongano** (il `bottom` del primo ≤ il `top` del secondo, con i `boundingBox`);
    - e, in chiaro e in scuro, che la tacca accesa stia almeno 3:1 sul fondo `card`: è un segno, non testo (WCAG 1.4.11). Si prendono i colori calcolati della barretta e del fondo, con gli helper già nel file.
  - **Aggiungere** una prova del riepilogo: creare con `page.request` una voce con `expires_on` fra due giorni, e controllare che il pulsante «… in scadenza questa settimana» ci sia, sia alto almeno 44 px, e premuto mostri la voce. La voce poi si archivia nella pulizia, come fanno gli altri test del file.
  - I controlli di contrasto e dei nomi dei pulsanti su `/dispensa`, in chiaro e in scuro, esistono già in `SCHERMATE`. Devono passare con la dispensa **non vuota**: se oggi la misurano vuota, il test del riepilogo o quello delle tacche va messo prima, oppure la voce si crea lì.
  - Anche «nessuno scorrimento orizzontale a 375 px» su `/dispensa` (~riga 637) va misurato con almeno una riga a video.

- [ ] **Step 1: Aggiornare le spec come sopra**

- [ ] **Step 2: Far girare l'e2e intera sullo stack pulito**

Dalla radice del worktree:

```bash
cp .env.example .env
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

Expected: tutte verdi. Oggi sono 29; il numero cambia di quanti test si aggiungono o si fondono, e il rapporto dice quanti sono. **Non** toccare il contenitore `spena-db-1`, che non è di questo stack. Se una prova fallisce, si guarda perché prima di cambiare l'atteso: una misura del browser che cade è quello che questo file esiste per trovare.

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e
git commit -m "e2e: la dispensa con le tacche, «In lista» e l'avviso, e le loro misure nel browser"
```

---

### Task 6: I documenti

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/prossimi-passi.md`

- [ ] **Step 1: `CLAUDE.md`**

Nel paragrafo «No quantities, in the pantry», la frase su `pantry_items.fill_percent` diventa:

> `pantry_items.fill_percent` (0–100, nullable) is not an exception: it was a slider *position* — no unit, nothing to convert — and since T3's first screen (2026-09-28) no client writes it any more: the pantry's three notches send `status` directly, and `set_status` clears the column. It stays in the schema, nullable, with its `PATCH` path (`set_fill`) still accepted by the API and used by nobody. The three statuses stay the only truth the rest of the app reasons on. The reasoning is in the note under D1 of `docs/prossimi-passi.md`; read it before citing this column as a precedent.

- [ ] **Step 2: `docs/prossimi-passi.md`**

- **Sotto D1**: la nota su `fill_percent` si completa con una frase. Dal 2026-09-28 (T3 Consegna 1) le tacche mandano lo stato e nessuno scrive più la colonna. La via `PATCH` di `fill_percent` resta nel backend senza chiamanti, ed è una voce piccola da togliere quando si tocca `api/pantry.py`.
- **S11**: nel titolo, **[FATTO 2026-09-28 — T3 Consegna 1]**. In fondo alla voce, un paragrafo **Fatto:**:
  - la barra «Cerca o aggiungi» filtra per ingrediente, prodotto e marca, senza badare agli accenti;
  - il + apre l'aggiunta con quel testo;
  - un testo che non trova niente offre «Aggiungi «…»».
  - La domanda del TBD («un campo che fa due cose deve dire quale sta facendo») si è chiusa così: il campo filtra sempre, e aggiunge solo il +.
- **T4**: «Aggiungi in dispensa» è fatto. L'avviso «In dispensa: …» e la riga nuova portata in vista con `revealAtTop`. Restano «Metti in dispensa» (Consegna 3) e «Salva nel ricettario».
- **T3**, dopo il paragrafo della Consegna 0: un paragrafo **Consegna 1 (Dispensa) fatta il 2026-09-28, sul ramo `t3-dispensa`, non ancora in produzione**, con:
  - cosa è cambiato (barra, riepilogo, sezioni, righe con ingrediente sopra e prodotto sotto, scadenza relativa, tacche, «In lista», ✕ con l'avviso; escono cursore, lapide e pastiglie);
  - i conti veri della suite: test jsdom e file, e2e;
  - le scelte prese nel piano che Mattia può voler rivedere:
    - «scadeva ieri» / «oltre la scadenza» al posto di «scaduto», per l'accordo;
    - le voci finite fuori dal riepilogo delle scadenze;
    - le date passate da più di un giorno scritte assolute, perché nessuna soglia di giorni entra nel TypeScript;
    - l'avviso che tiene solo l'**ultima** ✕: toglierne due di fila lascia l'annulla solo della seconda. La lapide ne teneva più d'una; la spec ha scelto l'avviso unico, e la prima voce si rimette con il + (sfusa e senza scadenza);
  - **da provare sul telefono**, prima di tutto le tacche col pollice (spec §7, il rischio più grosso): si toccano bene, lo scorrimento che parte da lì non cambia niente, e si capisce che si toccano. Poi il riepilogo, e il campo data nativo del «+ scadenza».
  - Dei tre punti di disegno del tema scuro annotati per questa consegna, uno si chiude: le zone del cursore non ci sono più. Si aggiunge cosa ha misurato l'e2e sulla tacca accesa. Gli altri due (il pulsante primario spento, il velo del ☰) restano, con la nota che non toccano la Dispensa.
- **Nell'esito del giro**, elenco **Dispensa**: segnare chiuse con «*(T3 Consegna 1)*» le righe risolte:
  - righe alte 150 px;
  - il cursore che non dice come si usa;
  - la riga che mostra il prodotto e non l'ingrediente;
  - il «Finito» ignorato;
  - «Sì» e «No» stretti;
  - la lapide che non dice quanto dura;
  - il riepilogo delle scadenze;
  - le date assolute;
  - la domanda del rientro per ciò che è già in lista;
  - le due schede prima della prima riga, ne resta una;
  - la X rossa.
  
  Restano aperte «due confezioni dello stesso prodotto non si distinguono» (la scadenza sotto il prodotto aiuta, ma solo se scritta) e «Aggiungi in dispensa non dice cosa fare se l'ingrediente non c'è» (S3/R12).

- [ ] **Step 3: Il giro finale dei controlli**

Run, da `frontend/`: `npx vitest run && npm run lint && npm run typecheck && npm run build`, poi `grep -rn "emerald\|neutral-" src` (deve restare vuoto).

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/prossimi-passi.md
git commit -m "docs: T3 Consegna 1, la dispensa ridisegnata"
```
