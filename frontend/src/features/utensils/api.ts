import { apiFetch } from "../../api/client";
import type { Utensil, UtensilInput } from "../../domain/types";

export const UTENSILS_KEY = ["utensils"] as const;

export function fetchUtensils() {
  return apiFetch<Utensil[]>("/utensils");
}

export function createUtensil(body: UtensilInput) {
  return apiFetch<Utensil>("/utensils", { method: "POST", body: JSON.stringify(body) });
}

export function patchUtensil(id: string, body: Partial<UtensilInput>) {
  return apiFetch<Utensil>(`/utensils/${id}`, { method: "PATCH", body: JSON.stringify(body) });
}

export function deleteUtensil(id: string) {
  return apiFetch<null>(`/utensils/${id}`, { method: "DELETE" });
}
