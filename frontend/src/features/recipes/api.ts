import { apiFetch, apiFetchWithHeaders } from "../../api/client";
import type {
  CookResult,
  RecipeBody,
  RecipeDetail,
  RecipeDraft,
  RecipeSource,
  RecipeSummary,
} from "../../domain/types";

/** Quante ricette per pagina. Si manda sempre, così il numero sta in un posto solo e
 * «l'ultima pagina era piena» si confronta con quel che si è chiesto davvero. */
export const RECIPE_PAGE_SIZE = 30;

/** Una pagina del ricettario e quante ricette rispondono in tutto, contate dal server
 * prima del limite (`X-Total-Count`, T3 Consegna 4). `total` è `null` quando il server
 * non lo dice: meglio nessun numero che uno inventato. */
export interface RecipePage {
  recipes: RecipeSummary[];
  total: number | null;
  /** Vero solo quando la piscina dei candidati era piena (ramo con le parole,
   * `X-Total-Count-Lower-Bound: 1`): `total` conta solo quelli guardati, non l'intero
   * ricettario, e l'etichetta dei risultati dice «almeno N ricette» (R-B). */
  totalIsLowerBound: boolean;
}

/** Il totale dell'intestazione, o `null` se manca o non è un intero. */
export function totalFrom(headers: Headers): number | null {
  const raw = headers.get("X-Total-Count");
  if (raw === null || !/^\d+$/.test(raw)) return null;
  return Number(raw);
}

/** Se il totale è solo un minimo: vero solo quando `X-Total-Count-Lower-Bound` vale
 * esattamente `"1"` (R-B). */
export function lowerBoundFrom(headers: Headers): boolean {
  return headers.get("X-Total-Count-Lower-Bound") === "1";
}

/** Da dove parte la pagina dopo, o `undefined` se non ce n'è un'altra.
 *
 * L'offset è quante ricette sono arrivate, doppioni compresi: è il conto che il server
 * usa. Col totale si sa se ne mancano, e una pagina piena che è anche l'ultima non
 * offre più «Mostra altre» su una pagina vuota. Senza totale — un server di prima —
 * vale la regola di prima: una pagina piena fa pensare che ce ne sia un'altra. Una
 * pagina vuota chiude sempre: un totale che non torna non tiene aperto un «Mostra
 * altre» che non porta niente. */
export function nextPageOffset(lastPage: RecipePage, allPages: RecipePage[]): number | undefined {
  if (lastPage.recipes.length === 0) return undefined;
  const loaded = allPages.reduce((count, page) => count + page.recipes.length, 0);
  if (lastPage.total !== null) return loaded < lastPage.total ? loaded : undefined;
  return lastPage.recipes.length === RECIPE_PAGE_SIZE ? loaded : undefined;
}

/** I filtri del ricettario, per nome e non per posizione: con quattro argomenti di
 * cui due stringhe, scambiare «categoria» e «parole cercate» è un difetto che il
 * compilatore non può vedere. */
export async function searchRecipes({
  query = "",
  maxMissing = null,
  category = "",
  ingredientIds = [],
  offset = 0,
}: {
  query?: string;
  /** Quante cose si è disposti a comprare. `null` è «tutte»: non una soglia
   * altissima, ma l'assenza di soglia — il server le distingue, perché una soglia
   * nasconde le ricette oltre, e «tutte» non nasconde niente. */
  maxMissing?: number | null;
  category?: string;
  ingredientIds?: string[];
  /** Da quale ricetta ripartire: «Mostra altre» (R4). */
  offset?: number;
} = {}): Promise<RecipePage> {
  const params = new URLSearchParams();
  if (query.trim()) params.set("q", query.trim());
  // `!== null` e non la verità: `0` è la soglia più stretta, non la sua assenza
  if (maxMissing !== null) params.set("max_missing", String(maxMissing));
  if (category) params.set("category", category);
  // `append` e non `set`: il parametro si ripete, una volta per ingrediente, e il
  // backend li vuole tutti e due. Con `set` sopravviverebbe solo l'ultimo, e
  // l'elenco a video sarebbe più largo di quanto il filtro dichiara.
  for (const id of ingredientIds) params.append("ingredient_id", id);
  params.set("limit", String(RECIPE_PAGE_SIZE));
  if (offset > 0) params.set("offset", String(offset));
  const { data, headers } = await apiFetchWithHeaders<RecipeSummary[]>(
    `/recipes/search?${params.toString()}`
  );
  return { recipes: data, total: totalFrom(headers), totalIsLowerBound: lowerBoundFrom(headers) };
}

export function fetchCategories() {
  return apiFetch<string[]>("/recipes/categories");
}

/** Se la ricerca del ricettario è ibrida o solo testuale, in questo momento. Il
 * backend la dichiara in una rotta sua (spec §11: «il modello di embedding non
 * caricato → la ricerca degrada a sola ricerca testuale, con avviso discreto»), e
 * non manda nessun testo da mostrare: la frase è nostra. */
export function fetchSearchMode() {
  return apiFetch<{ semantic: boolean }>("/recipes/search-mode");
}

export function fetchRecipe(id: string, servings?: number) {
  const query = servings ? `?servings=${servings}` : "";
  return apiFetch<RecipeDetail>(`/recipes/${id}${query}`);
}

export function createRecipe(body: RecipeBody & { source: RecipeSource; source_ref: string | null }) {
  return apiFetch<RecipeDetail>("/recipes", { method: "POST", body: JSON.stringify(body) });
}

/** La ricetta intera, righe comprese (R10). La provenienza non si manda: non si cambia. */
export function updateRecipe(id: string, body: RecipeBody) {
  return apiFetch<RecipeDetail>(`/recipes/${id}`, { method: "PUT", body: JSON.stringify(body) });
}

/** Elimina (`true`) o ripristina (`false`): non c'è una `DELETE`, come in dispensa. */
export function setRecipeArchived(id: string, archived: boolean) {
  return apiFetch<RecipeDetail>(`/recipes/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ archived }),
  });
}

// Propone una ricetta, non la salva: il salvataggio passa da createRecipe come
// per ogni altra fonte, una volta che l'utente ha visto e corretto la bozza.
export function draftRecipe(prompt: string) {
  return apiFetch<RecipeDraft>("/recipes/ai-draft", {
    method: "POST",
    body: JSON.stringify({ prompt }),
  });
}

export function cookRecipe(
  id: string,
  body: {
    servings?: number;
    transitions: { pantry_item_id: string; to_status: string; restock: boolean }[];
  }
) {
  return apiFetch<CookResult>(`/recipes/${id}/cook`, {
    method: "POST",
    body: JSON.stringify(body),
  });
}
