import { apiFetch } from "../../api/client";
import type { PantryItem, PantryStatus } from "../../domain/types";

export function fetchPantry() {
  return apiFetch<PantryItem[]>("/pantry");
}

/** L'ingresso diretto in dispensa della spec §8.3: qualcosa che non era in lista
 * e che quindi non passa da «Sistema la spesa». Entra `available` e senza
 * prodotto — sfusa — perché la marca si aggancia con un codice a barre o dal
 * catalogo, e qui non c'è niente da scansionare. */
export function addPantryItem(ingredientId: string) {
  return apiFetch<PantryItem>("/pantry", {
    method: "POST",
    body: JSON.stringify({ ingredient_id: ingredientId, status: "available" }),
  });
}

export function patchPantryItem(
  id: string,
  body: { status?: PantryStatus; archived?: boolean; fill_percent?: number }
) {
  return apiFetch<PantryItem>(`/pantry/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}
