import { describe, expect, it, vi, beforeEach } from "vitest";
import { apiFetch, UnauthorizedError } from "./client";

describe("apiFetch", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("restituisce il corpo JSON per una risposta riuscita", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), { status: 200 })
    ));
    await expect(apiFetch<{ status: string }>("/health")).resolves.toEqual({ status: "ok" });
  });

  it("invia sempre i cookie di sessione", async () => {
    const spy = vi.fn().mockResolvedValue(new Response("{}", { status: 200 }));
    vi.stubGlobal("fetch", spy);
    await apiFetch("/pantry");
    expect(spy.mock.calls[0][1].credentials).toBe("include");
  });

  it("solleva UnauthorizedError su 401, così l'app sa tornare all'accesso", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("", { status: 401 })));
    await expect(apiFetch("/pantry")).rejects.toBeInstanceOf(UnauthorizedError);
  });

  it("solleva ApiError con lo stato per gli altri errori", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "voce inesistente" }), { status: 404 })
    ));
    await expect(apiFetch("/pantry/x")).rejects.toMatchObject({
      status: 404,
      message: "voce inesistente",
    });
  });

  it("degrada a un messaggio generico quando il corpo d'errore non è JSON", async () => {
    // una pagina d'errore di nginx, non un {detail}: il client non deve esplodere
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response("<html>502 Bad Gateway</html>", { status: 502 })
    ));
    await expect(apiFetch("/pantry")).rejects.toMatchObject({
      status: 502,
      message: "errore 502",
    });
  });

  // Il corpo è quello vero: catturato da FastAPI con lo schema RecipeCreate del
  // backend (titolo oltre i 200 caratteri e porzioni oltre 50), con i soli campi
  // `input` accorciati perché ripetono il dato inviato. Inventarlo avrebbe
  // rischiato di difendere una forma che FastAPI non produce.
  it("il detail di un 422 diventa una frase leggibile, non «[object Object]»", async () => {
    const body = {
      detail: [
        {
          type: "string_too_long",
          loc: ["body", "title"],
          msg: "String should have at most 200 characters",
          input: "xxx",
          ctx: { max_length: 200 },
        },
        {
          type: "less_than_equal",
          loc: ["body", "servings"],
          msg: "Input should be less than or equal to 50",
          input: 99,
          ctx: { le: 50 },
        },
      ],
    };
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify(body), { status: 422 })
    ));

    await expect(apiFetch("/recipes", { method: "POST" })).rejects.toMatchObject({
      status: 422,
      message:
        "String should have at most 200 characters; Input should be less than or equal to 50",
    });
  });

  it("un detail di forma ignota degrada al messaggio generico invece di stamparsi male", async () => {
    // un oggetto, non una stringa né una lista: `String(...)` ne farebbe
    // "[object Object]", che è la bugia che questa funzione esiste per evitare
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: { motivo: "chissà" } }), { status: 400 })
    ));
    await expect(apiFetch("/pantry")).rejects.toMatchObject({
      status: 400,
      message: "errore 400",
    });
  });

  it("gestisce una risposta 204 senza corpo", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(apiFetch("/auth/logout", { method: "POST" })).resolves.toBeNull();
  });
});
