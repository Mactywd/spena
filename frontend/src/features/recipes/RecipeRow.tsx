import { Fragment, type ReactNode } from "react";
import { Link } from "react-router-dom";
import type { RecipeSummary } from "../../domain/types";
import { CostMeter } from "../../components/ui/CostMeter";
import { RecipeThumb } from "./RecipeThumb";

const MAX_NAMES = 3;

/** I mancanti, tagliati dove la riga smetterebbe di leggersi.
 *
 * Il taglio lo fa il client e non il server: è qui che si sa quanto spazio c'è, e il
 * server manda la lista intera. Con un gradino della scala acceso non si taglia mai — la
 * soglia arriva a tre — e si taglia solo su «Tutte», dove a una ricetta possono mancare
 * dodici cose e la riga diventerebbe più lunga del titolo.
 */
function missingNamesLabel(names: string[]): string {
  if (names.length <= MAX_NAMES) return names.join(", ");
  const altri = names.length - MAX_NAMES;
  return `${names.slice(0, MAX_NAMES).join(", ")} e ${altri === 1 ? "un altro" : `altri ${altri}`}`;
}

/** «Hai tutto», o «Manca: …» coi nomi (spec T3 §4.5; dal giro: i mancanti si leggevano
 * come un sottotitolo).
 *
 * Risponde a `cookable`, il verdetto del backend, e non a `missing === 0`: dedurre il
 * verdetto da un conteggio è il frontend che rifà un calcolo di dominio. I nomi vengono
 * dalla stessa regola del verdetto, quindi a una ricetta non cucinabile ne manca almeno
 * uno; se un giorno non fosse così, la riga dice il numero invece di «Manca:» e niente.
 */
function availabilityLabel(recipe: RecipeSummary): string {
  if (recipe.cookable) return "Hai tutto";
  if (recipe.missing_names.length > 0) return `Manca: ${missingNamesLabel(recipe.missing_names)}`;
  return recipe.missing === 1 ? "Manca 1 ingrediente" : `Mancano ${recipe.missing} ingredienti`;
}

/** Preparazione più cottura, quando almeno uno dei due c'è: «cucinabile ora» più «venti
 * minuti» è una risposta, «cucinabile ora» da solo è metà risposta. */
function totalMinutes(recipe: RecipeSummary): number | null {
  const total = (recipe.prep_minutes ?? 0) + (recipe.cook_minutes ?? 0);
  return total > 0 ? total : null;
}

/** Una riga del ricettario (spec T3 §4.5): miniatura, titolo su al più due righe, cosa
 * manca, e sotto categoria · costo (`CostMeter`) · minuti. Righe compatte al posto delle
 * schede con la foto a tutta larghezza, alte 386 px (dal giro): la prima ricetta sale
 * nella prima schermata. Provenienza e descrizione non ci stanno più: la prima diceva
 * «dataset» a chi non sa cosa sia, la seconda la dice il dettaglio. */
export function RecipeRow({ recipe }: { recipe: RecipeSummary }) {
  const minutes = totalMinutes(recipe);
  // categoria · costo · minuti, ciascuno solo se c'è: un «·» davanti a niente è rumore
  const details: ReactNode[] = [];
  if (recipe.category) {
    details.push(
      <span key="category" className="min-w-0 truncate">
        {recipe.category}
      </span>
    );
  }
  if (recipe.cost !== null) details.push(<CostMeter key="cost" cost={recipe.cost} />);
  if (minutes !== null) {
    details.push(
      <span key="minutes" className="shrink-0">
        {minutes} min
      </span>
    );
  }
  return (
    <li>
      <Link to={`/ricette/${recipe.id}`} className="flex items-center gap-3 py-2">
        <RecipeThumb imageUrl={recipe.image_url} department={recipe.main_department} />
        <span className="flex min-w-0 flex-1 flex-col gap-0.5">
          <span className="line-clamp-2 font-medium">{recipe.title}</span>
          {/* verde «Hai tutto», rosso «Manca»: il rosso è quello che la spec §3.1 dà
              all'ingrediente che manca, lo stesso del pallino del dettaglio */}
          <span
            className={`text-sm font-medium ${recipe.cookable ? "text-brand" : "text-finished"}`}
          >
            {availabilityLabel(recipe)}
          </span>
          {details.length > 0 && (
            <span className="flex min-w-0 flex-wrap items-center gap-x-1.5 text-xs text-ink-faint">
              {details.map((detail, n) => (
                <Fragment key={n}>
                  {n > 0 && <span aria-hidden="true">·</span>}
                  {detail}
                </Fragment>
              ))}
            </span>
          )}
        </span>
      </Link>
    </li>
  );
}
