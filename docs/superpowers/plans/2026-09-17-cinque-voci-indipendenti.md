# Cinque voci indipendenti — S1, S2, R1, R3, T1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** chiudere le cinque voci che `docs/prossimi-passi.md` elenca come «indipendenti e piccole» — la X rossa con l'annulla, lo slider a tre zone in dispensa, la foto dentro la ricetta, il filtro per ingrediente primario e la navigazione (intestazione, tasto indietro, schede d'ingresso sempre presenti).

**Architecture:** nessuna voce introduce un concetto nuovo. Tre sono solo frontend (T1, R1, e la metà visiva di S2); due aggiungono al backend una colonna (`pantry_items.fill_percent`), una regola pura (`status_for_fill`), una rotta (`POST /pantry/{id}/restock`) e un parametro di ricerca (`ingredient_id`). La posizione dello slider è **display**: lo stato resta l'unica verità e la conversione posizione → stato vive in `app/domain/rules.py`, non nel client.

**Tech Stack:** FastAPI + SQLAlchemy async + Alembic + Postgres 16; React 19 + Vite + TypeScript + Tailwind 4 + TanStack Query; pytest / Vitest / Playwright.

**Spec:** `docs/prossimi-passi.md` — S1 e S2 in Parte II, R1 e R3 in Parte III, T1 in Parte VII, con la decisione D3 in Parte I. Non è una spec e non vuole esserlo: è la cornice. Le tre domande che lasciava aperte sono state chiuse dal committente il 2026-09-17 e sono riportate qui sotto come vincoli.

## Decisioni prese il 2026-09-17, prima di questo piano

1. **S1 — la X rossa ha un annulla a tempo.** Tolta la voce, al suo posto resta per sei secondi «Tolta dalla dispensa — Annulla». Archiviare era già reversibile nel database (`archived_at`); mancava solo il modo di disfarlo dall'API.
2. **S2 — lo slider a zero segna «finito» e poi chiede.** Comparirà «Lo rimetto in lista?» con sì e no. Non scrive in lista da sé: nessuna sezione ne modifica un'altra in silenzio.
   **Nota di fatto, contro quanto suppone il TBD in `prossimi-passi.md`:** oggi portare una voce a `finished` dalla dispensa **non** la rimette in lista. `set_status` in `backend/app/repositories/pantry.py` cambia solo lo stato; l'unico punto che riempie la lista è `cook()`, e solo con la spunta «rimetti in lista». Il testo del TBD va corretto (Task 15).
3. **T1 — niente hamburger, per ora.** Si fanno intestazione globale, tasto indietro e schede d'ingresso. L'indice completo arriverà con la prima sezione secondaria vera (Pasti, Spese, Profilo, Connettori): un menu che ripete le tre schede della navbar non è un indice, è un doppione.
4. **T1 — il logo è un segno disegnato a mano in SVG**, nello stesso stile delle tre icone della `TabBar`. Nessun file binario, nessuna libreria di icone.

## Global Constraints

Valgono per ogni task. Le prime sette vengono da `CLAUDE.md` e non sono negoziabili.

- **Niente quantità in dispensa.** `fill_percent` è una posizione indicativa, non una quantità: niente unità, niente scadenze, e nessun calcolo la usa. Lo stato (`available` / `low` / `finished`) resta l'unica verità su cui il resto dell'app ragiona.
- **Il dominio sta nel backend.** La conversione posizione → stato è una funzione pura in `backend/app/domain/rules.py`. Il frontend chiede, non calcola. L'unico numero condiviso è la soglia della zona gialla, e un test del backend legge il file del frontend per impedire che i due divergano.
- **Mai un vicolo cieco.** Ogni fallimento lascia all'utente una strada: la X che fallisce lo dice accanto alla voce, la scheda d'ingresso resta raggiungibile anche quando il conteggio non si carica, una foto che non arriva non lascia un buco.
- **I nutrienti mancanti restano mancanti**, e per estensione: l'assenza di una posizione è `NULL`, mai `0` e mai `100`.
- **`tsc --noEmit` non è il type check di questo progetto.** Il type check è `npm run typecheck` (`tsc -b`); la prova finale è `npm run build`.
- **Un test che si costruisce l'oggetto non prova quello che gira in produzione.** Dove si può, il test passa dal componente o dalla funzione vera.
- **Il CSS non lo vede jsdom.** Quanto è visibile o toccabile un cursore si prova in un browser vero, in `frontend/e2e/`.
- **Tutto il colore vive nel blocco `@theme` di `frontend/src/index.css`**, come token (`--color-low` → `bg-low`). Nessuno schermo nomina un colore grezzo; `var(--color-…)` in uno stile in linea è lecito perché nomina il token, non il colore.
- **Bersagli da pollice: `min-h-11`** (44px) su ogni cosa che si tocca.
- **Specs e piani in italiano, codice e identificatori in inglese.**
- Ogni messaggio di commit finisce con `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
- **Nessun deploy in questo piano.** Il piano finisce su un ramo verde; merge e deploy si decidono dopo.

## Come si girano i test

La suite vera gira **sull'host, non in Docker** (undicesima parte di `prossimi-passi.md`):

```bash
docker compose up -d db
cd backend && .venv/bin/python -m pytest
```

```bash
cd frontend && npx vitest run && npm run typecheck && npm run build
```

I controlli nel browser (solo Task 9) girano sullo stack `spena-e2e`:

```bash
E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
$E2E up -d --build --wait
$E2E exec -T backend python -m app.cli.seed
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
$E2E down -v
```

**`docker compose` senza `-f` sostituisce la produzione con lo stack di sviluppo** (terza lezione di `CLAUDE.md`), e `-v` si usa **solo** sul progetto `spena-e2e`, mai su quello di default.

---

## Struttura dei file

**Backend — creati**

| File | Responsabilità |
|---|---|
| `backend/alembic/versions/0006_slider_dispensa.py` | aggiunge `pantry_items.fill_percent` e il suo vincolo 0–100 |
| `backend/app/services/restock.py` | «una voce torna in lista»: un solo posto, due chiamanti (la cottura e lo slider a zero) |
| `backend/tests/test_frontend_fill_zones.py` | la soglia della zona gialla è la stessa nei due linguaggi |
| `backend/tests/services/test_restock.py` | il servizio di rientro in lista, compreso il non-duplicare |

**Backend — modificati**

| File | Che cosa cambia |
|---|---|
| `backend/app/domain/rules.py` | `LOW_MAX_FILL` e `status_for_fill` |
| `backend/app/db/models/pantry.py` | colonna `fill_percent` + `CheckConstraint` |
| `backend/app/schemas/pantry.py` | `fill_percent` in uscita e in PATCH; `archived` diventa annullabile |
| `backend/app/repositories/pantry.py` | `unarchive_item`, `set_fill`; `set_status` azzera la posizione |
| `backend/app/api/pantry.py` | i tre rami della PATCH e la rotta `POST /{item_id}/restock` |
| `backend/app/services/cooking.py` | usa `services/restock.py` invece della sua copia |
| `backend/app/services/recipe_search.py` | filtro per ingrediente **primario**, applicato in SQL |
| `backend/app/api/recipes.py` | parametro `ingredient_id` su `/recipes/search` |

**Frontend — creati**

| File | Responsabilità |
|---|---|
| `frontend/src/components/AppHeader.tsx` | intestazione globale: segno e nome, collegati alla schermata iniziale |
| `frontend/src/components/BackLink.tsx` | il ritorno alla sezione madre, con destinazione dichiarata |
| `frontend/src/components/ui/SectionEntryCard.tsx` | la scheda d'ingresso a una sottosezione, sempre presente |
| `frontend/src/features/pantry/fillZones.ts` | la soglia della zona gialla e la posizione di partenza per chi non ne ha una |
| `frontend/src/features/pantry/FillSlider.tsx` | il cursore a tre zone |
| `frontend/src/features/pantry/PantryRow.tsx` | una riga di dispensa: cursore, stato, X con annulla, domanda sul rientro in lista |
| `frontend/src/features/recipes/RecipeImage.tsx` | la foto di una ricetta, con il buco già chiuso |

**Frontend — modificati**

`App.tsx` (intestazione), `components/ui/Screen.tsx` (`back`), `index.css` (forma del cursore), `domain/types.ts` (`fill_percent`, `RestockResult`), `features/pantry/{PantryScreen,api}.tsx|ts`, `features/shopping-list/ShoppingListScreen.tsx`, `features/recipes/{RecipeBookScreen,RecipeCard,api}.tsx|ts`, `features/cooking/RecipeDetailScreen.tsx`, `features/stocking/StockingScreen.tsx`, `features/ai-draft/AiDraftScreen.tsx`, `features/recipe-import/ImportQueueScreen.tsx`, e i rispettivi `*.test.tsx`.

**Frontend — cancellati**

`features/pantry/StatusToggle.tsx` e `features/pantry/StatusToggle.test.tsx` (Task 9): il cursore lo sostituisce, ed è l'unico schermo che lo usava. Due controlli per la stessa verità si contraddicono. `STATUS_LABELS` e `STATUS_TONE` **restano** in `statusLabels.ts`: li usano `StatusChip` e il foglio di cottura.

---

## Task 1: L'intestazione globale (T1)

**Files:**
- Create: `frontend/src/components/AppHeader.tsx`
- Test: `frontend/src/components/AppHeader.test.tsx`
- Modify: `frontend/src/App.tsx:48-71`, `frontend/src/App.test.tsx`

**Interfaces:**
- Consumes: niente.
- Produces: `AppHeader()` — nessun parametro. Resa da `App.tsx` sopra `<main>`, fuori da `<Routes>`.

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `frontend/src/components/AppHeader.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { AppHeader } from "./AppHeader";

function renderHeader() {
  return render(
    <MemoryRouter>
      <AppHeader />
    </MemoryRouter>
  );
}

describe("AppHeader", () => {
  it("porta il nome dell'app, e il nome riporta alla schermata iniziale", () => {
    renderHeader();
    const home = screen.getByRole("link", { name: "Spena" });
    expect(home.getAttribute("href")).toBe("/");
  });

  it("sta in un banner: chi naviga per landmark deve trovarlo", () => {
    renderHeader();
    expect(screen.getByRole("banner")).toBeDefined();
  });

  it("il segno non ha un nome suo: il link si chiama «Spena», una volta sola", () => {
    // stessa regola delle icone della TabBar: senza `aria-hidden` chi legge con la
    // voce sentirebbe due volte la stessa cosa
    const { container } = renderHeader();
    expect(container.querySelector("svg")?.getAttribute("aria-hidden")).toBe("true");
  });
});
```

- [ ] **Step 2: Falla fallire**

Run: `cd frontend && npx vitest run src/components/AppHeader.test.tsx`
Expected: FAIL — `Failed to resolve import "./AppHeader"`.

- [ ] **Step 3: Scrivi il componente**

Crea `frontend/src/components/AppHeader.tsx`:

```tsx
import { Link } from "react-router-dom";

// Il segno dell'app, disegnato qui come le tre icone della TabBar e per lo stesso
// motivo: una libreria di icone peserebbe sul primo avvio di una PWA più di quanto
// valga, e di marchi ce n'è uno. Una pentola con il vapore: solo tratti, nessun
// riempimento, `currentColor` così eredita il verde del nome accanto.
function Mark() {
  return (
    <svg
      viewBox="0 0 24 24"
      aria-hidden="true"
      className="size-6"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M3.5 10.5h17v4.5a4.5 4.5 0 0 1-4.5 4.5H8a4.5 4.5 0 0 1-4.5-4.5z" />
      <path d="M20.5 12h1a1.8 1.8 0 0 1 0 3.6h-1" />
      <path d="M9.5 7.5c0-1.2 1-1.6 1-2.8M14 7.5c0-1.2 1-1.6 1-2.8" />
    </svg>
  );
}

/** L'intestazione che sta sopra ogni schermata.
 *
 * `sticky` e non `fixed`: fissa, dovrebbe riservarsi lo spazio con un margine sul
 * contenuto, e quel margine si dimentica il giorno in cui l'altezza cambia.
 *
 * A destra non c'è niente, ed è una scelta: l'hamburger dell'indice completo
 * (T1 di docs/prossimi-passi.md) arriva quando esisterà la prima sezione
 * secondaria da indicizzare. Un menu che ripete le tre schede della barra in
 * basso non è un indice.
 */
export function AppHeader() {
  return (
    <header role="banner" className="sticky top-0 z-10 border-b border-line bg-card">
      <div className="mx-auto flex h-12 max-w-md items-center px-4">
        <Link
          to="/"
          className="flex min-h-11 items-center gap-2 font-semibold tracking-tight text-brand"
        >
          <Mark />
          Spena
        </Link>
      </div>
    </header>
  );
}
```

- [ ] **Step 4: Falla passare**

Run: `cd frontend && npx vitest run src/components/AppHeader.test.tsx`
Expected: PASS, 3 test.

- [ ] **Step 5: Aggancia l'intestazione all'app**

In `frontend/src/App.tsx` aggiungi l'import accanto agli altri componenti:

```tsx
import { AppHeader } from "./components/AppHeader";
```

e sostituisci l'apertura di `<BrowserRouter>` e di `<main>`:

```tsx
      <BrowserRouter>
        <AppHeader />
        {/* max-w-md: l'app è pensata per un telefono, e su uno schermo largo una
            lista che attraversa 1400px non si legge. pb-24 tiene l'ultima riga
            sopra la barra delle schede, che è fissa e coprirebbe un bersaglio.
            L'altezza minima toglie i 3rem dell'intestazione: con `min-h-dvh`
            pieno la pagina sarebbe sempre più alta dello schermo di quei 3rem,
            e ogni schermata avrebbe una barra di scorrimento che non serve. */}
        <main className="mx-auto min-h-[calc(100dvh-3rem)] max-w-md pb-24">
```

- [ ] **Step 6: Prova che l'intestazione c'è sopra una schermata vera**

In `frontend/src/App.test.tsx`, dentro `describe("App", …)`, aggiungi:

```tsx
  it("l'intestazione sta sopra le schermate, non dentro una di loro", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(ITEMS), { status: 200 })
    ));

    render(<App />);

    expect(await screen.findByRole("banner")).toBeDefined();
    expect(screen.getByRole("link", { name: "Spena" })).toBeDefined();
  });
```

- [ ] **Step 7: Tutto verde**

Run: `cd frontend && npx vitest run && npm run typecheck`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/AppHeader.tsx frontend/src/components/AppHeader.test.tsx frontend/src/App.tsx frontend/src/App.test.tsx
git commit -m "$(cat <<'MSG'
feat: l'intestazione globale con il nome e il segno dell'app

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Task 2: Il tasto indietro nelle sottosezioni (T1)

Oggi dalle sottosezioni si torna solo con la barra in basso o col tasto del telefono — che in una PWA installata su iOS non esiste.

**Files:**
- Create: `frontend/src/components/BackLink.tsx`
- Test: `frontend/src/components/BackLink.test.tsx`
- Modify: `frontend/src/components/ui/Screen.tsx`, `frontend/src/features/recipe-import/ImportQueueScreen.tsx:223`, `frontend/src/features/stocking/StockingScreen.tsx:326-328`, `frontend/src/features/ai-draft/AiDraftScreen.tsx:267-269`, `frontend/src/features/cooking/RecipeDetailScreen.tsx:83-85`, e i test `RecipeDetailScreen.test.tsx`, `ImportQueueScreen.test.tsx`

**Interfaces:**
- Consumes: niente.
- Produces:
  - `BackLink({ to, label }: { to: string; label: string })`
  - `Screen` accetta in più `back?: { to: string; label: string }`

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `frontend/src/components/BackLink.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { BackLink } from "./BackLink";

