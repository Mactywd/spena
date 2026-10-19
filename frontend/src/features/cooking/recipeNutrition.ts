import { apiFetch } from "../../api/client";

/** I nutrienti di una ricetta come li manda il server (S4, fetta 2): la porzione, i valori
 * già arrotondati, su quante righe c'è ogni valore, e le righe fuori dal conto col loro
 * perché. Il conto lo fa il backend; qui restano le frasi. */
export type RecipeNutrient = {
  key: string;
  label: string;
  unit: string;
  main: boolean;
  value: number | null;
  lines: number;
};

export type MissingLine = {
  ingredient_id: string;
  ingredient_name: string;
  quantity_text: string | null;
  reason: "no_quantity" | "no_nutrients" | "no_weight";
  unit_label: string | null;
};

export type RecipeNutrition = {
  basis: "serving" | "recipe";
  servings: number | null;
  lines_total: number;
  lines_counted: number;
  nutrients: RecipeNutrient[];
  missing: MissingLine[];
  source: string;
};

export const recipeNutritionKey = (id: string) => ["recipe-nutrition", id] as const;

export function fetchRecipeNutrition(id: string) {
  return apiFetch<RecipeNutrition>(`/recipes/${id}/nutrition`);
}

export function missingText(line: MissingLine): string {
  if (line.reason === "no_quantity") return "senza una dose da pesare";
  if (line.reason === "no_nutrients") return "senza un alimento CIQUAL";
  return `manca il peso di «${line.unit_label ?? "pezzo"}»`;
}

export function captionText(data: RecipeNutrition): string {
  if (data.basis === "recipe" || data.servings === null) return "Per tutta la ricetta: porzioni non indicate";
  return `A porzione, su ${data.servings} ${data.servings === 1 ? "porzione" : "porzioni"}`;
}

export function countedText(counted: number, total: number): string {
  return counted === 1 ? `Contata 1 riga su ${total}.` : `Contate ${counted} righe su ${total}.`;
}

/** «su 2 righe di 3»: il valore viene solo da una parte delle righe contate. */
export function partialNote(nutrient: RecipeNutrient, counted: number): string | undefined {
  return nutrient.value !== null && nutrient.lines < counted ? `su ${nutrient.lines} righe di ${counted}` : undefined;
}
