import { afterEach, describe, expect, it, vi } from "vitest";
import { fetchSpending } from "./api";

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("fetchSpending", () => {
  it("chiede il periodo alla rotta delle spese", async () => {
    const spy = vi.fn((url: unknown) =>
      Promise.resolve(new Response(JSON.stringify({ chiesto: String(url) }), { status: 200 }))
    );
    vi.stubGlobal("fetch", spy);

    await fetchSpending("30d");

    expect(String(spy.mock.calls[0][0])).toBe("/api/v1/llm-spending?period=30d");
  });
});
