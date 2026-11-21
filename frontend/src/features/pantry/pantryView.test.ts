import { describe, expect, it } from "vitest";
import type { PantryItem } from "../../domain/types";
import {
  attentionCounts,
  enteredNotice,
  expiringText,
  expiryCounts,
  expirySummary,
  finishedText,
  groupForDisplay,
  hasBothWorlds,
  hasExpiry,
  inWorld,
  isExpiring,
  itemLabel,
  matchesQuery,
  sectionOpen,
  settleWorld,
  visibleItems,
  worldSummary,
  type PantryWorld,
  type SectionView,
} from "./pantryView";

function item(over: Partial<PantryItem>): PantryItem {
  return {
    id: "x",
    ingredient_id: "i",
    product_id: null,
    ingredient_name: "mela",
    ingredient_category: "frutta",
    ingredient_kind: "food",
    product_name: null,
    product_brand: null,
    status: "available",
    fill_percent: null,
    note: null,
    added_at: "2026-09-11T10:00:00Z",
    expires_on: null,
    expiry: null,
    ingredient_emoji: null,
    ...over,
  };
}

// S14: una voce per mondo
const CIBO = item({ id: "c", ingredient_kind: "food" });
const CASA = item({
  id: "h",
  ingredient_name: "candeggina",
  ingredient_category: "casa",
  ingredient_kind: "non_food",
});

describe("itemLabel", () => {
  it("usa il prodotto se c'è, l'ingrediente altrimenti", () => {
    expect(itemLabel(item({ product_name: "Total 0%" }))).toBe("Total 0%");
    expect(itemLabel(item({}))).toBe("mela");
  });
});

describe("matchesQuery", () => {
  const yogurt = item({ ingredient_name: "yogurt greco", product_name: "Total 0%", product_brand: "Fage" });
  it.each([
    ["", true],
    ["   ", true],
    ["yog", true],
    ["GRECO", true],
    ["total", true],
    ["fage", true],
    ["latte", false],
  ])("«%s» → %s", (query, expected) => {
    expect(matchesQuery(yogurt, query)).toBe(expected);
  });

  it("non guarda gli accenti: «caffe» trova «caffè»", () => {
    expect(matchesQuery(item({ ingredient_name: "caffè" }), "caffe")).toBe(true);
    expect(matchesQuery(item({ ingredient_name: "caffe" }), "caffè")).toBe(true);
  });
});

describe("isExpiring", () => {
  it.each([
    [{ expiry: "soon" as const }, true],
    [{ expiry: "expired" as const }, true],
    [{ expiry: null }, false],
    // un barattolo finito non allarma: non c'è più niente da consumare in tempo
    [{ expiry: "soon" as const, status: "finished" as const }, false],
    [{ expiry: "expired" as const, status: "low" as const }, true],
  ])("%o → %s", (over, expected) => {
    expect(isExpiring(item(over))).toBe(expected);
  });
});

describe("hasExpiry", () => {
  // il filtro del riepilogo premuto: le finite restano, con il loro «In lista». Il
  // conteggio no (isExpiring), la vista sì — una voce segnata «Finito» dal filtro non
  // deve sparire sotto le dita insieme alla strada per rimetterla in lista
  it.each([
    [{ expiry: "soon" as const }, true],
    [{ expiry: "expired" as const }, true],
    [{ expiry: null }, false],
    [{ expiry: "soon" as const, status: "finished" as const }, true],
    [{ expiry: "expired" as const, status: "finished" as const }, true],
    [{ expiry: null, status: "finished" as const }, false],
  ])("%o → %s", (over, expected) => {
    expect(hasExpiry(item(over))).toBe(expected);
  });
});

