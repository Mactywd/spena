// Rispecchiano gli schemi Pydantic del backend. La logica resta là: qui solo forme.
export type PantryStatus = "available" | "low" | "finished";
export type Availability = "available" | "low" | "missing";
export type IngredientRole = "primary" | "secondary";
export type RecipeSource = "dataset" | "manual" | "ai";

export interface Ingredient {
  id: string;
  name: string;
  display_name: string;
  category: string;
}

export interface Product {
  id: string;
  ingredient_id: string;
  name: string;
  brand: string | null;
  barcode: string | null;
  source: string;
  nutrients: Record<string, number> | null;
  image_url: string | null;
}

export interface BarcodeLookup {
  found: boolean;
  origin: "catalog" | "openfoodfacts" | "unknown";
  product: Product | null;
  suggestion: {
    name: string;
    brand: string | null;
    barcode: string;
    nutrients: Record<string, number>;
    image_url: string | null;
  } | null;
}

export interface PantryItem {
  id: string;
  ingredient_id: string;
  product_id: string | null;
  ingredient_name: string;
  ingredient_category: string;
  product_name: string | null;
  product_brand: string | null;
  status: PantryStatus;
  note: string | null;
  added_at: string;
}

export interface ShoppingItem {
  id: string;
  raw_text: string;
  ingredient_id: string | null;
  ingredient_name: string | null;
  ingredient_category: string | null;
  status: "pending" | "checked" | "done" | "archived";
  reason: "manual" | "finished_while_cooking" | "low_while_cooking";
  created_at: string;
}

export interface RecipeSummary {
  id: string;
  title: string;
  description: string | null;
  source: RecipeSource;
  missing: number;
  cookable: boolean;
  image_url: string | null;
  prep_minutes: number | null;
  cook_minutes: number | null;
  category: string | null;
}

export interface RecipeIngredientLine {
  ingredient_id: string;
  ingredient_name: string;
  role: IngredientRole;
  quantity_text: string | null;
  note: string | null;
  availability: Availability;
  satisfied: boolean;
}

export interface RecipeDetail extends RecipeSummary {
  instructions: string;
  servings: number | null;
  source_ref: string | null;
  ingredients: RecipeIngredientLine[];
}

// L'esito di una cottura, così come lo restituisce il backend: quante voci di
// dispensa ha aggiornato e quante sono tornate in lista della spesa. Numeri da
// mostrare, mai da ricalcolare qui.
export interface CookResult {
  event_id: string;
  updated: number;
  restocked: number;
}

// Un ingrediente proposto da Claude, prima che l'utente l'accetti: `ingredient_id`
// è null quando niente in anagrafica gli somiglia, e `confident` è false quando
// l'aggancio è solo un suggerimento. Nessuno dei due casi va accettato in silenzio.
export interface DraftIngredient {
  raw_name: string;
  role: IngredientRole;
  quantity_text: string | null;
  ingredient_id: string | null;
  matched_name: string | null;
  confident: boolean;
}

// La bozza di ricetta restituita da POST /recipes/ai-draft. Non salva nulla da
// sé: propone soltanto, e non contiene mai valori nutrizionali.
export interface RecipeDraft {
  title: string;
  description: string | null;
  instructions: string;
  servings: number | null;
  ingredients: DraftIngredient[];
}

export interface ImportStatus {
  fetched: number;
  pending_recipes: number;
  imported: number;
  skipped: number;
  pending_terms: number;
}

export interface TermSuggestion {
  ingredient_id: string;
  name: string;
  certain: boolean;
}

export interface ImportTerm {
  id: string;
  display_name: string;
  /** Quante ricette scaricate aspettano questa decisione. Ordina la coda. */
  occurrences: number;
  suggestion: TermSuggestion | null;
  waiting_titles: string[];
}

export type TermAction = "map" | "create" | "ignore";

export interface TermProposal {
  term_id: string;
  action: TermAction;
  ingredient_id: string | null;
  name: string | null;
  display_name: string | null;
  category: string | null;
}

export interface TermDecisionResult {
  unlocked: number;
  remaining_terms: number;
}