describe("BackLink", () => {
  it("porta a una destinazione dichiarata, non alla cronologia", () => {
    render(
      <MemoryRouter>
        <BackLink to="/ricette" label="Ricette" />
      </MemoryRouter>
    );
    expect(screen.getByRole("link", { name: "Ricette" }).getAttribute("href")).toBe("/ricette");
  });

  it("il segno di minore non entra nel nome del collegamento", () => {
    const { container } = render(
      <MemoryRouter>
        <BackLink to="/lista" label="Lista" />
      </MemoryRouter>
    );
    // il nome accessibile è «Lista»: se il chevron non fosse nascosto, chi legge
    // con la voce sentirebbe un carattere che non si pronuncia
    expect(screen.getByRole("link", { name: "Lista" })).toBeDefined();
    expect(container.querySelector("[aria-hidden='true']")).not.toBeNull();
  });
});
```

- [ ] **Step 2: Falla fallire**

Run: `cd frontend && npx vitest run src/components/BackLink.test.tsx`
Expected: FAIL — `Failed to resolve import "./BackLink"`.

- [ ] **Step 3: Scrivi il componente**

Crea `frontend/src/components/BackLink.tsx`:

```tsx
import { Link } from "react-router-dom";

/** Il ritorno dalla sottosezione alla sezione madre.
 *
 * Una destinazione dichiarata, non `navigate(-1)`. In una PWA installata su iOS il
 * tasto indietro del telefono non c'è, e la cronologia può essere vuota: ci si
 * arriva da un collegamento condiviso, o da una schermata che il sistema ha
 * riaperto. Lì `-1` non torna alla sezione madre — esce dall'app, o non fa niente.
 * Sapere dove si torna è compito di chi rende lo schermo, e costa una parola.
 */
export function BackLink({ to, label }: { to: string; label: string }) {
  return (
    <Link
      to={to}
      className="-ml-1 inline-flex min-h-11 items-center gap-1 text-sm font-medium text-ink-soft"
    >
      <span aria-hidden="true">‹</span>
      {label}
    </Link>
  );
}
```

- [ ] **Step 4: Falla passare**

Run: `cd frontend && npx vitest run src/components/BackLink.test.tsx`
Expected: PASS, 2 test.

- [ ] **Step 5: `Screen` impara a portare il ritorno**

Sostituisci per intero `frontend/src/components/ui/Screen.tsx`:

```tsx
import type { ReactNode } from "react";
import { BackLink } from "../BackLink";

// L'intestazione di ogni schermata, in un posto solo. Quindici schermate che ripetono
// la stessa minestra di classi divergono da sole: basta un `pt-5` diventato `pt-4` e
// il titolo salta passando da una scheda all'altra.
export function Screen({
  title,
  subtitle,
  action,
  back,
  children,
}: {
  title: string;
  subtitle?: ReactNode;
  /** un bottone o un link in alto a destra, all'altezza del titolo */
  action?: ReactNode;
  /** dove si torna, per le sottosezioni. Le sezioni primarie non lo passano: da
   * loro non si torna, ci si sposta con la barra in basso. */
  back?: { to: string; label: string };
  children: ReactNode;
}) {
  return (
    // con il ritorno lo spazio sopra è già occupato dal collegamento, che porta la
    // sua altezza da bersaglio: `pt-5` in più staccherebbe il titolo dal resto
    <div className={`px-4 pb-4 ${back ? "pt-2" : "pt-5"}`}>
      {back && <BackLink to={back.to} label={back.label} />}
      <div className="flex items-start justify-between gap-3 pb-3">
        <div className="min-w-0">
          <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
          {subtitle && <p className="pt-0.5 text-sm text-ink-soft">{subtitle}</p>}
        </div>
        {action}
      </div>
      {children}
    </div>
  );
}
```

- [ ] **Step 6: Metti il ritorno nelle quattro sottosezioni**

`frontend/src/features/recipe-import/ImportQueueScreen.tsx`, riga 223 — usa già `Screen`:

```tsx
    <Screen title="Ingredienti da abbinare" back={{ to: "/ricette", label: "Ricette" }}>
```

`frontend/src/features/stocking/StockingScreen.tsx`, riga 328 — aggiungi l'import `import { BackLink } from "../../components/BackLink";` e metti il collegamento sopra il titolo:

```tsx
      <BackLink to="/lista" label="Lista" />
      <h1 className="pb-3 text-xl font-semibold">Sistema la spesa</h1>
```

`frontend/src/features/ai-draft/AiDraftScreen.tsx`, riga 269 — stesso import, e:

```tsx
      <BackLink to="/ricette" label="Ricette" />
      <h1 className="text-2xl font-semibold tracking-tight">Scrivi una ricetta</h1>
```

`frontend/src/features/cooking/RecipeDetailScreen.tsx`, riga 85 — stesso import, e:

```tsx
      <BackLink to="/ricette" label="Ricette" />
      <h1 className="text-2xl font-semibold tracking-tight">{recipe.title}</h1>
```

- [ ] **Step 7: Prova che il ritorno c'è dove serve**

In `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`, dentro il `describe` esistente:

```tsx
  it("da una ricetta aperta si torna al ricettario con un tasto", async () => {
    // in una PWA su iOS il tasto indietro del telefono non c'è: senza questo
    // collegamento l'unica uscita è la barra in basso
    stubFetch();
    renderScreen();
    expect((await screen.findByRole("link", { name: "Ricette" })).getAttribute("href"))
      .toBe("/ricette");
  });
```

Se il file non ha una `stubFetch()`/`renderScreen()` con quei nomi, usa gli helper che già ci sono: l'unica riga che conta è l'asserzione sul collegamento.

Aggiungi la gemella in `frontend/src/features/recipe-import/ImportQueueScreen.test.tsx`:

```tsx
  it("dalla coda dell'import si torna alle ricette con un tasto", async () => {
    // stessi stub del test accanto: qui interessa solo l'uscita
    expect((await screen.findByRole("link", { name: "Ricette" })).getAttribute("href"))
      .toBe("/ricette");
  });
```

- [ ] **Step 8: Tutto verde**

Run: `cd frontend && npx vitest run && npm run typecheck`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/components/BackLink.tsx frontend/src/components/BackLink.test.tsx frontend/src/components/ui/Screen.tsx frontend/src/features
git commit -m "$(cat <<'MSG'
feat: il tasto indietro nelle sottosezioni, con destinazione dichiarata

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Task 3: Le schede d'ingresso sempre presenti (T1)

Oggi «Sistema la spesa» compare solo se qualcosa è spuntato, e «Ingredienti da abbinare» solo se c'è una coda. Il caso «non ho niente da sistemare» fa sparire il tasto, e con lui la sottosezione. D3 lo vuole sempre presente, con un avviso solo quando c'è davvero qualcosa da fare.

**Files:**
- Create: `frontend/src/components/ui/SectionEntryCard.tsx`
- Test: `frontend/src/components/ui/SectionEntryCard.test.tsx`
- Modify: `frontend/src/features/shopping-list/ShoppingListScreen.tsx:92-108`, `frontend/src/features/pantry/PantryScreen.tsx`, `frontend/src/features/recipes/RecipeBookScreen.tsx:106-122`, e i rispettivi test

**Interfaces:**
- Consumes: niente.
- Produces: `SectionEntryCard({ to, title, note, pending }: { to: string; title: string; note: string; pending?: boolean })`

- [ ] **Step 1: Scrivi il test che fallisce**

Crea `frontend/src/components/ui/SectionEntryCard.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { SectionEntryCard } from "./SectionEntryCard";

function renderCard(pending: boolean, note: string) {
  return render(
    <MemoryRouter>
      <SectionEntryCard to="/sistema" title="Sistema la spesa" note={note} pending={pending} />
    </MemoryRouter>
  );
}

describe("SectionEntryCard", () => {
  it("resta un collegamento anche quando non c'è niente da fare", () => {
    // è il punto della voce: una sottosezione che sparisce quando è vuota non si
    // può visitare apposta
    renderCard(false, "Niente di spuntato, per ora");
    const link = screen.getByRole("link", { name: /Sistema la spesa/ });
    expect(link.getAttribute("href")).toBe("/sistema");
    expect(screen.getByText("Niente di spuntato, per ora")).toBeDefined();
  });

  it("quando c'è da fare prende il fondo ambra e il pallino", () => {
    const { container } = renderCard(true, "3 voci spuntate da mettere via");
    expect(screen.getByRole("link", { name: /Sistema la spesa/ })).toHaveClass("bg-low-tint");
    // il pallino è decorazione: il messaggio lo porta la nota, che si legge
    expect(container.querySelector(".bg-low")).not.toBeNull();
  });

  it("senza da fare non c'è né pallino né ambra", () => {
    const { container } = renderCard(false, "Niente di spuntato, per ora");
    expect(screen.getByRole("link", { name: /Sistema la spesa/ })).not.toHaveClass("bg-low-tint");
    expect(container.querySelector(".bg-low")).toBeNull();
  });
});
```

- [ ] **Step 2: Falla fallire**

Run: `cd frontend && npx vitest run src/components/ui/SectionEntryCard.test.tsx`
Expected: FAIL — `Failed to resolve import "./SectionEntryCard"`.

- [ ] **Step 3: Scrivi il componente**

Crea `frontend/src/components/ui/SectionEntryCard.tsx`:

```tsx
import { Link } from "react-router-dom";

/** L'ingresso a una sottosezione, in cima alla sezione madre.
 *
 * Sempre presente (D3 di docs/prossimi-passi.md). Sparire quando non c'è niente da
 * fare è ciò che rende una sottosezione irraggiungibile proprio quando la si vuole
 * visitare apposta — per sistemare una spesa che non si è spuntata, per rivedere
 * una decisione già presa.
 *
 * L'ambra è lo stesso colore di «quasi finito»: nell'app vuol dire «c'è qualcosa
 * che ti riguarda», non «è andato male qualcosa». Il pallino è decorazione e basta:
 * il messaggio lo porta la nota, che si legge anche con la voce.
 */
export function SectionEntryCard({
  to,
  title,
  note,
  pending = false,
}: {
  to: string;
  title: string;
  /** che cosa c'è da fare, o perché non c'è niente: mai vuota */
  note: string;
  pending?: boolean;
}) {
  return (
    <Link
      to={to}
      className={`mb-3 flex min-h-14 items-center justify-between gap-3 rounded-card px-3.5 py-2.5 ${
        pending ? "bg-low-tint text-low" : "bg-card text-ink"
      }`}
    >
      <span className="min-w-0">
        <span className="flex items-center gap-2 font-medium">
          {pending && (
            <span aria-hidden="true" className="size-2 shrink-0 rounded-full bg-low" />
          )}
          {title}
        </span>
        <span className={`block truncate text-sm ${pending ? "text-low" : "text-ink-soft"}`}>
          {note}
        </span>
      </span>
      <span aria-hidden="true" className="shrink-0">›</span>
    </Link>
  );
}
```

- [ ] **Step 4: Falla passare**

Run: `cd frontend && npx vitest run src/components/ui/SectionEntryCard.test.tsx`
Expected: PASS, 3 test.

- [ ] **Step 5: La scheda in cima alla Lista**

In `frontend/src/features/shopping-list/ShoppingListScreen.tsx` aggiungi l'import `import { SectionEntryCard } from "../../components/ui/SectionEntryCard";` e sostituisci il blocco condizionale delle righe 92-108 con:

```tsx
      {/* sempre presente, anche a zero spuntate: «sistema la spesa» è una
          sottosezione, non un avviso. Vedi D3 in docs/prossimi-passi.md */}
      <div className="px-4 pb-1">
        <SectionEntryCard
          to="/sistema"
          title="Sistema la spesa"
          note={
            checkedCount === 0
              ? "Niente di spuntato, per ora"
              : checkedCount === 1
                ? "1 voce spuntata da mettere via"
                : `${checkedCount} voci spuntate da mettere via`
          }
          pending={checkedCount > 0}
        />
      </div>
```

`buttonClasses` e `Link` restano importati solo se altro nel file li usa: se l'eslint segnala un import inutilizzato, toglilo.

- [ ] **Step 6: La stessa scheda in cima alla Dispensa**

**Nota sui test già esistenti:** quelli di `PantryScreen.test.tsx` rispondono con la stessa risposta a ogni percorso, quindi la nuova query della lista riceverà voci di dispensa. Nessuna di loro ha `status: "checked"`, quindi il conteggio è zero e la scheda resta nel suo stato tranquillo: non si rompe niente e non serve toccarli. Se preferisci renderlo esplicito, passa a `stubRoutedFetch` e fai rispondere `[]` a `/shopping-list`.

D3 la vuole in cima **sia** a Lista **sia** a Dispensa. In `frontend/src/features/pantry/PantryScreen.tsx` aggiungi gli import:

```tsx
import { SectionEntryCard } from "../../components/ui/SectionEntryCard";
import { fetchShoppingList } from "../shopping-list/api";
```

e dentro il componente, sotto la query della dispensa:

```tsx
  // la stessa chiave dello schermo Lista: la cache è una sola, e aprire la dispensa
  // dopo la lista non ricarica niente. Se non risponde non si mostra un conteggio
  // sbagliato — la scheda resta, con una nota che non promette nulla: l'ingresso
  // alla sottosezione non deve dipendere da una seconda chiamata
  const { data: shopping, isError: isShoppingError } = useQuery({
    queryKey: ["shopping-list"],
    queryFn: () => fetchShoppingList(),
  });
  const checkedCount = (shopping ?? []).filter((item) => item.status === "checked").length;
```

e come prima cosa dentro `<Screen title="Dispensa">`:

```tsx
      <SectionEntryCard
        to="/sistema"
        title="Sistema la spesa"
        note={
          isShoppingError || shopping === undefined
            ? "Metti via quello che hai comprato"
            : checkedCount === 0
              ? "Niente di spuntato, per ora"
              : checkedCount === 1
                ? "1 voce spuntata da mettere via"
                : `${checkedCount} voci spuntate da mettere via`
        }
        pending={checkedCount > 0}
      />
```

- [ ] **Step 7: La scheda in cima alle Ricette**

In `frontend/src/features/recipes/RecipeBookScreen.tsx` aggiungi `import { SectionEntryCard } from "../../components/ui/SectionEntryCard";` e sostituisci il blocco condizionale delle righe 106-122 con:

```tsx
      <SectionEntryCard
        to="/ricette/importa"
        title="Ingredienti da abbinare"
        note={
          importStatus === undefined
            ? "Le decisioni dell'import, da rivedere"
            : importStatus.pending_terms === 0
              ? "Niente in attesa: qui si rivedono le decisioni già prese"
              : `${importStatus.pending_terms === 1 ? "1 ingrediente" : `${importStatus.pending_terms} ingredienti`}, ` +
                `${importStatus.pending_recipes === 1 ? "1 ricetta in attesa" : `${importStatus.pending_recipes} ricette in attesa`}`
        }
        pending={(importStatus?.pending_terms ?? 0) > 0}
      />
```

- [ ] **Step 8: Prova che restano anche a zero**

In `frontend/src/features/recipes/RecipeBookScreen.test.tsx` aggiungi:

```tsx
  it("l'ingresso agli ingredienti da abbinare resta anche con la coda vuota", async () => {
    // prima spariva: la revisione delle decisioni già prese diventava irraggiungibile
    // proprio quando non c'era più niente da decidere
    stubFetch({ pending_terms: 0, pending_recipes: 0 });
    renderScreen();
    const link = await screen.findByRole("link", { name: /Ingredienti da abbinare/ });
    expect(link.getAttribute("href")).toBe("/ricette/importa");
    expect(link).not.toHaveClass("bg-low-tint");
  });
