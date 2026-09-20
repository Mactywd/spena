import { apiFetch } from "../../api/client";
import type { CookResult, RecipeDetail, RecipeDraft, RecipeSummary } from "../../domain/types";

/** I filtri del ricettario, per nome e non per posizione: con quattro argomenti di
 * cui due stringhe, scambiare «categoria» e «parole cercate» è un difetto che il
 * compilatore non può vedere. */
export function searchRecipes({
  query = "",
  onlyCookable = false,
  category = "",
  ingredientIds = [],
}: {
  query?: string;
  onlyCookable?: boolean;
  category?: string;
  ingredientIds?: string[];
} = {}) {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  if (onlyCookable) params.set("only_cookable", "true");
  if (category) params.set("category", category);
  // `append` e non `set`: il parametro si ripete, una volta per ingrediente, e il
  // backend li vuole tutti e due. Con `set` sopravviverebbe solo l'ultimo, e
  // l'elenco a video sarebbe più largo di quanto il filtro dichiara.
  for (const id of ingredientIds) params.append("ingredient_id", id);
  return apiFetch<RecipeSummary[]>(`/recipes/search?${params.toString()}`);
}

export function fetchCategories() {
  return apiFetch<string[]>("/recipes/categories");
}

/** Se la ricerca del ricettario è ibrida o solo testuale, in questo momento. Il
 * backend la dichiara in una rotta sua (spec §11: «il modello di embedding non
 * caricato → la ricerca degrada a sola ricerca testuale, con avviso discreto»), e
 * non manda nessun testo da mostrare: la frase è nostra. */
export function fetchSearchMode() {
  return apiFetch<{ semantic: boolean }>("/recipes/search-mode");
}

export function fetchRecipe(id: string, servings?: number) {
  const query = servings ? `?servings=${servings}` : "";
  return apiFetch<RecipeDetail>(`/recipes/${id}${query}`);
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
