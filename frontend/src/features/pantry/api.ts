import { apiFetch } from "../../api/client";
import type { PantryItem, PantryStatus, RestockResult } from "../../domain/types";

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
  body: {
    status?: PantryStatus;
    archived?: boolean;
    fill_percent?: number;
    /** `null` cancella la data: il backend rifiuta un corpo vuoto con 400, quindi
     * la cancellazione va scritta come `{ expires_on: null }`, mai come `{}`. */
    expires_on?: string | null;
  }
) {
  return apiFetch<PantryItem>(`/pantry/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

/** Rimette in lista una voce di dispensa, se non c'è già. La decisione è
 * dell'utente: questa chiamata parte solo da una risposta esplicita. */
export function restockPantryItem(id: string) {
  return apiFetch<RestockResult>(`/pantry/${id}/restock`, { method: "POST" });
}
