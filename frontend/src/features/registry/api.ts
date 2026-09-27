import type { QueryClient } from "@tanstack/react-query";
import { ApiError, apiFetch } from "../../api/client";
import type {
  AliasMoved,
  IngredientDetail,
  MergeCounts,
  RegistryRefusal,
} from "../../domain/types";

export function fetchIngredientDetail(id: string) {
  return apiFetch<IngredientDetail>(`/ingredients/${id}`);
}

/** `name` rinomina (nome e nome a video insieme), `category` cambia reparto. */
export function patchIngredient(id: string, body: { name?: string; category?: string }) {
  return apiFetch<IngredientDetail>(`/ingredients/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}

/** Con `dryRun` è l'anteprima: la stessa fusione, annullata dal server (spec §5.1). */
export function mergeIngredient(id: string, into: string, dryRun: boolean) {
  return apiFetch<MergeCounts>(`/ingredients/${id}/merge`, {
    method: "POST",
    body: JSON.stringify({ into, dry_run: dryRun }),
  });
}

export function moveAlias(ingredientId: string, aliasId: string, targetId: string) {
  return apiFetch<AliasMoved>(`/ingredients/${ingredientId}/aliases/${aliasId}`, {
    method: "PATCH",
    body: JSON.stringify({ ingredient_id: targetId }),
  });
}

export function deleteAlias(ingredientId: string, aliasId: string) {
  return apiFetch<null>(`/ingredients/${ingredientId}/aliases/${aliasId}`, { method: "DELETE" });
}

/** Il rifiuto dell'anagrafica dentro un errore, o `null` se l'errore è un altro.
 *
 * È il `code` a dire che è un rifiuto: un 409 senza `code` (il termine già in coda, per
 * dire) resta un errore qualsiasi, e lo schermo lo tratta come tale. */
export function registryRefusal(error: unknown): RegistryRefusal | null {
  if (!(error instanceof ApiError) || error.status !== 409) return null;
  const body = error.body as { code?: unknown } | null;
  return body !== null && typeof body.code === "string" ? (body as RegistryRefusal) : null;
}

// Quel che una correzione dell'anagrafica può cambiare a video: la scheda stessa, le
// ricerche, la dispensa, la lista, il ricettario e il dettaglio di una ricetta, e le
// decisioni della coda (una fusione le ridecide sul vincitore).
const TOUCHED = [
  "registry", "ingredients", "products", "pantry", "shopping-list", "recipes", "recipe",
  "import-terms",
] as const;

/** Dopo una correzione, tutto quel che potrebbe mostrarla è vecchio.
 *
 * Con `refetch = false` si segna vecchio senza rileggere: serve a chi sta per lasciare
 * la schermata (una fusione, un'eliminazione), perché rileggere subito vorrebbe dire
 * chiedere al server una scheda che non esiste più. La schermata dopo rilegge da sé.
 *
 * `excludeQueryKey`, se dato, lascia fuori le query la cui chiave comincia così: serve a
 * chi rilegge dopo un guasto della fusione vera senza rilanciare anche l'anteprima della
 * fusione, che è già un'intera fusione (fino a 130s) e non è lei ad essere fallita
 * (Task 17, fix round 2). */
export function refreshAfterCorrection(
  client: QueryClient,
  refetch = true,
  excludeQueryKey?: readonly unknown[]
) {
  const isExcluded = (key: readonly unknown[]) =>
    excludeQueryKey !== undefined && excludeQueryKey.every((part, i) => key[i] === part);
  return Promise.all(
    TOUCHED.map((key) =>
      client.invalidateQueries({
        queryKey: [key],
        refetchType: refetch ? "active" : "none",
        predicate: (query) => !isExcluded(query.queryKey),
      })
    )
  );
}
