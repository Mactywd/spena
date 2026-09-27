import type { IngredientUsage } from "../../domain/types";

/** Dove è usato un ingrediente, in una riga: «in 42 ricette · 1 in dispensa · in lista».
 * Il peso di una correzione, detto prima di farla (spec §6.3). */
export function usageText(usage: IngredientUsage): string {
  const parts = [
    usage.recipes === 0
      ? "in nessuna ricetta"
      : usage.recipes === 1
        ? "in 1 ricetta"
        : `in ${usage.recipes} ricette`,
  ];
  if (usage.pantry > 0) parts.push(`${usage.pantry} in dispensa`);
  if (usage.shopping > 0) parts.push("in lista");
  return parts.join(" · ");
}
