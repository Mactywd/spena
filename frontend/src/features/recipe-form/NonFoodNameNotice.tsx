import { Link } from "react-router-dom";
import { IconExternalLink } from "../../components/ui/icons";
import type { Ingredient } from "../../domain/types";
import { ingredientPath } from "../registry/origin";

/** L'avviso del passo del nome quando il nome è un non alimentare dell'anagrafica (piano
 * 20). Dice cosa fare, perché non sia un vicolo cieco: un altro nome, o correggere
 * l'anagrafica se è lei a sbagliare. «Questo nome è «…»» e non ««…» è»: il nome scritto
 * può essere un alias, e la voce da correggere è quella dell'anagrafica.
 *
 * Il collegamento apre la scheda dell'ingrediente in un'altra scheda del browser: uscire
 * dal modulo perderebbe la ricetta scritta fin qui. Tornati, `useNonFoodName` rifà la
 * domanda da sé. */
export function NonFoodNameNotice({ ingredient }: { ingredient: Ingredient }) {
  return (
    <div role="status" className="flex flex-col gap-1">
      <p className="text-xs text-low">
        In anagrafica questo nome è «{ingredient.display_name}», un non alimentare: una ricetta
        non può averlo. Scrivi un altro nome; se invece è l'anagrafica a sbagliare, correggila.
      </p>
      <Link
        to={ingredientPath(ingredient.id, null)}
        target="_blank"
        rel="noopener"
        className="inline-flex min-h-11 items-center gap-1.5 self-start text-sm font-medium text-brand"
      >
        <IconExternalLink aria-hidden="true" className="size-[1.1em]" stroke={1.8} />
        Correggi «{ingredient.display_name}» in Anagrafica
      </Link>
      <p className="text-xs text-ink-soft">Si apre a parte: la ricetta resta qui com'è.</p>
    </div>
  );
}
