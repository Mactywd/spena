import type { IngredientUsage, MergeCounts, ProductDetail } from "../../domain/types";

/** Dove è usato un ingrediente, in una riga: «in 42 ricette · 1 in dispensa · in lista».
 * Il peso di una correzione, detto prima di farla (spec §6.3). */
export function usageText(usage: IngredientUsage): string {
  const parts = [
    usage.recipes === 0
      ? "in nessuna ricetta"
      : usage.recipes === 1
        ? "in 1 ricetta"
        : `in ${usage.recipes} ricette`,
  ];
  if (usage.pantry > 0) parts.push(`${usage.pantry} in dispensa`);
  if (usage.shopping > 0) parts.push("in lista");
  return parts.join(" · ");
}

type Part = { n: number; one: string; many: string };

/** Quel che una fusione sposta, nell'ordine in cui interessa: prima le ricette, per
 * ultimi gli alias. Una parte a zero non si dice. */
function movedParts(counts: MergeCounts): Part[] {
  return [
    { n: counts.recipes_rebuilt + counts.recipe_lines_moved, one: "ricetta", many: "ricette" },
    { n: counts.pantry_items, one: "elemento di dispensa", many: "elementi di dispensa" },
    { n: counts.shopping_items, one: "voce di lista", many: "voci di lista" },
    { n: counts.products, one: "prodotto", many: "prodotti" },
    { n: counts.aliases, one: "alias", many: "alias" },
  ].filter((part) => part.n > 0);
}

function listed(parts: Part[]): string {
  return parts.map((part) => `${part.n} ${part.n === 1 ? part.one : part.many}`).join(", ");
}

/** Le voci attive del perdente che la fusione toglie, perché il vincitore era già in
 * lista: dirlo, altrimenti una voce sparisce dalla lista senza che nessuno l'abbia
 * tolta. `done` sceglie il tempo del verbo, anteprima o esito. */
function droppedText(counts: MergeCounts, done: boolean): string {
  const n = counts.shopping_items_dropped;
  if (n === 0) return "";
  const where = `«${counts.winner_name}» ${done ? "era" : "è"} già in lista:`;
  if (n === 1) {
    return `${where} la voce di «${counts.loser_name}» ${done ? "è stata tolta" : "si toglie"}.`;
  }
  return `${where} le ${n} voci di «${counts.loser_name}» ${done ? "sono state tolte" : "si tolgono"}.`;
}

/** L'anteprima della fusione (spec §6.3): «Si spostano 3 ricette, 1 elemento di
 * dispensa, 2 alias. «pomodori» diventa un alias di «pomodoro». Non si annulla.» Le
 * cotture si dicono quando ci sono, perché chi fonde lo vuole sapere (§5.2). */
export function mergePreviewText(counts: MergeCounts): string {
  const parts = movedParts(counts);
  const verb = parts.length === 1 && parts[0].n === 1 ? "Si sposta" : "Si spostano";
  const moved = parts.length === 0 ? "Non si sposta niente." : `${verb} ${listed(parts)}.`;
  const n = counts.cooking_events_relinked;
  const cooked =
    n === 0
      ? ""
      : n === 1
        ? "1 cottura già registrata ritrova la sua ricetta."
        : `${n} cotture già registrate ritrovano la loro ricetta.`;
  return [
    moved,
    droppedText(counts, false),
    `«${counts.loser_name}» diventa un alias di «${counts.winner_name}».`,
    cooked,
    "Non si annulla.",
  ]
    .filter((sentence) => sentence !== "")
    .join(" ");
}

/** L'esito, in vista sulla scheda del vincitore dopo la fusione. */
export function mergeDoneText(counts: MergeCounts): string {
  const parts = movedParts(counts);
  return [
    `Uniti: «${counts.loser_name}» ora è un alias di «${counts.winner_name}».`,
    parts.length === 0 ? "" : `Spostati qui: ${listed(parts)}.`,
    droppedText(counts, true),
  ]
    .filter((sentence) => sentence !== "")
    .join(" ");
}

/** Sopra questa soglia la fusione del perdente prende minuti, non secondi: misurato
 * su dati di produzione, circa 130s per calcolare l'anteprima e 125s per la fusione
 * vera, ed è per questo che nginx ora concede 300s su questa rotta (deciso con Mattia
 * al Task 11). Sotto la soglia non si avvisa: un avviso per un'attesa che non c'è
 * insegna a ignorarlo la volta buona. */
export const MERGE_SLOW_RECIPE_THRESHOLD = 1000;

/** L'avviso dei tempi lunghi, da mostrare appena si sceglie il vincitore — prima
 * ancora che l'anteprima risponda — quando il perdente è in più di
 * `MERGE_SLOW_RECIPE_THRESHOLD` ricette. `null` sotto la soglia: niente da dire. */
export function mergeSlowWarning(loserRecipeCount: number): string | null {
  return loserRecipeCount > MERGE_SLOW_RECIPE_THRESHOLD
    ? "Può volerci qualche minuto: questo ingrediente è in più di 1.000 ricette."
    : null;
}

function pantryItems(n: number): string {
  return n === 1 ? "1 elemento" : `${n} elementi`;
}

/** Dopo lo spostamento (spec §6.4): «Spostato sotto «parmigiano», con 1 elemento di
 * dispensa». Il conto è quello degli attivi che il server rimanda, cioè quelli che la
 * dispensa mostra. */
export function movedText(product: ProductDetail): string {
  const n = product.pantry_items.length;
  const where = `Spostato sotto «${product.ingredient.display_name}»`;
  return n === 0 ? `${where}.` : `${where}, con ${pantryItems(n)} di dispensa.`;
}

/** Quando lo spostamento di un alias lo fa sparire invece di spostarlo
 * (`AliasMovedOut.alias: null`, `backend/app/services/registry.py` — `move_alias`):
 * il testo esisteva già, come nome o come alias, sul bersaglio o su un terzo
 * ingrediente, e `remember_alias` lo scarta invece di raddoppiarlo. Va detto, non
 * lasciato sparire muto (rilievo della revisione finale S9). */
export function aliasVanishedText(aliasText: string, targetName: string): string {
  return (
    `«${aliasText}» esisteva già — come nome o alias, qui o su un altro ingrediente — ` +
    `e non si è spostato sotto «${targetName}»: è scomparso invece di raddoppiarsi.`
  );
}

export function pantryText(n: number): string {
  return n === 0 ? "Nessun elemento in dispensa." : `${pantryItems(n)} in dispensa.`;
}
