import type { ShoppingItem } from "../../domain/types";

/** Le voci come la Lista le mostra (spec T3 §4.2): un gruppo per reparto, in ordine
 * alfabetico, e il reparto ignoto in fondo — sono le voci da chiarire. Dentro ogni
 * reparto le voci nel carrello vanno in fondo (dal giro: «le voci spuntate restano in
 * mezzo alle altre»), così quel che manca ancora si legge per primo. Fra voci dello
 * stesso stato l'ordine è quello del server: `sort` è stabile. */
export function groupForDisplay(items: ShoppingItem[]): [string | null, ShoppingItem[]][] {
  const groups = new Map<string | null, ShoppingItem[]>();
  for (const item of items) {
    const key = item.ingredient_category;
    groups.set(key, [...(groups.get(key) ?? []), item]);
  }
  const rank = (item: ShoppingItem) => (item.status === "checked" ? 1 : 0);
  return [...groups.entries()]
    .sort(([a], [b]) => (a === null ? 1 : b === null ? -1 : a.localeCompare(b)))
    .map(([category, rows]) => [category, [...rows].sort((x, y) => rank(x) - rank(y))]);
}

/** La nota della scheda «Sistema la spesa», la stessa in Lista e in Dispensa (spec
 * §4.2: «Sistema la spesa · N nel carrello»). `null` quando il numero non si conosce —
 * la lista non è ancora arrivata, o non è arrivata affatto: allora non si dice niente
 * del suo contenuto, perché «niente nel carrello» sarebbe una bugia, e la strada resta
 * aperta (D3 di `docs/prossimi-passi.md`). */
export function entryNote(inCart: number | null): string {
  if (inCart === null) return "Metti via quello che hai comprato";
  if (inCart === 0) return "Niente nel carrello, per ora";
  return `${inCart} nel carrello`;
}