```

Adatta `stubFetch`/`renderScreen` agli helper che il file già usa: la risposta di `/imports/status` deve avere `pending_terms: 0`.

In `frontend/src/features/shopping-list/ShoppingListScreen.test.tsx`:

```tsx
  it("l'ingresso a «Sistema la spesa» resta anche senza voci spuntate", async () => {
    // stub: la lista risponde con voci tutte `pending`
    renderScreen();
    const link = await screen.findByRole("link", { name: /Sistema la spesa/ });
    expect(link.getAttribute("href")).toBe("/sistema");
    expect(screen.getByText("Niente di spuntato, per ora")).toBeDefined();
  });
```

- [ ] **Step 9: Tutto verde**

Run: `cd frontend && npx vitest run && npm run typecheck && npm run build`
Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add frontend/src
git commit -m "$(cat <<'MSG'
feat: le sottosezioni hanno una scheda d'ingresso che non sparisce

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Task 4: Disfare l'archiviazione (S1, backend)

Archiviare è già reversibile nel database: `archived_at` torna a `NULL` e la voce ricompare, perché `list_pantry` filtra su quello. Manca solo il modo di chiederlo.

**Files:**
- Modify: `backend/app/schemas/pantry.py:29-31`, `backend/app/repositories/pantry.py:119-125`, `backend/app/api/pantry.py:86-102`
- Test: `backend/tests/api/test_pantry.py`

**Interfaces:**
- Consumes: `archive_item(session, item_id) -> PantryItem`, già esistente.
- Produces:
  - `unarchive_item(session: AsyncSession, item_id: uuid.UUID) -> PantryItem` in `app/repositories/pantry.py`, `KeyError` se la voce non esiste;
  - `PantryItemPatch.archived: bool | None` — `None` significa «non toccare», `True` archivia, `False` disarchivia;
  - `PATCH /api/v1/pantry/{id}` accetta `{"archived": false}`.

- [ ] **Step 1: Scrivi i test che falliscono**

In coda a `backend/tests/api/test_pantry.py`:

```python
async def test_un_archiviato_torna_in_dispensa(logged_client, db_session, dispensa):
    """L'annulla della X rossa. Archiviare era già reversibile, mancava come chiederlo."""
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()

    await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"archived": True})
    elenco = (await logged_client.get("/api/v1/pantry")).json()
    assert all(voce["id"] != str(item.id) for voce in elenco)

    risposta = await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"archived": False})
    assert risposta.status_code == 200
    elenco = (await logged_client.get("/api/v1/pantry")).json()
    assert any(voce["id"] == str(item.id) for voce in elenco)


async def test_cambiare_stato_non_disarchivia_per_sbaglio(logged_client, db_session, dispensa):
    """`archived` era un bool con default False: ogni PATCH ne portava uno.

    Ora è annullabile, e «non l'ho detto» deve restare diverso da «mettilo a falso».
    Senza questa distinzione una PATCH di solo stato riporterebbe in dispensa una
    voce che l'utente aveva tolto.
    """
    from datetime import UTC, datetime

    item = PantryItem(
        ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE,
        archived_at=datetime.now(UTC),
    )
    db_session.add(item)
    await db_session.flush()

    risposta = await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"status": "low"})
    assert risposta.status_code == 200
    await db_session.refresh(item)
    assert item.archived_at is not None


async def test_una_patch_vuota_resta_un_400(logged_client, db_session, dispensa):
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()

    risposta = await logged_client.patch(f"/api/v1/pantry/{item.id}", json={})
    assert risposta.status_code == 400


async def test_disarchiviare_una_voce_inesistente_e_404(logged_client):
    import uuid

    risposta = await logged_client.patch(
        f"/api/v1/pantry/{uuid.uuid4()}", json={"archived": False}
    )
    assert risposta.status_code == 404
```

- [ ] **Step 2: Falli fallire**

Run: `cd backend && .venv/bin/python -m pytest tests/api/test_pantry.py -v`
Expected: FAIL — `test_un_archiviato_torna_in_dispensa` riceve 400 («niente da modificare»), perché `archived: False` è falso e la PATCH non ha altro da fare.

- [ ] **Step 3: Rendi `archived` annullabile**

In `backend/app/schemas/pantry.py`:

```python
class PantryItemPatch(BaseModel):
    status: PantryStatus | None = None
    # annullabile, e non `bool = False`: «non l'ho detto» e «mettilo a falso» sono
    # due richieste diverse, e la seconda è l'annulla della X rossa
    archived: bool | None = None
```

- [ ] **Step 4: Scrivi `unarchive_item`**

In `backend/app/repositories/pantry.py`, sotto `archive_item`:

```python
async def unarchive_item(session: AsyncSession, item_id: uuid.UUID) -> PantryItem:
    """L'annulla della X rossa: la voce torna in dispensa com'era.

    Lo stato non si tocca — chi archivia una voce «quasi finita» e si pente la
    rivuole quasi finita, non riportata a un valore scelto da noi.
    """
    item = await session.get(PantryItem, item_id)
    if item is None:
        raise KeyError(item_id)
    item.archived_at = None
    await session.flush()
    return item
```

- [ ] **Step 5: Il ramo nella rotta**

In `backend/app/api/pantry.py` aggiungi `unarchive_item` all'import da `app.repositories.pantry` e sostituisci il corpo di `patch`:

```python
    try:
        if payload.archived is not None:
            item = (
                await archive_item(session, item_id)
                if payload.archived
                else await unarchive_item(session, item_id)
            )
        elif payload.status is not None:
            item = await set_status(session, item_id, payload.status)
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "niente da modificare")
```

- [ ] **Step 6: Falli passare**

Run: `cd backend && .venv/bin/python -m pytest tests/api/test_pantry.py -v`
Expected: PASS.

- [ ] **Step 7: Nessun'altra rottura**

Run: `cd backend && .venv/bin/python -m pytest`
Expected: PASS, tutta la suite.

- [ ] **Step 8: Commit**

```bash
git add backend/app/schemas/pantry.py backend/app/repositories/pantry.py backend/app/api/pantry.py backend/tests/api/test_pantry.py
git commit -m "$(cat <<'MSG'
feat: una voce archiviata può tornare in dispensa

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Task 5: La X rossa con l'annulla (S1, frontend)

Il link «Togli dalla dispensa» diventa una X rossa. Perché una X non sia un vicolo cieco, la riga non sparisce subito: resta sei secondi come lapide, con l'annulla dentro.

**Nota per chi implementa:** la lista **non** si invalida al momento dell'archiviazione. È quello che tiene la riga dov'era: invalidando, la voce sparirebbe dalla risposta del server e la lapide non avrebbe più un posto in cui stare. L'invalidazione arriva alla scadenza o all'annulla.

**Files:**
- Create: `frontend/src/features/pantry/PantryRow.tsx`
- Modify: `frontend/src/features/pantry/PantryScreen.tsx`, `frontend/src/features/pantry/PantryScreen.test.tsx`

**Interfaces:**
- Consumes: `patchPantryItem(id, { archived?: boolean })`, già esistente e già capace di mandare `false`.
- Produces: `PantryRow({ item, busy, removed, failed, onStatus, onRemove, onUndo })`, con
  `item: PantryItem`, `busy: boolean`, `removed: boolean`, `failed: boolean`,
  `onStatus: (status: PantryStatus) => void`, `onRemove: () => void`, `onUndo: () => void`.
  I task 9 e 11 aggiungeranno a questa firma `onFill` e `onRestock` e toglieranno `onStatus`.

- [ ] **Step 1: Scrivi i test che falliscono**

In `frontend/src/features/pantry/PantryScreen.test.tsx`, dentro `describe("PantryScreen", …)`:

```tsx
  it("la X toglie la voce dalla dispensa e lascia un annulla al suo posto", async () => {
    const fetchMock = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [{ ...ITEMS[2], id: "p3" }, 200];
      return [ITEMS, 200];
    });
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Togli mela dalla dispensa" }));

    const patch = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === "PATCH");
    expect(JSON.parse(String((patch![1] as RequestInit).body))).toEqual({ archived: true });
    expect(await screen.findByText("Tolta dalla dispensa")).toBeDefined();
    expect(screen.getByRole("button", { name: "Annulla" })).toBeDefined();
  });

  it("annullare la rimette in dispensa con una PATCH che disarchivia", async () => {
    // il difetto che questo test difende: un annulla che si limita a nascondere la
    // lapide lascerebbe la voce archiviata sul server, e l'utente scoprirebbe di
    // averla persa solo al ricaricamento
    const fetchMock = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [ITEMS[2], 200];
      return [ITEMS, 200];
    });
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Togli mela dalla dispensa" }));
    await userEvent.click(await screen.findByRole("button", { name: "Annulla" }));

    const corpi = fetchMock.mock.calls
      .filter(([, init]) => (init as RequestInit)?.method === "PATCH")
      .map(([, init]) => JSON.parse(String((init as RequestInit).body)));
    expect(corpi).toEqual([{ archived: true }, { archived: false }]);
    await waitFor(() => expect(screen.queryByText("Tolta dalla dispensa")).toBeNull());
  });

  it("passati i secondi dell'annulla la riga se ne va", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const utente = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    try {
      stubRoutedFetch((path, init) => {
        if (init?.method === "PATCH") return [ITEMS[2], 200];
        // dopo l'archiviazione il server non manda più la mela
        return [ITEMS.filter((item) => item.id !== "p3"), 200];
      });
      renderScreen();
      // la prima lettura è quella con la mela: la si aspetta prima di sostituirla
      await utente.click(await screen.findByRole("button", { name: "Togli mela dalla dispensa" }));
      expect(await screen.findByText("Tolta dalla dispensa")).toBeDefined();

      await vi.advanceTimersByTimeAsync(6000);

      await waitFor(() => expect(screen.queryByText("Tolta dalla dispensa")).toBeNull());
    } finally {
      vi.useRealTimers();
    }
  });

  it("una X che fallisce lo dice accanto alla voce, e la voce resta", async () => {
    stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [{ detail: "no" }, 500];
      return [ITEMS, 200];
    });
    renderScreen();

    await userEvent.click(await screen.findByRole("button", { name: "Togli mela dalla dispensa" }));

    expect(await screen.findByText("Non sono riuscito a salvare la modifica. Riprova.")).toBeDefined();
    expect(screen.getByText("mela")).toBeDefined();
  });
```

La prima riga del file deve importare anche `waitFor` da `@testing-library/react`, se non c'è già.

- [ ] **Step 2: Falli fallire**

Run: `cd frontend && npx vitest run src/features/pantry/PantryScreen.test.tsx`
Expected: FAIL — `Unable to find an accessible element with the role "button" and name "Togli mela dalla dispensa"`: oggi il bersaglio si chiama «Togli dalla dispensa», uguale su ogni riga.

- [ ] **Step 3: Estrai la riga**

Crea `frontend/src/features/pantry/PantryRow.tsx`:

```tsx
import { StatusToggle } from "./StatusToggle";
import { Alert } from "../../components/ui/Alert";
import type { PantryItem, PantryStatus } from "../../domain/types";

/** Il nome con cui l'utente chiama questa voce: la marca se c'è, l'ingrediente
 * altrimenti. Entra anche nel nome accessibile della X, perché «Togli dalla
 * dispensa» ripetuto identico su trenta righe non dice quale riga si sta togliendo. */
export function itemLabel(item: PantryItem): string {
  return item.product_name ?? item.ingredient_name;
}

/** Una riga della dispensa.
 *
 * `removed` è la lapide: la riga resta dov'era, con l'annulla dentro, per i secondi
 * in cui il gesto si può disfare. Sparisce da sé quando lo schermo ricarica.
 */
export function PantryRow({
  item,
  busy,
  removed,
  failed,
  onStatus,
  onRemove,
  onUndo,
}: {
  item: PantryItem;
  busy: boolean;
  removed: boolean;
  failed: boolean;
  onStatus: (status: PantryStatus) => void;
  onRemove: () => void;
  onUndo: () => void;
}) {
  if (removed) {
    return (
      <li className="flex min-h-14 items-center justify-between gap-3 p-3" role="status">
        <span className="min-w-0 truncate text-ink-soft">
          <span className="font-medium text-ink">{itemLabel(item)}</span> Tolta dalla dispensa
        </span>
        <button
          type="button"
          onClick={onUndo}
          className="min-h-11 shrink-0 px-2 text-sm font-medium text-brand"
        >
          Annulla
        </button>
      </li>
    );
  }

  return (
    <li className="flex flex-col gap-2.5 p-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          {/* la marca che hai comprato è più utile del nome generico */}
          <span className="font-medium">{itemLabel(item)}</span>
          {/* lo spazio è scritto a mano perché `ml-2` è un margine, non del testo:
              senza, il nome accessibile della riga si legge «Total 0%Fage» */}
          {item.product_brand && (
            <>
              {" "}
              <span className="text-sm text-ink-faint">{item.product_brand}</span>
            </>
          )}
        </div>
        {/* una X, non più un link testuale. Il nome accessibile resta una frase
            intera e nomina la voce: è anche il nome con cui si comanda a voce
            questo bersaglio, e «Togli dalla dispensa» su trenta righe è ambiguo */}
        <button
          type="button"
          disabled={busy}
          onClick={onRemove}
          aria-label={`Togli ${itemLabel(item)} dalla dispensa`}
          className="-mt-1 -mr-1 flex size-11 shrink-0 items-center justify-center rounded-full text-danger disabled:opacity-40"
        >
          <svg
            viewBox="0 0 24 24"
            aria-hidden="true"
            className="size-5"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
          >
            <path d="M6 6l12 12M18 6L6 18" />
          </svg>
        </button>
      </div>
      <StatusToggle value={item.status} disabled={busy} onChange={onStatus} />
      {failed && <Alert>Non sono riuscito a salvare la modifica. Riprova.</Alert>}
    </li>
  );
}
```

- [ ] **Step 4: Lo schermo usa la riga, e tiene la lapide**

In `frontend/src/features/pantry/PantryScreen.tsx`: togli l'import di `StatusToggle`, aggiungi `import { useEffect, useState } from "react";` e `import { PantryRow } from "./PantryRow";`, e sostituisci la mutazione `archive` con:

```tsx
  // quanto dura l'annulla. Sei secondi: il tempo di accorgersi di aver sbagliato
  // riga senza che la dispensa resti mezza finta per mezzo minuto
  const UNDO_MS = 6000;

  // la voce appena tolta, finché l'annulla è possibile. La lista NON si invalida
  // qui: invalidando, la voce sparirebbe dalla risposta del server e la lapide non
  // avrebbe più un posto dov'essere
  const [removedId, setRemovedId] = useState<string | null>(null);

  const archive = useMutation({
    mutationFn: (id: string) => patchPantryItem(id, { archived: true }),
    onMutate: () => setFailedId(null),
    onSuccess: (_data, id) => setRemovedId(id),
    onError: (_error, id) => setFailedId(id),
  });

  const undo = useMutation({
    mutationFn: (id: string) => patchPantryItem(id, { archived: false }),
    onSuccess: () => {
      setRemovedId(null);
      invalidate();
    },
    // l'annulla fallito non può far finta di niente: la voce è archiviata davvero,
    // quindi si ricarica (e sparisce) e si dice che non è tornata
    onError: (_error, id) => {
      setRemovedId(null);
      setFailedId(id);
      invalidate();
    },
  });

  useEffect(() => {
    if (removedId === null) return;
    const timer = setTimeout(() => {
      setRemovedId(null);
      invalidate();
    }, UNDO_MS);
    return () => clearTimeout(timer);
    // `invalidate` è ricreata a ogni render: metterla fra le dipendenze rifarebbe
    // partire il conto alla rovescia da capo a ogni render, e la lapide non
    // scadrebbe mai
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [removedId]);
```