describe("expiryCounts ed expirySummary", () => {
  it("conta le voci per verdetto, senza le finite", () => {
    const items = [
      item({ id: "a", expiry: "soon" }),
      item({ id: "b", expiry: "soon" }),
      item({ id: "c", expiry: "expired" }),
      item({ id: "d", expiry: "soon", status: "finished" }),
      item({ id: "e" }),
    ];
    expect(expiryCounts(items)).toEqual({ soon: 2, expired: 1 });
  });

  it.each([
    [{ soon: 0, expired: 0 }, null],
    [{ soon: 1, expired: 0 }, "1 in scadenza questa settimana"],
    [{ soon: 3, expired: 0 }, "3 in scadenza questa settimana"],
    [{ soon: 0, expired: 2 }, "2 oltre la scadenza"],
    [{ soon: 2, expired: 1 }, "2 in scadenza questa settimana · 1 oltre la scadenza"],
  ])("%o → %s", (counts, expected) => {
    expect(expirySummary(counts)).toBe(expected);
  });
});

describe("groupForDisplay", () => {
  it("reparti in ordine alfabetico, e dentro l'ordine del server", () => {
    const groups = groupForDisplay([
      item({ id: "1", ingredient_category: "verdura" }),
      item({ id: "2", ingredient_category: "frutta" }),
      item({ id: "3", ingredient_category: "verdura" }),
    ]);
    expect(groups.map(([category, rows]) => [category, rows.map((r) => r.id)])).toEqual([
      ["frutta", ["2"]],
      ["verdura", ["1", "3"]],
    ]);
  });

  it("le finite vanno in fondo alla loro sezione, ciascun gruppo nel suo ordine", () => {
    const [[, rows]] = groupForDisplay([
      item({ id: "a", status: "finished" }),
      item({ id: "b" }),
      item({ id: "c", status: "finished" }),
      item({ id: "d", status: "low" }),
    ]);
    expect(rows.map((r) => r.id)).toEqual(["b", "d", "a", "c"]);
  });
});

describe("inWorld", () => {
  const casi: [PantryWorld, "food" | "non_food", boolean][] = [
    ["all", "food", true],
    ["all", "non_food", true],
    ["food", "food", true],
    ["food", "non_food", false],
    ["non_food", "food", false],
    ["non_food", "non_food", true],
  ];
  it.each(casi)("mondo %s, voce %s: %s", (world, kind, atteso) => {
    expect(inWorld(item({ ingredient_kind: kind }), world)).toBe(atteso);
  });

  it("guarda il verdetto del server, non il reparto", () => {
    // una riga scollata: il reparto dice casa, il server dice cibo. Vince il server,
    // perché il client non ha una sua copia di `kind_for_category`
    const scollata = item({ ingredient_category: "casa", ingredient_kind: "food" });
    expect(inWorld(scollata, "food")).toBe(true);
    expect(inWorld(scollata, "non_food")).toBe(false);
  });
});

describe("hasBothWorlds", () => {
  const casi: [string, PantryItem[], boolean][] = [
    ["vuota", [], false],
    ["solo cibo", [CIBO, item({ id: "c2" })], false],
    ["solo casa", [CASA], false],
    ["cibo e casa", [CIBO, CASA], true],
    // una cosa di casa finita è a video, col suo «In lista»: il selettore deve poterla mostrare
    ["cibo e una cosa di casa finita", [CIBO, { ...CASA, status: "finished" }], true],
  ];
  it.each(casi)("%s", (_caso, items, atteso) => {
    expect(hasBothWorlds(items)).toBe(atteso);
  });
});

describe("visibleItems", () => {
  it("con «Tutto», senza testo e col riepilogo spento, tutte, nell'ordine in cui arrivano", () => {
    expect(visibleItems([CASA, CIBO], { world: "all", query: "", expiringOnly: false })).toEqual([
      CASA,
      CIBO,
    ]);
  });

  it("il mondo si combina con la ricerca", () => {
    // «a» sta in «mela» e in «candeggina»: il mondo tiene solo la sua
    expect(visibleItems([CIBO, CASA], { world: "non_food", query: "a", expiringOnly: false })).toEqual([
      CASA,
    ]);
    expect(visibleItems([CIBO, CASA], { world: "non_food", query: "mela", expiringOnly: false })).toEqual(
      []
    );
  });

  it("il mondo si combina col riepilogo premuto", () => {
    const ciboInScadenza = { ...CIBO, expires_on: "2026-09-28", expiry: "soon" as const };
    const casaInScadenza = { ...CASA, expires_on: "2026-09-28", expiry: "soon" as const };
    const ciboSenza = item({ id: "c2" });
    expect(
      visibleItems([ciboInScadenza, casaInScadenza, ciboSenza], {
        world: "food",
        query: "",
        expiringOnly: true,
      })
    ).toEqual([ciboInScadenza]);
  });
});

