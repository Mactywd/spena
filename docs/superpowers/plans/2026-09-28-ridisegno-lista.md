# T3 Consegna 2 — La Lista ridisegnata: piano di implementazione

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** portare la schermata Lista sulle primitive della Consegna 0: barra «Cosa manca?» con il +, che resta sotto l'intestazione scorrendo; scheda «Sistema la spesa · N nel carrello», uguale in Lista e in Dispensa; sezioni per reparto con le voci nel carrello in fondo; la ✕ con l'avviso «Annulla».

**Architecture:** tutto nel frontend, nessuna rotta nuova e nessuna migrazione: la `PATCH` della lista accetta già di riportare una voce da `archived` a `pending` o `checked`. L'ordine delle voci e la nota della scheda d'ingresso vanno in funzioni pure testate a tabella (`listView.ts`). La scheda d'ingresso diventa un componente solo (`ShoppingEntryCard`) usato da Lista e Dispensa. `AddItemField` passa su `ActionBar`. La riga diventa `ListRow`, e `ShoppingListScreen` compone `Screen`, `Section`, `EmptyState`, `ErrorState` e l'avviso unico (`useNotice`).

**Tech Stack:** React 19, TypeScript, Tailwind 4 (token in `@theme`), TanStack Query 5, react-router 7, Vitest + Testing Library (jsdom), Playwright.

**Spec:** `docs/superpowers/specs/2026-09-28-ridisegno-design.md`, §2, §3.5 e §4.2. Si legge insieme a questo piano.

## Global Constraints

- Tutto il colore passa dai token di `frontend/src/index.css`. Nessuna schermata nomina un colore crudo: `grep -rn "emerald\|neutral-" frontend/src` resta vuoto.
- Le icone si importano solo da `frontend/src/components/ui/icons.ts`.
- Regola delle icone (spec §2): **più pulsanti in gruppo → solo icone; un pulsante da solo → icona e testo.** Ogni pulsante di sola icona ha il nome completo come `aria-label`: `Button` con `icon` e `label`.
- Ogni bersaglio nuovo è almeno 44×44 px. Ogni testo sta sopra 4,5:1, in chiaro e in scuro.
- **Nomi accessibili stabili** (spec §6): il campo resta «Aggiungi alla lista», il pulsante che aggiunge resta «Aggiungi», la ✕ resta «Togli <testo> dalla lista», la casella resta col nome dell'ingrediente abbinato (o il testo scritto, se non è abbinata).
- **S18 non cambia** (spec §4.2): «latte» + Invio si aggancia all'ingrediente, e un ingrediente già da comprare non si doppia: si dice «Era già in lista.».
- **Mai un vicolo cieco.** Ogni scrittura fallita lascia un modo di riprovare, accanto alla voce o nell'avviso. Un caricamento fallito non è una lista vuota, e scrivere resta possibile.
- Le parole a video sono in italiano, gli identificatori in inglese, i commenti in italiano come nel resto del codice.
- **Accordi**: niente participi che concordano con il nome della voce. Si scrive «Tolto dalla lista: kiwi».
- Il type check è `npm run typecheck` (`tsc -b`). **Mai `tsc --noEmit`**: in questo progetto non compila niente ed esce sempre 0.
- Controlli del frontend, da `frontend/`: `npx vitest run`, `npm run lint`, `npm run typecheck`, `npm run build`.
- e2e: stack `spena-e2e` (comandi nel Task 5). Serve un `.env` nella radice del worktree: si copia da `.env.example`, che non ha segreti, e si cancella a fine prova. **Mai copiare il `.env` del checkout principale.**

---

## File toccati

| File | Cosa |
|---|---|
| `frontend/src/features/shopping-list/listView.ts` (nuovo) | `groupForDisplay`, `entryNote` |
| `frontend/src/features/shopping-list/listView.test.ts` (nuovo) | test a tabella |
| `frontend/src/features/shopping-list/ShoppingEntryCard.tsx` (nuovo) | la scheda «Sistema la spesa», una per due schermi |
| `frontend/src/features/shopping-list/ShoppingEntryCard.test.tsx` (nuovo) | test |
| `frontend/src/features/pantry/PantryScreen.tsx` | usa `ShoppingEntryCard` |
| `frontend/src/features/shopping-list/AddItemField.tsx` | su `ActionBar`, appiccicata sotto l'intestazione, «Era già in lista.» nell'avviso |
| `frontend/src/features/shopping-list/AddItemField.test.tsx` | riscritta per il comportamento nuovo |
| `frontend/src/features/shopping-list/ListRow.tsx` (nuovo) | la riga |
| `frontend/src/features/shopping-list/ListRow.test.tsx` (nuovo) | test della riga |
| `frontend/src/features/shopping-list/ShoppingListScreen.tsx` | riscritta |
| `frontend/src/features/shopping-list/ShoppingListScreen.test.tsx` | riscritta |
| `frontend/e2e/cooking.spec.ts`, `frontend/e2e/non-alimentari.spec.ts`, `frontend/e2e/style.spec.ts` | il testo della lista vuota; la barra sotto l'intestazione; la ✕ con «Annulla» |
| `docs/prossimi-passi.md` | T3 Consegna 2, osservazioni del giro chiuse |

**Fuori da questa consegna, di proposito:** «C'è una scheda per reparto anche con una voce sola» (dal giro) resta com'è — le sezioni per reparto sono una decisione della spec (§2), e una sezione di una voce è il prezzo di avere la stessa forma sempre. Si scrive nei documenti (Task 6), non si cambia.

---

### Task 1: Le funzioni pure: ordine delle voci e nota della scheda d'ingresso

**Files:**
- Create: `frontend/src/features/shopping-list/listView.ts`
- Create: `frontend/src/features/shopping-list/listView.test.ts`

**Interfaces:**
- Consumes: `ShoppingItem` da `frontend/src/domain/types.ts`.
- Produces:
  - `groupForDisplay(items: ShoppingItem[]): [string | null, ShoppingItem[]][]` — reparti in ordine alfabetico (`localeCompare`), `null` (senza reparto) in fondo; dentro ogni reparto prima le voci `pending`, poi le `checked`, e fra voci dello stesso stato l'ordine d'arrivo.
  - `entryNote(inCart: number | null): string` — `null` → «Metti via quello che hai comprato»; `0` → «Niente nel carrello, per ora»; `n` → «n nel carrello».

- [ ] **Step 1: Scrivere il test che fallisce**

`frontend/src/features/shopping-list/listView.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { entryNote, groupForDisplay } from "./listView";
import type { ShoppingItem } from "../../domain/types";

function item(id: string, category: string | null, status: ShoppingItem["status"] = "pending"): ShoppingItem {
  return {
    id, raw_text: id, ingredient_id: category ? `i-${id}` : null, ingredient_name: category ? id : null,
    ingredient_category: category, ingredient_kind: category ? "food" : null, status,
    reason: "manual", created_at: "2026-09-28T10:00:00Z",
  };
}

const ids = (groups: [string | null, ShoppingItem[]][]) =>
  groups.map(([category, rows]) => [category, rows.map((row) => row.id)]);

describe("groupForDisplay", () => {
  it("i reparti in ordine alfabetico, quello ignoto in fondo", () => {
    const groups = groupForDisplay([item("a", "verdura"), item("b", null), item("c", "bevande")]);
    expect(ids(groups)).toEqual([["bevande", ["c"]], ["verdura", ["a"]], [null, ["b"]]]);
  });

  it("dentro il reparto le voci nel carrello vanno in fondo (dal giro)", () => {
    const groups = groupForDisplay([
      item("uova", "latticini", "checked"),
      item("latte", "latticini"),
      item("burro", "latticini", "checked"),
      item("yogurt", "latticini"),
    ]);
    // prima le da comprare, poi le spuntate; ciascun gruppo nell'ordine d'arrivo
    expect(ids(groups)).toEqual([["latticini", ["latte", "yogurt", "uova", "burro"]]]);
  });

  it("il reparto ignoto segue la stessa regola", () => {
    const groups = groupForDisplay([item("x", null, "checked"), item("y", null)]);
    expect(ids(groups)).toEqual([[null, ["y", "x"]]]);
  });

  it("una lista vuota non ha reparti", () => {
    expect(groupForDisplay([])).toEqual([]);
  });

  it("non tocca l'array che riceve: è la cache di React Query", () => {
    const input = [item("b", "latticini", "checked"), item("a", "latticini")];
    groupForDisplay(input);
    expect(input.map((row) => row.id)).toEqual(["b", "a"]);
  });
});

describe("entryNote", () => {
  it.each([
    [null, "Metti via quello che hai comprato"],
    [0, "Niente nel carrello, per ora"],
    [1, "1 nel carrello"],
    [7, "7 nel carrello"],
  ] as const)("%s → %s", (inCart, note) => {
    expect(entryNote(inCart)).toBe(note);
  });
});
```