Sostituisci poi il corpo del `map` sulle voci con:

```tsx
                {group.map((item) => (
                  <PantryRow
                    key={item.id}
                    item={item}
                    busy={busyId === item.id}
                    removed={removedId === item.id}
                    failed={failedId === item.id}
                    onStatus={(status) => change.mutate({ id: item.id, status })}
                    onRemove={() => archive.mutate(item.id)}
                    onUndo={() => undo.mutate(item.id)}
                  />
                ))}
```

`UNDO_MS` va dichiarata fuori dal componente, accanto agli altri valori di modulo.

- [ ] **Step 5: Falli passare**

Run: `cd frontend && npx vitest run src/features/pantry/PantryScreen.test.tsx`
Expected: PASS.

- [ ] **Step 6: Tutto verde**

Run: `cd frontend && npx vitest run && npm run typecheck`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/features/pantry
git commit -m "$(cat <<'MSG'
feat: togliere dalla dispensa è una X rossa, e si può annullare

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Task 6: La regola posizione → stato (S2, dominio)

**Files:**
- Modify: `backend/app/domain/rules.py`
- Test: `backend/tests/domain/test_rules.py`

**Interfaces:**
- Consumes: `PantryStatus`, già in questo modulo.
- Produces: `LOW_MAX_FILL: int = 30` e `status_for_fill(fill_percent: int) -> PantryStatus`.

- [ ] **Step 1: Scrivi i test che falliscono**

In coda a `backend/tests/domain/test_rules.py`:

```python
@pytest.mark.parametrize(
    "posizione, atteso",
    [
        (0, PantryStatus.FINISHED),
        (1, PantryStatus.LOW),
        (15, PantryStatus.LOW),
        (LOW_MAX_FILL, PantryStatus.LOW),
        (LOW_MAX_FILL + 1, PantryStatus.AVAILABLE),
        (100, PantryStatus.AVAILABLE),
    ],
)
def test_la_posizione_del_cursore_decide_lo_stato(posizione, atteso):
    assert status_for_fill(posizione) is atteso


def test_le_tre_zone_coprono_tutto_e_non_tornano_indietro():
    """Nessun buco fra 0 e 100, e nessuna inversione.

    Una soglia scritta con un `<` al posto di un `<=` lascia un valore scoperto o
    crea un'isola gialla dentro il verde, e un test a campione può non passarci
    sopra. Qui si controllano tutti e 101 i valori.
    """
    ordine = {PantryStatus.FINISHED: 0, PantryStatus.LOW: 1, PantryStatus.AVAILABLE: 2}
    gradini = [ordine[status_for_fill(posizione)] for posizione in range(0, 101)]
    assert gradini == sorted(gradini)
    assert set(gradini) == {0, 1, 2}
```

L'import in cima al file diventa:

```python
from app.domain.rules import (
    LOW_MAX_FILL,
    Availability,
    IngredientRole,
    PantryStatus,
    availability_of,
    default_role,
    is_cookable,
    is_satisfied,
    missing_count,
    status_for_fill,
)
```

Se il file importa in un altro modo (per esempio `from app.domain import rules`), aggiungi solo i due nomi nuovi nello stesso stile; `import pytest` c'è già.

- [ ] **Step 2: Falli fallire**

Run: `cd backend && .venv/bin/python -m pytest tests/domain/test_rules.py -v`
Expected: FAIL — `ImportError: cannot import name 'LOW_MAX_FILL'`.

- [ ] **Step 3: Scrivi la regola**

In `backend/app/domain/rules.py`, sotto `is_cookable`:

```python
# Il secondo pallino del cursore della dispensa: fin qui è «quasi finito», oltre è
# «disponibile». 30 e non 50: la zona gialla deve dire «comincia a mancare», non
# «siamo a metà».
#
# È una soglia display con una conseguenza che display non è: `low` è l'unico stato
# che cambia la risposta a «questa ricetta si può cucinare?» (vedi `is_satisfied`),
# quindi spostare questo numero sposta quali ricette risultano cucinabili. Va fatto
# sapendolo, e non in un foglio di stile.
LOW_MAX_FILL = 30


def status_for_fill(fill_percent: int) -> PantryStatus:
    """Dove sta il cursore → quale dei tre stati è la verità.

    La posizione è un'indicazione a occhio, utile in negozio per ricordarsi quanto
    ne resta; lo stato è l'unico giudizio su cui il resto dell'app ragiona. Vive qui
    e non nel frontend per la ragione di ogni altra regola di questo modulo: il
    client chiede, non calcola.
    """
    if fill_percent <= 0:
        return PantryStatus.FINISHED
    if fill_percent <= LOW_MAX_FILL:
        return PantryStatus.LOW
    return PantryStatus.AVAILABLE
```

- [ ] **Step 4: Falli passare**

Run: `cd backend && .venv/bin/python -m pytest tests/domain/test_rules.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/domain/rules.py backend/tests/domain/test_rules.py
git commit -m "$(cat <<'MSG'
feat: la posizione del cursore della dispensa decide lo stato, nel dominio

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Task 7: La colonna `fill_percent` (S2, schema)

**Files:**
- Create: `backend/alembic/versions/0006_slider_dispensa.py`
- Modify: `backend/app/db/models/pantry.py`, `backend/app/schemas/pantry.py`, `backend/app/api/pantry.py:26-38`
- Test: `backend/tests/db/test_pantry_shopping_schema.py`

**Interfaces:**
- Consumes: niente.
- Produces: `PantryItem.fill_percent: int | None` (SmallInteger, 0–100, annullabile) e `PantryItemOut.fill_percent: int | None`.

- [ ] **Step 1: Scrivi i test che falliscono**

In coda a `backend/tests/db/test_pantry_shopping_schema.py`:

```python
async def test_una_voce_senza_posizione_resta_valida(db_session):
    """Le voci già in dispensa non hanno mai visto un cursore.

    NULL è quel che sappiamo di loro. Riempirle con 100 sarebbe un'affermazione —
    «piena» — che nessuno ha mai fatto, e il cursore la mostrerebbe come una misura.
    """
    ingredient = await _ingredient(db_session, "mela")
    item = PantryItem(ingredient_id=ingredient.id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()
    assert item.fill_percent is None


async def test_la_posizione_sta_fra_zero_e_cento(db_session):
    ingredient = await _ingredient(db_session, "farina")
    db_session.add(
        PantryItem(
            ingredient_id=ingredient.id, status=PantryStatus.AVAILABLE, fill_percent=101
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.flush()
```

- [ ] **Step 2: Falli fallire**

Run: `cd backend && .venv/bin/python -m pytest tests/db/test_pantry_shopping_schema.py -v`
Expected: FAIL — `TypeError: 'fill_percent' is an invalid keyword argument for PantryItem`.

- [ ] **Step 3: Scrivi la migrazione**

Crea `backend/alembic/versions/0006_slider_dispensa.py`:

```python
"""la posizione del cursore accanto allo stato, in dispensa

Revision ID: 0006
"""
import sqlalchemy as sa
from alembic import op

revision = "0006"
down_revision = "0005"


def upgrade() -> None:
    # annullabile perché le voci già in dispensa non hanno mai visto un cursore, e
    # un valore di comodo sarebbe una misura inventata. SmallInteger: sono 0–100
    op.add_column("pantry_items", sa.Column("fill_percent", sa.SmallInteger(), nullable=True))
    op.create_check_constraint(
        "ck_pantry_fill_percent", "pantry_items", "fill_percent BETWEEN 0 AND 100"
    )


def downgrade() -> None:
    op.drop_constraint("ck_pantry_fill_percent", "pantry_items", type_="check")
    op.drop_column("pantry_items", "fill_percent")
```

- [ ] **Step 4: Dichiara la colonna sul modello**

In `backend/app/db/models/pantry.py` aggiungi `SmallInteger` all'import da `sqlalchemy`, il vincolo fra i `__table_args__`:

```python
        CheckConstraint(
            "fill_percent BETWEEN 0 AND 100", name="ck_pantry_fill_percent"
        ),
```

e la colonna accanto a `status`:

```python
    # Dove sta il cursore a tre zone, 0–100. È un'indicazione a occhio — utile in
    # negozio, e per seguire qualcosa che si consuma senza mai finire — non una
    # quantità: niente unità, niente conversioni, nessun conto la usa. Lo stato qui
    # sopra resta la verità, e `status_for_fill` è ciò che li tiene d'accordo.
    # NULL per chi non l'ha mai mosso.
    fill_percent: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
```

- [ ] **Step 5: Portala in uscita**

In `backend/app/schemas/pantry.py`, dentro `PantryItemOut`, sotto `status`:

```python
    fill_percent: int | None
```

e in `backend/app/api/pantry.py`, dentro `_to_out`, sotto `status=item.status,`:

```python
        fill_percent=item.fill_percent,
```

- [ ] **Step 6: Falli passare**

Run: `cd backend && .venv/bin/python -m pytest tests/db -v`
Expected: PASS, compreso `test_models_describe_the_migrated_schema` — se quello fallisce, modello e migrazione non dicono la stessa cosa (tipo della colonna, o nome).

- [ ] **Step 7: Nessun'altra rottura**

Run: `cd backend && .venv/bin/python -m pytest`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend/alembic/versions/0006_slider_dispensa.py backend/app/db/models/pantry.py backend/app/schemas/pantry.py backend/app/api/pantry.py backend/tests/db/test_pantry_shopping_schema.py
git commit -m "$(cat <<'MSG'
feat: pantry_items porta la posizione del cursore, annullabile

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Task 8: Salvare la posizione (S2, API)

**Files:**
- Modify: `backend/app/repositories/pantry.py:109-116`, `backend/app/schemas/pantry.py`, `backend/app/api/pantry.py:86-102`
- Test: `backend/tests/api/test_pantry.py`

**Interfaces:**
- Consumes: `status_for_fill` (Task 6), `PantryItem.fill_percent` (Task 7), il ramo `archived` (Task 4).
- Produces:
  - `set_fill(session: AsyncSession, item_id: uuid.UUID, fill_percent: int) -> PantryItem`;
  - `PantryItemPatch.fill_percent: int | None` con `ge=0, le=100`;
  - `PATCH /api/v1/pantry/{id}` accetta `{"fill_percent": 0..100}` e risponde con `status` già ricavato.

- [ ] **Step 1: Scrivi i test che falliscono**

In `backend/tests/api/test_pantry.py` aggiungi `import pytest` in cima, accanto a `import pytest_asyncio`, e i test in coda:

```python
@pytest.mark.parametrize(
    "posizione, stato_atteso",
    [(0, "finished"), (15, "low"), (30, "low"), (31, "available"), (100, "available")],
)
async def test_la_posizione_arriva_con_lo_stato_gia_ricavato(
    logged_client, db_session, dispensa, posizione, stato_atteso
):
    """Il client manda dove ha lasciato il dito; lo stato lo decide il dominio.

    È la riga che tiene la regola dalla parte giusta: se lo stato lo calcolasse il
    frontend, due schermi potrebbero non essere d'accordo su cosa vuol dire «quasi
    finito», e la cucinabilità delle ricette dipenderebbe da quale dei due ha
    scritto per ultimo.
    """
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()

    risposta = await logged_client.patch(
        f"/api/v1/pantry/{item.id}", json={"fill_percent": posizione}
    )
    assert risposta.status_code == 200
    assert risposta.json()["fill_percent"] == posizione
    assert risposta.json()["status"] == stato_atteso


async def test_una_posizione_fuori_scala_e_422(logged_client, db_session, dispensa):
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()
    risposta = await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"fill_percent": 101})
    assert risposta.status_code == 422


async def test_cambiare_lo_stato_a_mano_azzera_la_posizione(
    logged_client, db_session, dispensa
):
    """Una posizione lasciata lì sarebbe una bugia.

    Il foglio di cottura cambia lo stato senza toccare nessun cursore: se la
    posizione restasse a 80 mentre lo stato è «finito», la dispensa mostrerebbe un
    barattolo pieno per qualcosa che non c'è più. Sconosciuta è la verità.
    """
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.AVAILABLE)
    db_session.add(item)
    await db_session.flush()
    await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"fill_percent": 80})

    risposta = await logged_client.patch(f"/api/v1/pantry/{item.id}", json={"status": "finished"})
    assert risposta.json()["status"] == "finished"
    assert risposta.json()["fill_percent"] is None
```

- [ ] **Step 2: Falli fallire**

Run: `cd backend && .venv/bin/python -m pytest tests/api/test_pantry.py -v -k "posizione"`
Expected: FAIL — la PATCH con solo `fill_percent` torna 400 «niente da modificare», perché lo schema ignora il campo.

- [ ] **Step 3: Il campo nello schema**

In `backend/app/schemas/pantry.py`:

```python
class PantryItemPatch(BaseModel):
    status: PantryStatus | None = None
    # annullabile, e non `bool = False`: «non l'ho detto» e «mettilo a falso» sono
    # due richieste diverse, e la seconda è l'annulla della X rossa
    archived: bool | None = None
    # dove il dito ha lasciato il cursore. Lo stato non si manda: lo ricava il
    # dominio, ed è l'unico modo perché i due non possano contraddirsi
    fill_percent: int | None = Field(default=None, ge=0, le=100)
```

- [ ] **Step 4: `set_fill`, e `set_status` che azzera**

In `backend/app/repositories/pantry.py` aggiungi `status_for_fill` all'import da `app.domain.rules` e sostituisci `set_status`, aggiungendo `set_fill` sotto:

```python
async def set_status(session: AsyncSession, item_id: uuid.UUID, status: PantryStatus) -> PantryItem:
    item = await session.get(PantryItem, item_id)
    if item is None:
        raise KeyError(item_id)
    item.status = status
    # la posizione del cursore non sopravvive a uno stato deciso altrove: restare a
    # 80 mentre lo stato dice «finito» mostrerebbe un barattolo pieno per qualcosa
    # che non c'è più. Sconosciuta è la verità, e il cursore riparte dalla zona giusta
    item.fill_percent = None
    item.status_changed_at = datetime.now(UTC)
    await session.flush()
    return item


async def set_fill(session: AsyncSession, item_id: uuid.UUID, fill_percent: int) -> PantryItem:
    """La posizione e lo stato cambiano insieme, o uno dei due mente.

    Lo stato non arriva dal client: lo ricava `status_for_fill`, che è dove la
    regola vive. Vedi il commento su `LOW_MAX_FILL`.
    """
    item = await session.get(PantryItem, item_id)
    if item is None:
        raise KeyError(item_id)
    item.fill_percent = fill_percent
    item.status = status_for_fill(fill_percent)
    item.status_changed_at = datetime.now(UTC)
    await session.flush()
    return item
```

- [ ] **Step 5: Il terzo ramo nella rotta**

In `backend/app/api/pantry.py` aggiungi `set_fill` all'import da `app.repositories.pantry` e porta il corpo di `patch` a:

```python
    try:
        if payload.archived is not None:
            item = (
                await archive_item(session, item_id)
                if payload.archived
                else await unarchive_item(session, item_id)
            )
        elif payload.fill_percent is not None:
            # prima dello stato: una richiesta che porta entrambi viene dal cursore,
            # e lì lo stato è una conseguenza, non una seconda opinione
            item = await set_fill(session, item_id, payload.fill_percent)
        elif payload.status is not None:
            item = await set_status(session, item_id, payload.status)
        else:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "niente da modificare")
