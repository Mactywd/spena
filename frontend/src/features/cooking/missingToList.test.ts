import { afterEach, describe, expect, it, vi } from "vitest";
import { missingNotice, sendMissing, type MissingOutcome } from "./missingToList";
import type { RecipeIngredientLine } from "../../domain/types";

function riga(id: string, nome: string): RecipeIngredientLine {
  return {
    ingredient_id: id, ingredient_name: nome, role: "primary", quantity_text: null,
    quantity_display: null, quantity_scaled: false, note: null,
    availability: "missing", satisfied: false,
  };
}

const BASILICO = riga("i1", "basilico");
const POMODORO = riga("i2", "pomodoro");
const AGLIO = riga("i3", "aglio");

/** `POST /shopping-list` finta: lo stato della risposta si sceglie per ingrediente.
 * 201 è «entrata», 200 è «c'era già» (S18), dal 400 in su un guasto. */
function stubLista(risposte: Record<string, number>) {
  const spy = vi.fn((_url: unknown, init?: RequestInit) => {
    const { ingredient_id } = JSON.parse(String(init!.body)) as { ingredient_id: string };
    const status = risposte[ingredient_id];
    const corpo = status >= 400 ? { detail: "no" } : { id: `s-${ingredient_id}`, added: status === 201 };
    return Promise.resolve(new Response(JSON.stringify(corpo), { status }));
  });
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("missingNotice", () => {
  // Le frasi dell'avviso (decise il 2026-09-29, più le tre forme che il piano aggiunge:
  // i plurali e il caso in cui non è andata nessuna). Nessun participio che concorda
  // col nome di un ingrediente.
  it.each<[string, MissingOutcome, string]>([
    ["tutte nuove", { added: 3, already: 0, failed: [] }, "3 in lista"],
    ["una sola", { added: 1, already: 0, failed: [] }, "1 in lista"],
    ["una c'era già", { added: 2, already: 1, failed: [] }, "2 in lista · 1 c'era già"],
    ["due c'erano già", { added: 1, already: 2, failed: [] }, "1 in lista · 2 c'erano già"],
    ["c'era già tutto", { added: 0, already: 3, failed: [] }, "Era già tutto in lista."],
    ["un guasto", { added: 2, already: 0, failed: [BASILICO] }, "2 in lista · 1 non è andata"],
    [
      "tutto insieme",
      { added: 1, already: 1, failed: [BASILICO, POMODORO] },
      "1 in lista · 1 c'era già · 2 non sono andate",
    ],
    ["niente di nuovo, un guasto", { added: 0, already: 1, failed: [BASILICO] }, "1 c'era già · 1 non è andata"],
    ["solo guasti", { added: 0, already: 0, failed: [BASILICO, POMODORO] }, "Non è andata: la lista è com'era."],
  ])("%s", (_caso, esito, atteso) => {
    expect(missingNotice(esito)).toBe(atteso);
  });
});

describe("sendMissing", () => {
  it("una POST per riga, col nome e l'ingrediente, e conta chi è entrato e chi c'era già", async () => {
    const spy = stubLista({ i1: 201, i2: 200 });

    expect(await sendMissing([BASILICO, POMODORO])).toEqual({ added: 1, already: 1, failed: [] });
    const mandate = spy.mock.calls.map(([url, init]) => [
      String(url),
      init!.method,
      JSON.parse(String(init!.body)),
    ]);
    expect(mandate).toEqual([
      ["/api/v1/shopping-list", "POST", { raw_text: "basilico", ingredient_id: "i1" }],
      ["/api/v1/shopping-list", "POST", { raw_text: "pomodoro", ingredient_id: "i2" }],
    ]);
  });

  it("partono tutte insieme: una risposta lenta non ferma le altre", async () => {
    let rilascia = () => {};
    const lenta = new Promise<void>((resolve) => {
      rilascia = resolve;
    });
    const spy = vi.fn(async (_url: unknown, init?: RequestInit) => {
      const { ingredient_id } = JSON.parse(String(init!.body)) as { ingredient_id: string };
      if (ingredient_id === "i1") await lenta;
      return new Response(JSON.stringify({ id: "s", added: true }), { status: 201 });
    });
    vi.stubGlobal("fetch", spy);

    const inCorso = sendMissing([BASILICO, POMODORO, AGLIO]);
    // la prima è ancora per aria, e le altre due sono già partite
    await vi.waitFor(() => expect(spy).toHaveBeenCalledTimes(3));
    rilascia();
    expect(await inCorso).toEqual({ added: 3, already: 0, failed: [] });
  });

  it("una riga che non arriva finisce fra le fallite, e le altre contano lo stesso", async () => {
    stubLista({ i1: 201, i2: 500, i3: 200 });
    expect(await sendMissing([BASILICO, POMODORO, AGLIO])).toEqual({
      added: 1,
      already: 1,
      failed: [POMODORO],
    });
  });
});
