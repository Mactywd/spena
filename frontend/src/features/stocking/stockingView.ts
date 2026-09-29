import type { stockItems } from "./api";
import type { Product, ShoppingItem } from "../../domain/types";

/** Come una voce entra in dispensa: sfusa, o con un prodotto del catalogo. */
export type Resolution =
  | { kind: "loose" }
  // `barcode`: il codice letto per la voce prima di scegliere il prodotto a
  // catalogo (S8), che la sistemazione porta al backend perché lo dia al
  // prodotto se non ne ha. Solo quella scelta lo porta: il prodotto trovato dal
  // codice ce l'ha già, e quello creato a mano lo riceve alla creazione
  | { kind: "product"; product: Product; barcode?: string };

/** Chi apre un pannello sotto una voce: due delle tre icone di una voce con
 * l'ingrediente (il codice, il catalogo), e «Abbina» di una voce senza. Lo sfuso non
 * apre niente: è già una scelta. */
export type PanelTrigger = "scanner" | "catalog" | "match";

/** Dove va il fuoco quando la riga rinasce: al pulsante che aveva aperto il pannello,
 * o a «Cambia» quando la voce è stata risolta e le tre icone non ci sono più. */
export type FocusTarget = PanelTrigger | "change";

/** Una voce del corpo di `POST /shopping-list/stock`. */
export type StockEntry = Parameters<typeof stockItems>[0][number];

/** Le voci che «Metti in dispensa» manda, nell'ordine della lista. Una fonte sola per
 * il corpo della richiesta e per il numero sul pulsante (spec T3 §4.3, «Metti in
 * dispensa 4»): contati a parte, i due si scollerebbero proprio sulla voce che non
 * parte — scelta ma senza ingrediente, o sparita dalla lista riletta.
 *
 * Parte chi ha una scelta e un ingrediente. `ingredientOf` dice quello della voce: dalla
 * lista, o abbinato in questo schermo (S19). */
export function stockEntries(
  items: ShoppingItem[],
  resolved: Record<string, Resolution>,
  ingredientOf: (item: ShoppingItem) => string | null,
  expiry: Record<string, string>
): StockEntry[] {
  const entries: StockEntry[] = [];
  for (const item of items) {
    const resolution = resolved[item.id];
    const ingredientId = ingredientOf(item);
    if (!resolution || !ingredientId) continue;
    entries.push({
      shopping_item_id: item.id,
      ingredient_id: ingredientId,
      product_id: resolution.kind === "product" ? resolution.product.id : null,
      // sempre presente, mai assente: una riga senza scadenza manda `null`.
      //
      // `||` e non `??`, e la differenza è tutta qui: svuotare il campo data (un
      // Backspace su un segmento basta) lascia la stringa vuota, e `''` non è una
      // data — il backend risponde 422, il messaggio dice «riprova», e il riprova
      // ricostruisce lo stesso corpo identico all'infinito. `PantryRow.commitExpiry`
      // fa la stessa cosa nello stesso modo: le due forme devono restare uguali.
      expires_on: expiry[item.id] || null,
      // sempre presente come la scadenza; `null` per lo sfuso e per ogni prodotto che
      // non è stato scelto a catalogo dopo un codice letto
      barcode: (resolution.kind === "product" && resolution.barcode) || null,
    });
  }
  return entries;
}

/** L'avviso che arriva in Dispensa dopo «Metti in dispensa» (T4, spec T3 §4.3).
 * `checked` è quante voci erano nel carrello: quelle non mandate restano in lista,
 * spuntate. Le voci ancora da comprare non contano — non erano in questa spesa
 * (deciso con Mattia il 2026-09-29). Se sono entrate tutte, della lista non si dice
 * niente. */
export function stockNotice(sent: number, checked: number): string {
  const head = `${sent} in dispensa`;
  const left = checked - sent;
  if (left <= 0) return head;
  return `${head} · ${left} ${left === 1 ? "resta" : "restano"} in lista`;
}
