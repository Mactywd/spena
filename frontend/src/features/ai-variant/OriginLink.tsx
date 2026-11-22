import { Link } from "react-router-dom";
import type { RecipeOrigin } from "../../domain/types";

/** Sotto il titolo di una variante, la ricetta da cui nasce (R8; Mattia: «Variante di
 * «…»» che porta all'originale). Eliminata, lo dice come l'Anagrafica dice le ricette
 * eliminate — «(eliminata)» — e porta lo stesso al suo dettaglio, cioè alla lapide con
 * «Ripristina» (R10). Alto 44 px come «Apri l'originale»; `break-words` perché un titolo
 * lungo vada a capo invece di allargare la pagina a 375 px. */
export function OriginLink({ origin }: { origin: RecipeOrigin }) {
  return (
    <Link
      to={`/ricette/${origin.id}`}
      className="inline-flex min-h-11 max-w-full items-center text-sm font-medium break-words text-brand"
    >
      {`Variante di «${origin.title}»${origin.archived ? " (eliminata)" : ""}`}
    </Link>
  );
}