- [ ] **Step 2: Farlo fallire**

Run (da `frontend/`): `npx vitest run src/features/shopping-list/listView.test.ts`
Expected: FAIL, `Failed to resolve import "./listView"`.

- [ ] **Step 3: Scrivere il codice**

`frontend/src/features/shopping-list/listView.ts`:

```ts
import type { ShoppingItem } from "../../domain/types";

/** Le voci come la Lista le mostra (spec T3 §4.2): un gruppo per reparto, in ordine
 * alfabetico, e il reparto ignoto in fondo — sono le voci da chiarire. Dentro ogni
 * reparto le voci nel carrello vanno in fondo (dal giro: «le voci spuntate restano in
 * mezzo alle altre»), così quel che manca ancora si legge per primo. Fra voci dello
 * stesso stato l'ordine è quello del server: `sort` è stabile. */
export function groupForDisplay(items: ShoppingItem[]): [string | null, ShoppingItem[]][] {
  const groups = new Map<string | null, ShoppingItem[]>();
  for (const item of items) {
    const key = item.ingredient_category;
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  const rank = (item: ShoppingItem) => (item.status === "checked" ? 1 : 0);
  return [...groups.entries()]
    .sort(([a], [b]) => (a === null ? 1 : b === null ? -1 : a.localeCompare(b)))
    .map(([category, rows]) => [category, [...rows].sort((x, y) => rank(x) - rank(y))]);
}

/** La nota della scheda «Sistema la spesa», la stessa in Lista e in Dispensa (spec
 * §4.2: «Sistema la spesa · N nel carrello»). `null` quando il numero non si conosce —
 * la lista non è ancora arrivata, o non è arrivata affatto: allora non si dice niente
 * del suo contenuto, perché «niente nel carrello» sarebbe una bugia, e la strada resta
 * aperta (D3 di `docs/prossimi-passi.md`). */
export function entryNote(inCart: number | null): string {
  if (inCart === null) return "Metti via quello che hai comprato";
  if (inCart === 0) return "Niente nel carrello, per ora";
  return `${inCart} nel carrello`;
}
```

- [ ] **Step 4: Farlo passare**

Run: `npx vitest run src/features/shopping-list/listView.test.ts`
Expected: PASS, 9 test.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/features/shopping-list/listView.ts frontend/src/features/shopping-list/listView.test.ts
git commit -m "lista: l'ordine delle voci e la nota della scheda d'ingresso, in funzioni pure"
```

---

### Task 2: Una scheda «Sistema la spesa» per due schermi

La scheda d'ingresso è uguale in Lista e in Dispensa, e il giro l'ha segnato fra le cose da non rifare via: oggi è scritta due volte, con la stessa nota calcolata due volte. Diventa un componente solo, con la nota nuova della spec.

**Files:**
- Create: `frontend/src/features/shopping-list/ShoppingEntryCard.tsx`
- Create: `frontend/src/features/shopping-list/ShoppingEntryCard.test.tsx`
- Modify: `frontend/src/features/pantry/PantryScreen.tsx` (il blocco `<SectionEntryCard … />` e il `checkedCount` che lo nutre)

**Interfaces:**
- Consumes: `entryNote` (Task 1); `SectionEntryCard` da `frontend/src/components/ui/SectionEntryCard.tsx` (props `to`, `title`, `note`, `pending`).
- Produces: `ShoppingEntryCard({ items, failed }: { items: ShoppingItem[] | undefined; failed: boolean })`. Il Task 4 lo usa in `ShoppingListScreen`.

- [ ] **Step 1: Scrivere il test che fallisce**

`frontend/src/features/shopping-list/ShoppingEntryCard.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { ShoppingEntryCard } from "./ShoppingEntryCard";
import type { ShoppingItem } from "../../domain/types";

function item(id: string, status: ShoppingItem["status"]): ShoppingItem {
  return {
    id, raw_text: id, ingredient_id: null, ingredient_name: null, ingredient_category: null,
    ingredient_kind: null, status, reason: "manual", created_at: "2026-09-28T10:00:00Z",
  };
}

function renderCard(items: ShoppingItem[] | undefined, failed = false) {
  return render(
    <MemoryRouter>
      <ShoppingEntryCard items={items} failed={failed} />
    </MemoryRouter>
  );
}

describe("ShoppingEntryCard", () => {
  it("porta a /sistema e conta quel che è nel carrello", () => {
    renderCard([item("a", "checked"), item("b", "pending"), item("c", "checked")]);
    const link = screen.getByRole("link", { name: /Sistema la spesa/ });
    expect(link.getAttribute("href")).toBe("/sistema");
    expect(screen.getByText("2 nel carrello")).toBeDefined();
  });

  it("resta anche con il carrello vuoto, e lo dice (D3)", () => {
    renderCard([item("b", "pending")]);
    expect(screen.getByText("Niente nel carrello, per ora")).toBeDefined();
  });

  it("finché la lista non è arrivata non dice niente del suo contenuto", () => {
    renderCard(undefined);
    expect(screen.getByText("Metti via quello che hai comprato")).toBeDefined();
  });

  it("a lista fallita non conta i dati vecchi, e la strada resta aperta", () => {
    renderCard([item("a", "checked")], true);
    expect(screen.getByText("Metti via quello che hai comprato")).toBeDefined();
    expect(screen.queryByText("1 nel carrello")).toBeNull();
    expect(screen.getByRole("link", { name: /Sistema la spesa/ })).toBeDefined();
  });
});
```

- [ ] **Step 2: Farlo fallire**

Run: `npx vitest run src/features/shopping-list/ShoppingEntryCard.test.tsx`
Expected: FAIL, `Failed to resolve import "./ShoppingEntryCard"`.

- [ ] **Step 3: Scrivere il componente**

`frontend/src/features/shopping-list/ShoppingEntryCard.tsx`:

```tsx
import { SectionEntryCard } from "../../components/ui/SectionEntryCard";
import { entryNote } from "./listView";
import type { ShoppingItem } from "../../domain/types";

/** L'ingresso a «Sistema la spesa», in cima a Lista e a Dispensa. Uno solo per i due
 * schermi: il giro l'ha trovato uguale nei due posti e da tenere così, e due copie della
 * stessa scheda si scollano da sole. Riceve la lista già chiesta dallo schermo — la
 * chiave `["shopping-list"]` è una sola, e la cache anche.
 *
 * `failed` vince sui dati: dopo un aggiornamento fallito React Query tiene quelli
 * vecchi, e contarli direbbe un carrello che forse non c'è più. */
export function ShoppingEntryCard({
  items,
  failed,
}: {
  items: ShoppingItem[] | undefined;
  failed: boolean;
}) {
  const inCart =
    failed || items === undefined ? null : items.filter((item) => item.status === "checked").length;
  return (
    <SectionEntryCard
      to="/sistema"
      title="Sistema la spesa"
      note={entryNote(inCart)}
      pending={inCart !== null && inCart > 0}
    />
  );
}
```

- [ ] **Step 4: Farlo passare**

Run: `npx vitest run src/features/shopping-list/ShoppingEntryCard.test.tsx`
Expected: PASS, 4 test.

- [ ] **Step 5: La Dispensa usa la stessa scheda**

In `frontend/src/features/pantry/PantryScreen.tsx`:

1. Togli l'import di `SectionEntryCard` e aggiungi:
   ```tsx
   import { ShoppingEntryCard } from "../shopping-list/ShoppingEntryCard";
   ```
2. Togli la riga
   ```tsx
   const checkedCount = (shopping ?? []).filter((item) => item.status === "checked").length;
   ```
   e aggiorna il commento sopra la query `shopping` togliendo la frase sul conteggio: la nota la decide `ShoppingEntryCard`.
3. Sostituisci l'intero blocco `<SectionEntryCard to="/sistema" … pending={checkedCount > 0} />` con:
   ```tsx
   <ShoppingEntryCard items={shopping} failed={isShoppingError} />
   ```

Poi controlla che nessun test o e2e cerchi le note vecchie:

Run (dalla radice del worktree): `grep -rn "di spuntato\|voci spuntate da\|voce spuntata da" frontend/src frontend/e2e`
Expected: solo `frontend/src/features/shopping-list/ShoppingListScreen.tsx` e `ShoppingListScreen.test.tsx` (li riscrive il Task 4) e `frontend/src/components/ui/SectionEntryCard.test.tsx`, che passa stringhe sue al primitivo e resta com'è.

- [ ] **Step 6: Controlli**

Run (da `frontend/`): `npx vitest run src/features/pantry src/features/shopping-list/ShoppingEntryCard.test.tsx && npm run lint && npm run typecheck`
Expected: tutto verde.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/shopping-list/ShoppingEntryCard.tsx frontend/src/features/shopping-list/ShoppingEntryCard.test.tsx frontend/src/features/pantry/PantryScreen.tsx
git commit -m "lista, dispensa: una scheda «Sistema la spesa» sola, che conta quel che è nel carrello"
```

