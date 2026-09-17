import type { PantryStatus } from "../../domain/types";

// Lo stesso numero di `LOW_MAX_FILL` in backend/app/domain/rules.py, e non una
// seconda decisione: qui serve solo a dipingere le tre zone del cursore, mentre a
// decidere lo stato è il backend. Che i due restino uguali lo difende
// backend/tests/test_frontend_fill_zones.py, che legge questo file.
export const LOW_MAX_FILL = 30;

/** Da dove parte il cursore di una voce che non ne ha mai avuto uno.
 *
 * `fill_percent` resta NULL nel database e nell'API: non è una misura, e non deve
 * poter essere scambiata per una. Questo è solo il punto da cui si comincia a
 * trascinare, scelto dentro la zona dello stato che la voce ha davvero — così il
 * primo tocco non sposta il significato di niente.
 */
export function fillForStatus(status: PantryStatus): number {
  if (status === "finished") return 0;
  if (status === "low") return Math.round(LOW_MAX_FILL / 2);
  return 100;
}
