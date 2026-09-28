import type { PantryItem } from "../../domain/types";

/** Il nome con cui l'utente chiama questa voce: il prodotto se c'è, l'ingrediente
 * altrimenti. Entra nei nomi accessibili dei controlli della riga («Togli Total 0%
 * dalla dispensa»), perché due barattoli dello stesso ingrediente vanno distinti. */
export function itemLabel(item: PantryItem): string {
  return item.product_name ?? item.ingredient_name;
}

// minuscole e senza accenti: chi cerca «caffe» vuole il caffè
function fold(text: string): string {
  return text.normalize("NFD").replace(/\p{M}/gu, "").toLowerCase().trim();
}

/** Se la voce risponde a quel che è scritto nella barra (S11). Guarda ingrediente,
 * prodotto e marca: si cerca «fage» come si cerca «yogurt». */
export function matchesQuery(item: PantryItem, query: string): boolean {
  const wanted = fold(query);
  if (!wanted) return true;
  return [item.ingredient_name, item.product_name, item.product_brand].some(
    (field) => field !== null && fold(field).includes(wanted)
  );
}

/** Se la voce entra nel riepilogo delle scadenze. Il verdetto è del backend
 * (`expiry`); qui si toglie solo ciò che è finito, perché un barattolo vuoto non ha
 * più niente da consumare in tempo. */
export function isExpiring(item: PantryItem): boolean {
  return item.expiry !== null && item.status !== "finished";
}

/** Se la voce resta in vista col riepilogo premuto. Non è `isExpiring`: il conteggio
 * lascia fuori le finite, la vista no. Una voce segnata «Finito» dal filtro deve
 * restare lì, in fondo alla sua sezione, con il suo «In lista»: sparire sotto le dita
 * si porterebbe via proprio la strada che rimette in lista quel che è finito. */
export function hasExpiry(item: PantryItem): boolean {
  return item.expiry !== null;
}

export function expiryCounts(items: PantryItem[]): { soon: number; expired: number } {
  let soon = 0;
  let expired = 0;
  for (const item of items) {
    if (!isExpiring(item)) continue;
    if (item.expiry === "soon") soon += 1;
    else expired += 1;
  }
  return { soon, expired };
}

/** Il testo del riepilogo in cima alla dispensa, `null` se non c'è niente da dire:
 * il riepilogo compare solo quando serve (spec T3 §4.1). «Oltre la scadenza» e non
 * «scaduti»: il participio sbaglierebbe l'accordo su metà delle voci. */
export function expirySummary(counts: { soon: number; expired: number }): string | null {
  const parts: string[] = [];
  if (counts.soon > 0) parts.push(`${counts.soon} in scadenza questa settimana`);
  if (counts.expired > 0) parts.push(`${counts.expired} oltre la scadenza`);
  return parts.length > 0 ? parts.join(" · ") : null;
}

/** Le sezioni a video: reparti in ordine alfabetico; dentro, l'ordine del server
 * (stabile da S21) con le voci finite in fondo (spec T3 §4.1). Il filtro è stabile:
 * le finite restano fra loro nell'ordine in cui arrivano. */
export function groupForDisplay(items: PantryItem[]): [string, PantryItem[]][] {
  const groups = new Map<string, PantryItem[]>();
  for (const item of items) {
    groups.set(item.ingredient_category, [...(groups.get(item.ingredient_category) ?? []), item]);
  }
  return [...groups.entries()]
    .sort(([a], [b]) => a.localeCompare(b))
    .map(([category, rows]) => [
      category,
      [...rows.filter((r) => r.status !== "finished"), ...rows.filter((r) => r.status === "finished")],
    ]);
}
