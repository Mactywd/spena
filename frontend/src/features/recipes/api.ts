import { apiFetch } from "../../api/client";
import type { CookResult, RecipeDetail, RecipeDraft, RecipeSummary } from "../../domain/types";

export function searchRecipes(query: string, onlyCookable: boolean) {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  if (onlyCookable) params.set("only_cookable", "true");
  return apiFetch<RecipeSummary[]>(`/recipes/search?${params.toString()}`);
}

/** Se la ricerca del ricettario è ibrida o solo testuale, in questo momento. Il
 * backend la dichiara in una rotta sua (spec §11: «il modello di embedding non
 * caricato → la ricerca degrada a sola ricerca testuale, con avviso discreto»), e
 * non manda nessun testo da mostrare: la frase è nostra. */
export function fetchSearchMode() {
  return apiFetch<{ semantic: boolean }>("/recipes/search-mode");
}

export function fetchRecipe(id: string) {
  return apiFetch<RecipeDetail>(`/recipes/${id}`);
}

export function createRecipe(body: unknown) {
  return apiFetch<RecipeDetail>("/recipes", { method: "POST", body: JSON.stringify(body) });
}

// Propone una ricetta, non la salva: il salvataggio passa da createRecipe come
// per ogni altra fonte, una volta che l'utente ha visto e corretto la bozza.
export function draftRecipe(prompt: string) {
  return apiFetch<RecipeDraft>("/recipes/ai-draft", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
}

export function cookRecipe(
  id: string,
  body: {
    servings?: number;
    transitions: { pantry_item_id: string; to_status: string; restock: boolean }[];
  }
) {
  return apiFetch<CookResult>(`/recipes/${id}/cook`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
