import { apiFetch } from "../../api/client";
import type { NutrientValue } from "../../lib/nutrients";

/** Un alimento della tabella CIQUAL: il codice dell'Anses, il nome francese, il gruppo. */
export type CiqualFood = { code: string; name_fr: string; group_fr: string | null };

/** Il peso di una coppia ingrediente × unità canonica (S4, fetta 2). `unit` è l'id
 * dell'unità o la parola «pezzo», ed è anche il pezzo d'indirizzo delle rotte. */
export type UnitWeight = {
  unit: string;
  unit_label: string;
  grams: number | null;
  state: "undecided" | "decided" | "none";
  decided_by: "ai" | "human" | null;
};

/** I valori nutrizionali di un ingrediente (S4, fetta 1): lo stato, chi ha scelto,
 * l'alimento, i nutrienti per 100 g e la fonte. I tipi stanno qui e non in
 * `domain/types.ts`: li usa questa cartella, e quel file lo cambiano altri piani. */
export type IngredientNutrition = {
  state: "undecided" | "none" | "food" | "non_food";
  decided_by: "ai" | "human" | null;
  food: CiqualFood | null;
  nutrients: NutrientValue[];
  weights: UnitWeight[];
  source: string;
  citation: string;
};

/** Sotto `registry`: ogni correzione dell'anagrafica rinfresca `["registry"]`
 * (`refreshAfterCorrection`), e con lei questa sezione. */
export const nutritionKey = (id: string) => ["registry", "nutrition", id] as const;

export function fetchNutrition(id: string) {
  return apiFetch<IngredientNutrition>(`/ingredients/${id}/nutrition`);
}

/** `null` è «nessun alimento adatto», una scelta. */
export function chooseFood(id: string, code: string | null) {
  return apiFetch<IngredientNutrition>(`/ingredients/${id}/nutrition`, {
    method: "PUT",
    body: JSON.stringify({ ciqual_code: code }),
  });
}

/** L'annullamento: l'ingrediente torna da decidere, e l'AI lo riprenderà. */
export function forgetFood(id: string) {
  return apiFetch<IngredientNutrition>(`/ingredients/${id}/nutrition`, { method: "DELETE" });
}

export function searchCiqual(query: string) {
  return apiFetch<CiqualFood[]>(`/ciqual/foods?q=${encodeURIComponent(query)}`);
}

export function decidedText(decidedBy: "ai" | "human" | null): string {
  return decidedBy === "human" ? "scelto a mano" : "scelto dall'AI";
}

/** Il peso a mano; la risposta è l'intera scheda dei valori, pesi compresi. */
export function setWeight(id: string, unit: string, grams: number) {
  return apiFetch<IngredientNutrition>(`/ingredients/${id}/unit-grams/${encodeURIComponent(unit)}`, {
    method: "PUT",
    body: JSON.stringify({ grams }),
  });
}

/** L'annullamento: la coppia torna da decidere, e l'AI la riprenderà. */
export function forgetWeight(id: string, unit: string) {
  return apiFetch<IngredientNutrition>(`/ingredients/${id}/unit-grams/${encodeURIComponent(unit)}`, {
    method: "DELETE",
  });
}
