// Rispecchiano gli schemi Pydantic del backend. La logica resta là: qui solo forme.
export type PantryStatus = "available" | "low" | "finished";
export type ExpiryState = "soon" | "expired";
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
    // `null` quando Open Food Facts conosce il codice ma non il nome: il modulo
    // parte vuoto e lo chiede, invece di proporre un segnaposto (S20)
    name: string | null;
    brand: string | null;
    barcode: string;
    nutrients: Record<string, number>;
    image_url: string | null;
  } | null;
  // se la cifra di controllo GTIN torna, detto dal backend (app/domain/barcodes.py):
  // un avviso, mai un rifiuto — i codici interni di negozio esistono
  valid_checksum: boolean;
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
  /** La scadenza di questo barattolo, `null` se non è stata scritta. */
  expires_on: string | null;
  /** Il verdetto, già preso dal server: la soglia dei sette giorni non vive qui. */
  expiry: ExpiryState | null;
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

// La risposta dell'aggiunta in lista: la voce, più lo stesso `added` del rientro
// dalla dispensa. Falso vuol dire che l'ingrediente era già da comprare e la voce è
// quella che c'era (S18): il backend non scrive il doppione.
export interface ShoppingItemAdded extends ShoppingItem, RestockResult {}

export interface RecipeSummary {
  id: string;
  title: string;
  description: string | null;
  source: RecipeSource;
  missing: number;
  cookable: boolean;
  /** I nomi di quel che manca, in ordine alfabetico, decisi dal server. Il client
   * non li ricava da `ingredients`: chi manca lo dice la regola primario/secondario,
   * che vive nel backend. */
  missing_names: string[];
  image_url: string | null;
  prep_minutes: number | null;
  cook_minutes: number | null;
  category: string | null;
  /** Il costo, da 1 a 5 (R9). `null` è «non indicato», non «economica». */
  cost: number | null;
  /** Quando è stata eliminata, in ISO 8601 (R10). Negli elenchi è sempre `null`: il
   * server esclude le eliminate. Il dettaglio la manda, perché un collegamento vecchio
   * porti a «Ripristina» e non a un errore. */
  archived_at: string | null;
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
  /** Vero finché una pagina dell'import rifà questa ricetta: salvare una modifica la
   * rende tua, e l'import non la riscrive più (R10 §4). Lo decide il server. */
  owned_by_import: boolean;
}

/** Una riga come la si scrive: un ingrediente esistente, oppure nome e categoria con
 * cui crearlo salvando (`RecipeIngredientIn` nel backend). `note` si manda solo se c'è. */
export interface RecipeIngredientBody {
  ingredient_id?: string;
  name?: string;
  category?: string | null;
  role: IngredientRole;
  quantity_text: string | null;
  note?: string;
}

/** Quel che si scrive di una ricetta, alla creazione e alla modifica (`RecipeFields`
 * nel backend). La provenienza la aggiunge solo la creazione. */
export interface RecipeBody {
  title: string;
  description: string | null;
  category: string | null;
  instructions: string;
  servings: number | null;
  cost: number | null;
  ingredients: RecipeIngredientBody[];
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
  /** La proposta dell'AI, già controllata dal backend: un gradino o niente. */
  cost: number | null;
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
  /** Se il "map" ha creato l'ingrediente (`true`) o l'ha agganciato (`false`).
   * `null` o assente: non si sa (decisioni prima del 2026-09-28, o non deciso). */
  created_ingredient?: boolean | null;
  /** Quando è stata presa, in ISO 8601. Ordina l'elenco delle decisioni recenti,
   * dove quelle dell'AI e quelle a mano stanno insieme (R11). */
  decided_at: string | null;
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
  /** R10: le ricette tue (modificate o eliminate) che contengono il termine, lasciate
   * come sono. */
  adopted_untouched: number;
  /** L'ingrediente del termine resta perché una di quelle ricette lo usa. */
  ingredient_kept_for_adopted: boolean;
}

// L'esito di un rientro in lista. `added` falso non è un errore: la voce era già da
// comprare, e dirlo è diverso dal far credere di aver aggiunto qualcosa.
export interface RestockResult {
  added: boolean;
}

// L'anagrafica (S9): la scheda dell'ingrediente, la fusione, i rifiuti.
export interface AliasEntry {
  id: string;
  alias: string;
  source: string;
  /** Vero se l'alias è la metà di una decisione della coda: si corregge da lì. */
  decided_in_queue: boolean;
  /** Il termine di quella decisione, `null` se l'alias non ne è la metà. */
  term_id: string | null;
}

export interface ProductBrief {
  id: string;
  name: string;
  brand: string | null;
  barcode: string | null;
}

export interface IngredientUsage {
  recipes: number;
  pantry: number;
  shopping: number;
}

export interface IngredientDetail extends Ingredient {
  aliases: AliasEntry[];
  products: ProductBrief[];
  usage: IngredientUsage;
}

/** Quel che una fusione muove. Gli stessi numeri escono dall'anteprima, che è la
 * fusione stessa annullata (spec S9 §5.1). */
export interface MergeCounts {
  dry_run: boolean;
  loser_name: string;
  winner_id: string;
  winner_name: string;
  recipes_rebuilt: number;
  recipe_lines_moved: number;
  pantry_items: number;
  shopping_items: number;
  /** Voci attive del perdente tolte (archiviate): il vincitore era già in lista. */
  shopping_items_dropped: number;
  products: number;
  aliases: number;
  cooking_events_relinked: number;
}

export interface AliasMoved {
  /** `null` se l'alias era il nome stesso dell'ingrediente d'arrivo, e quindi è sparito. */
  alias: AliasEntry | null;
  ingredient: Ingredient;
}

/** Il corpo di un 409 dell'anagrafica. `code` dice quale passo offrire (spec S9 §7),
 * l'ostacolo accanto dice con chi. */
export type RegistryRefusal =
  | { code: "name_taken" | "kind_mismatch"; detail: string; existing?: Ingredient }
  | {
      code: "non_food_in_recipes";
      detail: string;
      recipe_count: number;
      /** Le ricette che lo usano, eliminate comprese (R10): una ricetta eliminata si
       * ripristina con le sue righe, quindi blocca come le altre, ma va segnata. */
      recipes: { id: string; title: string; archived: boolean }[];
      /** Le pagine dell'import in attesa che, materializzate, lo userebbero. */
      pending_import_count: number;
      /** I termini che le legano qui, al più dieci per nome; il conto dice il resto. */
      pending_terms: { id: string; display_name: string }[];
      pending_term_count: number;
    }
  | {
      code: "import_alias" | "decision_refused";
      detail: string;
      term: { id: string; display_name: string };
    }
  | { code: "barcode_taken"; detail: string; existing: ProductBrief }
  | {
      code:
        | "same_ingredient"
        | "empty_name"
        | "unknown_category"
        | "still_used"
        | "bad_checksum";
      detail: string;
    };

/** La scheda del prodotto (spec S9 §6.4): è anche la scheda dell'elemento di dispensa. */
export interface ProductDetail {
  id: string;
  name: string;
  brand: string | null;
  barcode: string | null;
  /** Se la cifra di controllo torna, detto dal server; `null` senza codice. */
  valid_checksum: boolean | null;
  ingredient: { id: string; name: string; display_name: string };
  /** Solo gli attivi: quelli che chi guarda la dispensa vede. */
  pantry_items: { id: string; status: PantryStatus; expires_on: string | null }[];
}