describe("settleWorld", () => {
  const casi: [string, PantryWorld, PantryItem[], string | null, PantryWorld][] = [
    ["«Tutto» resta «Tutto»", "all", [CIBO, CASA], null, "all"],
    ["un mondo scelto resta, coi due mondi in dispensa", "food", [CIBO, CASA], null, "food"],
    ["«Casa» senza più cose di casa torna a «Tutto»", "non_food", [CIBO], null, "all"],
    ["«Cibo» senza più cibo torna a «Tutto»", "food", [CASA], null, "all"],
    ["una dispensa vuota torna a «Tutto»", "non_food", [], null, "all"],
    ["la voce appena aggiunta dell'altro mondo porta a «Tutto»", "non_food", [CIBO, CASA], "c", "all"],
    ["la voce appena aggiunta dello stesso mondo lascia il mondo", "non_food", [CIBO, CASA], "h", "non_food"],
    ["una voce appena aggiunta che non è ancora arrivata non cambia niente", "non_food", [CIBO, CASA], "zz", "non_food"],
  ];
  it.each(casi)("%s", (_caso, world, items, revealId, atteso) => {
    expect(settleWorld(world, items, revealId)).toBe(atteso);
  });
});

// --- S15: i reparti che si aprono e si chiudono ---

describe("sectionOpen", () => {
  const NIENTE: ReadonlySet<string> = new Set();
  const FRUTTA: ReadonlySet<string> = new Set(["frutta"]);
  const LATTICINI: ReadonlySet<string> = new Set(["latticini"]);
  // Le righe della tabella di §3 della spec S15 che passano da qui. La voce aggiunta e
  // il mondo di S14 stanno fuori: la prima apre il suo reparto nei salvati (`setOpen`,
  // nel momento in cui la si porta in vista), il secondo decide quali reparti ci sono,
  // non come stanno.
  const casi: [string, SectionView, boolean][] = [
    [
      "nessun filtro, mai chiuso: aperto",
      { collapsed: NIENTE, filtering: false, closedWhileFiltering: NIENTE },
      true,
    ],
    [
      "nessun filtro, chiuso e salvato: chiuso",
      { collapsed: FRUTTA, filtering: false, closedWhileFiltering: NIENTE },
      false,
    ],
    [
      "ricerca o riepilogo, chiuso e salvato: aperto, perché a video c'è solo se ha un risultato",
      { collapsed: FRUTTA, filtering: true, closedWhileFiltering: NIENTE },
      true,
    ],
    [
      "ricerca o riepilogo, aperto: aperto",
      { collapsed: NIENTE, filtering: true, closedWhileFiltering: NIENTE },
      true,
    ],
    [
      "ricerca o riepilogo, chiuso a mano durante il filtro: chiuso",
      { collapsed: FRUTTA, filtering: true, closedWhileFiltering: FRUTTA },
      false,
    ],
    [
      "filtro spento: vale il salvato, non quel che si era chiuso durante il filtro",
      { collapsed: NIENTE, filtering: false, closedWhileFiltering: FRUTTA },
      true,
    ],
    [
      "riepilogo spento dallo schermo: tenuto aperto, anche chiuso e salvato",
      { collapsed: FRUTTA, filtering: false, closedWhileFiltering: NIENTE, held: FRUTTA },
      true,
    ],
    [
      "tenuto aperto un altro reparto: questo, chiuso e salvato, resta chiuso",
      { collapsed: FRUTTA, filtering: false, closedWhileFiltering: NIENTE, held: LATTICINI },
      false,
    ],
    [
      "tenuto aperto, ma con un filtro acceso vale il filtro: chiuso a mano durante, chiuso",
      { collapsed: FRUTTA, filtering: true, closedWhileFiltering: FRUTTA, held: FRUTTA },
      false,
    ],
  ];
  it.each(casi)("%s", (_caso, view, atteso) => {
    expect(sectionOpen("frutta", view)).toBe(atteso);
  });
});

