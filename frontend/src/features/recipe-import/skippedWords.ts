import type { RequeueResult, SkipCause } from "../../domain/types";

// Le parole delle pagine scartate (spec 2026-10-09-scartate-in-coda §4). Funzioni pure in
// un file loro: si provano frase per frase senza montare la schermata, e la schermata non
// decide niente — traduce i codici che il backend ha già deciso.

export function skippedTitle(count: number): string {
  return `Scartate (${count})`;
}

// la strada, scritta nella riga e non solo nell'avviso: la riga resta, l'avviso no
const NON_FOOD_WAY =
  "Rendilo un alimento in Anagrafica, o annulla la decisione che lo ha scelto; poi rimettila in coda.";

/** Il perché di una scartata, con la strada per correggerlo dove ce n'è una. */
export function skipReasonText(cause: SkipCause, nonFoodName: string | null): string {
  switch (cause) {
    case "non_food":
      return nonFoodName
        ? `Fra gli ingredienti c'è «${nonFoodName}», che non è un alimento. ${NON_FOOD_WAY}`
        : `Uno degli ingredienti non è un alimento. ${NON_FOOD_WAY}`;
    case "all_ignored":
      return "Tutti i suoi ingredienti sono ignorati, e una ricetta senza ingredienti non entra nel ricettario. Annulla la decisione su uno di loro; poi rimettila in coda.";
    case "unreadable":
      return "Sul sito la pagina non aveva una ricetta leggibile: rimetterla in coda non cambierebbe niente.";
    case "other":
      return "Non è entrata nel ricettario durante l'import.";
  }
}

export function cookingWaitingText(count: number): string {
  return count === 1
    ? "1 cottura registrata aspetta questa ricetta."
    : `${count} cotture registrate aspettano questa ricetta.`;
}

/** «A», «A» e «B», «A», «B» e «C». */
function quotedList(names: string[]): string {
  const quoted = names.map((name) => `«${name}»`);
  if (quoted.length === 1) return quoted[0];
  return `${quoted.slice(0, -1).join(", ")} e ${quoted[quoted.length - 1]}`;
}

function waitingPart(terms: string[]): string {
  if (terms.length === 0) return "aspetta che i suoi ingredienti siano decisi";
  if (terms.length === 1) return `aspetta la decisione su «${terms[0]}»`;
  if (terms.length <= 3) return `aspetta le decisioni su ${quotedList(terms)}`;
  const shown = terms
    .slice(0, 3)
    .map((name) => `«${name}»`)
    .join(", ");
  const rest = terms.length - 3;
  return `aspetta le decisioni su ${shown} e ${rest === 1 ? "un altro" : `altri ${rest}`}`;
}

function stillSkippedPart(cause: SkipCause | null, nonFoodName: string | null): string {
  if (cause === "non_food")
    return nonFoodName
      ? `: «${nonFoodName}» non è un alimento`
      : ": un ingrediente non è un alimento";
  if (cause === "all_ignored") return ": tutti i suoi ingredienti sono ignorati";
  return "";
}

/** L'avviso dopo «Rimetti in coda»: com'è finita quella pagina. Corto quando non è
 * riuscita: la strada per correggere resta scritta nella sua riga. */
export function requeueResultMessage(result: RequeueResult): string {
  const name = `«${result.title ?? result.url}»`;
  if (result.outcome === "imported") {
    const count = result.cooking_relinked;
    const cooking =
      count === 0 ? "" : count === 1 ? " Ha ritrovato 1 cottura." : ` Ha ritrovato ${count} cotture.`;
    return `${name} è entrata nel ricettario.${cooking}`;
  }
  if (result.outcome === "waiting")
    return `${name} è tornata in coda: ${waitingPart(result.waiting_terms)}.`;
  return `${name} è ancora scartata${stillSkippedPart(result.cause, result.non_food_name)}.`;
}