```

- [ ] **Step 6: Falli passare**

Run: `cd backend && .venv/bin/python -m pytest tests/api/test_pantry.py -v`
Expected: PASS.

- [ ] **Step 7: Nessun'altra rottura**

Run: `cd backend && .venv/bin/python -m pytest`
Expected: PASS.

**Resta un buco noto, e lo chiude il Task 10:** `cook()` scrive `item.status` direttamente e **non** passa da `set_status`, quindi una cottura lascia la posizione dov'era — 80 su una voce che ha appena dichiarato «finito». Nessun test lo vede oggi, perché nessuno guarda `fill_percent` dopo una cottura: è il tipo di bugia che si scopre soltanto guardando lo schermo. Il Task 10 tocca quel file e aggiunge lì `item.fill_percent = None`. Se salti il Task 10, la riga va aggiunta qui.

- [ ] **Step 8: Commit**

```bash
git add backend/app backend/tests
git commit -m "$(cat <<'MSG'
feat: la PATCH della dispensa salva la posizione e ne ricava lo stato

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Task 9: Il cursore a tre zone (S2, frontend)

`o--o------o`: il primo pallino è rosso e vuol dire finito, il tratto giallo arriva al secondo, il verde va fino in fondo. **Sostituisce** i tre pulsanti di `StatusToggle`: due controlli per la stessa verità, uno accanto all'altro, prima o poi si contraddicono.

**Files:**
- Create: `frontend/src/features/pantry/fillZones.ts`, `frontend/src/features/pantry/FillSlider.tsx`, `frontend/src/features/pantry/FillSlider.test.tsx`, `backend/tests/test_frontend_fill_zones.py`
- Modify: `frontend/src/domain/types.ts`, `frontend/src/features/pantry/api.ts`, `frontend/src/features/pantry/PantryRow.tsx`, `frontend/src/features/pantry/PantryScreen.tsx`, `frontend/src/features/pantry/PantryScreen.test.tsx`, `frontend/src/index.css`, `frontend/e2e/style.spec.ts`
- Delete: `frontend/src/features/pantry/StatusToggle.tsx`, `frontend/src/features/pantry/StatusToggle.test.tsx`

**Interfaces:**
- Consumes: `PATCH /pantry/{id}` con `{ fill_percent }` (Task 8); `PantryRow` (Task 5); `StatusChip` da `components/ui/StatusChip.tsx`, che esiste già e mostra uno stato senza chiedere niente.
- Produces:
  - `LOW_MAX_FILL: number` e `fillForStatus(status: PantryStatus): number` in `fillZones.ts`;
  - `FillSlider({ value, label, disabled, onCommit }: { value: number; label: string; disabled?: boolean; onCommit: (percent: number) => void })`;
  - `PantryItem.fill_percent: number | null` in `domain/types.ts`;
  - `patchPantryItem(id, { fill_percent })`;
  - `PantryRow` perde `onStatus` e guadagna `onFill: (percent: number) => void`.

- [ ] **Step 1: Scrivi i test che falliscono**

Crea `frontend/src/features/pantry/FillSlider.test.tsx`:

```tsx
import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { FillSlider } from "./FillSlider";

describe("FillSlider", () => {
  it("è un cursore da 0 a 100 e dice di cosa parla", () => {
    render(<FillSlider value={70} label="mela" onCommit={() => {}} />);
    const cursore = screen.getByRole("slider", { name: "Quanto ne resta di mela" });
    expect(cursore.getAttribute("min")).toBe("0");
    expect(cursore.getAttribute("max")).toBe("100");
    expect((cursore as HTMLInputElement).value).toBe("70");
  });

  it("mentre il dito trascina non manda niente: scrive quando lo si lascia", () => {
    // una PATCH per ogni pixel di trascinamento sarebbe una richiesta ogni pochi
    // millisecondi, e l'ultima a rispondere vincerebbe
    const onCommit = vi.fn();
    render(<FillSlider value={70} label="mela" onCommit={onCommit} />);
    const cursore = screen.getByRole("slider");

    fireEvent.change(cursore, { target: { value: "40" } });
    expect(onCommit).not.toHaveBeenCalled();

    fireEvent.pointerUp(cursore);
    expect(onCommit).toHaveBeenCalledWith(40);
  });

  it("lasciato dov'era non manda niente", () => {
    const onCommit = vi.fn();
    render(<FillSlider value={70} label="mela" onCommit={onCommit} />);
    fireEvent.pointerUp(screen.getByRole("slider"));
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("anche da tastiera si scrive, quando il tasto si alza", () => {
    const onCommit = vi.fn();
    render(<FillSlider value={70} label="mela" onCommit={onCommit} />);
    const cursore = screen.getByRole("slider");
    fireEvent.change(cursore, { target: { value: "75" } });
    fireEvent.keyUp(cursore, { key: "ArrowRight" });
    expect(onCommit).toHaveBeenCalledWith(75);
  });

  it("una posizione arrivata dal server riprende il comando", () => {
    // l'annulla, una ricarica, una cottura: quando la verità cambia da fuori il
    // cursore non può restare dove l'ha lasciato il dito
    const { rerender } = render(<FillSlider value={70} label="mela" onCommit={() => {}} />);
    fireEvent.change(screen.getByRole("slider"), { target: { value: "10" } });
    rerender(<FillSlider value={0} label="mela" onCommit={() => {}} />);
    expect((screen.getByRole("slider") as HTMLInputElement).value).toBe("0");
  });
});
```

E il test di parità, `backend/tests/test_frontend_fill_zones.py`:

```python
"""La soglia della zona gialla è una sola, scritta in due linguaggi.

Il backend decide lo stato dalla posizione; il frontend usa lo stesso numero solo
per dipingere le tre zone del cursore. Se i due divergono, il cursore mostra il
giallo dove il server ha già detto verde: nessun test lo vedrebbe, perché ciascuna
metà è coerente con sé stessa. Stesso schema di tests/test_frontend_categories.py.
"""

import re
from pathlib import Path

from app.domain.rules import LOW_MAX_FILL

REPO_ROOT = Path(__file__).resolve().parents[2]
FILL_ZONES_TS = REPO_ROOT / "frontend" / "src" / "features" / "pantry" / "fillZones.ts"


def test_la_soglia_della_zona_gialla_e_la_stessa_nei_due_linguaggi():
    contenuto = FILL_ZONES_TS.read_text()
    trovato = re.search(r"export const LOW_MAX_FILL\s*=\s*(\d+)", contenuto)

    assert trovato is not None, f"{FILL_ZONES_TS}: non dichiara più LOW_MAX_FILL"
    assert int(trovato.group(1)) == LOW_MAX_FILL, (
        f"{FILL_ZONES_TS} dice {trovato.group(1)}, "
        f"app/domain/rules.py dice {LOW_MAX_FILL}"
    )
```

- [ ] **Step 2: Falli fallire**

Run: `cd frontend && npx vitest run src/features/pantry/FillSlider.test.tsx`
Expected: FAIL — `Failed to resolve import "./FillSlider"`.

Run: `cd backend && .venv/bin/python -m pytest tests/test_frontend_fill_zones.py -v`
Expected: FAIL — `non dichiara più LOW_MAX_FILL` (il file non esiste ancora: la lettura solleva `FileNotFoundError`, che va bene come rosso).

- [ ] **Step 3: Le zone**

Crea `frontend/src/features/pantry/fillZones.ts`:

```ts
import type { PantryStatus } from "../../domain/types";

// Lo stesso numero di `LOW_MAX_FILL` in backend/app/domain/rules.py, e non una
// seconda decisione: qui serve solo a dipingere le tre zone del cursore, mentre a
// decidere lo stato è il backend. Che i due restino uguali lo difende
// backend/tests/test_frontend_fill_zones.py, che legge questo file.
export const LOW_MAX_FILL = 30;

/** Da dove parte il cursore di una voce che non ne ha mai avuto uno.
 *
 * `fill_percent` resta NULL nel database e nell'API: non è una misura, e non deve
 * poter essere scambiata per una. Questo è solo il punto da cui si comincia a
 * trascinare, scelto dentro la zona dello stato che la voce ha davvero — così il
 * primo tocco non sposta il significato di niente.
 */
export function fillForStatus(status: PantryStatus): number {
  if (status === "finished") return 0;
  if (status === "low") return Math.round(LOW_MAX_FILL / 2);
  return 100;
}
```

- [ ] **Step 4: Il cursore**

Crea `frontend/src/features/pantry/FillSlider.tsx`:

```tsx
import { useEffect, useState } from "react";
import { LOW_MAX_FILL } from "./fillZones";

// Le tre zone dipinte sulla traccia. I colori sono token (`var(--color-…)`), non
// valori grezzi: il rosso è lo stesso di ogni rifiuto, l'ambra lo stesso di «quasi
// finito», il verde lo stesso del marchio. Il primo tratto è corto di proposito —
// lo zero è un punto, non una zona in cui si atterra per caso.
const ZONES =
  "linear-gradient(to right," +
  " var(--color-danger) 0 3%," +
  ` var(--color-low-tint) 3% ${LOW_MAX_FILL}%,` +
  ` var(--color-brand-tint) ${LOW_MAX_FILL}% 100%)`;

/** Quanto ne resta, a occhio.
 *
 * Il valore si scrive quando il dito si alza, non a ogni scatto: una PATCH ogni
 * pochi millisecondi arriverebbe fuori ordine e l'ultima a rispondere vincerebbe.
 * Lo stato non si calcola qui — lo ricava il backend e lo mostra la pastiglia
 * accanto, che è l'unica cosa in questa riga a dire una verità.
 */
export function FillSlider({
  value,
  label,
  disabled = false,
  onCommit,
}: {
  value: number;
  /** che cosa si sta misurando: entra nel nome accessibile del cursore */
  label: string;
  disabled?: boolean;
  onCommit: (percent: number) => void;
}) {
  const [position, setPosition] = useState(value);

  // quando la verità cambia da fuori — l'annulla, una ricarica, una cottura — è
  // quella a comandare, non dove il dito aveva lasciato il cursore
  useEffect(() => setPosition(value), [value]);

  const commit = () => {
    if (position !== value) onCommit(position);
  };

  return (
    <div className="relative flex h-11 items-center">
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-x-0 h-2 rounded-full"
        style={{ backgroundImage: ZONES }}
      />
      <input
        type="range"
        min={0}
        max={100}
        step={5}
        value={position}
        disabled={disabled}
        aria-label={`Quanto ne resta di ${label}`}
        onChange={(event) => setPosition(Number(event.target.value))}
        onPointerUp={commit}
        onKeyUp={commit}
        onBlur={commit}
        className="relative h-11 w-full appearance-none bg-transparent disabled:opacity-50"
      />
    </div>
  );
}
```

- [ ] **Step 5: La forma del cursore, nel foglio di base**

In `frontend/src/index.css`, dentro `@layer base` e sotto la regola dei campi di testo:

```css
  /* Il cursore della dispensa. Le tre zone le dipinge il componente su un elemento
     dietro: qui c'è solo la forma, perché la traccia nativa non si colora allo
     stesso modo nei due motori. Il pallino è 28px e la zona toccabile 44px, come
     ogni altro bersaglio dell'app.

     Niente di tutto questo lo vede jsdom: Tailwind compila il CSS e i test in
     memoria non lo calcolano (quarta lezione di CLAUDE.md). La prova sta in
     frontend/e2e/style.spec.ts. */
  input[type="range"] {
    appearance: none;
    background-color: transparent;
  }

  input[type="range"]::-webkit-slider-runnable-track {
    height: 0.5rem;
    background: transparent;
  }

  input[type="range"]::-moz-range-track {
    height: 0.5rem;
    background: transparent;
  }

  input[type="range"]::-webkit-slider-thumb {
    appearance: none;
    width: 1.75rem;
    height: 1.75rem;
    margin-top: -0.625rem;
    border-radius: 999px;
    border: 2px solid var(--color-ink-soft);
    background-color: var(--color-card);
  }

  input[type="range"]::-moz-range-thumb {
    width: 1.75rem;
    height: 1.75rem;
    border-radius: 999px;
    border: 2px solid var(--color-ink-soft);
    background-color: var(--color-card);
  }
```

- [ ] **Step 6: Il tipo e la chiamata**

In `frontend/src/domain/types.ts`, dentro `PantryItem`, sotto `status`:

```ts
  /** Dove sta il cursore, 0–100. `null` per chi non l'ha mai mosso: è una posizione
   * a occhio, non una quantità, e non esiste finché nessuno l'ha indicata. */
  fill_percent: number | null;
```

In `frontend/src/features/pantry/api.ts`:

```ts
export function patchPantryItem(
  id: string,
  body: { status?: PantryStatus; archived?: boolean; fill_percent?: number }
) {
```

- [ ] **Step 7: Il cursore nella riga, al posto dei tre pulsanti**

In `frontend/src/features/pantry/PantryRow.tsx`: togli l'import di `StatusToggle`, aggiungi

```tsx
import { FillSlider } from "./FillSlider";
import { fillForStatus } from "./fillZones";
import { StatusChip } from "../../components/ui/StatusChip";
```

sostituisci nella firma `onStatus: (status: PantryStatus) => void;` con `onFill: (percent: number) => void;` (e togli `PantryStatus` dagli import di tipo se non serve più), e al posto della riga `<StatusToggle …/>`:

```tsx
      <FillSlider
        value={item.fill_percent ?? fillForStatus(item.status)}
        label={itemLabel(item)}
        disabled={busy}
        onCommit={onFill}
      />
      {/* la verità sullo stato la dice il server, e questa pastiglia è l'unica cosa
          nella riga a dirla: il cursore, da solo, è un'indicazione a occhio */}
      <StatusChip status={item.status} />
```

In `frontend/src/features/pantry/PantryScreen.tsx` sostituisci la mutazione `change` e l'uso nella riga:

```tsx
  const change = useMutation({
    mutationFn: ({ id, fill }: { id: string; fill: number }) =>
      patchPantryItem(id, { fill_percent: fill }),
    onMutate: () => setFailedId(null),
    onSuccess: invalidate,
    // senza questo una PATCH fallita non dice niente: il cursore torna da sé al
    // valore del server e l'utente resta convinto di averlo spostato
    onError: (_error, { id }) => setFailedId(id),
  });
```

```tsx
                    onFill={(percent) => change.mutate({ id: item.id, fill: percent })}
```

Togli l'import di `PantryStatus` da `PantryScreen.tsx` se non lo usa più nient'altro.

- [ ] **Step 8: Cancella il controllo che il cursore sostituisce**

```bash
git rm frontend/src/features/pantry/StatusToggle.tsx frontend/src/features/pantry/StatusToggle.test.tsx
```

`STATUS_LABELS` e `STATUS_TONE` **restano** in `statusLabels.ts`: li usano `StatusChip` e il foglio di cottura, e `statusLabels.test.ts` continua a difenderli.

- [ ] **Step 9: Aggiorna i test dello schermo**

In `frontend/src/features/pantry/PantryScreen.test.tsx`: aggiungi `fill_percent: null` a ciascuna delle tre voci di `ITEMS`, e sostituisci il test che cambiava stato con i tre pulsanti:

```tsx
  it("spostare il cursore manda la posizione, non lo stato", async () => {
    // lo stato lo ricava il backend: mandarlo da qui vorrebbe dire avere due
    // opinioni su cosa sia «quasi finito»
    const fetchMock = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [{ ...ITEMS[2], status: "low", fill_percent: 15 }, 200];
      return [ITEMS, 200];
    });
    renderScreen();

    const cursore = await screen.findByRole("slider", { name: "Quanto ne resta di mela" });
    fireEvent.change(cursore, { target: { value: "15" } });
    fireEvent.pointerUp(cursore);

    await waitFor(() => {
      const patch = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === "PATCH");
      expect(JSON.parse(String((patch![1] as RequestInit).body))).toEqual({ fill_percent: 15 });
    });
  });

  it("una voce che non ha mai visto il cursore parte dalla zona del suo stato", async () => {
    // `fill_percent` resta null: non si inventa una misura per riempire un buco
    stubRoutedFetch(() => [ITEMS, 200]);
    renderScreen();
    const cursore = await screen.findByRole("slider", { name: "Quanto ne resta di Pesca" });
    // ITEMS[1] è `low`: metà della zona gialla
    expect((cursore as HTMLInputElement).value).toBe("15");
  });
```