---

### Task 3: La barra «Cosa manca?», sotto l'intestazione e non sopra

**Files:**
- Modify: `frontend/src/features/shopping-list/AddItemField.tsx` (riscritto)
- Modify: `frontend/src/features/shopping-list/AddItemField.test.tsx` (riscritto)

**Interfaces:**
- Consumes: `ActionBar` da `frontend/src/components/ui/ActionBar.tsx` (props `inputLabel`, `placeholder`, `addLabel`, `value`, `onChange`, `onAdd(text)`; a campo vuoto il + porta il fuoco nel campo e non chiama `onAdd`; `onAdd` riceve il testo già senza spazi ai lati). `useNotice` da `frontend/src/components/ui/noticeContext.ts`. `OptionList`, `Alert`, `searchIngredients`, `useDebounced` come oggi.
- Produces: `AddItemField({ onAdd }: { onAdd: (rawText: string, ingredientId?: string) => Promise<RestockResult> })` — firma invariata. «Era già in lista.» esce dall'avviso unico, non più da un paragrafo sotto il campo.

Perché la barra si sposta: oggi il modulo è `sticky top-0 z-10`, come `AppHeader` (`sticky top-0 z-10 h-12`), e scorrendo la copre (dal giro). Ora è `sticky top-12`, cioè appena sotto l'intestazione alta `h-12`, con `z-5`: sotto l'intestazione anche se un giorno le due si toccassero. `-mx-4 px-4` porta il fondo della barra da bordo a bordo: dentro il `px-4` di `Screen`, le righe si vedrebbero scorrere nei margini ai lati.

- [ ] **Step 1: Riscrivere il test**

Sostituisci tutto `frontend/src/features/shopping-list/AddItemField.test.tsx` con:

```tsx
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryCache, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AddItemField } from "./AddItemField";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import { UnauthorizedError } from "../../api/client";

const POMODORO = { id: "i1", name: "pomodoro", display_name: "Pomodoro", category: "verdura" };
const PORRO = { id: "i9", name: "porro", display_name: "Porro", category: "verdura" };

/** Un'aggiunta riuscita, come la risponde il backend: la voce è nuova (S18). */
const added = () => vi.fn().mockResolvedValue({ added: true });

/** La ricerca dei suggerimenti passa da react-query, quindi il campo vuole il suo
 * provider: un 401 che non arriva alla QueryCache non riporta all'accesso. E
 * «Era già in lista.» esce dall'avviso unico: senza `NoticeProvider` non avrebbe dove
 * comparire. */
function renderField(
  props: { onAdd: (rawText: string, ingredientId?: string) => Promise<{ added: boolean }> },
  queryCache?: QueryCache
) {
  const client = new QueryClient({
    queryCache,
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <NoticeProvider>
        <AddItemField {...props} />
      </NoticeProvider>
    </QueryClientProvider>
  );
}

describe("AddItemField", () => {
  it("il campo dice cosa scriverci, e il + ha il suo nome", () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    renderField({ onAdd: added() });
    expect(screen.getByLabelText("Aggiungi alla lista").getAttribute("placeholder")).toBe("Cosa manca?");
    expect(screen.getByRole("button", { name: "Aggiungi" })).toBeDefined();
  });

  it("suggerisce ingredienti mentre si digita", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify([POMODORO]), { status: 200 })
    ));
    renderField({ onAdd: added() });

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "pomo");
    expect(await screen.findByRole("option", { name: /Pomodoro/ })).toBeDefined();
  });

  it("l'elenco dei suggerimenti ha un nome, che dice di quale campo è", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify([POMODORO]), { status: 200 })
    ));
    renderField({ onAdd: added() });

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "pomo");
    expect(await screen.findByRole("listbox", { name: "Suggerimenti: Aggiungi alla lista" })).toBeDefined();
  });

  it("scegliendo un suggerimento passa l'ingrediente risolto", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify([POMODORO]), { status: 200 })
    ));
    const onAdd = added();
    renderField({ onAdd });

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    expect(onAdd).toHaveBeenCalledWith("pomodoro", "i1");
  });

  it("accetta testo libero con l'Invio, perché non deve bloccare", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    const onAdd = added();
    renderField({ onAdd });

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "quella cosa verde{Enter}");
    await waitFor(() => expect(onAdd).toHaveBeenCalledWith("quella cosa verde", undefined));
  });

  it("e col +: da telefono il tasto invio della tastiera non si vede", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    const onAdd = added();
    renderField({ onAdd });

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "  quella cosa verde  ");
    await userEvent.click(screen.getByRole("button", { name: "Aggiungi" }));
    expect(onAdd).toHaveBeenCalledWith("quella cosa verde", undefined);
  });

  it("il + a campo vuoto non aggiunge niente e porta nel campo", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    const onAdd = added();
    renderField({ onAdd });

    await userEvent.click(screen.getByRole("button", { name: "Aggiungi" }));
    expect(onAdd).not.toHaveBeenCalled();
    expect(document.activeElement).toBe(screen.getByLabelText("Aggiungi alla lista"));
  });

  it("una ricerca lenta e superata non sovrascrive i suggerimenti freschi", async () => {
    // due ricerche in volo insieme: la prima, per "po", risponde dopo la seconda.
    // Senza guardia sull'ordine l'utente vede Porro e sceglie l'ingrediente sbagliato.
    let releaseStale: (response: Response) => void = () => {};
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(
        () => new Promise<Response>((resolve) => { releaseStale = resolve; })
      )
      .mockResolvedValue(new Response(JSON.stringify([POMODORO]), { status: 200 }));
    vi.stubGlobal("fetch", fetchMock);

    renderField({ onAdd: added() });
    const field = screen.getByLabelText("Aggiungi alla lista");

    await userEvent.type(field, "po");
    await waitFor(() => expect(fetchMock).toHaveBeenCalledTimes(1));
    await userEvent.type(field, "mo");
    expect(await screen.findByRole("option", { name: /Pomodoro/ })).toBeDefined();

    releaseStale(new Response(JSON.stringify([PORRO]), { status: 200 }));
    await waitFor(() => expect(screen.getByRole("option", { name: /Pomodoro/ })).toBeDefined());
    expect(screen.queryByRole("option", { name: /Porro/ })).toBeNull();
  });

  it("un'aggiunta fallita non perde il testo scritto", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    const onAdd = vi.fn().mockRejectedValue(new Error("il server non risponde"));
    renderField({ onAdd });

    const field = screen.getByLabelText("Aggiungi alla lista");
    await userEvent.type(field, "quella cosa verde{Enter}");

    expect(await screen.findByRole("alert")).toBeDefined();
    expect(field).toHaveValue("quella cosa verde");
  });

  it("un'aggiunta riuscita svuota il campo, e non dice niente", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    renderField({ onAdd: added() });

    const field = screen.getByLabelText("Aggiungi alla lista");
    await userEvent.type(field, "latte{Enter}");

    await waitFor(() => expect(field).toHaveValue(""));
    expect(screen.queryByText("Era già in lista.")).toBeNull();
  });

  // m10: un 401 durante la ricerca deve arrivare alla QueryCache che App.tsx aggancia
  // al ritorno all'accesso, non morire in un `.catch` locale
  it("una sessione scaduta durante la ricerca arriva alla QueryCache", async () => {
    const onError = vi.fn();
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 401 })));

    renderField({ onAdd: added() }, new QueryCache({ onError }));
    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "pomo");

    await waitFor(() => expect(onError).toHaveBeenCalled());
    expect(onError.mock.calls[0][0]).toBeInstanceOf(UnauthorizedError);
  });

  it("una ricerca che non risponde non blocca il testo libero, e lo dice", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new TypeError("network down")));
    const onAdd = added();
    renderField({ onAdd });

    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "quella cosa verde");
    // per testo e non per ruolo: la regione `status` dell'avviso unico c'è sempre
    expect(await screen.findByText(/autocomplete non risponde/i)).toBeDefined();

    await userEvent.click(screen.getByRole("button", { name: "Aggiungi" }));
    expect(onAdd).toHaveBeenCalledWith("quella cosa verde", undefined);
  });

  // S18: il backend non doppia un ingrediente già da comprare e risponde con la voce
  // che c'era, `added` falso. Non è un errore: lo dice l'avviso unico, con le stesse
  // parole della dispensa quando rimette in lista
  it("se la voce era già in lista lo dice nell'avviso, senza allarmi, e svuota il campo", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("[]", { status: 200 })));
    renderField({ onAdd: vi.fn().mockResolvedValue({ added: false }) });

    const field = screen.getByLabelText("Aggiungi alla lista");
    await userEvent.type(field, "latte{Enter}");

    const status = await screen.findByRole("status");
    await waitFor(() => expect(status).toHaveTextContent("Era già in lista."));
    expect(screen.queryByRole("alert")).toBeNull();
    expect(field).toHaveValue("");
  });
});
```

