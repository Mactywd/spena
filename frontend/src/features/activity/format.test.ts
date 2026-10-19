import { describe, expect, it } from "vitest";
import {
  connectionText,
  dayLabel,
  exerciseLine,
  formatKg,
  formatSteps,
  ignoredText,
  momentText,
  syncText,
} from "./format";
import type { ActivitySync, Connection, ExerciseSession } from "./types";

const OGGI = "2026-10-13";

describe("dayLabel", () => {
  it.each([
    ["2026-10-13", "Oggi"],
    ["2026-10-12", "Ieri"],
    ["2026-10-11", "dom 11 ott"],
    ["2026-09-30", "mer 30 set"],
  ])("%s è «%s»", (giorno, atteso) => {
    expect(dayLabel(giorno, OGGI)).toBe(atteso);
  });
});

describe("momentText", () => {
  it.each([
    ["2026-10-13", "14:05", "oggi alle 14:05"],
    ["2026-10-12", "23:50", "ieri alle 23:50"],
    ["2026-10-07", "09:10", "7 ottobre alle 09:10"],
  ])("%s %s è «%s»", (giorno, ora, atteso) => {
    expect(momentText(giorno, ora, OGGI)).toBe(atteso);
  });
});

describe("formatSteps", () => {
  it.each([
    [0, "0"],
    [999, "999"],
    [8421, "8.421"],
    [12345, "12.345"],
    [1234567, "1.234.567"],
  ])("%s passi si scrivono «%s»", (passi, atteso) => {
    expect(formatSteps(passi)).toBe(atteso);
  });
});

describe("formatKg", () => {
  it.each([
    [72.4, "72,4 kg"],
    [80, "80,0 kg"],
  ])("%s → «%s»", (chili, atteso) => {
    expect(formatKg(chili)).toBe(atteso);
  });
});

describe("exerciseLine", () => {
  const corsa: ExerciseSession = {
    day: OGGI,
    time: "18:00",
    label: "Corsa",
    title: null,
    minutes: 32,
    distance_km: 5.1,
    source: "Samsung Health",
  };

  it.each([
    [corsa, "Corsa · 32 min · 5,1 km"],
    [{ ...corsa, title: "Giro del parco" }, "Corsa («Giro del parco») · 32 min · 5,1 km"],
    [{ ...corsa, label: "Allenamento di forza", distance_km: null, minutes: 45 }, "Allenamento di forza · 45 min"],
  ])("%# → «%s»", (allenamento, atteso) => {
    expect(exerciseLine(allenamento)).toBe(atteso);
  });
});

describe("syncText", () => {
  const sync: ActivitySync = {
    day: OGGI,
    time: "14:05",
    status: "ok",
    stale: false,
    steps_days: 1,
    exercises: 0,
    weights: 0,
    ignored: [],
    problems: [],
  };

  it.each([
    ["ok", "Ultima sincronizzazione: oggi alle 14:05."],
    ["test", "Ultima sincronizzazione: oggi alle 14:05, la prova di HC Webhook: arrivata, e non salva niente."],
    ["rejected", "Ultima sincronizzazione: oggi alle 14:05, rifiutata."],
  ] as const)("%s → «%s»", (status, atteso) => {
    expect(syncText({ ...sync, status }, OGGI)).toBe(atteso);
  });
});

describe("connectionText", () => {
  const chiave: Connection = {
    has_token: true,
    created_day: "2026-10-12",
    created_time: "21:00",
    last_used_day: OGGI,
    last_used_time: "14:05",
  };

  it("creata e usata", () => {
    expect(connectionText(chiave, OGGI)).toBe(
      "Chiave creata ieri alle 21:00. Usata l'ultima volta oggi alle 14:05."
    );
  });

  it("creata e mai usata", () => {
    expect(connectionText({ ...chiave, last_used_day: null, last_used_time: null }, OGGI)).toBe(
      "Chiave creata ieri alle 21:00. Non ancora usata."
    );
  });
});

describe("ignoredText", () => {
  it("elenca i tipi e dice dove toglierli", () => {
    expect(ignoredText(["frequenza cardiaca", "sonno"])).toBe(
      "Arrivati e non usati: frequenza cardiaca, sonno. Nel webhook di Spena, in HC Webhook, si possono togliere."
    );
  });
});
