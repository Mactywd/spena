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
  /** Il nome dell'ingrediente del prodotto (`Ingredient.name`), mandato dal server:
   * «È di un altro ingrediente: burro» lo dice senza che il client vada a cercarlo
   * (T3 Consegna 3). */
  ingredient_name: string;
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
  /** Il mondo della voce, deciso dal server (`ingredients.kind`): il selettore «Tutto /
   * Cibo / Casa» della Dispensa (S14) lo confronta, non lo ricava dal reparto. */
  ingredient_kind: "food" | "non_food";
  product_name: string | null;
  product_brand: string | null;
  status: PantryStatus;
  /** La posizione del cursore di prima di T3. Dalla Consegna 1 nessun client la
   * scrive più — le tacche mandano `status`, e `set_status` la azzera — ma la
   * colonna resta, annullabile. */
  fill_percent: number | null;
  note: string | null;
  added_at: string;
  /** La scadenza di questo barattolo, `null` se non è stata scritta. */
  expires_on: string | null;
  /** Il verdetto, già preso dal server: la soglia dei sette giorni non vive qui. */
  expiry: ExpiryState | null;
  /** La figura della riga (S12): l'emoji dell'ingrediente, `null` per il ripiego
   * sull'icona del reparto. La decide il server (l'AI o una persona in Anagrafica): qui
   * si mostra e basta. */
  ingredient_emoji: string | null;
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
  /** Il reparto più frequente fra le righe principali, deciso dal server
   * (`main_department` in `backend/app/domain/rules.py`): la miniatura del ricettario ne
   * mostra l'icona quando la foto manca (T3 Consegna 4). `null` senza righe principali. */
  main_department: string | null;
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
  /** Se da questa riga si può riscalare (R2, secondo modo): ha una dose strutturata più
   * grande di zero. Lo decide il server; «q.b.» e le righe senza dose no. */
  anchorable: boolean;
  /** La parola dell'unità da scrivere accanto al campo «Quanto ne fai?»: il plurale
   * deciso, o la parola com'è arrivata. `null` per un numero nudo, o se la riga non si
   * riscala. */
  anchor_unit: string | null;
  note: string | null;
  availability: Availability;
  satisfied: boolean;
}

/** La ricetta da cui una variante nasce (R8), come la manda il server: il titolo di oggi
 * e se è stata eliminata. Il collegamento la apre comunque: eliminata, si apre dalla sua
 * lapide con «Ripristina» (R10). */
export interface RecipeOrigin {
  id: string;
  title: string;
  archived: boolean;
}

