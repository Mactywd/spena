/** La scala del costo di una ricetta (R9): un livello da 1 a 5, non una cifra.
 * Stessi estremi di `COST_MIN`/`COST_MAX` in backend/app/domain/rules.py. */
export const COST_STEPS = [1, 2, 3, 4, 5] as const;

export function costLabel(cost: number): string {
  return `Costo ${cost} su ${COST_STEPS.length}`;
}
