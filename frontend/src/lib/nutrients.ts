/** Un nutriente come lo manda il server (S4): nome, unità, e se è una delle otto righe
 * dell'etichetta, che si mostrano sempre. `value` è `null` solo per un principale che la
 * fonte non dà: a video «—», mai zero (CLAUDE.md, «missing nutrients stay missing»). */
export type NutrientValue = {
  key: string;
  label: string;
  unit: string;
  main: boolean;
  value: number | null;
};

/** Una riga della tabella: il nutriente, e una nota sotto il valore se serve (la fetta 2
 * ci scrive «su 3 righe di 4»). */
export type NutrientRow = NutrientValue & { note?: string };

/** Il numero all'italiana: kcal senza decimali, il resto con uno, due sotto l'unità, e
 * senza il punto delle migliaia (che in una tabella stretta si legge come un decimale). */
export function formatNutrient(value: number, unit: string): string {
  const digits = unit === "kcal" ? 0 : value !== 0 && Math.abs(value) < 1 ? 2 : 1;
  const number = value.toLocaleString("it-IT", { maximumFractionDigits: digits, useGrouping: false });
  return `${number} ${unit}`;
}
