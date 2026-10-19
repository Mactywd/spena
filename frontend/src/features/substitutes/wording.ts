import { ApiError } from "../../api/client";
import type { DecidedBy, SubstitutionContext } from "./types";

/** «nei piatti salati» / «nei dolci»: dentro una frase o un nome accessibile. */
export function contextIn(context: SubstitutionContext): string {
  return context === "dolce" ? "nei dolci" : "nei piatti salati";
}

/** Il titolo di una scheda in Anagrafica. */
export function contextTitle(context: SubstitutionContext): string {
  return context === "dolce" ? "Nei dolci" : "Nei piatti salati";
}

/** Da dove viene una risposta: la riga piccola sotto di lei. */
export function provenanceText(answer: {
  scope: "recipe" | "general" | null;
  decided_by: DecidedBy | null;
  context: SubstitutionContext;
}): string {
  if (answer.scope === "recipe") return "Scelto a mano per questa ricetta.";
  const forWhat = answer.context === "dolce" ? "per i dolci" : "per i piatti salati";
  return answer.decided_by === "ai" ? `Suggerito dall'AI ${forWhat}.` : `Scelto a mano ${forWhat}.`;
}

export function recipesText(count: number): string {
  if (count === 0) return "in nessuna ricetta";
  return count === 1 ? "in 1 ricetta" : `in ${count} ricette`;
}

export function overridesText(count: number): string | null {
  if (count === 0) return null;
  return count === 1 ? "Corretto a mano in 1 ricetta." : `Corretto a mano in ${count} ricette.`;
}

/** Il 422 del server porta la frase che dice cosa togliere: si mostra com'è. Un 422 di
 * validazione (con `detail` lista) e ogni altro guasto dicono di riprovare. */
export function saveErrorText(error: unknown): string {
  if (error instanceof ApiError && error.status === 422) {
    const detail = (error.body as { detail?: unknown } | null)?.detail;
    if (typeof detail === "string") return detail;
  }
  return "Non sono riuscito a salvare. Riprova.";
}
