import { getConfig } from "@testing-library/react";
import { describe, expect, it } from "vitest";

// Le attese di Testing Library (`findBy…`, `waitFor`) rinunciavano dopo 1 s, e sotto il
// carico dell'e2e accanto le schermate con due o tre letture finte e un `useDebounced`
// cadevano ogni volta su un'asserzione diversa (T3 Consegne 5 e 6a). 4 s per tutte, in
// src/test/setup.ts: una prova che passa passa al primo disegno buono, una che fallisce
// fallisce lo stesso, solo più tardi (pulizie del 2026-10-13).
describe("le attese dei test", () => {
  it("un'attesa di Testing Library dura fino a 4 secondi", () => {
    expect(getConfig().asyncUtilTimeout).toBe(4000);
  });
});
