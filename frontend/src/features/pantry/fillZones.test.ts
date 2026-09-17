import { describe, expect, it } from "vitest";
import { fillForStatus, LOW_MAX_FILL } from "./fillZones";
import type { PantryStatus } from "../../domain/types";

// Prima di questo file solo il ramo `low` era provato: cambiare `return 0` in
// `return 10`, o `return 100` in `return 90`, non faceva fallire nessun test.
describe("fillForStatus", () => {
  it.each<[PantryStatus, number]>([
    ["finished", 0],
    ["low", Math.round(LOW_MAX_FILL / 2)],
    ["available", 100],
  ])("parte da %i per lo stato %s", (status, expected) => {
    expect(fillForStatus(status)).toBe(expected);
  });
});
