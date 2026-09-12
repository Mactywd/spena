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

  it("gestisce una risposta 204 senza corpo", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(null, { status: 204 })));
    await expect(apiFetch("/auth/logout", { method: "POST" })).resolves.toBeNull();
  });
});
