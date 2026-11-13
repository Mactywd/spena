import { describe, expect, it } from "vitest";
import { dayLabel, longDayLabel, weekLabel } from "./format";

describe("le date dei pasti", () => {
  it("dayLabel", () => expect(dayLabel("2025-11-10")).toBe("Lunedì 10"));
  it("longDayLabel", () => expect(longDayLabel("2025-11-11")).toBe("martedì 11 novembre"));
  it("weekLabel nello stesso mese", () =>
    expect(weekLabel("2025-11-10", "2025-11-16")).toBe("10–16 novembre"));
  it("weekLabel a cavallo di due mesi", () =>
    expect(weekLabel("2025-10-27", "2025-11-02")).toBe("27 ottobre – 2 novembre"));
  it("weekLabel a cavallo dell'anno", () =>
    expect(weekLabel("2025-12-29", "2026-01-04")).toBe("29 dicembre 2025 – 4 gennaio 2026"));
});
