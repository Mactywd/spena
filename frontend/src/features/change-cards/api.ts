import type { QueryClient } from "@tanstack/react-query";
import { apiFetch } from "../../api/client";
import type { ChangeCard, PantryStatus } from "../../domain/types";

export const cardKey = (id: string) => ["change-card", id] as const;
export const PENDING_CARDS_KEY = ["change-cards", "proposed"] as const;

export function fetchCard(id: string) {
  return apiFetch<ChangeCard>(`/change-cards/${id}`);
}

export function fetchPendingCards() {
  return apiFetch<ChangeCard[]>("/change-cards?status=proposed");
}

/** Le correzioni di Mattia (casella e stato) restano locali fino a qui: partono tutte
 * insieme, in una richiesta sola. */
export function applyCard(
  id: string,
  rows: { id: string; checked: boolean; to_status?: PantryStatus }[]
) {
  return apiFetch<ChangeCard>(`/change-cards/${id}/apply`, {
    method: "POST",
    body: JSON.stringify({ rows }),
  });
}

export function discardCard(id: string) {
  return apiFetch<ChangeCard>(`/change-cards/${id}/discard`, { method: "POST" });
}

export function addCardRow(id: string, body: { pantry_item_id: string } | { raw_text: string }) {
  return apiFetch<ChangeCard>(`/change-cards/${id}/rows`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}

/** Chi scrive in una scheda tocca anche pasti, dispensa e lista: si rileggono tutti. */
export function invalidateAfterCard(queryClient: QueryClient) {
  for (const key of [["change-card"], ["change-cards"], ["meals"], ["pantry"], ["shopping-list"]]) {
    void queryClient.invalidateQueries({ queryKey: key });
  }
}
