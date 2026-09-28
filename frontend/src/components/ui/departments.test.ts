import { describe, expect, it } from "vitest";
import { FOOD_CATEGORIES, NON_FOOD_CATEGORIES } from "../../domain/categories";
import { departmentStyle, TINT_CLASSES } from "./departments";
import { IconPackage } from "./icons";

describe("departmentStyle", () => {
  // come test_frontend_categories.py per l'elenco: un reparto nuovo senza icona non
  // deve arrivare a video con il segnaposto senza che nessuno lo abbia deciso
  it.each([...FOOD_CATEGORIES, ...NON_FOOD_CATEGORIES])("«%s» ha la sua icona e una tinta", (category) => {
    const style = departmentStyle(category);
    expect(Object.keys(TINT_CLASSES)).toContain(style.tint);
    if (category !== "altro") expect(style.icon).not.toBe(IconPackage);
  });

  it("senza reparto, o con uno sconosciuto, usa la scatola in ardesia", () => {
    expect(departmentStyle(null)).toEqual({ icon: IconPackage, tint: "slate" });
    expect(departmentStyle("inventato")).toEqual({ icon: IconPackage, tint: "slate" });
  });

  it("i non alimentari stanno nell'ardesia, lontani dalle tinte del cibo", () => {
    for (const category of NON_FOOD_CATEGORIES) expect(departmentStyle(category).tint).toBe("slate");
  });
});
