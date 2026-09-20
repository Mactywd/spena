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
  /** Se questa voce è cibo. Lo dice il server: la partizione dei reparti vive in
   * `kind_for_category`, nel dominio del backend. */
  kind: "food" | "non_food";
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
  /** Dove sta il cursore, 0–100. `null` per chi non l'ha mai mosso: è una posizione
   * a occhio, non una quantità, e non esiste finché nessuno l'ha indicata. */
  fill_percent: number | null;
  note: string | null;
  added_at: string;
}

export interface ShoppingItem {
  id: string;
  raw_text: string;
  ingredient_id: string | null;
  ingredient_name: string | null;
  ingredient_category: string | null;
  ingredient_kind: "food" | "non_food" | null;
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
  /** La dose da mostrare per le porzioni chieste: a 1× coincide con `quantity_text`.
   * Il calcolo resta nel backend — qui si mostra, non si ricalcola. */
  quantity_display: string | null;
  /** Se `quantity_display` è stato riscalato rispetto a `quantity_text`. */
  quantity_scaled: boolean;
  note: string | null;
  availability: Availability;
  satisfied: boolean;
}

export interface RecipeDetail extends RecipeSummary {
  instructions: string;
  servings: number | null;
  source_ref: string | null;
  ingredients: RecipeIngredientLine[];
  /** Le porzioni per cui il server ha effettivamente riscalato la risposta. */
  scaled_to: number | null;
  /** Quante righe non si sono potute riscalare e sono rimaste come sono. */
  unscalable_lines: number;
  /** Il denominatore di `unscalable_lines`: quante righe hanno una dose scritta.
   * Arriva dal server e non si ricalcola qui — `ingredients.length` conterebbe anche
   * le righe senza dose, che non sono dosi mancate. */
  dose_lines: number;
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
  proposed_category: string | null;
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
  /** Valorizzati solo per un termine già deciso, cioè solo nell'elenco della
   * revisione: la coda da decidere li ha sempre nulli. */
  decided_by: string | null;
  // Solo "map" o "ignored": non esiste un terzo valore "created". Nessun fatto
  // scritto oggi distingue un `map` che ha usato un ingrediente già in anagrafica
  // da uno che l'ha creato — vedi `_decided_action` in `backend/app/api/imports.py`
  // per il perché, compreso perché la deduzione che sembra ovvia è sbagliata.
  decided_action: "map" | "ignored" | null;
  decided_name: string | null;
}

export interface TermDecisionResult {
  unlocked: number;
  remaining_terms: number;
}

export interface DecideResult {
  applied: number;
  created: number;
  ignored: number;
  still_pending: number;
  unlocked: number;
  remaining_terms: number;
}

export interface UndoResult {
  recipes_requeued: number;
  ingredient_deleted: boolean;
  remaining_terms: number;
}

// L'esito di un rientro in lista. `added` falso non è un errore: la voce era già da
// comprare, e dirlo è diverso dal far credere di aver aggiunto qualcosa.
export interface RestockResult {
  added: boolean;
}
