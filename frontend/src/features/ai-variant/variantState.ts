import type { RecipeDraft } from "../../domain/types";

/** L'id del pannello della variante nel dettaglio, per `aria-controls` del suo tasto. */
export const VARIANT_PANEL_ID = "variante-ai";

/** Dove si corregge la proposta: sotto la ricetta da cui nasce (R8). */
export function variantPath(recipeId: string): string {
  return `/ricette/${recipeId}/variante`;
}

/** Quel che il pannello consegna al modulo della variante, nella cronologia (R8): la
 * richiesta, la proposta dell'AI, e dell'originale il titolo (per le parole) e la
 * categoria (il modulo parte da lì: la proposta non ne ha). Nella cronologia e non in una
 * cache: regge un ricaricamento, e se ne va con la sua voce. */
export interface VariantState {
  prompt: string;
  draft: RecipeDraft;
  originTitle: string;
  originCategory: string | null;
}

/** La proposta portata dalla cronologia, o `null` se la voce non ne porta una — un
 * indirizzo scritto a mano, un preferito, una cronologia di prima. */
export function readVariantState(state: unknown): VariantState | null {
  if (typeof state !== "object" || state === null) return null;
  const candidate = state as Partial<VariantState>;
  const draft = candidate.draft;
  if (
    typeof candidate.prompt !== "string" ||
    typeof candidate.originTitle !== "string" ||
    typeof draft !== "object" ||
    draft === null ||
    !Array.isArray(draft.ingredients)
  )
    return null;
  return {
    prompt: candidate.prompt,
    draft,
    originTitle: candidate.originTitle,
    originCategory: typeof candidate.originCategory === "string" ? candidate.originCategory : null,
  };
}
