import { WORLDS, type PantryWorld } from "./pantryView";

/** Dove il mondo scelto in Dispensa si ricorda finché l'app è aperta (S14, Mattia
 * 2026-10-07). `sessionStorage` e non `localStorage`, come i filtri del ricettario
 * (`recipeFilters.ts`): chiusa l'app, la dispensa riparte intera, invece di aprirsi su
 * «Casa» per una scelta di tre giorni fa e sembrare senza cibo. */
export const WORLD_KEY = "spena.dispensa.mondo";

/** La `sessionStorage`, se si riesce ad aprirla: già leggerla può lanciare (dati del sito
 * bloccati), quindi anche l'accesso sta nel try. */
function sessionStore(): Storage | null {
  try {
    return globalThis.sessionStorage ?? null;
  } catch {
    return null;
  }
}

/** Il mondo ricordato, o «Tutto». Un valore che non si riconosce vale «Tutto»: il ricordo
 * è una comodità, e una scelta illeggibile non deve nascondere niente. */
export function loadWorld(store: Storage | null = sessionStore()): PantryWorld {
  if (store === null) return "all";
  try {
    const saved = store.getItem(WORLD_KEY);
    return WORLDS.find((world) => world === saved) ?? "all";
  } catch {
    return "all";
  }
}

/** Scrive il mondo. Se non si può (memoria piena o bloccata), vale lo stesso finché lo
 * schermo è aperto. */
export function saveWorld(world: PantryWorld, store: Storage | null = sessionStore()): void {
  if (store === null) return;
  try {
    store.setItem(WORLD_KEY, world);
  } catch {
    // vedi sopra: niente da fare, e niente da dire
  }
}
