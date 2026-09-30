import { addShoppingItem } from "../shopping-list/api";
import type { RecipeIngredientLine } from "../../domain/types";

/** Com'è andata «Metti in lista ciò che manca» (spec T3 §4.6): quante voci sono entrate
 * in lista, quante c'erano già — il server non scrive il doppione e risponde con la voce
 * che c'era, `added` falso (S18) — e quali righe non sono arrivate, da rimandare con
 * «Riprova». */
export type MissingOutcome = {
  added: number;
  already: number;
  failed: RecipeIngredientLine[];
};

/** Una `POST /shopping-list` per riga, tutte insieme. Quali righe mancano non si decide
 * qui: le passa chi chiama, filtrate su `satisfied`, che arriva dal server (la regola
 * primario/secondario vive nel backend). Il testo della voce è il nome dell'ingrediente,
 * e l'ingrediente va con lui: così la voce nasce agganciata, e un doppione non nasce.
 *
 * `allSettled` e non `all`: una riga che non arriva non deve far dimenticare quelle
 * arrivate, che in lista ci sono davvero. Per questo la promessa non rifiuta mai. */
export async function sendMissing(lines: RecipeIngredientLine[]): Promise<MissingOutcome> {
  const results = await Promise.allSettled(
    lines.map((line) => addShoppingItem(line.ingredient_name, line.ingredient_id))
  );
  const outcome: MissingOutcome = { added: 0, already: 0, failed: [] };
  results.forEach((result, index) => {
    if (result.status === "rejected") outcome.failed.push(lines[index]);
    else if (result.value.added) outcome.added += 1;
    else outcome.already += 1;
  });
  return outcome;
}

/** La frase dell'avviso. Numeri e non nomi: l'avviso è una riga sola, e i nomi sono
 * già a video, sulla ricetta. */
export function missingNotice({ added, already, failed }: MissingOutcome): string {
  if (failed.length === 0 && added === 0) return "Era già tutto in lista.";
  if (added === 0 && already === 0) return "Non è andata: la lista è com'era.";
  const parts: string[] = [];
  if (added > 0) parts.push(`${added} in lista`);
  if (already > 0) parts.push(already === 1 ? "1 c'era già" : `${already} c'erano già`);
  if (failed.length > 0) {
    parts.push(failed.length === 1 ? "1 non è andata" : `${failed.length} non sono andate`);
  }
  return parts.join(" · ");
}
