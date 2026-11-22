import { apiFetch } from "../../api/client";
import type { PantryItem, PantryStatus, RestockResult } from "../../domain/types";

export function fetchPantry() {
  return apiFetch<PantryItem[]>("/pantry");
}

/** L'ingresso diretto in dispensa (S3): una confezione che non passa dalla lista. Entra
 * `available`; prodotto, scadenza e codice letto sono facoltativi, e si mandano sempre
 * (`null` quando non ci sono). Se il codice va al prodotto lo decide il backend
 * (`stock_one`, la stessa funzione della sistemazione): mai a un prodotto che ne ha già
 * uno, mai togliendolo a un altro. */
export function addPantryItem(entry: {
  ingredientId: string;
  productId: string | null;
  expiresOn: string | null;
  barcode: string | null;
}) {
  return apiFetch<PantryItem>("/pantry", {
    method: "POST",
    body: JSON.stringify({
      ingredient_id: entry.ingredientId,
      product_id: entry.productId,
      status: "available",
      expires_on: entry.expiresOn,
      barcode: entry.barcode,
    }),
  });
}

export function patchPantryItem(
  id: string,
  body: {
    status?: PantryStatus;
    archived?: boolean;
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