describe("attentionCounts", () => {
  const casi: [string, PantryItem[], { finished: number; expiring: number }][] = [
    ["niente da dire", [item({}), item({ status: "low" })], { finished: 0, expiring: 0 }],
    ["una finita", [item({ status: "finished" }), item({})], { finished: 1, expiring: 0 }],
    [
      "in scadenza e oltre la scadenza contano tutte e due",
      [
        item({ expires_on: "2026-10-10", expiry: "soon" }),
        item({ expires_on: "2026-10-01", expiry: "expired" }),
      ],
      { finished: 0, expiring: 2 },
    ],
    [
      "una finita con la scadenza conta una volta, come finita (come nel riepilogo)",
      [item({ status: "finished", expires_on: "2026-10-10", expiry: "soon" })],
      { finished: 1, expiring: 0 },
    ],
  ];
  it.each(casi)("%s", (_caso, rows, atteso) => {
    expect(attentionCounts(rows)).toEqual(atteso);
  });
});

describe("finishedText e expiringText", () => {
  // l'accordo al plurale: «2 finito» era uno degli «accordi sbagliati» del giro di T3
  const casi: [number, string, string][] = [
    [1, "1 finito", "1 in scadenza"],
    [2, "2 finiti", "2 in scadenza"],
    [11, "11 finiti", "11 in scadenza"],
  ];
  it.each(casi)("%i", (n, finito, scadenza) => {
    expect(finishedText(n)).toBe(finito);
    expect(expiringText(n)).toBe(scadenza);
  });
});

describe("worldSummary", () => {
  it("conta solo il mondo scelto", () => {
    const yogurt = item({ id: "y", expires_on: "2026-10-10", expiry: "soon" });
    const spugne = item({ ...CASA, id: "s", expires_on: "2026-10-01", expiry: "expired" });
    expect(worldSummary([yogurt, spugne], "food")).toBe("1 in scadenza questa settimana");
    expect(worldSummary([yogurt, spugne], "all")).toBe("1 in scadenza questa settimana · 1 oltre la scadenza");
  });
  it("in un mondo senza scadenze non c'è", () => {
    const yogurt = item({ id: "y", expires_on: "2026-10-10", expiry: "soon" });
    expect(worldSummary([yogurt, CASA], "non_food")).toBeNull();
  });
});

describe("enteredNotice", () => {
  const casi: [string, PantryItem["ingredient_kind"], PantryWorld, boolean, string][] = [
    ["in serie su «Tutto»: l'avviso di sempre", "food", "all", true, "In dispensa: Fage Total 0%"],
    ["in serie, lo stesso mondo: l'avviso di sempre", "food", "food", true, "In dispensa: Fage Total 0%"],
    ["in serie su «Casa», un cibo: dove è finito", "food", "non_food", true, "In dispensa: Fage Total 0%, sotto «Cibo»"],
    ["in serie su «Cibo», una cosa di casa: dove è finita", "non_food", "food", true, "In dispensa: Fage Total 0%, sotto «Casa»"],
    ["dal +, l'altro mondo: l'avviso di sempre (il selettore va a «Tutto»)", "food", "non_food", false, "In dispensa: Fage Total 0%"],
  ];
  it.each(casi)("%s", (_caso, kind, world, series, atteso) => {
    expect(enteredNotice("Fage Total 0%", kind, world, series)).toBe(atteso);
  });
});
