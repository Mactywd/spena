import { apiFetch } from "../../api/client";
import type { Meal, MealBody, MealPatch, MealSlot, MealWeek } from "../../domain/types";

/** Chiavi di cache dei pasti. Chi scrive invalida `["meals"]`, cioè tutte. */
export const MEALS_KEY = ["meals"] as const;

export function fetchWeek(of: string | null) {
  return apiFetch<MealWeek>(of ? `/meals/week?of=${encodeURIComponent(of)}` : "/meals/week");
}

export function fetchMeal(id: string) {
  return apiFetch<Meal>(`/meals/${id}`);
}

export function fetchLeftoverCandidates(day: string, slot: MealSlot) {
  return apiFetch<Meal[]>(
    `/meals/leftover-candidates?day=${encodeURIComponent(day)}&slot=${slot}`
  );
}

export function createMeal(body: MealBody) {
  return apiFetch<Meal>("/meals", { method: "POST", body: JSON.stringify(body) });
}

export function updateMeal(id: string, patch: MealPatch) {
  return apiFetch<Meal>(`/meals/${id}`, { method: "PATCH", body: JSON.stringify(patch) });
}

export async function deleteMeal(id: string): Promise<void> {
  await apiFetch<null>(`/meals/${id}`, { method: "DELETE" });
}

export function copyRecipeToMeal(mealId: string, recipeId: string) {
  return apiFetch<Meal>(`/meals/${mealId}/recipe/copy`, {
    method: "POST",
    body: JSON.stringify({ recipe_id: recipeId }),
  });
}
