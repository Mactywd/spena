import { apiFetch } from "../../api/client";
import type { RecipeDetail, RecipeSummary } from "../../domain/types";

export function searchRecipes(query: string, onlyCookable: boolean) {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  if (onlyCookable) params.set("only_cookable", "true");
  return apiFetch<RecipeSummary[]>(`/recipes/search?${params.toString()}`);
}

export function fetchRecipe(id: string) {
  return apiFetch<RecipeDetail>(`/recipes/${id}`);
}

export function createRecipe(body: unknown) {
  return apiFetch<RecipeDetail>("/recipes", { method: "POST", body: JSON.stringify(body) });
}

export function cookRecipe(
  id: string,
  body: {
    servings?: number;
    transitions: { pantry_item_id: string; to_status: string; restock: boolean }[];
  }
) {
  return apiFetch<{ event_id: string; updated: number; restocked: number }>(
    `/recipes/${id}/cook`,
    { method: "POST", body: JSON.stringify(body) }
  );
}
