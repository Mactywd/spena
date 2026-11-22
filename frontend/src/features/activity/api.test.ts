import { afterEach, describe, expect, it, vi } from "vitest";
import { createToken, fetchActivity, headersJson, webhookUrl } from "./api";

function stubFetch() {
  const spy = vi.fn((_url: unknown, _init?: RequestInit) =>
    Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
  );
  vi.stubGlobal("fetch", spy);
  return spy;
}

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("le chiamate di «Attività»", () => {
  it("fetchActivity legge il riepilogo", async () => {
    const spy = stubFetch();

    await fetchActivity();

    expect(String(spy.mock.calls[0][0])).toBe("/api/v1/activity");
  });

  it("createToken chiede una chiave nuova con un POST", async () => {
    const spy = stubFetch();

    await createToken();

    expect(String(spy.mock.calls[0][0])).toBe("/api/v1/activity/token");
    expect(spy.mock.calls[0][1]?.method).toBe("POST");
  });

  it("l'indirizzo del webhook è l'origine della pagina più il percorso", () => {
    expect(webhookUrl("https://spena.example")).toBe("https://spena.example/api/v1/activity/hc-webhook");
  });

  it("le intestazioni da incollare in HC Webhook sono un oggetto JSON", () => {
    expect(headersJson({ token: "abc", header: "X-Spena-Token" })).toBe('{"X-Spena-Token":"abc"}');
  });
});