Importa `fireEvent` da `@testing-library/react` in cima al file.

- [ ] **Step 10: Falli passare**

Run: `cd frontend && npx vitest run && npm run typecheck && npm run build`
Expected: PASS.

Run: `cd backend && .venv/bin/python -m pytest tests/test_frontend_fill_zones.py -v`
Expected: PASS.

- [ ] **Step 11: Provalo in un browser vero**

In `frontend/e2e/style.spec.ts`, in coda:

```ts
test("il cursore della dispensa è un bersaglio da pollice, e le zone si vedono", async ({ page }) => {
  // jsdom non calcola il CSS: che il pallino esista, si veda e si possa toccare
  // non lo può dire nessun test in memoria (quarta lezione di CLAUDE.md)
  await page.getByRole("link", { name: "Dispensa" }).click();
  const cursore = page.getByRole("slider").first();
  await expect(cursore).toBeVisible();

  const box = await cursore.boundingBox();
  expect(box!.height).toBeGreaterThanOrEqual(40);

  // le tre zone stanno su un elemento dietro al cursore: se il gradiente non
  // arrivasse, resterebbe un binario invisibile e il cursore non direbbe più nulla
  const zone = page.locator("input[type='range']").first().locator("xpath=preceding-sibling::div[1]");
  await expect(zone).toHaveCSS("background-image", /linear-gradient/);
});
```

```bash
E2E="docker compose -p spena-e2e -f docker-compose.yml -f docker-compose.e2e.yml"
$E2E up -d --build --wait
$E2E exec -T backend python -m app.cli.seed
(cd frontend && E2E_BASE_URL=http://localhost:5174 npm run e2e)
$E2E down -v
```

Expected: PASS. Se la dispensa del seme è vuota il test non trova nessun cursore: aggiungi una voce dall'interfaccia prima dell'asserzione, oppure salta a `/dispensa` dopo aver sistemato la spesa come fa `frontend/e2e/cooking.spec.ts`.

- [ ] **Step 12: Commit**

```bash
git add -A frontend backend/tests/test_frontend_fill_zones.py
git commit -m "$(cat <<'MSG'
feat: la dispensa si regola con un cursore a tre zone

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Task 10: Una voce torna in lista, in un posto solo (S2, backend)

Il cursore a zero chiederà «Lo rimetto in lista?». Il codice che ci vuole esiste già dentro `cook()`: va portato dove possono usarlo entrambi, senza cambiare cosa fa.

**Files:**
- Create: `backend/app/services/restock.py`, `backend/tests/services/test_restock.py`
- Modify: `backend/app/services/cooking.py:35-40,67-81`, `backend/app/api/pantry.py`, `backend/app/schemas/pantry.py`
- Test: `backend/tests/api/test_pantry.py`

**Interfaces:**
- Consumes: `add_item` non serve — `restock` costruisce `ShoppingListItem` come già fa `cook()`.
- Produces:
  - `already_in_list(session: AsyncSession, ingredient_id: uuid.UUID) -> bool`;
  - `restock(session: AsyncSession, item: PantryItem, reason: ShoppingReason = ShoppingReason.MANUAL) -> bool` — `True` se ha scritto una riga nuova, `False` se c'era già;
  - `RestockOut(added: bool)` in `app/schemas/pantry.py`;
  - `POST /api/v1/pantry/{item_id}/restock` → `RestockOut`.

- [ ] **Step 1: Scrivi i test che falliscono**

Crea `backend/tests/services/test_restock.py`:

```python
"""Il rientro in lista, condiviso fra la cottura e il cursore a zero."""

from app.db.models.ingredient import Ingredient, IngredientCategory
from app.db.models.pantry import PantryItem
from app.db.models.product import Product
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus
from app.domain.rules import PantryStatus
from app.services.restock import restock
from sqlalchemy import select


async def _voce(db_session, *, con_marca: bool = False) -> PantryItem:
    ingrediente = Ingredient(
        name="pomodoro", display_name="Pomodoro", category=IngredientCategory.VERDURA
    )
    db_session.add(ingrediente)
    await db_session.flush()
    prodotto = None
    if con_marca:
        prodotto = Product(ingredient_id=ingrediente.id, name="Pelati Mutti", source="custom")
        db_session.add(prodotto)
        await db_session.flush()
    item = PantryItem(
        ingredient_id=ingrediente.id,
        product_id=prodotto.id if prodotto else None,
        status=PantryStatus.FINISHED,
    )
    db_session.add(item)
    await db_session.flush()
    return item


async def test_una_voce_finita_torna_in_lista(db_session):
    item = await _voce(db_session)

    assert await restock(db_session, item) is True

    righe = (await db_session.execute(select(ShoppingListItem))).scalars().all()
    assert [(r.raw_text, r.status, r.reason) for r in righe] == [
        ("pomodoro", ShoppingStatus.PENDING, ShoppingReason.MANUAL)
    ]


async def test_in_lista_ci_va_la_marca_che_avevi_comprato(db_session):
    """In negozio «Pelati Mutti» dice più di «pomodoro»."""
    item = await _voce(db_session, con_marca=True)

    await restock(db_session, item)

    riga = (await db_session.execute(select(ShoppingListItem))).scalars().one()
    assert riga.raw_text == "Pelati Mutti"


async def test_quel_che_è_già_in_lista_non_si_duplica(db_session):
    """Due righe identiche in lista sono due giri nello stesso reparto."""
    item = await _voce(db_session)
    await restock(db_session, item)

    assert await restock(db_session, item) is False

    righe = (await db_session.execute(select(ShoppingListItem))).scalars().all()
    assert len(righe) == 1


async def test_una_riga_archiviata_non_conta_come_già_in_lista(db_session):
    """«C'è già» vale per pending e checked: archiviata vuol dire cancellata."""
    item = await _voce(db_session)
    db_session.add(
        ShoppingListItem(
            raw_text="pomodoro", ingredient_id=item.ingredient_id,
            status=ShoppingStatus.ARCHIVED, reason=ShoppingReason.MANUAL,
        )
    )
    await db_session.flush()

    assert await restock(db_session, item) is True


async def test_il_motivo_si_può_dichiarare(db_session):
    """La cottura dice perché la voce rientra; il cursore no, ed è una richiesta a mano."""
    item = await _voce(db_session)

    await restock(db_session, item, reason=ShoppingReason.FINISHED_WHILE_COOKING)

    riga = (await db_session.execute(select(ShoppingListItem))).scalars().one()
    assert riga.reason == ShoppingReason.FINISHED_WHILE_COOKING
```

E in coda a `backend/tests/api/test_pantry.py`:

```python
async def test_la_rotta_di_rientro_scrive_in_lista_e_lo_dice(
    logged_client, db_session, dispensa
):
    item = PantryItem(ingredient_id=dispensa["pomodoro"].id, status=PantryStatus.FINISHED)
    db_session.add(item)
    await db_session.flush()

    risposta = await logged_client.post(f"/api/v1/pantry/{item.id}/restock")
    assert risposta.status_code == 200
    assert risposta.json() == {"added": True}

    lista = (await logged_client.get("/api/v1/shopping-list")).json()
    assert [voce["raw_text"] for voce in lista] == ["pomodoro"]

    # una seconda volta non duplica, e lo dice invece di fingere di aver scritto
    ancora = await logged_client.post(f"/api/v1/pantry/{item.id}/restock")
    assert ancora.json() == {"added": False}


async def test_il_rientro_di_una_voce_inesistente_e_404(logged_client):
    import uuid

    risposta = await logged_client.post(f"/api/v1/pantry/{uuid.uuid4()}/restock")
    assert risposta.status_code == 404
```

- [ ] **Step 2: Falli fallire**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_restock.py tests/api/test_pantry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.services.restock'`.

- [ ] **Step 3: Scrivi il servizio**

Crea `backend/app/services/restock.py`:

```python
"""Una voce di dispensa che torna in lista della spesa.

Un solo posto per due chiamanti: la cottura, che rimette in lista quel che ha
finito, e il cursore portato a zero, che lo chiede. Stava tutto dentro `cook()`;
una seconda copia si sarebbe scollata sul punto che conta — il non duplicare.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.pantry import PantryItem
from app.db.models.shopping import ShoppingListItem, ShoppingReason, ShoppingStatus


async def already_in_list(session: AsyncSession, ingredient_id: uuid.UUID) -> bool:
    """Se quell'ingrediente è già da comprare. Archiviato non conta: è cancellato."""
    statement = select(ShoppingListItem.id).where(
        ShoppingListItem.ingredient_id == ingredient_id,
        ShoppingListItem.status.in_([ShoppingStatus.PENDING, ShoppingStatus.CHECKED]),
    )
    return (await session.execute(statement)).first() is not None


async def restock(
    session: AsyncSession,
    item: PantryItem,
    reason: ShoppingReason = ShoppingReason.MANUAL,
) -> bool:
    """Scrive la voce in lista, se non c'è già. Torna se ha scritto davvero.

    Il falso non è un errore ed è un'informazione: chi chiede può dire «era già in
    lista» invece di far credere di aver aggiunto qualcosa.
    """
    if await already_in_list(session, item.ingredient_id):
        return False

    await session.refresh(item, ["ingredient", "product"])
    # la marca che avevi comprato è l'informazione più utile in negozio
    label = item.product.name if item.product else item.ingredient.name
    session.add(
        ShoppingListItem(
            raw_text=label,
            ingredient_id=item.ingredient_id,
            status=ShoppingStatus.PENDING,
            reason=reason,
        )
    )
    await session.flush()
    return True
```

- [ ] **Step 4: La cottura usa il servizio invece della sua copia**

In `backend/app/services/cooking.py` togli `_already_in_list` e l'import di `select`, aggiungi `from app.services.restock import restock`, e sostituisci il blocco delle transizioni:

```python
        previous = item.status
        item.status = transition.to_status
        # la posizione del cursore non sopravvive a uno stato deciso qui: restare a
        # 80 mentre lo stato dice «finito» mostrerebbe un barattolo pieno per
        # qualcosa che non c'è più (stesso motivo di `set_status`)
        item.fill_percent = None
        item.status_changed_at = now

        if transition.restock and await restock(
            session,
            item,
            reason=_RESTOCK_REASON.get(transition.to_status, ShoppingReason.MANUAL),
        ):
            restocked += 1
```

`ShoppingListItem` e `ShoppingStatus` restano importati solo se altro nel file li usa: se l'analisi segnala import inutilizzati, toglili.

- [ ] **Step 5: La rotta**

In `backend/app/schemas/pantry.py`, in coda:

```python
class RestockOut(BaseModel):
    """`added` falso non è un errore: la voce era già da comprare."""

    added: bool
```

In `backend/app/api/pantry.py` aggiungi gli import (`RestockOut` dallo schema, `restock` da `app.services.restock`) e la rotta in coda:

```python
@router.post("/{item_id}/restock", response_model=RestockOut)
async def restock_item(
    item_id: uuid.UUID, session: AsyncSession = Depends(get_session)
) -> RestockOut:
    """Rimette in lista quel che è finito, se non c'è già.

    Una rotta sua e non un campo della PATCH: spostare un cursore e comprare una
    cosa sono due gesti, e l'utente ne compie il secondo rispondendo a una domanda.
    Nessuna sezione ne modifica un'altra in silenzio.
    """
    item = await session.get(PantryItem, item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "voce inesistente")
    added = await restock(session, item)
    await session.commit()
    return RestockOut(added=added)
```

- [ ] **Step 6: Falli passare**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_restock.py tests/api/test_pantry.py -v`
Expected: PASS.

- [ ] **Step 7: La cottura si comporta come prima**

Run: `cd backend && .venv/bin/python -m pytest`
Expected: PASS, compresi `tests/api/test_cooking.py` e `tests/services/` — il comportamento della cottura non cambia di una riga, cambia solo dove sta scritto.

- [ ] **Step 8: Commit**

```bash
git add backend/app backend/tests
git commit -m "$(cat <<'MSG'
feat: il rientro in lista è un servizio solo, e una rotta della dispensa

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Task 11: «Lo rimetto in lista?» (S2, frontend)

**Files:**
- Modify: `frontend/src/domain/types.ts`, `frontend/src/features/pantry/api.ts`, `frontend/src/features/pantry/PantryRow.tsx`, `frontend/src/features/pantry/PantryScreen.tsx`, `frontend/src/features/pantry/PantryScreen.test.tsx`

**Interfaces:**
- Consumes: `POST /pantry/{id}/restock` → `{ added: boolean }` (Task 10); `PantryRow` (Task 9).
- Produces:
  - `RestockResult { added: boolean }` in `domain/types.ts`;
  - `restockPantryItem(id: string): Promise<RestockResult>` in `features/pantry/api.ts`;
  - `PantryRow` guadagna `onFill: (percent: number) => Promise<PantryItem>` (non più `void`) e `onRestock: () => Promise<RestockResult>`.

- [ ] **Step 1: Scrivi i test che falliscono**

In `frontend/src/features/pantry/PantryScreen.test.tsx`:

```tsx
  it("portato a zero il cursore chiede se rimettere la voce in lista", async () => {
    stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [{ ...ITEMS[2], status: "finished", fill_percent: 0 }, 200];
      return [ITEMS, 200];
    });
    renderScreen();

    const cursore = await screen.findByRole("slider", { name: "Quanto ne resta di mela" });
    fireEvent.change(cursore, { target: { value: "0" } });
    fireEvent.pointerUp(cursore);

    expect(await screen.findByText("Lo rimetto in lista?")).toBeDefined();
    expect(screen.getByRole("button", { name: "Sì" })).toBeDefined();
    expect(screen.getByRole("button", { name: "No" })).toBeDefined();
  });

  it("finire una voce non scrive in lista da sé: solo il sì lo fa", async () => {
    // è il punto della decisione: nessuna sezione ne modifica un'altra in silenzio
    const fetchMock = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [{ ...ITEMS[2], status: "finished", fill_percent: 0 }, 200];
      if (init?.method === "POST") return [{ added: true }, 200];
      return [ITEMS, 200];
    });
    renderScreen();

    const cursore = await screen.findByRole("slider", { name: "Quanto ne resta di mela" });
    fireEvent.change(cursore, { target: { value: "0" } });
    fireEvent.pointerUp(cursore);
    await screen.findByText("Lo rimetto in lista?");
    expect(fetchMock.mock.calls.some(([, init]) => (init as RequestInit)?.method === "POST")).toBe(false);

    await userEvent.click(screen.getByRole("button", { name: "Sì" }));

    const post = fetchMock.mock.calls.find(([, init]) => (init as RequestInit)?.method === "POST");
    expect(String(post![0])).toContain("/pantry/p3/restock");
    expect(await screen.findByText("Rimesso in lista.")).toBeDefined();
  });

  it("se era già in lista lo dice, invece di far credere di aver aggiunto qualcosa", async () => {
    stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [{ ...ITEMS[2], status: "finished", fill_percent: 0 }, 200];
      if (init?.method === "POST") return [{ added: false }, 200];
      return [ITEMS, 200];
    });
    renderScreen();

    const cursore = await screen.findByRole("slider", { name: "Quanto ne resta di mela" });
    fireEvent.change(cursore, { target: { value: "0" } });
    fireEvent.pointerUp(cursore);
    await userEvent.click(await screen.findByRole("button", { name: "Sì" }));

    expect(await screen.findByText("Era già in lista.")).toBeDefined();
  });

  it("il no chiude la domanda e non scrive niente", async () => {
    const fetchMock = stubRoutedFetch((path, init) => {
      if (init?.method === "PATCH") return [{ ...ITEMS[2], status: "finished", fill_percent: 0 }, 200];
      return [ITEMS, 200];
    });
    renderScreen();

    const cursore = await screen.findByRole("slider", { name: "Quanto ne resta di mela" });
    fireEvent.change(cursore, { target: { value: "0" } });
    fireEvent.pointerUp(cursore);
    await userEvent.click(await screen.findByRole("button", { name: "No" }));

    await waitFor(() => expect(screen.queryByText("Lo rimetto in lista?")).toBeNull());
    expect(fetchMock.mock.calls.some(([, init]) => (init as RequestInit)?.method === "POST")).toBe(false);
  });
```