- [ ] **Step 2: Farlo fallire**

Run: `npx vitest run src/features/shopping-list/AddItemField.test.tsx`
Expected: FAIL — almeno «il campo dice cosa scriverci» (il segnaposto oggi è «Cosa serve?»), «il + a campo vuoto…» (oggi il pulsante è disabilitato a campo vuoto e il fuoco non si sposta) e «…lo dice nell'avviso…» (oggi è un paragrafo).

- [ ] **Step 3: Riscrivere il componente**

Sostituisci tutto `frontend/src/features/shopping-list/AddItemField.tsx` con:

```tsx
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { searchIngredients } from "./api";
import { useDebounced } from "../../hooks/useDebounced";
import { ActionBar } from "../../components/ui/ActionBar";
import { Alert } from "../../components/ui/Alert";
import { OptionList } from "../../components/ui/OptionList";
import { useNotice } from "../../components/ui/noticeContext";
import type { RestockResult } from "../../domain/types";

const DEBOUNCE_MS = 180;

/** La barra in cima alla Lista (spec T3 §4.2): «Cosa manca?» e il +, con i suggerimenti
 * dell'anagrafica sotto. Il testo libero passa sempre, con l'Invio o col +: se coincide
 * con un ingrediente lo aggancia il backend (S18). */
export function AddItemField({
  onAdd,
}: {
  onAdd: (rawText: string, ingredientId?: string) => Promise<RestockResult>;
}) {
  const [text, setText] = useState("");
  const [failed, setFailed] = useState(false);
  const notice = useNotice();
  const term = useDebounced(text, DEBOUNCE_MS).trim();
  // sotto 2 caratteri non vale la pena interrogare il backend: il testo resta libero
  const enabled = term.length >= 2;

  // La ricerca passa da `useQuery`, come in IngredientPicker: il termine sta nella
  // chiave, quindi una risposta superata atterra sotto la propria chiave e non può
  // sovrascrivere suggerimenti più recenti; e un 401 arriva alla QueryCache che
  // App.tsx aggancia al ritorno all'accesso, invece di morire qui dentro.
  const { data: suggestions = [], isError } = useQuery({
    queryKey: ["ingredients", term],
    queryFn: () => searchIngredients(term),
    enabled,
  });

  // sul testo corrente, non sul termine ritardato: svuotando il campo i
  // suggerimenti devono sparire subito, non dopo l'attesa
  const showSuggestions = text.trim().length >= 2;

  async function add(rawText: string, ingredientId?: string) {
    setFailed(false);
    let result: RestockResult;
    try {
      result = await onAdd(rawText, ingredientId);
    } catch {
      // il testo resta nel campo. Svuotarlo prima di sapere com'è andata perde
      // quello che l'utente ha scritto, che è il peggiore dei vicoli ciechi
      setFailed(true);
      return;
    }
    // svuotato anche quando c'era già: quel che si voleva in lista ci sta
    setText("");
    // S18: l'ingrediente era già da comprare e il backend non ha scritto il doppione.
    // Un'informazione, non un errore: l'avviso unico, con le parole della dispensa
    if (!result.added) notice({ text: "Era già in lista." });
  }

  return (
    // Appiccicata appena sotto l'intestazione (`top-12` è l'altezza di AppHeader), non
    // sopra: con `top-0` e lo stesso `z-10` dell'intestazione la copriva scorrendo (dal
    // giro). `-mx-4 px-4` porta il fondo da bordo a bordo, o nei margini di `Screen` le
    // righe si vedrebbero scorrere ai lati della barra.
    <div className="sticky top-12 z-5 -mx-4 bg-page px-4 pt-1 pb-3">
      <ActionBar
        inputLabel="Aggiungi alla lista"
        placeholder="Cosa manca?"
        addLabel="Aggiungi"
        value={text}
        onChange={(value) => {
          setText(value);
          setFailed(false);
        }}
        onAdd={(value) => void add(value, undefined)}
      />
      {failed && (
        <Alert className="pt-2">
          Non sono riuscito ad aggiungere la voce. Il testo è ancora qui: riprova.
        </Alert>
      )}
      {/* una ricerca che non risponde non deve bloccare la scrittura, e nemmeno restare
          muta: il testo libero passa comunque, e va detto che passerà senza ingrediente
          abbinato. `status` e non `alert`: è una rinuncia, non un guasto. L'ambra di
          «quasi finito» vuol dire, nell'app, «funziona, ma non del tutto». */}
      {showSuggestions && isError && (
        <p role="status" className="pt-2 text-sm text-low">
          L'autocomplete non risponde. Puoi aggiungere la voce così com'è: l'ingrediente
          si abbina dopo.
        </p>
      )}
      {showSuggestions && suggestions.length > 0 && (
        <div className="pt-2">
          <OptionList
            options={suggestions}
            fieldLabel="Aggiungi alla lista"
            onPick={(ingredient) => void add(ingredient.name, ingredient.id)}
          />
        </div>
      )}
    </div>
  );
}
```

Nota: `setFailed(false)` nell'`onChange` è nuovo — scrivendo altro, l'avviso del guasto precedente non riguarda più il testo nel campo. Non c'è un test che lo richieda; se il revisore lo trova superfluo si può togliere, ma non va tolto l'avviso stesso.

- [ ] **Step 4: Farlo passare**

Run: `npx vitest run src/features/shopping-list/AddItemField.test.tsx`
Expected: PASS, 13 test.

Se `z-5` non producesse una classe (Tailwind 4 accetta i numeri nudi per `z-*`, ma si verifica): `npm run build` e `grep -o "z-5{[^}]*}" dist/assets/*.css` deve trovare `z-index:5`.

- [ ] **Step 5: Controlli**

Run: `npm run lint && npm run typecheck`
Expected: verdi. `ShoppingListScreen.test.tsx` ha ancora un test su «Era già in lista.» che cercava il paragrafo: lo riscrive il Task 4, e fino ad allora può fallire — annotalo nel report, non correggerlo qui.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/features/shopping-list/AddItemField.tsx frontend/src/features/shopping-list/AddItemField.test.tsx
git commit -m "lista: la barra «Cosa manca?» col +, sotto l'intestazione e non sopra; «Era già in lista.» nell'avviso"
```

---

### Task 4: La riga e lo schermo nuovi — sezioni, voci nel carrello in fondo, ✕ con «Annulla»

**Files:**
- Create: `frontend/src/features/shopping-list/ListRow.tsx`
- Create: `frontend/src/features/shopping-list/ListRow.test.tsx`
- Modify: `frontend/src/features/shopping-list/ShoppingListScreen.tsx` (riscritto)
- Modify: `frontend/src/features/shopping-list/ShoppingListScreen.test.tsx` (riscritto)

**Interfaces:**
- Consumes: `groupForDisplay` (Task 1), `ShoppingEntryCard` (Task 2), `AddItemField` (Task 3); `Section({ category, count, children })` (con `category` `null` scrive «Senza reparto», e il nome del reparto lo mette in maiuscolo: «verdura» → «Verdura»); `Screen`, `EmptyState`, `ErrorState({ message, onRetry, retrying })`, `Button`, `Alert`, `IconX`, `useNotice`; `patchShoppingItem(id, { status })`, `addShoppingItem`, `fetchShoppingList` da `./api`.
- Produces: `ListRow({ item, busy, failed, onToggle, onRemove })`.

Due scelte da conoscere prima di scrivere:

1. **La casella si spegne con `aria-disabled`, non con `disabled`.** Il browser toglie il fuoco a un controllo che diventa `disabled`: chi spunta con la tastiera (spazio) lo perdeva sul `body` appena partiva la `PATCH`. È lo stesso difetto già corretto sulle tacche della dispensa (`StockGauge`) e sul pulsante della scadenza. La casella resta controllata (`checked` dallo stato del server) e l'`onChange` non fa niente mentre `busy`: React la ridisegna com'era.
2. **L'«Annulla» controlla il doppione.** Nei 6 secondi dell'avviso si può riscrivere la stessa cosa dalla barra; rimettere anche la voce tolta farebbe il doppione che S18 esiste per evitare. Se nella cache della lista c'è già un'altra voce aperta con lo stesso ingrediente, l'annulla non scrive e dice «Era già in lista.». Una voce senza ingrediente (testo libero non abbinato) non ha doppioni da controllare.

- [ ] **Step 1: Scrivere il test della riga**

`frontend/src/features/shopping-list/ListRow.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { ListRow } from "./ListRow";
import type { ShoppingItem } from "../../domain/types";

const BASE: ShoppingItem = {
  id: "s1", raw_text: "Total 0%", ingredient_id: "i2", ingredient_name: "yogurt greco",
  ingredient_category: "latticini", ingredient_kind: "food", status: "pending",
  reason: "manual", created_at: "2026-09-28T10:00:00Z",
};

