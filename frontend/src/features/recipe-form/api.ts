import { apiFetch } from "../../api/client";
import type { Ingredient } from "../../domain/types";

/** L'ingrediente a cui questo nome si collegherebbe salvando la ricetta, o `null` se
 * salvando nascerebbe (`GET /ingredients/match`, piano 20). La regola è del server — la
 * stessa di `_resolve_lines` — e qui non se ne copia niente. */
export function matchNewName(name: string) {
  return apiFetch<{ ingredient: Ingredient | null }>(
    `/ingredients/match?${new URLSearchParams({ name })}`
  );
}
