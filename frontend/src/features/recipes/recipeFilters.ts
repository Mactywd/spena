import type { Ingredient } from "../../domain/types";
import { BUDGET_STEPS } from "./missingBudget";

/** Quel che si è chiesto al ricettario: le parole, la scala, la categoria, gli
 * ingredienti. Gli ingredienti interi e non solo gli id: i nomi servono alle pastiglie
 * del pannello e al messaggio del vuoto, e una seconda chiamata per riaverli sarebbe un
 * giro in rete per qualcosa che l'utente ha appena toccato. */
export interface RecipeFilters {
  query: string;
  /** `null` è «Tutte»: l'assenza di soglia, non una soglia larghissima. */
  maxMissing: number | null;
  /** `""` è «Tutte». */
  category: string;
  ingredients: Ingredient[];
}

export const EMPTY_FILTERS: RecipeFilters = {
  query: "",
  maxMissing: null,
  category: "",
  ingredients: [],
};

/** Dove i filtri si ricordano finché l'app è aperta (Mattia, 2026-09-29): tornando da una
 * ricetta si ritrovano. `sessionStorage` e non `localStorage`: chiusa l'app, il
 * ricettario riparte intero, invece di aprirsi filtrato da una ricerca di tre giorni fa. */
export const FILTERS_KEY = "spena.ricettario.filtri";

/** Quanti filtri sono accesi, per il numero su «Filtri»: la categoria conta uno, ogni
 * ingrediente uno. Le parole e la scala stanno fuori dal pannello, sempre a video, e non
 * contano: il numero dice cosa c'è dentro il pannello chiuso. */
export function activeFilterCount(filters: Pick<RecipeFilters, "category" | "ingredients">): number {
  return (filters.category ? 1 : 0) + filters.ingredients.length;
}

/** Il nome di «Filtri» per chi ascolta: la scritta a video, e il numero detto a parole. Il
 * nome comincia con la scritta (label-in-name), così chi dà comandi a voce dice «Filtri». */
export function filtersButtonName(count: number): string {
  if (count === 0) return "Filtri";
  return count === 1 ? "Filtri, 1 attivo" : `Filtri, ${count} attivi`;
}

/** Quante ricette rispondono, a parole. `null` quando il server non lo dice: meglio nessun
 * numero che uno inventato. Con `lowerBound` e `total >= 1`, il numero è un minimo:
 * la piscina di candidati era piena, potrebbero essercene altri. */
export function resultsLabel(total: number | null, lowerBound = false): string | null {
  if (total === null) return null;
  if (total === 0) return "Nessuna ricetta";
  const prefix = lowerBound ? "almeno " : "";
  return total === 1 ? `${prefix}1 ricetta` : `${prefix}${total} ricette`;
}

/** La `sessionStorage`, se si riesce ad aprirla: già leggerla può lanciare (dati del sito
 * bloccati), quindi anche l'accesso sta nel try. */
function sessionStore(): Storage | null {
  try {
    return globalThis.sessionStorage ?? null;
  } catch {
    return null;
  }
}

function isIngredient(value: unknown): value is Ingredient {
  if (typeof value !== "object" || value === null) return false;
  const v = value as Record<string, unknown>;
  return (
    typeof v.id === "string" &&
    typeof v.name === "string" &&
    typeof v.display_name === "string" &&
    typeof v.category === "string" &&
    (v.kind === "food" || v.kind === "non_food")
  );
}

/** I filtri ricordati, o quelli vuoti. Quel che non si riconosce si scarta pezzo per pezzo
 * — una scala che non è un gradino, un ingrediente scritto male, un doppione — e il resto
 * resta: una memoria scritta da una versione di prima non deve azzerare tutto. */
export function loadFilters(store: Storage | null = sessionStore()): RecipeFilters {
  if (store === null) return EMPTY_FILTERS;
  let saved: unknown;
  try {
    saved = JSON.parse(store.getItem(FILTERS_KEY) ?? "null");
  } catch {
    return EMPTY_FILTERS;
  }
  if (typeof saved !== "object" || saved === null) return EMPTY_FILTERS;
  const s = saved as Record<string, unknown>;
  const steps = BUDGET_STEPS.map((step) => step.value);
  const ingredients = Array.isArray(s.ingredients) ? s.ingredients.filter(isIngredient) : [];
  return {
    query: typeof s.query === "string" ? s.query : "",
    maxMissing:
      typeof s.maxMissing === "number" && steps.includes(s.maxMissing) ? s.maxMissing : null,
    category: typeof s.category === "string" ? s.category : "",
    // due volte lo stesso non stringe niente: resta il primo
    ingredients: ingredients.filter(
      (ingredient, n) => ingredients.findIndex((other) => other.id === ingredient.id) === n
    ),
  };
}

/** Scrive i filtri. Se non si può (memoria piena o bloccata), valgono lo stesso finché lo
 * schermo è aperto: il ricordo è una comodità, non una condizione. */
export function saveFilters(
  filters: RecipeFilters,
  store: Storage | null = sessionStore()
): void {
  if (store === null) return;
  try {
    store.setItem(FILTERS_KEY, JSON.stringify(filters));
  } catch {
    // vedi sopra: niente da fare, e niente da dire
  }
}
