import { apiFetch } from "../../api/client";
import type {
  IngredientSubstitutions,
  LineSubstitution,
  SubstitutionBody,
  SubstitutionContext,
} from "./types";

function linePath(recipeId: string, ingredientId: string) {
  return `/recipes/${recipeId}/substitutes/${ingredientId}`;
}

export function fetchLineSubstitution(recipeId: string, ingredientId: string) {
  return apiFetch<LineSubstitution>(linePath(recipeId, ingredientId));
}

export function askLineSubstitution(recipeId: string, ingredientId: string) {
  return apiFetch<LineSubstitution>(`${linePath(recipeId, ingredientId)}/ask`, { method: "POST" });
}

/** Quel che il pannello mostra: la risposta salvata, o — se non c'è — quella che il
 * server chiede adesso all'AI e salva (R5: una voce scoperta si calcola al primo tocco).
 * Senza AI torna una risposta vuota con `ai_failed`, mai un errore: la strada a mano
 * resta. */
export async function loadLineSubstitution(recipeId: string, ingredientId: string) {
  const saved = await fetchLineSubstitution(recipeId, ingredientId);
  return saved.verdict !== null ? saved : askLineSubstitution(recipeId, ingredientId);
}

/** «Non va bene qui»: la correzione di questa ricetta, e solo di questa. */
export function saveLineSubstitution(recipeId: string, ingredientId: string, body: SubstitutionBody) {
  return apiFetch<LineSubstitution>(linePath(recipeId, ingredientId), {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

/** «Torna al suggerimento generale». */
export function resetLineSubstitution(recipeId: string, ingredientId: string) {
  return apiFetch<null>(linePath(recipeId, ingredientId), { method: "DELETE" });
}

export function fetchIngredientSubstitutions(ingredientId: string) {
  return apiFetch<IngredientSubstitutions>(`/ingredients/${ingredientId}/substitutes`);
}

/** La voce generale, scritta a mano in Anagrafica (anche «Va bene così»). */
export function saveIngredientSubstitution(
  ingredientId: string,
  context: SubstitutionContext,
  body: SubstitutionBody
) {
  return apiFetch<IngredientSubstitutions>(`/ingredients/${ingredientId}/substitutes/${context}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}