- [ ] **Step 2: Falli fallire**

Run: `cd frontend && npx vitest run src/features/pantry/PantryScreen.test.tsx`
Expected: FAIL — `Unable to find an element with the text: Lo rimetto in lista?`.

- [ ] **Step 3: Il tipo e la chiamata**

In `frontend/src/domain/types.ts`:

```ts
// L'esito di un rientro in lista. `added` falso non è un errore: la voce era già da
// comprare, e dirlo è diverso dal far credere di aver aggiunto qualcosa.
export interface RestockResult {
  added: boolean;
}
```

In `frontend/src/features/pantry/api.ts`:

```ts
/** Rimette in lista una voce di dispensa, se non c'è già. La decisione è
 * dell'utente: questa chiamata parte solo da una risposta esplicita. */
export function restockPantryItem(id: string) {
  return apiFetch<RestockResult>(`/pantry/${id}/restock`, { method: "POST" });
}
```

con `RestockResult` aggiunto all'import di tipo in cima al file.

- [ ] **Step 4: La domanda nella riga**

In `frontend/src/features/pantry/PantryRow.tsx`: aggiungi `import { useState } from "react";`, aggiungi `RestockResult` all'import di tipo da `../../domain/types`, porta `onFill` e `onRestock` a restituire una promessa, e aggiungi lo stato locale della domanda.

Firma:

```tsx
  onFill: (percent: number) => Promise<PantryItem>;
  onRestock: () => Promise<RestockResult>;
```

Dentro il componente, prima del `return`:

```tsx
  // la domanda vive qui e non nello schermo: riguarda questa riga, e fuori di qui
  // sarebbe un avviso in cima a una dispensa lunga, cioè fuori schermo
  const [asking, setAsking] = useState(false);
  const [restocked, setRestocked] = useState<RestockResult | null>(null);

  async function fill(percent: number) {
    setRestocked(null);
    try {
      const updated = await onFill(percent);
      // «finito» lo dice il server, non una soglia ricopiata qui
      setAsking(updated.status === "finished");
    } catch {
      // il guasto lo mostra già lo schermo, accanto a questa riga
      setAsking(false);
    }
  }
```

e dopo `<StatusChip …/>`:

```tsx
      {asking && (
        <div className="flex items-center justify-between gap-2 rounded-card bg-page px-3 py-2">
          <span className="text-sm text-ink-soft">Lo rimetto in lista?</span>
          <span className="flex shrink-0 gap-1">
            <button
              type="button"
              onClick={async () => {
                setAsking(false);
                try {
                  setRestocked(await onRestock());
                } catch {
                  setRestocked(null);
                }
              }}
              className="min-h-11 rounded-full px-3 text-sm font-medium text-brand"
            >
              Sì
            </button>
            <button
              type="button"
              onClick={() => setAsking(false)}
              className="min-h-11 rounded-full px-3 text-sm font-medium text-ink-soft"
            >
              No
            </button>
          </span>
        </div>
      )}

      {restocked && (
        <p role="status" className="text-sm text-ink-soft">
          {restocked.added ? "Rimesso in lista." : "Era già in lista."}
        </p>
      )}
```

Nel `<FillSlider …>` la chiamata diventa `onCommit={fill}`.

- [ ] **Step 5: Lo schermo passa le promesse**

In `frontend/src/features/pantry/PantryScreen.tsx` aggiungi `restockPantryItem` all'import da `./api`, la mutazione:

```tsx
  // il rientro in lista tocca la lista, non la dispensa: si invalida quella chiave,
  // altrimenti tornando in Lista il numero della scheda d'ingresso resta vecchio
  const restock = useMutation({
    mutationFn: (id: string) => restockPantryItem(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["shopping-list"] }),
  });
```

e nella riga:

```tsx
                    onFill={(percent) => change.mutateAsync({ id: item.id, fill: percent })}
                    onRestock={() => restock.mutateAsync(item.id)}
```

`mutateAsync` e non `mutate`: la riga ha bisogno della voce aggiornata per sapere se chiedere. Il rifiuto resta gestito — `onError` della mutazione mette l'avviso, e il `try/catch` dentro la riga impedisce la promessa non catturata.

- [ ] **Step 6: Falli passare**

Run: `cd frontend && npx vitest run && npm run typecheck && npm run build`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "$(cat <<'MSG'
feat: il cursore a zero chiede se rimettere la voce in lista

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Task 12: La foto dentro la ricetta (R1)

La foto delle ricette importate si vede solo nell'elenco. `RecipeOut` la porta già (`image_url`, `backend/app/schemas/recipe.py:70`): manca solo mostrarla. Attenzione al difetto già corretto una volta (`6a2175b`): una foto che non carica non deve lasciare un buco.

**Files:**
- Create: `frontend/src/features/recipes/RecipeImage.tsx`, `frontend/src/features/recipes/RecipeImage.test.tsx`
- Modify: `frontend/src/features/recipes/RecipeCard.tsx:31-54`, `frontend/src/features/cooking/RecipeDetailScreen.tsx:83-86`, `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`

**Interfaces:**
- Consumes: `RecipeDetail.image_url`, già nel tipo (`domain/types.ts`, ereditato da `RecipeSummary`).
- Produces: `RecipeImage({ url, alt, className }: { url: string | null; alt: string; className?: string })` — rende `null` quando non c'è url o quando il caricamento fallisce.

- [ ] **Step 1: Scrivi i test che falliscono**

Crea `frontend/src/features/recipes/RecipeImage.test.tsx`:

```tsx
import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { RecipeImage } from "./RecipeImage";

describe("RecipeImage", () => {
  it("senza indirizzo non rende niente, non un riquadro vuoto", () => {
    const { container } = render(<RecipeImage url={null} alt="Carbonara" />);
    expect(container.firstChild).toBeNull();
  });

  it("mostra la foto con il titolo come testo alternativo", () => {
    render(<RecipeImage url="https://esempio.invalid/foto.jpg" alt="Carbonara" />);
    const foto = screen.getByRole("img", { name: "Carbonara" });
    expect(foto.getAttribute("src")).toBe("https://esempio.invalid/foto.jpg");
    // duecento schede su un telefono sono duecento immagini, e arrivano dal
    // server di origine
    expect(foto.getAttribute("loading")).toBe("lazy");
  });

  it("una foto che non carica sparisce invece di lasciare un buco", () => {
    // il difetto corretto in 6a2175b: l'immagine arriva dal server di origine e non
    // viene mai copiata (spec §6.3), quindi un 404 è il caso normale
    const { container } = render(<RecipeImage url="https://esempio.invalid/rotta.jpg" alt="Carbonara" />);
    fireEvent.error(screen.getByRole("img", { name: "Carbonara" }));
    expect(container.firstChild).toBeNull();
  });
});
```

E in `frontend/src/features/cooking/RecipeDetailScreen.test.tsx`:

```tsx
  it("la ricetta aperta mostra la sua foto", async () => {
    // fino a ieri si vedeva solo nell'elenco: aprire la ricetta la faceva sparire
    stubFetch({ image_url: "https://esempio.invalid/foto.jpg" });
    renderScreen();
    expect((await screen.findByRole("img", { name: "Carbonara" })).getAttribute("src"))
      .toBe("https://esempio.invalid/foto.jpg");
  });

  it("una foto che non carica non lascia un buco sopra il titolo", async () => {
    stubFetch({ image_url: "https://esempio.invalid/rotta.jpg" });
    renderScreen();
    fireEvent.error(await screen.findByRole("img", { name: "Carbonara" }));
    expect(screen.queryByRole("img", { name: "Carbonara" })).toBeNull();
    // il resto della scheda resta al suo posto
    expect(screen.getByRole("heading", { name: "Carbonara" })).toBeDefined();
  });
```

Adatta `stubFetch`/`renderScreen` e il titolo agli helper e ai dati che il file già usa: quel che conta è che la risposta di `/recipes/{id}` porti `image_url`.

- [ ] **Step 2: Falli fallire**

Run: `cd frontend && npx vitest run src/features/recipes/RecipeImage.test.tsx`
Expected: FAIL — `Failed to resolve import "./RecipeImage"`.

- [ ] **Step 3: Scrivi il componente**

Crea `frontend/src/features/recipes/RecipeImage.tsx`:

```tsx
import { useState } from "react";

/** La foto di una ricetta, con il buco già chiuso.
 *
 * L'immagine arriva dal server di origine e non viene mai copiata (spec §6.3): un
 * 404 dopo che la ricetta è stata rinominata altrove, un blocco sul Referer, o solo
 * il segnale debole del corridoio del supermercato sono il caso normale, non
 * l'eccezione. Quando il caricamento fallisce, chi la usa si comporta come se
 * `image_url` fosse stato null da sempre — lo stesso disegno già pensato e già
 * provato per quel caso, non un terzo stato da inventare.
 *
 * Sta in un componente suo perché i posti che la mostrano sono due, la scheda
 * dell'elenco e la ricetta aperta, e la seconda copia di questa logica si
 * scollerebbe proprio sul ramo che nessuno guarda: quello dell'immagine rotta.
 */
export function RecipeImage({
  url,
  alt,
  className = "",
}: {
  url: string | null;
  alt: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  if (url === null || failed) return null;

  return (
    <img
      src={url}
      alt={alt}
      // duecento schede su un telefono sono duecento immagini
      loading="lazy"
      onError={() => setFailed(true)}
      className={className}
    />
  );
}
```

- [ ] **Step 4: La scheda dell'elenco lo usa**

In `frontend/src/features/recipes/RecipeCard.tsx` togli `useState`, il commento sul difetto e le variabili `imageFailed`/`showImage` (sono passati dentro `RecipeImage`), aggiungi `import { RecipeImage } from "./RecipeImage";` e sostituisci il blocco `{showImage && (…)}` con:

```tsx
        <RecipeImage
          url={recipe.image_url}
          alt={recipe.title}
          className="mb-2.5 aspect-[3/2] w-full rounded-lg object-cover"
        />
```

- [ ] **Step 5: La ricetta aperta la mostra**

In `frontend/src/features/cooking/RecipeDetailScreen.tsx` aggiungi `import { RecipeImage } from "../recipes/RecipeImage";` e mettila sopra il titolo, sotto il `BackLink` del Task 2:

```tsx
      <RecipeImage
        url={recipe.image_url}
        alt={recipe.title}
        className="mb-3 aspect-[3/2] w-full rounded-card object-cover"
      />
      <h1 className="text-2xl font-semibold tracking-tight">{recipe.title}</h1>
```

`rounded-card` e non `rounded-lg`: nella scheda aperta la foto è una superficie, e l'app ha un solo raggio per le superfici.

- [ ] **Step 6: Falli passare**

Run: `cd frontend && npx vitest run && npm run typecheck && npm run build`
Expected: PASS — compresi i test che `RecipeCard` aveva già sull'immagine rotta, che ora provano `RecipeImage` attraverso la scheda vera.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "$(cat <<'MSG'
feat: la foto si vede anche dentro la ricetta, e se non carica non lascia un buco

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Task 13: Filtrare per ingrediente primario (R3, backend)

«Ho questo, cosa ci faccio». Vale **solo sugli ingredienti primari**: un secondario non caratterizza il piatto, e «cosa faccio con il sale» non è una domanda.

**Files:**
- Modify: `backend/app/services/recipe_search.py:254-317`, `backend/app/api/recipes.py:79-96`
- Test: `backend/tests/services/test_recipe_search.py`, `backend/tests/api/test_recipes.py`

**Interfaces:**
- Consumes: `RecipeIngredient`, già importato in `recipe_search.py`; `IngredientRole` idem.
- Produces:
  - `search_recipes(session, query=None, only_cookable=False, limit=30, category=None, ingredient_id: uuid.UUID | None = None)`;
  - `GET /api/v1/recipes/search?ingredient_id=<uuid>`.

- [ ] **Step 1: Scrivi i test che falliscono**

In coda a `backend/tests/services/test_recipe_search.py`:

```python
async def test_il_filtro_per_ingrediente_sceglie_in_sql(db_session):
    """Sesta lezione di CLAUDE.md: un filtro dietro a un limite guarda un campione.

    Con il catalogo intero, filtrare dopo aver preso le cento più recenti
    risponderebbe «con il pomodoro non ci fai niente» solo perché le ricette col
    pomodoro sono più vecchie di ieri.
    """
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import CANDIDATE_POOL, search_recipes

    pomodoro = Ingredient(
        name="pomodoro", display_name="Pomodoro", category=IngredientCategory.VERDURA
    )
    farina = Ingredient(
        name="farina", display_name="Farina", category=IngredientCategory.CEREALI
    )
    db_session.add_all([pomodoro, farina])
    await db_session.flush()

    voluta = await create_recipe(
        db_session, title="Pomodori al riso", description="Con il pomodoro",
        instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
        ingredients=[(pomodoro.id, "primary", "6", None)], embedding=None,
    )
    assert voluta is not None
    for numero in range(CANDIDATE_POOL + 5):
        await create_recipe(
            db_session, title=f"Pane {numero}", description="Senza pomodoro",
            instructions="Inforna.", servings=2, source="dataset", source_ref=None,
            ingredients=[(farina.id, "primary", "500 g", None)], embedding=None,
        )
    await db_session.flush()

    risultati = await search_recipes(db_session, ingredient_id=pomodoro.id)

    assert [r.recipe.title for r in risultati] == ["Pomodori al riso"]


async def test_un_ingrediente_secondario_non_fa_trovare_la_ricetta(db_session):
    """Un secondario non caratterizza il piatto: «cosa faccio col sale» non è una domanda."""
    from app.db.models.ingredient import Ingredient, IngredientCategory
    from app.repositories.recipes import create_recipe
    from app.services.recipe_search import search_recipes

    sale = Ingredient(name="sale", display_name="Sale", category=IngredientCategory.CONDIMENTI)
    pasta = Ingredient(name="pasta", display_name="Pasta", category=IngredientCategory.CEREALI)
    db_session.add_all([sale, pasta])
    await db_session.flush()

    await create_recipe(
        db_session, title="Pasta in bianco", description="Solo pasta",
        instructions="Cuoci.", servings=2, source="dataset", source_ref=None,
        ingredients=[(pasta.id, "primary", "320 g", None), (sale.id, "secondary", "q.b.", None)],
        embedding=None,
    )
    await db_session.flush()

    assert await search_recipes(db_session, ingredient_id=sale.id) == []
    assert [r.recipe.title for r in await search_recipes(db_session, ingredient_id=pasta.id)] == [
        "Pasta in bianco"
    ]
```

E in `backend/tests/api/test_recipes.py`, nello stile dei test già presenti nel file:

