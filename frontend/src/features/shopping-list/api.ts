import { apiFetch } from "../../api/client";
import type { Ingredient, ShoppingItem } from "../../domain/types";

export function fetchShoppingList(statuses: string[] = ["pending", "checked"]) {
  const query = statuses.map((s) => `status=${s}`).join("&");
  return apiFetch<ShoppingItem[]>(`/shopping-list?${query}`);
}

export function addShoppingItem(rawText: string, ingredientId?: string) {
  return apiFetch<ShoppingItem>("/shopping-list", {
    method: "POST",
    body: JSON.stringify({ raw_text: rawText, ingredient_id: ingredientId ?? null }),
  });
}

export function patchShoppingItem(
  id: string,
  body: { status?: string; ingredient_id?: string }
) {
  return apiFetch<ShoppingItem>(`/shopping-list/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

export function searchIngredients(query: string) {
  return apiFetch<Ingredient[]>(`/ingredients/search?q=${encodeURIComponent(query)}`);
}

/** L'ultima uscita per una voce il cui testo libero non somiglia a nessun
 * ingrediente: crearlo è l'unico modo perché quella voce non resti in lista per
 * sempre. La normalizzazione del nome la fa il backend, non noi. */
export function createIngredient(body: { name: string; display_name: string; category: string }) {
  return apiFetch<Ingredient>("/ingredients", { method: "POST", body: JSON.stringify(body) });
}
