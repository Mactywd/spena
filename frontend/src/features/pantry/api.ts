import { apiFetch } from "../../api/client";
import type { PantryItem, PantryStatus } from "../../domain/types";

export function fetchPantry() {
  return apiFetch<PantryItem[]>("/pantry");
}

export function patchPantryItem(
  id: string,
  body: { status?: PantryStatus; archived?: boolean }
) {
  return apiFetch<PantryItem>(`/pantry/${id}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}