/** La dose fissata da cui il server ha riscalato la ricetta (R2, secondo modo). */
export interface RecipeAnchor {
  ingredient_id: string;
  /** La dose come il server l'ha letta, col punto («112.5»): torna così alla cottura. */
  amount: string;
  /** Le porzioni che quella dose fa, già arrotondate dal server; `null` se la ricetta
   * non dice per quante porzioni è. */
  equivalent_servings: number | null;
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
  /** La dose fissata, se la risposta è riscalata da un ingrediente; `null` altrimenti —
   * anche quando il server ha ignorato un'ancora che la ricetta non ha più. */
  anchor: RecipeAnchor | null;
  /** Vero finché una pagina dell'import rifà questa ricetta: salvare una modifica la
   * rende tua, e l'import non la riscrive più (R10 §4). Lo decide il server. */
  owned_by_import: boolean;
  /** Da quale ricetta nasce, se è una variante scritta con l'AI (R8); `null` altrimenti.
   * Lo dice il server: il client non cerca l'originale da sé. */
  derived_from: RecipeOrigin | null;
  /** Pasti (decisione 22): facoltativi, perché un backend vecchio in cache non li manda.
   * Si legge `in_book ?? true`. */
  in_book?: boolean;
  meal?: MealRef | null;
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
  /** La riga nomina con certezza un non alimentare: è staccata, e il modulo lo dice. Il
   * server lo manda sempre; facoltativo qui perché le bozze scritte a mano (i test, la
   * variante di R8) non lo portano, e senza vale «no». */
  non_food?: boolean;
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
  /** Se annullare questo "map" cancella l'ingrediente nato dall'import (`true`) o lo
   * lascia (`false`, agganciato a uno che c'era). Il `true` l'ha il termine che l'ha
   * creato, o quello che l'ha ereditato quando il creatore è stato annullato: i testi
   * dicono «creato dall'import», vero in tutti e due i casi. `null` o assente: non si sa
   * (decisioni prima del 2026-09-28, o non deciso). */
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
  /** Se il giro si è fermato a metà per un guasto dell'AI, la frase da mostrare
   * (scritta nel backend, spec llm-haiku §5); `null` se è arrivato in fondo. */
  stopped_notice?: string | null;
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

/** Perché una pagina dell'import è scartata, in un codice: le parole le scrive la
 * schermata (`features/recipe-import/skippedWords.ts`). Spec 2026-10-09-scartate-in-coda
 * §3.1. */
export type SkipCause = "unreadable" | "all_ignored" | "non_food" | "other";

export interface SkippedPage {
  id: string;
  url: string;
  /** Il titolo della ricetta; `null` per una pagina illeggibile, che non ne ha. */
  title: string | null;
  cause: SkipCause;
  /** La voce non alimentare, solo per `non_food` (e non sempre: un nome lunghissimo può
   * essere stato tagliato via dal limite del motivo). */
  non_food_name: string | null;
  /** Se «Rimetti in coda» può cambiare qualcosa: falso per una pagina illeggibile. */
  requeueable: boolean;
  /** Le cotture registrate che aspettano la ricetta di questa pagina. */
  waiting_cooking_events: number;
}

export interface SkippedPages {
  total: number;
  pages: SkippedPage[];
}

/** Com'è finita una pagina rimessa in coda. `recipe_id` solo se è entrata; `cause` e
 * `non_food_name` solo se è di nuovo scartata; `waiting_terms` solo se aspetta. */
export interface RequeueResult {
  outcome: "imported" | "skipped" | "waiting";
  title: string | null;
  url: string;
  recipe_id: string | null;
  cooking_relinked: number;
  cause: SkipCause | null;
  non_food_name: string | null;
  waiting_terms: string[];
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
  /** La figura delle sue righe in Dispensa (S12): un'emoji, o `null` per l'icona del
   * reparto. Solo nella scheda: la ricerca non la porta. */
  emoji: string | null;
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
      recipes: { id: string; title: string; archived: boolean; from_meal?: boolean }[];
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
        | "bad_checksum"
        | "unknown_emoji";
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

/** Uno strumento di cucina (spec 2026-11-12 §4.4). Il server pulisce nome e nota. */
export interface Utensil {
  id: string;
  name: string;
  note: string | null;
}

export interface UtensilInput {
  name: string;
  note: string | null;
}

export type MealSlot = "lunch" | "dinner";
export type MealStatus = "draft" | "official";
export interface MealRef {
  id: string;
  day: string;
  slot: MealSlot;
  dish: string;
  recipe_id: string | null;
}
export interface Meal {
  id: string;
  day: string;
  slot: MealSlot;
  week: string;
  dish: string;
  sides: string | null;
  away: boolean;
  status: MealStatus;
  unrecorded: boolean;
  recipe: { id: string; title: string; in_book: boolean } | null;
  leftover_of: MealRef | null;
  /** Se il pasto ha la chat con Claude: lo decide il backend (`MealOut.can_chat`). */
  can_chat?: boolean;
  /** La ricetta in preparazione o non arrivata: lo dice il backend (piano 6c). */
  recipe_state?: "none" | "preparing" | "failed";
  recipe_notice?: string | null;
  can_ask_recipe?: boolean;
  /** La scheda dei cambi ancora da applicare che riguarda questo pasto. */
  open_card_id?: string | null;
}
export interface MealWeek {
  monday: string;
  sunday: string;
  today: string;
  previous: string;
  next: string;
  days: string[];
  meals: Meal[];
  /** Qualche pasto della settimana ha la ricetta in preparazione. */
  preparing?: boolean;
}
export interface MealBody {
  day: string;
  slot: MealSlot;
  dish: string;
  sides: string | null;
  away: boolean;
  leftover_of_id: string | null;
  replace?: boolean;
  /** Lo spostamento stacca gli avanzi che verrebbero prima (risposta a `leftover_after`). */
  detach_leftovers?: boolean;
}
export type MealPatch = Partial<Pick<MealBody, "day" | "slot" | "dish" | "sides" | "away">> & {
  status?: "official";
  replace?: boolean;
  detach_leftovers?: boolean;
};

/** Una modifica della ricetta fatta da Claude, come la riga sotto la sua risposta
 * (`RecipeChangeOut`). Se si può annullare lo dice il backend. */
export interface RecipeChange {
  id: string;
  summary: string;
  created_recipe: boolean;
  undone: boolean;
  undoable: boolean;
}
export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  text: string;
  status: "pending" | "sent" | "failed";
  notice: string | null;
  created_at: string;
  changes: RecipeChange[];
  /** Le proposte e le schede del giro, sotto il messaggio (piano 6c). Facoltative: le
   * risposte vecchie in cache non le hanno. */
  proposals?: MealProposal[];
  cards?: ChangeCard[];
}
/** Le parti della ricetta cambiate dall'ultimo giro, da evidenziare nel dettaglio. */
export interface RecipeHighlight {
  ingredient_ids: string[];
  title: boolean;
  servings: boolean;
  instructions: boolean;
  description: boolean;
}
export interface DishChat {
  meal_id: string;
  conversation_id: string | null;
  messages: ChatMessage[];
  replying: boolean;
  highlight: RecipeHighlight | null;
  claude_ready: boolean;
  claude_notice: string | null;
}
/** Gli eventi dello streaming di una chat con Claude, già letti: `TChat` è la vista che
 * `done` ed `error` portano, quella del piatto (`POST /meals/{id}/chat/messages`) o quella
 * della pianificazione (`POST /planning/conversations/{id}/messages`). */
export type ChatStreamEvent<TChat = DishChat> =
  | { name: "start"; message: ChatMessage }
  | { name: "delta"; text: string }
  | { name: "change"; change: RecipeChange }
  | { name: "proposal"; proposal: MealProposal }
  | { name: "card"; card: ChangeCard }
  | { name: "done"; chat: TChat }
  // `chat` è null quando il server non ha potuto rileggerla (il pasto è sparito, o la
  // rilettura dopo un crollo è fallita): allora la chat si rilegge.
  | { name: "error"; code: string; notice: string; chat: TChat | null };

/** Una riga della scheda dei cambi (`ChangeRowOut`): «Ora», le note e chi si può
 * correggere li decide il backend. */
export interface ChangeRow {
  id: string;
  kind: "pantry" | "list" | "unlist";
  label: string;
  from_status: PantryStatus | null;
  to_status: PantryStatus | null;
  listed: boolean;
  checked: boolean;
  editable: boolean;
  note: string | null;
  applied: boolean | null;
}
export interface ChangeCard {
  id: string;
  kind: "forward" | "inverse";
  status: "proposed" | "applied" | "discarded" | "superseded";
  list_only: boolean;
  title: string;
  meals: MealRef[];
  rows: ChangeRow[];
  created_at: string;
  applied_at: string | null;
}

/** Una riga della proposta di pasti (`ProposalRowOut`). */
export interface ProposalRow {
  day: string;
  slot: MealSlot;
  dish: string;
  sides: string | null;
  effect: "new" | "officialize" | "replace";
  occupant: MealRef | null;
  meal_id: string | null;
}
export interface MealProposal {
  id: string;
  kind: "official" | "draft";
  status: "open" | "placed" | "superseded";
  rows: ProposalRow[];
  created_at: string;
}
/** La chat di pianificazione (`PlanningChatOut`). */
export interface PlanningChat {
  conversation_id: string | null;
  focus: { day: string; slot: MealSlot } | null;
  messages: ChatMessage[];
  replying: boolean;
  concluded: boolean;
  claude_ready: boolean;
  claude_notice: string | null;
}
/** La risposta di «Metti nella settimana» (`PlaceOut`): `follow_up` è il messaggio che il
 * telefono manda subito a Claude, scritto dal backend. */
export interface PlaceResult {
  chat: PlanningChat;
  meals: Meal[];
  follow_up: string;
}