```python
async def test_la_ricerca_accetta_un_ingrediente(logged_client, db_session):
    """La rotta passa il filtro al servizio, e un id inventato non è un errore.

    Una PWA con la cache vecchia può mandare l'id di un ingrediente che non c'è più:
    la risposta giusta è «nessuna ricetta», non un muro.
    """
    import uuid

    risposta = await logged_client.get(
        "/api/v1/recipes/search", params={"ingredient_id": str(uuid.uuid4())}
    )
    assert risposta.status_code == 200
    assert risposta.json() == []
```

- [ ] **Step 2: Falli fallire**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_recipe_search.py tests/api/test_recipes.py -v`
Expected: FAIL — `TypeError: search_recipes() got an unexpected keyword argument 'ingredient_id'`.

- [ ] **Step 3: Il filtro, in SQL**

In `backend/app/services/recipe_search.py`, sopra `search_recipes`:

```python
def _with_primary_ingredient(statement, ingredient_id: uuid.UUID):
    """«Ho questo, cosa ci faccio»: solo dove l'ingrediente è principale.

    Un secondario non caratterizza il piatto — la regola primario/secondario di
    `domain/rules.py` vista dall'altro capo — e un filtro che li accettasse
    risponderebbe «tutto» a chi ha in casa il sale.

    Un EXISTS e non una join: la join moltiplicherebbe le righe per ogni
    ingrediente corrispondente, e il limite più avanti conterebbe righe invece di
    ricette.
    """
    return statement.where(
        select(RecipeIngredient.recipe_id)
        .where(
            RecipeIngredient.recipe_id == Recipe.id,
            RecipeIngredient.ingredient_id == ingredient_id,
            RecipeIngredient.role == IngredientRole.PRIMARY,
        )
        .exists()
    )
```

e dentro `search_recipes` porta la firma a:

```python
async def search_recipes(
    session: AsyncSession,
    query: str | None = None,
    only_cookable: bool = False,
    limit: int = 30,
    category: str | None = None,
    ingredient_id: uuid.UUID | None = None,
) -> list[RecipeSearchResult]:
```

Nel ramo senza parole cercate, accanto al filtro di categoria e **prima** del `.limit(CANDIDATE_POOL)`:

```python
        if ingredient_id is not None:
            statement = _with_primary_ingredient(statement, ingredient_id)
```

E accanto all'altro filtro su `recipe_statement`, così che valga anche sul percorso con le parole cercate:

```python
    if ingredient_id is not None:
        # vale anche quando i candidati arrivano dal riordino: far cadere fuori chi
        # non ha quell'ingrediente costa zero query
        recipe_statement = _with_primary_ingredient(recipe_statement, ingredient_id)
```

- [ ] **Step 4: Il parametro sulla rotta**

In `backend/app/api/recipes.py`, dentro `search`:

```python
async def search(
    q: str | None = None,
    only_cookable: bool = False,
    category: str | None = None,
    ingredient_id: uuid.UUID | None = None,
    limit: int = Query(default=30, le=100),
    session: AsyncSession = Depends(get_session),
) -> list[RecipeSummaryOut]:
    results = await search_recipes(
        session, q, only_cookable, limit, category=category, ingredient_id=ingredient_id
    )
```

- [ ] **Step 5: Falli passare**

Run: `cd backend && .venv/bin/python -m pytest tests/services/test_recipe_search.py tests/api/test_recipes.py -v`
Expected: PASS.

- [ ] **Step 6: Nessun'altra rottura**

Run: `cd backend && .venv/bin/python -m pytest`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app backend/tests
git commit -m "$(cat <<'MSG'
feat: il ricettario si filtra per ingrediente principale, scegliendo in SQL

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Task 14: «Ho questo, cosa ci faccio» (R3, frontend)

**Files:**
- Modify: `frontend/src/features/recipes/api.ts:4-10`, `frontend/src/features/recipes/RecipeBookScreen.tsx`, `frontend/src/features/recipes/RecipeBookScreen.test.tsx`

**Interfaces:**
- Consumes: `GET /recipes/search?ingredient_id=` (Task 13); `IngredientPicker` da `components/IngredientPicker.tsx`, che esiste già e passa da `useQuery` come deve.
- Produces: `searchRecipes({ query, onlyCookable, category, ingredientId })` — **oggetto, non più quattro posizionali**: con quattro argomenti di cui due stringhe, scambiarne due è un difetto che il compilatore non vede.

- [ ] **Step 1: Scrivi i test che falliscono**

In `frontend/src/features/recipes/RecipeBookScreen.test.tsx`:

```tsx
  it("scegliere un ingrediente filtra il ricettario su di lui", async () => {
    const fetchMock = stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO], 200];
      return [RECIPES, 200];
    });
    renderScreen();

    await userEvent.type(await screen.findByLabelText("Cosa hai in casa"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    await waitFor(() => {
      const ultima = fetchMock.mock.calls.map(([url]) => String(url)).filter((u) => u.includes("/recipes/search")).pop();
      expect(ultima).toContain(`ingredient_id=${POMODORO.id}`);
    });
    expect(screen.getByRole("button", { name: "Togli il filtro su Pomodoro" })).toBeDefined();
  });

  it("togliere il filtro riporta il ricettario intero", async () => {
    const fetchMock = stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO], 200];
      return [RECIPES, 200];
    });
    renderScreen();

    await userEvent.type(await screen.findByLabelText("Cosa hai in casa"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));
    await userEvent.click(await screen.findByRole("button", { name: "Togli il filtro su Pomodoro" }));

    await waitFor(() => {
      const ultima = fetchMock.mock.calls.map(([url]) => String(url)).filter((u) => u.includes("/recipes/search")).pop();
      expect(ultima).not.toContain("ingredient_id");
    });
  });

  it("nessun risultato con un ingrediente dice che è il filtro, non il ricettario", async () => {
    // stesso errore corretto in b6ed1d9 dall'altro lato dell'app: «nessuna ricetta»
    // è un verdetto sul ricettario, e quasi sempre riguarda il filtro
    stubRoutedFetch((path) => {
      if (path.includes("/ingredients")) return [[POMODORO], 200];
      if (path.includes("/recipes/search")) return [[], 200];
      return [[], 200];
    });
    renderScreen();

    await userEvent.type(await screen.findByLabelText("Cosa hai in casa"), "pomo");
    await userEvent.click(await screen.findByRole("option", { name: /Pomodoro/ }));

    expect(
      await screen.findByText(/Nessuna ricetta che abbia «Pomodoro» fra gli ingredienti principali/)
    ).toBeDefined();
  });
```

con, in cima al file, `const POMODORO = { id: "i9", name: "pomodoro", display_name: "Pomodoro", category: "verdura" };` e `stubRoutedFetch` nello stile di quella di `PantryScreen.test.tsx` se il file non ne ha già una.

- [ ] **Step 2: Falli fallire**

Run: `cd frontend && npx vitest run src/features/recipes/RecipeBookScreen.test.tsx`
Expected: FAIL — `Unable to find a label with the text of: Cosa hai in casa`.

- [ ] **Step 3: La chiamata prende un oggetto**

In `frontend/src/features/recipes/api.ts`:

```ts
/** I filtri del ricettario, per nome e non per posizione: con quattro argomenti di
 * cui due stringhe, scambiare «categoria» e «parole cercate» è un difetto che il
 * compilatore non può vedere. */
export function searchRecipes({
  query = "",
  onlyCookable = false,
  category = "",
  ingredientId = "",
}: {
  query?: string;
  onlyCookable?: boolean;
  category?: string;
  ingredientId?: string;
} = {}) {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  if (onlyCookable) params.set("only_cookable", "true");
  if (category) params.set("category", category);
  if (ingredientId) params.set("ingredient_id", ingredientId);
  return apiFetch<RecipeSummary[]>(`/recipes/search?${params.toString()}`);
}
```

- [ ] **Step 4: Il filtro nello schermo**

In `frontend/src/features/recipes/RecipeBookScreen.tsx` aggiungi `import { IngredientPicker } from "../../components/IngredientPicker";` e `import type { Ingredient } from "../../domain/types";`, poi:

```tsx
  // l'ingrediente scelto, non solo il suo id: il nome serve al riquadro del filtro e
  // al messaggio di elenco vuoto, e una seconda chiamata per riaverlo sarebbe un
  // giro in rete per qualcosa che l'utente ha appena toccato
  const [ingredient, setIngredient] = useState<Ingredient | null>(null);
```

la query diventa:

```tsx
  const { data: recipes = [], isLoading, isError } = useQuery({
    queryKey: ["recipes", debouncedQuery, onlyCookable, category, ingredient?.id ?? ""],
    queryFn: () =>
      searchRecipes({
        query: debouncedQuery,
        onlyCookable,
        category,
        ingredientId: ingredient?.id ?? "",
      }),
  });
```

e sotto il filtro di categoria:

```tsx
      {ingredient === null ? (
        <IngredientPicker
          label="Cosa hai in casa"
          failureNote="Puoi comunque cercare per parole qui sopra."
          onPick={setIngredient}
        />
      ) : (
        <div className="flex items-center justify-between gap-2 rounded-card bg-brand-tint px-3 py-2">
          <span className="min-w-0 truncate text-sm text-brand">
            Solo con {ingredient.display_name}
          </span>
          <button
            type="button"
            aria-label={`Togli il filtro su ${ingredient.display_name}`}
            onClick={() => setIngredient(null)}
            className="min-h-11 shrink-0 px-2 text-sm font-medium text-brand"
          >
            Togli
          </button>
        </div>
      )}
```

- [ ] **Step 5: L'elenco vuoto sa anche di questo filtro**

Sempre in `RecipeBookScreen.tsx`, porta `emptyMessage` a prendere un oggetto — quattro parametri di cui tre stringhe sono tre occasioni di scambiarli — e aggiungi il caso nuovo **per primo**, perché è il più stretto:

```tsx
function emptyMessage({
  query,
  onlyCookable,
  category,
  ingredientName,
}: {
  query: string;
  onlyCookable: boolean;
  category: string;
  ingredientName: string | null;
}): string {
  const searched = query.trim() !== "";
  if (ingredientName) {
    return (
      `Nessuna ricetta che abbia «${ingredientName}» fra gli ingredienti principali` +
      `${searched ? " con queste parole" : ""}${category ? ` in «${category}»` : ""}` +
      `${onlyCookable ? " fra quelle che puoi cucinare adesso" : ""}: ` +
      "togli il filtro, o provane un altro."
    );
  }
  if (category) {
```

il resto della funzione resta identico. La chiamata diventa:

```tsx
        <p className="pt-4 text-ink-soft">
          {emptyMessage({
            query: debouncedQuery,
            onlyCookable,
            category,
            ingredientName: ingredient?.display_name ?? null,
          })}
        </p>
```

- [ ] **Step 6: Falli passare**

Run: `cd frontend && npx vitest run && npm run typecheck && npm run build`
Expected: PASS. Se un test vecchio chiama `searchRecipes("pasta", false, "")`, aggiornalo alla forma a oggetto: è il punto della modifica.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "$(cat <<'MSG'
feat: «ho questo, cosa ci faccio» filtra il ricettario per ingrediente principale

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Task 15: Quel che resta scritto

Un piano che non aggiorna i documenti lascia la prossima sessione a scoprire da sola cos'è cambiato.

**Files:**
- Modify: `docs/prossimi-passi.md`, `README.md`

- [ ] **Step 1: Segna le cinque voci come fatte**

In `docs/prossimi-passi.md`:

- **S1** → `## S1. La X rossa **[FATTO 2026-09-17]**`, e al posto del TBD: l'annulla c'è, dura sei secondi, e si appoggia a `archived_at` che era già reversibile; la riga resta dov'era invece di sparire, perché una lapide senza posto non si può annullare.
- **S2** → `## S2. Lo slider a tre zone **[FATTO 2026-09-17]**`. Il TBD va **corretto, non solo chiuso**: diceva «come fa oggi il passaggio a `finished`», e oggi il passaggio a `finished` dalla dispensa **non** rimette niente in lista — l'unico punto che riempie la lista è `cook()`. Scrivi com'è finita: il cursore a zero segna finito e **chiede**, con `POST /pantry/{id}/restock` che non duplica quel che è già in lista. Aggiungi che `LOW_MAX_FILL` è 30, che vive in `app/domain/rules.py`, che `backend/tests/test_frontend_fill_zones.py` impedisce ai due linguaggi di divergere, e che `StatusToggle` non esiste più.
- **R1** → `## R1. La foto dentro la ricetta **[FATTO 2026-09-17]**`, con la nota che il ramo dell'immagine rotta ora sta in un componente solo (`RecipeImage`), usato dalle due schermate.
- **R3** → `## R3. Filtra per ingrediente **[FATTO 2026-09-17]**`, con la nota che il filtro sceglie in SQL prima del limite (sesta lezione di `CLAUDE.md`) e vale solo sui primari.
- **T1** → `## T1. Navigazione **[FATTO IN PARTE 2026-09-17]**`: intestazione, tasto indietro e schede d'ingresso ci sono; il logo è un segno disegnato in SVG dentro `AppHeader.tsx`. **Resta aperto l'hamburger**, rinviato di proposito alla prima sezione secondaria vera (Pasti, Spese, Profilo, Connettori) — un indice che ripete le tre schede della navbar non è un indice. Spostalo come voce aperta, non come voce fatta.
- **Parte VIII** → la riga «Poi, indipendenti e piccole: S1, S2, R1, R3, T1» diventa il resoconto di cosa è stato fatto e di cosa resta (l'hamburger di T1). Il blocco successivo — D4/S5, S4, D1 applicata — diventa il primo che aspetta.
- **Parte I, D1** → una riga di avviso: `pantry_items.fill_percent` esiste ed è una **posizione**, non una quantità; la decisione fondante numero 1 resta intera perché niente la usa in un calcolo. Quando D1 verrà implementata, chi tocca `CLAUDE.md` deve sapere che questa colonna c'è e perché non è un'eccezione.

- [ ] **Step 2: Aggiorna il README dove descrive l'interfaccia**

In `README.md`, dove il testo elenca le schermate o gli stati della dispensa: i tre pulsanti sono diventati un cursore a tre zone, e togliere una voce è una X con annulla. Se il README non descrive quel livello di dettaglio, non inventare una sezione: limita la modifica alla riga che oggi è diventata falsa.

- [ ] **Step 3: Rileggi e commit**

Run: `git diff docs/prossimi-passi.md README.md`
Expected: nessuna riga che promette qualcosa che il codice non fa.

```bash
git add docs/prossimi-passi.md README.md
git commit -m "$(cat <<'MSG'
docs: le cinque voci indipendenti sono fatte, e S2 racconta com'è finita davvero

Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>
MSG
)"
```

---

## Chiusura

Prima di considerare il piano finito, sull'albero completo:

```bash
docker compose up -d db
cd backend && .venv/bin/python -m pytest
cd ../frontend && npx vitest run && npm run typecheck && npm run build
```

Tutti e quattro verdi. Poi si decide se unire e distribuire: **non fa parte di questo piano**, e il deploy è sempre `docker compose -f docker-compose.prod.yml up -d --build --wait`.

### Quel che questo piano non fa, di proposito

- **L'hamburger di T1.** Rinviato alla prima sezione secondaria vera.
- **La quarta scheda «Pasti» di D3.** La sezione non esiste: `TabBar.tsx` resta a `grid-cols-3` finché non c'è qualcosa dietro la quarta icona.
- **S3** (parità dell'ingresso diretto in dispensa) — dipende dallo scontrino, che è fase 2 e non esiste.
- **Qualunque import di massa.** Il vincolo di ~100 ricette resta attivo.