function renderRow(over: Partial<ShoppingItem> = {}, props: { busy?: boolean; failed?: boolean } = {}) {
  const onToggle = vi.fn();
  const onRemove = vi.fn();
  render(
    <ul>
      <ListRow item={{ ...BASE, ...over }} busy={props.busy ?? false} failed={props.failed ?? false}
        onToggle={onToggle} onRemove={onRemove} />
    </ul>
  );
  return { onToggle, onRemove };
}

describe("ListRow", () => {
  it("si legge il testo scritto, e la casella porta il nome dell'ingrediente abbinato", () => {
    renderRow();
    expect(screen.getByText("Total 0%")).toBeDefined();
    expect(screen.getByRole("checkbox", { name: "yogurt greco" })).toBeDefined();
  });

  it("una voce non abbinata porta il testo scritto anche sulla casella", () => {
    renderRow({ ingredient_id: null, ingredient_name: null, raw_text: "cosa verde" });
    expect(screen.getByRole("checkbox", { name: "cosa verde" })).toBeDefined();
  });

  it("toccando il nome la voce si spunta, non solo sulla casella (S17)", () => {
    const { onToggle } = renderRow();
    fireEvent.click(screen.getByText("Total 0%"));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("la nota del rientro si legge, e fa parte del bersaglio che spunta", () => {
    const { onToggle } = renderRow({ reason: "finished_while_cooking" });
    fireEvent.click(screen.getByText("rientrata perché finita cucinando"));
    expect(onToggle).toHaveBeenCalledTimes(1);
  });

  it("la ✕ sta fuori dal bersaglio della spunta: togliere non spunta", () => {
    const { onToggle, onRemove } = renderRow();
    const remove = screen.getByRole("button", { name: "Togli Total 0% dalla lista" });
    expect(remove.closest("label")).toBeNull();
    fireEvent.click(remove);
    expect(onRemove).toHaveBeenCalledTimes(1);
    expect(onToggle).not.toHaveBeenCalled();
  });

  it("una voce nel carrello è spuntata e barrata", () => {
    renderRow({ status: "checked" });
    expect(screen.getByRole("checkbox", { name: "yogurt greco" })).toBeChecked();
    expect(screen.getByText("Total 0%").className).toContain("line-through");
  });

  it("mentre una scrittura è in volo la casella è spenta ma tiene il fuoco", () => {
    const { onToggle, onRemove } = renderRow({}, { busy: true });
    const box = screen.getByRole("checkbox", { name: "yogurt greco" });
    // `aria-disabled` e non `disabled`: un controllo che diventa `disabled` perde il
    // fuoco, e chi spunta con la tastiera lo ritroverebbe sul `body`
    expect(box.hasAttribute("disabled")).toBe(false);
    expect(box).toHaveAttribute("aria-disabled", "true");
    fireEvent.click(box);
    expect(onToggle).not.toHaveBeenCalled();
    expect(box).not.toBeChecked();
    const remove = screen.getByRole("button", { name: "Togli Total 0% dalla lista" });
    expect(remove.hasAttribute("disabled")).toBe(true);
    fireEvent.click(remove);
    expect(onRemove).not.toHaveBeenCalled();
  });

  it("una scrittura fallita lo dice nella riga", () => {
    renderRow({}, { failed: true });
    expect(screen.getByRole("alert").textContent).toContain("riprova");
  });
});
```

- [ ] **Step 2: Farlo fallire**

Run: `npx vitest run src/features/shopping-list/ListRow.test.tsx`
Expected: FAIL, `Failed to resolve import "./ListRow"`.

- [ ] **Step 3: Scrivere la riga**

`frontend/src/features/shopping-list/ListRow.tsx`:

```tsx
import { Alert } from "../../components/ui/Alert";
import { Button } from "../../components/ui/Button";
import { IconX } from "../../components/ui/icons";
import type { ShoppingItem } from "../../domain/types";

// Parziale e tipizzato sull'unione: "manual" non ha nota perché non c'è niente da
// spiegare, e il giorno in cui il backend aggiunge un motivo il compilatore lo dice.
const REASON_HINT: Partial<Record<ShoppingItem["reason"], string>> = {
  finished_while_cooking: "rientrata perché finita cucinando",
  low_while_cooking: "rientrata perché quasi finita cucinando",
};

/** Una voce della lista (spec T3 §4.2): la casella con il testo scritto, la nota del
 * rientro se c'è, e la ✕ a destra. Senza linee fra le righe: le separa la sezione. */
export function ListRow({
  item,
  busy,
  failed,
  onToggle,
  onRemove,
}: {
  item: ShoppingItem;
  busy: boolean;
  failed: boolean;
  onToggle: () => void;
  onRemove: () => void;
}) {
  const checked = item.status === "checked";
  const hint = REASON_HINT[item.reason];
  return (
    <li>
      <div className="flex items-center gap-1">
        {/* S17: in corsia spuntare è il gesto che si fa di più, e il pollice tocca la
            parola, non il quadratino accanto. La label prende casella, nome e nota, ed è
            alta almeno 44px. L'`aria-label` della casella vince sul testo della label: il
            nome accessibile è l'ingrediente abbinato, non «Total 0% rientrata perché…».
            La ✕ sta fuori, bersaglio suo: dentro, un tocco per togliere spunterebbe anche */}
        <label className="flex min-h-11 min-w-0 flex-1 items-center gap-3 py-1.5">
          <input
            type="checkbox"
            aria-label={item.ingredient_name ?? item.raw_text}
            checked={checked}
            // `aria-disabled` e non `disabled`, come le tacche della dispensa: il browser
            // toglie il fuoco a un controllo che diventa `disabled`, e chi spunta con la
            // tastiera lo ritrovava sul `body` appena partiva la PATCH. La casella resta
            // controllata: ignorato il cambio, React la ridisegna com'era
            aria-disabled={busy || undefined}
            onChange={() => {
              if (!busy) onToggle();
            }}
            className="size-5 shrink-0 accent-brand aria-disabled:opacity-40"
          />
          {/* S16: `min-w-0` lascia stringere la colonna sotto la sua parola più lunga, e
              `break-words` spezza un nome che non ci sta: a 375px la riga spingeva la
              pagina di lato */}
          <span className="flex min-w-0 flex-1 flex-col break-words">
            <span className={checked ? "text-ink-faint line-through" : ""}>{item.raw_text}</span>
            {/* visibile, non un tooltip: da telefono non esiste il passaggio del mouse,
                e il motivo per cui una voce è rientrata va letto */}
            {hint && <span className="text-xs text-low">{hint}</span>}
          </span>
        </label>
        <Button
          variant="ghost"
          icon={IconX}
          label={`Togli ${item.raw_text} dalla lista`}
          onClick={onRemove}
          disabled={busy}
        />
      </div>
      {failed && (
        <Alert className="pb-2">
          Non sono riuscito a salvare la modifica. La voce è ancora qui: riprova.
        </Alert>
      )}
    </li>
  );
}
```

- [ ] **Step 4: Farlo passare**

Run: `npx vitest run src/features/shopping-list/ListRow.test.tsx`
Expected: PASS, 8 test.

- [ ] **Step 5: Riscrivere il test dello schermo**

Sostituisci tutto `frontend/src/features/shopping-list/ShoppingListScreen.test.tsx` con:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MemoryRouter } from "react-router-dom";
import { ShoppingListScreen } from "./ShoppingListScreen";
import { NoticeProvider } from "../../components/ui/NoticeProvider";
import type { ShoppingItem } from "../../domain/types";

function item(over: Partial<ShoppingItem> & Pick<ShoppingItem, "id" | "raw_text">): ShoppingItem {
  return {
    ingredient_id: null, ingredient_name: null, ingredient_category: null, ingredient_kind: null,
    status: "pending", reason: "manual", created_at: "2026-09-28T10:00:00Z", ...over,
  };
}

const ITEMS: ShoppingItem[] = [
  item({ id: "s4", raw_text: "zucchine", ingredient_id: "i4", ingredient_name: "zucchina",
    ingredient_category: "verdura", status: "checked" }),
  item({ id: "s1", raw_text: "pomodoro", ingredient_id: "i1", ingredient_name: "pomodoro",
    ingredient_category: "verdura" }),
  item({ id: "s2", raw_text: "Total 0%", ingredient_id: "i2", ingredient_name: "yogurt greco",
    ingredient_category: "latticini", reason: "finished_while_cooking" }),
  item({ id: "s3", raw_text: "cosa verde", status: "checked" }),
];

type Route = (path: string, init?: RequestInit) => [unknown, number];

/** Un fetch che risponde in base a metodo e percorso, e tiene le chiamate. */
function stubRoutedFetch(route: Route) {
  const spy = vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const [body, status] = route(String(input), init);
    return Promise.resolve(new Response(JSON.stringify(body), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

const patchesOf = (spy: ReturnType<typeof stubRoutedFetch>) =>
  spy.mock.calls
    .filter(([, init]) => init?.method === "PATCH")
    .map(([url, init]) => [String(url).match(/\/shopping-list\/[^/?]+$/)?.[0], JSON.parse(String(init?.body))]);

// senza `NoticeProvider` l'avviso di conferma (la ✕, «Era già in lista.») non avrebbe
// dove comparire: `useNotice()` restituirebbe il no-op del contesto vuoto
function renderScreen() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <NoticeProvider>
          <ShoppingListScreen />
        </NoticeProvider>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

/** Le caselle di una sezione, nell'ordine in cui si vedono. */
async function boxesIn(heading: string) {
  const section = (await screen.findByRole("heading", { name: heading })).closest("section")!;
  return within(section).getAllByRole("checkbox").map((box) => box.getAttribute("aria-label"));
}

describe("ShoppingListScreen", () => {
  it("una sezione per reparto, con il conteggio; quello ignoto in fondo", async () => {
    stubRoutedFetch(() => [ITEMS, 200]);
    renderScreen();
    await screen.findByRole("heading", { name: "Verdura" });
    const headings = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(headings).toEqual(["Latticini", "Verdura", "Senza reparto"]);
    const verdura = screen.getByRole("heading", { name: "Verdura" }).closest("section")!;
    expect(within(verdura).getByText("2")).toBeDefined();
  });

  it("le voci nel carrello vanno in fondo al loro reparto (dal giro)", async () => {
    stubRoutedFetch(() => [ITEMS, 200]);
    renderScreen();
    // «zucchine» arriva per prima dal server, ma è nel carrello
    expect(await boxesIn("Verdura")).toEqual(["pomodoro", "zucchina"]);
  });

  it("segnala le voci rientrate dopo aver cucinato", async () => {
    stubRoutedFetch(() => [ITEMS, 200]);
    renderScreen();
    expect(await screen.findByText("rientrata perché finita cucinando")).toBeDefined();
  });

  it("mostra le voci non abbinate col testo che hai scritto", async () => {
    stubRoutedFetch(() => [ITEMS, 200]);
    renderScreen();
    expect(await screen.findByText("cosa verde")).toBeDefined();
  });

  it("la scheda d'ingresso conta quel che è nel carrello", async () => {
    stubRoutedFetch(() => [ITEMS, 200]);
    renderScreen();
    expect(await screen.findByText("2 nel carrello")).toBeDefined();
  });

  it("spuntando una voce la manda nel carrello", async () => {
    const spy = stubRoutedFetch((_path, init) =>
      init?.method === "PATCH" ? [{ ...ITEMS[1], status: "checked" }, 200] : [ITEMS, 200]
    );
    renderScreen();
    await userEvent.click(await screen.findByRole("checkbox", { name: "pomodoro" }));
    await waitFor(() => expect(patchesOf(spy)).toEqual([["/shopping-list/s1", { status: "checked" }]]));
  });

  it("la ✕ toglie la voce e l'avviso offre «Annulla», che la rimette da comprare", async () => {
    const spy = stubRoutedFetch((_path, init) => (init?.method === "PATCH" ? [ITEMS[1], 200] : [ITEMS, 200]));
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli pomodoro dalla lista" }));
    expect(await screen.findByText("Tolto dalla lista: pomodoro")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Annulla" }));
    await waitFor(() =>
      expect(patchesOf(spy)).toEqual([
        ["/shopping-list/s1", { status: "archived" }],
        ["/shopping-list/s1", { status: "pending" }],
      ])
    );
  });

  it("«Annulla» rimette nel carrello una voce che era nel carrello", async () => {
    const spy = stubRoutedFetch((_path, init) => (init?.method === "PATCH" ? [ITEMS[0], 200] : [ITEMS, 200]));
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli zucchine dalla lista" }));
    fireEvent.click(await screen.findByRole("button", { name: "Annulla" }));
    await waitFor(() =>
      expect(patchesOf(spy)).toEqual([
        ["/shopping-list/s4", { status: "archived" }],
        ["/shopping-list/s4", { status: "checked" }],
      ])
    );
  });

  it("un «Annulla» fallito lo dice, e offre di riprovare", async () => {
    let patches = 0;
    stubRoutedFetch((_path, init) => {
      if (init?.method !== "PATCH") return [ITEMS, 200];
      patches += 1;
      return patches === 1 ? [ITEMS[1], 200] : [{ detail: "no" }, 500];
    });
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli pomodoro dalla lista" }));
    fireEvent.click(await screen.findByRole("button", { name: "Annulla" }));
    expect(await screen.findByText("Non sono riuscito a rimettere pomodoro in lista.")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Riprova" }));
    await waitFor(() => expect(patches).toBe(3));
  });

  it("se nel frattempo la stessa cosa è tornata in lista, «Annulla» non fa il doppione", async () => {
    // dopo la ✕ il server risponde con la voce tolta sparita e un «pomodoro» nuovo,
    // riscritto dalla barra: stesso ingrediente, altra voce
    let archived = false;
    const rewritten = item({ id: "s9", raw_text: "pomodori", ingredient_id: "i1",
      ingredient_name: "pomodoro", ingredient_category: "verdura" });
    const spy = stubRoutedFetch((_path, init) => {
      if (init?.method === "PATCH") {
        archived = true;
        return [ITEMS[1], 200];
      }
      return [archived ? [...ITEMS.filter((i) => i.id !== "s1"), rewritten] : ITEMS, 200];
    });
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli pomodoro dalla lista" }));
    await screen.findByText("pomodori");
    fireEvent.click(screen.getByRole("button", { name: "Annulla" }));
    expect(await screen.findByText("Era già in lista.")).toBeDefined();
    expect(patchesOf(spy)).toEqual([["/shopping-list/s1", { status: "archived" }]]);
  });

  it("una modifica rifiutata lo dice accanto alla voce giusta, e la voce resta", async () => {
    stubRoutedFetch((_path, init) => (init?.method === "PATCH" ? [{ detail: "no" }, 500] : [ITEMS, 200]));
    renderScreen();
    fireEvent.click(await screen.findByRole("button", { name: "Togli pomodoro dalla lista" }));
    const alert = await screen.findByRole("alert");
    expect(alert.closest("li")).toBe(screen.getByRole("checkbox", { name: "pomodoro" }).closest("li"));
    expect(screen.queryByText("Tolto dalla lista: pomodoro")).toBeNull();
  });

  it("mentre una scrittura è in volo, la stessa voce non ne parte una seconda", async () => {
    let release: (response: Response) => void = () => {};
    const spy = vi.fn((_input: RequestInfo | URL, init?: RequestInit) =>
      init?.method === "PATCH"
        ? new Promise<Response>((resolve) => { release = resolve; })
        : Promise.resolve(new Response(JSON.stringify(ITEMS), { status: 200 }))
    );
    vi.stubGlobal("fetch", spy);
    renderScreen();
    const box = await screen.findByRole("checkbox", { name: "pomodoro" });
    fireEvent.click(box);
    await waitFor(() => expect(box).toHaveAttribute("aria-disabled", "true"));
    fireEvent.click(box);
    expect(screen.getByRole("button", { name: "Togli pomodoro dalla lista" })).toBeDisabled();
    expect(spy.mock.calls.filter(([, init]) => init?.method === "PATCH")).toHaveLength(1);
    release(new Response(JSON.stringify({ ...ITEMS[1], status: "checked" }), { status: 200 }));
  });

  it("un ingrediente già in lista non si doppia: «Era già in lista.» nell'avviso", async () => {
    stubRoutedFetch((path, init) =>
      init?.method === "POST"
        ? [{ ...ITEMS[1], added: false }, 200]
        : path.includes("/ingredients") // i suggerimenti della barra: nessuno
          ? [[], 200]
          : [ITEMS, 200]
    );
    renderScreen();
    await screen.findByText("pomodoro");
    await userEvent.type(screen.getByLabelText("Aggiungi alla lista"), "pomodoro{Enter}");
    expect(await screen.findByText("Era già in lista.")).toBeDefined();
  });

  it("una lista vuota lo dice, e dice cosa fare", async () => {
    stubRoutedFetch(() => [[], 200]);
    renderScreen();
    expect(await screen.findByRole("heading", { name: "Lista vuota" })).toBeDefined();
    expect(screen.getByText("Niente nel carrello, per ora")).toBeDefined();
  });

  it("un caricamento fallito non viene spacciato per lista vuota, e si può riprovare", async () => {
    let calls = 0;
    stubRoutedFetch((_path, init) => {
      if (init?.method) return [{}, 200];
      calls += 1;
      return calls === 1 ? [{ detail: "no" }, 500] : [ITEMS, 200];
    });
    renderScreen();
    expect(await screen.findByText(/Non sono riuscito a caricare la lista/)).toBeDefined();
    expect(screen.queryByRole("heading", { name: "Lista vuota" })).toBeNull();
    // né la scheda d'ingresso afferma qualcosa sul contenuto
    expect(screen.getByText("Metti via quello che hai comprato")).toBeDefined();
    // e scrivere resta possibile
    expect(screen.getByLabelText("Aggiungi alla lista")).toBeDefined();
    fireEvent.click(screen.getByRole("button", { name: "Riprova" }));
    expect(await screen.findByText("pomodoro")).toBeDefined();
  });
});
```

Nota per chi implementa: `apiFetch` (`frontend/src/api/client.ts`) passa a `fetch` l'`init` di chi chiama più `credentials` e `headers`: una GET arriva senza `method`, una POST o una PATCH con il suo. Per questo il routing sopra distingue per `init?.method`.

- [ ] **Step 6: Farlo fallire**

Run: `npx vitest run src/features/shopping-list/ShoppingListScreen.test.tsx`
Expected: FAIL — le intestazioni in minuscolo («verdura»), nessun avviso «Tolto dalla lista», nessuna «Lista vuota» come intestazione, nessun «nel carrello».

- [ ] **Step 7: Riscrivere lo schermo**

Sostituisci tutto `frontend/src/features/shopping-list/ShoppingListScreen.tsx` con:

```tsx
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AddItemField } from "./AddItemField";
import { ListRow } from "./ListRow";
import { ShoppingEntryCard } from "./ShoppingEntryCard";
import { groupForDisplay } from "./listView";
import { addShoppingItem, fetchShoppingList, patchShoppingItem } from "./api";
import { EmptyState } from "../../components/ui/EmptyState";
import { ErrorState } from "../../components/ui/ErrorState";
import { Screen } from "../../components/ui/Screen";
import { Section } from "../../components/ui/Section";
import { useNotice } from "../../components/ui/noticeContext";
import type { ShoppingItem } from "../../domain/types";

// la stessa chiave della Dispensa, che ne legge la scheda d'ingresso: la cache è una
const LIST_KEY = ["shopping-list"];

export function ShoppingListScreen() {
  const queryClient = useQueryClient();
  const notice = useNotice();
  const { data, isLoading, isError, refetch, isFetching } = useQuery({
    queryKey: LIST_KEY,
    queryFn: () => fetchShoppingList(),
  });
  // un caricamento fallito non è una lista vuota; ma se uno era già riuscito, React
  // Query ne tiene i dati anche quando il successivo fallisce, e quelli restano a video
  // sotto l'errore. `loaded` distingue i due casi, come in PantryScreen
  const loaded = data !== undefined;
  const items = data ?? [];

  // quali voci hanno rifiutato l'ultima modifica. Un insieme, non un solo id: una
  // spunta fallita su una voce e un «Annulla» fallito su un'altra sono indipendenti.
  // Il messaggio va accanto alla voce e non in cima: la lista si scorre camminando per
  // i reparti, e un avviso fuori schermo non è un avviso
  const [failedIds, setFailedIds] = useState<Set<string>>(new Set());
  const markFailed = (id: string) =>
    setFailedIds((prev) => (prev.has(id) ? prev : new Set(prev).add(id)));
  const clearFailed = (id: string) =>
    setFailedIds((prev) => {
      if (!prev.has(id)) return prev;
      const next = new Set(prev);
      next.delete(id);
      return next;
    });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: LIST_KEY });

  const add = useMutation({
    mutationFn: ({ text, id }: { text: string; id?: string }) => addShoppingItem(text, id),
    onSuccess: invalidate,
  });

  const toggle = useMutation({
    mutationFn: (item: ShoppingItem) =>
      patchShoppingItem(item.id, { status: item.status === "checked" ? "pending" : "checked" }),
    onMutate: (item) => clearFailed(item.id),
    onSuccess: invalidate,
    // senza questo una PATCH fallita non dice niente: la casella torna da sé al valore
    // del server e chi guarda resta convinto di aver spuntato
    onError: (_error, item) => markFailed(item.id),
  });

  // L'annulla vive nell'avviso, che è dell'app e non di questo schermo: si può toccare
  // anche dopo essere passati a un'altra scheda. Per questo non è una useMutation
  // (legata al componente) ma una chiamata col queryClient dell'app, come in
  // PantryScreen. La voce torna allo stato che aveva — da comprare o nel carrello —
  // con la PATCH di sempre (spec §4.2).
  function undoRemove(item: ShoppingItem) {
    // nei 6 secondi dell'avviso la stessa cosa può essere stata riscritta dalla barra:
    // rimettere anche questa farebbe il doppione che S18 esiste per evitare
    const current = queryClient.getQueryData<ShoppingItem[]>(LIST_KEY) ?? [];
    const relisted =
      item.ingredient_id !== null &&
      current.some((other) => other.id !== item.id && other.ingredient_id === item.ingredient_id);
    if (relisted) {
      notice({ text: "Era già in lista." });
      return;
    }
    patchShoppingItem(item.id, { status: item.status }).then(
      () => queryClient.invalidateQueries({ queryKey: LIST_KEY }),
      // la voce è archiviata davvero: perderla qui sarebbe il vicolo cieco
      () =>
        notice({
          text: `Non sono riuscito a rimettere ${item.raw_text} in lista.`,
          action: { label: "Riprova", onClick: () => undoRemove(item) },
        })
    );
  }

  // Archiviare è l'unico modo di togliere una voce: «pomdoro» scritto per sbaglio non
  // si cancella spuntandolo, perché spuntarlo lo fa entrare in dispensa — cioè sporca
  // la dispensa per pulire la lista. `fetchShoppingList` chiede solo `pending` e
  // `checked`, quindi la riga sparisce senza altro lavoro.
  const archive = useMutation({
    mutationFn: (item: ShoppingItem) => patchShoppingItem(item.id, { status: "archived" }),
    onMutate: (item) => clearFailed(item.id),
    onSuccess: (_data, item) => {
      invalidate();
      notice({
        text: `Tolto dalla lista: ${item.raw_text}`,
        action: { label: "Annulla", onClick: () => undoRemove(item) },
      });
    },
    onError: (_error, item) => markFailed(item.id),
  });

  // quali voci hanno una richiesta in volo: due PATCH sulla stessa riga arrivano in
  // ordine ignoto e l'ultima a rispondere vince. Il limite è quello di PantryScreen:
  // `variables` tiene solo l'ultima chiamata di ogni mutazione
  const busyIds = new Set<string>();
  if (toggle.isPending) busyIds.add(toggle.variables.id);
  if (archive.isPending) busyIds.add(archive.variables.id);

  return (
    <Screen title="Lista">
      <div className="flex flex-col gap-3">
        <AddItemField onAdd={(text, id) => add.mutateAsync({ text, id })} />

        {/* sempre presente, anche a carrello vuoto: «Sistema la spesa» è una
            sottosezione, non un avviso (D3 di docs/prossimi-passi.md) */}
        <ShoppingEntryCard items={data} failed={isError} />

        {isLoading && <p className="text-ink-soft">Carico…</p>}

        {/* scrivere resta possibile in ogni caso: la barra è sopra, e non dipende dal
            caricamento */}
        {isError && (
          <ErrorState
            message={
              loaded
                ? "Non sono riuscito ad aggiornare la lista. Quella qui sotto è dell'ultimo caricamento."
                : "Non sono riuscito a caricare la lista. Puoi comunque aggiungere voci."
            }
            onRetry={() => void refetch()}
            retrying={isFetching}
          />
        )}

        {loaded && items.length === 0 && (
          <EmptyState title="Lista vuota" body="Scrivi qui sopra cosa ti serve e tocca +." />
        )}

        {loaded &&
          groupForDisplay(items).map(([category, rows]) => (
            <Section key={category ?? "senza-reparto"} category={category} count={rows.length}>
              <ul>
                {rows.map((item) => (
                  <ListRow
                    key={item.id}
                    item={item}
                    busy={busyIds.has(item.id)}
                    failed={failedIds.has(item.id)}
                    onToggle={() => toggle.mutate(item)}
                    onRemove={() => archive.mutate(item)}
                  />
                ))}
              </ul>
            </Section>
          ))}
      </div>
    </Screen>
  );
}
```

- [ ] **Step 8: Farlo passare, e tutto il resto**

Run: `npx vitest run src/features/shopping-list && npx vitest run && npm run lint && npm run typecheck && npm run build`
Expected: tutto verde. Se un altro test dell'app cerca ancora «Lista vuota. Scrivi cosa ti serve.» o le intestazioni di reparto in minuscolo, correggilo e scrivilo nel report.

Run (dalla radice): `grep -rn "emerald\|neutral-" frontend/src`
Expected: niente.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/features/shopping-list/ListRow.tsx frontend/src/features/shopping-list/ListRow.test.tsx frontend/src/features/shopping-list/ShoppingListScreen.tsx frontend/src/features/shopping-list/ShoppingListScreen.test.tsx
git commit -m "lista: sezioni per reparto, le voci nel carrello in fondo, e la ✕ con «Annulla»"
```

---

### Task 5: L'e2e — i percorsi che attraversano la lista, e le misure nel browser

jsdom non calcola il CSS (quarta lezione di `CLAUDE.md`): che la barra resti sotto l'intestazione scorrendo, e che la ✕ sia un bersaglio da 44 px, lo dice solo un browser.

**Files:**
- Modify: `frontend/e2e/cooking.spec.ts` (la guardia sullo stack pulito)
- Modify: `frontend/e2e/non-alimentari.spec.ts` (solo se cerca testi cambiati: controlla)
- Modify: `frontend/e2e/style.spec.ts` (un test nuovo)

- [ ] **Step 1: La guardia di `cooking.spec.ts`**

In `frontend/e2e/cooking.spec.ts` la guardia sullo stack pulito cerca `page.getByText("Lista vuota. Scrivi cosa ti serve.")`. Ora il titolo è un'intestazione a sé. Sostituisci il localizzatore con:

```ts
    page.getByRole("heading", { name: "Lista vuota" }),
```

lasciando com'è il messaggio che segue («lo stack e2e non è pulito…»).

Poi cerca il resto:

Run (dalla radice): `grep -rn "Lista vuota\|Cosa serve\|voci spuntate\|di spuntato\|Era già in lista" frontend/e2e`
Expected: solo il commento di `non-alimentari.spec.ts` intorno alla riga 112 e la riga appena cambiata. Leggi quel commento: se descrive il testo vecchio della lista vuota, aggiornalo al testo nuovo; se il codice lì sotto cerca un testo cambiato, correggilo.

- [ ] **Step 2: Il test nuovo in `style.spec.ts`**

Aggiungi in fondo a `frontend/e2e/style.spec.ts` (il `beforeEach` del file ha già fatto l'accesso, e `page.request` condivide i cookie della pagina):

```ts
test("la barra della lista resta sotto l'intestazione scorrendo, e la ✕ offre «Annulla»", async ({
  page,
}) => {
  // Dal giro: la barra e l'intestazione erano tutte e due `sticky top-0 z-10`, e
  // scorrendo la barra copriva l'intestazione. Ora la barra si ferma sotto. Serve una
  // lista più alta della finestra: otto voci a testo libero, create con l'API e tolte
  // in fondo, perché la lista è stato condiviso e il database vive quanto lo stack.
  await page.setViewportSize({ width: 375, height: 500 });
  const voci = Array.from({ length: 8 }, (_, i) => `prova scorrimento ${i + 1}`);
  const create: string[] = [];
  for (const raw_text of voci) {
    const risposta = await page.request.post("/api/v1/shopping-list", {
      data: { raw_text, ingredient_id: null },
    });
    expect(risposta.ok()).toBe(true);
    create.push(((await risposta.json()) as { id: string }).id);
  }

  await page.goto("/lista");
  await expect(page.getByRole("checkbox", { name: "prova scorrimento 8" })).toBeVisible();
  await page.mouse.wheel(0, 1500);
  // aspetta che lo scorrimento sia arrivato davvero, o le misure qui sotto
  // guarderebbero la pagina ferma in cima
  await expect.poll(() => page.evaluate<number>("window.scrollY")).toBeGreaterThan(100);

  const intestazione = await page.getByRole("banner").boundingBox();
  const campo = page.getByLabel("Aggiungi alla lista");
  await expect(campo).toBeInViewport();
  const barra = await campo.boundingBox();
  expect(
    barra!.y,
    "la barra della lista copre l'intestazione"
  ).toBeGreaterThanOrEqual(intestazione!.y + intestazione!.height);
  // e l'intestazione è davvero quella che si vede lì sopra, non qualcosa che le
  // passa sopra: il punto al centro del marchio appartiene all'intestazione
  const sopra = await page.evaluate<boolean>(
    `(() => { const h = document.querySelector("header"); const r = h.getBoundingClientRect();
       const el = document.elementFromPoint(r.left + 40, r.top + r.height / 2);
       return !!el && h.contains(el); })()`
  );
  expect(sopra, "qualcosa copre l'intestazione").toBe(true);

  // la ✕ è un bersaglio da pollice, e togliere offre «Annulla», che rimette la voce
  const togli = page.getByRole("button", { name: "Togli prova scorrimento 1 dalla lista" });
  const box = await togli.boundingBox();
  expect(box!.width).toBeGreaterThanOrEqual(44);
  expect(box!.height).toBeGreaterThanOrEqual(44);
  await togli.click();
  await expect(page.getByText("Tolto dalla lista: prova scorrimento 1")).toBeVisible();
  await expect(page.getByRole("checkbox", { name: "prova scorrimento 1" })).toHaveCount(0);
  await page.getByRole("button", { name: "Annulla" }).click();
  await expect(page.getByRole("checkbox", { name: "prova scorrimento 1" })).toBeVisible();

  // la pulizia
  for (const id of create) {
    const risposta = await page.request.patch(`/api/v1/shopping-list/${id}`, {
      data: { status: "archived" },
    });
    expect(risposta.ok()).toBe(true);
  }
});
```

- [ ] **Step 3: Lo stack e2e, e l'e2e intera**

Dalla radice del worktree:

```bash
cp .env.example .env
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml up -d --build --wait
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml exec -T backend python -m app.cli.seed --con-ricette
cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e; cd ..
```

Expected: tutti i test passano (erano 30, ora 31). Se un test fallisce e lascia dati nello stack, prima di rieseguire ricrea lo stack da zero (`down -v` e di nuovo `up` e seme): i test contano su una lista e una dispensa pulite.

Poi, sempre dalla radice:

```bash
docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml down -v
rm .env
```

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e
git commit -m "e2e: la barra della lista resta sotto l'intestazione scorrendo, e la ✕ offre «Annulla»"
```

---

### Task 6: I documenti

**Files:**
- Modify: `docs/prossimi-passi.md`

- [ ] **Step 1: Il paragrafo della consegna**

In `docs/prossimi-passi.md`, nella voce T3, dopo i paragrafi della Consegna 1 (cerca «**Consegna 1 (Dispensa) fatta il 2026-09-28**» e i paragrafi che la seguono, fino a quello che comincia con «**Dei tre punti di disegno del tema scuro**»), aggiungi un paragrafo:

```markdown
**Consegna 2 (Lista) fatta il <data di oggi>, sul ramo `<nome del ramo>`, non ancora in
produzione.** Cosa è cambiato: la barra «Cosa manca?» col + al posto del campo con
«Aggiungi», appiccicata sotto l'intestazione invece che sopra (erano tutte e due `sticky
top-0 z-10`, e scorrendo la barra la copriva); la scheda «Sistema la spesa» dice «N nel
carrello», ed è ora un componente solo per Lista e Dispensa (`ShoppingEntryCard`), che
quindi cambiano nota insieme; i reparti in sezioni, con le voci nel carrello in fondo al
loro reparto; la ✕ con l'avviso unico e «Annulla», che rimette la voce com'era — da
comprare o nel carrello — e non scrive se nel frattempo la stessa cosa è tornata in lista
dalla barra; «Era già in lista.» esce dall'avviso unico, come in dispensa; l'errore di
caricamento ha «Riprova», e la lista vuota dice cosa fare. La casella si spegne con
`aria-disabled` mentre la spunta è in volo, come le tacche: con `disabled` chi spunta con
la tastiera perdeva il fuoco.

**Da provare sul telefono:** la barra che resta sotto l'intestazione scorrendo, e i
suggerimenti che si aprono sotto la barra appiccicata (su una lista lunga coprono le
righe finché non si sceglie o si svuota il campo); spuntare camminando, ora che le righe
non hanno più le linee fra loro; «Annulla» dopo la ✕ su una voce nel carrello.
```

Sostituisci `<data di oggi>` e `<nome del ramo>` con i valori veri.

- [ ] **Step 2: Le osservazioni del giro**

Nella sezione del giro, sotto **Lista**, segna *(T3 Consegna 2)* in fondo a queste tre voci:

- «**Il campo di aggiunta scorrendo copre l'intestazione.** …»
- «**La X della lista non ha la lapide con «Annulla»**, …»
- «**Le voci spuntate restano in mezzo alle altre.** …»

E sotto l'elenco della Lista aggiungi:

```markdown
Resta com'è, di proposito, «c'è una scheda per reparto anche con una voce sola»: le
sezioni per reparto sono una decisione della spec del ridisegno (§2), e una sezione di
una voce è il prezzo di avere la stessa forma sempre.
```

- [ ] **Step 3: Commit**

```bash
git add docs/prossimi-passi.md
git commit -m "docs: T3 Consegna 2, la Lista, e le osservazioni del giro che chiude"
```
